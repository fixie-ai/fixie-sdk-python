import argparse
import asyncio
import dataclasses
import logging
import signal
import sys
from typing import Optional

import websockets
from livekit import rtc
from pyee import asyncio as pyee_asyncio

from fixie_sdk.voice import audio_base
from fixie_sdk.voice import audio_local
from fixie_sdk.voice import audio_track
from fixie_sdk.voice import types

PING_INTERVAL = 5


@dataclasses.dataclass
class VoiceSessionParams:
    webrtc_url: str
    asr_provider: Optional[str] = None
    asr_language: Optional[str] = None
    tts_provider: Optional[str] = None
    tts_model: Optional[str] = None
    tts_voice: Optional[str] = None
    model: Optional[str] = None
    agent_id: Optional[str] = None


class VoiceSession(pyee_asyncio.AsyncIOEventEmitter):
    def __init__(
        self,
        source: audio_base.AudioSource,
        sink: audio_base.AudioSink,
        params: VoiceSessionParams,
    ):
        super().__init__()
        self._params = params
        self._state = types.SessionState.IDLE
        self._socket = None
        self._receive_task: Optional[asyncio.Task] = None
        self._ping_task: Optional[asyncio.Task] = None
        self._room: rtc.Room = None
        self._room_emitter = pyee_asyncio.AsyncIOEventEmitter()
        self._source = source
        self._source_adapter = audio_track.AudioSourceToSendTrackAdapter(source)
        self._source_adapter.enabled = False
        self._sink = sink
        self._sink_adapter: Optional[audio_track.AudioSinkFromRecvTrackAdapter] = None
        self._started = False
        self._pending_output = ""

    @property
    def state(self):
        return self._state

    async def warmup(self):
        url = self._params.webrtc_url
        logging.info(f"[session] Connecting to {url}")
        self._socket = await websockets.connect(url)
        msg = self._create_init_message()
        await self._socket.send(msg.to_json())
        self._receive_task = asyncio.create_task(self._socket_receive())

    async def start(self):
        logging.info("[session] Starting...")
        self._started = True
        await self._maybe_publish_local_audio()

    async def stop(self):
        logging.info("[session] Stopping...")
        self._started = False
        await self._source_adapter.close()
        if self._sink_adapter:
            await self._sink_adapter.close()
            self._sink_adapter = None
        if self._ping_task:
            self._ping_task.cancel()
            await self._ping_task
            self._ping_task = None
        if self._room:
            await self._room.disconnect()
            self._room = None
        if self._socket:
            await self._socket.close()
            await self._receive_task
            self._receive_task = None
        self._socket = None
        self._change_state(types.SessionState.IDLE)

    async def interrupt(self):
        logging.info("[session] Interrupting...")
        await self._send_data(types.InterruptMessage())

    async def _ping_loop(self, interval: float):
        try:
            while True:
                timestamp = asyncio.get_event_loop().time()
                await self._send_data(types.PingMessage(timestamp=timestamp))
                await asyncio.sleep(interval)
        except asyncio.CancelledError:
            pass

    async def _socket_receive(self):
        try:
            async for message in self._socket:
                await self._on_message(message)
        except asyncio.CancelledError as e:
            logging.info("[session] socket cancelled")
        except websockets.ConnectionClosedOK as e:
            logging.info("[session] socket closed ok")
        except websockets.ConnectionClosedError as e:
            self.emit("error", e)

    async def _on_message(self, payload: str):
        msg = types.message_from_json(payload)
        logging.debug(f"[session] msg: {msg.type}")
        match msg.type:
            case "room_info":
                self._room = rtc.Room()
                self._room.on("track_subscribed", self._on_track_subscribed)
                self._room.on("data_received", self._on_data_received)
                self._room_emitter.on(
                    "track_subscribed", self._async_on_track_subscribed
                )
                await self._room.connect(msg.room_url, msg.token)
                logging.info(f"[session] connected to room: {self._room.name}")
                self._ping_task = asyncio.create_task(self._ping_loop(PING_INTERVAL))
                await self._maybe_publish_local_audio()

            case _:
                logging.error(f"[session] unknown message type {msg['type']}")

    def _on_track_subscribed(
        self,
        track: rtc.Track,
        publication: rtc.RemoteTrackPublication,
        participant: rtc.Participant,
    ):
        self._room_emitter.emit("track_subscribed", track, publication, participant)

    async def _async_on_track_subscribed(
        self,
        track: rtc.Track,
        publication: rtc.RemoteTrackPublication,
        participant: rtc.Participant,
    ):
        logging.info(f"[session] subscribed to remote audio track {track.sid}")
        if self._state == types.SessionState.THINKING:
            self._change_state(types.SessionState.SPEAKING)
        self._sink_adapter = audio_track.AudioSinkFromRecvTrackAdapter(
            self._sink, track
        )
        await self._sink_adapter.start()

    def _on_data_received(
        self,
        payload: bytes,
        kind: rtc.DataPacketKind,
        participant: rtc.Participant,
        topic: str,
    ):
        msg = types.message_from_json(payload.decode("utf-8"))
        if msg is None:
            return

        logging.debug(f"[session] dc_msg: {msg.type}")
        match msg.type:
            case "pong":
                elapsed_ms = (asyncio.get_event_loop().time() - msg.timestamp) * 1000
                logging.debug(f"[session] worker RTT: {elapsed_ms:.0f} ms")
            case "state":
                new_state = msg.state
                if (
                    new_state == types.SessionState.SPEAKING
                    and self._sink_adapter is None
                ):
                    # Skip the first speaking state, before we've hooked up the recv track.
                    # on_track_subscribed will be called soon and we'll change the state then.
                    pass
                else:
                    self._change_state(new_state)
            case "transcript":
                transcript = msg.transcript
                self._on_input_change(transcript.text, transcript.final)
            case "output_delta":
                self._pending_output += msg.delta
                self._on_output_change(self._pending_output, False)
            case "output":
                self._pending_output = ""
                self._on_output_change(msg.text, True)
            case "latency":
                self._on_latency_change(msg.kind, msg.value)
            case "error":
                self.emit("error", Exception(msg.message))

    def _on_input_change(self, text: str, final: bool):
        self.emit("input", text, final)

    def _on_output_change(self, text: str, final: bool):
        self.emit("output", text, final)

    def _on_latency_change(self, metric: types.SessionMetric, value: float):
        self.emit("latency", metric, value)

    def _change_state(self, state: types.SessionState):
        if state != self._state:
            self._state = state
            self.emit("state", state)
            if self._state == types.SessionState.LISTENING:
                self._source_adapter.enabled = True
            elif self._state == types.SessionState.SPEAKING:
                self._source_adapter.enabled = False

    def _create_init_message(self):
        asr = tts = None
        if self._params.asr_provider:
            asr = types.ASRParameters(
                provider=self._params.asr_provider,
                language=self._params.asr_language,
            )
        if self._params.tts_provider:
            tts = types.TTSParameters(
                provider=self._params.tts_provider,
                voice=self._params.tts_voice,
                model=self._params.tts_model,
            )
        agent = types.AgentParameters(
            agent_id=self._params.agent_id, model=self._params.model
        )
        return types.InitMessage(
            params=types.InitParameters(asr=asr, tts=tts, agent=agent)
        )

    async def _maybe_publish_local_audio(self):
        if self._room and self._room.isconnected() and self._started:
            logging.info("[session] publishing local audio track")
            opts = rtc.TrackPublishOptions()
            opts.source = rtc.TrackSource.SOURCE_MICROPHONE
            await self._source_adapter.start()
            await self._room.local_participant.publish_track(
                self._source_adapter.track, opts
            )

    async def _send_data(self, msg):
        assert self._room is not None
        await self._room.local_participant.publish_data(msg.to_json())


async def main():
    source = audio_local.LocalAudioSource()
    sink = audio_local.LocalAudioSink()
    params = VoiceSessionParams(
        webrtc_url=args.url,
        agent_id=args.agent,
        model=args.model,
        tts_provider=args.tts,
        tts_voice=args.tts_voice,
    )
    client = VoiceSession(source, sink, params)
    done = asyncio.Event()
    loop = asyncio.get_event_loop()

    @client.on("state")
    async def on_state(state):
        logging.info(f"[session] state: {state.value}")
        if state == types.SessionState.LISTENING:
            print("User:  ", end="\r")
        elif state == types.SessionState.THINKING:
            print("Agent:  ", end="\r")

    @client.on("input")
    async def on_input(text, final):
        print("User:  " + text, end="\n" if final else "\r")

    @client.on("output")
    async def on_output(text, final):
        print("Agent: " + text, end="\n" if final else "\r")

    @client.on("latency")
    async def on_latency(metric, value):
        logging.info(f"[session] latency: {metric.value}={value}")

    @client.on("error")
    async def on_error(error):
        print(f"Error: {error}")
        done.set()

    loop.add_signal_handler(signal.SIGINT, lambda: done.set())
    loop.add_signal_handler(signal.SIGTERM, lambda: done.set())
    await client.warmup()
    if not args.warmup_only:
        await client.start()
    await done.wait()
    await client.stop()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--url",
        "-u",
        type=str,
        default="wss://wsapi.fixie.ai",
        help="URL to connect to",
    )
    parser.add_argument(
        "--agent", "-a", type=str, default="dr-donut", help="Agent ID to talk to"
    )
    parser.add_argument(
        "--tts",
        "-t",
        type=str,
        help="TTS provider to use (e.g., eleven, playht)",
    )
    parser.add_argument("--tts-voice", type=str, help="TTS voice ID to use")
    parser.add_argument("--model", "-m", type=str, help="Model the agent should use")
    parser.add_argument(
        "--warmup-only", action="store_true", help="Only connect to the server"
    )
    parser.add_argument(
        "--verbose", "-v", action="store_true", help="Show verbose session information"
    )
    args = parser.parse_args()
    logging.getLogger("livekit").disabled = True
    if args.verbose:
        logging.basicConfig(stream=sys.stdout, level=logging.INFO)
    asyncio.run(main())
