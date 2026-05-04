import os

from flask import Blueprint, current_app, jsonify, request

from routes.graph import service
from services.official_read_service import OfficialReadService

official_read_bp = Blueprint("official_read", __name__, url_prefix="/api/official-read")
_svc = OfficialReadService(service)


@official_read_bp.get("/filters")
def filters():
    try:
        cache = current_app.extensions.get("redis_cache")
        key = "official_read:filters:v1"
        ttl = int(os.getenv("OFFICIAL_READ_FILTERS_CACHE_TTL_SEC", "300"))
        if cache and cache.enabled:
            cached = cache.get_json(key)
            if isinstance(cached, dict):
                return jsonify(cached)
        data = {"organizations": _svc.organizations()}
        if cache and cache.enabled:
            cache.set_json(key, data, ttl=ttl)
        return jsonify(data)
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500


@official_read_bp.get("/list")
def list_docs():
    try:
        data = _svc.list_documents(
            request.args.get("q", ""),
            request.args.get("datePrefix", ""),
            request.args.get("organization", ""),
            request.args.get("page", 1),
            request.args.get("pageSize", 20),
        )
        return jsonify(data)
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500


@official_read_bp.get("/detail")
def detail():
    try:
        return jsonify(_svc.detail(request.args.get("id", "")))
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500


@official_read_bp.get("/direction-analysis")
def direction_analysis():
    try:
        return jsonify(_svc.direction_analysis(request.args.get("id", "")))
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500
