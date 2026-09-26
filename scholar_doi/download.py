"""PDF 文件下载与本地保存。

支持：
- 跟随 HTTP 重定向
- URL 里含 .pdf 直接下载
- 落地页是 HTML 时，自动从页内提取 PDF 链接后再下载
- 多个候选 URL 顺序尝试
"""
import os
import re

try:
    import urllib.request as _request
    from urllib.parse import urlparse, urljoin, unquote
except ImportError:  # pragma: no cover
    import urllib2 as _request  # type: ignore

from .httpget import _DEFAULT_USER_AGENT
from .httpget import ApiError, http_get

_DEFAULT_TIMEOUT = 60

# 常见 PDF 链接特征：.pdf 结尾，或指向 pdffulltext/pdf/download 等路径
_PDF_HINT_RE = re.compile(
    r"""(["'=]\s*)(https?://[^'">\s]+|/[^'">\s]+)""",
    re.IGNORECASE,
)
_PDF_SUFFIX_RE = re.compile(
    r"\.pdf(?=[?&]|$)\s*$", re.IGNORECASE,
)
_PDF_PATH_RE = re.compile(
    r"(pdf|fulltext|download|journal%2f|/articlepdf)",
    re.IGNORECASE,
)


def sanitize_filename(name):
    """把字符串清洗为安全文件名。"""
    if not name:
        return "paper"
    clean = re.sub(r"[\\/:*?\"<>|\s]+", "_", str(name))
    return clean.strip("._") or "paper"


def safe_download_path(url, dest_dir, fallback_name="paper"):
    """根据 URL 或给定名称在 dest_dir 中生成一个唯一保存路径。"""
    dest_dir = os.path.abspath(dest_dir)
    os.makedirs(dest_dir, exist_ok=True)

    base = fallback_name or "paper"
    base = sanitize_filename(base)[:80]
    fname = _filename_from_url(url) or base
    fname = sanitize_filename(fname)[:80]
    if not fname.lower().endswith(".pdf"):
        fname += ".pdf"

    candidate = os.path.join(dest_dir, fname)
    counter = 1
    while os.path.exists(candidate):
        stem, ext = os.path.splitext(fname)
        candidate = os.path.join(
            dest_dir, "%s_%d%s" % (stem[:70], counter, ext)
        )
        counter += 1
    return candidate


def _filename_from_url(url):
    if not url:
        return None
    try:
        path = urlparse(url).path
    except Exception:  # noqa: BLE001
        return None
    if not path:
        return None
    name = unquote(os.path.basename(path))
    return name if name else None


def extract_pdf_links(html, base_url=None):
    """从 HTML 文本中提取候选 PDF 链接。"""
    links = []
    for m in _PDF_HINT_RE.finditer(html or ""):
        link = m.group(2).strip()
        if not link or not (link.startswith("http") or link.startswith("/")):
            continue
        # 判定是否为 PDF
        is_pdf = bool(_PDF_SUFFIX_RE.search(link))
        is_pdf_path = bool(_PDF_PATH_RE.search(link))
        if not (is_pdf or is_pdf_path):
            continue
        if base_url and link.startswith("/"):
            link = urljoin(base_url, link)
        if base_url and not link.startswith("http"):
            link = urljoin(base_url, link)
        if link not in links:
            links.append(link)
    return links[:10]


def _is_pdf_content(body):
    return body is not None and body[:5].lower().startswith(b"%pdf")


def _decode_html(body):
    for enc in ("utf-8", "latin-1", "gbk"):
        try:
            return body.decode(enc, errors="strict")
        except (UnicodeDecodeError, LookupError):
            continue
    return body.decode("utf-8", errors="replace")


def _download_raw(url, timeout):
    """下载原始内容(不校验类型)。返回 bytes。"""
    status, body = http_get(url, timeout=timeout)
    if status != 200:
        raise ApiError("下载失败，状态码: %s (%s)" % (status, url))
    if not body:
        raise ApiError("下载内容为空: %s" % url)
    return body


def download_from_url(
    url, dest_dir, fallback_name="paper", timeout=_DEFAULT_TIMEOUT
):
    """从单个 url 尽力下载 PDF。

    1. 若返回内容本身是 PDF → 直接保存
    2. 若是 HTML → 提取页内 PDF 链接，逐个尝试
    3. 失败返回 None；遇到非 PDF 且无法提取则返回 None
    """
    if not url:
        return None
    body = None
    try:
        body = _download_raw(url, timeout)
    except ApiError:
        return None

    if _is_pdf_content(body):
        return _save_bytes(
            body, url, dest_dir, fallback_name
        )

    # 是 HTML：提取 PDF 链接
    html = _decode_html(body)
    pdf_links = extract_pdf_links(html, base_url=url)
    for cand in pdf_links:
        if cand == url:
            continue
        try:
            sub = _download_raw(cand, timeout)
        except ApiError:
            continue
        if _is_pdf_content(sub):
            return _save_bytes(sub, cand, dest_dir, fallback_name)
    return None


def _save_bytes(body, url, dest_dir, fallback_name):
    dest_path = safe_download_path(url, dest_dir, fallback_name)
    with open(dest_path, "wb") as f:
        f.write(body)
    return dest_path


def download_first(
    urls, dest_dir, fallback_name="paper", timeout=_DEFAULT_TIMEOUT
):
    """从 urls 列表顺序尝试，返回第一个成功保存的本地路径，失败返回 None。"""
    for url in urls:
        if not url:
            continue
        try:
            p = download_from_url(
                url, dest_dir, fallback_name=fallback_name, timeout=timeout
            )
        except Exception:  # noqa: BLE001
            p = None
        if p:
            return p
    return None


def download_pdf(url, dest_dir, fallback_name="paper", timeout=_DEFAULT_TIMEOUT):
    """兼容旧接口：从 url 下载 PDF，若失败抛异常。"""
    p = download_from_url(url, dest_dir, fallback_name, timeout)
    if not p:
        raise ValueError("未能从 %s 下载到有效 PDF" % (url or "空地址"))
    return p


def readable_size(num_bytes):
    """人类可读的文件大小。"""
    if num_bytes is None:
        return "unknown"
    size = float(num_bytes)
    for unit in ("B", "KB", "MB", "GB"):
        if size < 1024.0 or unit == "GB":
            return "%.1f %s" % (size, unit)
        size /= 1024.0
    return "%.1f GB" % size