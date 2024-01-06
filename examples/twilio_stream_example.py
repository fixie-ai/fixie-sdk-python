import argparse
import asyncio
import audioop
import base64
import json
import logging
import time
from typing import AsyncGenerator, Optional

import aiohttp.web
import numpy
import soxr
from pyee import asyncio as pyee_asyncio

from fixie_sdk.voice import audio_base
from fixie_sdk.voice.session import VoiceSession
from fixie_sdk.voice.session import VoiceSessionParams

# Maximum amount of audio data we will queue; we'll drop any additional data.
MAX_QUEUE_SIZE = 10  # 100 ms

# Make sure our logger is configured to show info messages.
logging.basicConfig(
    format="%(asctime)s.%(msecs)03d %(levelname)-8s %(message)s",
    level=logging.INFO,
    datefmt="%Y-%m-%d %H:%M:%S",
)


class PhoneAudioSink(audio_base.AudioSink, pyee_asyncio.AsyncIOEventEmitter):
    """AudioSink that queues up audio for the phone stream."""

    def __init__(self) -> None:
        super().__init__()

    async def start(self, sample_rate: int, num_channels: int):
        self._sample_rate = sample_rate

    async def write(self, chunk: bytes) -> None:
        self._started = True
        sample = numpy.frombuffer(chunk, numpy.int16)
        resampled = soxr.resample(sample, self._sample_rate, 8000).astype(numpy.int16)
        ulaw = audioop.lin2ulaw(resampled.tobytes(), 2)
        self.emit("data", ulaw)

    async def close(self) -> None:
        pass


class PhoneAudioSource(audio_base.AudioSource):
    """AudioSource that reads from the phone stream."""

    def __init__(self, sample_rate: int = 8000, channels: int = 1):
        super().__init__(sample_rate, channels)
        self._queue: asyncio.Queue[bytes] = asyncio.Queue(MAX_QUEUE_SIZE)
        self._started = False

    def write(self, chunk: bytes) -> None:
        if not self._started:
            return
        decoded = audioop.ulaw2lin(chunk, 2)
        try:
            self._queue.put_nowait(decoded)
        except asyncio.QueueFull:
            logging.warning("Dropping audio data; queue is full")

    async def stream(self) -> AsyncGenerator[bytes, None]:
        self._started = True
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
    ws_prepare_msec = (time.perf_counter() - ws_prepare_start_time) * 1000
    logging.info(f"Websocket connection ready, took {ws_prepare_msec:.0f} ms")

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
        assert stream_sid
        media_data = {
            "event": "media",
            "streamSid": stream_sid,
            "media": {"payload": base64.b64encode(data).decode()},
        }
        await ws.send_json(media_data)

    # Set up the event handlers for the voice session.
    @session.on("state")
    async def on_state(state):
        logging.info(f"State: {state}")

    @session.on("input")
    async def on_input(text, final):
        logging.info(f"User: {text}{' FINAL' if final else ''}")

    @session.on("output")
    async def on_output(text, final):
        logging.info(f"Agent: {text}{' FINAL' if final else ''}")

    @session.on("latency")
    async def on_latency(metric, value):
        logging.info(f"Latency: {metric.value}={value}")

    @session.on("error")
    async def on_error(error):
        logging.error(f"Error: {error}")

    async for msg in ws:
        if msg.type == aiohttp.WSMsgType.TEXT:
            # Messages are a JSON encoded string
            data = json.loads(msg.data)
            match data["event"]:
                case "connected":
                    # Connect to the voice server.
                    logging.info(f"Received connected message={data}")
                    await session.warmup()

                case "start":
                    # Publish our track to the voice server.
                    logging.info(f"Received start message={data}")
                    stream_sid = data["streamSid"]
                    await session.start()

                case "media":
                    # If we've published our track, forward the received
                    # audio to the voice server.
                    payload = data["media"]["payload"]
                    chunk = base64.b64decode(payload)
                    source.write(chunk)

                case "stop":
                    # Stop the voice session and close the websocket.
                    logging.info(f"Received stop message={data}")
                    await session.stop()
                    await ws.close()

    logging.info("Websocket connection closed")
    await session.stop()
    return ws


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--interface",
        "-i",
        type=str,
        default="localhost",
        help="Interface to listen on",
    )
    parser.add_argument(
        "--port",
        "-p",
        type=int,
        default=5000,
        help="Port to listen on",
    )
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
    aiohttp.web.run_app(app, host=args.interface, port=args.port)
