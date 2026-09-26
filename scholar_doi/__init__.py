"""scholar-doi
输入 DOI 下载开放获取(OA)学术文献的 Python 工具。
兼容 Python 3.8+。
"""
__version__ = "1.0.0"
__all__ = [
    "is_valid_doi",
    "normalize_doi",
    "fetch_crossref_meta",
    "fetch_unpaywall_oa",
    "resolve_doi",
    "download_pdf",
    "extract_arxiv_id",
    "resolve_arxiv",
    "http_get"
]