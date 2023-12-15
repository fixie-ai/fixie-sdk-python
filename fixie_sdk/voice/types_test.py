from fixie_sdk.voice import types


def test_init_message():
    json = """
    {
        "type": "init",
        "params": {
            "asr": {
                "provider": "test_asr",
                "language": "test_asr_lang",
                "model": "test_asr_model",
                "baseUrl": "https://test.example.com"
            },
            "tts": {
                "provider": "test_tts",
                "model": "test_tts_model",
                "rate": 1.4,
                "voice": "test_tts_voice"
            },
            "agent": {
                "model": "test_agent_model",
                "agentId": "test_agent_id"
            }
        }
    }
    """
    message = types.InitMessage.from_json(json)
    assert message.type == "init"
    assert message.params.asr.provider == "test_asr"
    assert message.params.asr.language == "test_asr_lang"
    assert message.params.asr.model == "test_asr_model"
    assert message.params.asr.base_url == "https://test.example.com"
    assert message.params.tts.provider == "test_tts"
    assert message.params.tts.model == "test_tts_model"
    assert message.params.tts.rate == 1.4
    assert message.params.tts.voice == "test_tts_voice"
    assert message.params.agent.model == "test_agent_model"
    assert message.params.agent.agent_id == "test_agent_id"
