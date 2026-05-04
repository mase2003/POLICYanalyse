import copy
import hashlib
import json
import os
from datetime import datetime, timezone

from flask import Blueprint, current_app, jsonify, request, send_file

from services.policy_forecast_service import PolicyForecastService

policy_forecast_bp = Blueprint("policy_forecast", __name__, url_prefix="/api/policy-forecast")
_svc = PolicyForecastService()

LOG_KEY = "policy_parse:log"


def _crawler():
    svc = current_app.extensions.get("policy_crawler_service")
    if not svc:
        raise RuntimeError("crawler service unavailable")
    return svc


def _cache():
    return current_app.extensions.get("redis_cache")


def _pipeline_cache_key(body: dict) -> str:
    normalized = json.dumps(body, sort_keys=True, ensure_ascii=False)
    h = hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:40]
    return f"policy_parse:v1:{h}"


def _append_parse_log(cache, body: dict, *, hit: bool, task_id: str | None) -> None:
    if not cache or not getattr(cache, "enabled", False):
        return
    max_len = int(os.getenv("POLICY_PARSE_LOG_MAX", "300"))
    entry = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "taskId": task_id,
        "cacheHit": hit,
        "filters": {
            "source": body.get("source"),
            "docType": body.get("docType"),
            "category": body.get("category"),
            "month": body.get("month"),
            "selectedTrendKeywords": body.get("selectedTrendKeywords"),
        },
    }
    cache.lpush_json(LOG_KEY, entry, max_len=max_len)


@policy_forecast_bp.get("/fifteen-five")
def fifteen_five():
    try:
        return jsonify(_svc.fifteen_five_bundle())
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500


@policy_forecast_bp.get("/party-20")
def party_20():
    try:
        return jsonify(_svc.party20_bundle())
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500


@policy_forecast_bp.get("/crawler-parse/log")
def crawler_parse_log():
    """最近采集解析请求日志（Redis 列表，便于排查）。"""
    cache = _cache()
    if not cache or not cache.enabled:
        return jsonify({"items": [], "error": "Redis 未启用或不可用"}), 503
    limit = min(100, max(1, int(request.args.get("limit", "50"))))
    items = cache.lrange_json(LOG_KEY, 0, limit - 1)
    return jsonify({"items": items, "total": len(items)})


@policy_forecast_bp.post("/crawler-parse")
def crawler_parse():
    try:
        body = request.get_json(silent=True) or {}
        cache = _cache()
        key = _pipeline_cache_key(body)
        if cache and cache.enabled:
            cached = cache.get_json(key)
            if cached is not None:
                sel = body.get("selectedTrendKeywords")
                if isinstance(sel, list) and len(sel) > 0:
                    data = copy.deepcopy(cached)
                    sk = _svc.normalize_selected_trend_keywords(body)
                    data["step5"] = dict(data.get("step5") or {})
                    data["step5"]["policies"] = _svc.build_step5_policies_list(sk)
                    data["filters"] = dict(data.get("filters") or {})
                    data["filters"]["selectedTrendKeywords"] = sk
                    _append_parse_log(cache, body, hit=False, task_id=data.get("taskId"))
                    return jsonify(data)
                _append_parse_log(cache, body, hit=True, task_id=cached.get("taskId"))
                return jsonify(cached)

        data = _svc.crawler_parse_pipeline(_crawler(), body)
        if cache and cache.enabled:
            ttl = int(os.getenv("POLICY_PARSE_CACHE_TTL_SEC", "86400"))
            cache.set_json(key, data, ttl=ttl)
        _append_parse_log(cache, body, hit=False, task_id=data.get("taskId"))
        return jsonify(data)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500


@policy_forecast_bp.post("/crawler-parse/export")
def crawler_parse_export():
    try:
        body = request.get_json(silent=True) or {}
        cache = _cache()
        key = _pipeline_cache_key(body)
        pipeline = None
        if cache and cache.enabled:
            pipeline = cache.get_json(key)
        if pipeline is not None:
            sel = body.get("selectedTrendKeywords")
            if isinstance(sel, list) and len(sel) > 0:
                pipeline = copy.deepcopy(pipeline)
                sk = _svc.normalize_selected_trend_keywords(body)
                pipeline["step5"] = dict(pipeline.get("step5") or {})
                pipeline["step5"]["policies"] = _svc.build_step5_policies_list(sk)
        if pipeline is None:
            pipeline = _svc.crawler_parse_pipeline(_crawler(), body)
            if cache and cache.enabled:
                ttl = int(os.getenv("POLICY_PARSE_CACHE_TTL_SEC", "86400"))
                cache.set_json(key, pipeline, ttl=ttl)
        path = PolicyForecastService.export_parse_workbook(pipeline)
        return send_file(str(path), as_attachment=True, download_name=path.name)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500
