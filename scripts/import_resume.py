#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""导入你现有的简历（docx / pdf / txt / md），自动识别基础字段并写进 config/profile.json。

用法:
  python scripts/import_resume.py 我的简历.docx
  python scripts/import_resume.py 我的简历.pdf --dry        # 只看识别结果，不落盘
  python scripts/import_resume.py 我的简历.txt --force      # 覆盖已填字段

做两件事:
  1. 把简历原文抽成纯文本存到 data/imported_resume.txt（给 AI 结构化用的原料）
  2. 用正则识别 姓名/电话/邮箱/学校/专业/学历/在校时间/求职意向，补进 profile.json
     只填空字段，已有内容不动（除非 --force）

识别不出来的（尤其是经历段落）不用管 —— 下一步让 AI 把原文整理进 materials 就行。
"""
import argparse
import datetime
import io
import json
import re
import unicodedata
import zipfile
from pathlib import Path

from common import ROOT, die

PROFILE = ROOT / "config" / "profile.json"
PROFILE_TPL = ROOT / "config" / "profile.example.json"
RAW = ROOT / "data" / "imported_resume.txt"

PLACEHOLDER_NAME = {"张三", "姓名", "your name", "yourname"}
PLACEHOLDER_PHONE = {"13800000000", "138-0000-0000"}
PLACEHOLDER_MAIL = {"your.name@example.com", "you@example.com"}


# ---------- 文本抽取 ----------

def from_docx(path):
    """docx 是 zip，正文在 word/document.xml —— 用标准库解析，不引入 python-docx。"""
    with zipfile.ZipFile(path) as z:
        names = [n for n in z.namelist() if n == "word/document.xml"]
        if not names:
            die("这个 .docx 里找不到正文（可能是旧版 .doc 改名而来），"
                "请另存为 .docx 或 .txt 再试")
        xml = z.read("word/document.xml").decode("utf-8", "ignore")
    xml = (xml.replace("</w:p>", "\n")
              .replace("<w:br/>", "\n")
              .replace("<w:tab/>", "\t"))
    text = re.sub(r"<[^>]+>", "", xml)
    for a, b in (("&amp;", "&"), ("&lt;", "<"), ("&gt;", ">"),
                 ("&quot;", '"'), ("&apos;", "'"), ("&nbsp;", " ")):
        text = text.replace(a, b)
    return text


def from_pdf(path):
    try:
        from pypdf import PdfReader
    except ImportError:  # noqa: BLE001
        die("读取 PDF 需要 pypdf：pip install -r requirements.txt")
    reader = PdfReader(str(path))
    return "\n".join((p.extract_text() or "") for p in reader.pages)


def from_text(path):
    for enc in ("utf-8-sig", "utf-8", "gb18030", "big5"):
        try:
            return io.open(str(path), encoding=enc).read()
        except UnicodeDecodeError:
            continue
    die("文本编码认不出来，请另存为 UTF-8 再试")


def extract(path: Path):
    ext = path.suffix.lower()
    if ext in (".docx", ".doc"):
        return from_docx(path)
    if ext == ".pdf":
        return from_pdf(path)
    if ext in (".txt", ".md", ".markdown", ".csv"):
        return from_text(path)
    die("暂不支持 %s，请用 .docx / .pdf / .txt / .md" % ext)


def normalize(text):
    text = unicodedata.normalize("NFKC", text)          # 全角数字/空格 -> 半角
    text = text.replace("\u3000", " ").replace("\xa0", " ")
    lines = [re.sub(r"[ \t]+", " ", l).strip() for l in text.splitlines()]
    return "\n".join(l for l in lines if l)


# ---------- 字段识别 ----------

def find_phone(text):
    for m in re.finditer(r"1[3-9]\d(?:[\s-]?)\d{4}(?:[\s-]?)\d{4}", text):
        digits = re.sub(r"\D", "", m.group())
        if len(digits) == 11 and digits not in PLACEHOLDER_PHONE:
            return digits
    return None


def find_email(text):
    for m in re.finditer(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+", text):
        mail = m.group().strip(".")
        local = mail.split("@")[0].lower()
        if mail.lower() in PLACEHOLDER_MAIL or local in ("your.name", "you", "name", "email"):
            continue
        return mail
    return None


def find_name(lines):
    for line in lines[:12]:
        m = re.match(r"^(?:姓\s*名|Name)[:：]\s*(\S{2,10})$", line, re.I)
        if m:
            return m.group(1)
    if lines:
        first = lines[0]
        # 首行通常是姓名：2-4 个汉字 / 2-20 个英文词，且不含数字与常见标题词
        if re.fullmatch(r"[\u4e00-\u9fa5]{2,4}", first):
            return first
        if re.fullmatch(r"[A-Za-z][A-Za-z .'-]{1,29}", first) and len(first.split()) <= 4:
            return first.title()
    return None


SCHOOL_RE = re.compile(r"[\u4e00-\u9fa5]{2,20}(?:大学|学院|学校|中学)(?:（[^）]*）|\([^)]*\))?")


def find_school(text):
    for line in text.splitlines():
        if re.search(r"大学|学院|学校", line) and not re.search(r"奖|证书|竞赛", line):
            m = SCHOOL_RE.search(line)
            if m:
                return m.group()
    return None


MAJOR_RE = re.compile(r"专\s*业[:：]\s*([\u4e00-\u9fa5A-Za-z（）()·\s]{2,30})")
DEGREES = ["博士研究生", "硕士研究生", "本科", "研究生", "大专", "专科", "高中"]


def find_major(text):
    m = MAJOR_RE.search(text)
    if m:
        return m.group(1).strip()
    # 退一步：学校同一行里 | 或 空格 分隔的片段中，找不含学校/学历关键词的那段
    for line in text.splitlines():
        if re.search(r"大学|学院", line):
            for seg in re.split(r"[|｜/、　]|\s{2,}", line):
                seg = seg.strip()
                if 2 <= len(seg) <= 24 and not re.search(
                        r"大学|学院|本科|硕士|博士|专科|20\d{2}", seg):
                    return seg
    return None


def find_degree(text):
    for d in DEGREES:
        if d in text:
            return "本科" if d in ("本科", "研究生") else d
    return None


def find_edu_date(text):
    """匹配「2023.09 - 2027.06」这类在校时间，取第一组。"""
    pat = (r"(20\d{2})\s*[.\-/年]\s*(\d{1,2})?\s*[月]?\s*[—\-~至到]+\s*"
           r"(20\d{2})\s*[.\-/年]\s*(\d{1,2})?")
    m = re.search(pat, text)
    if not m:
        return None
    y1, m1, y2, m2 = m.group(1), m.group(2) or "09", m.group(3), m.group(4) or "06"
    return "%s.%02d - %s.%02d" % (y1, int(m1), y2, int(m2))


def find_intent(text):
    m = re.search(r"求职意向[:：]?\s*(.{2,60})", text)
    return m.group(1).strip() if m else None


def detect(text):
    lines = text.splitlines()
    return {
        "name": find_name(lines),
        "phone": find_phone(text),
        "email": find_email(text),
        "school": find_school(text),
        "major": find_major(text),
        "degree": find_degree(text),
        "edu_date": find_edu_date(text),
        "_intent_hint": find_intent(text),
    }


# ---------- 写回 profile ----------

def blank_profile():
    if PROFILE.exists():
        return json.loads(PROFILE.read_text(encoding="utf-8"))
    return load_template()


def load_template():
    if PROFILE_TPL.exists():
        return json.loads(PROFILE_TPL.read_text(encoding="utf-8"))
    die("找不到 config/profile.example.json，无法生成档案")


def is_blank(val, placeholders):
    if not val:
        return True
    v = str(val).strip()
    return v in placeholders or v.startswith("某某") or v.startswith("your.")


PHONE_IN_LINE = re.compile(r"1[3-9]\d{9}")


def apply(profile, found, force=False):
    tpl = load_template()
    tpl_p = tpl.get("personal") or {}
    tpl_contact = [str(c) for c in (tpl_p.get("contact") or [])]
    p = profile.setdefault("personal", {})
    changed = []

    def put(key, value, placeholders=()):
        """只填空字段；模板原样的默认值也算空（否则导入会被模板值挡住）。"""
        if not value:
            return
        cur = p.get(key)
        cur_is_tpl = str(tpl_p.get(key) or "").strip() == str(cur or "").strip()
        if force or cur_is_tpl or is_blank(cur, placeholders):
            if cur != value:
                p[key] = value
                changed.append(key)

    put("name", found["name"], PLACEHOLDER_NAME)
    put("school", found["school"])
    put("major", found["major"])
    put("degree", found["degree"])
    put("edu_date", found["edu_date"])

    # 联系方式：拆成 电话行 / 邮箱行 / 其他行（如「可全职到岗」）重新拼
    contact = [str(c) for c in (p.get("contact") or [])]
    old_phones = [c for c in contact
                  if PHONE_IN_LINE.search(re.sub(r"\D", "", c))
                  and re.sub(r"\D", "", c) not in PLACEHOLDER_PHONE]
    old_mails = [c for c in contact if "@" in c and c not in tpl_contact
                 and c.split("@")[0].split("：")[-1].lower() not in ("your.name", "you")]
    others = [c for c in contact
              if "@" not in c and not re.search(r"\d{7,}", re.sub(r"\D", "", c))]

    phone_val = found["phone"] or (re.sub(r"\D", "", old_phones[0]) if old_phones else None)
    mail_val = found["email"] or (old_mails[0].split("：")[-1] if old_mails else None)

    def line(prefix, val, old_list):
        if not val:
            return None
        return old_list[0] if old_list and val in old_list[0] else "%s：%s" % (prefix, val)

    new_contact = [x for x in (line("电话", phone_val, old_phones),
                               line("邮箱", mail_val, old_mails)) if x] + others
    if new_contact != contact and any(x not in tpl_contact for x in new_contact):
        p["contact"] = new_contact
        if phone_val and phone_val not in " ".join(tpl_contact):
            changed.append("contact.phone")
        if mail_val and mail_val not in " ".join(tpl_contact):
            changed.append("contact.email")

    profile["_imported"] = {
        "source": RAW.name,
        "text_file": str(RAW.relative_to(ROOT)).replace("\\", "/"),
        "lines": found.get("_lines", 0),
        "at": datetime.date.today().isoformat(),
        "intent_hint": found.get("_intent_hint"),
    }
    return changed



def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("resume", help="原版简历路径（.docx / .pdf / .txt / .md）")
    ap.add_argument("--dry", action="store_true", help="只打印识别结果，不写文件")
    ap.add_argument("--force", action="store_true", help="覆盖已填字段")
    args = ap.parse_args()

    src = Path(args.resume).expanduser()
    if not src.is_absolute():
        src = (Path.cwd() / src).resolve()
    if not src.exists():
        die("简历文件不存在：%s" % src)

    text = normalize(extract(src))
    if len(text) < 30:
        die("抽出来的文字太少（%d 字）。如果是扫描版 PDF，请先转成文字版或 .docx" % len(text))

    found = detect(text)
    found["_lines"] = len(text.splitlines())

    print("== 识别结果 ==")
    for k in ("name", "phone", "email", "school", "major", "degree", "edu_date", "_intent_hint"):
        print("  %-12s %s" % (k, found.get(k) or "（未识别，稍后手填或让 AI 补）"))
    print("  原文 %d 行 / %d 字" % (found["_lines"], len(text)))

    if args.dry:
        print("\n--dry：未写入任何文件")
        print("\n原文前 20 行预览：")
        for l in text.splitlines()[:20]:
            print("  " + l)
        return

    RAW.parent.mkdir(parents=True, exist_ok=True)
    io.open(str(RAW), "w", encoding="utf-8").write(text)

    profile = blank_profile()
    changed = apply(profile, found, args.force)
    io.open(str(PROFILE), "w", encoding="utf-8").write(
        json.dumps(profile, ensure_ascii=False, indent=2) + "\n")

    print("\n已保存原文 -> %s" % RAW.relative_to(ROOT))
    print("已更新档案 -> %s" % PROFILE.relative_to(ROOT))
    print("补进去的字段：%s" % (("、".join(changed)) if changed else "无（档案里已有值）"))
    print("""
== 下一步 ==
让 AI 把原文整理成结构化素材，或自己动手：
  1. 把 data/imported_resume.txt 的每段经历，按「做什么 / 怎么做 / 结果」填进
     config/profile.json 的 materials
  2. 补全 education.courses 与 education.ability
  3. python scripts/check_profile.py   # 确认档案够用了再开始接 JD
""")


if __name__ == "__main__":
    main()
