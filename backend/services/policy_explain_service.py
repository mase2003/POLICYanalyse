"""政策拆解：豆包对话、解析、写 CSV、导入 Neo4j（对齐 text1.py / policyexplain.csv）。"""
from __future__ import annotations

import csv
import os
import re
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

from runtime_paths import data_path
from services.doubao_chat_service import DoubaoChatService

# 与 text1.py 读取列一致
CSV_COLUMNS: list[str] = [
    "文件名称",
    "文件级别",
    "公文种类",
    "主题分类",
    "国家级文件名称",
    "市级省级文件名称",
    "区级县级文件名称",
    "责任机构或人",
    "具体事权",
    "具体面向对象",
    "必要条件",
    "管理标准",
    "审核过程",
    "施行时间",
    "继承关系",
    "联系",
    "关联内容",
    "变动",
    "推行和改革要求",
    "实施内容",
    "对应群体",
    "对应区域",
    "对应方向",
    "对应经济文化",
    "附件",
]

# 模型输出字段名（含提示词别名）→ CSV 列名
_KEY_ALIASES: dict[str, str] = {
    "市级省级文件名": "市级省级文件名称",
    "区级县级文件名": "区级县级文件名称",
}

SYSTEM_PROMPT = """# 政策文件智能拆解大模型提示词（新版·中文字段）
## 一、基础指令
你是专业的政策文件拆解助手，**严格按照指定字段、原文提取、不修改、不省略、不增删内容**，对用户提供的政策文件进行结构化拆解，仅提取文件中明确存在的信息，无对应信息则标注「无」。

## 二、核心拆解规则
1. **原文保真**：所有提取内容必须**完全照搬政策原文**，不得改写、缩写、扩写、遗漏关键信息。
2. **字段对应**：严格匹配下方指定字段，不新增、不删减字段，重复字段按要求保留。
3. **无信息标注**：文件中未提及的字段，统一填写「无」。
4. **格式规范**：按「字段名：提取内容」的格式清晰呈现，不保留正文内容。

## 三、待拆解字段清单（严格按顺序输出）
1. 文件名称
2. 文件级别
3. 公文种类
4. 主题分类
5. 责任机构或人
6. 具体事权
7. 具体面向对象
8. 必要条件
9. 管理标准
10. 审核过程
11. 施行时间
12. 国家级文件名称
13. 市级省级文件名
14. 区级县级文件名
15. 继承关系
16. 关联内容
17. 联系
18. 变动
19. 推行和改革要求
20. 实施内容
21. 对应群体
22. 对应区域
23. 对应方向
24. 对应经济文化
25. 附件

## 四、执行流程
1. 接收用户上传的政策文件全文。
2. 逐字段匹配原文信息，**纯原文提取**。
3. 按字段顺序完整输出拆解结果，确保无内容篡改、无信息遗漏。

### 示例输出格式（参考）
文件名称：北京市工业厂区（产业园区）适旅化改造指引
文件级别：市级非强制性、参考性、指导性技术文件
公文种类：通知
（其余字段按此格式依次输出）
"""


def _seconds_until_local_midnight() -> int:
    now = datetime.now()
    tomorrow = (now + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
    sec = int((tomorrow - now).total_seconds())
    return max(1, sec)


def _normalize_key(raw: str) -> str | None:
    t = (raw or "").strip()
    if not t:
        return None
    t = re.sub(r"^\d+\.\s*", "", t).strip()
    if t in _KEY_ALIASES:
        return _KEY_ALIASES[t]
    if t in CSV_COLUMNS:
        return t
    return None


def parse_llm_to_row(llm_text: str) -> dict[str, str]:
    """从模型输出中解析各字段；未识别列填「无」。"""
    out: dict[str, str] = {k: "无" for k in CSV_COLUMNS}
    if not (llm_text or "").strip():
        return out
    lines = llm_text.replace("\r\n", "\n").split("\n")
    current: str | None = None
    buf: list[str] = []

    def flush() -> None:
        nonlocal current, buf
        if current and current in out:
            val = "\n".join(buf).strip()
            out[current] = val if val else "无"
        current = None
        buf = []

    for line in lines:
        m = re.match(r"^(?:\d+\.\s*)?(.+?)[：:]\s*(.*)$", line.strip())
        if m:
            nk = _normalize_key(m.group(1))
            rest = (m.group(2) or "").strip()
            if nk:
                flush()
                current = nk
                buf = [rest] if rest else []
                continue
        if current:
            buf.append(line)
    flush()
    return out


def _normalize_single_file_level(value: Any) -> str:
    """
    规范「文件级别」为单值。
    - 多值时优先返回包含「市级」的项；
    - 若无市级则返回第一项；
    - 空值统一返回「无」。
    """
    text = str(value or "").strip()
    if not text or text in ("无", "无。"):
        return "无"

    # 按常见分隔符切分，避免一条政策返回多个级别。
    parts = [p.strip() for p in re.split(r"[，,、；;|\n]+", text) if p.strip()]
    if not parts:
        return "无"

    for part in parts:
        if "市级" in part:
            return part
    return parts[0]


def append_policy_explain_csv(path: Path, row: dict[str, str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    write_header = not path.exists() or path.stat().st_size == 0
    with path.open("a", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=CSV_COLUMNS, extrasaction="ignore")
        if write_header:
            w.writeheader()
        w.writerow({k: (row.get(k) or "无") for k in CSV_COLUMNS})


_memory_daily: dict[str, tuple[date, int]] = {}


def check_and_touch_rate_limit_ip(
    redis_cache: Any,
    client_ip: str,
    daily_limit: int,
    unlimited: bool,
) -> tuple[bool, int, str]:
    """
    返回 (allowed, current_count, message)。
    unlimited 为 True 时不计数。
    """
    if unlimited or daily_limit <= 0:
        return True, 0, ""

    if redis_cache and redis_cache.enabled and redis_cache.ping():
        key = f"policy_explain:daily:{client_ip}:{date.today().strftime('%Y%m%d')}"
        n = redis_cache.incr(key)
        if n is not None:
            if n == 1:
                redis_cache.expire(key, _seconds_until_local_midnight())
            if n > daily_limit:
                return False, n, f"本 IP 每日限用 {daily_limit} 次政策拆解，请次日 0 点后再试。"
            return True, n, ""

    # 内存回退（单进程有效）
    d = date.today()
    prev = _memory_daily.get(client_ip)
    if not prev or prev[0] != d:
        _memory_daily[client_ip] = (d, 0)
    c = _memory_daily[client_ip][1] + 1
    _memory_daily[client_ip] = (d, c)
    if c > daily_limit:
        return False, c, f"本 IP 每日限用 {daily_limit} 次政策拆解，请次日 0 点后再试。"
    return True, c, ""


def client_ip_from_request(req) -> str:
    xff = (req.headers.get("X-Forwarded-For") or "").split(",")[0].strip()
    if xff:
        return xff
    return (req.remote_addr or "").strip() or "unknown"


def is_unlimited_ip(ip: str) -> bool:
    ip = (ip or "").strip()
    if ip in ("127.0.0.1", "::1", "localhost"):
        return True
    raw = os.getenv("POLICY_EXPLAIN_UNLIMITED_IPS", "")
    parts = [x.strip() for x in raw.split(",") if x.strip()]
    return ip in parts


def default_csv_path() -> Path:
    p = os.getenv("POLICY_EXPLAIN_CSV_PATH", "").strip()
    if p:
        return Path(p)
    return Path("你的政策拆解文件本机地址")


def build_user_message(policy_title: str, policy_body: str) -> str:
    title = (policy_title or "").strip() or "（无标题）"
    body = (policy_body or "").strip() or "（无正文）"
    max_chars = max(5000, int(os.getenv("POLICY_EXPLAIN_MAX_POLICY_CHARS", "120000")))
    if len(body) > max_chars:
        body = body[:max_chars] + "\n\n（正文过长已截断至前 " + str(max_chars) + " 字）"
    return f"以下为待拆解的政策信息。\n\n【标题】\n{title}\n\n【正文】\n{body}"


def run_deconstruct(
    neo_service: Any,
    detail: dict[str, Any],
    node_id: str,
) -> dict[str, Any]:
    """调用豆包、写 CSV、导入图库。detail 为 get_policy_detail 返回值。"""
    chat = DoubaoChatService()
    if not chat.is_configured():
        raise ValueError("未配置豆包对话（ARK_API_KEY + ARK_CHAT_MODEL）。")

    d = detail.get("detail") or {}
    title = (
        str(d.get("标题") or "").strip()
        or str((detail.get("properties") or {}).get("文件名称") or "").strip()
        or str((detail.get("properties") or {}).get("name") or "").strip()
    )
    body = str(d.get("正文") or "").strip()

    user_msg = build_user_message(title, body)
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_msg},
    ]
    raw = chat.chat(messages, temperature=0.1)
    row = parse_llm_to_row(raw)
    if row.get("文件名称") in (None, "", "无"):
        row["文件名称"] = title or "无"
    row["文件级别"] = _normalize_single_file_level(row.get("文件级别"))

    csv_path = default_csv_path()
    append_policy_explain_csv(csv_path, row)

    neo_service.import_policy_explain_graph(node_id, row, raw)

    return {
        "ok": True,
        "nodeId": str(node_id),
        "csvPath": str(csv_path.resolve()),
        "rawText": raw,
        "row": row,
    }
