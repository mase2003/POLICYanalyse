import os

from flask import Blueprint, current_app, jsonify, request

from routes.graph import service as graph_service
from services.policy_explain_service import (
    check_and_touch_rate_limit_ip,
    client_ip_from_request,
    is_unlimited_ip,
    run_deconstruct,
)

policy_explain_bp = Blueprint("policy_explain", __name__, url_prefix="/api/policy-explain")


@policy_explain_bp.route("/deconstruct", methods=["POST", "OPTIONS"])
def deconstruct():
    if request.method == "OPTIONS":
        return ("", 204)

    body = request.get_json(silent=True) or {}
    node_id = str(body.get("nodeId") or "").strip()
    if not node_id:
        return jsonify({"error": "请提供 nodeId"}), 400

    daily_limit = max(0, int(os.getenv("POLICY_EXPLAIN_DAILY_LIMIT", "2")))
    ip = client_ip_from_request(request)
    unlimited = is_unlimited_ip(ip)
    cache = current_app.extensions.get("redis_cache")
    ok, used, msg = check_and_touch_rate_limit_ip(cache, ip, daily_limit, unlimited)
    if not ok:
        return jsonify({"error": msg, "rateLimited": True, "clientIp": ip, "used": used}), 429

    try:
        detail = graph_service.get_policy_detail(node_id)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    except Exception as exc:
        return jsonify({"error": f"读取政策详情失败: {exc}"}), 500

    try:
        data = run_deconstruct(graph_service, detail, node_id)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    except Exception as exc:
        return jsonify({"error": f"政策拆解失败: {exc}"}), 500

    data["clientIp"] = ip
    data["unlimitedIp"] = unlimited
    data["dailyLimit"] = daily_limit if not unlimited else None
    data["usedToday"] = used
    return jsonify(data)
