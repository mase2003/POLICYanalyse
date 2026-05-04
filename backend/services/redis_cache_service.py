import json
import os
import time
from typing import Any

import redis


def _bool_env(key: str, default: bool = False) -> bool:
    val = os.getenv(key, "")
    if not val:
        return default
    return val.strip().lower() in ("1", "true", "yes", "on")


class RedisCacheService:
    """Lightweight Redis cache wrapper for crawler temp data."""

    def __init__(self) -> None:
        host = os.getenv("REDIS_HOST", "127.0.0.1")
        port = int(os.getenv("REDIS_PORT", "6379"))
        db = int(os.getenv("REDIS_DB", "0"))
        password = os.getenv("REDIS_PASSWORD", "")
        socket_timeout = float(os.getenv("REDIS_SOCKET_TIMEOUT_SEC", "2"))
        decode_responses = _bool_env("REDIS_DECODE_RESPONSES", False)
        self.default_ttl = int(os.getenv("REDIS_CACHE_TTL_SEC", "900"))
        self.enabled = _bool_env("REDIS_ENABLED", True)
        self._configured_enabled = self.enabled

        self._client: redis.Redis | None = None
        self._last_error: str = ""
        self._reconnect_interval_sec = float(os.getenv("REDIS_RECONNECT_INTERVAL_SEC", "5"))
        self._next_reconnect_ts = 0.0

        if not self._configured_enabled:
            self._last_error = "redis disabled by REDIS_ENABLED"
            return

        self._conn_kwargs = {
            "host": host,
            "port": port,
            "db": db,
            "password": (password or None),
            "socket_timeout": socket_timeout,
            "socket_connect_timeout": socket_timeout,
            "decode_responses": decode_responses,
        }
        self._client = redis.Redis(**self._conn_kwargs)
        # 启动时探活：Redis 不可达则先降级；后续会自动重连恢复。
        try:
            self._client.ping()
        except Exception as exc:
            self._last_error = str(exc)
            self.enabled = False
            self._client = None
            self._next_reconnect_ts = time.time() + self._reconnect_interval_sec

    def _ensure_client(self) -> bool:
        if not self._configured_enabled:
            self.enabled = False
            return False
        if self._client is not None:
            self.enabled = True
            return True
        now = time.time()
        if now < self._next_reconnect_ts:
            return False
        try:
            self._client = redis.Redis(**self._conn_kwargs)
            self._client.ping()
            self.enabled = True
            self._last_error = ""
            return True
        except Exception as exc:
            self._last_error = str(exc)
            self.enabled = False
            self._client = None
            self._next_reconnect_ts = now + self._reconnect_interval_sec
            return False

    @property
    def last_error(self) -> str:
        return self._last_error

    def ping(self) -> bool:
        if not self._ensure_client():
            return False
        try:
            return bool(self._client.ping())
        except Exception as exc:
            self._last_error = str(exc)
            return False

    def get(self, key: str) -> str | bytes | None:
        if not self._ensure_client():
            return None
        try:
            return self._client.get(key)
        except Exception as exc:
            self._last_error = str(exc)
            return None

    def set(self, key: str, value: str | bytes, ttl: int | None = None) -> bool:
        if not self._ensure_client():
            return False
        ex = self.default_ttl if ttl is None else max(1, int(ttl))
        try:
            return bool(self._client.set(name=key, value=value, ex=ex))
        except Exception as exc:
            self._last_error = str(exc)
            return False

    def delete(self, key: str) -> int:
        if not self._ensure_client():
            return 0
        try:
            return int(self._client.delete(key))
        except Exception as exc:
            self._last_error = str(exc)
            return 0

    def incr(self, key: str) -> int | None:
        """自增计数；Redis 不可用时返回 None。"""
        if not self._ensure_client():
            return None
        try:
            return int(self._client.incr(key))
        except Exception as exc:
            self._last_error = str(exc)
            return None

    def expire(self, key: str, seconds: int) -> bool:
        if not self._ensure_client():
            return False
        try:
            return bool(self._client.expire(key, max(1, int(seconds))))
        except Exception as exc:
            self._last_error = str(exc)
            return False

    def get_json(self, key: str) -> Any:
        raw = self.get(key)
        if raw is None:
            return None
        try:
            if isinstance(raw, bytes):
                raw = raw.decode("utf-8")
            return json.loads(raw)
        except Exception as exc:
            self._last_error = str(exc)
            return None

    def set_json(self, key: str, value: Any, ttl: int | None = None) -> bool:
        try:
            payload = json.dumps(value, ensure_ascii=False)
        except Exception as exc:
            self._last_error = str(exc)
            return False
        return self.set(key, payload, ttl=ttl)

    def lpush_json(self, key: str, value: Any, max_len: int = 300) -> bool:
        """左侧插入一条 JSON 日志，并截断列表长度（最新在前）。"""
        if not self._ensure_client():
            return False
        try:
            payload = json.dumps(value, ensure_ascii=False)
            pipe = self._client.pipeline()
            pipe.lpush(key, payload)
            pipe.ltrim(key, 0, max(0, max_len - 1))
            pipe.execute()
            return True
        except Exception as exc:
            self._last_error = str(exc)
            return False

    def lrange_json(self, key: str, start: int = 0, end: int = 49) -> list[Any]:
        """读取列表中的 JSON 项（下标与 Redis lrange 一致）。"""
        if not self._ensure_client():
            return []
        try:
            parts = self._client.lrange(key, start, end)
        except Exception as exc:
            self._last_error = str(exc)
            return []
        out: list[Any] = []
        for p in parts:
            try:
                if isinstance(p, bytes):
                    p = p.decode("utf-8")
                out.append(json.loads(p))
            except Exception:
                continue
        return out
