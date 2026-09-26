"""DOI 校验与规范化工具。"""
import re

# 常见 DOI 前缀形如: 10.xxxx/... 支持额外的 registro-agency 二级前缀 (如 10.1002/...)
_DOI_RE = re.compile(
    r"^(10\.\d{4,9}/[^\s,]+)$",
    re.IGNORECASE,
)


def normalize_doi(value):
    """把用户可能输入的各种形式规范成纯 DOI 字符串。

    支持：
    - 直接输入: 10.1000/xyz
    - 含 URL 前缀: https://doi.org/10.1000/xyz
    - 含空格/换行
    返回规范化后的 DOI；无法识别时返回 None。
    """
    if not value:
        return None
    v = str(value).strip()
    # 去掉可能的 URL 前缀
    for prefix in ("https://doi.org/", "http://doi.org/", "doi:"):
        if v.lower().startswith(prefix):
            v = v[len(prefix):]
            break
    v = v.strip()
    # 去掉尾部多余的标点(如句号、右括号)
    v = v.rstrip(")].;,")
    match = _DOI_RE.match(v)
    return match.group(1) if match else None


def is_valid_doi(value):
    """判断给定字符串是否为合法 DOI。"""
    return normalize_doi(value) is not None