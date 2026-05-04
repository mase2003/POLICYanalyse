"""
政策节点在 Neo4j 中的统一范围：节点标签、MATCH(n:Label) 与 MATCH(n) 回退。
目录「发文机构」字段：若 .env 中的属性在库里不存在或无数据，会按 CATALOG_ORG_CANDIDATES 自动尝试常见别名。
"""

import os
import re


def _safe_ident(s: str) -> str:
    t = (s or "").strip()
    if not t or not re.match(r"^[\u4e00-\u9fffa-zA-Z0-9_]+$", t):
        raise ValueError(f"非法字段名: {s!r}")
    return t


class PolicyNodeScope:
    """
    - label：政策类节点标签（与 Neo4j Browser 中一致）
    - org_prop：政策节点上的「机构」属性键（CATALOG_ORG_PROP），与 org_node_label 二选一
    - org_node_label：若库中机构是独立节点标签（如 :发文机构），则下拉从该类节点取 DISTINCT，筛选走 (政策)--(机构)
    """

    def __init__(self, neo_service):
        self._neo = neo_service
        self._t = float(os.getenv("HOME_QUERY_TIMEOUT_SEC", "8"))
        raw = (
            os.getenv("SEARCH_POLICY_LABEL")
            or os.getenv("HOME_POLICY_LABEL", "文件名称")
            or "文件名称"
        )
        self.label = _safe_ident(raw.strip())
        _org_node_raw = (os.getenv("CATALOG_ORG_NODE_LABEL", "") or "").strip().strip("\ufeff")
        self.org_node_label = _safe_ident(_org_node_raw) if _org_node_raw else None
        self.org_node_name_prop = _safe_ident(
            os.getenv("CATALOG_ORG_NODE_NAME_PROP", "name")
        )
        _org_raw = (
            os.getenv("CATALOG_ORG_PROP")
            or os.getenv("SEARCH_ORG_PROP")
            or "发文机构"
        )
        _org_raw = (_org_raw or "").strip().strip("\ufeff").strip()
        self._org_prop_configured = _safe_ident(_org_raw)
        self.org_prop = self._org_prop_configured
        self._org_prop_resolved = False
        self._org_prop_guessed = False
        self._match_unlabeled: bool | None = None

    def _run(self, cypher: str, params: dict | None = None) -> list:
        return self._neo._run(cypher, params or {}, timeout=self._t)

    def _count_nodes_with_org_prop(self, prop: str) -> int:
        """全库带该属性且非空的节点数（用于自动选字段名）。"""
        try:
            r = self._run(
                f"MATCH (n) WHERE n.`{prop}` IS NOT NULL AND trim(toString(n.`{prop}`)) <> '' RETURN count(n) AS c"
            )
            return int(r[0]["c"]) if r else 0
        except Exception:
            return 0

    def _ensure_org_prop(self) -> None:
        """
        若配置的 CATALOG_ORG_PROP 在库中无数据，按 CATALOG_ORG_CANDIDATES 依次尝试，
        避免 Neo4j 里实际字段叫「发文机关」等时下拉为空。
        若已配置 CATALOG_ORG_NODE_LABEL（机构为独立标签节点），则不解析政策节点上的机构属性。
        """
        if self._org_prop_resolved:
            return
        if self.org_node_label:
            guessed_name_prop = self._guess_node_name_prop(self.org_node_label)
            if guessed_name_prop:
                self.org_node_name_prop = guessed_name_prop
            self._org_prop_resolved = True
            return
        configured = self._org_prop_configured
        raw = os.getenv(
            "CATALOG_ORG_CANDIDATES",
            "发文机构,发文机关,发布机构,发布单位,主办单位,责任机构,来文单位,"
            "organization,organizationName,issuer,issuerOrg,issueOrg,publishOrg,publishUnit,orgName",
        )
        candidates: list[str] = []
        for item in [configured] + raw.split(","):
            p = (item or "").strip()
            if not p:
                continue
            try:
                ident = _safe_ident(p)
            except ValueError:
                continue
            if ident not in candidates:
                candidates.append(ident)

        for pk in candidates:
            if self._count_nodes_with_org_prop(pk) > 0:
                if self.org_prop != pk:
                    self.org_prop = pk
                    self._match_unlabeled = None
                self._org_prop_guessed = False
                self._org_prop_resolved = True
                return

        guessed = self._guess_org_prop_from_sample_nodes()
        if guessed:
            self.org_prop = guessed
            self._match_unlabeled = None
            self._org_prop_guessed = True
            self._org_prop_resolved = True
            return

        # 若政策节点上确实没有机构属性，自动尝试“机构独立节点标签”模式
        linked = self._guess_org_node_label()
        if linked:
            self.org_node_label = linked
            self.org_node_name_prop = self._guess_node_name_prop(linked) or self.org_node_name_prop
            self._org_prop_resolved = True
            return

        self.org_prop = configured
        self._org_prop_guessed = False
        self._org_prop_resolved = True

    def _guess_org_node_label(self) -> str | None:
        lb = self.label
        candidates = ["发文机构", "发布机构", "责任机构或人", "机构", "单位"]
        for c in candidates:
            try:
                r = self._run(f"MATCH (n:`{lb}`)--(o:`{c}`) RETURN count(DISTINCT n) AS c")
                if r and int(r[0].get("c") or 0) > 0:
                    return c
            except Exception:
                continue
        return None

    def _guess_node_name_prop(self, node_label: str) -> str | None:
        cand = ["name", "名称", "机构", "单位", "value", "title"]
        for p in cand:
            try:
                r = self._run(
                    f"MATCH (o:`{node_label}`) WHERE o.`{p}` IS NOT NULL AND trim(toString(o.`{p}`)) <> '' RETURN count(o) AS c"
                )
                if r and int(r[0].get("c") or 0) > 0:
                    return p
            except Exception:
                continue
        return None

    def _guess_org_prop_from_sample_nodes(self) -> str | None:
        """当候选名在库里都不存在时，从带政策标签的节点 keys 里猜机构类字段。"""
        lb = self.label
        try:
            rows = self._run(f"MATCH (n:`{lb}`) RETURN keys(n) AS ks LIMIT 80")
        except Exception:
            return None
        deny = {
            "name",
            "searchCount",
            "id",
            "policyType",
            "政策类型",
            "发文日期",
            "文件名称",
            "主题词",
            "title",
            "content",
            "正文",
            "url",
        }
        scored: list[tuple[int, str]] = []
        all_keys: list[str] = []
        for r in rows:
            for k in r.get("ks") or []:
                if not isinstance(k, str):
                    continue
                if k not in all_keys:
                    all_keys.append(k)
                kl = k.lower()
                score = 0
                if "机构" in k:
                    score += 12
                if "单位" in k or "部门" in k:
                    score += 10
                if "org" in kl:
                    score += 5
                for sub in ("issuer", "publish", "unit", "department", "office", "bureau"):
                    if sub in kl:
                        score += 2
                if score > 0:
                    scored.append((score, k))
        scored.sort(key=lambda x: (-x[0], x[1]))
        seen: set[str] = set()
        for _, k in scored:
            if k in seen:
                continue
            seen.add(k)
            try:
                pk = _safe_ident(k)
            except ValueError:
                continue
            if self._count_nodes_with_org_prop(pk) > 0:
                return pk
        # 第二遍：任意非排除键，首个在库中有非空值的作为机构字段（便于字段名完全自定义）
        for k in sorted(all_keys):
            if k in deny:
                continue
            try:
                pk = _safe_ident(k)
            except ValueError:
                continue
            if self._count_nodes_with_org_prop(pk) > 0:
                return pk
        return None

    def _ensure_match_mode(self) -> None:
        self._ensure_org_prop()
        if self._match_unlabeled is not None:
            return
        if os.getenv("CATALOG_FORCE_UNLABELED_MATCH", "").lower() in ("1", "true", "yes"):
            self._match_unlabeled = True
            return
        lb = self.label
        if self.org_node_label:
            r = self._run(f"MATCH (n:`{lb}`) RETURN count(n) AS c")
            n_pol = int(r[0]["c"]) if r else 0
            if n_pol > 0:
                self._match_unlabeled = False
                return
            r2 = self._run(
                "MATCH (n) WHERE $label IN labels(n) RETURN count(n) AS c LIMIT 1",
                {"label": lb},
            )
            n2 = int(r2[0]["c"]) if r2 else 0
            self._match_unlabeled = n2 > 0
            return
        po = self.org_prop
        r = self._run(
            f"MATCH (n:`{lb}`) WHERE n.`{po}` IS NOT NULL AND trim(toString(n.`{po}`)) <> '' RETURN count(n) AS c"
        )
        n_labeled_with_org = int(r[0]["c"]) if r else 0
        if n_labeled_with_org > 0:
            self._match_unlabeled = False
            return
        r2 = self._run(
            f"MATCH (n) WHERE n.`{po}` IS NOT NULL AND trim(toString(n.`{po}`)) <> '' RETURN count(n) AS c LIMIT 1"
        )
        n2 = int(r2[0]["c"]) if r2 else 0
        self._match_unlabeled = n2 > 0

    def match_clause(self) -> str:
        """与目录、搜索共用同一套 MATCH，避免一处能查、一处为空。"""
        self._ensure_match_mode()
        if self._match_unlabeled:
            return "MATCH (n)"
        return f"MATCH (n:`{self.label}`)"

    @property
    def match_unlabeled(self) -> bool | None:
        return self._match_unlabeled

    def sample_policy_node_keys(self) -> list[str]:
        """政策标签节点上出现过的一批属性名，便于在 .env 填写 CATALOG_ORG_PROP。"""
        lb = self.label
        try:
            rows = self._run(f"MATCH (n:`{lb}`) RETURN keys(n) AS ks LIMIT 15")
        except Exception:
            return []
        out: list[str] = []
        for r in rows:
            for k in r.get("ks") or []:
                if isinstance(k, str) and k not in out:
                    out.append(k)
        return out[:50]

    def diagnostics(self) -> dict:
        lb = self.label
        r0 = self._run(f"MATCH (n:`{lb}`) RETURN count(n) AS c")
        if self.org_node_label:
            ol = self.org_node_label
            onp = self.org_node_name_prop
            r_ol = self._run(
                f"MATCH (o:`{ol}`) WHERE o.`{onp}` IS NOT NULL AND trim(toString(o.`{onp}`)) <> '' RETURN count(o) AS c"
            )
            r_join = self._run(
                f"MATCH (n:`{lb}`)--(o:`{ol}`) RETURN count(DISTINCT n) AS c"
            )
            return {
                "nodesWithPolicyLabel": int(r0[0]["c"]) if r0 else 0,
                "catalogOrgMode": "related_org_node",
                "orgNodesWithNameFilled": int(r_ol[0]["c"]) if r_ol else 0,
                "policyNodesLinkedToAnyOrg": int(r_join[0]["c"]) if r_join else 0,
            }
        po = self.org_prop
        r1 = self._run(
            f"MATCH (n:`{lb}`) WHERE n.`{po}` IS NOT NULL AND trim(toString(n.`{po}`)) <> '' RETURN count(n) AS c"
        )
        r2 = self._run(
            f"MATCH (n) WHERE n.`{po}` IS NOT NULL AND trim(toString(n.`{po}`)) <> '' RETURN count(n) AS c"
        )
        return {
            "nodesWithPolicyLabel": int(r0[0]["c"]) if r0 else 0,
            "catalogOrgMode": "property_on_policy",
            "labeledNodesWithOrgFilled": int(r1[0]["c"]) if r1 else 0,
            "allNodesWithOrgFilled": int(r2[0]["c"]) if r2 else 0,
        }

    def public_schema(self) -> dict:
        self._ensure_match_mode()
        out = {
            "policyLabel": self.label,
            "catalogOrgProp": self.org_prop,
            "catalogOrgPropConfigured": self._org_prop_configured,
            "catalogOrgNodeLabel": self.org_node_label,
            "catalogOrgNodeNameProp": self.org_node_name_prop,
            "orgPropAutoResolved": self.org_prop != self._org_prop_configured,
            "orgPropGuessedFromKeys": self._org_prop_guessed,
            "matchUnlabeled": self._match_unlabeled is True,
        }
        out.update(self.diagnostics())
        return out
