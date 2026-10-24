#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""一键初始化 + 环境自检。

用法:
  python scripts/setup.py            # 从示例生成 profile.json / ledger.md 并自检
  python scripts/setup.py --force    # 覆盖已有的 profile.json（会先备份）

做的四件事:
  1. 生成 config/profile.json（个人档案）与 data/ledger.md（投递台账）
  2. 检查 Python 版本、pypdf、Chromium 内核浏览器
  3. 创建 output/ 目录
  4. 打印下一步该做什么
"""
import argparse
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PROFILE = ROOT / "config" / "profile.json"
PROFILE_TPL = ROOT / "config" / "profile.example.json"
LEDGER = ROOT / "data" / "ledger.md"
LEDGER_TPL = ROOT / "data" / "ledger.example.md"

OK, NO, WARN = "[OK]  ", "[FAIL]", "[WARN]"


def copy_tpl(src, dst, force=False):
    if dst.exists() and not force:
        print("%s %s 已存在，跳过" % (WARN, dst.relative_to(ROOT)))
        return False
    if dst.exists():
        backup = dst.with_suffix(dst.suffix + ".bak")
        shutil.move(str(dst), str(backup))
        print("%s 已备份旧文件 -> %s" % (WARN, backup.name))
    shutil.copyfile(str(src), str(dst))
    print("%s 已生成 %s" % (OK, dst.relative_to(ROOT)))
    return True


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--force", action="store_true", help="覆盖已有 profile.json（先备份）")
    args = ap.parse_args()

    print("== resume-tailor 初始化 ==\n")

    print("[1/3] 生成配置文件")
    copy_tpl(PROFILE_TPL, PROFILE, args.force)
    copy_tpl(LEDGER_TPL, LEDGER)

    print("\n[2/3] 环境自检")
    print("%s Python %d.%d.%d" % (OK, *sys.version_info[:3]))
    if sys.version_info < (3, 8):
        print("%s 需要 Python 3.8 及以上" % NO)

    try:
        import pypdf  # noqa: F401
        print("%s pypdf %s" % (OK, getattr(pypdf, "__version__", "?")))
    except ImportError:
        print("%s 缺少 pypdf，请运行：pip install -r requirements.txt" % NO)

    sys.path.insert(0, str(ROOT / "scripts"))
    try:
        from common import find_browser
        print("%s 浏览器：%s" % (OK, find_browser()))
    except SystemExit as exc:
        print("%s %s" % (NO, str(exc).replace("[resume-tailor] ", "")))

    print("\n[3/3] 目录")
    out = ROOT / "output"
    out.mkdir(exist_ok=True)
    print("%s output/ 就绪" % OK)

    print("""
== 首次使用：只填这一次 ==

方案 A（推荐）导入你现有的简历，让脚本先把基础字段认出来：
    python scripts/import_resume.py 我的简历.docx      # 也支持 .pdf / .txt / .md
    python scripts/import_resume.py 我的简历.docx --dry # 只看识别结果

方案 B 直接手填：
    打开 config/profile.json，把姓名、联系方式、学校专业写进 personal

填完之后：
    1. 把 data/imported_resume.txt（或你原来的简历）里的每段经历，按
       「做什么 / 怎么做 / 结果」填进 config/profile.json 的 materials
    2. 补全 education.courses（5-7 门课）与 education.ability（2-3 句）
    3. 简历照片可选，放 assets/photo.png
    4. python scripts/check_profile.py    # 体检通过就说明档案够用了

== 之后每次只要发 JD ==

    「帮我按这个 JD 定制简历」+ JD 截图 / 文字 / 公司+岗位名

AI 会自己走完：查台账去重 → 按 JD 重写经历 → 生成并校验 PDF → 四项打分 → 台账入库。

推 GitHub 前跑一遍：python scripts/privacy_check.py
""")


if __name__ == "__main__":
    main()
