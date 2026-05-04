"""政策预测：静态纲要/报告解析 + 采集数据多步对比与导出。"""
from __future__ import annotations

import os
import re
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any

from openpyxl import Workbook

from runtime_paths import data_path
from routes.graph_route import service as _graph_service
from services.policy_crawler_service import PolicyCrawlerService
from services.text_keyword_stats import (
    analyze_study_100,
    overlap_bucket,
    vocab_from_study,
)

STEP1_COLUMNS = [
    "来源",
    "标题",
    "网址",
    "公文种类",
    "发文机构\\发文机构",
    "发布日期",
    "联合发文单位",
    "发文字号\\文号",
    "索引号",
    "有效性",
]

# 列表展示：单独由这些字符组成的占位值不展示；关键词本身若含这些字符则过滤
_EXCLUDE_LIST_CHARS = frozenset(']"\u201c\u201d\u2014')  # ]、ASCII"、中文弯引号、一字线 —


def _string_has_excluded_chars(s: str) -> bool:
    if not s:
        return False
    for ch in s:
        if ch in _EXCLUDE_LIST_CHARS:
            return True
    return False


def _sanitize_display_value(v: Any) -> Any:
    if not isinstance(v, str):
        return v
    s = v.strip()
    if not s:
        return None
    stripped = "".join(ch for ch in s if ch not in _EXCLUDE_LIST_CHARS and not ch.isspace())
    if not stripped:
        return None
    return v


def _is_clean_keyword_word(w: str) -> bool:
    w = (w or "").strip()
    return bool(w) and not _string_has_excluded_chars(w)


def _scrub_freq_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [x for x in rows if _is_clean_keyword_word(str(x.get("word") or ""))]


def _scrub_study(study: dict[str, Any]) -> dict[str, Any]:
    out = dict(study)
    for k in ("fourCharFrequency", "nounFrequency", "attributiveFrequency", "generalFrequency"):
        out[k] = _scrub_freq_rows(list(out.get(k) or []))
    kw100: list[str] = []
    for k in ("fourCharFrequency", "nounFrequency", "attributiveFrequency", "generalFrequency"):
        for x in out.get(k) or []:
            w = str(x.get("word") or "")
            kw100.append(w)
    out["keywords100"] = kw100
    tfidf: list[dict[str, Any]] = []
    for it in out.get("tfidfKeywords") or []:
        if _is_clean_keyword_word(str(it.get("word") or "")):
            tfidf.append(it)
    out["tfidfKeywords"] = tfidf
    return out


def _forecast_text_file(env_key: str, default_under_root: Path) -> Path:
    raw = (os.getenv(env_key) or "").strip().strip('"').strip("'")
    if raw:
        return Path(raw)
    return default_under_root


class PolicyForecastService:
    def __init__(self) -> None:
        root = data_path("POLICY_FORECAST_DATA_DIR")
        self.root = root
        self.path_fifteen_main = _forecast_text_file(
            "POLICY_FORECAST_FILE_FIFTEEN_MAIN",
            root / "中华人民共和国国民经济和社会发展第十五个五年规划纲要.txt",
        )
        self.path_fifteen_concept = _forecast_text_file(
            "POLICY_FORECAST_FILE_FIFTEEN_CONCEPT",
            root / "十五五规划解析.txt",
        )
        self.path_party20 = _forecast_text_file(
            "POLICY_FORECAST_FILE_PARTY20",
            root / "中国共产党第二十次全国代表大会报告.txt",
        )

    @staticmethod
    def _read_paragraphs(path: Path) -> list[str]:
        if not path.exists():
            return [f"（未找到文件：{path.name}，请将文本放在项目根目录）"]
        raw = path.read_text(encoding="utf-8", errors="ignore")
        if not raw.strip():
            return [f"（文件「{path.name}」暂无内容，请将正文保存到：{path}）"]
        parts = re.split(r"\r?\n{2,}", raw)
        ps = [p.strip() for p in parts if p.strip()]
        if ps:
            return ps
        lines = [ln.strip() for ln in raw.splitlines() if ln.strip()]
        if lines:
            return lines
        return [raw.strip()]

    def fifteen_five_bundle(self) -> dict[str, Any]:
        main_ps = self._read_paragraphs(self.path_fifteen_main)
        concept_ps = self._read_paragraphs(self.path_fifteen_concept)
        main_text = "\n".join(main_ps)
        concept_text = "\n".join(concept_ps)
        return {
            "main": {"paragraphs": main_ps},
            "mainAnalysis": analyze_study_100(main_text),
            "concept": {
                "paragraphs": concept_ps,
                "fullText": "\n\n".join(concept_ps),
            },
            "conceptAnalysis": analyze_study_100(concept_text),
        }

    def party20_bundle(self) -> dict[str, Any]:
        ps = self._read_paragraphs(self.path_party20)
        text = "\n".join(ps)
        return {"paragraphs": ps, "analysis": analyze_study_100(text)}

    @staticmethod
    def _filter_items(
        items: list[dict[str, Any]],
        source: str,
        doc_type: str,
        category: str,
    ) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        for row in items:
            if source and (row.get("来源") or "").strip() != source:
                continue
            if doc_type and (row.get("公文种类") or "").strip() != doc_type:
                continue
            if category and (row.get("主题分类\\分类") or "").strip() != category:
                continue
            out.append(row)
        return out

    @staticmethod
    def _row_for_table(row: dict[str, Any]) -> dict[str, Any]:
        out = {k: _sanitize_display_value(row.get(k)) for k in STEP1_COLUMNS}
        out["_rowId"] = row.get("_rowId")
        return out

    def normalize_selected_trend_keywords(self, body: dict[str, Any]) -> list[str]:
        raw_selected = body.get("selectedTrendKeywords")
        selected_keys: list[str] = []
        if isinstance(raw_selected, list):
            for x in raw_selected:
                s = str(x).strip()
                if _is_clean_keyword_word(s):
                    selected_keys.append(s)
        return selected_keys

    def build_step5_policies_list(self, selected_keys: list[str]) -> list[dict[str, Any]]:
        matched: list[dict[str, Any]] = []
        if not selected_keys:
            return matched
        try:
            raw_policies = _graph_service.search_nodes_by_file_name_keywords(selected_keys)
        except Exception:
            raw_policies = []
        for rp in raw_policies:
            row = dict(rp)
            fn = row.get("文件名称")
            row["文件名称"] = _sanitize_display_value(fn) or fn or ""
            for k in (
                "标题",
                "发文日期",
                "主题分类",
                "发文机构",
                "网址",
                "来源",
                "公文种类",
                "发布日期",
                "发文机构\\发文机构",
            ):
                if k not in row:
                    continue
                v = _sanitize_display_value(row.get(k))
                row[k] = v if v is not None else row.get(k)
            matched.append(row)
        return matched

    @staticmethod
    def _publish_in_month(row: dict[str, Any], ym: str) -> bool:
        """ym 形如 2026-04，匹配发布日期或成文日期字段中的同年同月。"""
        if not ym or len(ym) < 7:
            return True
        parts = ym.split("-")
        if len(parts) < 2:
            return True
        y, mo = parts[0], str(int(parts[1]))
        blob = " ".join(
            str(row.get(k) or "")
            for k in ("发布日期", "成文日期\\印发日期", "实施日期")
        )
        if not blob.strip():
            return False
        if ym in blob or f"{y}-{mo.zfill(2)}" in blob:
            return True
        if f"{y}年{mo}月" in blob or f"{y}年{mo.zfill(2)}月" in blob:
            return True
        m = re.search(r"(\d{4})\D*(\d{1,2})", blob)
        if m and m.group(1) == y and str(int(m.group(2))) == mo:
            return True
        return False

    def crawler_parse_pipeline(self, crawler: PolicyCrawlerService, body: dict[str, Any]) -> dict[str, Any]:
        task_id = (body.get("taskId") or "").strip() or crawler.get_latest_task_id() or ""
        if not task_id:
            raise ValueError("暂无采集任务，请先在「最新政策获取」中执行一次采集")
        source = (body.get("source") or "").strip()
        doc_type = (body.get("docType") or "").strip()
        category = (body.get("category") or "").strip()
        selected_row_ids = [str(x).strip() for x in (body.get("selectedRowIds") or []) if str(x).strip()]

        task = crawler.status(task_id)
        items = list(task.get("items") or [])
        filtered = self._filter_items(items, source, doc_type, category)
        month = (body.get("month") or "").strip()
        if month:
            filtered = [r for r in filtered if self._publish_in_month(r, month)]
        if selected_row_ids:
            selected_set = set(selected_row_ids)
            filtered = [r for r in filtered if str(r.get("_rowId") or "") in selected_set]
        step1_rows = [self._row_for_table(r) for r in filtered]

        corpus_text = "\n".join(
            f"{(r.get('标题') or '')}\n{(r.get('正文') or '')}" for r in filtered
        )
        corpus_study = analyze_study_100(corpus_text) if corpus_text.strip() else analyze_study_100("")
        corpus_study = _scrub_study(corpus_study)

        main_ps = self._read_paragraphs(self.path_fifteen_main)
        party_ps = self._read_paragraphs(self.path_party20)
        ref_text = "\n".join(main_ps) + "\n" + "\n".join(party_ps)
        ref_study = _scrub_study(analyze_study_100(ref_text))

        overlap_four = overlap_bucket(corpus_study["fourCharFrequency"], ref_study["fourCharFrequency"], 10)
        overlap_noun = overlap_bucket(corpus_study["nounFrequency"], ref_study["nounFrequency"], 10)
        overlap_general = overlap_bucket(corpus_study["generalFrequency"], ref_study["generalFrequency"], 10)

        ref_vocab = vocab_from_study(ref_study)
        corpus_vocab = vocab_from_study(corpus_study)

        new_words: list[dict[str, Any]] = []
        for w in corpus_study["keywords100"]:
            if not _is_clean_keyword_word(w):
                continue
            if w not in ref_vocab:
                c = int(corpus_study["freqAll"].get(w, 0))
                new_words.append({"word": w, "count": c})
        new_words.sort(key=lambda x: (-x["count"], x["word"]))
        new_words = new_words[:40]

        disappeared: list[dict[str, Any]] = []
        ref_freq = Counter()
        for k in ("fourCharFrequency", "nounFrequency", "attributiveFrequency", "generalFrequency"):
            for it in ref_study.get(k) or []:
                w0 = str(it["word"])
                if not _is_clean_keyword_word(w0):
                    continue
                ref_freq[w0] = int(it.get("count") or 0)
        for w, c in ref_freq.most_common(200):
            if w not in corpus_vocab:
                disappeared.append({"word": w, "count": c})
        disappeared = disappeared[:40]

        trend: list[str] = []
        for w in [x["word"] for x in overlap_four + overlap_noun + overlap_general]:
            if _is_clean_keyword_word(w) and w not in trend:
                trend.append(w)
        for w in [x["word"] for x in new_words[:25]]:
            if _is_clean_keyword_word(w) and w not in trend:
                trend.append(w)
        for w in corpus_study["keywords100"][:30]:
            if _is_clean_keyword_word(w) and w not in trend:
                trend.append(w)
        trend = trend[:80]

        selected_keys = self.normalize_selected_trend_keywords(body)
        matched = self.build_step5_policies_list(selected_keys)

        return {
            "taskId": task_id,
            "filters": {
                "source": source,
                "docType": doc_type,
                "category": category,
                "month": month,
                "selectedRowIds": selected_row_ids,
                "selectedTrendKeywords": selected_keys,
            },
            "step1": {"rows": step1_rows, "total": len(step1_rows)},
            "step2": corpus_study,
            "step3": {
                "overlapFour": overlap_four,
                "overlapNoun": overlap_noun,
                "overlapGeneral": overlap_general,
            },
            "step4": {"newWords": new_words, "disappeared": disappeared},
            "step5": {"trendKeywords": trend, "policies": matched},
            "_rawFiltered": filtered,
        }

    @staticmethod
    def _truncate_xlsx_cell(value: Any, max_len: int = 32000) -> Any:
        if value is None:
            return ""
        if not isinstance(value, str):
            value = str(value)
        if len(value) > max_len:
            return value[: max_len - 30] + "\n…(正文过长已截断，请从图库查看全文)"
        return value

    @staticmethod
    def _step6_policy_export_row(policy: dict[str, Any], detail: dict[str, Any]) -> list[Any]:
        """detail 为 get_policy_detail 的 detail 字典；与前端政策原文字段一致。"""

        def d(key: str, fallback: str = "") -> str:
            v = detail.get(key)
            if v is None:
                return fallback
            s = str(v).strip()
            return s if s else fallback

        mk = policy.get("matchedKeywords") or []
        mk_str = ",".join(mk) if isinstance(mk, list) else str(mk)
        body = PolicyForecastService._truncate_xlsx_cell(d("正文"))
        file_name_col = (policy.get("文件名称") or "").strip() or d("标题")
        return [
            file_name_col,
            d("标题", policy.get("标题") or ""),
            body,
            d("网址"),
            d("来源"),
            d("公文种类"),
            d("发文机构\\发文机构", policy.get("发文机构") or ""),
            d("发布日期", policy.get("发文日期") or ""),
            d("联合发文单位"),
            d("发文字号\\文号"),
            d("索引号"),
            d("主题分类\\分类", policy.get("主题分类") or ""),
            d("成文日期\\印发日期"),
            d("实施日期"),
            d("废止日期"),
            d("有效性"),
            d("附件"),
            mk_str,
            policy.get("neo4jId") or "",
        ]

    @staticmethod
    def export_parse_workbook(pipeline: dict[str, Any]) -> Path:
        export_dir = data_path("EXPORTS_DIR", "exports")
        export_dir.mkdir(parents=True, exist_ok=True)
        path = export_dir / f"policy_parse_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
        wb = Workbook()

        def write_sheet(name: str, headers: list[str], rows: list[list[Any]]):
            ws = wb.create_sheet(title=name)
            ws.append(headers)
            for row in rows:
                ws.append(row)

        # remove default
        default = wb.active
        wb.remove(default)

        s1 = pipeline.get("step1") or {}
        rows1 = s1.get("rows") or []
        h1 = list(STEP1_COLUMNS) + ["正文", "命中关键词"]
        data1: list[list[Any]] = []
        items_map: dict[str, dict] = {}
        for raw in pipeline.get("_rawFiltered") or []:
            rid = str(raw.get("_rowId") or "")
            if rid:
                items_map[rid] = raw
        hit_map_export: dict[str, list[str]] = {}
        for p in (pipeline.get("step5") or {}).get("policies") or []:
            rid = str(p.get("_rowId") or "")
            if rid and p.get("matchedKeywords"):
                hit_map_export[rid] = list(p["matchedKeywords"])
        for r in rows1:
            rid = str(r.get("_rowId") or "")
            raw = items_map.get(rid) or {}
            body = (raw.get("正文") or "") if isinstance(raw, dict) else ""
            mk = ",".join(hit_map_export.get(rid, []))
            data1.append([r.get(k) for k in STEP1_COLUMNS] + [body, mk])
        write_sheet("Sheet1-政策全文", h1, data1)

        def study_rows(study: dict[str, Any], label: str) -> list[list[Any]]:
            out: list[list[Any]] = []
            for cat, key in [
                ("四字词语", "fourCharFrequency"),
                ("关键名词", "nounFrequency"),
                ("定语", "attributiveFrequency"),
                ("综合词频", "generalFrequency"),
            ]:
                for it in study.get(key) or []:
                    out.append([label, cat, it.get("word"), it.get("count")])
            for it in study.get("tfidfKeywords") or []:
                out.append([label, "TF-IDF", it.get("word"), it.get("score")])
            return out

        s2 = pipeline.get("step2") or {}
        write_sheet("Sheet2-第二页关键词", ["阶段", "类别", "词语", "值"], study_rows(s2, "采集数据"))

        s3 = pipeline.get("step3") or {}
        r3: list[list[Any]] = []
        for cat, key in [("四字", "overlapFour"), ("名词", "overlapNoun"), ("综合词频", "overlapGeneral")]:
            for it in s3.get(key) or []:
                r3.append([cat, it.get("word"), it.get("count")])
        write_sheet("Sheet3-第三页重合词", ["类别", "词语", "频次"], r3)

        s4 = pipeline.get("step4") or {}
        r4: list[list[Any]] = []
        for it in s4.get("newWords") or []:
            r4.append(["新出现", it.get("word"), it.get("count")])
        for it in s4.get("disappeared") or []:
            r4.append(["消失", it.get("word"), it.get("count")])
        write_sheet("Sheet4-第四页新旧词", ["类型", "词语", "频次"], r4)

        s5 = pipeline.get("step5") or {}
        r5: list[list[Any]] = []
        r5.append(["【本月趋势关键词】", "", ""])
        for kw in s5.get("trendKeywords") or []:
            r5.append([kw, "", ""])
        r5.append([])
        r5.append(
            [
                "说明：第五步政策明细（含「正文」及多字段）请见 Sheet「Sheet6-第五页图库全文导出」。",
                "",
                "",
            ]
        )
        write_sheet("Sheet5-第五页趋势关键词", ["列1", "列2", "列3"], r5)

        step6_headers = [
            "文件名称",
            "标题",
            "正文",
            "网址",
            "来源",
            "公文种类",
            "发文机构",
            "发布日期",
            "联合发文单位",
            "发文字号",
            "索引号",
            "主题分类",
            "成文日期",
            "实施日期",
            "废止日期",
            "有效性",
            "附件",
            "命中关键词",
            "节点ID",
        ]
        r6: list[list[Any]] = []
        seen_policy_keys: set[tuple[str, str, str]] = set()
        for p in s5.get("policies") or []:
            dedupe_key = (
                str(p.get("neo4jId") or "").strip(),
                str(p.get("标题") or p.get("文件名称") or "").strip(),
                str(p.get("网址") or "").strip(),
            )
            if dedupe_key in seen_policy_keys:
                continue
            seen_policy_keys.add(dedupe_key)
            det: dict[str, Any] = {}
            nid = p.get("neo4jId")
            if nid:
                try:
                    raw = _graph_service.get_policy_detail(nid)
                    det = raw.get("detail") or {}
                except Exception:
                    det = {}
            r6.append(PolicyForecastService._step6_policy_export_row(p, det))
        write_sheet("Sheet6-第五页图库全文导出", step6_headers, r6)

        wb.save(path)
        return path
