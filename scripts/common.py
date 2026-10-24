# -*- coding: utf-8 -*-
"""公共模块：配置加载、路径解析、浏览器定位。

所有脚本都从 config/profile.json 读取个人信息与路径，因此脚本本身不含任何个人数据。
可用环境变量 RESUME_PROFILE 指向别的配置文件（方便一人多套档案）。
"""
import json
import os
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_PROFILE = ROOT / "config" / "profile.json"

DEFAULT_FORBIDDEN = ["前10%", "前 10%", "年级排名", "专业成绩排名", "前 10 %"]
DEFAULT_LAYOUT = {
    "min_margin_pt": 25,     # 低于此值判定拥挤
    "ideal_min_pt": 30,      # 理想留白下界
    "ideal_max_pt": 50,      # 理想留白上界
    "sparse_pt": 60,         # 高于此值判定偏空
}


def die(msg):
    raise SystemExit("[resume-tailor] %s" % msg)


def load_profile(path=None):
    """读取 profile.json。相对路径以项目根目录为基准。"""
    p = Path(path or os.environ.get("RESUME_PROFILE") or DEFAULT_PROFILE).expanduser()
    if not p.is_absolute():
        p = (ROOT / p).resolve()
    if not p.exists():
        die("找不到配置文件 %s\n首次使用请先运行：python scripts/setup.py" % p)
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001
        die("配置文件解析失败：%s\n路径：%s" % (exc, p))
    data["_path"] = str(p)
    return data


def resolve(path_str, base=None):
    """相对路径 -> 绝对路径（默认基准为项目根目录）。"""
    if not path_str:
        return None
    p = Path(str(path_str)).expanduser()
    return p if p.is_absolute() else ((base or ROOT) / p).resolve()


def personal(profile):
    p = profile.get("personal") or {}
    if not p.get("name"):
        die("config/profile.json 缺少 personal.name")
    return p


def output_dir(profile):
    d = resolve(profile.get("output_dir") or "output")
    d.mkdir(parents=True, exist_ok=True)
    return d


def pdf_prefix(profile):
    """PDF 文件名前缀，支持 {name} 占位。"""
    tpl = profile.get("pdf_prefix") or "{name}-简历"
    return tpl.format(name=personal(profile).get("name", "简历"))


def forbidden_words(profile):
    return list(profile.get("forbidden_words") or DEFAULT_FORBIDDEN)


def layout(profile):
    cfg = dict(DEFAULT_LAYOUT)
    cfg.update(profile.get("layout") or {})
    return cfg


def ledger_path(profile, override=None):
    p = resolve(override or profile.get("ledger") or "data/ledger.md")
    if not p.exists():
        die("找不到台账文件 %s\n可运行 python scripts/setup.py 生成模板" % p)
    return p


def file_uri(path):
    """绝对路径 -> file:/// URI（Windows 反斜杠转正斜杠并转义）。"""
    from urllib.parse import quote
    return "file:///" + quote(str(path).replace("\\", "/"))


BROWSER_CANDIDATES = {
    "win32": [
        r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
    ],
    "darwin": [
        "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
        "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
        "/Applications/Chromium.app/Contents/MacOS/Chromium",
    ],
}


def find_browser():
    """定位一个 Chromium 内核浏览器（Edge / Chrome / Chromium）。

    优先级：环境变量 RESUME_BROWSER > 系统默认安装路径 > PATH 中的可执行文件。
    """
    env = os.environ.get("RESUME_BROWSER")
    if env:
        p = Path(env).expanduser()
        if p.exists():
            return str(p)
        die("RESUME_BROWSER 指向的文件不存在：%s" % env)

    for cand in BROWSER_CANDIDATES.get(sys.platform, []):
        if Path(cand).exists():
            return cand

    for name in ("msedge", "google-chrome", "chromium", "chromium-browser",
                 "microsoft-edge", "chrome"):
        found = shutil.which(name)
        if found:
            return found

    die("未找到 Edge / Chrome / Chromium。\n"
        "请安装其一，或设置环境变量 RESUME_BROWSER 指向浏览器可执行文件。")
