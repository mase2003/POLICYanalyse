"""磁盘路径：优先读环境变量（绝对路径），否则落在 get_deployment_root() 下相对路径。"""
from __future__ import annotations

import os
from pathlib import Path

from deployment_root import get_deployment_root


def data_path(env_key: str, *default_relative: str) -> Path:
    """
    若设置了 env_key，则使用该值（应为绝对路径或相对于进程 cwd 的路径）。
    未设置时：get_deployment_root() / default_relative[0] / ...
    default_relative 为空时，未设置 env 则返回 get_deployment_root()。
    """
    raw = (os.getenv(env_key) or "").strip().strip('"').strip("'")
    if raw:
        return Path(raw)
    root = get_deployment_root()
    if not default_relative:
        return root
    return root.joinpath(*default_relative)
