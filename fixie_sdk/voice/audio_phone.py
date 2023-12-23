import asyncio
import base64
import json
from typing import AsyncGenerator

import aiohttp.web
import g711
import numpy

from fixie_sdk.voice import audio_base


class PhoneAudioSink(audio_base.AudioSink):
    """AudioSink that plays to the phone stream."""

    def __init__(self, ws: aiohttp.web.WebSocketResponse) -> None:
        super().__init__()
        self._ws = ws
        self._stream_sid = ""
        self._sequence_no = 0

    async def start(self, sample_rate: int = 8000, num_channels: int = 1):
        pass

    def stream_sid(self, value):
        self._stream_sid = value

    async def write(self, chunk: bytes) -> None:
        audio_data = numpy.frombuffer(chunk, dtype=numpy.int16).astype(numpy.float32)
        ulaw = g711.encode_ulaw(audio_data)
        pay_load = base64.b64encode(ulaw)
        # Send media message
        media_data = {
            "event": "media",
            "streamSid": self._stream_sid,
            "media": {"payload": pay_load},
        }
        media = json.dumps(media_data)
        await self._ws.send_str(media)

        # Send mark message
        mark_data = {
            "event": "mark",
            "streamSid": self._stream_sid,
            "mark": {"name": str(self._sequence_no)},
        }
        mark = json.dumps(mark_data)
        await self._ws.send_str(mark)
        self._sequence_no = self._sequence_no + 1

    async def close(self) -> None:
        pass


class PhoneAudioSource(audio_base.AudioSource):
    """AudioSource that reads from the phone stream."""

    def __init__(self, sample_rate=8000, channels=1):
        super().__init__(sample_rate, channels)
        self._queue: asyncio.Queue[bytes] = asyncio.Queue()

    async def write(self, chunk: bytes) -> None:
        decoded = g711.decode_ulaw(chunk).astype(numpy.int16)
        await self._queue.put(decoded)

    async def stream(self) -> AsyncGenerator[bytes, None]:
        while True:
            buf = await self._queue.get()
            yield buf if self.enabled else b"\x00" * len(buf)
