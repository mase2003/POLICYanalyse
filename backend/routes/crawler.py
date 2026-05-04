import hashlib
import os
from datetime import date
from pathlib import Path

from flask import Blueprint, current_app, jsonify, request

from routes.graph import service as graph_service
from runtime_paths import data_path
from services.policy_crawler_service import PolicyCrawlerService

crawler_bp = Blueprint("crawler", __name__, url_prefix="/api/crawler")
_content_pwd_day = ""
_content_pwd_value = ""


def _content_pwd_path() -> Path:
    """政策内容管理每日口令落盘路径，可用 CONTENT_MANAGE_PASSWORD_LOG 覆盖。"""
    return data_path("CONTENT_MANAGE_PASSWORD_LOG", "logs", "policy_content_manage_password.txt")


def _svc():
    service = current_app.extensions.get("policy_crawler_service")
    if service:
        return service
    redis_cache = current_app.extensions.get("redis_cache")
    service = PolicyCrawlerService(redis_cache)
    current_app.extensions["policy_crawler_service"] = service
    return service


def _import_svc():
    return current_app.extensions.get("policy_data_import_service")


def _daily_content_password() -> str:
    """
    每日 6 位数字密码：
    - 按日期 + 服务端密钥派生；
    - 每天变更一次；
    - 当天首次计算时输出到后端日志，并写入 CONTENT_MANAGE_PASSWORD_LOG（默认 logs/ 下）。
    """
    global _content_pwd_day, _content_pwd_value
    today = date.today().strftime("%Y-%m-%d")
    if _content_pwd_day == today and _content_pwd_value:
        return _content_pwd_value

    secret = os.getenv("CONTENT_MANAGE_PASSWORD_SEED") or os.getenv("SECRET_KEY") or "policy-content-manage"
    raw = f"{today}|{secret}|crawler-content".encode("utf-8")
    num = int(hashlib.sha256(raw).hexdigest()[:12], 16) % 1000000
    pwd = f"{num:06d}"
    _content_pwd_day = today
    _content_pwd_value = pwd
    # 打印到后端运行日志（你的 python backend/app.py 终端）
    print(f"[PolicyContentManage] {today} unlock password: {pwd}", flush=True)
    try:
        pwd_path = _content_pwd_path()
        pwd_path.parent.mkdir(parents=True, exist_ok=True)
        pwd_path.write_text(
            f"{today} {pwd}\n",
            encoding="utf-8",
        )
    except Exception:
        # 文件写入失败不影响服务运行
        pass
    return pwd


# 模块加载时先生成当日密码并落盘，确保无需先请求接口也能在日志文件看到密码。
try:
    _daily_content_password()
except Exception:
    pass


def _check_content_password() -> tuple[bool, str]:
    sent = (request.headers.get("X-Content-Manage-Password") or "").strip()
    if not sent:
        return False, "请先解锁政策内容管理功能"
    if sent != _daily_content_password():
        return False, "密码错误或已过期（每日刷新）"
    return True, ""


@crawler_bp.post("/start")
def start():
    body = request.get_json(silent=True) or {}
    try:
        data = _svc().start(body)
        return jsonify(data)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    except Exception as exc:
        return jsonify({"error": f"start failed: {exc}"}), 500


@crawler_bp.get("/latest-task")
def latest_task():
    try:
        return jsonify(_svc().latest_task_snapshot())
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 404
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500


@crawler_bp.get("/status")
def status():
    task_id = request.args.get("taskId", "")
    try:
        data = _svc().status(task_id)
        return jsonify(data)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    except Exception as exc:
        return jsonify({"error": f"status failed: {exc}"}), 500


@crawler_bp.post("/export")
def export_csv():
    body = request.get_json(silent=True) or {}
    task_id = body.get("taskId", "")
    try:
        data = _svc().export_csv(task_id)
        return jsonify(data)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    except Exception as exc:
        return jsonify({"error": f"export failed: {exc}"}), 500


@crawler_bp.post("/export-xlsx")
def export_xlsx():
    body = request.get_json(silent=True) or {}
    task_id = body.get("taskId", "")
    row_ids = body.get("rowIds") or []
    try:
        data = _svc().export_selected_xlsx(task_id, row_ids)
        return jsonify(data)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    except Exception as exc:
        return jsonify({"error": f"export xlsx failed: {exc}"}), 500


@crawler_bp.post("/import-db")
def import_db():
    body = request.get_json(silent=True) or {}
    task_id = body.get("taskId", "")
    row_ids = body.get("rowIds") or []
    try:
        rows = _svc().resolve_import_rows(task_id, row_ids)
        data = _import_svc().import_rows(rows)
        return jsonify(data)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    except Exception as exc:
        return jsonify({"error": f"import db failed: {exc}"}), 500


@crawler_bp.get("/content/list")
def content_list():
    ok, msg = _check_content_password()
    if not ok:
        return jsonify({"error": msg, "locked": True}), 401
    try:
        data = graph_service.list_policy_content(
            keyword=request.args.get("q", ""),
            page=request.args.get("page", 1),
            page_size=request.args.get("pageSize", 20),
        )
        return jsonify(data)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    except Exception as exc:
        return jsonify({"error": f"content list failed: {exc}"}), 500


@crawler_bp.get("/content/detail")
def content_detail():
    ok, msg = _check_content_password()
    if not ok:
        return jsonify({"error": msg, "locked": True}), 401
    node_id = request.args.get("nodeId", "")
    try:
        return jsonify(graph_service.get_policy_content_detail(node_id))
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    except Exception as exc:
        return jsonify({"error": f"content detail failed: {exc}"}), 500


@crawler_bp.post("/content/update-fields")
def content_update_fields():
    ok, msg = _check_content_password()
    if not ok:
        return jsonify({"error": msg, "locked": True}), 401
    body = request.get_json(silent=True) or {}
    try:
        return jsonify(
            graph_service.update_policy_content_fields(
                body.get("nodeId", ""),
                body.get("updates") or {},
            )
        )
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    except Exception as exc:
        return jsonify({"error": f"content update failed: {exc}"}), 500


@crawler_bp.post("/content/delete-field")
def content_delete_field():
    ok, msg = _check_content_password()
    if not ok:
        return jsonify({"error": msg, "locked": True}), 401
    body = request.get_json(silent=True) or {}
    try:
        return jsonify(
            graph_service.delete_policy_content_field(
                body.get("nodeId", ""),
                body.get("field", ""),
            )
        )
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    except Exception as exc:
        return jsonify({"error": f"delete field failed: {exc}"}), 500


@crawler_bp.post("/content/delete-relation")
def content_delete_relation():
    ok, msg = _check_content_password()
    if not ok:
        return jsonify({"error": msg, "locked": True}), 401
    body = request.get_json(silent=True) or {}
    try:
        return jsonify(graph_service.delete_policy_content_relation(body.get("relId", "")))
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    except Exception as exc:
        return jsonify({"error": f"delete relation failed: {exc}"}), 500


@crawler_bp.post("/content/delete-relations")
def content_delete_relations():
    ok, msg = _check_content_password()
    if not ok:
        return jsonify({"error": msg, "locked": True}), 401
    body = request.get_json(silent=True) or {}
    try:
        return jsonify(graph_service.delete_policy_content_relations(body.get("relIds") or []))
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    except Exception as exc:
        return jsonify({"error": f"delete relations failed: {exc}"}), 500


@crawler_bp.post("/content/delete-node")
def content_delete_node():
    ok, msg = _check_content_password()
    if not ok:
        return jsonify({"error": msg, "locked": True}), 401
    body = request.get_json(silent=True) or {}
    try:
        return jsonify(graph_service.delete_policy_content_node(body.get("nodeId", "")))
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    except Exception as exc:
        return jsonify({"error": f"delete node failed: {exc}"}), 500


@crawler_bp.post("/content/unlock")
def content_unlock():
    body = request.get_json(silent=True) or {}
    sent = str(body.get("password") or "").strip()
    if not sent:
        return jsonify({"error": "请输入密码"}), 400
    if sent != _daily_content_password():
        return jsonify({"error": "密码错误或已过期（每日刷新）"}), 401
    return jsonify({"ok": True})
