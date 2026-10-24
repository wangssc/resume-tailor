#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""档案体检：确认 config/profile.json 已经填到「可以开始接 JD」的程度。

用法:
  python scripts/check_profile.py
  python scripts/check_profile.py --profile config/profile-tech.json

退出码 0 = 可用；1 = 还缺东西（会列出缺什么、怎么补）。
"""
import argparse
import json
import re
import sys
from pathlib import Path

from common import DEFAULT_PROFILE, ROOT, die

PLACEHOLDER_TEXT = ("负责什么业务", "用了什么方法", "有哪些可量化", "遇到过什么问题",
                    "对接了多少外部单位", "统筹过什么规模", "跟过的课程", "读过的行业报告",
                    "能力主张", "专业方向一句话", "目标行业", "行业名", "岗位名",
                    "XX 公司", "某某大学", "某某学科竞赛")


def load(path):
    p = Path(path).expanduser()
    if not p.is_absolute():
        p = (ROOT / p).resolve()
    if not p.exists():
        die("找不到 %s，先运行 python scripts/setup.py" % p)
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001
        die("JSON 解析失败：%s" % exc)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--profile", default=None)
    args = ap.parse_args()

    path = args.profile or DEFAULT_PROFILE
    prof = load(path)
    person = prof.get("personal") or {}
    edu = prof.get("education") or {}

    problems, warns = [], []

    # 1. 基本信息
    name = str(person.get("name") or "").strip()
    if not name or name in ("张三", "姓名", "Your Name"):
        problems.append("personal.name 还是占位符 —— 填上真实姓名")

    contact = [str(c) for c in (person.get("contact") or [])]
    phone_digits = " ".join(re.sub(r"\D", "", c) for c in contact)
    if not re.search(r"1[3-9]\d{9}", phone_digits):
        problems.append("personal.contact 里没有可用的手机号（11 位，1 开头）")

    if not any("@" in c for c in contact):
        problems.append("personal.contact 里没有邮箱")

    if not str(person.get("school") or "").strip() or str(person.get("school")).startswith("某某"):
        problems.append("personal.school 还是占位符 —— 填上学校全称")
    if not str(person.get("major") or "").strip():
        problems.append("personal.major 为空 —— 填专业名，或写进 major_variants")
    if not str(person.get("edu_date") or "").strip():
        warns.append("personal.edu_date 为空（教育背景的在校时间会留白）")

    # 2. 教育与能力
    courses = str(edu.get("courses") or "")
    ability = str(edu.get("ability") or "")
    if len(courses) < 10:
        problems.append("education.courses 太短 —— 列 5-7 门与求职方向相关的课")
    if len(ability) < 20:
        problems.append("education.ability 太短 —— 写 2-3 句：方向 + 工具 + 一个亮点")
    for field, val in (("courses", courses), ("ability", ability)):
        if any(t in val for t in PLACEHOLDER_TEXT):
            problems.append("education.%s 还留着模板占位文字，删掉换成你自己的" % field)

    # 3. 素材库
    mats = prof.get("materials") or []
    real = []
    for m in mats:
        raw = " ".join(str(x) for x in (m.get("raw") or []))
        if len(raw) < 20:
            continue
        if any(t in raw for t in PLACEHOLDER_TEXT):
            warns.append("materials「%s」还是模板示例，换成真实经历后删掉" % m.get("name", "?"))
            continue
        real.append(m)
    if len(real) < 2:
        problems.append("materials 里至少要有 2 段真实经历（做了什么/怎么做/结果如何），"
                        "现在可用的是 %d 段" % len(real))

    # 4. 荣誉与禁用词
    if len(str(prof.get("honors") or "")) < 4:
        warns.append("honors 为空 —— 有奖项/证书就写上，没有可以写「暂无」")

    imported = prof.get("_imported") or {}
    if imported and len(real) < 2:
        warns.append("检测到已导入原版简历（%s），但素材库还没整理 —— "
                     "让 AI 把 %s 整理进 materials"
                     % (imported.get("source", "?"), imported.get("text_file", "原文")))

    # 输出
    print("== 档案体检：%s ==" % Path(path).as_posix())
    if problems:
        print("\n[必须补]")
        for i, p in enumerate(problems, 1):
            print("  %d. %s" % (i, p))
    if warns:
        print("\n[建议补]")
        for w in warns:
            print("  - %s" % w)

    if problems:
        print("\nRESULT: 未就绪 —— 补完上面 %d 项再开始投递" % len(problems))
        return 1
    print("\nRESULT: 就绪 —— 之后只发 JD 即可，AI 会按 SKILL.md 全自动处理")
    return 0


if __name__ == "__main__":
    sys.exit(main())
