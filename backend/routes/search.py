from flask import Blueprint, jsonify, request

from routes.catalog import policy_scope
from routes.graph import service
from services.policy_search_service import PolicySearchService

search_bp = Blueprint("search", __name__, url_prefix="/api/search")
_service = PolicySearchService(service, policy_scope)


@search_bp.route("/policies", methods=["GET"])
def search_policies():
    q = request.args.get("q", "")
    limit = request.args.get("limit", 30)
    try:
        lim = int(limit)
    except (TypeError, ValueError):
        lim = 30
    try:
        data = _service.search(q, lim)
        return jsonify(data)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    except Exception as exc:
        return jsonify({"error": f"search failed: {exc}"}), 500
