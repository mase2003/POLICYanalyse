"""
政策目录（筛选）：与顶栏「关键词搜索」分离。
- 发文机构：默认在政策节点属性 CATALOG_ORG_PROP 上 DISTINCT；若设置 CATALOG_ORG_NODE_LABEL，
  则从该标签的节点取机构名，并按 (政策)--(机构) 关系筛选。
- 主题词：见 listMode；列表中的发文日期、责任机构或人、发文级别可为政策节点属性，或独立标签节点（MATCH (n:`发文日期`) 等），由 CATALOG_*_NODE_LABEL 与 OPTIONAL MATCH 取值

节点 MATCH 与 PolicySearchService 共用 PolicyNodeScope。
"""

import os
import re
from typing import Any

from policy_topics import POLICY_TOPIC_NAMES


def _safe_ident(s: str) -> str:
    t = (s or "").strip()
    if not t or not re.match(r"^[\u4e00-\u9fffa-zA-Z0-9_]+$", t):
        raise ValueError(f"非法字段名: {s!r}")
    return t


class CatalogService:
    def __init__(self, neo_service, scope):
        self._neo = neo_service
        self._scope = scope
        self._t = float(os.getenv("CATALOG_QUERY_TIMEOUT_SEC") or os.getenv("HOME_QUERY_TIMEOUT_SEC", "8"))

        self.prop_title = _safe_ident(os.getenv("HOME_TITLE_PROP", "name"))
        self.prop_category = os.getenv("HOME_CATEGORY_PROP", "政策类型").strip() or "政策类型"
        self.prop_date = os.getenv("HOME_DATE_PROP", "发文日期").strip() or "发文日期"

        self.prop_file = os.getenv("SEARCH_FILE_PROP", "文件名称").strip() or "文件名称"
        self.prop_responsible = os.getenv("CATALOG_RESPONSIBLE_PROP", "责任机构或人").strip() or "责任机构或人"
        self.prop_level = os.getenv("CATALOG_LEVEL_PROP", "发文级别").strip() or "发文级别"
        self.prop_topic = os.getenv("CATALOG_TOPIC_PROP", "主题词").strip() or "主题词"
        self.prop_source = os.getenv("CATALOG_SOURCE_PROP", "来源").strip() or "来源"
        self.topic_label = self._resolve_topic_label()
        self.topic_name_props = self._parse_prop_list("CATALOG_TOPIC_NAME_PROPS", "name,主题分类")

        for p in (
            self.prop_category,
            self.prop_date,
            self._scope.org_prop,
            self.prop_file,
            self.prop_responsible,
            self.prop_level,
            self.prop_topic,
            self.prop_source,
        ):
            _safe_ident(p)

        self.org_list_limit = min(2000, max(50, int(os.getenv("CATALOG_ORG_LIST_LIMIT", "500"))))
        self.page_default = 20
        self.page_max = 100
        # 列表展示用：多键名 coalesce（与筛选无关）
        self._list_date_props = self._parse_prop_list(
            "CATALOG_LIST_DATE_PROPS", self.prop_date
        )
        self._list_responsible_props = self._parse_prop_list(
            "CATALOG_LIST_RESPONSIBLE_PROPS", self.prop_responsible
        )
        # 若「发文日期」「责任机构或人」在库里是独立节点标签（MATCH (n:`发文日期`)），
        # 从 (政策)--(该标签) 取值；未单独配置 CATALOG_*_NODE_LABEL 时用属性名作标签名回退。
        self._date_node_label = self._resolve_linked_value_label(
            "CATALOG_DATE_NODE_LABEL", self.prop_date
        )
        self._date_node_name_prop = _safe_ident(
            os.getenv("CATALOG_DATE_NODE_NAME_PROP", "name")
        )
        self._date_node_name_props = self._parse_prop_list(
            "CATALOG_DATE_NODE_NAME_PROPS", f"{self._date_node_name_prop},发文日期,value,日期,title,名称"
        )
        self._resp_node_label = self._resolve_linked_value_label(
            "CATALOG_RESPONSIBLE_NODE_LABEL", self.prop_responsible
        )
        self._resp_node_name_prop = _safe_ident(
            os.getenv("CATALOG_RESPONSIBLE_NODE_NAME_PROP", "name")
        )
        self._resp_node_name_props = self._parse_prop_list(
            "CATALOG_RESPONSIBLE_NODE_NAME_PROPS", f"{self._resp_node_name_prop},责任机构或人,发布机构,发文机构,机构,单位,名称,value,title"
        )
        self._list_level_props = self._parse_prop_list(
            "CATALOG_LIST_LEVEL_PROPS", self.prop_level
        )
        self._level_node_label = self._resolve_linked_value_label(
            "CATALOG_LEVEL_NODE_LABEL", self.prop_level
        )
        self._level_node_name_prop = _safe_ident(
            os.getenv("CATALOG_LEVEL_NODE_NAME_PROP", "name")
        )
        self._level_node_name_props = self._parse_prop_list(
            "CATALOG_LEVEL_NODE_NAME_PROPS", f"{self._level_node_name_prop},发文级别,级别,等级,名称,value,title"
        )

    @staticmethod
    def _resolve_linked_value_label(env_key: str, fallback_from_prop: str) -> str | None:
        """空 / none / false / - 表示不从关联标签节点取值；未设置 env 时用属性名作为标签名（与常见建模一致）。"""
        raw = (os.getenv(env_key, "") or "").strip()
        if raw.lower() in ("none", "false", "-", "0"):
            return None
        if raw:
            return _safe_ident(raw)
        return _safe_ident(fallback_from_prop) if fallback_from_prop else None

    @staticmethod
    def _parse_prop_list(env_key: str, default_single: str) -> list[str]:
        raw = os.getenv(env_key, "").strip()
        def _split_props(text: str) -> list[str]:
            out: list[str] = []
            for part in (text or "").split(","):
                p = part.strip()
                if p:
                    out.append(_safe_ident(p))
            return out
        if raw:
            out = _split_props(raw)
            return out or [_safe_ident(default_single)]
        # 兼容默认值也为逗号分隔（例如 "name,主题分类"）
        out = _split_props(default_single)
        return out or [_safe_ident(default_single)]

    @staticmethod
    def _coalesce_n_to_string(alias: str, props: list[str]) -> str:
        if not props:
            return "''"
        if len(props) == 1:
            return f"trim(toString({alias}.`{props[0]}`))"
        inner = ", ".join(f"toString({alias}.`{p}`)" for p in props)
        return f"trim(coalesce({inner}, ''))"

    @staticmethod
    def _optional_first_neighbor_stage(
        var: str, label: str, acc: str, carry_before: list[str]
    ) -> str:
        """与政策节点相邻的「值节点」取第一个（按 id），用于 :发文日期 等独立标签建模。
        carry_before：本阶段之前已绑定、且必须在 WITH 中一路传下去的变量名（含 n 与已得到的 d_*0）。"""
        carry = ", ".join(carry_before)
        return f"""
            OPTIONAL MATCH (n)--({var}:`{label}`)
            WITH {carry}, {var}
            ORDER BY id({var}) ASC
            WITH {carry}, collect({var})[0] AS {acc}
        """

    def _linked_value_chain(self, carry_base: list[str] | None = None) -> tuple[str, dict[str, str | None]]:
        """生成 OPTIONAL MATCH 链；返回 (cypher 片段, 各列绑定的节点变量名)。"""
        parts: list[str] = []
        acc: dict[str, str | None] = {"date": None, "resp": None, "level": None}
        carry: list[str] = list(carry_base) if carry_base else ["n"]
        if self._date_node_label:
            parts.append(
                self._optional_first_neighbor_stage(
                    "d_date", self._date_node_label, "d_date0", carry
                )
            )
            acc["date"] = "d_date0"
            carry.append("d_date0")
        if self._resp_node_label:
            parts.append(
                self._optional_first_neighbor_stage(
                    "d_resp", self._resp_node_label, "d_resp0", carry
                )
            )
            acc["resp"] = "d_resp0"
            carry.append("d_resp0")
        if self._level_node_label:
            parts.append(
                self._optional_first_neighbor_stage(
                    "d_lvl", self._level_node_label, "d_lvl0", carry
                )
            )
            acc["level"] = "d_lvl0"
        return "".join(parts), acc

    def _field_expr_linked_or_props(
        self,
        acc: str | None,
        link_name_props: list[str],
        props: list[str],
    ) -> str:
        """优先从关联节点 acc.link_name_prop 展示，否则与政策节点上 props 多键名 coalesce 一致。"""
        if not props:
            return "''"
        if len(props) == 1:
            pa = props[0]
            if not acc:
                return f"trim(toString(coalesce(n.`{pa}`)))"
            link_parts = ", ".join(f"toString({acc}.`{p}`)" for p in link_name_props)
            return (
                f"trim(coalesce({link_parts}, toString(n.`{pa}`), ''))"
            )
        n_parts = ", ".join(f"toString(n.`{p}`)" for p in props)
        if not acc:
            return f"trim(coalesce({n_parts}, ''))"
        link_parts = ", ".join(f"toString({acc}.`{p}`)" for p in link_name_props)
        return (
            f"trim(coalesce({link_parts}, {n_parts}, ''))"
        )

    def _run(self, cypher: str, params: dict | None = None) -> list:
        params = params or {}
        with self._neo.driver.session() as session:
            return list(session.run(cypher, params, timeout=self._t))

    def _resolve_topic_label(self) -> str:
        raw = (os.getenv("CATALOG_TOPIC_LABEL", "主题分类") or "").strip()
        configured = _safe_ident(raw or "主题分类")
        q = "MATCH (n) UNWIND labels(n) AS lb RETURN lb, count(*) AS c ORDER BY c DESC LIMIT 300"
        try:
            rows = self._run(q, {})
        except Exception:
            return configured
        labels = [str(r.get("lb") or "").strip() for r in rows]
        if configured in labels:
            return configured
        for lb in (configured, "主题分类", "主题词", "政策主题", "政策类型"):
            if lb in labels:
                return lb
        for lb in labels:
            if "主题" in lb:
                return lb
        return configured

    def topics(self) -> list[str]:
        return list(POLICY_TOPIC_NAMES)

    def topic_children(self, topic: str | None = None) -> list[dict[str, str]]:
        """返回主题词下可选子主题；支持模糊匹配（contains）。"""
        t = (topic or "").strip()
        if not t:
            return []
        q = f"""
        MATCH (c:`{self.topic_label}`)
        WITH trim(toString(coalesce({", ".join(f"c.`{p}`" for p in self.topic_name_props)}, ''))) AS topicName
        WHERE topicName <> '' AND toLower(topicName) CONTAINS toLower($kw)
        RETURN DISTINCT topicName
        ORDER BY topicName
        LIMIT 80
        """
        rows = self._run(q, {"kw": t})
        out: list[dict[str, str]] = []
        for r in rows:
            name = str(r.get("topicName") or "").strip()
            if not name:
                continue
            out.append({"name": name})
        return out

    def _source_region_expr(self, alias: str = "n") -> str:
        """由「来源」字段（多为网址或站点名）推导省级/直辖市地区，供筛选与下拉。"""
        p = self.prop_source
        src = f"trim(toString(coalesce({alias}.`{p}`, '')))"
        low = f"toLower({src})"
        return f"""CASE
            WHEN {src} = '' THEN ''
            WHEN {low} CONTAINS 'beijing' OR {low} CONTAINS 'bj.gov' OR {src} CONTAINS '北京' OR {src} CONTAINS '首都之窗' THEN '北京'
            WHEN {low} CONTAINS 'tianjin' OR {low} CONTAINS 'tj.gov' OR {src} CONTAINS '天津' THEN '天津'
            WHEN {low} CONTAINS 'hebei' OR {src} CONTAINS '河北' THEN '河北'
            WHEN {src} CONTAINS '陕西' OR {low} CONTAINS 'shaanxi' OR {low} CONTAINS 'sn.gov.cn' THEN '陕西'
            WHEN {src} CONTAINS '山西' OR {low} CONTAINS 'shanxi.gov' THEN '山西'
            WHEN {low} CONTAINS 'nm.gov' OR {src} CONTAINS '内蒙古' THEN '内蒙古'
            WHEN {low} CONTAINS 'liaoning' OR {low} CONTAINS 'ln.gov' OR {src} CONTAINS '辽宁' THEN '辽宁'
            WHEN {low} CONTAINS 'jilin' OR {low} CONTAINS 'jl.gov' OR {src} CONTAINS '吉林' THEN '吉林'
            WHEN {low} CONTAINS 'heilongjiang' OR {low} CONTAINS 'hlj' OR {src} CONTAINS '黑龙江' THEN '黑龙江'
            WHEN {low} CONTAINS 'shanghai' OR {low} CONTAINS 'sh.gov' OR {src} CONTAINS '上海' THEN '上海'
            WHEN {low} CONTAINS 'jiangsu' OR {low} CONTAINS 'js.gov' OR {src} CONTAINS '江苏' THEN '江苏'
            WHEN {low} CONTAINS 'zhejiang' OR {low} CONTAINS 'zj.gov' OR {src} CONTAINS '浙江' THEN '浙江'
            WHEN {low} CONTAINS 'anhui' OR {low} CONTAINS 'ah.gov' OR {src} CONTAINS '安徽' THEN '安徽'
            WHEN {low} CONTAINS 'fujian' OR {low} CONTAINS 'fj.gov' OR {src} CONTAINS '福建' THEN '福建'
            WHEN {low} CONTAINS 'jiangxi' OR {low} CONTAINS 'jx.gov' OR {src} CONTAINS '江西' THEN '江西'
            WHEN {low} CONTAINS 'shandong' OR {low} CONTAINS 'sd.gov' OR {src} CONTAINS '山东' THEN '山东'
            WHEN {low} CONTAINS 'henan' OR {src} CONTAINS '河南' THEN '河南'
            WHEN {low} CONTAINS 'hubei' OR {low} CONTAINS 'hb.gov.cn' OR {src} CONTAINS '湖北' THEN '湖北'
            WHEN {low} CONTAINS 'hunan' OR {low} CONTAINS 'hn.gov' OR {src} CONTAINS '湖南' THEN '湖南'
            WHEN {low} CONTAINS 'guangdong' OR {low} CONTAINS 'gd.gov' OR {src} CONTAINS '广东' THEN '广东'
            WHEN {low} CONTAINS 'guangxi' OR {src} CONTAINS '广西' THEN '广西'
            WHEN {low} CONTAINS 'hainan' OR {src} CONTAINS '海南' THEN '海南'
            WHEN {low} CONTAINS 'chongqing' OR {low} CONTAINS 'cq.gov' OR {src} CONTAINS '重庆' THEN '重庆'
            WHEN {low} CONTAINS 'sichuan' OR {low} CONTAINS 'sc.gov' OR {src} CONTAINS '四川' THEN '四川'
            WHEN {low} CONTAINS 'guizhou' OR {src} CONTAINS '贵州' THEN '贵州'
            WHEN {low} CONTAINS 'yunnan' OR {src} CONTAINS '云南' THEN '云南'
            WHEN {src} CONTAINS '西藏' THEN '西藏'
            WHEN {low} CONTAINS 'shaanxi' OR {src} CONTAINS '陕西' THEN '陕西'
            WHEN {low} CONTAINS 'gansu' OR {src} CONTAINS '甘肃' THEN '甘肃'
            WHEN {low} CONTAINS 'qinghai' OR {src} CONTAINS '青海' THEN '青海'
            WHEN {low} CONTAINS 'ningxia' OR {src} CONTAINS '宁夏' THEN '宁夏'
            WHEN {low} CONTAINS 'xinjiang' OR {src} CONTAINS '新疆' THEN '新疆'
            ELSE '其它'
        END"""

    def regions(self) -> list[str]:
        """按「来源」推导的地区列表（发布机构筛选用）。"""
        match_clause = self._scope.match_clause()
        region_expr = self._source_region_expr("n")
        q = f"""
            {match_clause}
            WHERE {region_expr} <> ''
            RETURN DISTINCT {region_expr} AS region
            ORDER BY region
            LIMIT 80
            """
        rows = self._run(q, {})
        out: list[str] = []
        for r in rows:
            name = str(r.get("region") or "").strip()
            if name and name not in out:
                out.append(name)
        return out

    def organizations(self) -> list[str]:
        """发文机构下拉：属性模式 DISTINCT 政策节点上的机构字段；或从独立标签节点 DISTINCT 机构名。"""
        if self._scope.org_node_label:
            ol = self._scope.org_node_label
            onp = self._scope.org_node_name_prop
            org_node_props = [onp, "name", "名称", "机构", "单位", "value", "title"]
            org_expr = "trim(toString(coalesce({})))".format(
                ", ".join(f"o.`{p}`" for p in org_node_props)
            )
            q = f"""
            MATCH (o:`{ol}`)
            WHERE {org_expr} <> ''
            RETURN DISTINCT {org_expr} AS org
            ORDER BY org
            LIMIT $lim
            """
        else:
            po = self._scope.org_prop
            match = self._scope.match_clause()
            q = f"""
            {match}
            WHERE n.`{po}` IS NOT NULL AND trim(toString(n.`{po}`)) <> ''
            RETURN DISTINCT trim(toString(n.`{po}`)) AS org
            ORDER BY org
            LIMIT $lim
            """
        rows = self._run(q, {"lim": self.org_list_limit})
        out = []
        for r in rows:
            o = r.get("org")
            if o is not None and str(o).strip():
                out.append(str(o).strip())
        return out

    def _first_label_value(self, label: str | None, props: list[str]) -> str:
        if not label:
            return ""
        expr = "trim(toString(coalesce({}, '')))".format(", ".join(f"n.`{p}`" for p in props))
        q = f"""
        MATCH (n:`{label}`)
        WHERE {expr} <> ''
        RETURN {expr} AS v
        ORDER BY elementId(n) ASC
        LIMIT 1
        """
        try:
            rows = self._run(q, {})
        except Exception:
            return ""
        if not rows:
            return ""
        return str(rows[0].get("v") or "").strip()

    def _normalize_page(self, page, page_size) -> tuple[int, int]:
        try:
            p = int(page)
        except (TypeError, ValueError):
            p = 1
        try:
            ps = int(page_size)
        except (TypeError, ValueError):
            ps = self.page_default
        p = max(1, p)
        ps = max(1, min(ps, self.page_max))
        return p, ps

    def policies(
        self,
        list_mode: str,
        organization: str | None,
        category: str | None,
        topic_child: str | None,
        page,
        page_size,
        source_region: str | None = None,
    ) -> dict[str, Any]:
        mode = (list_mode or "organization").strip().lower()
        if mode not in ("organization", "topic"):
            raise ValueError("listMode 须为 organization 或 topic")

        org = (organization or "").strip() or None
        cat = (category or "").strip() or None
        child = (topic_child or "").strip() or None
        if cat is not None and cat not in POLICY_TOPIC_NAMES:
            raise ValueError("无效的主题词")

        if mode == "organization":
            cat = None
        else:
            org = None

        region_filter = (source_region or "").strip() or None
        if mode != "organization":
            region_filter = None

        p, ps = self._normalize_page(page, page_size)
        skip = (p - 1) * ps

        pt = self.prop_title
        po = self._scope.org_prop
        org_lb = self._scope.org_node_label
        onp = self._scope.org_node_name_prop
        lb = self._scope.label
        pc = self.prop_category
        pf = self.prop_file
        ptopic = self.prop_topic

        chain, acc_map = self._linked_value_chain(["n", "t0"])
        date_expr = self._field_expr_linked_or_props(
            acc_map.get("date"), self._date_node_name_props, self._list_date_props
        )
        resp_expr = self._field_expr_linked_or_props(
            acc_map.get("resp"), self._resp_node_name_props, self._list_responsible_props
        )
        level_expr = self._field_expr_linked_or_props(
            acc_map.get("level"), self._level_node_name_props, self._list_level_props
        )

        topic_expr_n = f"trim(toString(coalesce({', '.join(f'n.`{p}`' for p in self.topic_name_props)}, n.`{ptopic}`, n.`{pc}`, '')))"
        topic_expr_t_match = f"trim(toString(coalesce({', '.join(f't.`{p}`' for p in self.topic_name_props)}, '')))"
        topic_expr_t_row = f"trim(toString(coalesce({', '.join(f't0.`{p}`' for p in self.topic_name_props)}, '')))"
        topic_match = (
            "($cat IS NULL OR ("
            f"toLower({topic_expr_n}) CONTAINS toLower($cat)"
            f" OR toLower({topic_expr_t_match}) CONTAINS toLower($cat)"
            "))"
        )
        child_match = "($child IS NULL OR toLower({expr}) CONTAINS toLower($child))".format(
            expr=topic_expr_t_match
        )
        rest_where = f"\n          AND {topic_match}\n          AND {child_match}\n        "

        region_expr = self._source_region_expr("n")
        region_clause = f"\n            AND ($sourceRegion IS NULL OR ({region_expr}) = $sourceRegion)"

        if org_lb and org:
            match_n = f"MATCH (n:`{lb}`)--(o:`{org_lb}`)"
            org_where = f"trim(toString(o.`{onp}`)) = $org"
            count_ret = "RETURN count(DISTINCT n) AS total"
            # Neo4j 5：WHERE 紧跟 OPTIONAL MATCH 时只绑定可选模式，o/n 与 t 与后续 WITH 作用域易错乱。
            # 必须先 WITH 显式带出 n（及 o），再写 WHERE，再 collect(t)。
            carry_after_optional = "n, o, t"
        elif org_lb:
            match_n = self._scope.match_clause()
            org_where = "true"
            count_ret = "RETURN count(n) AS total"
            carry_after_optional = "n, t"
        else:
            match_n = self._scope.match_clause()
            org_where = f"($org IS NULL OR trim(toString(coalesce(n.`{po}`, ''))) = $org)"
            count_ret = "RETURN count(n) AS total"
            carry_after_optional = "n, t"

        q_count = f"""
            {match_n}
            OPTIONAL MATCH (n)--(t:`{self.topic_label}`)
            WITH {carry_after_optional}
            WHERE {org_where}
            {region_clause}{rest_where}
            {count_ret}
            """
        q_rows = f"""
            {match_n}
            OPTIONAL MATCH (n)--(t:`{self.topic_label}`)
            WITH {carry_after_optional}
            WHERE {org_where}
            {region_clause}{rest_where}
            WITH n, collect(t)[0] AS t0
            {chain}RETURN id(n) AS id,
                   trim(toString(coalesce(n.`{pf}`, n.`{pt}`, ''))) AS fileName,
                   {date_expr} AS publishDate,
                   {resp_expr} AS responsible,
                   {level_expr} AS publishLevel,
                   trim(toString(coalesce({topic_expr_t_row}, n.`{ptopic}`, n.`{pc}`, ''))) AS topicKeyword
            ORDER BY publishDate DESC, id(n) DESC
            SKIP $skip LIMIT $lim
            """
        bind = {
            "org": org,
            "cat": cat,
            "child": child,
            "sourceRegion": region_filter,
            "skip": skip,
            "lim": ps,
        }
        total_rows = self._run(q_count, bind)
        total = int(total_rows[0]["total"]) if total_rows else 0
        rows = self._run(q_rows, bind)
        fallback_resp = self._first_label_value(self._resp_node_label, self._resp_node_name_props)
        fallback_lvl = self._first_label_value(self._level_node_label, self._level_node_name_props)

        items = []
        for r in rows:
            tid = r.get("id")
            fn = r.get("fileName")
            items.append(
                {
                    "id": str(tid) if tid is not None else "",
                    "fileName": (str(fn).strip() if fn is not None else "") or f"节点 {tid}",
                    "publishDate": str(r.get("publishDate") or ""),
                    "responsible": str(r.get("responsible") or "") or fallback_resp,
                    "publishLevel": str(r.get("publishLevel") or "") or fallback_lvl,
                    "topicKeyword": str(r.get("topicKeyword") or ""),
                }
            )

        sch = self._scope.public_schema()
        sch.update(
            {
                "catalogMode": "filter_only",
                "categoryProp": self.prop_category,
                "titleProp": self.prop_title,
                "dateProp": self.prop_date,
                "listDateProps": self._list_date_props,
                "dateValueNodeLabel": self._date_node_label,
                "dateValueNodeNameProp": self._date_node_name_prop,
                "fileProp": self.prop_file,
                "responsibleProp": self.prop_responsible,
                "listResponsibleProps": self._list_responsible_props,
                "responsibleValueNodeLabel": self._resp_node_label,
                "responsibleValueNodeNameProp": self._resp_node_name_prop,
                "levelProp": self.prop_level,
                "listLevelProps": self._list_level_props,
                "levelValueNodeLabel": self._level_node_label,
                "levelValueNodeNameProp": self._level_node_name_prop,
                "topicProp": self.prop_topic,
                "sourceProp": self.prop_source,
            }
        )

        return {
            "items": items,
            "total": total,
            "page": p,
            "pageSize": ps,
            "listMode": mode,
            "schema": sch,
        }
