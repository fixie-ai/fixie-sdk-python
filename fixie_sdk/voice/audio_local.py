import asyncio
from typing import AsyncGenerator, Optional

import numpy as np
import pydub

from fixie_sdk.voice import audio_base

try:
    import sounddevice as sd

    sd_imported = True
except OSError:
    sd_imported = False


class LocalAudioSink(audio_base.AudioSink):
    """AudioSink that plays to the default audio device."""

    def __init__(self) -> None:
        super().__init__()
        self._queue: asyncio.Queue[bytes] = asyncio.Queue()
        self._stream: Optional[sd.OutputStream] = None

    async def start(self, sample_rate: int = 48000, num_channels: int = 1):
        if not sd_imported:
            raise RuntimeError("Failed to import sounddevice")

        def callback(outdata: np.ndarray, frame_count, time, status):
            try:
                data = self._queue.get_nowait()
            except asyncio.QueueEmpty:
                data = b"\x00" * len(outdata) * 2
            outdata[:] = np.frombuffer(data, dtype="int16").reshape(
                (frame_count, num_channels)
            )

        self._stream = sd.OutputStream(
            samplerate=sample_rate,
            channels=num_channels,
            callback=callback,
            device=None,
            dtype="int16",
            blocksize=sample_rate // 100,
        )
        self._stream.start()
        if not self._stream.active:
            raise RuntimeError("Failed to open audio output stream")

    async def write(self, chunk: bytes) -> None:
        await self._queue.put(chunk)

    async def close(self) -> None:
        if self._stream:
            self._stream.close()


class LocalAudioSource(audio_base.AudioSource):
    """AudioSource that reads from the default microphone."""

    def __init__(self, sample_rate=48000, channels=1):
        super().__init__(sample_rate, channels)

    async def stream(self) -> AsyncGenerator[bytes, None]:
        if not sd_imported:
            raise RuntimeError("Failed to import sounddevice")
        queue: asyncio.Queue[bytes] = asyncio.Queue()
        loop = asyncio.get_event_loop()

        def callback(indata: np.ndarray, frame_count, time, status):
            loop.call_soon_threadsafe(queue.put_nowait, indata.tobytes())

        stream = sd.InputStream(
            samplerate=self._sample_rate,
            channels=self._num_channels,
            callback=callback,
            device=None,
            dtype="int16",
            blocksize=self._sample_rate // 100,
        )
        with stream:
            if not stream.active:
                raise RuntimeError("Failed to open audio input stream")
            while True:
                buf = await queue.get()
                yield buf if self.enabled else b"\x00" * len(buf)


class WavAudioSource(audio_base.AudioSource):
    """AudioSource that reads from a WAV file."""

    _segment: pydub.AudioSegment

    def __init__(self, filename: str):
        self._segment = pydub.AudioSegment.from_wav(filename)
        super().__init__(self._segment.frame_rate, self._segment.channels)

    def set_enabled(self, enabled: bool):
        if not enabled:
            raise NotImplementedError()

    async def stream(self) -> AsyncGenerator[bytes, None]:
        return (chunk async for chunk in self._segment.raw_data)
