from __future__ import annotations

"""NVIDIA NIM seam for a later function-calling iteration.

The delivered MVP intentionally uses deterministic orchestration so it runs
without secrets. This small OpenAI-compatible client keeps the model swap
isolated once a NIM endpoint and model are confirmed on the hackathon machine.
"""

import os

import httpx


class NimClient:
    def __init__(self) -> None:
        self.base_url = os.getenv("NIM_BASE_URL", "").rstrip("/")
        self.api_key = os.getenv("NIM_API_KEY", "")
        self.model = os.getenv("NIM_MODEL", "")

    @property
    def enabled(self) -> bool:
        return bool(self.base_url and self.model)

    async def complete(self, messages: list[dict], tools: list[dict] | None = None) -> dict:
        if not self.enabled:
            raise RuntimeError("NIM is not configured; use the deterministic MVP orchestrator.")
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        payload = {"model": self.model, "messages": messages, "temperature": 0}
        if tools:
            payload.update({"tools": tools, "tool_choice": "auto"})
        async with httpx.AsyncClient(timeout=45) as client:
            response = await client.post(f"{self.base_url}/chat/completions", headers=headers, json=payload)
            response.raise_for_status()
            return response.json()

