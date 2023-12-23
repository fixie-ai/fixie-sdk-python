import asyncio
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

    async def start(self, sample_rate: int = 8000, num_channels: int = 1):
        pass

    async def write(self, chunk: bytes) -> None:
        # TODO: write to ws
        # https://github.com/twilio/media-streams/blob/master/node/connect-basic/server.js
        # (Received 100th media message=WSMessage(type=<WSMsgType.TEXT: 1>, data='{"event":"media","sequenceNumber":"102","media":{"track":"inbound","chunk":"101","timestamp":"2088","payload":"/////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////w=="},"streamSid":"MZ351c981a36cd9426fc1b17974b5d0327"}', extra='') with payload size=160
        # frame_data = wav.read(1024)
        #         if len(frame_data) == 0:
        #             print('no more data')
        #             break
        #         base64_data = base64.b64encode(frame_data).decode('utf-8')
        #         print('send base64 data')
        #         media_data = {
        #             "event": "media",
        #             "streamSid": stream_sid,
        #             "media": {
        #                 "playload": base64_data
        #             }
        #         }
        #         media = json.dumps(media_data)
        #         print(f"media: {media}")
        #         await ws.send(media)
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
