import asyncio
from typing import AsyncGenerator, Optional

from livekit import rtc

from fixie_sdk.voice import audio_base


class AudioSinkToSendTrack(audio_base.AudioSink):
    """AudioSink that owns and writes to a LiveKit audio track."""

    def __init__(self) -> None:
        super().__init__()
        self._sample_rate = 0
        self._num_channels = 0
        self._source: Optional[rtc.AudioSource] = None
        self._track: Optional[rtc.LocalAudioTrack] = None

    @property
    def sample_rate(self) -> int:
        return self._sample_rate

    @property
    def num_channels(self) -> int:
        return self._num_channels

    @property
    def track(self):
        if not self._track:
            raise Exception("track not initialized")
        return self._track

    async def start(self, sample_rate: int, num_channels: int):
        self._sample_rate = sample_rate
        self._num_channels = num_channels
        self._source = rtc.AudioSource(sample_rate, num_channels)
        self._track = rtc.LocalAudioTrack.create_audio_track("output", self._source)

    async def write(self, data: bytes):
        assert self._source is not None
        samples_per_channel = len(data) // (self._num_channels * 2)
        frame = rtc.AudioFrame(
            data, self._sample_rate, self._num_channels, samples_per_channel
        )
        await self._source.capture_frame(frame)

    async def close(self):
        pass


class AudioSourceFromRecvTrack(audio_base.AudioSource):
    """AudioSource that owns and reads from a LiveKit audio track."""

    def __init__(self, track: rtc.Track):
        super().__init__()
        self._stream = rtc.AudioStream(track)

    async def stream(self) -> AsyncGenerator[bytes, None]:
        async for frame in self._stream:
            buf = frame.data.tobytes()
            yield buf if self.enabled else b"\x00" * len(buf)


class AudioSourceToSendTrackAdapter:
    """Adapter than takes in an AudioSource and writes from it to a LiveKit audio track."""

    def __init__(self, source: audio_base.AudioSource):
        self._source = source
        self._rtc_source = rtc.AudioSource(source.sample_rate, source.num_channels)
        self._task: Optional[asyncio.Task] = None

    @property
    def enabled(self):
        return self._source.enabled

    @enabled.setter
    def enabled(self, value):
        self._source.enabled = value

    @property
    def track(self):
        if not self._track:
            raise Exception("track not initialized")
        return self._track

    async def start(self):
        self._track = rtc.LocalAudioTrack.create_audio_track("input", self._rtc_source)
        self._task = asyncio.create_task(self._pump())

    async def close(self):
        if self._task:
            self._task.cancel()
            self._task = None

    async def _pump(self):
        async for chunk in self._source.stream():
            frame = rtc.AudioFrame(
                chunk,
                self._source.sample_rate,
                self._source.num_channels,
                len(chunk) // (self._source.num_channels * 2),
            )
            await self._rtc_source.capture_frame(frame)


class AudioSinkFromRecvTrackAdapter:
    """Adapter that takes in a LiveKit audio track and reads from it to an AudioSink (e.g., a speaker)."""

    def __init__(self, sink: audio_base.AudioSink, track: rtc.Track):
        super().__init__()
        self._track = track
        self._stream = rtc.AudioStream(track=track)
        self._sink = sink
        self._task: Optional[asyncio.Task] = None

    async def start(self):
        await self._sink.start(48000, 1)  # ?
        self._task = asyncio.create_task(self._pump())

    async def close(self):
        if self._task:
            self._task.cancel()
            self._task = None
        await self._sink.close()

    async def _pump(self):
        async for chunk in self._stream:
            await self._sink.write(chunk.data.tobytes())
