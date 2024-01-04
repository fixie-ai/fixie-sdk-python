import argparse
import asyncio
import audioop
import base64
import json
import logging
import time
from typing import AsyncGenerator

import aiohttp.web
import numpy
import soxr
from pyee import asyncio as pyee_asyncio

from fixie_sdk.voice import audio_base
from fixie_sdk.voice import types
from fixie_sdk.voice.session import VoiceSession
from fixie_sdk.voice.session import VoiceSessionParams

# Make sure our logger is configured to show info messages.
logging.basicConfig(level=logging.INFO)


class PhoneAudioSink(audio_base.AudioSink, pyee_asyncio.AsyncIOEventEmitter):
    """AudioSink that plays to the phone stream."""

    def __init__(self) -> None:
        super().__init__()

    async def start(self, sample_rate: int, num_channels: int):
        self._sample_rate = sample_rate

    async def write(self, chunk: bytes) -> None:
        sample = numpy.frombuffer(chunk, numpy.int16).astype(numpy.float32)
        resampled = soxr.resample(sample, 48000, 8000).astype(numpy.int16)
        ulaw = audioop.lin2ulaw(resampled.tobytes(), 2)
        self.emit("data", ulaw)

    async def close(self) -> None:
        pass


class PhoneAudioSource(audio_base.AudioSource):
    """AudioSource that reads from the phone stream."""

    def __init__(self, sample_rate=8000, channels=1):
        super().__init__(sample_rate, channels)
        self._queue: asyncio.Queue[bytes] = asyncio.Queue()

    async def write(self, chunk: bytes) -> None:
        decoded = audioop.ulaw2lin(chunk, 2)
        await self._queue.put(decoded)

    async def stream(self) -> AsyncGenerator[bytes, None]:
        while True:
            buf = await self._queue.get()
            yield buf if self.enabled else b"\x00" * len(buf)


async def testhandle(request):
    return aiohttp.web.Response(text="Hello Fixie!")


async def websocket_handler(request):
    logging.info("Websocket connection starting")
    ws = aiohttp.web.WebSocketResponse()
    ws_prepare_start_time = time.perf_counter()
    await ws.prepare(request)
    ws_prepare_total_time = time.perf_counter() - ws_prepare_start_time
    logging.info(
        f"Websocket connection ready. Took {ws_prepare_total_time * 1000} milliseconds"
    )

    source = PhoneAudioSource()
    sink = PhoneAudioSink()
    params = VoiceSessionParams(
        agent_id=args.agent,
        tts_voice=args.tts_voice,
    )
    session = VoiceSession(source, sink, params)
    stream_sid = ""

    @sink.on("data")
    async def on_sink_data(data):
        payload = base64.b64encode(data).decode()
        media_data = {
            "event": "media",
            "streamSid": stream_sid,
            "media": {"payload": payload},
        }
        await ws.send_json(media_data)

    # Set up the event handlers for the voice session.
    @session.on("state")
    async def on_state(state):
        if state == types.SessionState.LISTENING:
            logging.info("State:  Listening")
        elif state == types.SessionState.THINKING:
            logging.info("State:  Thinking")

    @session.on("input")
    async def on_input(text, final):
        if final:
            logging.info("User:  " + text)

    @session.on("output")
    async def on_output(text, final):
        if final:
            logging.info("Agent: " + text)

    @session.on("latency")
    async def on_latency(metric, value):
        logging.info(f"[session] latency: {metric.value}={value}")

    @session.on("error")
    async def on_error(error):
        logging.error(f"Error: {error}")

    async for msg in ws:
        if msg.type == aiohttp.WSMsgType.TEXT:
            # Messages are a JSON encoded string
            data = json.loads(msg.data)

            # Using the event type you can determine what type of msg you are receiving
            if data["event"] == "connected":
                logging.info(f"Received connected message={msg}")
                # Warm up the voice session by connecting to the server.
                await session.warmup()

            if data["event"] == "start":
                logging.info(f"Received start message={msg}")
                stream_sid = data["streamSid"]
                await session.start()

            if data["event"] == "media":
                payload = data["media"]["payload"]
                chunk = base64.b64decode(payload)
                await source.write(chunk)

            if data["event"] == "stop":
                logging.info(f"Received stop message={msg}")
                await session.stop()
                await ws.close()

    logging.info("Websocket connection closed")
    await session.stop()
    return ws


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--agent",
        "-a",
        type=str,
        default="5d37e2c5-1e96-4c48-b3f1-98ac08d40b9a",
        help="Agent ID to talk to",
    )
    parser.add_argument(
        "--tts-voice",
        "-V",
        type=str,
        default="Kp00queBTLslXxHCu1jq",
        help="TTS voice ID to use",
    )
    args = parser.parse_args()

    app = aiohttp.web.Application()
    app.router.add_route("GET", "/", testhandle)
    app.router.add_route("GET", "/media", websocket_handler)
    aiohttp.web.run_app(app, host="0.0.0.0", port=5000)
