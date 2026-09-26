# scholar-doi 学术文献下载工具

输入 DOI 查询并下载 **开放获取(OA)** 学术文献的 Python 工具。
支持单个 / 批量 DOI、元数据导出（CSV/JSON），并内置一个可选的本地网页版界面。兼容 **Python 3.8+**，核心功能仅依赖标准库。

---

## ✨ 功能

- **DOI 解析**：支持直接输入 DOI，或 `https://doi.org/...` 形式的链接，自动规范化为标准 DOI。
- **元数据查询**：通过 [Crossref](https://www.crossref.org/) 获取标题、作者、期刊、年份、出版社等元数据。
- **开放获取(OA)定位**：通过 [Unpaywall](https://unpaywall.org/) 查询该 DOI 是否有合法 OA 版本，并尝试获取 PDF 直链。
- **PDF 下载**：优先下载 PDF 直链；若落地页是 HTML，自动从页内提取 PDF 链接再下载；支持跟随重定向、多候选地址顺序尝试。
- **批量下载**：从文件或文本一次性处理多个 DOI。
- **元数据导出**：导出为 CSV / JSON。
- **网页版(可选)**：基于 Flask 的本地图形界面。

---

## 📦 安装

```bash
pip install -r requirements.txt   # 安装 flask即可
```

---

## 🚀 命令行用法

所有命令都可通过邮箱参数 `-e`（Unpaywall 需要邮箱用于溯源）或环境变量 `SCHOLAR_EMAIL` 提供邮箱；未指定时程序会交互式询问。

### 1. 下载单个 DOI

```bash
python -m scholar_doi.cli doi 10.1021/jacs.1c07042 -o ./papers -e you@example.com
```

### 2. 批量下载

```bash
# 从文件读取（每行一个 DOI）
python -m scholar_doi.cli batch dois.txt -o ./papers -e you@example.com

# 或直接传入以空格/逗号分隔的 DOI 文本
python -m scholar_doi.cli batch "10.1000/a 10.1000/b 10.1000/c" -o ./papers

# 同时导出元数据到 CSV
python -m scholar_doi.cli batch dois.txt -o ./papers --meta manifest.csv --failed-list failed.csv
```

### 3. 启动网页版

```bash
pip install flask
python -m scholar_doi.cli web --port 5000 -e you@example.com
# 浏览器打开 http://127.0.0.1:5000
```

### 4. 其他入口

```bash
python -m scholar_doi      # 等价于 python -m scholar_doi.cli
python scholar_doi_cli.py  # 等价入口
python -m scholar_doi.cli --help   # 查看帮助
```

---

## 🧠 合规与版权说明（重要）

- 本工具 **仅下载开放获取(OA)** 的合法文献，默认通过 Crossref + Unpaywall 等开放接口查询，**不采集、不绕过付费墙**。
- **付费墙限制**：JACS、Nature 等订阅期刊的非 OA 付费文章，Unpaywall 会标记为 `非 OA`，本工具不会也无法获取其正文 PDF（除非你有机构订阅并通过浏览器访问）。
- **反爬限制**：部分出版社（如 **MDPI、ACS、PMC**）对脚本直接下载设有 Cloudflare / JS 验证等反爬机制。即使文章是 OA，脚本也可能被 403 拦截。此时请用浏览器打开工具输出的落地页下载。
- 原始可下载内容版权归属各出版社，请遵守相应许可（CC、订阅协议等），仅用于个人学习与合法研究。

---

## 🗂️ 项目结构

```
scholar-doi/
├── scholar_doi/
│   ├── __init__.py    # 版本与公开接口
│   ├── doi.py         # DOI 校验 / 规范化
│   ├── api.py         # Crossref / Unpaywall 查询封装
│   ├── download.py    # PDF 下载(重定向、HTML 提取 PDF 链接、多候选)
│   ├── export.py      # CSV / JSON 导出
│   ├── cli.py         # 命令行入口
│   ├── web.py         # Flask 网页版(可选)
│   └── __main__.py    # python -m scholar_doi
├── scholar_doi_cli.py # 便捷入口脚本
├── requirements.txt   # flask(可选)
└── README.md
```

---

## 📇 元数据导出字段

| 元数据导出字段 |
|:---:|
| DOI |
| 标题 |
| 作者 |
| 期刊 |
| 年份 |
| OA状态 |
| PDF地址(如果有的话) |

---

## 🛠️ 常见问题

**Q: 提示"请输入邮箱(必填)"？**
A: Unpaywall 要求提供邮箱。用 `-e 你的邮箱` 传入，或设置环境变量 `export SCHOLAR_EMAIL=you@example.com`。

**Q: 下载返回 403？**
A: 该出版源有反爬(如 MDPI、ACS、PMC)。请用浏览器打开工具提供的落地页/PDF 地址手动下载。

**Q: 提示"未找到记录"？**
A: DOI 可能输入有误，或该文章没有注册在 Crossref。可先到 doi.org 验证 DOI 是否有效。

**Q: `10.3390/xxx`（MDPI）为什么有时下不了？**
A: MDPI 是 OA 期刊，但其网站设有 Cloudflare 反爬，脚本直接访问 PDF 常返回 403。请用浏览器访问。

---

## 🔒 隐私

工具仅向 Crossref / Unpaywall 发送 DOI 与你提供的邮箱，不上传任何其他个人数据。

## 开源协议

MIT

```txt
Copyright 2026 Sen

Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated documentation files (the "Software"), to deal in the Software without restriction, including without limitation the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software, and to permit persons to whom the Software is furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
```
