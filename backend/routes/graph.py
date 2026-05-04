import os

from flask import Blueprint, jsonify, request

from services.neo4j_service import Neo4jService

graph_bp = Blueprint("graph", __name__, url_prefix="/api/graph")
service = Neo4jService()


@graph_bp.route("/status", methods=["GET"])
def graph_status():
    info = service.ping()
    hint = info.get("hint") or ""
    pwd_from_env = service.password_from_env
    if not info["ok"] and not pwd_from_env and info.get("kind") == "auth":
        hint = (
            "【关键】未读取到 NEO4J_PASSWORD：Flask 正在使用默认密码 neo4j。"
            "若你已在 Neo4j Desktop/Browser 里改过密码，必须在项目根目录新建文件 .env（不是 .env.example），"
            "并写入 NEO4J_PASSWORD=你的真实密码，保存后重启 Flask。"
            + " "
            + hint
        )
    return jsonify(
        {
            "neo4j_connected": info["ok"],
            "message": info["message"],
            "kind": info.get("kind", "unknown"),
            "hint": hint,
            "uri": service.uri,
            "user": service.user,
            "password_from_env": pwd_from_env,
            "password_source": "env" if pwd_from_env else "default",
            "timeout_sec": float(os.getenv("NEO4J_QUERY_TIMEOUT_SEC", "30")),
        }
    )


@graph_bp.route("/query", methods=["POST"])
def query_graph():
    body = request.get_json(silent=True) or {}
    query = body.get("query", "")
    limit = body.get("limit", 300)
    try:
        data = service.query_graph(query=query, limit=limit)
        return jsonify(data)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    except Exception as exc:
        return jsonify({"error": f"query failed: {exc}"}), 500


@graph_bp.route("/search", methods=["GET"])
def search_nodes():
    keyword = request.args.get("q", "")
    limit = request.args.get("limit", 20)
    try:
        data = service.search_nodes(keyword=keyword, limit=limit)
        return jsonify(data)
    except Exception as exc:
        return jsonify({"error": f"search failed: {exc}"}), 500


@graph_bp.route("/expand", methods=["GET"])
def expand_node():
    node_id = request.args.get("nodeId", "")
    depth = request.args.get("depth", 1)
    limit = request.args.get("limit", 100)
    if not node_id:
        return jsonify({"error": "nodeId is required"}), 400

    try:
        data = service.expand_node(node_id=node_id, depth=depth, limit=limit)
        return jsonify(data)
    except Exception as exc:
        return jsonify({"error": f"expand failed: {exc}"}), 500


@graph_bp.route("/node-detail", methods=["GET"])
def node_detail():
    node_id = request.args.get("nodeId", "")
    if not node_id:
        return jsonify({"error": "nodeId is required"}), 400
    try:
        return jsonify(service.get_node_detail(node_id))
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    except Exception as exc:
        return jsonify({"error": f"node detail failed: {exc}"}), 500


@graph_bp.route("/policy-detail", methods=["GET"])
def policy_detail():
    node_id = request.args.get("nodeId", "")
    if not node_id:
        return jsonify({"error": "nodeId is required"}), 400
    try:
        return jsonify(service.get_policy_detail(node_id))
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    except Exception as exc:
        return jsonify({"error": f"policy detail failed: {exc}"}), 500


@graph_bp.route("/resolve-policy-node", methods=["POST"])
def resolve_policy_node():
    """按采集「标题」「网址」解析 Neo4j 政策节点 id（与入库 MERGE 键一致）。"""
    body = request.get_json(silent=True) or {}
    title = (body.get("title") or "").strip()
    url = (body.get("url") or "").strip()
    if not title and not url:
        return jsonify({"nodeId": None})
    try:
        m = service.match_policies_for_crawler_rows(
            [{"rowId": "x", "title": title, "url": url}]
        )
        info = m.get("x") or {}
        return jsonify({"nodeId": info.get("neo4jId")})
    except Exception as exc:
        return jsonify({"nodeId": None, "error": str(exc)}), 200


@graph_bp.route("/direction-analysis", methods=["GET"])
def direction_analysis():
    node_id = request.args.get("nodeId", "")
    if not node_id:
        return jsonify({"error": "nodeId is required"}), 400
    try:
        return jsonify(service.get_policy_direction_analysis(node_id))
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    except Exception as exc:
        return jsonify({"error": f"direction analysis failed: {exc}"}), 500


@graph_bp.route("/dedupe-db", methods=["POST"])
def dedupe_db():
    try:
        data = service.cleanup_duplicate_data()
        return jsonify(data)
    except Exception as exc:
        return jsonify({"error": f"dedupe db failed: {exc}"}), 500
