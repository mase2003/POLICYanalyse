import os
from typing import Any


class PolicyDataImportService:
    FIELD_MAP = {
        "来源": "来源",
        "标题": "标题",
        "文件名称": "文件名称",
        "网址": "网址",
        "正文": "正文",
        "公文种类": "公文种类",
        "发文机构\\发文机构": "发文机构\\发文机构",
        "发布机构": "发文机构\\发文机构",
        "发布日期": "发布日期",
        "联合发文单位": "联合发文单位",
        "发文字号\\文号": "发文字号\\文号",
        "索引号": "索引号",
        "主题分类\\分类": "主题分类\\分类",
        "成文日期\\印发日期": "成文日期\\印发日期",
        "实施日期": "实施日期",
        "废止日期": "废止日期",
        "有效性": "有效性",
        "附件": "附件",
    }

    def __init__(self, neo_service):
        self._neo = neo_service
        self.label = (os.getenv("HOME_POLICY_LABEL") or "文件名称").strip() or "文件名称"
        self.title_prop = (os.getenv("HOME_TITLE_PROP") or "name").strip() or "name"
        self.date_prop = (os.getenv("HOME_DATE_PROP") or "发文日期").strip() or "发文日期"
        self.category_prop = (os.getenv("HOME_CATEGORY_PROP") or "政策类型").strip() or "政策类型"
        self.org_prop = (os.getenv("CATALOG_ORG_PROP") or os.getenv("SEARCH_ORG_PROP") or "发文机构").strip() or "发文机构"
        self._timeout = float(os.getenv("IMPORT_QUERY_TIMEOUT_SEC", os.getenv("NEO4J_QUERY_TIMEOUT_SEC", "30")))

    @staticmethod
    def _clean_value(value: Any):
        if value is None:
            return None
        text = str(value).strip()
        if not text or text.lower() == "nan":
            return None
        return text

    @staticmethod
    def _dedupe_key(payload: dict[str, Any]) -> tuple[str, str, str, str]:
        def t(v: Any) -> str:
            return str(v or "").strip().lower()

        return (
            t(payload.get("标题") or payload.get("文件名称")),
            t(payload.get("网址")),
            t(payload.get("发文字号\\发文号") or payload.get("发文字号\\文号")),
            t(payload.get("索引号")),
        )

    def _existing_titles(self, titles: list[str]) -> set[str]:
        picked = [str(x or "").strip() for x in titles if str(x or "").strip()]
        if not picked:
            return set()
        cypher = f"""
        UNWIND $titles AS t
        MATCH (n:`{self.label}`)
        WHERE trim(toString(coalesce(n.`{self.title_prop}`, n.`标题`, n.`文件名称`, ''))) = t
        RETURN DISTINCT trim(toString(coalesce(n.`{self.title_prop}`, n.`标题`, n.`文件名称`, ''))) AS t
        """
        rows = self._neo._run(cypher, {"titles": picked}, timeout=self._timeout)
        return {str(r.get("t") or "").strip() for r in rows if str(r.get("t") or "").strip()}

    def import_rows(self, rows: list[dict]) -> dict[str, Any]:
        cleaned_rows: list[dict[str, Any]] = []
        seen_keys: set[tuple[str, str, str, str]] = set()
        skipped_duplicates = 0
        for row in rows or []:
            title = self._clean_value(row.get("标题") or row.get("文件名称"))
            if not title:
                continue
            payload = {}
            for source_key, target_key in self.FIELD_MAP.items():
                value = self._clean_value(row.get(source_key))
                if value is not None:
                    payload[target_key] = value
            payload["标题"] = title
            payload["文件名称"] = title
            payload[self.title_prop] = title
            if payload.get("发布日期"):
                payload[self.date_prop] = payload["发布日期"]
            if payload.get("发文机构\\发文机构"):
                payload[self.org_prop] = payload["发文机构\\发文机构"]
            if payload.get("主题分类\\分类"):
                payload[self.category_prop] = payload["主题分类\\分类"]
            key = self._dedupe_key(payload)
            if key in seen_keys:
                skipped_duplicates += 1
                continue
            seen_keys.add(key)
            cleaned_rows.append(payload)

        if not cleaned_rows:
            return {"imported": 0, "skippedDuplicates": skipped_duplicates, "scanned": 0}

        existing = self._existing_titles([r.get("标题") for r in cleaned_rows])
        to_import = []
        for payload in cleaned_rows:
            if str(payload.get("标题") or "").strip() in existing:
                skipped_duplicates += 1
                continue
            to_import.append(payload)

        if not to_import:
            return {
                "imported": 0,
                "skippedDuplicates": skipped_duplicates,
                "scanned": len(cleaned_rows),
            }

        cypher = f"""
        UNWIND $rows AS row
        MERGE (n:`{self.label}` {{`{self.title_prop}`: row.`{self.title_prop}`}})
        SET n += row,
            n.`{self.title_prop}` = row.`{self.title_prop}`,
            n.`文件名称` = row.`文件名称`,
            n.`标题` = row.`标题`
        RETURN count(n) AS imported
        """
        rows = self._neo._run(cypher, {"rows": to_import}, timeout=self._timeout)
        imported = int(rows[0].get("imported") or 0) if rows else 0
        return {
            "imported": imported,
            "skippedDuplicates": skipped_duplicates,
            "scanned": len(cleaned_rows),
        }
