"""
顶栏政策搜索：关键词在「可配置的一组节点属性」上做 OR 匹配（默认：文件名称、备用标题、发文机构）。
与「目录按发文机构筛选」解耦；扩展搜索字段请改 SEARCH_MATCH_PROPS。
"""

import os
import re

from services.neo4j_service import _serialize_props


def _safe_ident(s: str) -> str:
    t = (s or "").strip()
    if not t or not re.match(r"^[\u4e00-\u9fffa-zA-Z0-9_]+$", t):
        raise ValueError(f"非法字段名: {s!r}")
    return t


class PolicySearchService:
    def __init__(self, neo_service, scope):
        """
        scope: PolicyNodeScope — 与 CatalogService 共用标签与 MATCH(n)/MATCH(n:Label)。
        """
        self._neo = neo_service
        self._scope = scope
        self._t = float(
            os.getenv("SEARCH_QUERY_TIMEOUT_SEC")
            or os.getenv("HOME_QUERY_TIMEOUT_SEC", "8")
        )
        self.file_prop = _safe_ident(os.getenv("SEARCH_FILE_PROP", "文件名称"))
        alt = os.getenv(
            "SEARCH_FILE_ALT_PROP",
            os.getenv("HOME_TITLE_PROP", "name"),
        ).strip() or "name"
        self.alt_prop = _safe_ident(alt)
        self._scope._ensure_org_prop()
        self._search_props = self._resolve_search_props()
        raw_excludes = os.getenv("SEARCH_EXCLUDE_LABELS", "政策解读,官方解读,政策解读文件")
        self._exclude_labels = []
        for part in raw_excludes.split(","):
            p = (part or "").strip()
            if not p:
                continue
            self._exclude_labels.append(_safe_ident(p))

    def _resolve_search_props(self) -> list[str]:
        """
        SEARCH_MATCH_PROPS：逗号分隔，如「文件名称,name,发文机构」。
        未设置时：文件名列 OR 备用标题 OR 发文机构（与需求「文件名或发文机构」一致，并保留 name 兼容旧库）。
        """
        raw = os.getenv("SEARCH_MATCH_PROPS", "").strip()
        if raw:
            out = []
            seen: set[str] = set()
            for part in raw.split(","):
                p = part.strip()
                if not p:
                    continue
                ident = _safe_ident(p)
                if ident not in seen:
                    seen.add(ident)
                    out.append(ident)
            if not out:
                raise ValueError("SEARCH_MATCH_PROPS 解析后为空")
            return out
        return [self.file_prop, self.alt_prop, self._scope.org_prop]

    def _build_search_where(self) -> str:
        parts = []
        for p in self._search_props:
            parts.append(
                f"toLower(toString(coalesce(n.`{p}`, ''))) CONTAINS $kwLower"
            )
        return "(" + " OR ".join(parts) + ")"

    def search(self, keyword: str, limit) -> dict:
        try:
            lim = int(limit)
        except (TypeError, ValueError):
            lim = 30
        lim = max(1, min(lim, 100))
        kw = (keyword or "").strip()
        if not kw:
            return {"items": [], "schema": self._schema()}

        kw_lower = kw.lower()
        match = self._scope.match_clause()
        where_or = self._build_search_where()
        exclude = ""
        if self._exclude_labels:
            ex = ", ".join(f"'{x}'" for x in self._exclude_labels)
            exclude = f" AND NONE(lb IN labels(n) WHERE lb IN [{ex}])"
        cypher = f"""
        {match}
        WHERE {where_or}{exclude}
        RETURN n
        LIMIT $limit
        """
        records = self._neo._run(
            cypher, {"kwLower": kw_lower, "limit": lim}, timeout=self._t
        )
        items = []
        for rec in records:
            node = rec["n"]
            props = _serialize_props(node)
            items.append(
                {
                    "id": str(node.id),
                    "labels": list(node.labels),
                    "properties": props,
                    "fileName": props.get(self.file_prop)
                    or props.get(self.alt_prop)
                    or "",
                    "organization": props.get(self._scope.org_prop) or "",
                }
            )
        return {"items": items, "schema": self._schema()}

    def _schema(self) -> dict:
        base = self._scope.public_schema()
        base["searchMatchProps"] = list(self._search_props)
        base["searchMode"] = "or_contains"
        return base
