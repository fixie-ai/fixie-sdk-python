import argparse
import asyncio
import audioop
import base64
import json
import logging
from typing import AsyncGenerator

import aiohttp.web

from fixie_sdk.voice import audio_base
from fixie_sdk.voice import types
from fixie_sdk.voice.session import VoiceSession
from fixie_sdk.voice.session import VoiceSessionParams


class PhoneAudioSink(audio_base.AudioSink):
    """AudioSink that plays to the phone stream."""

    def __init__(self) -> None:
        super().__init__()
        self._queue: asyncio.Queue[bytes] = asyncio.Queue()

    async def start(self, sample_rate: int = 8000, num_channels: int = 1):
        pass

    async def write(self, chunk: bytes) -> None:
        await self._queue.put(chunk)

    def read(self) -> bytes:
        return self._queue.get_nowait()

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
    await ws.prepare(request)
    logging.info("Websocket connection ready")

    source = PhoneAudioSource()
    sink = PhoneAudioSink()
    params = VoiceSessionParams(
        agent_id=args.agent,
        tts_voice=args.tts_voice,
    )
    session = VoiceSession(source, sink, params)

    # Set up the event handlers for the voice session.
    @session.on("state")
    async def on_state(state):
        if state == types.SessionState.LISTENING:
            print("User:  ", end="\r")
        elif state == types.SessionState.THINKING:
            print("Agent:  ", end="\r")

    @session.on("input")
    async def on_input(text, final):
        print("User:  " + text, end="\n" if final else "\r")

    @session.on("output")
    async def on_output(text, final):
        print("Agent: " + text, end="\n" if final else "\r")

    @session.on("latency")
    async def on_latency(metric, value):
        logging.info(f"[session] latency: {metric.value}={value}")

    @session.on("error")
    async def on_error(error):
        print(f"Error: {error}")

    stream_sid = ""
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

                try:
                    chunk = sink.read()
                    ulaw = audioop.lin2ulaw(chunk, 2)
                    payload = base64.b64encode(ulaw).decode("utf-8")
                    media_data = {
                        "event": "media",
                        "streamSid": stream_sid,
                        "media": {"payload": payload},
                    }
                    await ws.send_json(media_data)
                except asyncio.QueueEmpty:
                    pass

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
    aiohttp.web.run_app(app, host="localhost", port=5000)
