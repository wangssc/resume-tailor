#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""JSON 配置 -> 单页 A4 简历 HTML（版式与配色已内置，只需写内容）。

用法:
  python scripts/build_resume.py config/resume.example.json
  python scripts/build_resume.py my.json --dry          # 只校验，不写文件
  python scripts/build_resume.py my.json --profile config/professional.json

配置里 **文本** 会渲染为深色高亮；<b> 标签原样透传。
个人信息（姓名/联系方式/学校/专业）来自 config/profile.json，
本脚本与仓库内不含任何个人数据。
"""
import argparse
import json
import os
import re

from common import (die, file_uri, load_profile, output_dir, pdf_prefix,
                    personal, resolve)

CSS = """
  @page { size: A4; margin: 0; }
  * { margin: 0; padding: 0; box-sizing: border-box; }
  html, body { width: 210mm; }
  body {
    font-family: "Microsoft YaHei", "PingFang SC", "Hiragino Sans GB",
                 "Noto Sans CJK SC", "Source Han Sans SC", "WenQuanYi Micro Hei", sans-serif;
    font-size: 9.5pt; color: #1B1B1B; line-height: 1.40;
    padding: 10mm 14mm 8.5mm 14mm; background: #fff;
  }
  .header { position: relative; padding-bottom: 9pt; border-bottom: 1pt solid #12314F; }
  .name { font-size: 23pt; font-weight: bold; color: #12314F; letter-spacing: 1pt; }
  .sub { font-size: 9.5pt; color: #57616B; margin-top: 3pt; }
  .contact { position: absolute; right: 32mm; top: 14pt; text-align: right;
             font-size: 9.5pt; color: #1B1B1B; line-height: 1.7; }
  .contact.no-photo { right: 0; }
  .photo { position: absolute; right: 0; top: 0; width: 23.8mm; height: 33.4mm; object-fit: cover; }
  .sec { background: #EEEEF6; border-left: 2pt solid #12314F;
         padding: 3.4pt 8pt; margin-top: 7pt; margin-bottom: 4pt; }
  .sec span { font-size: 10.5pt; font-weight: bold; color: #12314F; letter-spacing: 1pt; }
  .row { display: flex; justify-content: space-between; align-items: baseline; }
  .row .t { font-weight: bold; color: #12314F; }
  .row .d { color: #57616B; font-size: 9.5pt; }
  .intent { font-size: 9.5pt; }
  ul { list-style: none; margin: 2pt 0 0 0; }
  li { padding-left: 10pt; position: relative; margin-bottom: 1.8pt; text-align: justify; }
  li::before { content: "\\2022"; position: absolute; left: 1pt; color: #1B1B1B; }
  li b { color: #1B1B1B; }
  .hl { color: #12314F; font-weight: bold; }
"""

LABELS = {
    "intent": "求职意向",
    "education": "教育背景",
    "practice": "实践经历",
    "honors": "荣誉证书",
    "self": "自我评价",
}


def hl(text):
    """**文本** -> 深色高亮 span。"""
    return re.sub(r"\*\*(.+?)\*\*", r'<span class="hl">\1</span>', text)


def esc(text):
    return (text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))


def resolve_major(cfg, profile):
    """专业写法优先级：cfg.major > cfg.major_variant > profile.personal.major"""
    if cfg.get("major"):
        return cfg["major"]
    variant = cfg.get("major_variant")
    if variant:
        table = profile.get("major_variants") or {}
        if variant not in table:
            die("major_variant「%s」不在 profile.major_variants 中，可选：%s"
                % (variant, "、".join(table) or "（空）"))
        return table[variant]
    return personal(profile).get("major", "")


def build(cfg, profile):
    p = personal(profile)
    edu = profile.get("education") or {}

    name = cfg.get("name") or p["name"]
    tagline = cfg.get("tagline", p.get("tagline", ""))
    contact = cfg.get("contact") or p.get("contact") or []
    if not isinstance(contact, list):
        die("配置里的 contact 必须是字符串数组，每项一行")

    photo_raw = cfg.get("photo", p.get("photo") or "")
    photo = resolve(photo_raw) if photo_raw else None
    has_photo = bool(photo and photo.exists())
    if photo_raw and not has_photo:
        print("提示：照片文件不存在，已跳过 -> %s" % photo)

    major = resolve_major(cfg, profile)
    school = cfg.get("school") or p.get("school", "")
    degree = cfg.get("degree") or p.get("degree", "")
    edu_date = cfg.get("edu_date") or p.get("edu_date", "")

    courses = cfg.get("courses") or edu.get("courses") or ""
    ability = cfg.get("ability") or edu.get("ability") or ""
    honors = cfg.get("honors") or profile.get("honors") or ""

    for key, val in (("courses", courses), ("ability", ability), ("honors", honors)):
        if not str(val).strip():
            die("缺少内容：%s（配置与 profile 里都没有）" % key)

    parts = [
        "<!DOCTYPE html>",
        '<html lang="zh-CN">',
        "<head>",
        '<meta charset="UTF-8">',
        "<title>%s - 简历</title>" % esc(name),
        "<style>" + CSS + "</style>",
        "</head>",
        "<body>",
        "",
        '  <div class="header">',
        '    <div class="name">%s</div>' % esc(name),
    ]
    if tagline:
        parts.append('    <div class="sub">%s</div>' % esc(tagline))
    cls = "contact" if has_photo else "contact no-photo"
    lines = "<br>".join(esc(x) for x in contact)
    parts.append('    <div class="%s">%s</div>' % (cls, lines))
    if has_photo:
        parts.append('    <img class="photo" src="%s" alt="">' % file_uri(photo))
    parts += ["  </div>", ""]

    parts += ['  <div class="sec"><span>%s</span></div>' % LABELS["intent"],
              '  <div class="intent">%s</div>' % hl(cfg["intent"]), ""]

    row = "　|　".join(x for x in (esc(school), esc(major), esc(degree)) if x)
    parts += ['  <div class="sec"><span>%s</span></div>' % LABELS["education"],
              '  <div class="row"><span class="t">%s</span><span class="d">%s</span></div>'
              % (row, esc(edu_date)),
              "  <ul>",
              "    <li><b>主修课程：</b>%s</li>" % esc(courses),
              "    <li><b>专业能力：</b>%s</li>" % hl(ability),
              "  </ul>", ""]

    parts.append('  <div class="sec"><span>%s</span></div>' % LABELS["practice"])
    for i, sec in enumerate(cfg["sections"]):
        mt = ' style="margin-top:4pt"' if i else ""
        parts.append('  <div class="row"%s><span class="t">%s</span><span class="d">%s</span></div>'
                     % (mt, sec["title"], sec.get("date", "")))
        parts.append("  <ul>")
        for b in sec["bullets"]:
            parts.append("    <li>%s</li>" % hl(b))
        parts += ["  </ul>", ""]

    parts += ['  <div class="sec"><span>%s</span></div>' % LABELS["honors"],
              "  <ul>", "    <li>%s</li>" % hl(honors), "  </ul>", "",
              '  <div class="sec"><span>%s</span></div>' % LABELS["self"],
              "  <ul>"]
    for s in cfg["self"]:
        parts.append("    <li>%s</li>" % hl(s))
    parts += ["  </ul>", "", "</body>", "</html>", ""]

    return "\n".join(parts)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("config", help="简历内容 JSON 路径")
    ap.add_argument("--profile", default=None, help="档案配置，默认 config/profile.json")
    ap.add_argument("--dry", action="store_true", help="只校验不写文件")
    args = ap.parse_args()

    profile = load_profile(args.profile)
    cfg = json.loads(open(args.config, encoding="utf-8").read())

    for k in ("intent", "sections", "self"):
        if k not in cfg:
            die("配置缺少必填字段：%s" % k)
    if len(cfg["self"]) != 3:
        die("self（自我评价）必须是 3 条，当前 %d 条" % len(cfg["self"]))
    if not cfg["sections"]:
        die("sections（实践经历）不能为空")

    html = build(cfg, profile)
    n_li = html.count("<li>")

    if args.dry:
        print("OK 自检通过：%d 个 bullet，%d 字符" % (n_li, len(html)))
        print("参考：13-16 个 bullet 通常对应底部留白 30-50pt")
        return

    out = cfg.get("out")
    if out:
        out = resolve(out)
    else:
        slug = cfg.get("slug") or "custom"
        out = output_dir(profile) / ("resume_%s.html" % slug)

    os.makedirs(os.path.dirname(str(out)), exist_ok=True)
    with open(str(out), "w", encoding="utf-8") as fh:
        fh.write(html)
    print("已生成 %s（%d 个 bullet）" % (out, n_li))
    print("下一步：python scripts/make_pdf.py \"%s\"" % out)


if __name__ == "__main__":
    main()
