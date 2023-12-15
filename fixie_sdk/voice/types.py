import enum
import inspect
import json
import logging
import sys
from dataclasses import dataclass
from typing import Literal, Optional

from dataclasses_json import DataClassJsonMixin
from dataclasses_json import LetterCase
from dataclasses_json import config


class SessionState(enum.StrEnum):
    IDLE = "idle"
    LISTENING = "listening"
    THINKING = "thinking"
    SPEAKING = "speaking"


class SessionMetric(enum.StrEnum):
    ASR = "asr"
    LLM_FIRST_TOKEN = "llm"
    LLM_FIRST_UTTERANCE = "llmt"
    TTS = "tts"


class SessionError(enum.StrEnum):
    TTS_ERROR = "tts_error"


class Parameters(DataClassJsonMixin):
    """Base class for parameters, reads and writes camel case property names."""

    dataclass_json_config = config(letter_case=LetterCase.CAMEL)["dataclasses_json"]


class Message(DataClassJsonMixin):
    """Base class for client-server messages."""

    dataclass_json_config = config(letter_case=LetterCase.CAMEL)["dataclasses_json"]


@dataclass
class ASRParameters(Parameters):
    provider: Optional[str] = None
    language: Optional[str] = None
    model: Optional[str] = None
    base_url: Optional[str] = None


@dataclass
class TTSParameters(Parameters):
    provider: Optional[str] = None
    model: Optional[str] = None
    rate: float = 1.0
    voice: Optional[str] = None


@dataclass
class AgentParameters(Parameters):
    model: Optional[str] = None
    agent_id: Optional[str] = None
    conversation_id: Optional[str] = None


@dataclass
class RecordingParameters(Parameters):
    template_url: Optional[str] = None


@dataclass
class InitParameters(Parameters):
    asr: Optional[ASRParameters] = None
    tts: Optional[TTSParameters] = None
    agent: Optional[AgentParameters] = None
    recording: Optional[RecordingParameters] = None


# WebSocket messages


@dataclass(kw_only=True)
class InitMessage(Message):
    type: Literal["init"] = "init"
    params: InitParameters


@dataclass(kw_only=True)
class RoomInfoMessage(Message):
    type: Literal["room_info"] = "room_info"
    room_url: str
    token: str
    feature_flags: dict[str, str | bool | int | float]


# Datachannel messages


@dataclass(kw_only=True)
class InterruptMessage(Message):
    type: Literal["interrupt"] = "interrupt"


@dataclass(kw_only=True)
class LatencyMessage(Message):
    type: Literal["latency"] = "latency"
    kind: SessionMetric
    value: int


@dataclass(kw_only=True)
class OutputDeltaMessage(Message):
    type: Literal["output_delta"] = "output_delta"
    delta: str


@dataclass(kw_only=True)
class OutputCompleteMessage(Message):
    type: Literal["output"] = "output"
    text: str


@dataclass(kw_only=True)
class PingMessage(Message):
    type: Literal["ping"] = "ping"
    timestamp: float


@dataclass(kw_only=True)
class PongMessage(Message):
    type: Literal["pong"] = "pong"
    timestamp: float


@dataclass(kw_only=True)
class StateMessage(Message):
    type: Literal["state"] = "state"
    state: SessionState


@dataclass(kw_only=True)
class ConversationCreatedMessage(Message):
    type: Literal["conversation_created"] = "conversation_created"
    conversation_id: str


@dataclass(kw_only=True)
class ErrorMessage(Message):
    type: Literal["error"] = "error"
    error: SessionError
    message: str


@dataclass
class Transcript:
    text: str
    final: bool
    """Milliseconds since the start of the audio stream when this event was created."""
    stream_timestamp: int = 0
    """Milliseconds since the start of the audio stream for the most recent audio frame containing speech."""
    last_voice_timestamp: int = 0
    """Milliseconds since the start of the audio stream that the recognizer has processed."""
    recognition_timestamp: int = 0


@dataclass(kw_only=True)
class TranscriptMessage(Message):
    type: Literal["transcript"] = "transcript"
    transcript: Transcript


def message_from_json(data: str):
    """Deserialize a JSON message into a Message object."""
    msg = json.loads(data)
    type = msg["type"]
    clazz = get_message_class(type)
    if clazz is None:
        logging.warning(f"Unknown message type {type}")
    return clazz.from_dict(msg)


def get_message_class(type: str):
    for _, obj in inspect.getmembers(sys.modules[__name__]):
        if inspect.isclass(obj) and issubclass(obj, Message):
            if type == getattr(obj, "type", None):
                return obj
    return None
