#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""隐私体检：确认仓库里没有任何个人信息 —— 推 GitHub 前跑一遍。

用法:
  python scripts/privacy_check.py            # 只看被 git 跟踪的文件
  python scripts/privacy_check.py --all      # 连未跟踪的文件（除 output/.git）一起查

检什么:
  - 11 位手机号（排除 138-0000-0000 这类占位）
  - 邮箱（排除 example.com / example.org）
  - 18 位身份证号
  - 真实姓名/学校是否泄进了示例文件（对 profile.json 里登记的姓名做比对）

退出码 0 = 干净；1 = 发现疑似个人信息（会给出文件与脱敏片段）。
"""
import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

from common import DEFAULT_PROFILE, ROOT

SKIP_DIRS = {".git", "output", "__pycache__", "node_modules", ".venv", "venv"}
BINARY_EXT = {".png", ".jpg", ".jpeg", ".pdf", ".docx", ".doc", ".zip", ".gz",
              ".ico", ".gif", ".woff", ".woff2", ".ttf"}

PHONE_RE = re.compile(r"(?<!\d)1[3-9]\d[\s-]?\d{4}[\s-]?\d{4}(?!\d)")
MAIL_RE = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
ID_RE = re.compile(r"(?<!\d)\d{17}[\dXx](?!\d)")

SAFE_PHONE = {"13800000000", "138-0000-0000"}
SAFE_MAIL_DOMAIN = {"example.com", "example.org", "example.net", "test.com"}


def git_files(include_untracked=False):
    args = ["git", "-C", str(ROOT), "ls-files", "--cached"]
    if include_untracked:
        # 已跟踪 + 未跟踪但没被 .gitignore 排除的 —— 这些才是「可能被提交」的东西
        args += ["--others", "--exclude-standard"]
    try:
        out = subprocess.run(args, capture_output=True, text=True, encoding="utf-8")
        if out.returncode == 0:
            files = [f for f in out.stdout.splitlines() if f.strip()]
            if files:
                return [ROOT / f for f in files]
    except FileNotFoundError:
        pass
    return None


def walk_files():
    files = []
    for p in ROOT.rglob("*"):
        if p.is_dir() or p.suffix.lower() in BINARY_EXT:
            continue
        if any(part in SKIP_DIRS for part in p.parts):
            continue
        files.append(p)
    return files


TEMPLATE_MARKERS = ("XX", "xx", "示例", "某某", "占位", "岗位名", "公司名", "你的")
PROFILE_TPL = ROOT / "config" / "profile.example.json"


def identity_terms():
    """从 profile.json 取真实姓名/学校/经历主体，用于反查示例文件里有没有泄露。"""
    p = Path(DEFAULT_PROFILE)
    if not p.exists():
        return []
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return []
    tpl_text = ""
    if PROFILE_TPL.exists():
        tpl_text = PROFILE_TPL.read_text(encoding="utf-8", errors="ignore")

    person = data.get("personal") or {}
    name = str(person.get("name") or "").strip()
    terms = []
    if 2 <= len(name) <= 20 and name not in ("张三", "姓名", "Your Name"):
        terms.append(name)

    raw_terms = [str(person.get("school") or "")]
    for m in data.get("materials") or []:
        raw_terms.append(str(m.get("name") or "").split("|")[0])

    for t in raw_terms:
        t = t.strip()
        if len(t) < 3:
            continue
        if any(mark in t for mark in TEMPLATE_MARKERS):
            continue          # 模板占位文字不算个人信息
        if tpl_text and t in tpl_text:
            continue          # 模板里本来就有的文字，不是个人信息
        terms.append(t)
    return terms


def mask(s):
    s = s.strip()
    if len(s) <= 6:
        return s[:2] + "***"
    return s[:3] + "***" + s[-2:]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--all", action="store_true", help="连未跟踪文件也查")
    args = ap.parse_args()

    files = git_files(include_untracked=args.all)
    scope = "git 跟踪的文件"
    if files is None:
        files, scope = walk_files(), "工作目录全部文件（排除 output/.git）"
    elif args.all:
        scope = "git 跟踪 + 未跟踪但会被提交的文件（.gitignore 里的已排除）"

    terms = identity_terms()
    hits = []

    for f in files:
        if f.suffix.lower() in BINARY_EXT or not f.exists():
            continue
        try:
            text = f.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        rel = f.relative_to(ROOT).as_posix()

        for m in PHONE_RE.finditer(text):
            if m.group() not in SAFE_PHONE:
                hits.append((rel, "手机号", mask(m.group())))
        for m in MAIL_RE.finditer(text):
            if m.group().split("@")[-1].lower() not in SAFE_MAIL_DOMAIN:
                hits.append((rel, "邮箱", mask(m.group())))
        for m in ID_RE.finditer(text):
            hits.append((rel, "身份证号", mask(m.group())))
        for t in terms:
            if t in text:
                hits.append((rel, "真实姓名/单位「%s」" % mask(t), "…"))

    print("== 隐私体检 ==")
    print("扫描范围：%s，共 %d 个文件" % (scope, len(files)))
    print("比对词典：%s" % ("、".join(mask(t) for t in terms) if terms else "（profile.json 尚未填写）"))

    if not hits:
        print("\nRESULT: 干净 —— 没有手机号 / 邮箱 / 身份证 / 真实姓名泄露")
        print("提示：config/profile.json、data/ledger.md、data/imported_resume.txt、"
              "assets/photo.png 都已写进 .gitignore，不会被提交。")
        return 0

    print("\n发现 %d 处疑似个人信息：" % len(hits))
    for rel, kind, sample in hits:
        print("  %-34s %-14s %s" % (rel, kind, sample))
    print("\nRESULT: 不干净 —— 先处理上面这些文件，再推 GitHub")
    return 1


if __name__ == "__main__":
    sys.exit(main())
