"""HTTP-session med retry för källornas API:er."""

from __future__ import annotations

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


def session(user_agent: str = "fallen_leaves/0.1 (+https://github.com)") -> requests.Session:
    retry = Retry(
        total=5,
        backoff_factor=2,
        status_forcelist=(429, 500, 502, 503, 504),
        allowed_methods=frozenset({"GET", "POST"}),
        respect_retry_after_header=True,
    )
    s = requests.Session()
    s.headers["User-Agent"] = user_agent
    s.mount("https://", HTTPAdapter(max_retries=retry, pool_maxsize=16))
    return s
