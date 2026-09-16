from types import SimpleNamespace

import pytest

from futechi_graphrag.infrastructure.llm.client import OpenAICompatibleLLMClient, normalize_base_url


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("https://openrouter.ai/api/v1/chat/completions", "https://openrouter.ai/api/v1"),
        ("https://openrouter.ai/api/v1/chat/completions/", "https://openrouter.ai/api/v1"),
        ("https://openrouter.ai/api/v1/", "https://openrouter.ai/api/v1"),
        ("http://localhost:8000/v1", "http://localhost:8000/v1"),
        ("", None),
        (None, None),
    ],
)
def test_normalize_base_url(raw, expected) -> None:
    assert normalize_base_url(raw) == expected


def test_client_exposes_normalized_configuration() -> None:
    client = OpenAICompatibleLLMClient(
        model="z-ai/glm-5.3-flash",
        base_url="https://openrouter.ai/api/v1/chat/completions",
        client=SimpleNamespace(),
    )
    assert client.base_url == "https://openrouter.ai/api/v1"
    assert client.model == client.multimodal_model == "z-ai/glm-5.3-flash"
