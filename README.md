# resume-tailor · 校招简历定制工作流

把一个 JD 变成一份**刚好一页 A4、版面饱满、关键词贴合**的简历 PDF，并自动记到投递台账里。
给应届生用，也能直接当作 Claude Code / WorkBuddy 的 Skill 调用。

> Tailor one résumé PDF per job description, verify it fits exactly one A4 page, and keep an application tracker in sync. Python + headless Chromium, no cloud, no personal data in the repo.

## 为什么不用现成的简历工具

大多数简历工具解决的是「排版」，这个项目解决的是**排版之后仍然会挂掉的那部分**：

- **版面靠实测，不靠肉眼**：解析 PDF 内容流算出「内容底部到页面底边的真实距离」，30-50pt 判定为刚好饱满，>60pt 自动提示补内容，2 页直接判失败
- **生成即校验**：一条命令完成「渲染 → 打印 → 校验页数/留白/禁用词/姓名」，不会出现「看起来是一页、打开是两页」
- **素材边界是硬约束**：所有经历只能来自 `config/profile.json` 的 `materials`，AI 没有素材就写不出东西，从机制上抑制编造
- **台账不会写坏**：追加脚本强制校验列数、序号顺延、备注字数，并保留文末锚点标题

## 效果

```
pages: 1 | bottom_margin_pt: 32.6 | forbidden_hits: none | has_name: True | RESULT: PASS
PDF: output/张三-简历-岗位-公司.pdf
```

（这是 `config/resume.example.json` 的真实输出，可以先跑一遍看效果。）

## 首次使用：填一次，之后只发 JD

```bash
git clone https://github.com/wangssc/resume-tailor.git && cd resume-tailor
pip install -r requirements.txt        # 唯一依赖是 pypdf
python scripts/setup.py                # 生成档案与台账模板 + 环境自检

# ① 导入你现有的简历（.docx / .pdf / .txt / .md 都行）
python scripts/import_resume.py 我的简历.docx
#    自动识别 姓名 / 电话 / 邮箱 / 学校 / 专业 / 学历 / 在校时间 / 求职意向
#    原文另存到 data/imported_resume.txt，留给下一步整理素材

# ② 把经历整理成结构化素材
#    让 AI 做：「把 data/imported_resume.txt 整理进 profile.json 的 materials」
#    或自己按「做什么 / 怎么做 / 结果」手填，并补全 education.courses 与 education.ability

# ③ 体检：通过就说明档案够用了
python scripts/check_profile.py
```

看到 `RESULT: 就绪` 之后，就进入日常状态 —— **只发 JD 就行**。

没有现成简历也能用：跳过 ①，把 `config/profile.example.json` 复制成 `config/profile.json` 手填即可。
想先看成品长什么样（完全不需要个人信息）：

```bash
python scripts/build_resume.py config/resume.example.json --profile config/profile.example.json
python scripts/make_pdf.py "output/resume_岗位-公司.html" --profile config/profile.example.json
```

`--profile` 指向示例档案即可，不需要填写任何真实信息。

`setup.py` 会顺带检查 Python 版本、`pypdf`、以及系统里的 Chromium 内核浏览器（Edge / Chrome / Chromium 任一即可）。

## 日常用法：只发 JD

每拿到一个 JD，就一句话：

> 帮我按这个 JD 定制简历（附 JD 截图 / 文字 / 公司+岗位名）

AI 会按 `SKILL.md` 走完整条链：查台账避免重复投 → 按 JD 重写经历 → 生成 PDF 并校验版面 → 给 HR 四项打分 → 追加台账行 → 给 1-2 条面试准备。**不需要再重复你的个人信息。**

**当作 Skill 用**（WorkBuddy / Claude Code）：把整个仓库放进 skills 目录即可，`SKILL.md` 就是它的作业手册。

```bash
git clone https://github.com/wangssc/resume-tailor.git ~/.workbuddy/skills/resume-tailor   # Windows: %USERPROFILE%\.workbuddy\skills\resume-tailor
```

**当作方法论读**：`SKILL.md` 讲流程与红线，`references/playbook.md` 讲怎么把经历改写成 JD 想要的样子，`references/scoring.md` 讲怎么给自己打分。这三份不依赖脚本，纯手写简历也能照用。

想完全手动也行，脚本就是全部：

```bash
# JSON -> HTML（版式已内置，你只写内容）
python scripts/build_resume.py output/jd-某公司.json

# HTML -> PDF + 自动校验
python scripts/make_pdf.py output/resume_岗位-公司.html
python scripts/make_pdf.py x.html --pdf "output/自定义名.pdf"   # 指定输出

# 台账追加（序号写 auto 自动取号）
python scripts/add_record.py "| auto | 公司 | 岗位 | 城市 | 行业 | **A** | 待投递 | 备注 |"
```

## 脚本一览

| 脚本 | 干什么 | 什么时候用 |
|---|---|---|
| `setup.py` | 生成 `profile.json` / 台账，自检 Python、pypdf、浏览器 | 装完第一次 |
| `import_resume.py` | 从 docx / pdf / txt 抽文本，识别基础字段写进档案 | 首次使用（可选，但省事） |
| `check_profile.py` | 档案体检，列出还缺什么 | 首次使用最后一步；改过档案后 |
| `build_resume.py` | JSON 配置 → 单页 A4 HTML | 每个 JD |
| `make_pdf.py` | HTML → PDF + 自动校验（一条命令） | 每个 JD |
| `verify_pdf.py` | 页数 / 底部留白 / 禁用词 / 姓名 | 被 `make_pdf.py` 调用，也可单独跑 |
| `add_record.py` | 台账安全追加（列数 / 序号 / 备注字数校验） | 每个 JD |
| `privacy_check.py` | 扫描个人信息泄露 | 推 GitHub 前 |

## 目录结构

```
resume-tailor/
├── SKILL.md                    # AI 作业手册：三步流、改写规则、打分、台账规则
├── config/
│   ├── profile.example.json    # 个人档案模板（setup.py 会复制成 profile.json）
│   └── resume.example.json     # 单份简历内容模板
├── data/
│   ├── ledger.example.md       # 投递台账模板（8 列）
│   └── imported_resume.txt     # import_resume.py 抽出的简历原文（已 gitignore）
├── references/
│   ├── playbook.md             # 同构挂靠公式、弱口径词表、版面经验、踩过的坑
│   └── scoring.md              # HR 四项打分细则与定级
├── scripts/
│   ├── common.py               # 配置加载、路径解析、浏览器定位
│   ├── setup.py                # 初始化 + 环境自检
│   ├── import_resume.py        # 导入原版简历，识别基础字段
│   ├── check_profile.py        # 档案体检
│   ├── build_resume.py         # JSON -> HTML
│   ├── make_pdf.py             # HTML -> PDF + 校验（一条命令）
│   ├── verify_pdf.py           # 页数 / 底部留白 / 禁用词 / 姓名
│   ├── add_record.py           # 台账安全追加
│   └── privacy_check.py        # 个人信息泄露扫描
└── output/                     # 生成的 HTML 与 PDF（已 gitignore）
```

## 配置说明（config/profile.json）

| 字段 | 说明 |
|---|---|
| `personal` | 姓名、一行标签（年龄/届别）、`contact`（多行联系方式）、学校、专业、学历、在校时间、照片路径 |
| `major_variants` | 同一专业在不同 JD 下的写法。JD 写「计算机类」就用工学口径，写「信息安全」就用方向口径，写「专业不限」就换一种表述 |
| `education` | 主修课程、专业能力两段默认文案（单份简历可覆盖） |
| `materials` | **素材库**：每段经历写清「做什么 / 怎么做 / 结果 / 遇到什么问题」，AI 只从这里取材 |
| `honors` | 荣誉证书一行 |
| `forbidden_words` | 校验时命中也算失败的词（默认拦截「年级排名」这类无法证实的表述） |
| `output_dir` / `pdf_prefix` / `ledger` / `note_limit` / `layout` | 路径与阈值，按需改 |

想给不同求职方向维护多套档案，就复制多份 profile，用环境变量切换：

```bash
export RESUME_PROFILE=config/profile-tech.json      # Windows: set RESUME_PROFILE=...
```

## 版面调优

`verify_pdf.py` 实测的底部留白是唯一判据：

| 留白 | 判定 | 怎么改 |
|---|---|---|
| 30-50pt | 刚好饱满 | 不动 |
| 50-60pt | 略空但可接受 | 补 1-2 行 |
| >60pt | 偏空 | 补 2-4 行（拆细条目 / 加协作维度 / 加课余自学） |
| <25pt | 偏挤 | 删 1-2 行 |
| 2 页 | 失败 | 先精简 1-3 行文字，**不要改样式、不要删板块** |

经验值：一页 A4 写满大约 1400-1600 字（含标点），换算成 16-22 条写得比较实的 bullet。判定只认 PDF 实测，不认观感。

## 隐私

**这个仓库本身不含任何人的个人信息** —— 没有姓名、手机号、邮箱、学校，也没有照片。示例里的人名是「张三」、电话是 `138-0000-0000`、邮箱是 `your.name@example.com`，全部是占位符。

**本项目的简历模板由使用者自行填写个人信息**：仓库只提供空白模板 `config/profile.example.json`，不包含任何可直接使用的 `config/profile.json`。首次使用请复制为 `config/profile.json`（或运行 `python scripts/setup.py` 自动生成），再把姓名、联系方式、学校专业、经历素材填成你自己的内容。填完后请确认 `config/profile.json` 仍处在 `.gitignore` 覆盖范围内，不要提交到你自己的仓库。

你的真实信息只会落在这几处，而且都在 `.gitignore` 里：

| 文件 | 内容 |
|---|---|
| `config/profile.json` | 姓名、联系方式、学校专业、经历素材 |
| `data/ledger.md` | 投递记录 |
| `data/imported_resume.txt` | 导入的简历原文 |
| `assets/photo.png` | 证件照 |
| `output/` | 生成的 HTML / PDF |

推 GitHub 前跑一遍体检：

```bash
python scripts/privacy_check.py         # 扫 git 跟踪的文件
python scripts/privacy_check.py --all   # 连未跟踪但会被提交的文件一起扫（.gitignore 里的自动跳过）
```

它会拦 11 位手机号、邮箱、18 位身份证号，以及 `profile.json` 里登记的姓名/学校有没有泄进示例文件。全流程本地运行：不联网、不上传简历、不依赖任何在线服务。

## 常见问题

**找不到浏览器 / 打印失败**
装 Edge、Chrome 或 Chromium 任一个即可；也可以显式指定：

```bash
export RESUME_BROWSER="/path/to/msedge"     # Windows: set RESUME_BROWSER=C:\...\msedge.exe
```

`make_pdf.py` 会先用新版 headless，失败自动回退旧参数。

**中文变成方框**
Linux 需装中文字体，如 `fonts-noto-cjk`。CSS 里已按 Microsoft YaHei → PingFang SC → Noto Sans CJK SC 的顺序回退。

**校验说留白 100pt 以上**
内容太少。别去改 CSS 撑版面，按上面「偏空」的补充优先序加内容 —— 改样式撑出来的留白，打印出来是「空得很有规律」。

**可以用在非应届场景吗**
可以。改 `personal.tagline`、`education` 和 `materials` 就行，脚本与流程与届别无关。

## License

MIT
