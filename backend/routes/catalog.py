"""
政策目录 API：发文机构列表、主题词列表、分页政策表。
"""

import os

from flask import Blueprint, current_app, jsonify, request

from routes.graph import service
from services.catalog_service import CatalogService
from services.policy_node_scope import PolicyNodeScope

catalog_bp = Blueprint("catalog", __name__, url_prefix="/api/catalog")

# 与顶栏搜索共用：节点标签 + MATCH(n)/MATCH(n:Label)
policy_scope = PolicyNodeScope(service)
# 先解析「发文机构」实际属性名，再建 CatalogService，避免 prop_org 快照过期
policy_scope._ensure_org_prop()
_cs = CatalogService(service, policy_scope)


@catalog_bp.get("/topics")
def topics():
    try:
        return jsonify({"topics": _cs.topics()})
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500


@catalog_bp.get("/topic-children")
def topic_children():
    topic = request.args.get("topic", "")
    try:
        return jsonify({"items": _cs.topic_children(topic)})
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500


@catalog_bp.get("/organizations")
def organizations():
    try:
        return jsonify({"organizations": _cs.organizations()})
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500


@catalog_bp.get("/debug-env")
def debug_env():
    """确认 Flask 进程实际读到的环境变量（与 .env 不一致时多为未重启或曾被系统环境覆盖）。"""
    return jsonify(
        {
            "CATALOG_ORG_PROP": os.getenv("CATALOG_ORG_PROP"),
            "CATALOG_ORG_NODE_LABEL": os.getenv("CATALOG_ORG_NODE_LABEL"),
            "CATALOG_ORG_NODE_NAME_PROP": os.getenv("CATALOG_ORG_NODE_NAME_PROP"),
            "SEARCH_ORG_PROP": os.getenv("SEARCH_ORG_PROP"),
            "HOME_POLICY_LABEL": os.getenv("HOME_POLICY_LABEL"),
            "SEARCH_POLICY_LABEL": os.getenv("SEARCH_POLICY_LABEL"),
            "resolvedCatalogOrgProp": policy_scope.org_prop,
            "resolvedCatalogOrgNodeLabel": policy_scope.org_node_label,
            "note": "项目根目录 .env 已用 load_dotenv(override=True) 加载；改完后请完全重启 Flask。",
        }
    )


def _is_org_like_property_key(k: str) -> bool:
    if not k:
        return False
    if "机构" in k or "单位" in k or "部门" in k:
        return True
    kl = k.lower()
    return any(x in kl for x in ("org", "issuer", "publish", "unit", "department", "bureau"))


@catalog_bp.get("/inspect")
def inspect():
    """返回带政策标签的若干节点的 properties，便于对照填写 CATALOG_ORG_PROP（须与键名完全一致）。
    若机构是独立标签节点（CATALOG_ORG_NODE_LABEL），政策节点上可无「发文机构」属性；此时看 schema.catalogOrgMode 与 policyNodesLinkedToAnyOrg。"""
    lb = policy_scope.label
    try:
        rows = service._run(
            f"MATCH (n:`{lb}`) RETURN properties(n) AS props LIMIT 5",
            {},
            timeout=15.0,
        )
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500
    samples = []
    keys_union: set[str] = set()
    for r in rows:
        props = r.get("props")
        if not isinstance(props, dict):
            continue
        keys_union.update(props.keys())
        row = {}
        for k, v in props.items():
            if v is None:
                row[k] = None
            elif isinstance(v, (bool, int, float)):
                row[k] = v
            else:
                s = str(v)
                row[k] = s if len(s) <= 300 else s[:300] + "…"
        samples.append(row)

    configured = (os.getenv("CATALOG_ORG_PROP") or os.getenv("SEARCH_ORG_PROP") or "发文机构").strip()
    likely_org_keys = sorted(k for k in keys_union if _is_org_like_property_key(k))
    has_configured_key = configured in keys_union

    issue = None
    hint_detail = ""
    if not keys_union:
        issue = "no_nodes_or_empty_props"
        hint_detail = "未读到任何属性，请确认 HOME_POLICY_LABEL 与库中节点标签一致。"
    elif keys_union == {"name"} or keys_union <= {"name"}:
        issue = "only_name_property"
        hint_detail = (
            "样本节点上只有 name：这是「政策名称/标题」，不是发文单位。"
            "设置 CATALOG_ORG_PROP=发文机构 无效，因为图中没有「发文机构」这个属性键。"
            "需要先在 Neo4j 里为政策节点写入发文机构字段（或你们库里的真实键名），再把它填进 CATALOG_ORG_PROP。"
        )
    elif not likely_org_keys and not has_configured_key:
        issue = "no_org_property_on_nodes"
        hint_detail = (
            "样本里没有出现 .env 中的 CATALOG_ORG_PROP 键名，也没有明显「机构」类属性。"
            "仅改 .env 不能凭空生成机构列表，请核对导入数据是否包含机构字段。"
        )

    return jsonify(
        {
            "policyLabel": lb,
            "propertyKeysUnion": sorted(keys_union),
            "likelyOrgPropertyKeys": likely_org_keys,
            "envCatalogOrgProp": configured,
            "envKeyPresentOnSamples": has_configured_key,
            "issue": issue,
            "sampleNodesProperties": samples,
            "hint": (
                "若样本里已有「发文机构」或类似键：把左侧键名原样写入 .env 的 CATALOG_ORG_PROP=键名，保存后重启 Flask。"
                + (" " + hint_detail if hint_detail else "")
            ),
        }
    )


@catalog_bp.get("/filters")
def filters():
    """一次返回主题词 + 发文机构 + schema（含诊断计数），减少前端往返。"""
    try:
        cache = current_app.extensions.get("redis_cache")
        key = "catalog:filters:v1"
        ttl = int(os.getenv("CATALOG_FILTERS_CACHE_TTL_SEC", "300"))
        if cache and cache.enabled:
            cached = cache.get_json(key)
            if isinstance(cached, dict):
                return jsonify(cached)

        organizations = _cs.organizations()
        regions = _cs.regions()
        data = {
            "topics": _cs.topics(),
            "organizations": organizations,
            "regions": regions,
            "schema": policy_scope.public_schema(),
            "samplePropertyKeys": policy_scope.sample_policy_node_keys(),
        }
        if cache and cache.enabled:
            cache.set_json(key, data, ttl=ttl)
        return jsonify(data)
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500


@catalog_bp.get("/policies")
def policies():
    list_mode = request.args.get("listMode", "organization")
    org = request.args.get("organization", "")
    cat = request.args.get("category", "")
    topic_child = request.args.get("topicChild", "")
    source_region = request.args.get("sourceRegion", "")
    page = request.args.get("page", "1")
    page_size = request.args.get("pageSize", "20")
    try:
        data = _cs.policies(
            list_mode,
            org,
            cat,
            topic_child,
            page,
            page_size,
            source_region,
        )
        return jsonify(data)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500
