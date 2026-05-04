import csv
import json
import os
import re
import threading
import time
import uuid
from datetime import datetime
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup
from openpyxl import Workbook

from runtime_paths import data_path


class PolicyCrawlerService:
    FIELDS = [
        "爬取编号",
        "来源",
        "标题",
        "网址",
        "正文",
        "公文种类",
        "发文机构\\发文机构",
        "发布日期",
        "联合发文单位",
        "发文字号\\文号",
        "索引号",
        "主题分类\\分类",
        "成文日期\\印发日期",
        "实施日期",
        "废止日期",
        "有效性",
        "附件",
    ]

    REGION_SOURCES = {
        "北京市": "https://www.beijing.gov.cn/zhengce/zhengcefagui/",
        "广东省": "https://www.gd.gov.cn/zwgk/wjk/qbwj/index.html",
        "上海市": "https://www.shanghai.gov.cn/nw39221/index.html",
        "四川省": "https://www.sc.gov.cn/10462/c103042/stt_list.shtml",
    }
    FIELD_LABELS = {
        "公文种类": ["公文种类"],
        "发文机构\\发文机构": ["发文机构", "发布机构"],
        "联合发文单位": ["联合发文单位"],
        "发文字号\\文号": ["发文字号", "文号", "文 号"],
        "索引号": ["索引号", "索 引 号"],
        "主题分类\\分类": ["主题分类"],
        "成文日期\\印发日期": ["成文日期", "印发日期"],
        "实施日期": ["实施日期"],
        "废止日期": ["废止日期"],
        "有效性": ["有效性", "有 效 性"],
    }

    def __init__(self, redis_cache):
        self._cache = redis_cache
        self._tasks = {}
        self._lock = threading.Lock()
        self._request_interval = float(os.getenv("CRAWLER_REQUEST_INTERVAL_SEC", "1.5"))
        self._request_timeout = float(os.getenv("CRAWLER_REQUEST_TIMEOUT_SEC", "10"))
        self._retry_max = int(os.getenv("CRAWLER_RETRY_MAX", "2"))
        self._cache_ttl = int(os.getenv("CRAWLER_CACHE_TTL_SEC", "3600"))
        self._latest_task_id: str | None = None

        self._csv_path = data_path("POLICYDATA_CSV_PATH", "policydata.csv")
        self._seq_path = data_path("POLICYDATA_SEQ_PATH", "policydata_seq.txt")
        self._task_store_dir = data_path("CRAWLER_TASK_STORE_DIR", "backend", "crawler_task_items")
        self._task_store_dir.mkdir(parents=True, exist_ok=True)

    def start(self, payload):
        err = self._validate_payload(payload)
        if err:
            raise ValueError(err)

        task_id = uuid.uuid4().hex
        task = {
            "taskId": task_id,
            "status": "running",
            "message": "爬取任务已启动",
            "progress": 0,
            "createdAt": datetime.now().isoformat(),
            "params": payload,
            "matched": 0,
            "written": 0,
            "failed": 0,
            "skipped": 0,
            "reasonStats": {},
            "csvPath": str(self._csv_path),
            "errors": [],
            "items": [],
        }
        with self._lock:
            self._tasks[task_id] = task
        self._latest_task_id = task_id
        if self._cache:
            self._cache.set("crawler:latest_task_id", task_id, ttl=self._cache_ttl)
        self._save_task(task_id)

        t = threading.Thread(target=self._run_task, args=(task_id,), daemon=True)
        t.start()
        return {"taskId": task_id, "status": "running", "cacheRetentionSec": self._cache_ttl}

    def get_latest_task_id(self) -> str | None:
        if self._cache:
            raw = self._cache.get("crawler:latest_task_id")
            if raw:
                return raw.decode("utf-8") if isinstance(raw, bytes) else str(raw)
            raw_done = self._cache.get("crawler:latest_completed_task_id")
            if raw_done:
                return raw_done.decode("utf-8") if isinstance(raw_done, bytes) else str(raw_done)
        return self._latest_task_id

    def _inject_crawler_meta(self, snap: dict, *, from_csv_fallback: bool) -> dict:
        out = dict(snap)
        out["cacheRetentionSec"] = self._cache_ttl
        out["fromCsvFallback"] = from_csv_fallback
        return out

    def latest_task_snapshot(self):
        """优先返回最近任务；若缓存过期，则从 policydata.csv 恢复最近采集数据。"""
        task_id = self.get_latest_task_id()
        if task_id:
            try:
                snap = self.status(task_id)
                if snap.get("items"):
                    return self._inject_crawler_meta(snap, from_csv_fallback=False)
            except ValueError:
                pass

        csv_rows = self._load_latest_rows_from_csv()
        if csv_rows:
            pseudo_task_id = "csv-latest"
            items = self._attach_row_ids(pseudo_task_id, csv_rows)
            return self._inject_crawler_meta(
                {
                    "taskId": pseudo_task_id,
                    "status": "done",
                    "message": "任务缓存已过期，已从 policydata.csv 恢复最近采集数据",
                    "progress": 100,
                    "createdAt": None,
                    "params": {},
                    "matched": len(items),
                    "written": len(items),
                    "failed": 0,
                    "skipped": 0,
                    "reasonStats": {},
                    "csvPath": str(self._csv_path),
                    "errors": [],
                    "items": items,
                },
                from_csv_fallback=True,
            )
        raise ValueError("暂无采集任务，请先在「最新政策获取」中执行一次采集")

    def status(self, task_id):
        if not task_id:
            raise ValueError("taskId is required")
        with self._lock:
            task = self._tasks.get(task_id)
        if task:
            out = dict(task)
            out["cacheRetentionSec"] = self._cache_ttl
            out["fromCsvFallback"] = False
            return out
        disk_task = self._load_task_meta_from_disk(task_id)
        cached = self._cache.get_json(f"crawler:task:{task_id}:meta") if self._cache else None
        if not cached and disk_task:
            cached = disk_task
        if not cached:
            raise ValueError("任务不存在或已过期")
        cached = dict(cached)
        cached["items"] = self._resolve_task_items(task_id)
        cached["cacheRetentionSec"] = self._cache_ttl
        cached["fromCsvFallback"] = False
        return cached

    def export_csv(self, task_id):
        task = self.status(task_id)
        items = self._dedupe_rows(self._resolve_task_items(task_id))
        if not items:
            raise ValueError("暂无可导出的爬取数据")
        written, skipped, csv_path = self._append_rows(items)
        task["written"] = written
        task["csvPath"] = str(csv_path)
        task["status"] = "done"
        task["message"] = "CSV 写入完成"
        self._save_task(task_id, task)
        return {"taskId": task_id, "written": written, "skippedDuplicates": skipped, "csvPath": str(csv_path)}

    def export_selected_xlsx(self, task_id, row_ids=None):
        items = self._dedupe_rows(self._select_rows(task_id, row_ids))
        if not items:
            raise ValueError("请选择需要导出的政策")
        output_dir = data_path("EXPORTS_DIR", "exports")
        output_dir.mkdir(parents=True, exist_ok=True)
        output_path = output_dir / f"crawler_{task_id[:8]}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
        wb = Workbook()
        ws = wb.active
        ws.title = "最新政策"
        ws.append([
            "来源",
            "标题",
            "公文种类",
            "发文机构\\发文机构",
            "发布日期",
            "联合发文单位",
            "发文字号\\文号",
            "索引号",
            "主题分类\\分类",
            "成文日期\\印发日期",
            "实施日期",
            "废止日期",
            "有效性",
            "附件",
            "网址",
        ])
        for row in items:
            ws.append([
                row.get("来源"),
                row.get("标题"),
                row.get("公文种类"),
                row.get("发文机构\\发文机构"),
                row.get("发布日期"),
                row.get("联合发文单位"),
                row.get("发文字号\\文号"),
                row.get("索引号"),
                row.get("主题分类\\分类"),
                row.get("成文日期\\印发日期"),
                row.get("实施日期"),
                row.get("废止日期"),
                row.get("有效性"),
                row.get("附件"),
                row.get("网址"),
            ])
        wb.save(output_path)
        return {"path": str(output_path), "count": len(items)}

    def resolve_import_rows(self, task_id, row_ids=None):
        items = self._dedupe_rows(self._select_rows(task_id, row_ids))
        if not items:
            raise ValueError("请选择需要导入的数据")
        return items

    def _run_task(self, task_id):
        task = self._tasks[task_id]
        p = task["params"]
        all_rows = []
        failed = 0
        skipped = 0
        errors = []
        reason_stats = {}
        keywords = self._split_keywords(p.get("keywords", ""))
        limit = int(p["limit"])
        regions = p["regions"]

        try:
            for idx, region in enumerate(regions):
                if len(all_rows) >= limit:
                    break
                base_url = self.REGION_SOURCES.get(region)
                if not base_url:
                    continue

                links = self._fetch_links(base_url, region, keywords, limit - len(all_rows))
                for link in links:
                    if len(all_rows) >= limit:
                        break
                    row, reason = self._fetch_detail(link, region, p["startDate"], p["endDate"], keywords)
                    if row:
                        all_rows.append(row)
                    else:
                        if reason in ("http_forbidden", "http_empty", "parse_error", "detail_fetch_error"):
                            failed += 1
                        else:
                            skipped += 1
                        reason_stats[reason] = reason_stats.get(reason, 0) + 1
                    time.sleep(self._request_interval)

                task["progress"] = int(((idx + 1) / max(1, len(regions))) * 100)
                task["matched"] = len(all_rows)
                task["failed"] = failed
                task["skipped"] = skipped
                task["reasonStats"] = reason_stats
                task["message"] = f"已完成 {idx + 1}/{len(regions)} 个地区"
                self._save_task(task_id, task)

            cleaned = self._clean_and_dedupe(all_rows)
            cleaned = self._attach_row_ids(task_id, cleaned)
            if self._cache:
                self._cache.set_json(f"crawler:task:{task_id}:items", cleaned, ttl=self._cache_ttl)
            self._persist_task_items(task_id, cleaned)
            written, skipped_in_csv, csv_path = self._append_rows(cleaned)

            task["status"] = "done"
            task["message"] = f"爬取完成，文件已生成：{csv_path.name}"
            task["matched"] = len(cleaned)
            task["written"] = written
            task["skipped"] = skipped + skipped_in_csv
            task["csvPath"] = str(csv_path)
            task["failed"] = failed
            task["reasonStats"] = reason_stats
            task["errors"] = errors[-20:]
            task["progress"] = 100
            task["items"] = cleaned
            if self._cache:
                self._cache.set("crawler:latest_completed_task_id", task_id, ttl=self._cache_ttl)
            self._save_task(task_id, task)
            self._persist_task_meta(task_id, task)
        except Exception as exc:
            task["status"] = "failed"
            task["message"] = f"爬取失败: {exc}"
            task["errors"] = [str(exc)]
            self._save_task(task_id, task)

    def _fetch_links(self, url, region, keywords, limit):
        html = self._request_text(url)
        if not html:
            return []
        soup = BeautifulSoup(html, "html.parser")
        links = []
        seen = set()
        scanned = 0
        for a in soup.select("a[href]"):
            title = self._clean_text(a.get_text(" ", strip=True))
            href = a.get("href", "").strip()
            if not title or not href:
                continue
            full = urljoin(url, href)
            if urlparse(full).scheme not in ("http", "https"):
                continue
            # 这些省站 http 链接常被网关拒绝，统一切到 https 提升成功率。
            full = re.sub(r"^http://(www\.)?gd\.gov\.cn", "https://www.gd.gov.cn", full, flags=re.I)
            full = re.sub(r"^http://(www\.)?sc\.gov\.cn", "https://www.sc.gov.cn", full, flags=re.I)
            scanned += 1
            if not self._is_policy_detail_link(region, full, title):
                continue
            if full in seen:
                continue
            seen.add(full)
            links.append({"title": title, "url": full, "source": region})
            if len(links) >= limit * 8:
                break
            if scanned > 2000:
                break
        return links

    def _fetch_detail(self, link, region, start_date, end_date, keywords):
        html = self._request_text(link["url"])
        if not html:
            return None, "http_empty"
        try:
            soup = BeautifulSoup(html, "html.parser")
            full_text_raw = soup.get_text("\n", strip=True)
            full_text = self._clean_text(full_text_raw)
            text = self._extract_main_text(soup)
            title = self._extract_title(soup) or link["title"]
            pub_date = self._extract_publish_date(soup, full_text)
            if pub_date and not self._date_in_range(pub_date, start_date, end_date):
                return None, "date_out_of_range"
            if keywords and not (self._contains_keywords(title, keywords) or self._contains_keywords(full_text)):
                return None, "keyword_mismatch"

            meta = self._extract_meta_fields(soup, full_text_raw)
            annex = self._extract_attachments(soup, link["url"])
            row = {
                "来源": region,
                "标题": title,
                "网址": link["url"],
                "正文": text[:50000] if text else None,
                "公文种类": meta.get("公文种类"),
                "发文机构\\发文机构": meta.get("发文机构\\发文机构"),
                "发布日期": pub_date,
                "联合发文单位": meta.get("联合发文单位"),
                "发文字号\\文号": meta.get("发文字号\\文号"),
                "索引号": meta.get("索引号"),
                "主题分类\\分类": meta.get("主题分类\\分类"),
                "成文日期\\印发日期": meta.get("成文日期\\印发日期"),
                "实施日期": meta.get("实施日期"),
                "废止日期": meta.get("废止日期"),
                "有效性": meta.get("有效性"),
                "附件": annex,
            }
            for k, v in list(row.items()):
                if v in ("", "--"):
                    row[k] = None
            if isinstance(row.get("废止日期"), str) and re.fullmatch(r"\d{10,13}", row["废止日期"]):
                row["废止日期"] = None
            if isinstance(row.get("发文字号\\文号"), str) and row["发文字号\\文号"] in {"：", ":"}:
                row["发文字号\\文号"] = None
            if region == "四川省":
                row["发文字号\\文号"] = self._tighten_sc_meta_field(row.get("发文字号\\文号"), "doc_no")
                row["索引号"] = self._tighten_sc_meta_field(row.get("索引号"), "index_no")
            return row, ""
        except Exception:
            return None, "parse_error"

    def _append_rows(self, rows):
        if not rows:
            return 0, 0, self._csv_path
        self._csv_path.parent.mkdir(parents=True, exist_ok=True)
        existing_before = self._read_existing_rows()
        existing_count = len(existing_before)
        merged_rows = self._merge_with_existing(rows)
        merged_count = len(merged_rows)
        written = max(0, merged_count - existing_count)
        skipped = max(0, len(rows) - written)

        try:
            self._write_rows(self._csv_path, merged_rows, 0, overwrite=True)
        except PermissionError:
            raise PermissionError(
                f"policydata.csv 正在被占用，请关闭 Excel/WPS 后重试: {self._csv_path}"
            )

        self._write_seq(len(merged_rows))
        return written, skipped, self._csv_path

    def _write_rows(self, file_path: Path, rows: list[dict], start_seq: int, overwrite: bool = False):
        mode = "w" if overwrite else "a"
        file_exists = file_path.exists() and file_path.stat().st_size > 0
        with file_path.open(mode, newline="", encoding="utf-8-sig") as f:
            writer = csv.DictWriter(f, fieldnames=self.FIELDS)
            if overwrite or not file_exists:
                writer.writeheader()
            seq = start_seq
            for row in rows:
                seq += 1
                out = {"爬取编号": seq}
                for field in self.FIELDS[1:]:
                    out[field] = row.get(field)
                writer.writerow(out)

    def _clean_and_dedupe(self, rows):
        out = []
        seen = {}
        for r in rows:
            key = (
                self._clean_text(r.get("标题") or ""),
                self._clean_text(r.get("发文字号\\文号") or ""),
                self._clean_text(r.get("索引号") or ""),
            )
            cleaned = {}
            for k, v in r.items():
                if isinstance(v, str):
                    val = re.sub(r"\s+", " ", v).strip()
                    cleaned[k] = val if val else None
                else:
                    cleaned[k] = v
            seen[key] = cleaned
        return list(seen.values())

    def _attach_row_ids(self, task_id, rows):
        out = []
        for idx, row in enumerate(rows, start=1):
            item = dict(row)
            item["_rowId"] = f"{task_id}:{idx}"
            out.append(item)
        return out

    def _resolve_task_items(self, task_id):
        items = self._cache.get_json(f"crawler:task:{task_id}:items") if self._cache else None
        if isinstance(items, list) and len(items) > 0:
            return items
        with self._lock:
            task = self._tasks.get(task_id) or {}
        task_items = task.get("items")
        if isinstance(task_items, list) and len(task_items) > 0:
            return task_items
        disk = self._load_task_items_from_disk(task_id)
        return disk if isinstance(disk, list) else []

    def _persist_task_items(self, task_id: str, items: list) -> None:
        path = self._task_store_dir / f"{task_id}_items.json"
        try:
            with path.open("w", encoding="utf-8") as f:
                json.dump(items, f, ensure_ascii=False)
        except Exception:
            pass

    def _load_task_items_from_disk(self, task_id: str) -> list | None:
        path = self._task_store_dir / f"{task_id}_items.json"
        if not path.exists():
            return None
        try:
            with path.open("r", encoding="utf-8") as f:
                data = json.load(f)
            return data if isinstance(data, list) else None
        except Exception:
            return None

    def _persist_task_meta(self, task_id: str, task: dict) -> None:
        """磁盘保留任务元信息，便于 Redis 仅残留 meta、items 已过期时仍能组装状态。"""
        safe = {
            k: task.get(k)
            for k in (
                "taskId",
                "status",
                "message",
                "progress",
                "createdAt",
                "params",
                "matched",
                "written",
                "failed",
                "skipped",
                "reasonStats",
                "csvPath",
                "errors",
            )
        }
        safe["taskId"] = task_id
        path = self._task_store_dir / f"{task_id}_meta.json"
        try:
            with path.open("w", encoding="utf-8") as f:
                json.dump(safe, f, ensure_ascii=False)
        except Exception:
            pass

    def _load_task_meta_from_disk(self, task_id: str) -> dict | None:
        path = self._task_store_dir / f"{task_id}_meta.json"
        if not path.exists():
            return None
        try:
            with path.open("r", encoding="utf-8") as f:
                data = json.load(f)
            return data if isinstance(data, dict) else None
        except Exception:
            return None

    def _select_rows(self, task_id, row_ids=None):
        items = self._resolve_task_items(task_id)
        if not items:
            return []
        if not row_ids:
            return items
        selected = set(str(v) for v in row_ids if str(v).strip())
        return [row for row in items if str(row.get("_rowId")) in selected]

    def _merge_with_existing(self, rows):
        ordered = {}
        for row in self._read_existing_rows():
            ordered[self._dedupe_key(row)] = row
        for row in rows:
            ordered[self._dedupe_key(row)] = row
        return list(ordered.values())

    def _read_existing_rows(self):
        if not self._csv_path.exists():
            return []
        last_error = None
        for encoding in ("utf-8-sig", "utf-8", "gb18030", "gbk"):
            try:
                with self._csv_path.open("r", newline="", encoding=encoding) as f:
                    reader = csv.DictReader(f)
                    out = []
                    for row in reader:
                        item = {}
                        for field in self.FIELDS[1:]:
                            item[field] = row.get(field) or None
                        out.append(item)
                    return out
            except UnicodeDecodeError as exc:
                last_error = exc
                continue
        if last_error:
            raise last_error
        return []

    def _load_latest_rows_from_csv(self):
        rows = self._read_existing_rows()
        if not rows:
            return []
        # CSV 中保留历史数据；这里优先返回靠后的较新结果，避免一次拉全量导致前端过重
        tail = rows[-300:]
        return list(reversed(tail))

    def _dedupe_key(self, row):
        return (
            self._clean_text(row.get("标题") or ""),
            self._clean_text(row.get("发文字号\\文号") or ""),
            self._clean_text(row.get("索引号") or ""),
        )

    def _dedupe_rows(self, rows):
        ordered = {}
        for row in rows or []:
            ordered[self._dedupe_key(row)] = row
        return list(ordered.values())

    def _request_text(self, url):
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
            ),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            "Connection": "keep-alive",
        }
        for i in range(self._retry_max + 1):
            try:
                headers["Referer"] = f"{urlparse(url).scheme}://{urlparse(url).netloc}/"
                resp = requests.get(url, headers=headers, timeout=self._request_timeout)
                if resp.status_code >= 400:
                    if resp.status_code in (401, 403):
                        return None
                    continue
                resp.encoding = resp.apparent_encoding or "utf-8"
                return resp.text
            except Exception:
                if i >= self._retry_max:
                    return None
                time.sleep(5)
        return None

    @staticmethod
    def _is_policy_detail_link(region, url, title):
        u = (url or "").lower()
        t = (title or "").strip()
        if len(t) < 8:
            return False
        # 过滤明显导航项
        if t in {"首页", "政务公开", "政策", "政策文件", "文件库", "全部文件", "English"}:
            return False

        if region == "北京市":
            return "/zhengce/zhengcefagui/" in u and re.search(r"/t\d{8}_\d+\.html?$", u) is not None
        if region == "广东省":
            return "/zwgk/wjk/qbwj/" in u and "content/post_" in u
        if region == "上海市":
            return "/nw" in u and u.endswith(".html") and "/index.html" not in u
        if region == "四川省":
            return ("/10462/c103042/" in u or "/stt_" in u or "/10462/zfwjts/" in u) and (
                u.endswith(".shtml") or u.endswith(".html")
            )
        return True

    @staticmethod
    def _extract_title(soup):
        for sel in ["#ivs_title", ".Article-title-zw", ".header h1 p", ".contText p", "h1", "h2", ".title"]:
            n = soup.select_one(sel)
            if n:
                t = n.get_text(" ", strip=True)
                if t:
                    return PolicyCrawlerService._clean_title(t)
        for sel in ["meta[property='og:title']", "meta[name='Title']", "meta[name='ArticleTitle']"]:
            n = soup.select_one(sel)
            if n and n.get("content"):
                return PolicyCrawlerService._clean_title(n.get("content"))
        return ""

    @staticmethod
    def _clean_title(title):
        t = (title or "").strip()
        for sep in ("印发日期", "发布日期", "字号", "大 中 小"):
            if sep in t:
                t = t.split(sep)[0].strip(" -|，,")
        return t

    @staticmethod
    def _extract_main_text(soup):
        selectors = [
            "#ivs_content",
            "#mainText",
            ".trout-region-content",
            ".zw",
            ".contText",
            "article",
            ".Article_content",
            ".view",
        ]
        for sel in selectors:
            node = soup.select_one(sel)
            if node:
                txt = PolicyCrawlerService._clean_text(node.get_text("\n", strip=True))
                if len(txt) > 120:
                    return txt
        return PolicyCrawlerService._clean_text(soup.get_text("\n", strip=True))

    def _extract_publish_date(self, soup, text):
        selectors = [
            "#ivs_date",
            ".PBtime label",
            ".col.left[wzades*='发布日期'] span",
        ]
        for sel in selectors:
            n = soup.select_one(sel)
            if n:
                d = self._extract_date(n.get_text(" ", strip=True))
                if d:
                    return d
        return self._extract_date(text)

    @staticmethod
    def _tighten_sc_meta_field(val, kind: str):
        """四川省站点常把多栏元数据拼进同一段。发文字号：以首个「号/號」为结尾截取；索引号：取首行首段编号样式串。"""
        if val is None or (isinstance(val, str) and not val.strip()):
            return val
        v = str(val).replace("\r", "\n").strip()
        v = v.split("\n")[0].strip()
        for stop in (
            "主题分类",
            "主题词",
            "关键词",
            "发布日期",
            "发文日期",
            "发文单位",
            "发文机构",
            "公开日期",
            "效力状态",
            "有效性",
            "公文种类",
            "成文日期",
            "索引号",
            "发文字号",
        ):
            p = v.find(stop)
            if p > 0:
                v = v[:p].strip(" ：:\t　")
                break
        v = re.sub(r"\s+", " ", v).strip(" ：:：\t　")
        if kind == "doc_no":
            # 需求：发文字号以「号」字为结束（含该字），避免把后文主题词等吞进来
            idxs = [i for i in (v.find("号"), v.find("號")) if i != -1]
            if idxs:
                v = v[: min(idxs) + 1].strip()
            elif len(v) > 55:
                v = v[:55].rstrip("，,；; ")
        elif kind == "index_no":
            # 索引号：取行首一段字母数字与 /._-，避免中文正文整段被当成索引领
            m = re.match(r"^[:：\s]*([0-9A-Za-z][0-9A-Za-z./_\-]{2,42})", v)
            if m:
                v = m.group(1).strip()
            elif len(v) > 40:
                v = v[:40].rstrip("，,；; ")
        return v or None

    def _extract_meta_fields(self, soup, text):
        meta = {}
        all_text = self._clean_text(text)
        for out_key, labels in self.FIELD_LABELS.items():
            if out_key == "有效性":
                val = self._extract_validity(soup, text)
            else:
                val = self._extract_from_dom_by_labels(soup, labels) or self._extract_by_label(all_text, labels)
            if out_key in ("成文日期\\印发日期", "实施日期", "废止日期"):
                val = self._extract_date(val or "") or val
            meta[out_key] = val
        return meta

    @staticmethod
    def _extract_from_dom_by_labels(soup, labels):
        for lb in labels:
            for node in soup.find_all(string=re.compile(re.escape(lb))):
                txt = node.strip()
                if not txt:
                    continue
                parent = node.parent
                if parent:
                    nxt = parent.find_next("span")
                    if nxt:
                        v = nxt.get_text(" ", strip=True)
                        if v and v not in ("--", lb):
                            return v
                    if parent.next_sibling and hasattr(parent.next_sibling, "get_text"):
                        v2 = parent.next_sibling.get_text(" ", strip=True)
                        if v2 and v2 not in ("--", lb):
                            return v2
                m = re.search(rf"{re.escape(lb)}[：:\s]*([^\n\r;；]+)", txt)
                if m:
                    return m.group(1).strip()
        return None

    @staticmethod
    def _extract_date(text):
        m = re.search(r"(20\d{2}[-/.年]\d{1,2}[-/.月]\d{1,2})", text or "")
        if not m:
            return None
        d = m.group(1).replace("年", "-").replace("月", "-").replace("日", "")
        d = d.replace("/", "-").replace(".", "-")
        parts = d.split("-")
        if len(parts) == 3:
            return f"{parts[0]}-{int(parts[1]):02d}-{int(parts[2]):02d}"
        return None

    @staticmethod
    def _extract_by_label(text, labels):
        for lb in labels:
            label_pat = r"\s*".join(re.escape(ch) for ch in lb if ch.strip())
            m = re.search(rf"{label_pat}[：:\s]*([^\n\r;；]+)", text or "")
            if m:
                v = m.group(1).strip()
                if v in {"：", ":"}:
                    continue
                return v
        return None

    @staticmethod
    def _extract_attachments(soup, base_url):
        vals = []
        seen = set()
        for a in soup.select("a[href]"):
            txt = a.get_text(" ", strip=True)
            href = a.get("href", "").strip()
            if not href:
                continue
            full = urljoin(base_url, href)
            if any(x in txt for x in ("附件", ".pdf", ".doc", ".docx", ".xls", ".xlsx")) or href.lower().endswith(
                (".pdf", ".doc", ".docx", ".xls", ".xlsx")
            ):
                key = f"{txt}|{full}"
                if key in seen:
                    continue
                seen.add(key)
                vals.append(key)
        if not vals:
            return None
        return " ; ".join(vals[:20])

    @staticmethod
    def _extract_validity(soup, raw_text):
        # 1) DOM 优先：在“有效性/有 效 性”标签后找最近 span/label 的短值
        dom_val = PolicyCrawlerService._extract_from_dom_by_labels(soup, ["有效性", "有 效 性"])
        cleaned_dom = PolicyCrawlerService._normalize_validity(dom_val)
        if cleaned_dom:
            return cleaned_dom

        # 2) 文本兜底：只取短片段，避免吞入后续正文
        txt = raw_text or ""
        patterns = [
            r"(?:有\s*效\s*性)[：:\s]*([^\n\r]{1,12})",
            r"(?:有效状态|现行有效)[：:\s]*([^\n\r]{1,12})",
        ]
        for pat in patterns:
            m = re.search(pat, txt)
            if not m:
                continue
            v = PolicyCrawlerService._normalize_validity(m.group(1))
            if v:
                return v
        return None

    @staticmethod
    def _normalize_validity(v):
        if not v:
            return None
        s = re.sub(r"\s+", "", str(v))
        # 先做关键词识别
        if "现行有效" in s:
            return "现行有效"
        if "有效" in s and "无效" not in s:
            return "有效"
        if any(x in s for x in ("失效", "无效", "废止", "已废止")):
            return "失效"
        # 再做有限清洗并限制长度
        s = re.split(r"[，,。；;、\|]", s)[0]
        s = re.sub(r"[：:]", "", s).strip()
        if len(s) > 8:
            return None
        return s or None

    @staticmethod
    def _split_keywords(s):
        if not s:
            return []
        return [x.strip() for x in re.split(r"[,\s，]+", s) if x.strip()]

    @staticmethod
    def _contains_keywords(text, keywords):
        if not keywords:
            return True
        t = (text or "").lower()
        return any(k.lower() in t for k in keywords)

    @staticmethod
    def _clean_text(v):
        return re.sub(r"\s+", " ", (v or "")).strip()

    @staticmethod
    def _date_in_range(date_str, start, end):
        try:
            d = datetime.strptime(date_str, "%Y-%m-%d").date()
            s = datetime.strptime(start, "%Y-%m-%d").date()
            e = datetime.strptime(end, "%Y-%m-%d").date()
        except Exception:
            return True
        return s <= d <= e

    def _save_task(self, task_id, task_obj=None):
        with self._lock:
            if task_obj is not None:
                self._tasks[task_id] = task_obj
            task = self._tasks[task_id]
        if self._cache:
            self._cache.set_json(f"crawler:task:{task_id}:meta", task, ttl=self._cache_ttl)

    def _read_seq(self):
        if not self._seq_path.exists():
            return 0
        try:
            return int(self._seq_path.read_text(encoding="utf-8").strip() or "0")
        except Exception:
            return 0

    def _write_seq(self, v):
        self._seq_path.write_text(str(int(v)), encoding="utf-8")

    def _validate_payload(self, p):
        required = ["limit", "startDate", "endDate", "regions"]
        for k in required:
            if k not in p or p[k] in (None, "", []):
                return "请完善爬取参数"
        try:
            limit = int(p.get("limit"))
        except Exception:
            return "请输入有效正整数"
        if limit <= 0:
            return "请输入有效正整数"
        if limit > 1000:
            return "单次最大爬取数量需低于1000"
        if str(p.get("endDate")) < str(p.get("startDate")):
            return "结束时间需晚于起始时间"
        for rg in p.get("regions", []):
            if rg not in self.REGION_SOURCES:
                return f"不支持的地区: {rg}"
        return ""
