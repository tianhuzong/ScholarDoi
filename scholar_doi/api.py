"""多来源学术文献元数据与开放获取(OA)查询。

数据来源（均为合规开放接口）：
- Crossref: 文章元数据（标题、作者、期刊、年份、DOI 等）
  https://api.crossref.org/works/{doi}
- Unpaywall: 查询该 DOI 是否有合法开放获取(OA)版本及其 PDF 直链
  https://api.unpaywall.org/v2/{doi}?email=...
"""
import json
import time
from .arxiv import resolve_arxiv, extract_arxiv_id
from .httpget import http_get

try:
    import urllib.request as _request
except ImportError:  # pragma: no cover
    import urllib2 as _request  # type: ignore

_DEFAULT_TIMEOUT = 30
_DEFAULT_USER_AGENT = (
    #"scholar-doi/1.0 (Python academic OA downloader; "
    #"mailto:you@example.com)"
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/120.0.0.0 Safari/537.36"

)
_HTTP_STATUS_OK = 200


class ApiError(Exception):
    """API 调用错误基类。"""


class NotFoundError(ApiError):
    """未找到对应文献。"""


class RateLimitError(ApiError):
    """请求过于频繁或配额受限。"""


def _json_load(body):
    try:
        return json.loads(body.decode("utf-8", errors="replace"))
    except (ValueError, UnicodeDecodeError):
        return None



def fetch_crossref_meta(doi, timeout=_DEFAULT_TIMEOUT):
    """通过 Crossref 查询文章元数据。

    返回 dict 或 None（未找到时）。字段结构随 Crossref 而定，
    本函数做一层扁平化整理。
    """
    url = "https://api.crossref.org/works/%s" % _quote(doi)
    status, body = http_get(url, timeout=timeout)
    if status == _HTTP_STATUS_OK:
        data = _json_load(body)
        return data.get("message") if data else None
    if status in (404, 400):
        return None
    if status == 429:
        raise RateLimitError("Crossref 请求过于频繁(429)，请稍后重试")
    raise ApiError("Crossref 返回异常状态码: %s" % status)


def _quote(doi):
    from urllib.parse import quote

    return quote(str(doi), safe=":/()")


def fetch_unpaywall_oa(doi, email, timeout=_DEFAULT_TIMEOUT):
    """通过 Unpaywall 查询给定 DOI 的开放获取(OA)信息。

    email 必填（Unpaywall 要求提供邮箱用于溯源）。

    返回 dict，若该 DOI 无记录返回 {}：
    {
        "doi": str,
        "is_oa": bool,
        "oa_status": str,
        "best_oa_location": {...} | None,
        "oa_locations": [ {...}, ... ],
    }
    """
    if not email:
        raise ValueError("Unpaywall 需要提供邮箱(email)参数")
    url = (
        "https://api.unpaywall.org/v2/%s?email=%s"
        % (_quote(doi), _quote(email))
    )
    status, body = http_get(url, timeout=timeout)
    if status == _HTTP_STATUS_OK:
        return _json_load(body) or {}
    if status == 404:
        return {}
    if status == 429:
        raise RateLimitError("Unpaywall 请求过于频繁(429)，请稍后重试")
    raise ApiError("Unpaywall 返回异常状态码: %s" % status)


def resolve_doi(doi, email=None, timeout=_DEFAULT_TIMEOUT):
    """一站式解析：聚合 Crossref 元数据 + Unpaywall OA 信息。

    返回 dict：
    {
        "doi": str,
        "title": str,
        "authors": [ {family, given, orcid} ],
        "journal": str,
        "year": int | None,
        "publisher": str,
        "type": str,
        "is_oa": bool,
        "oa_status": str,
        "pdf_url": str | None,     # 最佳可用 PDF 直链
        "landing_url": str | None, # 文章落地页
        "oa_locations": [...] ,
    }
    未找到时返回 None。
    """
    arxiv_id = extract_arxiv_id(doi)
    if arxiv_id:
        return resolve_arxiv(arxiv_id, doi)
    meta = fetch_crossref_meta(doi, timeout=timeout)
    oa = {}
    if email:
        try:
            oa = fetch_unpaywall_oa(doi, email, timeout=timeout)
        except ApiError:
            oa = {}

    result = {
        "doi": doi,
        "title": _crossref_title(meta) if meta else None,
        "authors": _crossref_authors(meta) if meta else [],
        "journal": _crossref_journal(meta) if meta else None,
        "year": _crossref_year(meta) if meta else None,
        "publisher": _crossref_publisher(meta) if meta else None,
        "type": (meta or {}).get("type"),
        "is_oa": bool(oa.get("is_oa")),
        "oa_status": oa.get("oa_status"),
        "pdf_url": _best_pdf(oa),
        "pdf_urls": _all_pdf_candidates(oa),
        "landing_url": _best_landing(oa),
        "oa_locations": oa.get("oa_locations") or [],
    }

    # 若无任何信息则视为未找到
    if (
        not result["title"]
        and not result["journal"]
        and not result["pdf_url"]
        and not result["landing_url"]
    ):
        return None
    return result


def _crossref_title(meta):
    titles = meta.get("title") or []
    return titles[0] if titles else None


def _crossref_authors(meta):
    out = []
    for a in meta.get("author") or []:
        out.append(
            {
                "family": a.get("family"),
                "given": a.get("given"),
                "orcid": a.get("ORCID"),
            }
        )
    return out


def _crossref_journal(meta):
    cont = meta.get("container-title") or meta.get("container") or []
    return cont[0] if cont else None


def _crossref_publisher(meta):
    return meta.get("publisher")


def _crossref_year(meta):
    for k in ("published-print", "published-online", "issued", "created"):
        v = meta.get(k) or {}
        parts = v.get("date-parts") or []
        if parts and parts[0]:
            try:
                return int(parts[0][0])
            except (ValueError, TypeError):
                continue
    return None


def _best_pdf(oa):
    """从 OA 信息中取最佳 PDF 直链。"""
    best = oa.get("best_oa_location") or {}
    url = best.get("url_for_pdf") or best.get("url")
    if url:
        return url
    for loc in oa.get("oa_locations") or []:
        u = loc.get("url_for_pdf") or loc.get("url")
        if u:
            return u
    return None


def _best_landing(oa):
    best = oa.get("best_oa_location") or {}
    url = best.get("url") or best.get("url_for_landing_page")
    if url:
        return url
    for loc in oa.get("oa_locations") or []:
        u = loc.get("url_for_landing_page") or loc.get("url")
        if u:
            return u
    return None


def _all_pdf_candidates(oa):
    """聚合所有可尝试下载 PDF 的地址(去重保序)。

    优先 url_for_pdf，其次各 location 的 url；DOI 跳转地址放最后。
    """
    seen, out = set(), []
    for loc in (oa.get("oa_locations") or []):
        for key in ("url_for_pdf", "url_for_landing_page", "url"):
            u = loc.get(key)
            if u and u not in seen:
                seen.add(u)
                out.append(u)
    # 兜底补上 best
    if oa.get("best_oa_location"):
        url = (oa["best_oa_location"].get("url_for_pdf")
               or oa["best_oa_location"].get("url"))
        if url and url not in seen:
            seen.add(url)
            out.insert(0, url)
    return out


def _sleep_between_calls(seconds=1.0):
    """简单节流，避免触发命中率限制。"""
    time.sleep(seconds)