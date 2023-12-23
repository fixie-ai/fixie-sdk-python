import asyncio
from typing import AsyncGenerator

import g711
import numpy

from fixie_sdk.voice import audio_base


class PhoneAudioSink(audio_base.AudioSink):
    """AudioSink that plays to the phone stream."""

    def __init__(self) -> None:
        super().__init__()
        self._queue: asyncio.Queue[bytes] = asyncio.Queue()

    async def start(self, sample_rate: int = 8000, num_channels: int = 1):
        pass

    async def write(self, chunk: bytes) -> None:
        pass

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
