"""
LLM client -- satu client untuk seluruh workflow agentic:
  - ekstraksi fitur visual dari citra (MLLM, Modul A)
  - reasoning diferensial & chat (LLM teks, Modul C)

Protocol dipisah (LLMClient / MultimodalLLMClient) supaya pipeline bisa diuji
dengan fake client. Implementasi konkret memakai API Chat Completions
OpenAI-compatible, sehingga endpoint bisa diarahkan ke OpenRouter, OpenCode,
Z.ai, vLLM self-host, dsb. lewat LLM_BASE_URL tanpa mengubah kode.
"""
from __future__ import annotations

import base64
import json
import mimetypes
from collections.abc import Sequence
from pathlib import Path
from typing import TYPE_CHECKING, Any, Protocol, TypeVar

from pydantic import BaseModel, ValidationError

if TYPE_CHECKING:
    from futechi_graphrag.config.settings import Settings

T = TypeVar("T", bound=BaseModel)
ImageInput = bytes | str | Path

_COMPLETIONS_SUFFIX = "/chat/completions"


class LLMClient(Protocol):
    def generate(self, system_prompt: str, user_prompt: str) -> str:
        """Kirim prompt, kembalikan teks respons bebas (dipakai untuk chat)."""
        ...

    def generate_structured(
        self, system_prompt: str, user_prompt: str, schema: type[T]
    ) -> T:
        """Kirim prompt, parse & validasi JSON respons menjadi instance `schema`."""
        ...


class MultimodalLLMClient(Protocol):
    def generate_structured_with_images(
        self,
        system_prompt: str,
        user_prompt: str,
        images: Sequence[ImageInput],
        schema: type[T],
    ) -> T:
        """Kirim prompt + citra, parse & validasi JSON respons menjadi instance `schema`."""
        ...


class LLMResponseFormatError(RuntimeError):
    """Respons LLM kosong atau tidak bisa di-parse menjadi JSON sesuai schema."""


class LLMResponseTruncatedError(LLMResponseFormatError):
    """
    Respons berhenti karena batas token (finish_reason=length). Pada reasoning
    model (mis. GLM-5.3-Flash via OpenRouter) token "berpikir" ikut memakan
    max_tokens. Repair TIDAK dicoba karena akan terpotong lagi dengan batas
    yang sama -- naikkan LLM_MAX_TOKENS.
    """


def normalize_base_url(base_url: str | None) -> str | None:
    """
    SDK OpenAI menambahkan '/chat/completions' sendiri. Jika .env berisi URL
    endpoint lengkap (mis. https://openrouter.ai/api/v1/chat/completions),
    potong sufiks tsb supaya request tidak menjadi .../chat/completions/chat/completions.
    """
    if not base_url:
        return None
    url = base_url.strip().rstrip("/")
    if url.endswith(_COMPLETIONS_SUFFIX):
        url = url[: -len(_COMPLETIONS_SUFFIX)]
    return url


def image_to_url(image: ImageInput) -> str:
    """URL http(s)/data diteruskan; bytes atau path file di-encode jadi data URL base64."""
    if isinstance(image, str) and image.startswith(("data:", "http://", "https://")):
        return image
    if isinstance(image, bytes):
        data = image
        mime = _sniff_image_mime(data)
    else:
        path = Path(image)
        data = path.read_bytes()
        mime = mimetypes.guess_type(path.name)[0] or _sniff_image_mime(data)
    return f"data:{mime};base64,{base64.b64encode(data).decode('ascii')}"


def _sniff_image_mime(data: bytes) -> str:
    if data.startswith(b"\x89PNG"):
        return "image/png"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp"
    return "image/jpeg"


def extract_json_object(text: str) -> dict[str, Any]:
    """Ambil objek JSON pertama dari teks (toleran terhadap code fence / teks pengantar)."""
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end < start:
        raise LLMResponseFormatError("Respons tidak mengandung objek JSON")
    try:
        data = json.loads(text[start : end + 1])
    except json.JSONDecodeError as exc:
        raise LLMResponseFormatError(f"JSON tidak valid: {exc}") from exc
    if not isinstance(data, dict):
        raise LLMResponseFormatError("JSON teratas harus berupa objek")
    return data


def schema_instruction(schema: type[BaseModel]) -> str:
    return (
        "\n\nWajib jawab HANYA dengan satu objek JSON valid sesuai JSON Schema "
        "berikut, tanpa teks lain dan tanpa markdown code fence:\n"
        f"{json.dumps(schema.model_json_schema(), ensure_ascii=False)}"
    )


class OpenAICompatibleLLMClient:
    """Implementasi LLMClient + MultimodalLLMClient untuk endpoint Chat Completions OpenAI-compatible."""

    def __init__(
        self,
        *,
        model: str,
        api_key: str | None = None,
        base_url: str | None = None,
        multimodal_model: str | None = None,
        temperature: float = 0.0,
        max_tokens: int = 4096,
        timeout_seconds: float = 60.0,
        json_mode: bool = True,
        max_repair_attempts: int = 1,
        client: Any | None = None,
    ) -> None:
        self._base_url = normalize_base_url(base_url)
        if client is None:
            from openai import OpenAI

            # Beberapa endpoint self-host tidak butuh key, tapi SDK mewajibkan nilai.
            client = OpenAI(
                api_key=api_key or "not-needed",
                base_url=self._base_url,
                timeout=timeout_seconds,
            )
        self._client = client
        self._model = model
        self._multimodal_model = multimodal_model or model
        self._temperature = temperature
        self._max_tokens = max_tokens
        self._json_mode = json_mode
        self._max_repair_attempts = max(0, max_repair_attempts)

    @property
    def base_url(self) -> str | None:
        return self._base_url

    @property
    def model(self) -> str:
        return self._model

    @property
    def multimodal_model(self) -> str:
        return self._multimodal_model

    def generate(self, system_prompt: str, user_prompt: str) -> str:
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]
        return self._complete(self._model, messages, json_mode=False)

    def generate_structured(
        self, system_prompt: str, user_prompt: str, schema: type[T]
    ) -> T:
        return self._structured(
            self._model, system_prompt, user_prompt + schema_instruction(schema), schema
        )

    def generate_structured_with_images(
        self,
        system_prompt: str,
        user_prompt: str,
        images: Sequence[ImageInput],
        schema: type[T],
    ) -> T:
        if not images:
            raise ValueError("images must contain at least one image")
        content: list[dict[str, Any]] = [
            {"type": "text", "text": user_prompt + schema_instruction(schema)}
        ]
        content += [
            {"type": "image_url", "image_url": {"url": image_to_url(image)}}
            for image in images
        ]
        return self._structured(self._multimodal_model, system_prompt, content, schema)

    def _structured(
        self,
        model: str,
        system_prompt: str,
        user_content: str | list[dict[str, Any]],
        schema: type[T],
    ) -> T:
        messages: list[dict[str, Any]] = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_content},
        ]
        last_error: Exception | None = None
        for _ in range(self._max_repair_attempts + 1):
            raw = self._complete(model, messages, json_mode=self._json_mode)  # truncation tidak di-repair
            try:
                return schema.model_validate(extract_json_object(raw))
            except (LLMResponseFormatError, ValidationError) as exc:
                last_error = exc
                messages = [
                    *messages,
                    {"role": "assistant", "content": raw},
                    {
                        "role": "user",
                        "content": (
                            f"Respons sebelumnya tidak valid: {exc}. Kirim ulang HANYA "
                            "objek JSON valid sesuai schema."
                        ),
                    },
                ]
        raise LLMResponseFormatError(
            f"Respons LLM tidak sesuai schema {schema.__name__} setelah "
            f"{self._max_repair_attempts + 1} percobaan: {last_error}"
        ) from last_error

    def _complete(
        self, model: str, messages: list[dict[str, Any]], json_mode: bool
    ) -> str:
        kwargs: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "temperature": self._temperature,
            "max_tokens": self._max_tokens,
        }
        if json_mode:
            kwargs["response_format"] = {"type": "json_object"}
        response = self._client.chat.completions.create(**kwargs)
        if not response.choices:
            raise LLMResponseFormatError("Respons LLM tanpa choices")
        choice = response.choices[0]
        if getattr(choice, "finish_reason", None) == "length":
            raise LLMResponseTruncatedError(
                f"Respons model {model} terpotong karena batas max_tokens={self._max_tokens} "
                "(finish_reason=length). Naikkan LLM_MAX_TOKENS."
            )
        content = choice.message.content
        if not content:
            raise LLMResponseFormatError("Respons LLM kosong")
        return content


def build_llm_client(settings: Settings | None = None) -> OpenAICompatibleLLMClient:
    """Bangun client dari konfigurasi LLM_* di .env."""
    if settings is None:
        from futechi_graphrag.config.settings import get_settings

        settings = get_settings()
    if not settings.llm_model:
        raise ValueError("LLM_MODEL belum diisi. Definisikan di file .env root proyek.")
    return OpenAICompatibleLLMClient(
        model=settings.llm_model,
        api_key=settings.llm_api_key,
        base_url=settings.llm_base_url,
        multimodal_model=settings.mllm_model or None,
        temperature=settings.llm_temperature,
        max_tokens=settings.llm_max_tokens,
        timeout_seconds=settings.llm_timeout_seconds,
        json_mode=settings.llm_json_mode,
    )
