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



def http_get(url, timeout=_DEFAULT_TIMEOUT, headers=None):
    """执行 GET 请求，返回 (status_code, bytes_body)。"""
    hdrs = {"User-Agent": _DEFAULT_USER_AGENT}
    if headers:
        hdrs.update(headers)

    req = _request.Request(url, headers=hdrs, method="GET")
    try:
        with _request.urlopen(req, timeout=timeout) as resp:
            body = resp.read()
            return resp.status, body
    except _request.HTTPError as e:
        return e.code, _safe_read(e)
    except _request.URLError as e:
        raise ApiError("网络请求失败: %s" % (e,))
    except Exception as e:  # noqa: BLE001
        raise ApiError("请求异常: %s" % (e,))

def _safe_read(resp):
    try:
        return resp.read()
    except Exception:  # noqa: BLE001
        return b""


