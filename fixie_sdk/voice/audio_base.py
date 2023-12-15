import abc


class AudioSource(abc.ABC):
    """Base class for audio sources."""

    _sample_rate: int
    _num_channels: int
    _enabled: bool = True

    def __init__(self, sample_rate=48000, num_channels=1):
        self._sample_rate = sample_rate
        self._num_channels = num_channels

    @property
    def sample_rate(self) -> int:
        return self._sample_rate

    @property
    def num_channels(self) -> int:
        return self._num_channels

    @property
    def enabled(self) -> bool:
        return self._enabled

    @enabled.setter
    def enabled(self, enabled: bool):
        self._enabled = enabled

    @abc.abstractmethod
    async def stream(self):
        pass


class AudioSink(abc.ABC):
    """Abstract base class for audio sinks."""

    @abc.abstractmethod
    async def start(self, sample_rate: int, num_channels: int):
        """Called from TtsProvider.set_sink to prepare the stream."""

    @abc.abstractmethod
    async def write(self, data: bytes):
        """Called to write a chunk of PCM data with the specified format."""

    @abc.abstractmethod
    async def close(self):
        """Called from TtsProvider.close to tear down the stream."""


class NullAudioSink(AudioSink):
    """No-op audio sink."""

    async def start(self, sample_rate: int, num_channels: int):
        pass

    async def write(self, data: bytes):
        pass

    async def close(self):
        pass
