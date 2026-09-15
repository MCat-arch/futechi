from pathlib import Path
from types import SimpleNamespace

import pytest
from pydantic import BaseModel

from futechi_graphrag.config.settings import Settings
from futechi_graphrag.infrastructure.llm.client import (
    LLMResponseFormatError,
    OpenAICompatibleLLMClient,
    build_llm_client,
    extract_json_object,
    image_to_url,
)


class Answer(BaseModel):
    answer: str


class FakeCompletions:
    def __init__(self, outputs: list[str | None]) -> None:
        self.outputs = list(outputs)
        self.calls: list[dict] = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        content = self.outputs.pop(0)
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=content))])


def _client(outputs: list[str | None], **kwargs) -> tuple[OpenAICompatibleLLMClient, FakeCompletions]:
    completions = FakeCompletions(outputs)
    fake_sdk = SimpleNamespace(chat=SimpleNamespace(completions=completions))
    return OpenAICompatibleLLMClient(model="text-model", client=fake_sdk, **kwargs), completions


def test_generate_returns_plain_text_without_json_mode() -> None:
    client, completions = _client(["halo"])
    assert client.generate("sys", "user") == "halo"
    call = completions.calls[0]
    assert call["model"] == "text-model"
    assert "response_format" not in call
    assert call["messages"] == [
        {"role": "system", "content": "sys"},
        {"role": "user", "content": "user"},
    ]


def test_generate_structured_parses_fenced_json_and_sends_schema() -> None:
    client, completions = _client(['```json\n{"answer": "ok"}\n```'])
    assert client.generate_structured("sys", "tanya", Answer) == Answer(answer="ok")
    call = completions.calls[0]
    assert call["response_format"] == {"type": "json_object"}
    assert call["messages"][1]["content"].startswith("tanya")
    assert '"answer"' in call["messages"][1]["content"]


def test_generate_structured_repairs_invalid_response_once() -> None:
    client, completions = _client(["bukan json", '{"answer": "ok"}'])
    assert client.generate_structured("sys", "tanya", Answer).answer == "ok"
    second_messages = completions.calls[1]["messages"]
    assert second_messages[2] == {"role": "assistant", "content": "bukan json"}
    assert "tidak valid" in second_messages[3]["content"]


def test_generate_structured_raises_after_repair_attempts_exhausted() -> None:
    client, _ = _client(['{"wrong": 1}', '{"wrong": 2}'])
    with pytest.raises(LLMResponseFormatError):
        client.generate_structured("sys", "tanya", Answer)


def test_empty_response_is_rejected() -> None:
    client, _ = _client([None])
    with pytest.raises(LLMResponseFormatError):
        client.generate("sys", "user")


def test_multimodal_request_uses_multimodal_model_and_image_parts(tmp_path: Path) -> None:
    image_file = tmp_path / "crop.jpg"
    image_file.write_bytes(b"\xff\xd8\xff-jpeg")
    client, completions = _client(['{"answer": "ok"}'], multimodal_model="vision-model")

    client.generate_structured_with_images(
        "sys", "lihat", [b"\x89PNG\r\n\x1a\n-png", image_file], Answer
    )

    call = completions.calls[0]
    assert call["model"] == "vision-model"
    content = call["messages"][1]["content"]
    assert content[0]["type"] == "text"
    assert content[1]["image_url"]["url"].startswith("data:image/png;base64,")
    assert content[2]["image_url"]["url"].startswith("data:image/jpeg;base64,")


def test_multimodal_request_requires_images() -> None:
    client, _ = _client([])
    with pytest.raises(ValueError):
        client.generate_structured_with_images("sys", "lihat", [], Answer)


def test_image_to_url_passes_through_remote_and_data_urls() -> None:
    assert image_to_url("https://example.com/a.jpg") == "https://example.com/a.jpg"
    assert image_to_url("data:image/png;base64,AAA") == "data:image/png;base64,AAA"


def test_extract_json_object_rejects_non_object() -> None:
    with pytest.raises(LLMResponseFormatError):
        extract_json_object("[1, 2]")


def test_build_llm_client_requires_model() -> None:
    with pytest.raises(ValueError):
        build_llm_client(Settings(_env_file=None, neo4j_password="x", llm_model=None))


def test_build_llm_client_uses_settings() -> None:
    settings = Settings(
        _env_file=None,
        neo4j_password="x",
        llm_model="glm-text",
        mllm_model="glm-vision",
        llm_base_url="http://localhost:8000/v1",
        llm_json_mode=False,
    )
    client = build_llm_client(settings)
    assert client._model == "glm-text"
    assert client._multimodal_model == "glm-vision"
    assert client._json_mode is False
