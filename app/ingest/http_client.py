"""Shared HTTP GET with retry for transient network errors, reused by every EDGAR/FMP client."""

import time
import urllib.error
import urllib.request

REQUEST_TIMEOUT_SECONDS = 15
MAX_ATTEMPTS = 3
RETRY_DELAY_SECONDS = 2


def get_with_retry(url: str, headers: dict[str, str]) -> bytes:
    """GET a URL with the given headers, retrying transient network errors."""
    request = urllib.request.Request(url, headers=headers)
    last_error: urllib.error.URLError | None = None
    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            with urllib.request.urlopen(request, timeout=REQUEST_TIMEOUT_SECONDS) as response:
                return response.read()
        except urllib.error.URLError as error:
            last_error = error
            if attempt < MAX_ATTEMPTS:
                time.sleep(RETRY_DELAY_SECONDS)
    raise last_error
