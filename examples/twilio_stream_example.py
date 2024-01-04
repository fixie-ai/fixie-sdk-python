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

from fixie_sdk.voice import audio_base
from fixie_sdk.voice.session import VoiceSession
from fixie_sdk.voice.session import VoiceSessionParams

# Maximum amount of audio data we will queue; we'll drop any additional data.
MAX_QUEUE_SIZE = 10  # 100 ms

# Make sure our logger is configured to show info messages.
logging.basicConfig(level=logging.INFO)


class PhoneAudioSink(audio_base.AudioSink):
    """AudioSink that queues up audio for the phone stream."""

    def __init__(self) -> None:
        super().__init__()
        self._queue: asyncio.Queue[bytes] = asyncio.Queue(MAX_QUEUE_SIZE)

    def get(self) -> bytes:
        return self._queue.get_nowait() or b"\x00\x00" * 80

    async def start(self, sample_rate: int, num_channels: int):
        self._sample_rate = sample_rate

    async def write(self, chunk: bytes) -> None:
        sample = numpy.frombuffer(chunk, numpy.int16)
        resampled = soxr.resample(sample, self._sample_rate, 8000).astype(numpy.int16)
        ulaw = audioop.lin2ulaw(resampled.tobytes(), 2)
        try:
            self._queue.put_nowait(ulaw)
        except asyncio.QueueFull:
            logging.warning("Dropping audio data; queue is full")

    async def close(self) -> None:
        pass


class PhoneAudioSource(audio_base.AudioSource):
    """AudioSource that reads from the phone stream."""

    def __init__(self, sample_rate: int = 8000, channels: int = 1):
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
    send_task = None

    async def send():
        while True:
            try:
                data = await sink.get()
                media_data = {
                    "event": "media",
                    "streamSid": stream_sid,
                    "media": {"payload": base64.b64encode(data).decode()},
                }
                await ws.send_json(media_data)
            except asyncio.CancelledError:
                break
            await asyncio.sleep(0.01)

    # Set up the event handlers for the voice session.
    @session.on("state")
    async def on_state(state):
        logging.info(f"State: {state}")

    @session.on("input")
    async def on_input(text, final):
        if final:
            logging.info("User: " + text)

    @session.on("output")
    async def on_output(text, final):
        if final:
            logging.info("Agent: " + text)

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
                    logging.info(f"Received connected message={msg}")
                    # Warm up the voice session by connecting to the server.
                    await session.warmup()

                case "start":
                    logging.info(f"Received start message={msg}")
                    stream_sid = data["streamSid"]
                    await session.start()
                    send_task = asyncio.create_task(send())

                case "media":
                    payload = data["media"]["payload"]
                    chunk = base64.b64decode(payload)
                    await source.write(chunk)

                case "stop":
                    logging.info(f"Received stop message={msg}")
                    if send_task:
                        send_task.cancel()
                        await send_task
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
        "--port", "-p", type=int, default=5000, help="Port to listen on"
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
