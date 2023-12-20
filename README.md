# fixie-sdk-python
Fixie SDK for Python


## Quickstart

```bash
pip install fixie
```

### Create voice_example.py

Create a file named `voice_example.py` with the following content:

```python
import argparse
import asyncio
import logging
import signal
import sys

from fixie_sdk.voice import audio_local
from fixie_sdk.voice import types
from fixie_sdk.voice.session import VoiceSession
from fixie_sdk.voice.session import VoiceSessionParams


async def main():
    # Get the default microphone and audio output device.
    source = audio_local.LocalAudioSource()
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

    # Set up the event handlers for the voice session.
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

    # Set up signal handlers for SIGINT (Ctrl-C) and SIGTERM (kill).
    loop.add_signal_handler(signal.SIGINT, lambda: done.set())
    loop.add_signal_handler(signal.SIGTERM, lambda: done.set())

    # Warm up the voice session by connecting to the server.
    await client.warmup()

    # Not just warming up...Start the voice session.
    if not args.warmup_only:
        await client.start()

    # Wait for the voice session to end.
    await done.wait()
    await client.stop()


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

    asyncio.run(main())
```

### Run the Example
```bash
python voice_example.py
```

## Installing & Running from Source

1. Install
```bash
poetry install
```
1. Run included voice example
```bash
poetry run python examples/voice_example.py
```
Use `Ctrl-C` to terminate the program.

The example program will use the default microphone and output device (i.e. speaker) for your computer. These are set in this code:

```python
# Get the default microphone and audio output device.
source = audio_local.LocalAudioSource()
sink = audio_local.LocalAudioSink()
```
You can find more information in the file `voice/audio_local.py`.

### Using Your Own Agent
You can pass in the `--agent` (or `-a`) input parameter followed by a space and then the ID of your agent.

### Using a Different Voice
Adding more voices is a WIP. For now you can use the default voice or can pick any of the voices that are defined [here](https://github.com/fixie-ai/hisanta.ai/blob/main/lib/config.ts). Pass in the desired voiceID with the `--tts-voice` (`-tv`) parameter.