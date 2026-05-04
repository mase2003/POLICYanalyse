from flask import Blueprint, current_app, jsonify, request

embeddings_bp = Blueprint("embeddings", __name__, url_prefix="/api/embeddings")


def _svc():
    return current_app.extensions.get("doubao_embedding")


@embeddings_bp.get("/status")
def status():
    svc = _svc()
    if not svc:
        return jsonify({"error": "服务未初始化"}), 500
    return jsonify(svc.status())


@embeddings_bp.post("/doubao")
def doubao_embed():
    svc = _svc()
    if not svc:
        return jsonify({"error": "服务未初始化"}), 500
    if not svc.is_configured():
        return (
            jsonify(
                {
                    "error": "豆包向量化未配置",
                    "hint": "在 .env 中设置 ARK_API_KEY（或 DOUBAO_API_KEY）与 ARK_EMBEDDING_MODEL；"
                    "可选 ARK_EMBEDDING_BASE_URL（默认北京区 api/v3）。",
                    "doc": "https://www.volcengine.com/docs/82379/1523520?redirect=1&lang=zh",
                }
            ),
            503,
        )

    body = request.get_json(silent=True) or {}
    single = body.get("input")
    multi = body.get("inputs")
    texts: list[str] = []
    if multi is not None:
        if not isinstance(multi, list):
            return jsonify({"error": "inputs 须为字符串数组"}), 400
        texts = [str(x) for x in multi]
    elif single is not None:
        texts = [str(single)]
    else:
        return jsonify({"error": "请提供 input（单条字符串）或 inputs（字符串数组）"}), 400

    if len(texts) > 200:
        return jsonify({"error": "单次最多 200 条文本"}), 400

    try:
        out = svc.embed_texts(texts)
        return jsonify(out)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500
