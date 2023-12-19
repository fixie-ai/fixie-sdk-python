# fixie-sdk-python
Fixie SDK for Python

## Quickstart

1. Install
```bash
poetry install
```
1. Run example
```bash
just run-example
```


## Voice Example
While you can use `just run-example`, this is just a convenience method for `voice_example.py`
1. Run example
```bash
poetry run python fixie_sdk/examples/voice_example.py
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