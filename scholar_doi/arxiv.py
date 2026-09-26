# 为arxiv做一个适配

import re
from .httpget import _DEFAULT_TIMEOUT, http_get

_ARXIV_DOI_RE = re.compile(r"^10\.48550/arXiv\.(.+)$", re.IGNORECASE)
_ARXIV_ID_RE = re.compile(r"^(\d{4}\.\d{4,5})(v\d+)?$", re.IGNORECASE)

def extract_arxiv_id(doi):
    """从 DOI 或裸 arXiv ID 中提取 arXiv ID，失败返回 None。"""
    if not doi:
        return None
    s = str(doi).strip()
    # 形式 1: 10.48550/arXiv.2308.14469
    m = _ARXIV_DOI_RE.match(s)
    if m:
        return m.group(1)
    # 形式 2: 裸 ID，如 2308.14469 或 2308.14469v2
    if _ARXIV_ID_RE.match(s):
        return s
    return None

def _fetch_arxiv_meta(arxiv_id, timeout=_DEFAULT_TIMEOUT):
    """调用 arXiv API 获取标题/作者，失败返回 (None, [])。"""
    url = "http://export.arxiv.org/api/query?id_list=%s" % arxiv_id
    try:
        status, body = http_get(url, timeout=timeout)
        if status != 200:
            return None, []
        import xml.etree.ElementTree as ET
        ns = {"a": "http://www.w3.org/2005/Atom"}
        root = ET.fromstring(body)
        entry = root.find("a:entry", ns)
        if entry is None:
            return None, []
        title = (entry.findtext("a:title", default="", namespaces=ns) or "").strip()
        authors = []
        for a in entry.findall("a:author", ns):
            name = (a.findtext("a:name", default="", namespaces=ns) or "").strip()
            if name:
                parts = name.rsplit(" ", 1)
                authors.append({
                    "given": parts[0] if len(parts) > 1 else "",
                    "family": parts[-1],
                    "orcid": None,
                })
        return title or None, authors
    except Exception:
        return None, []

def resolve_arxiv(arxiv_id, original_doi=None):
    """arXiv 论文直通解析：直接构造开放 PDF 地址，不走 Crossref/Unpaywall。

    返回结构与 resolve_doi 完全一致，便于上层代码复用。
    """
    clean_id = arxiv_id
    # 去掉版本号，用于构造稳定链接（arXiv 的 /pdf/ 链接带不带 v 都能用）
    base_id = _ARXIV_ID_RE.match(arxiv_id)
    if base_id:
        clean_id = base_id.group(1)

    pdf_url = "https://arxiv.org/pdf/%s.pdf" % clean_id
    abs_url = "https://arxiv.org/abs/%s" % arxiv_id
    title, authors = _fetch_arxiv_meta(clean_id)

    return {
        "doi": original_doi or ("10.48550/arXiv." + clean_id),
        "title": title,
        "authors": authors,
        "journal": "arXiv",
        "year": _arxiv_year_from_id(clean_id),
        "publisher": "arXiv",
        "type": "preprint",
        "is_oa": True,
        "oa_status": "gold",
        "pdf_url": pdf_url,
        "pdf_urls": [pdf_url],
        "landing_url": abs_url,
        "oa_locations": [],
    }


def _arxiv_year_from_id(arxiv_id):
    """从 arXiv ID 前两位推断年份，如 2308 -> 2023。"""
    m = re.match(r"^(\d{2})\d{2}\.", arxiv_id)
    if not m:
        return None
    yy = int(m.group(1))
    return 2000 + yy if yy < 90 else 1900 + yy