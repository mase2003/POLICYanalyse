"""
首页 API：与图谱查询分离，避免与只读 Cypher 校验混在一起。
"""

import os

from runtime_paths import data_path
from flask import Blueprint, current_app, jsonify, request, send_from_directory

from routes.graph import service
from services.home_service import HomeService

home_bp = Blueprint("home", __name__, url_prefix="/api/home")
_hs = HomeService(service)


@home_bp.get("/dashboard")
def dashboard():
    try:
        cache = current_app.extensions.get("redis_cache")
        key = "home:dashboard:v5"
        ttl = int(os.getenv("HOME_DASHBOARD_CACHE_TTL_SEC", "300"))
        if cache and cache.enabled:
            cached = cache.get_json(key)
            if isinstance(cached, dict):
                return jsonify(cached)
        data = _hs.dashboard()
        if cache and cache.enabled:
            cache.set_json(key, data, ttl=ttl)
        return jsonify(data)
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500


@home_bp.post("/search-hit")
def search_hit():
    """检索结果点击时上报，用于累计 searchCount。"""
    body = request.get_json(silent=True) or {}
    node_id = body.get("nodeId", "")
    try:
        data = _hs.increment_search(node_id)
        return jsonify(data)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500


@home_bp.get("/carousel-image/<path:filename>")
def carousel_image(filename: str):
    photo_dir = data_path("STATIC_PHOTO_DIR", "static", "photo")
    return send_from_directory(photo_dir, filename)
