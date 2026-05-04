"""火山方舟（豆包）OpenAI 兼容对话 API（chat/completions）。"""
from __future__ import annotations

import os
from typing import Any

import requests


class DoubaoChatService:
    def __init__(self) -> None:
        self.api_key = (os.getenv("ARK_API_KEY") or os.getenv("DOUBAO_API_KEY") or "").strip()
        self.base_url = (
            os.getenv("ARK_CHAT_BASE_URL") or os.getenv("ARK_EMBEDDING_BASE_URL") or "https://ark.cn-beijing.volces.com/api/v3"
        ).rstrip("/")
        self.model = (os.getenv("ARK_CHAT_MODEL") or "").strip()
        self.timeout = float(os.getenv("ARK_CHAT_TIMEOUT_SEC", "180"))

    def is_configured(self) -> bool:
        return bool(self.api_key and self.model)

    def status(self) -> dict[str, Any]:
        return {
            "configured": self.is_configured(),
            "baseUrl": self.base_url,
            "modelSet": bool(self.model),
        }

    def chat(self, messages: list[dict[str, str]], temperature: float = 0.2) -> str:
        if not self.is_configured():
            raise ValueError(
                "未配置豆包对话：请在环境变量中设置 ARK_API_KEY（或 DOUBAO_API_KEY）与 ARK_CHAT_MODEL。"
            )
        url = f"{self.base_url}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
        }
        resp = requests.post(url, json=payload, headers=headers, timeout=self.timeout)
        try:
            data = resp.json()
        except Exception as exc:
            raise ValueError(f"对话接口返回非 JSON（HTTP {resp.status_code}）: {exc}") from exc
        if resp.status_code >= 400:
            err = data.get("error") if isinstance(data, dict) else None
            if isinstance(err, dict):
                msg = err.get("message") or err.get("code") or str(err)
            else:
                msg = (data or {}).get("message") if isinstance(data, dict) else str(data)
            raise ValueError(msg or f"对话失败 HTTP {resp.status_code}")
        choices = (data or {}).get("choices") if isinstance(data, dict) else None
        if not choices:
            raise ValueError("对话接口未返回 choices")
        content = (choices[0] or {}).get("message", {}).get("content")
        if content is None:
            raise ValueError("对话接口未返回 content")
        return str(content).strip()
