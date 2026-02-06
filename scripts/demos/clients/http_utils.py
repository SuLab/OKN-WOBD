"""Shared HTTP session configuration with retry logic."""

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


def create_session(
    max_retries: int = 3,
    backoff_factor: float = 0.5,
    status_forcelist: tuple = (500, 502, 503, 504),
    allowed_methods: tuple = ("GET", "POST"),
    user_agent: str = "OKN-WOBD/1.0",
) -> requests.Session:
    """
    Create a requests Session with retry logic and standard headers.

    Args:
        max_retries: Maximum retry attempts
        backoff_factor: Backoff multiplier between retries
        status_forcelist: HTTP status codes that trigger retries
        allowed_methods: HTTP methods that can be retried
        user_agent: User-Agent header value

    Returns:
        Configured requests.Session
    """
    session = requests.Session()
    retries = Retry(
        total=max_retries,
        backoff_factor=backoff_factor,
        status_forcelist=status_forcelist,
        allowed_methods=allowed_methods,
    )
    adapter = HTTPAdapter(max_retries=retries)
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    session.headers.update({"User-Agent": user_agent})
    return session
