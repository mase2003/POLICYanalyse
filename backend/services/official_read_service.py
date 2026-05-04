import os
import re
from collections import Counter
from typing import Any

import jieba.analyse
import jieba.posseg as pseg

from runtime_paths import data_path


def _safe_ident(s: str) -> str:
    t = (s or "").strip()
    if not t or not re.match(r"^[\u4e00-\u9fffa-zA-Z0-9_]+$", t):
        raise ValueError(f"非法字段名: {s!r}")
    return t


class OfficialReadService:
    def __init__(self, neo_service):
        self._neo = neo_service
        self._t = float(os.getenv("OFFICIAL_READ_QUERY_TIMEOUT_SEC", os.getenv("HOME_QUERY_TIMEOUT_SEC", "8")))
        self.label = self._resolve_label()
        self._label_props = self._collect_label_props(self.label)
        self.title_prop = self._resolve_prop(
            "OFFICIAL_READ_TITLE_PROP", ["name", "标题", "文件标题", "政策解读文件标题", "title"]
        )
        self.org_prop = self._resolve_prop(
            "OFFICIAL_READ_ORG_PROP", ["发布机构", "责任机构或人", "发文机构", "机构", "organization"]
        )
        self.date_prop = self._resolve_prop(
            "OFFICIAL_READ_DATE_PROP", ["发布日期", "发文日期", "日期", "publishDate", "date"]
        )
        self.content_prop = self._resolve_prop(
            "OFFICIAL_READ_CONTENT_PROP", ["content", "正文", "内容", "全文", "text"]
        )
        self.title_props = self._resolve_prop_list(
            "OFFICIAL_READ_TITLE_PROPS", [self.title_prop, "name", "标题", "文件标题", "政策解读文件标题", "title"]
        )
        self.org_props = self._resolve_prop_list(
            "OFFICIAL_READ_ORG_PROPS", [self.org_prop, "发布机构", "责任机构或人", "发文机构", "机构", "organization"]
        )
        self.date_props = self._resolve_prop_list(
            "OFFICIAL_READ_DATE_PROPS", [self.date_prop, "发布日期", "发文日期", "日期", "publishDate", "date"]
        )
        self.content_props = self._resolve_prop_list(
            "OFFICIAL_READ_CONTENT_PROPS", [self.content_prop, "content", "正文", "内容", "全文", "text"]
        )
        self.org_label = self._resolve_related_label("OFFICIAL_READ_ORG_LABEL", [self.org_prop, "发文机构", "发布机构", "责任机构或人"])
        self.date_label = self._resolve_related_label("OFFICIAL_READ_DATE_LABEL", [self.date_prop, "发布日期", "发文日期", "日期"])
        self.content_label = self._resolve_related_label("OFFICIAL_READ_CONTENT_LABEL", [self.content_prop, "政策解读正文", "正文", "内容", "全文"])
        self.link_value_props = self._resolve_prop_list(
            "OFFICIAL_READ_LINK_VALUE_PROPS",
            ["name", "名称", "value", "title", "text", "content", "正文", "内容", "全文", "发布机构", "发文机构", "机构", "发布日期", "发文日期"],
        )
        self.max_limit = 100
        self._prepositions = self._load_prepositions()
        self._attributive_flags = ("a", "ad", "ag", "an", "b", "z")
        self._noun_flags = ("n",)

    @staticmethod
    def _load_prepositions() -> set[str]:
        stopword_file = data_path("STOPWORDS_PATH", "介词库.txt")
        words: set[str] = set()
        if stopword_file.exists():
            text = stopword_file.read_text(encoding="utf-8", errors="ignore")
            for token in re.findall(r"[\u4e00-\u9fffA-Za-z]+", text):
                t = token.strip().lower()
                if t:
                    words.add(t)
        words.update({"以及", "或者", "一个", "一种", "相关", "进行"})
        return words

    def _run(self, cypher: str, params: dict | None = None) -> list:
        with self._neo.driver.session() as session:
            return list(session.run(cypher, params or {}, timeout=self._t))

    def _label_counts(self) -> list[str]:
        q = "MATCH (n) UNWIND labels(n) AS lb RETURN lb, count(*) AS c ORDER BY c DESC LIMIT 300"
        try:
            rows = self._run(q, {})
        except Exception:
            return []
        return [str(r.get("lb") or "").strip() for r in rows]

    def _resolve_label(self) -> str:
        configured = _safe_ident((os.getenv("OFFICIAL_READ_LABEL", "政策解读文件") or "").strip() or "政策解读文件")
        labels = self._label_counts()
        if configured in labels:
            return configured
        for lb in ["政策解读文件名称", "政策解读文件", "政策解读", "官方解读", "解读文件"]:
            if lb in labels:
                return lb
        for lb in labels:
            if "解读" in lb:
                return _safe_ident(lb)
        return configured

    def _collect_label_props(self, label: str) -> set[str]:
        q = f"MATCH (n:`{label}`) RETURN keys(n) AS ks LIMIT 80"
        try:
            rows = self._run(q, {})
        except Exception:
            return set()
        props: set[str] = set()
        for row in rows:
            for key in row.get("ks") or []:
                if isinstance(key, str) and key.strip():
                    props.add(key.strip())
        return props

    def _resolve_prop(self, env_key: str, candidates: list[str]) -> str:
        raw = (os.getenv(env_key, "") or "").strip()
        if raw:
            return _safe_ident(raw)
        for p in candidates:
            ident = _safe_ident(p)
            if ident in self._label_props:
                return ident
        return _safe_ident(candidates[0])

    def _resolve_prop_list(self, env_key: str, candidates: list[str]) -> list[str]:
        raw = (os.getenv(env_key, "") or "").strip()
        out: list[str] = []
        vals = [x.strip() for x in raw.split(",") if x.strip()] if raw else candidates
        seen: set[str] = set()
        for p in vals:
            ident = _safe_ident(p)
            if ident not in seen:
                seen.add(ident)
                out.append(ident)
        return out

    def _resolve_related_label(self, env_key: str, candidates: list[str]) -> str | None:
        raw = (os.getenv(env_key, "") or "").strip()
        if raw.lower() in ("none", "false", "-", "0"):
            return None
        if raw:
            return _safe_ident(raw)
        labels = self._label_counts()
        for c in candidates:
            cc = _safe_ident(c)
            if cc in labels:
                return cc
        return None

    @staticmethod
    def _coalesce_expr(alias: str, props: list[str]) -> str:
        inner = ", ".join(f"toString({alias}.`{p}`)" for p in props)
        return f"trim(toString(coalesce({inner}, '')))"

    def list_documents(self, keyword: str, date_prefix: str, organization: str, page: int, page_size: int) -> dict[str, Any]:
        kw = (keyword or "").strip()
        dp = (date_prefix or "").strip()
        org = (organization or "").strip()
        p = max(1, int(page or 1))
        ps = max(1, min(int(page_size or 20), self.max_limit))
        skip = (p - 1) * ps

        title_n = self._coalesce_expr("n", self.title_props)
        org_n = self._coalesce_expr("n", self.org_props)
        date_n = self._coalesce_expr("n", self.date_props)
        org_link = self._coalesce_expr("o0", self.link_value_props) if self.org_label else "''"
        date_link = self._coalesce_expr("d0", self.link_value_props) if self.date_label else "''"
        title_final = f"trim(toString(coalesce({title_n}, '')))"
        org_final = f"trim(toString(coalesce({org_link}, {org_n}, '')))"
        date_final = f"trim(toString(coalesce({date_link}, {date_n}, '')))"
        org_match = (
            f"OPTIONAL MATCH (n)--(o:`{self.org_label}`)\n        WITH n, collect(o)[0] AS o0"
            if self.org_label
            else "WITH n, NULL AS o0"
        )
        date_match = (
            f"OPTIONAL MATCH (n)--(d:`{self.date_label}`)\n        WITH n, o0, collect(d)[0] AS d0"
            if self.date_label
            else "WITH n, o0, NULL AS d0"
        )
        q_base = f"""
        MATCH (n:`{self.label}`)
        {org_match}
        {date_match}
        WHERE ($kw = '' OR toLower({title_final}) CONTAINS toLower($kw))
          AND ($dp = '' OR {date_final} STARTS WITH $dp)
          AND ($org = '' OR {org_final} = $org)
        """
        q_count = q_base + " RETURN count(n) AS total"
        q_rows = q_base + f"""
        RETURN id(n) AS id,
               {title_final} AS title,
               {org_final} AS organization,
               {date_final} AS publishDate
        ORDER BY publishDate DESC, elementId(n) DESC
        SKIP $skip LIMIT $lim
        """
        bind = {"kw": kw, "dp": dp, "org": org, "skip": skip, "lim": ps}
        total_rows = self._run(q_count, bind)
        rows = self._run(q_rows, bind)
        items = []
        for r in rows:
            items.append(
                {
                    "id": str(r.get("id")),
                    "title": str(r.get("title") or ""),
                    "organization": str(r.get("organization") or ""),
                    "publishDate": str(r.get("publishDate") or ""),
                }
            )
        return {"items": items, "total": int(total_rows[0]["total"]) if total_rows else 0, "page": p, "pageSize": ps}

    def organizations(self) -> list[str]:
        org_n = self._coalesce_expr("n", self.org_props)
        org_link = self._coalesce_expr("o0", self.link_value_props) if self.org_label else "''"
        org_final = f"trim(toString(coalesce({org_link}, {org_n}, '')))"
        org_match = (
            f"OPTIONAL MATCH (n)--(o:`{self.org_label}`)\n        WITH n, collect(o)[0] AS o0"
            if self.org_label
            else "WITH n, NULL AS o0"
        )
        q = f"""
        MATCH (n:`{self.label}`)
        {org_match}
        WHERE {org_final} <> ''
        RETURN DISTINCT {org_final} AS org
        ORDER BY org
        LIMIT 1000
        """
        rows = self._run(q, {})
        return [str(r.get("org")).strip() for r in rows if str(r.get("org") or "").strip()]

    def detail(self, node_id: str) -> dict[str, Any]:
        if not re.fullmatch(r"\d+", (node_id or "").strip()):
            raise ValueError("id 必须是数字")
        title_n = self._coalesce_expr("n", self.title_props)
        org_n = self._coalesce_expr("n", self.org_props)
        date_n = self._coalesce_expr("n", self.date_props)
        content_n = self._coalesce_expr("n", self.content_props)
        org_link = self._coalesce_expr("o0", self.link_value_props) if self.org_label else "''"
        date_link = self._coalesce_expr("d0", self.link_value_props) if self.date_label else "''"
        content_link = self._coalesce_expr("c0", self.link_value_props) if self.content_label else "''"
        org_match = (
            f"OPTIONAL MATCH (n)--(o:`{self.org_label}`)\n        WITH n, collect(o)[0] AS o0"
            if self.org_label
            else "WITH n, NULL AS o0"
        )
        date_match = (
            f"OPTIONAL MATCH (n)--(d:`{self.date_label}`)\n        WITH n, o0, collect(d)[0] AS d0"
            if self.date_label
            else "WITH n, o0, NULL AS d0"
        )
        content_match = (
            f"OPTIONAL MATCH (n)--(c:`{self.content_label}`)\n        WITH n, o0, d0, collect(c)[0] AS c0"
            if self.content_label
            else "WITH n, o0, d0, NULL AS c0"
        )
        q = f"""
        MATCH (n:`{self.label}`)
        WHERE id(n) = $nid
        {org_match}
        {date_match}
        {content_match}
        RETURN id(n) AS id,
               trim(toString(coalesce({title_n}, ''))) AS title,
               trim(toString(coalesce({org_link}, {org_n}, ''))) AS organization,
               trim(toString(coalesce({date_link}, {date_n}, ''))) AS publishDate,
               trim(toString(coalesce({content_link}, {content_n}, ''))) AS content
        LIMIT 1
        """
        rows = self._run(q, {"nid": int(node_id)})
        if not rows:
            raise ValueError("未找到解读文件")
        r = rows[0]
        return {
            "id": str(r.get("id")),
            "title": str(r.get("title") or ""),
            "organization": str(r.get("organization") or ""),
            "publishDate": str(r.get("publishDate") or ""),
            "content": str(r.get("content") or ""),
        }

    @staticmethod
    def _is_valid_token(word: str) -> bool:
        if not word:
            return False
        if len(word) < 2:
            return False
        if re.fullmatch(r"[\W_]+", word):
            return False
        if re.fullmatch(r"\d+", word):
            return False
        return True

    def direction_analysis(self, node_id: str) -> dict[str, Any]:
        doc = self.detail(node_id)
        text = "\n".join([doc.get("title", ""), doc.get("content", "")]).strip()
        if not text:
            return {
                "keywords": [],
                "wordFrequency": [],
                "attributiveFrequency": [],
                "nounFrequency": [],
                "wordCloud": [],
            }

        keyword_rows = jieba.analyse.extract_tags(text, topK=20, withWeight=True)
        keywords = [{"word": str(word), "score": round(float(score), 4)} for word, score in keyword_rows if str(word).strip()]

        all_counter: Counter[str] = Counter()
        attributive_counter: Counter[str] = Counter()
        noun_counter: Counter[str] = Counter()

        for token in pseg.cut(text):
            word = str(token.word or "").strip()
            flag = str(token.flag or "").strip()
            lowered = word.lower()
            if lowered in self._prepositions or not self._is_valid_token(word):
                continue
            all_counter[word] += 1
            if flag.startswith(self._attributive_flags):
                attributive_counter[word] += 1
            if flag.startswith(self._noun_flags):
                noun_counter[word] += 1

        def pack(counter: Counter[str], topn: int) -> list[dict[str, Any]]:
            return [{"word": word, "count": count} for word, count in counter.most_common(topn)]

        word_frequency = pack(all_counter, 30)
        attributive_frequency = pack(attributive_counter, 30)
        noun_frequency = pack(noun_counter, 30)
        word_cloud = pack(all_counter, 5)

        return {
            "keywords": keywords,
            "wordFrequency": word_frequency,
            "attributiveFrequency": attributive_frequency,
            "nounFrequency": noun_frequency,
            "wordCloud": word_cloud,
        }
