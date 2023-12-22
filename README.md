# fixie-sdk-python
Fixie SDK for Python


## Quickstart

```bash
pip install fixie
```

### Hello Agent

To start a voice session with a Fixie agent, create a `VoiceSession` object and call `session.start()`.

```python
from fixie_sdk.voice import audio_local
from fixie_sdk.voice import types
from fixie_sdk.voice.session import VoiceSession
from fixie_sdk.voice.session import VoiceSessionParams


async def main():
    source = audio_local.LocalAudioSource()
    sink = audio_local.LocalAudioSink()
    params = VoiceSessionParams(agent_id=<your agent uuid>)
    client = VoiceSession(source, sink, params)
    await client.warmup()
    await client.start()
    await asyncio.Event().wait()


asyncio.run(main())
```

### Hello Santa

For a more complete example, see the command-line client included with the Fixie SDK: https://github.com/fixie-ai/fixie-sdk-python/blob/main/fixie_sdk/examples/voice_example.py


## Installing & Running from Source

1. Install
```bash
poetry install
```

2. Run included voice example
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

3. Run included Twilio stream example
```bash
poetry run python examples/twilio_stream_example.py
ngrok http 5000
```
where ngrok output looks like
```bash
Forwarding  https://eb06-98-203-158-121.ngrok-free.app -> http://localhost:5000
```

Following https://www.twilio.com/docs/voice/tutorials/consume-real-time-media-stream-using-websockets-python-and-flask#start-streaming-audio to  configure TwiML Bin
```xml
<Response>
    <Connect>
        <Stream url="wss://eb06-98-203-158-121.ngrok-free.app/media" />
     </Connect>
</Response>
```
### Using Your Own Agent
You can pass in the `--agent` (or `-a`) input parameter followed by a space and then the ID of your agent.

### Using a Different Voice
Adding more voices is a WIP. For now you can use the default voice or can pick any of the voices that are defined [here](https://github.com/fixie-ai/hisanta.ai/blob/main/lib/config.ts). Pass in the desired voiceID with the `--tts-voice` (`-V`) parameter.

### Using Your Own Audio Devices
Typically you will want to supply your own audio source and sink (e.g., to pipe the data to the phone network rather than the local audio devices). To do this, simply create your own classes derived from AudioSource and AudioSink and pass them in to the VoiceSession constructor.
