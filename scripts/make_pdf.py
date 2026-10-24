#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""HTML -> 单页 A4 PDF，并自动调用 verify_pdf.py 校验（打印 + 校验一条命令）。

用法:
  python scripts/make_pdf.py output/resume_jd.html
  python scripts/make_pdf.py output/resume_jd.html --pdf "output/张三-简历-岗位-公司.pdf"
  python scripts/make_pdf.py x.html --profile config/professional.json

默认命名规则：output/<pdf_prefix>-<slug>.pdf
其中 slug 取 HTML 文件名去掉 resume_ 前缀；pdf_prefix 来自 profile（默认 {name}-简历）。
"""
import argparse
import os
import subprocess
import sys

from common import (die, file_uri, find_browser, load_profile, output_dir,
                    pdf_prefix)


def slug_of(html_path):
    base = os.path.splitext(os.path.basename(html_path))[0]
    return base[len("resume_"):] if base.startswith("resume_") else base


def render(browser, html_path, pdf_path):
    """用 Chromium 内核浏览器无头打印 PDF。新版 headless 失败时回退旧参数。"""
    url = file_uri(html_path)
    variants = [
        ["--headless=new", "--disable-gpu", "--no-pdf-header-footer",
         "--virtual-time-budget=3000", "--print-to-pdf=" + pdf_path, url],
        ["--headless", "--disable-gpu", "--no-pdf-header-footer",
         "--virtual-time-budget=3000", "--print-to-pdf=" + pdf_path, url],
    ]
    for flags in variants:
        if os.path.exists(pdf_path):
            os.remove(pdf_path)
        subprocess.run([browser] + flags, capture_output=True)
        if os.path.exists(pdf_path) and os.path.getsize(pdf_path) > 0:
            return True
    return False


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("html")
    ap.add_argument("--pdf", default=None)
    ap.add_argument("--profile", default=None)
    args = ap.parse_args()

    profile = load_profile(args.profile)
    html = args.html if os.path.isabs(args.html) else os.path.abspath(args.html)
    if not os.path.exists(html):
        die("HTML 不存在：%s" % html)

    if args.pdf:
        pdf = args.pdf if os.path.isabs(args.pdf) else os.path.abspath(args.pdf)
    else:
        pdf = str(output_dir(profile) / ("%s-%s.pdf" % (pdf_prefix(profile), slug_of(html))))
    os.makedirs(os.path.dirname(pdf) or ".", exist_ok=True)

    browser = find_browser()
    if not render(browser, html, pdf):
        die("PDF 生成失败。\n浏览器：%s\n请确认该浏览器可正常运行，"
            "或用 RESUME_BROWSER 指定其他 Chromium 内核浏览器。" % browser)

    verify = os.path.join(os.path.dirname(os.path.abspath(__file__)), "verify_pdf.py")
    cmd = [sys.executable, verify, pdf]
    if args.profile:
        cmd += ["--profile", args.profile]
    r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")

    keys = ("pages", "bottom", "forbidden", "has_name", "RESULT")
    summary = " | ".join(l.strip() for l in r.stdout.splitlines() if any(k in l for k in keys))
    print(summary)
    print("PDF: %s" % pdf)
    if "PASS" not in summary:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
