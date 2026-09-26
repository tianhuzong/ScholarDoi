"""本地 Flask 网页版界面(可选依赖 flask)。

启动:
    python -m scholar_doi.cli web --port 5000 -e you@example.com
"""
import os

try:
    from flask import Flask, request, send_file

    _HAS_FLASK = True
except ImportError:  # pragma: no cover
    Flask = None
    request = None
    send_file = None
    _HAS_FLASK = False

from .api import resolve_doi, ApiError
from .doi import normalize_doi
from .download import download_first, sanitize_filename
from .export import export_records

_DEFAULT_DOWNLOAD_DIR = os.path.join(".", "downloads")


def _download_dir(base):
    path = os.path.abspath(base)
    os.makedirs(path, exist_ok=True)
    return path


def create_app(email=None):
    """创建 Flask 应用(便于测试)。"""
    if not _HAS_FLASK:
        raise RuntimeError("需要安装 flask: pip install flask")

    app = Flask(__name__)
    app.config["EMAIL"] = email or os.environ.get("SCHOLAR_EMAIL") or ""
    app.config["DOWNLOAD_DIR"] = _download_dir(_DEFAULT_DOWNLOAD_DIR)

    html_head = """
    <!doctype html>
    <html lang="zh-CN"><head><meta charset="utf-8">
    <meta name="viewport" content="width=device-width,initial-scale=1">
    <title>scholar-doi 文献下载</title>
    <style>
      body{font-family:-apple-system,'Segoe UI',Roboto,sans-serif;max-width:760px;
           margin:40px auto;padding:0 20px;color:#222;line-height:1.6}
      h1{font-size:1.6em;border-bottom:2px solid #4a7dff}
      input[type=text]{width:70%;padding:10px;font-size:1em;border:1px solid #ccc;
           border-radius:6px}
      button{padding:10px 22px;font-size:1em;border:none;border-radius:6px;
           background:#2563eb;color:#fff;cursor:pointer}
      button:hover{background:#1d4ed8}
      .box{background:#f8fafc;border:1px solid #e2e8f0;border-radius:8px;
           padding:16px;margin-top:16px}
      .info{display:flex;justify-content:space-between;flex-wrap:wrap}
      a{color:#2563eb;text-decoration:none}
      table{width:100%;border-collapse:collapse;margin-top:12px}
      th,td{border:1px solid #e2e8f0;padding:8px;text-align:left;font-size:.92em}
      .err{color:#dc2626}
      .ok{color:#16a34a}
      textarea{width:100%;height:90px;padding:10px;font-size:.95em;
           border:1px solid #ccc;border-radius:6px;font-family:monospace}
    </style></head><body>
    """

    def _page(body):
        return html_head + body + "</body></html>"

    @app.route("/", methods=["GET"])
    def index():
        return _page("""
        <h1>📄 scholar-doi 文献下载</h1>
        <p>输入 DOI 查询开放获取(OA)文献并下载 PDF。</p>
        <form action="/download" method="post">
          <input type="text" name="doi" placeholder="例如 10.1038/s41586-021-03970-8"
                 required>
          <button type="submit">查询并下载</button>
        </form>
        <form action="/batch" method="post" style="margin-top:24px">
          <h2>批量下载</h2>
          <textarea name="dois" placeholder="每行一个 DOI"></textarea>
          <br><button type="submit">批量下载并导出 CSV</button>
        </form>
        <p class="box" style="margin-top:24px">说明：本工具通过 Crossref 与
        Unpaywall 等开放接口查询，仅下载<strong>开放获取(OA)</strong>的合法
        PDF。付费墙文章可能无法获取。</p>
        """)

    @app.route("/download", methods=["POST"])
    def download():
        doi = normalize_doi(request.form.get("doi", ""))
        if not doi:
            return _page('<h1>📄</h1><p class="err">无效的 DOI</p>'
                         '<p><a href="/">返回</a></p>')
        try:
            rec = resolve_doi(
                doi,
                email=app.config["EMAIL"] or None,
            )
        except ApiError as e:
            return _page('<h1>📄</h1><p class="err">查询失败: %s</p>'
                         '<p><a href="/">返回</a></p>' % e)
        if rec is None:
            return _page('<h1>📄</h1><p class="err">未找到该 DOI 记录</p>'
                         '<p><a href="/">返回</a></p>')

        saved = None
        if rec["pdf_url"] or rec.get("pdf_urls"):
            urls = rec.get("pdf_urls") or []
            if rec["pdf_url"] not in urls:
                urls.insert(0, rec["pdf_url"])
            try:
                saved = download_first(
                    urls,
                    app.config["DOWNLOAD_DIR"],
                    fallback_name=sanitize_filename(
                        rec.get("journal") or rec.get("title") or "paper"),
                )
            except Exception:  # noqa: BLE001
                saved = None
        body = "<h1>✅ 查询结果</h1>"
        body += "<div class='box'>"
        body += "<p><b>标题:</b> %s</p>" % (rec["title"] or "N/A")
        body += "<p><b>期刊:</b> %s</p>" % (rec["journal"] or "N/A")
        body += "<p><b>年份:</b> %s</p>" % (rec["year"] or "N/A")
        authors = ", ".join("%s %s" % (a.get("given",""), a.get("family",""))
                            for a in (rec.get("authors") or []))
        body += "<p><b>作者:</b> %s</p>" % (authors or "N/A")
        body += "<p><b>OA状态:</b> %s</p>" % (rec["oa_status"] or "N/A")
        if rec["landing_url"]:
            body += '<p><b>原文页:</b> <a href="%s" target="_blank">%s</a></p>' \
                    % (rec["landing_url"], rec["landing_url"])
        body += "</div>"
        if saved:
            body += '<div class="box ok"><p>✅ 已下载 <b>%s</b> \
(<a href="/file?path=%s">打开</a>)</p></div>' % (
                os.path.basename(saved), saved)
        elif rec["pdf_url"]:
            body += '<div class="box err"><p>⚠️ 找到 Pdf 地址但下载失败，\
可手动访问: <a href="%s" target="_blank">%s</a></p></div>' % (
                rec["pdf_url"], rec["pdf_url"])
        else:
            body += '<div class="box"><p>未找到可下载的 OA PDF。</p></div>'
        body += '<p><a href="/">返回</a></p>'
        return _page(body)

    @app.route("/batch", methods=["POST"])
    def batch():
        raw = request.form.get("dois", "")
        from .cli import _parse_dois
        from .export import export_records

        dois = _parse_dois(raw)
        if not dois:
            return _page('<h1>📄</h1><p class="err">未解析到有效 DOI</p>'
                         '<p><a href="/">返回</a></p>')
        rows = []
        for doi in dois:
            try:
                rec = resolve_doi(doi, email=app.config["EMAIL"] or None)
            except ApiError as e:
                rows.append({"doi": doi, "error": str(e)})
                continue
            if rec is None:
                rows.append({"doi": doi, "error": "not found"})
                continue
            p = None
            if rec.get("pdf_url") or rec.get("pdf_urls"):
                urls = rec.get("pdf_urls") or []
                if rec["pdf_url"] not in urls:
                    urls.insert(0, rec["pdf_url"])
                try:
                    p = download_first(
                        urls,
                        app.config["DOWNLOAD_DIR"],
                        fallback_name=sanitize_filename(
                            rec.get("journal") or rec.get("title") or "paper"),
                    )
                except Exception:  # noqa: BLE001
                    p = None
            rec["saved_file"] = p
            rows.append(rec)

        csv_path = os.path.join(app.config["DOWNLOAD_DIR"],
                                "manifest.csv")
        export_records(rows, csv_path, fmt="csv")
        body = "<h1>📄 批量结果</h1>"
        body += "<table><tr><th>DOI</th><th>标题</th><th>保存</th></tr>"
        for r in rows:
            title = (r.get("title") or "N/A")
            if len(title) > 40:
                title = title[:40] + "…"
            saved = os.path.basename(r["saved_file"]) if r.get("saved_file") else r.get("error", "-")
            body += "<tr><td>%s</td><td>%s</td><td>%s</td></tr>" % (
                r.get("doi", ""), title, saved)
        body += "</table>"
        body += '<p><a href="/file?path=%s">下载 CSV 清单</a> · <a href="/">返回</a></p>' % csv_path
        return _page(body)

    @app.route("/file", methods=["GET"])
    def serve_file():
        path = request.args.get("path", "")
        if not path or not os.path.isfile(path):
            return "文件不存在", 404
        return send_file(path, as_attachment=False)

    return app


def run_app(host="127.0.0.1", port=5000, email=None):
    if not _HAS_FLASK:
        raise RuntimeError("需要安装 flask: pip install flask")
    app = create_app(email=email)
    print("scholar-doi 网页版已启动: http://%s:%d" % (host, port))
    app.run(host=host, port=port, debug=False)


if __name__ == "__main__":
    create_app().run(debug=True, host="127.0.0.1", port=5000)