#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""安全追加一条投递台账记录（自动保留锚点标题、校验列数 / 序号 / 备注长度）。

用法:
  python scripts/add_record.py '| auto | 某公司 | 某岗位 | 城市 | 行业 | **A** | 待投递 | 备注 |'
  python scripts/add_record.py '...' --check-only     # 只校验不写入
  python scripts/add_record.py '...' --ledger other.md

约定:
- 列数由 profile.columns 决定（默认 8 列 = 9 个竖线）
- 第一列写 auto（或留空）时自动取「当前最大序号 + 1」
- 备注字数上限 profile.note_limit（默认 80，不含「简历：xxx.pdf」部分）
- 新行插入到表格最后一行的下面，不依赖文档里其他标题的位置
"""
import argparse
import io
import re
import sys

from common import die, ledger_path, load_profile

DEFAULT_ANCHOR = "## 进度枚举值"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("line")
    ap.add_argument("--profile", default=None)
    ap.add_argument("--ledger", default=None)
    ap.add_argument("--check-only", action="store_true")
    args = ap.parse_args()

    profile = load_profile(args.profile)
    path = ledger_path(profile, args.ledger)
    anchor = profile.get("ledger_anchor") or DEFAULT_ANCHOR
    cols = int(profile.get("columns") or 8)
    note_limit = int(profile.get("note_limit") or 80)

    line = args.line.strip()
    if not line.startswith("|") or not line.endswith("|"):
        die("该行必须以 | 开头并以 | 结尾")
    if line.count("|") != cols + 1:
        die("列数错误：应为 %d 列（%d 个 |），当前 %d 个" % (cols, cols + 1, line.count("|")))
    if "｜" in line:
        die("含有全角竖线「｜」，会破坏表格，请改为句号或逗号")
    if "（对标" in line or "(对标" in line:
        die("含有「对标」类内部注释标记，台账与简历正文都不允许出现")

    text = io.open(str(path), encoding="utf-8").read()
    ids = [int(m.group(1)) for m in re.finditer(r"^\|\s*(\d+)\s*\|", text, re.M)]

    m = re.match(r"^\|\s*(\d+)\s*\|", line)
    if m:
        new_id = int(m.group(1))
        if new_id in ids:
            die("序号 %d 已存在，禁止重复" % new_id)
        if ids and new_id < max(ids):
            die("序号 %d 小于当前最大 %d，应顺延；或第一列写 auto 让脚本自动取号"
                % (new_id, max(ids)))
    else:
        new_id = (max(ids) + 1) if ids else 1
        line = re.sub(r"^\|\s*[^|]*\|", "| %d |" % new_id, line, count=1)

    cells = line.split("|")
    note = cells[-2].strip()
    body = note.split("简历：")[0]
    if len(body) > note_limit:
        print("警告：备注正文 %d 字，超过建议上限 %d 字，请精简"
              % (len(body), note_limit), file=sys.stderr)

    # 插入位置 = 表格最后一行之后（不依赖文档里其他标题的位置）
    rows = [i for i, ln in enumerate(text.splitlines()) if ln.startswith("|")]
    if not rows:
        die("台账里找不到表格（以 | 开头的行）")
    if anchor and anchor not in text:
        print("警告：台账缺少锚点标题「%s」，请确认文件结构完整" % anchor, file=sys.stderr)

    if args.check_only:
        print("OK 校验通过（未写入）：序号 %d，备注 %d 字" % (new_id, len(body)))
        return

    lines = text.splitlines()
    lines.insert(rows[-1] + 1, line)
    io.open(str(path), "w", encoding="utf-8").write("\n".join(lines) + "\n")
    print("已写入序号 %d（台账现有 %d 条记录，最大序号 %d）"
          % (new_id, len(ids) + 1, new_id))


if __name__ == "__main__":
    main()
