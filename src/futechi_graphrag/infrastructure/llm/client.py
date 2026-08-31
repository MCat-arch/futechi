"""
LLM client -- abstraksi pemanggilan text LLM untuk reasoning Modul C.
Didesain sebagai Protocol supaya pipeline bisa diuji dengan fake client,
terlepas dari provider LLM asli yang dipakai.

CATATAN: implementasi konkret di bawah (AnthropicLLMClient) TIDAK diuji
langsung di sandbox pengembangan (butuh akses jaringan ke api.anthropic.com
yang tidak tersedia saat kode ini ditulis) -- WAJIB diverifikasi manual
dengan API key sungguhan sebelum dipakai produksi. Seluruh logika
reasoner.py sendiri diuji dengan FakeLLMClient (lihat tests/), terpisah
dari implementasi konkret ini.
"""
from typing import Protocol, TypeVar

from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)


class LLMClient(Protocol):
    def generate(self, system_prompt: str, user_prompt: str) -> str:
        """Kirim prompt, kembalikan teks respons bebas (dipakai untuk chat)."""
        ...

    def generate_structured(
        self, system_prompt: str, user_prompt: str, schema: type[T]
    ) -> T:
        """
        Kirim prompt, minta LLM mengembalikan JSON sesuai `schema`, lalu
        parse & validasi jadi instance pydantic. Dipakai untuk reasoning
        awal (Tier 1) yang butuh struktur ketat (differential_notes,
        overall_uncertainty).
        """
        ...


class AnthropicLLMClient:
    """
    Implementasi LLMClient menggunakan Anthropic API.

    TIDAK diuji langsung di sandbox -- lihat catatan di atas modul ini.
    """

    def __init__(self, api_key: str, model: str):
        import anthropic  # import di sini supaya modul ini tetap bisa
        # di-import untuk testing tanpa package anthropic ter-install

        self._client = anthropic.Anthropic(api_key=api_key)
        self._model = model

    def generate(self, system_prompt: str, user_prompt: str) -> str:
        response = self._client.messages.create(
            model=self._model,
            max_tokens=1500,
            system=system_prompt,
            messages=[{"role": "user", "content": user_prompt}],
        )
        return "".join(
            block.text for block in response.content if block.type == "text"
        )

    def generate_structured(
        self, system_prompt: str, user_prompt: str, schema: type[T]
    ) -> T:
        import json

        json_instruction = (
            f"\n\nWajib jawab HANYA dengan JSON valid sesuai schema berikut, "
            f"tanpa teks lain, tanpa markdown code fence:\n"
            f"{schema.model_json_schema()}"
        )
        raw_text = self.generate(system_prompt, user_prompt + json_instruction)
        cleaned = raw_text.strip().removeprefix("```json").removesuffix("```").strip()
        data = json.loads(cleaned)
        return schema.model_validate(data)
