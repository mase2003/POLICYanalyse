import os
import sys
from pathlib import Path

from deployment_root import get_deployment_root
from dotenv import load_dotenv

# 必须在导入 routes（会初始化 Neo4j 连接）之前加载 .env
_backend_dir = Path(__file__).resolve().parent
_project_root = get_deployment_root()
# override=True：以项目 .env 为准，避免系统环境里旧值覆盖你在文件里改的 CATALOG_ORG_PROP 等
load_dotenv(_project_root / ".env", override=True)
load_dotenv(_backend_dir / ".env", override=True)

from flask import Flask, jsonify, make_response, request

from routes.catalog_route import catalog_bp
from routes.crawler_route import crawler_bp
from routes.graph_route import graph_bp, service as graph_service
from routes.home_route import home_bp
from routes.official_read_route import official_read_bp
from routes.policy_forecast_route import policy_forecast_bp
from routes.embeddings_route import embeddings_bp
from routes.search_route import search_bp
from routes.policy_explain_route import policy_explain_bp
from services.policy_data_import_service import PolicyDataImportService
from services.policy_crawler_service import PolicyCrawlerService
from services.redis_cache_service import RedisCacheService
from services.doubao_embedding_service import DoubaoEmbeddingService


def create_app():
    app = Flask(__name__)
    cache = RedisCacheService()
    app.extensions["redis_cache"] = cache

    @app.before_request
    def _api_cors_preflight():
        """浏览器跨域会先发 OPTIONS；保证 /api 下预检不因路由未匹配而 404（并避免旧进程未注册新蓝图时预检失败）。"""
        if request.method == "OPTIONS" and request.path.startswith("/api/"):
            return make_response("", 204)
    app.extensions["policy_crawler_service"] = PolicyCrawlerService(cache)
    app.extensions["policy_data_import_service"] = PolicyDataImportService(graph_service)
    app.extensions["doubao_embedding"] = DoubaoEmbeddingService()

    @app.after_request
    def add_cors_headers(response):
        response.headers["Access-Control-Allow-Origin"] = "*"
        response.headers["Access-Control-Allow-Headers"] = "Content-Type,Authorization,X-Content-Manage-Password"
        response.headers["Access-Control-Allow-Methods"] = "GET,POST,OPTIONS"
        return response

    @app.get("/api/health")
    def health_check():
        redis_ok = cache.ping()
        return jsonify(
            {
                "status": "ok",
                "redis": {
                    "enabled": cache.enabled,
                    "connected": redis_ok,
                    "error": "" if redis_ok else cache.last_error,
                },
            }
        )

    app.register_blueprint(graph_bp)
    app.register_blueprint(home_bp)
    app.register_blueprint(search_bp)
    app.register_blueprint(catalog_bp)
    app.register_blueprint(official_read_bp)
    app.register_blueprint(policy_forecast_bp)
    app.register_blueprint(embeddings_bp)
    app.register_blueprint(crawler_bp)
    app.register_blueprint(policy_explain_bp)
    return app


if __name__ == "__main__":
    app = create_app()
    port = int(os.getenv("FLASK_PORT", "5005"))
    debug = os.getenv("FLASK_DEBUG", "").lower() in ("1", "true", "yes")
    if getattr(sys, "frozen", False) and not os.getenv("FLASK_DEBUG"):
        debug = False
    app.run(host="0.0.0.0", port=port, debug=debug, threaded=True)
