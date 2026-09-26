"""scholar-doi 命令行工具。

用法示例：
    python -m scholar_doi.cli doi 10.1000/xyz -o ./papers -e you@example.com
    python -m scholar_doi.cli batch dois.txt -o ./papers -e you@example.com
"""
import argparse
import os
import re
import sys

from . import __version__
from .api import resolve_doi, ApiError
from .doi import normalize_doi
from .download import download_first, sanitize_filename
from .export import export_records

_ENV_EMAIL_FLAG = "SCHOLAR_EMAIL"


def _email_from_env():
    return os.environ.get(_ENV_EMAIL_FLAG) or None


def _get_email(args):
    """优先命令行 -e，其次环境变量，最后交互输入。"""
    email = getattr(args, "email", None) or _email_from_env()
    if email:
        return email
    try:
        return input("请输入用于 Unpaywall API 的邮箱(必填): ").strip()
    except EOFError:
        return ""


def _parse_dois(raw):
    """从文件内容或文本中解析 DOI 列表(去重保序)。"""
    if os.path.isfile(raw):
        with open(raw, "r", encoding="utf-8") as f:
            raw = f.read()
    dois = []
    for token in re.split(r"[\s,;]+", raw.strip()):
        if not token:
            continue
        d = normalize_doi(token)
        if d and d not in dois:
            dois.append(d)
    return dois


def download_record(record, output_dir):
    """尝试下载 record 的 OA PDF。返回本地路径或 None。"""
    if not output_dir:
        return None
    urls = record.get("pdf_urls") or []
    if record.get("pdf_url"):
        failed = record["pdf_url"]
        if failed not in urls:
            urls.insert(0, failed)
    if not urls:
        return None
    fallback = sanitize_filename(
        record.get("journal") or record.get("title") or "paper"
    )
    try:
        return download_first(urls, output_dir, fallback_name=fallback)
    except Exception as e:  # noqa: BLE001
        print("   下载失败: %s" % e, file=sys.stderr)
        return None


def cmd_doi(args):
    doi = normalize_doi(args.doi)
    if not doi:
        print("无效的 DOI: %s" % args.doi, file=sys.stderr)
        return 1
    email = _get_email(args)
    try:
        record = resolve_doi(doi, email=email)
    except ApiError as e:
        print("查询失败: %s" % e, file=sys.stderr)
        return 1
    if record is None:
        print("未找到该 DOI 对应的文献记录。")
        return 1

    print("=" * 60)
    print("标题 : %s" % (record["title"] or "N/A"))
    print("期刊 : %s" % (record["journal"] or "N/A"))
    print("年份 : %s" % (record["year"] or "N/A"))
    authors = ", ".join(
        "%s %s" % (a.get("given", ""), a.get("family", ""))
        for a in (record.get("authors") or [])
    )
    print("作者 : %s" % (authors or "N/A"))
    print("OA   : %s" % ("是" if record["is_oa"] else "否"))
    (print("PDF  : %s" % record["pdf_url"]) if record["pdf_url"] else None)

    if args.output:
        os.makedirs(args.output, exist_ok=True)
        p = download_record(record, args.output)
        if p:
            print("已下载: %s" % p)
        else:
            print("未找到可下载的 OA PDF，可访问落地页: %s"
                  % record.get("landing_url"))
    return 0


def cmd_batch(args):
    dois = _parse_dois(args.file)
    if not dois:
        print("未从输入中解析到有效 DOI。", file=sys.stderr)
        return 1
    email = _get_email(args)
    print("解析到 %d 个 DOI，开始查询..." % len(dois))

    records, failed = [], []
    for i, doi in enumerate(dois, 1):
        print("[%d/%d] %s" % (i, len(dois), doi))
        try:
            rec = resolve_doi(doi, email=email)
        except ApiError as e:
            print("   查询失败: %s" % e)
            failed.append({"doi": doi, "error": str(e)})
            continue
        if rec is None:
            print("   未找到记录")
            failed.append({"doi": doi, "error": "not found"})
            continue
        p = download_record(rec, args.output) if args.output else None
        if p:
            rec["saved_file"] = p
            print("   ✓ %s" % os.path.basename(p))
        elif rec["pdf_url"]:
            failed.append({"doi": doi, "error": "下载失败"})
        else:
            print("   无可用 OA PDF")
            failed.append({"doi": doi, "error": "no OA pdf"})
        records.append(rec)

    if records and args.meta:
        try:
            mp = export_records(records, args.meta, fmt="csv")
            print("元数据已导出: %s" % mp)
        except Exception as e:  # noqa: BLE001
            print("元数据导出失败: %s" % e, file=sys.stderr)
    if failed and args.failed_list:
        export_records(failed, args.failed_list, fmt="csv")
    print("-" * 60)
    print("完成: 查询 %d 条，成功下载/可获取 %d，失败 %d"
          % (len(dois), len(records) - len(failed) if records else 0, len(failed)))
    return 0


def cmd_web(args):
    """启动本地 Flask 网页版(可选依赖 flask)。"""
    try:
        from .web import run_app
    except ImportError as e:
        print("启动网页版需要 flask，请先: pip install flask", file=sys.stderr)
        print("详情: %s" % e, file=sys.stderr)
        return 1
    run_app(host=args.host, port=args.port, email=args.email or _email_from_env())
    return 0


def build_parser():
    p = argparse.ArgumentParser(
        prog="scholar-doi",
        description="输入 DOI 下载开放获取(OA)学术文献(Python 3.8+)",
    )
    p.add_argument("--version", action="version", version=__version__)
    sub = p.add_subparsers(dest="command", required=True)

    p_doi = sub.add_parser("doi", help="下载单个 DOI")
    p_doi.add_argument("doi", help="DOI 或 DOI 链接")
    p_doi.add_argument("-o", "--output", help="PDF 保存目录")
    p_doi.add_argument("-e", "--email", help="Unpaywall 邮箱")
    p_doi.set_defaults(func=cmd_doi)

    p_b = sub.add_parser("batch", help="批量下载(文件/文本)")
    p_b.add_argument("file", help="多个 DOI 的文件路径或逗号/空格分隔文本")
    p_b.add_argument("-o", "--output", help="PDF 保存目录")
    p_b.add_argument("-e", "--email", help="Unpaywall 邮箱")
    p_b.add_argument("--meta", help="导出 CSV 元数据路径")
    p_b.add_argument("--failed-list", dest="failed_list", help="失败记录 CSV 路径")
    p_b.set_defaults(func=cmd_batch)

    p_web = sub.add_parser("web", help="启动本地网页版(需 flask)")
    p_web.add_argument("--host", default="127.0.0.1")
    p_web.add_argument("--port", type=int, default=5000)
    p_web.add_argument("-e", "--email", help="Unpaywall 邮箱")
    p_web.set_defaults(func=cmd_web)

    return p


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())