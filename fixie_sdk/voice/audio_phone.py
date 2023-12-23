import asyncio
from typing import AsyncGenerator

from fixie_sdk.voice import audio_base


class PhoneAudioSink(audio_base.AudioSink):
    """AudioSink that plays to the phone stream."""

    def __init__(self) -> None:
        super().__init__()
        self._queue: asyncio.Queue[bytes] = asyncio.Queue()

    async def start(self, sample_rate: int = 48000, num_channels: int = 1):
        pass

    async def write(self, chunk: bytes) -> None:
        pass

    async def close(self) -> None:
        pass


class PhoneAudioSource(audio_base.AudioSource):
    """AudioSource that reads from the phone stream."""

    def __init__(self, sample_rate=48000, channels=1):
        super().__init__(sample_rate, channels)

    async def stream(self) -> AsyncGenerator[bytes, None]:
        while True:
            yield b"\x00" * 960