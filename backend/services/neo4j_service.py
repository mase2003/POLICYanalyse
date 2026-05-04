import os
import re
from dataclasses import dataclass

from neo4j import GraphDatabase
from neo4j.exceptions import AuthError, ServiceUnavailable

from services.text_keyword_stats import analyze_policy_text
from utils.cypher_guard import internal_scan_limit, validate_user_cypher


def _serialize_value(value):
    if value is None:
        return None
    if isinstance(value, (bool, int, float, str)):
        return value
    if isinstance(value, (list, tuple)):
        return [_serialize_value(v) for v in value]
    if isinstance(value, dict):
        return {k: _serialize_value(v) for k, v in value.items()}
    if hasattr(value, "iso_format"):
        return value.iso_format()
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return str(value)


def _serialize_props(node_or_rel):
    return {k: _serialize_value(v) for k, v in node_or_rel.items()}


def _first_nonempty_prop(props: dict, keys: list) -> str | None:
    for pk in keys:
        if not pk or pk not in props:
            continue
        val = props[pk]
        if val in (None, ""):
            continue
        v = str(val).strip()
        if v and v.lower() != "nan":
            return v
    return None


@dataclass
class GraphPayload:
    nodes: list
    edges: list
    total: int
    has_more: bool
    cursor: int


class Neo4jService:
    def __init__(self):
        # strip 避免 .env 里换行/BOM 导致密码错误
        self.uri = (os.getenv("NEO4J_URI") or "bolt://localhost:7687").strip()
        self.user = (os.getenv("NEO4J_USER") or "neo4j").strip()
        raw_pw = os.getenv("NEO4J_PASSWORD")
        if raw_pw is None:
            self.password = "neo4j"
            self.password_from_env = False
        else:
            self.password = raw_pw.strip()
            self.password_from_env = len(self.password) > 0
        self.driver = GraphDatabase.driver(self.uri, auth=(self.user, self.password))
        self._query_timeout = float(os.getenv("NEO4J_QUERY_TIMEOUT_SEC", "30"))
        self._ping_timeout = float(os.getenv("NEO4J_PING_TIMEOUT_SEC", "5"))

    def close(self):
        self.driver.close()

    @staticmethod
    def _safe_int(value):
        try:
            return int(value)
        except (TypeError, ValueError):
            return 0

    @staticmethod
    def _safe_property_key(value: str) -> str:
        """
        内容管理页字段键名校验：
        - 允许中文字段中的反斜杠、斜杠、空格等（如「发文字号\\文号」「有 效 性」）
        - 禁止反引号，避免拼接反引号属性时破坏 Cypher
        """
        t = str(value or "").strip()
        if not t:
            raise ValueError("字段名不能为空")
        if "`" in t:
            raise ValueError(f"非法字段名: {value!r}")
        return t

    def _run(self, cypher, params=None, timeout=None):
        params = params or {}
        timeout = self._query_timeout if timeout is None else timeout
        with self.driver.session() as session:
            return list(session.run(cypher, params, timeout=timeout))

    def ping(self):
        """返回诊断信息 dict，供 /api/graph/status 使用。"""
        try:
            with self.driver.session() as session:
                list(session.run("RETURN 1 AS ok", timeout=self._ping_timeout))
            return {
                "ok": True,
                "message": "已连接",
                "kind": "ok",
                "hint": "",
            }
        except AuthError as exc:
            return {
                "ok": False,
                "message": str(exc),
                "kind": "auth",
                "hint": (
                    "认证失败：用户名或密码与 Neo4j 不一致。"
                    "若已修改项目根目录的 .env，请保存后完全退出并重新启动 Flask。"
                    "若在 Neo4j Browser 能登录，请把同一组账号密码写入 .env 的 NEO4J_USER / NEO4J_PASSWORD。"
                ),
            }
        except ServiceUnavailable as exc:
            return {
                "ok": False,
                "message": str(exc),
                "kind": "network",
                "hint": (
                    "连不上 Neo4j 进程：请确认已用 neo4j.bat console 或 Windows 服务启动数据库，"
                    "且 NEO4J_URI 为 bolt://localhost:7687（与 Neo4j 配置的 Bolt 端口一致）。"
                ),
            }
        except Exception as exc:
            return {
                "ok": False,
                "message": str(exc),
                "kind": "unknown",
                "hint": "请根据 message 排查；也可在浏览器访问 Neo4j Browser 对比能否登录。",
            }

    def _to_graph(self, records, limit):
        nodes = {}
        edges = {}

        for record in records:
            for value in record.values():
                if hasattr(value, "nodes") and hasattr(value, "relationships"):
                    for node in value.nodes:
                        key = str(node.id)
                        nodes[key] = {
                            "id": key,
                            "labels": list(node.labels),
                            "properties": _serialize_props(node),
                        }
                    for rel in value.relationships:
                        key = str(rel.id)
                        edges[key] = {
                            "id": key,
                            "type": rel.type,
                            "source": str(rel.start_node.id),
                            "target": str(rel.end_node.id),
                            "properties": _serialize_props(rel),
                        }
                elif hasattr(value, "type") and hasattr(value, "start_node"):
                    rel = value
                    key = str(rel.id)
                    edges[key] = {
                        "id": key,
                        "type": rel.type,
                        "source": str(rel.start_node.id),
                        "target": str(rel.end_node.id),
                        "properties": _serialize_props(rel),
                    }
                elif hasattr(value, "labels") and hasattr(value, "items"):
                    key = str(value.id)
                    nodes[key] = {
                        "id": key,
                        "labels": list(value.labels),
                        "properties": _serialize_props(value),
                    }

        edge_list = list(edges.values())
        total = len(edge_list)
        limited_edges = edge_list[:limit]

        valid_node_ids = set()
        for edge in limited_edges:
            valid_node_ids.add(edge["source"])
            valid_node_ids.add(edge["target"])

        if limited_edges:
            node_list = [node for node in nodes.values() if node["id"] in valid_node_ids]
        else:
            node_list = list(nodes.values())
        return GraphPayload(
            nodes=node_list,
            edges=limited_edges,
            total=total,
            has_more=total > limit,
            cursor=min(limit, total),
        )

    @staticmethod
    def _pick_single_publish_level_edge(edges: list[dict], nodes_by_id: dict[str, dict], node_id: str):
        candidates = [
            e
            for e in edges
            if str(e.get("source")) == node_id and str(e.get("type") or "").strip() == "发文级别"
        ]
        if not candidates:
            return None

        def _score(edge: dict) -> tuple[int, int, str]:
            target_id = str(edge.get("target") or "")
            target = nodes_by_id.get(target_id) or {}
            props = target.get("properties") or {}
            name = str(props.get("name") or props.get("发文级别") or "").strip()
            prefer_city = 1 if "市级" in name else 0
            # 同分时优先更短、更稳定的值，避免每次显示不同。
            return (prefer_city, -len(name), name)

        return max(candidates, key=_score)

    def _collapse_publish_level_edges_for_node(self, payload: GraphPayload, node_id: str) -> GraphPayload:
        edges = list(payload.edges or [])
        nodes = list(payload.nodes or [])
        nodes_by_id = {str(n.get("id")): n for n in nodes if n and n.get("id") is not None}
        keep = self._pick_single_publish_level_edge(edges, nodes_by_id, node_id)
        out_edges = []
        for edge in edges:
            is_publish_level = (
                str(edge.get("source")) == node_id and str(edge.get("type") or "").strip() == "发文级别"
            )
            if not is_publish_level:
                out_edges.append(edge)
                continue
            if keep and str(edge.get("id")) == str(keep.get("id")):
                out_edges.append(edge)

        used_ids = set()
        for edge in out_edges:
            used_ids.add(str(edge.get("source")))
            used_ids.add(str(edge.get("target")))
        out_nodes = [n for n in nodes if str(n.get("id")) in used_ids]

        return GraphPayload(
            nodes=out_nodes,
            edges=out_edges,
            total=len(out_edges),
            has_more=payload.has_more,
            cursor=min(payload.cursor, len(out_edges)),
        )

    def query_graph(self, query, limit=300):
        limit = max(1, min(self._safe_int(limit) or 300, 300))
        cypher = query.strip() if query else ""
        if not cypher:
            cypher = "MATCH p=(n)-[r]->(m) RETURN p LIMIT 5000"
        else:
            cypher = validate_user_cypher(cypher)

        records = self._run(cypher, timeout=self._query_timeout)
        payload = self._to_graph(records, limit)
        return payload.__dict__

    def search_nodes(self, keyword, limit=20):
        limit = max(1, min(self._safe_int(limit) or 20, 100))
        kw = (keyword or "").strip()
        if not kw:
            return {"items": []}

        cypher = """
        MATCH (n)
        WHERE any(k IN keys(n) WHERE toString(n[k]) CONTAINS $kw)
        RETURN n
        LIMIT $limit
        """
        records = self._run(cypher, {"kw": kw, "limit": limit})
        items = []
        for rec in records:
            node = rec.get("n")
            items.append(
                {
                    "id": str(node.id),
                    "labels": list(node.labels),
                    "properties": _serialize_props(node),
                }
            )
        return {"items": items}

    def expand_node(self, node_id, depth=1, limit=100):
        depth = max(1, min(self._safe_int(depth) or 1, 3))
        limit = max(1, min(self._safe_int(limit) or 100, 300))
        scan_limit = internal_scan_limit()
        cypher = f"""
        MATCH p=(n)-[*1..{depth}]-(m)
        WHERE id(n) = toInteger($node_id)
        RETURN p
        LIMIT $scan_limit
        """
        records = self._run(
            cypher,
            {"node_id": node_id, "scan_limit": scan_limit},
            timeout=self._query_timeout,
        )
        payload = self._to_graph(records, limit)
        payload = self._collapse_publish_level_edges_for_node(payload, str(node_id))
        out = payload.__dict__
        out["scan_limit"] = scan_limit
        return out

    def get_node_detail(self, node_id):
        if self._safe_int(node_id) <= 0 and str(node_id) != "0":
            raise ValueError("nodeId 必须是数字")
        cypher = """
        MATCH (n)
        WHERE id(n) = toInteger($node_id)
        RETURN n
        LIMIT 1
        """
        rows = self._run(cypher, {"node_id": node_id}, timeout=self._query_timeout)
        if not rows:
            raise ValueError("节点不存在")
        node = rows[0].get("n")
        return {
            "id": str(node.id),
            "labels": list(node.labels),
            "properties": _serialize_props(node),
        }

    @staticmethod
    def _pick_property(props, keys):
        for key in keys:
            value = props.get(key)
            if value is None:
                continue
            text = str(value).strip()
            if text and text.lower() != "nan":
                return text
        return ""

    def get_policy_detail(self, node_id):
        if self._safe_int(node_id) <= 0 and str(node_id) != "0":
            raise ValueError("nodeId 必须是数字")
        cypher = """
        MATCH (n)
        WHERE id(n) = toInteger($node_id)
        OPTIONAL MATCH (n)--(m)
        RETURN n, collect(DISTINCT m) AS neighbors
        LIMIT 1
        """
        rows = self._run(cypher, {"node_id": node_id}, timeout=self._query_timeout)
        if not rows:
            raise ValueError("节点不存在")
        row = rows[0]
        node = row.get("n")
        neighbors = row.get("neighbors") or []
        node_props = _serialize_props(node)
        neighbor_items = [
            {
                "labels": list(neighbor.labels),
                "properties": _serialize_props(neighbor),
            }
            for neighbor in neighbors
            if neighbor is not None
        ]

        field_aliases = {
            "来源": ["来源", "source"],
            "标题": ["标题", "文件名称", "name", "title"],
            "网址": ["网址", "url", "链接"],
            "正文": ["正文", "content", "内容", "全文", "text"],
            "政策拆解全文": ["政策拆解全文", "policyExplainText", "政策拆解"],
            "公文种类": ["公文种类"],
            "发文机构\\发文机构": ["发文机构\\发文机构", "发文机构\\发布机构", "发文机构", "发布机构"],
            "发布日期": ["发布日期", "发文日期", "日期", "publishDate", "date"],
            "联合发文单位": ["联合发文单位"],
            "发文字号\\文号": ["发文字号\\文号", "发文字号", "文号"],
            "索引号": ["索引号"],
            "主题分类\\分类": ["主题分类\\分类", "主题分类", "分类", "政策类型", "主题词"],
            "成文日期\\印发日期": ["成文日期\\印发日期", "成文日期", "印发日期"],
            "实施日期": ["实施日期", "施行时间"],
            "废止日期": ["废止日期"],
            "有效性": ["有效性"],
            "附件": ["附件"],
        }
        neighbor_label_aliases = {
            "正文": ["正文", "政策解读正文", "内容", "全文"],
            "发文机构\\发文机构": ["发文机构", "发布机构", "责任机构或人", "机构"],
            "发布日期": ["发布日期", "发文日期", "日期"],
            "联合发文单位": ["联合发文单位"],
            "发文字号\\文号": ["发文字号", "文号"],
            "索引号": ["索引号"],
            "主题分类\\分类": ["主题分类", "分类", "政策类型", "主题词"],
            "成文日期\\印发日期": ["成文日期", "印发日期"],
            "实施日期": ["实施日期", "施行时间"],
            "废止日期": ["废止日期"],
            "有效性": ["有效性"],
            "附件": ["附件"],
            "公文种类": ["公文种类"],
            "来源": ["来源"],
        }
        value_prop_aliases = [
            "name",
            "标题",
            "文件名称",
            "title",
            "value",
            "content",
            "正文",
            "内容",
            "全文",
            "text",
            "url",
            "网址",
            "发文机构",
            "发布机构",
            "发布日期",
            "发文日期",
            "主题分类",
            "分类",
        ]

        resolved = {}
        for field, aliases in field_aliases.items():
            value = self._pick_property(node_props, aliases)
            if not value:
                for item in neighbor_items:
                    labels = item["labels"]
                    props = item["properties"]
                    if any(alias in labels for alias in neighbor_label_aliases.get(field, [])):
                        value = self._pick_property(props, aliases + value_prop_aliases)
                    if not value:
                        value = self._pick_property(props, aliases)
                    if value:
                        break
            if field == "正文" and not value:
                fallback_texts = []
                for item in neighbor_items:
                    text = self._pick_property(item["properties"], value_prop_aliases)
                    if text and len(text) >= 20:
                        fallback_texts.append(text)
                if fallback_texts:
                    value = max(fallback_texts, key=len)
            resolved[field] = value

        return {
            "id": str(node.id),
            "labels": list(node.labels),
            "properties": node_props,
            "detail": resolved,
            "neighbors": neighbor_items,
        }

    def get_policy_direction_analysis(self, node_id):
        detail_data = self.get_policy_detail(node_id)
        detail = detail_data.get("detail") or {}
        text = "\n".join([str(detail.get("标题") or ""), str(detail.get("正文") or "")]).strip()
        return analyze_policy_text(text)

    @staticmethod
    def _safe_policy_ident(s: str) -> str:
        t = (s or "").strip()
        if not t or not re.match(r"^[\u4e00-\u9fffa-zA-Z0-9_]+$", t):
            raise ValueError(f"非法 Neo4j 标签/属性名: {s!r}")
        return t

    def match_policies_for_crawler_rows(self, items: list) -> dict:
        """
        按采集「标题」或「网址」在政策节点上解析图库中的展示名（默认属性 SEARCH_FILE_PROP /「文件名称」）。
        items: [{"rowId": str, "title": str, "url": str}, ...]
        返回: rowId -> {"neo4jId": str | None, "文件名称": str | None}
        """
        if not items:
            return {}
        raw_label = (
            os.getenv("SEARCH_POLICY_LABEL") or os.getenv("HOME_POLICY_LABEL") or "文件名称"
        ).strip()
        raw_title_prop = (os.getenv("HOME_TITLE_PROP") or "name").strip()
        raw_file_prop = (os.getenv("SEARCH_FILE_PROP") or "文件名称").strip() or "文件名称"
        try:
            label = self._safe_policy_ident(raw_label)
            title_prop = self._safe_policy_ident(raw_title_prop)
            file_prop = self._safe_policy_ident(raw_file_prop)
        except ValueError:
            return {}

        cypher = f"""
        UNWIND $items AS row
        OPTIONAL MATCH (n:`{label}`)
        WHERE trim(toString(coalesce(n.`{title_prop}`, ""))) = row.title
           OR trim(toString(coalesce(n.`标题`, ""))) = row.title
           OR trim(toString(coalesce(n.`{file_prop}`, ""))) = row.title
           OR (coalesce(row.url, "") <> ''
               AND trim(toString(coalesce(n.`网址`, ""))) = trim(toString(row.url)))
        WITH row, n
        ORDER BY row.rowId, id(n)
        WITH row, collect(n) AS ns
        WITH row, head([x IN ns WHERE x IS NOT NULL]) AS n
        RETURN row.rowId AS rowId,
          CASE WHEN n IS NULL THEN NULL ELSE id(n) END AS neo4jId,
          CASE WHEN n IS NULL THEN NULL
               ELSE trim(toString(coalesce(n.`{file_prop}`, n.`标题`, n.`{title_prop}`)))
          END AS graphFileName
        """
        try:
            rows = self._run(cypher, {"items": items}, timeout=self._query_timeout)
        except Exception:
            return {}
        out: dict = {}
        for rec in rows or []:
            rid = rec.get("rowId")
            if rid is None:
                continue
            rid_s = str(rid)
            nid = rec.get("neo4jId")
            gfn = rec.get("graphFileName")
            gfn_s = str(gfn).strip() if gfn not in (None, "") else None
            out[rid_s] = {
                "neo4jId": None if nid is None else str(int(nid)),
                "文件名称": gfn_s,
            }
        return out

    def search_nodes_by_file_name_keywords(self, keywords: list) -> list:
        """
        在标签为政策类节点（默认 :`文件名称`）上，对「文件名称」属性、以及「标题」与 HOME_TITLE_PROP（如 name）做 CONTAINS 匹配（兼容旧节点）。
        keywords: 用户选择的关键词列表
        返回: [{"_rowId","neo4jId","文件名称","matchedKeywords","标题","网址",...}, ...]
        """
        kws = [str(k).strip() for k in (keywords or []) if str(k).strip()]
        if not kws:
            return []
        try:
            label = self._safe_policy_ident(
                (os.getenv("SEARCH_POLICY_LABEL") or os.getenv("HOME_POLICY_LABEL") or "文件名称").strip()
            )
            file_prop = self._safe_policy_ident(
                (os.getenv("SEARCH_FILE_PROP") or "文件名称").strip() or "文件名称"
            )
        except ValueError:
            return []
        # 旧数据可能只有 name /「标题」没有填「文件名称」：多字段 OR 匹配；LIMIT 过小 + 无 ORDER 时引擎可能只扫到部分节点
        lim_raw = int(os.getenv("POLICY_PARSE_STEP5_NEO4J_LIMIT", "8000"))
        limit = min(50000, max(200, lim_raw))
        try:
            title_prop = self._safe_policy_ident((os.getenv("HOME_TITLE_PROP") or "name").strip())
        except ValueError:
            title_prop = "name"
        cypher = f"""
        MATCH (n:`{label}`)
        WHERE any(k IN $keywords WHERE k <> '' AND (
          toString(coalesce(n.`{file_prop}`, '')) CONTAINS k
          OR toString(coalesce(n.`标题`, '')) CONTAINS k
          OR toString(coalesce(n.`{title_prop}`, '')) CONTAINS k
        ))
        OPTIONAL MATCH (n)--(d_date:`发文日期`)
        WITH n, collect(DISTINCT d_date) AS date_nodes
        OPTIONAL MATCH (n)--(d_topic:`主题分类`)
        WITH n, date_nodes, collect(DISTINCT d_topic) AS topic_nodes
        OPTIONAL MATCH (n)--(d_org:`发文机构`)
        WITH n, date_nodes, topic_nodes, collect(DISTINCT d_org) AS org_nodes
        RETURN
          n AS n,
          head([x IN date_nodes WHERE x IS NOT NULL]) AS d_date,
          head([x IN topic_nodes WHERE x IS NOT NULL]) AS d_topic,
          head([x IN org_nodes WHERE x IS NOT NULL]) AS d_org
        ORDER BY id(n) ASC
        LIMIT $lim
        """
        try:
            records = self._run(cypher, {"keywords": kws, "lim": int(limit)}, timeout=self._query_timeout)
        except Exception:
            return []
        seen: set = set()
        out: list = []
        for rec in records or []:
            node = rec.get("n")
            if node is None:
                continue
            nid = int(node.id)
            if nid in seen:
                continue
            seen.add(nid)
            props = _serialize_props(node)
            fn_text = (
                str(props.get(file_prop) or "").strip()
                or str(props.get("标题") or "").strip()
                or str(props.get(title_prop) or "").strip()
            )
            field_texts = [
                str(props.get(file_prop) or ""),
                str(props.get("标题") or ""),
                str(props.get(title_prop) or ""),
            ]
            hits = [
                k
                for k in kws
                if k and any(k in t for t in field_texts)
            ]
            if not hits:
                continue
            row = {
                "_rowId": f"neo_{nid}",
                "neo4jId": str(nid),
                "文件名称": fn_text,
                "matchedKeywords": hits,
            }
            title = (props.get("标题") or props.get(title_prop) or props.get("name") or "").strip()
            if title:
                row["标题"] = title

            date_keys = list(
                dict.fromkeys(
                    [
                        (os.getenv("HOME_DATE_PROP") or "发文日期").strip(),
                        "发文日期",
                        "发布日期",
                    ]
                )
            )
            topic_keys = list(
                dict.fromkeys(
                    [
                        "主题分类\\分类",
                        "主题分类",
                        (os.getenv("HOME_CATEGORY_PROP") or "政策类型").strip(),
                        "主题词",
                    ]
                )
            )
            org_keys = list(
                dict.fromkeys(
                    [
                        "发文机构\\发文机构",
                        "发文机构",
                        "发布机构",
                        (os.getenv("CATALOG_ORG_PROP") or os.getenv("SEARCH_ORG_PROP") or "发文机构").strip(),
                    ]
                )
            )
            fd = _first_nonempty_prop(props, date_keys)
            if fd:
                row["发文日期"] = fd
            tc = _first_nonempty_prop(props, topic_keys)
            if tc:
                row["主题分类"] = tc
            og = _first_nonempty_prop(props, org_keys)
            if og:
                row["发文机构"] = og

            date_node = rec.get("d_date")
            if date_node is not None and not row.get("发文日期"):
                date_props = _serialize_props(date_node)
                fd = _first_nonempty_prop(
                    date_props,
                    ["name", "发文日期", "日期", "发布日期", "value", "title", "名称"],
                )
                if fd:
                    row["发文日期"] = fd

            topic_node = rec.get("d_topic")
            if topic_node is not None and not row.get("主题分类"):
                topic_props = _serialize_props(topic_node)
                tc = _first_nonempty_prop(
                    topic_props,
                    ["name", "主题分类", "分类", "主题词", "value", "title", "名称"],
                )
                if tc:
                    row["主题分类"] = tc

            org_node = rec.get("d_org")
            if org_node is not None and not row.get("发文机构"):
                org_props = _serialize_props(org_node)
                og = _first_nonempty_prop(
                    org_props,
                    ["name", "发文机构", "发布机构", "机构", "单位", "value", "title", "名称"],
                )
                if og:
                    row["发文机构"] = og
            out.append(row)
        return out

    @staticmethod
    def _blank_explain_value(v) -> bool:
        if v is None:
            return True
        t = str(v).strip()
        return not t or t.lower() in ("nan", "none") or t in ("无", "无。")

    def import_policy_explain_graph(self, node_id, row: dict, raw_llm_text: str) -> None:
        """
        将政策拆解一行写入图库：与 text1.py 一致的关系类型与值节点标签；
        并在政策节点上写入「政策拆解全文」便于 policy-detail 展示。
        row 的键须与 policyexplain.csv 列名一致。
        """
        nid = self._safe_int(node_id)
        if nid <= 0 and str(node_id) != "0":
            raise ValueError("nodeId 无效")

        from datetime import datetime

        ts = datetime.now().astimezone().isoformat(timespec="seconds")

        def esc_rel(rel: str) -> str:
            if not rel or not re.match(r"^[\u4e00-\u9fffa-zA-Z0-9_]+$", rel):
                raise ValueError(f"非法关系类型: {rel!r}")
            return rel

        def esc_label(lb: str) -> str:
            if not lb or not re.match(r"^[\u4e00-\u9fffa-zA-Z0-9_]+$", lb):
                raise ValueError(f"非法标签: {lb!r}")
            return lb

        # 与 text1.py：文件级别列 → 发文级别 节点与关系
        direct: list[tuple[str, str, str]] = [
            ("文件级别", "发文级别", "发文级别"),
            ("公文种类", "公文种类", "公文种类"),
            ("主题分类", "主题分类", "主题分类"),
            ("继承关系", "继承关系", "继承关系"),
            ("联系", "联系", "联系"),
            ("关联内容", "关联内容", "关联内容"),
            ("变动", "变动", "变动"),
            ("推行和改革要求", "推行和改革要求", "推行和改革要求"),
            ("实施内容", "实施内容", "实施内容"),
            ("对应群体", "对应群体", "对应群体"),
            ("对应区域", "对应区域", "对应区域"),
            ("对应方向", "对应方向", "对应方向"),
            ("对应经济文化", "对应经济文化", "对应经济文化"),
            ("责任机构或人", "责任机构或人", "责任机构或人"),
            ("具体事权", "具体事权", "具体事权"),
            ("具体面向对象", "具体面向对象", "具体面向对象"),
            ("必要条件", "必要条件", "必要条件"),
            ("管理标准", "管理标准", "管理标准"),
            ("审核过程", "审核过程", "审核过程"),
            ("施行时间", "施行时间", "施行时间"),
            ("附件", "附件", "附件"),
        ]

        params_base = {
            "node_id": nid,
            "政策拆解全文": (raw_llm_text or "").strip(),
            "政策拆解时间": ts,
        }

        cypher_start = """
        MATCH (p)
        WHERE id(p) = toInteger($node_id)
        SET p.`政策拆解全文` = $政策拆解全文,
            p.`政策拆解时间` = $政策拆解时间
        """
        self._run(cypher_start + " RETURN 1 AS ok", params_base, timeout=self._query_timeout)

        # 强制单值：每条政策只保留 1 条「发文级别」关系
        self._run(
            """
            MATCH (p)-[r:`发文级别`]->(:`发文级别`)
            WHERE id(p) = toInteger($node_id)
            DELETE r
            RETURN 1 AS ok
            """,
            {"node_id": nid},
            timeout=self._query_timeout,
        )

        for col, rel_type, node_label in direct:
            val = row.get(col)
            if self._blank_explain_value(val):
                continue
            rt = esc_rel(rel_type)
            lb = esc_label(node_label)
            cy = f"""
            MATCH (p)
            WHERE id(p) = toInteger($node_id)
            MERGE (v:`{lb}` {{name: $vname}})
            MERGE (p)-[:`{rt}`]->(v)
            RETURN 1 AS ok
            """
            self._run(
                cy,
                {"node_id": nid, "vname": str(val).strip()},
                timeout=self._query_timeout,
            )

    def cleanup_duplicate_data(self) -> dict:
        """
        全库去重（保守策略）：
        1) 删除重复关系（同起点/终点/类型保留一条）
        2) 每个政策节点仅保留一条「发文级别」关系（优先目标节点 name 包含“市级”）
        3) 删除同标签 + 同 name 的重复值节点（仅处理无关系孤立节点，避免误删业务链路）
        """
        rel_rows = self._run(
            """
            MATCH (a)-[r]->(b)
            WITH a, b, type(r) AS rt, collect(r) AS rs
            WHERE size(rs) > 1
            WITH rs[1..] AS drop_rels
            UNWIND drop_rels AS dr
            DELETE dr
            RETURN count(dr) AS removed
            """,
            timeout=self._query_timeout,
        )
        removed_rel_duplicates = int(rel_rows[0].get("removed") or 0) if rel_rows else 0

        level_rows = self._run(
            """
            MATCH (p)-[r:`发文级别`]->(l:`发文级别`)
            WITH p, collect({rid: id(r), name: coalesce(l.name, '')}) AS rels
            WHERE size(rels) > 1
            WITH p, rels,
                 [x IN rels WHERE x.name CONTAINS '市级'] AS city_rels
            WITH p, rels,
                 CASE WHEN size(city_rels) > 0 THEN head(city_rels).rid ELSE head(rels).rid END AS keep_rid
            UNWIND rels AS rel_item
            WITH p, keep_rid, rel_item
            WHERE rel_item.rid <> keep_rid
            MATCH (p)-[rd:`发文级别`]->(:`发文级别`)
            WHERE id(rd) = rel_item.rid
            DELETE rd
            RETURN count(rd) AS removed
            """,
            timeout=self._query_timeout,
        )
        removed_level_rels = int(level_rows[0].get("removed") or 0) if level_rows else 0

        orphan_rows = self._run(
            """
            MATCH (n)
            WHERE n.name IS NOT NULL AND trim(toString(n.name)) <> ''
            WITH labels(n) AS lbs, trim(toString(n.name)) AS name_key, collect(n) AS ns
            WHERE size(ns) > 1
            WITH ns[1..] AS candidates
            UNWIND candidates AS d
            OPTIONAL MATCH (d)-[r]-()
            WITH d, count(r) AS rc
            WHERE rc = 0
            DELETE d
            RETURN count(d) AS removed
            """,
            timeout=self._query_timeout,
        )
        removed_orphan_nodes = int(orphan_rows[0].get("removed") or 0) if orphan_rows else 0

        return {
            "ok": True,
            "removedRelationshipDuplicates": removed_rel_duplicates,
            "removedExtraPublishLevelRelations": removed_level_rels,
            "removedOrphanDuplicateNameNodes": removed_orphan_nodes,
        }

    def list_policy_content(self, keyword: str = "", page=1, page_size=20) -> dict:
        kw = (keyword or "").strip()
        p = max(1, self._safe_int(page) or 1)
        ps = max(1, min(self._safe_int(page_size) or 20, 100))
        skip = (p - 1) * ps
        label = self._safe_policy_ident((os.getenv("SEARCH_POLICY_LABEL") or os.getenv("HOME_POLICY_LABEL") or "文件名称").strip())
        title_prop = self._safe_policy_ident((os.getenv("SEARCH_FILE_PROP") or "文件名称").strip() or "文件名称")
        where_kw = ""
        params: dict = {"skip": skip, "lim": ps}
        if kw:
            where_kw = """
            AND (
              toLower(toString(coalesce(n.`文件名称`, n.`标题`, n.`name`, ''))) CONTAINS toLower($kw)
              OR toLower(toString(coalesce(n.`网址`, ''))) CONTAINS toLower($kw)
              OR toLower(toString(coalesce(n.`发文字号\\文号`, ''))) CONTAINS toLower($kw)
            )
            """
            params["kw"] = kw
        q_count = f"""
        MATCH (n:`{label}`)
        WHERE 1=1
        {where_kw}
        RETURN count(n) AS total
        """
        q_rows = f"""
        MATCH (n:`{label}`)
        WHERE 1=1
        {where_kw}
        RETURN id(n) AS id,
               trim(toString(coalesce(n.`{title_prop}`, n.`文件名称`, n.`标题`, n.`name`, ''))) AS title,
               trim(toString(coalesce(n.`网址`, ''))) AS url,
               trim(toString(coalesce(n.`发布日期`, n.`发文日期`, ''))) AS publishDate,
               trim(toString(coalesce(n.`发文字号\\文号`, n.`发文字号`, n.`文号`, ''))) AS docNo
        ORDER BY publishDate DESC, id(n) DESC
        SKIP $skip LIMIT $lim
        """
        total_rows = self._run(q_count, params, timeout=self._query_timeout)
        rows = self._run(q_rows, params, timeout=self._query_timeout)
        total = int(total_rows[0].get("total") or 0) if total_rows else 0
        items = []
        for r in rows:
            items.append(
                {
                    "id": str(r.get("id")),
                    "title": str(r.get("title") or "").strip(),
                    "url": str(r.get("url") or "").strip(),
                    "publishDate": str(r.get("publishDate") or "").strip(),
                    "docNo": str(r.get("docNo") or "").strip(),
                }
            )
        return {"items": items, "total": total, "page": p, "pageSize": ps}

    def get_policy_content_detail(self, node_id: str) -> dict:
        if self._safe_int(node_id) <= 0 and str(node_id) != "0":
            raise ValueError("nodeId 必须是数字")
        rows = self._run(
            """
            MATCH (n)
            WHERE id(n) = toInteger($node_id)
            OPTIONAL MATCH (n)-[r]-(m)
            RETURN n, collect({rid:id(r), type:type(r), dir: CASE WHEN startNode(r)=n THEN 'out' ELSE 'in' END, mid:id(m), labels:labels(m), props:properties(m)}) AS rels
            LIMIT 1
            """,
            {"node_id": node_id},
            timeout=self._query_timeout,
        )
        if not rows:
            raise ValueError("节点不存在")
        rec = rows[0]
        n = rec.get("n")
        rels_raw = rec.get("rels") or []
        rels = []
        for x in rels_raw:
            if not x or x.get("rid") is None:
                continue
            rels.append(
                {
                    "relId": str(x.get("rid")),
                    "type": str(x.get("type") or ""),
                    "direction": str(x.get("dir") or ""),
                    "neighborId": str(x.get("mid")),
                    "neighborLabels": list(x.get("labels") or []),
                    "neighborProperties": _serialize_value(x.get("props") or {}),
                }
            )
        return {
            "id": str(n.id),
            "labels": list(n.labels),
            "properties": _serialize_props(n),
            "relations": rels,
        }

    def update_policy_content_fields(self, node_id: str, updates: dict) -> dict:
        nid = self._safe_int(node_id)
        if nid <= 0 and str(node_id) != "0":
            raise ValueError("nodeId 必须是数字")
        if not isinstance(updates, dict) or not updates:
            raise ValueError("请提供要更新的字段")
        safe_updates = {}
        for k, v in updates.items():
            kk = self._safe_property_key(str(k))
            safe_updates[kk] = v
        rows = self._run(
            """
            MATCH (n)
            WHERE id(n) = toInteger($node_id)
            SET n += $updates
            RETURN id(n) AS id, properties(n) AS props
            """,
            {"node_id": nid, "updates": safe_updates},
            timeout=self._query_timeout,
        )
        if not rows:
            raise ValueError("节点不存在")
        return {"ok": True, "id": str(rows[0].get("id")), "properties": _serialize_value(rows[0].get("props") or {})}

    def delete_policy_content_field(self, node_id: str, field: str) -> dict:
        nid = self._safe_int(node_id)
        if nid <= 0 and str(node_id) != "0":
            raise ValueError("nodeId 必须是数字")
        ff = self._safe_property_key(field)
        ff_escaped = ff.replace("`", "``")
        cypher = f"""
        MATCH (n)
        WHERE id(n) = toInteger($node_id)
        REMOVE n.`{ff_escaped}`
        RETURN id(n) AS id
        """
        rows = self._run(cypher, {"node_id": nid}, timeout=self._query_timeout)
        if not rows:
            raise ValueError("节点不存在")
        return {"ok": True, "id": str(rows[0].get("id")), "field": ff}

    def delete_policy_content_relation(self, rel_id: str) -> dict:
        rid = self._safe_int(rel_id)
        if rid <= 0 and str(rel_id) != "0":
            raise ValueError("relId 必须是数字")
        rows = self._run(
            """
            MATCH ()-[r]-()
            WHERE id(r) = toInteger($rel_id)
            DELETE r
            RETURN $rel_id AS rid
            """,
            {"rel_id": rid},
            timeout=self._query_timeout,
        )
        if not rows:
            raise ValueError("关系不存在")
        return {"ok": True, "relId": str(rid)}

    def delete_policy_content_relations(self, rel_ids: list) -> dict:
        ids = []
        for raw in rel_ids or []:
            rid = self._safe_int(raw)
            if rid > 0 or str(raw) == "0":
                ids.append(rid)
        ids = list(dict.fromkeys(ids))
        if not ids:
            raise ValueError("请提供至少一个 relId")
        rows = self._run(
            """
            UNWIND $rel_ids AS rid
            OPTIONAL MATCH ()-[r]-()
            WHERE id(r) = toInteger(rid)
            WITH rid, r
            WHERE r IS NOT NULL
            DELETE r
            RETURN count(r) AS removed
            """,
            {"rel_ids": ids},
            timeout=self._query_timeout,
        )
        removed = int(rows[0].get("removed") or 0) if rows else 0
        return {"ok": True, "removed": removed, "requested": len(ids)}

    def delete_policy_content_node(self, node_id: str) -> dict:
        nid = self._safe_int(node_id)
        if nid <= 0 and str(node_id) != "0":
            raise ValueError("nodeId 必须是数字")
        rows = self._run(
            """
            MATCH (n)
            WHERE id(n) = toInteger($node_id)
            DETACH DELETE n
            RETURN $node_id AS nid
            """,
            {"node_id": nid},
            timeout=self._query_timeout,
        )
        if not rows:
            raise ValueError("节点不存在")
        return {"ok": True, "nodeId": str(nid)}

        na = row.get("国家级文件名称")
        mu = row.get("市级省级文件名称")
        di = row.get("区级县级文件名称")
        if not self._blank_explain_value(na) and not self._blank_explain_value(mu):
            self._run(
                """
                MERGE (a:`国家级文件名称` {name: $na})
                MERGE (b:`市级省级文件名称` {name: $mu})
                MERGE (b)-[:`市级省级文件名称`]->(a)
                MERGE (a)-[:`国家级文件名称`]->(b)
                RETURN 1 AS ok
                """,
                {"na": str(na).strip(), "mu": str(mu).strip()},
                timeout=self._query_timeout,
            )
        if not self._blank_explain_value(di) and not self._blank_explain_value(na):
            self._run(
                """
                MERGE (a:`国家级文件名称` {name: $na})
                MERGE (c:`区级县级文件名称` {name: $di})
                MERGE (c)-[:`区级县级文件名称`]->(a)
                RETURN 1 AS ok
                """,
                {"na": str(na).strip(), "di": str(di).strip()},
                timeout=self._query_timeout,
            )

        triples = [
            ("国家级文件名称", "国家级文件名称", "国家级文件名称"),
            ("市级省级文件名称", "市级省级文件名称", "市级省级文件名称"),
            ("区级县级文件名称", "区级县级文件名称", "区级县级文件名称"),
        ]
        for col, rel_type, node_label in triples:
            val = row.get(col)
            if self._blank_explain_value(val):
                continue
            rt = esc_rel(rel_type)
            lb = esc_label(node_label)
            cy = f"""
            MATCH (p)
            WHERE id(p) = toInteger($node_id)
            MERGE (v:`{lb}` {{name: $vname}})
            MERGE (v)-[:`{rt}`]->(p)
            RETURN 1 AS ok
            """
            self._run(
                cy,
                {"node_id": nid, "vname": str(val).strip()},
                timeout=self._query_timeout,
            )
