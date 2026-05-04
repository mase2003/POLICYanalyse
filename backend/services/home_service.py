"""
首页数据：假设图中政策节点使用统一主标签 + 若干属性（可通过环境变量改，便于换库不换代码）。
查询保持「少跳、少字段、带 LIMIT」，优先降低执行时间。
"""

import os
import re
from pathlib import Path
from typing import Any

from deployment_root import get_deployment_root
from runtime_paths import data_path
from policy_topics import POLICY_TOPIC_NAMES

def _safe_ident(s: str) -> str:
    """仅允许中文/字母/数字/下划线，防 Cypher 注入。"""
    t = (s or "").strip()
    if not t or not re.match(r"^[\u4e00-\u9fffa-zA-Z0-9_]+$", t):
        raise ValueError(f"非法字段名: {s!r}")
    return t


class HomeService:
    def __init__(self, neo_service):
        self._neo = neo_service
        self._t_home = float(os.getenv("HOME_QUERY_TIMEOUT_SEC", "8"))
        self._project_root = get_deployment_root()
        self._photo_dir = data_path("STATIC_PHOTO_DIR", "static", "photo")

        self.label = _safe_ident(os.getenv("HOME_POLICY_LABEL", "文件名称"))
        self.prop_title = _safe_ident(os.getenv("HOME_TITLE_PROP", "name"))
        self.prop_category = os.getenv("HOME_CATEGORY_PROP", "政策类型").strip() or "政策类型"
        self.prop_search = _safe_ident(os.getenv("HOME_SEARCH_PROP", "searchCount"))
        # 日期字段名可能含中文，单独校验
        self.prop_date = os.getenv("HOME_DATE_PROP", "发文日期").strip() or "发文日期"
        _safe_ident(self.prop_category)
        _safe_ident(self.prop_date)

        self.pie_limit = min(20, max(3, int(os.getenv("HOME_PIE_SEGMENTS", "10"))))
        self.list_limit = min(30, max(1, int(os.getenv("HOME_LIST_LIMIT", "10"))))
        self.topic_label = self._resolve_topic_label()
        raw_ex = (os.getenv("HOME_EXCLUDE_LABELS", "政策解读文件,政策解读,官方解读,解读文件") or "").strip()
        self._exclude_labels = [x.strip() for x in raw_ex.split(",") if x.strip()]
        self.topic_name_props = []
        # 饼图/主题分类取值优先用节点属性「主题分类」（与库中 :主题分类 标签一致）
        raw_topic_props = (os.getenv("HOME_TOPIC_NAME_PROPS", "主题分类,name") or "").strip()
        for p in [x.strip() for x in raw_topic_props.split(",") if x.strip()]:
            self.topic_name_props.append(_safe_ident(p))
        if not self.topic_name_props:
            self.topic_name_props = ["name"]

    def _run(self, cypher: str, params: dict | None = None) -> list:
        params = params or {}
        with self._neo.driver.session() as session:
            return list(session.run(cypher, params, timeout=self._t_home))

    def _resolve_topic_label(self) -> str:
        configured = _safe_ident((os.getenv("HOME_TOPIC_LABEL", "主题分类") or "").strip() or "主题分类")
        q = "MATCH (n) UNWIND labels(n) AS lb RETURN lb, count(*) AS c ORDER BY c DESC LIMIT 300"
        try:
            rows = self._run(q, {})
        except Exception:
            return configured
        labels = [str(r.get("lb") or "").strip() for r in rows]
        if configured in labels:
            return configured
        for lb in ["主题分类", "主题词", "政策主题", "政策类型"]:
            if lb in labels:
                return _safe_ident(lb)
        for lb in labels:
            if "主题" in lb:
                return _safe_ident(lb)
        return configured

    def _title_cell(self, row: dict, key: str = "title") -> str:
        v = row.get(key)
        if isinstance(v, str) and v.strip():
            return v
        return f"节点 {row.get('id')}"

    def pie_series(self) -> list[dict[str, Any]]:
        """
        已收录政策类型：仅统计与「主题分类」节点存在关联且主题字段非空的政策数量；
        与政策目录主题词（POLICY_TOPIC_NAMES）对齐后汇总；未命名类计入「其他」再排除饼图扇区。
        """
        lb = self.label
        topic_proj_t0 = ", ".join(f"t0.`{p}`" for p in self.topic_name_props)
        coalesce_t = "coalesce(" + ", ".join(f"t.`{p}`" for p in self.topic_name_props) + ", '')"
        nonempty = f"trim(toString({coalesce_t})) <> ''"
        ex_where = ""
        params: dict = {}
        if self._exclude_labels:
            params["exLabels"] = self._exclude_labels
            ex_where = "WHERE NONE(lb0 IN labels(n) WHERE lb0 IN $exLabels)\n        "
        q = f"""
        MATCH (n:`{lb}`)
        {ex_where}MATCH (n)--(t:`{self.topic_label}`)
        WHERE {nonempty}
        WITH n, t
        ORDER BY id(t) ASC
        WITH n, collect(t)[0] AS t0
        WITH trim(toString(coalesce({topic_proj_t0}, ''))) AS name, count(DISTINCT n) AS v
        WHERE name <> ''
        RETURN name, v AS value
        """
        rows = self._run(q, params)
        raw: dict[str, int] = {}
        for r in rows:
            name = r.get("name")
            val = r.get("value")
            if name is not None and val is not None:
                k = str(name).strip() or "未分类"
                if k in ("其它", "其它类"):
                    k = "其他"
                raw[k] = raw.get(k, 0) + int(val)

        fixed = list(POLICY_TOPIC_NAMES)
        fixed_set = set(fixed)
        out: list[dict[str, Any]] = []
        agg: dict[str, int] = {k: 0 for k in fixed}
        rest = 0
        for k, v in raw.items():
            matched = None
            for topic_name in fixed:
                if k == topic_name or k.startswith(f"{topic_name}/") or f"{topic_name}/" in k:
                    matched = topic_name
                    break
            if matched:
                agg[matched] += int(v)
            else:
                rest += int(v)
        for t in fixed:
            out.append({"name": t, "value": int(agg.get(t, 0))})
        # 未归入固定分类的计数并入「其他」，并保证「其他」在序列为固定项时一定可见（含 0 与累加 rest）
        if "其他" in fixed_set:
            extra_other = rest + int(agg.get("其他", 0))
            for i, seg in enumerate(out):
                if seg["name"] == "其他":
                    out[i] = {"name": "其他", "value": extra_other}
                    break
        elif rest > 0:
            out.append({"name": "其他", "value": rest})
        # 饼图扇区不包含「其他」：占比仅在其余与政策目录主题词一致的分类间计算
        return [seg for seg in out if str(seg.get("name") or "").strip() != "其他"]

    def hot_policies(self) -> list[dict[str, Any]]:
        """热门检索：按 searchCount 降序，次级按 id 稳定排序。"""
        lb = self.label
        ps = self.prop_search
        pt = self.prop_title
        ex_where = ""
        params: dict = {"lim": self.list_limit}
        if self._exclude_labels:
            params["exLabels"] = self._exclude_labels
            ex_where = "WHERE NONE(lb0 IN labels(n) WHERE lb0 IN $exLabels)\n        "
        q = f"""
        MATCH (n:`{lb}`)
        {ex_where}RETURN id(n) AS id,
               n.`{pt}` AS title,
               coalesce(n.`{ps}`, 0) AS searchCount
        ORDER BY coalesce(n.`{ps}`, 0) DESC, id(n) DESC
        LIMIT $lim
        """
        rows = self._run(q, params)
        return [
            {
                "id": str(r["id"]),
                "title": self._title_cell(r),
                "searchCount": int(r.get("searchCount") or 0),
            }
            for r in rows
        ]

    def latest_policies(self) -> list[dict[str, Any]]:
        """最新政策：要求日期属性存在；按字符串降序（ISO yyyy-MM-dd 可直接比）。"""
        lb = self.label
        pd = self.prop_date
        pt = self.prop_title
        ex_pred = "true"
        params: dict = {"lim": self.list_limit}
        if self._exclude_labels:
            params["exLabels"] = self._exclude_labels
            ex_pred = "NONE(lb0 IN labels(n) WHERE lb0 IN $exLabels)"
        q = f"""
        MATCH (n:`{lb}`)
        WHERE n.`{pd}` IS NOT NULL AND {ex_pred}
        RETURN id(n) AS id,
               n.`{pt}` AS title,
               toString(n.`{pd}`) AS publishDate
        ORDER BY publishDate DESC
        LIMIT $lim
        """
        rows = self._run(q, params)
        return [
            {
                "id": str(r["id"]),
                "title": self._title_cell(r),
                "publishDate": str(r.get("publishDate") or ""),
            }
            for r in rows
        ]

    def carousel(self) -> list[dict[str, Any]]:
        if not self._photo_dir.exists():
            return []
        exts = {".png", ".jpg", ".jpeg", ".webp", ".gif"}
        files = sorted(
            [p for p in self._photo_dir.iterdir() if p.is_file() and p.suffix.lower() in exts],
            key=lambda p: p.name.lower(),
        )
        return [
            {
                "title": f.stem,
                "imageUrl": f"/api/home/carousel-image/{f.name}",
            }
            for f in files
        ]

    def dashboard(self) -> dict[str, Any]:
        """单次请求聚齐首页块，减少 HTTP 往返。"""
        pie = self.pie_series()
        hot = self.hot_policies()
        latest = self.latest_policies()
        carousel = self.carousel()
        return {
            "carousel": carousel,
            "pie": pie,
            "pieTopicOrder": list(POLICY_TOPIC_NAMES),
            "hot": hot,
            "latest": latest,
            "schema": {
                "policyLabel": self.label,
                "categoryProp": self.prop_category,
                "titleProp": self.prop_title,
                "searchProp": self.prop_search,
                "dateProp": self.prop_date,
            },
        }

    def increment_search(self, node_id: str) -> dict[str, Any]:
        """用户检索/扩展节点时调用，累加 searchCount（不限制标签，与图谱搜索 id 一致）。"""
        if not re.fullmatch(r"\d+", (node_id or "").strip()):
            raise ValueError("nodeId 须为数字 id")
        nid = int(node_id)
        ps = self.prop_search
        q = f"""
        MATCH (n) WHERE id(n) = $nid
        SET n.`{ps}` = coalesce(n.`{ps}`, 0) + 1
        RETURN id(n) AS id, n.`{ps}` AS searchCount
        """
        rows = self._run(q, {"nid": nid})
        if not rows:
            raise ValueError("节点不存在或标签不匹配")
        r = rows[0]
        return {"id": str(r["id"]), "searchCount": int(r.get("searchCount") or 0)}
