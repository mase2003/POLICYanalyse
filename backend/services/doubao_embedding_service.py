"""火山方舟（豆包）OpenAI 兼容向量化 API 封装。

文档：向量化 API https://www.volcengine.com/docs/82379/1523520?redirect=1&lang=zh
鉴权与 Base URL：https://www.volcengine.com/docs/82379/1541594?lang=zh
"""
from __future__ import annotations

import os
from typing import Any

import requests


class DoubaoEmbeddingService:
    """调用方舟 `/v3/embeddings`，与 OpenAI Embeddings 请求体兼容。"""

    def __init__(self) -> None:
        self.api_key = (os.getenv("ARK_API_KEY") or os.getenv("DOUBAO_API_KEY") or "").strip()
        self.base_url = (
            os.getenv("ARK_EMBEDDING_BASE_URL") or "https://ark.cn-beijing.volces.com/api/v3"
        ).rstrip("/")
        self.model = (os.getenv("ARK_EMBEDDING_MODEL") or "").strip()
        self.timeout = float(os.getenv("ARK_EMBEDDING_TIMEOUT_SEC", "90"))
        self._max_inputs = max(1, int(os.getenv("ARK_EMBEDDING_MAX_BATCH", "32")))
        self._max_chars = max(256, int(os.getenv("ARK_EMBEDDING_MAX_CHARS", "8000")))

    def is_configured(self) -> bool:
        return bool(self.api_key and self.model)

    def status(self) -> dict[str, Any]:
        return {
            "configured": self.is_configured(),
            "baseUrl": self.base_url,
            "modelSet": bool(self.model),
            "modelPreview": (self.model[:6] + "…") if len(self.model) > 8 else (self.model or ""),
        }

    def embed_texts(self, texts: list[str]) -> dict[str, Any]:
        if not self.is_configured():
            raise ValueError(
                "未配置豆包向量化：请在环境变量中设置 ARK_API_KEY（或 DOUBAO_API_KEY）"
                " 与 ARK_EMBEDDING_MODEL（向量化模型名或推理接入点 ep- 开头 ID）。"
            )
        cleaned: list[str] = []
        for i, t in enumerate(texts):
            s = (t or "").strip()
            if len(s) > self._max_chars:
                raise ValueError(f"第 {i + 1} 条文本超过长度上限 {self._max_chars} 字符")
            cleaned.append(s)
        if not cleaned:
            raise ValueError("inputs 不能为空")

        url = f"{self.base_url}/embeddings"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        # 分批，避免单次请求体过大
        all_rows: list[dict[str, Any]] = []
        usage_prompt = 0
        usage_total = 0
        model_name = self.model

        for start in range(0, len(cleaned), self._max_inputs):
            batch = cleaned[start : start + self._max_inputs]
            payload: dict[str, Any] = {"model": self.model, "input": batch}
            resp = requests.post(url, json=payload, headers=headers, timeout=self.timeout)
            try:
                data = resp.json()
            except Exception as exc:
                raise ValueError(f"向量化接口返回非 JSON（HTTP {resp.status_code}）: {exc}") from exc

            if resp.status_code >= 400:
                err = data.get("error") if isinstance(data, dict) else None
                if isinstance(err, dict):
                    msg = err.get("message") or err.get("code") or str(err)
                else:
                    msg = (data or {}).get("message") if isinstance(data, dict) else str(data)
                raise ValueError(msg or f"向量化失败 HTTP {resp.status_code}")

            rows = data.get("data") or []
            if not isinstance(rows, list) or not rows:
                raise ValueError("向量化接口未返回 data 数组")

            for row in rows:
                if isinstance(row, dict) and "embedding" in row:
                    all_rows.append(row)

            u = data.get("usage") or {}
            if isinstance(u, dict):
                usage_prompt += int(u.get("prompt_tokens") or 0)
                usage_total += int(u.get("total_tokens") or 0)
            if isinstance(data.get("model"), str):
                model_name = data["model"]

        all_rows.sort(key=lambda x: int(x.get("index", 0)))
        vectors = [list(map(float, r["embedding"])) for r in all_rows if r.get("embedding")]

        if len(vectors) != len(cleaned):
            raise ValueError(f"返回向量条数 {len(vectors)} 与输入 {len(cleaned)} 不一致")

        return {
            "model": model_name,
            "embeddings": vectors,
            "dimensions": len(vectors[0]) if vectors else 0,
            "usage": {"prompt_tokens": usage_prompt, "total_tokens": usage_total},
        }
