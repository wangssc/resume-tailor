#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""PDF 校验：页数 / 底部留白 / 禁用词 / 姓名是否渲染成功。

用法:
  python scripts/verify_pdf.py output/xxx.pdf
  python scripts/verify_pdf.py output/xxx.pdf --name 张三

退出码: 0 = PASS 或仅告警；1 = FAIL。
"""
import argparse
import sys

from common import die, forbidden_words, layout, load_profile, personal

try:
    from pypdf import PdfReader
    from pypdf.generic import ContentStream
except ImportError:  # noqa: BLE001
    die("缺少依赖 pypdf，请先运行：pip install -r requirements.txt")

PAGE_H = 841.9  # A4 高度（pt）


def bottom_margin(page, reader):
    """内容最低点距页面底边的距离（pt）。

    Edge/Chrome 打印时坐标以 0.75 的缩放写入 Tm，故 y_page = 841.9 - max_y * 0.75。
    """
    try:
        cs = ContentStream(page.get_contents(), reader)
    except Exception:  # noqa: BLE001
        return -1.0
    max_y = 0.0
    for operands, op in cs.operations:
        if op == b"Tm":
            try:
                max_y = max(max_y, float(operands[5]))
            except (ValueError, TypeError, IndexError):
                continue
    return round(PAGE_H - max_y * 0.75, 1)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("pdf")
    ap.add_argument("--profile", default=None)
    ap.add_argument("--name", default=None, help="覆盖 profile 里的姓名校验")
    args = ap.parse_args()

    profile = load_profile(args.profile)
    lay = layout(profile)
    expect_name = args.name or personal(profile)["name"]
    bad = forbidden_words(profile)

    reader = PdfReader(args.pdf)
    pages = len(reader.pages)
    text = "".join((p.extract_text() or "") for p in reader.pages)
    margin = bottom_margin(reader.pages[-1], reader) if pages else -1.0
    hits = [w for w in bad if w in text]
    name_ok = expect_name in text

    print("pages: %d" % pages)
    print("bottom_margin_pt: %s" % margin)
    print("forbidden_hits: %s" % (hits if hits else "none"))
    print("has_name: %s" % name_ok)

    if pages != 1:
        print("RESULT: FAIL -> 页数为 %d，需要精简 1-3 行文字后重新打印（不要改样式、不要删板块）"
              % pages)
        return 1
    if hits:
        print("RESULT: FAIL -> 出现禁用词 %s，必须移除后重新打印" % "、".join(hits))
        return 1
    if not name_ok:
        print("RESULT: FAIL -> 正文未找到姓名「%s」，检查 profile 或字体渲染" % expect_name)
        return 1

    if margin < lay["min_margin_pt"]:
        print("RESULT: WARN -> 底部留白仅 %.1fpt，版面偏挤，建议删 1-2 行" % margin)
        return 0
    if margin <= lay["ideal_max_pt"]:
        print("RESULT: PASS")
        return 0
    if margin <= lay["sparse_pt"]:
        print("RESULT: PASS(偏空) -> 留白 %.1fpt，建议补 2-4 行内容填满" % margin)
        return 0
    print("RESULT: PASS(严重偏空) -> 留白 %.1fpt，建议补 4-6 行内容" % margin)
    return 0


if __name__ == "__main__":
    sys.exit(main())
