import argparse
import asyncio
import audioop
import base64
import json
import logging
import signal

import aiohttp.web

from fixie_sdk.voice import audio_local
from fixie_sdk.voice import audio_phone
from fixie_sdk.voice.session import VoiceSession
from fixie_sdk.voice.session import VoiceSessionParams


async def testhandle(request):
    return aiohttp.web.Response(text="Hello Fixie!")


async def websocket_handler(request):
    logging.info("Websocket connection starting")
    ws = aiohttp.web.WebSocketResponse()
    await ws.prepare(request)
    logging.info("Websocket connection ready")

    async for msg in ws:
        if msg.type == aiohttp.WSMsgType.TEXT:
            # Messages are a JSON encoded string
            data = json.loads(msg.data)

            # Using the event type you can determine what type of msg you are receiving
            if data["event"] == "connected":
                logging.info(f"Received connected message={msg}")
                # Warm up the voice session by connecting to the server.
                await client.warmup()

                # Not just warming up...Start the voice session.
                if not args.warmup_only:
                    await client.start()

            if data["event"] == "start":
                logging.info(f"Received start message={msg}")
            if data["event"] == "media":
                payload = data["media"]["payload"]
                ulaw = base64.b64decode(payload)
                pcm16 = audioop.ulaw2lin(ulaw, 2)
                await source.write(pcm16)
            if data["event"] == "closed":
                logging.info("Received close message={msg}")
                await ws.close()

    logging.info("Websocket connection closed")
    # Wait for the voice session to end.
    await done.wait()
    await client.stop()
    return ws


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--agent", "-a", type=str, default="dr-donut", help="Agent ID to talk to"
    )
    parser.add_argument("--tts-voice", "-tv", type=str, help="TTS voice ID to use")
    parser.add_argument(
        "--warmup-only", "-w", action="store_true", help="Only connect to the server"
    )
    args = parser.parse_args()

    # Get the default microphone and audio output device.
    source = audio_phone.PhoneAudioSource()
    sink = audio_local.LocalAudioSink()

    # Set up the voice session parameters.
    params = VoiceSessionParams(
        agent_id=args.agent,
        tts_voice=args.tts_voice,
    )

    # Create the client for the voice session.
    client = VoiceSession(source, sink, params)

    # Set up an event loop for the voice session.
    done = asyncio.Event()
    loop = asyncio.get_event_loop()

    # Set up signal handlers for SIGINT (Ctrl-C) and SIGTERM (kill).
    loop.add_signal_handler(signal.SIGINT, lambda: done.set())
    loop.add_signal_handler(signal.SIGTERM, lambda: done.set())

    app = aiohttp.web.Application()
    app.router.add_route("GET", "/", testhandle)
    app.router.add_route("GET", "/media", websocket_handler)
    aiohttp.web.run_app(app, host="localhost", port=5000)
