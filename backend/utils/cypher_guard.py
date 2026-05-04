import re

# 用户提交的 Cypher：仅允许读路径，禁止写/管理/过程调用（避免拖垮库）
_MAX_LEN = int(__import__("os").getenv("NEO4J_MAX_CYPHER_LEN", "8000"))

_FORBIDDEN = re.compile(
    r"\b("
    r"create|merge|delete|detach|remove|set|drop|foreach|"
    r"grant|deny|revoke|alter|admin|use|"
    r"load\s+csv|using\s+periodic\s+commit|"
    r"call"
    r")\b",
    re.IGNORECASE | re.DOTALL,
)

# 必须以这些关键字之一开头（去掉注释与首尾空白后）
_ALLOWED_START = re.compile(
    r"^(match|optional\s+match|with|unwind|return)\b",
    re.IGNORECASE | re.DOTALL,
)


def strip_cypher_comments(text: str) -> str:
    if not text:
        return ""
    s = text
    # /* ... */
    s = re.sub(r"/\*.*?\*/", " ", s, flags=re.DOTALL)
    out_lines = []
    for line in s.splitlines():
        if "//" in line:
            line = line[: line.index("//")]
        out_lines.append(line)
    return " ".join(out_lines)


def validate_user_cypher(cypher: str) -> str:
    raw = (cypher or "").strip()
    if not raw:
        raise ValueError("Cypher 不能为空")
    if len(raw) > _MAX_LEN:
        raise ValueError(f"Cypher 过长（>{_MAX_LEN} 字符）")

    cleaned = strip_cypher_comments(raw).strip()
    if not cleaned:
        raise ValueError("Cypher 在去掉注释后为空")

    if _FORBIDDEN.search(cleaned):
        raise ValueError("仅允许只读查询：禁止 CREATE/MERGE/DELETE/SET/CALL 等语句")

    if not _ALLOWED_START.match(cleaned):
        raise ValueError("查询必须以 MATCH、OPTIONAL MATCH、WITH、UNWIND 或 RETURN 开头")

    return raw


def internal_scan_limit() -> int:
    return min(
        50000,
        max(1000, int(__import__("os").getenv("NEO4J_INTERNAL_SCAN_LIMIT", "5000"))),
    )
