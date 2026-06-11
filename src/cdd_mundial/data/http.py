"""Bounded HTTP acquisition for public tabular data sources."""

from __future__ import annotations

import time

import requests


RETRYABLE_STATUS_CODES = {429, 500, 502, 503, 504}


def fetch_bytes(
    url: str,
    *,
    connect_timeout: float = 5,
    read_timeout: float = 20,
    retries: int = 2,
    backoff_seconds: float = 1.0,
    user_agent: str = "CDD-MUNDIAL/1.0 (+public research project)",
) -> bytes:
    """Fetch a non-empty tabular payload with bounded retries and timeouts."""
    if retries < 0:
        raise ValueError("retries must be non-negative")

    session = requests.Session()
    session.headers.update({"User-Agent": user_agent})

    for attempt in range(retries + 1):
        try:
            response = session.get(url, timeout=(connect_timeout, read_timeout))
            if response.status_code in RETRYABLE_STATUS_CODES and attempt < retries:
                time.sleep(backoff_seconds * (2**attempt))
                continue
            response.raise_for_status()
        except (requests.ConnectionError, requests.Timeout):
            if attempt >= retries:
                raise
            time.sleep(backoff_seconds * (2**attempt))
            continue

        body = response.content
        if not body:
            raise ValueError(f"empty response body from {url}")

        if url.lower().endswith(".tsv"):
            content_type = response.headers.get("Content-Type", "").lower()
            prefix = body.lstrip()[:256].lower()
            if "text/html" in content_type or prefix.startswith(
                (b"<!doctype html", b"<html")
            ):
                raise ValueError(f"HTML response rejected for TSV endpoint: {url}")

        return body

    raise RuntimeError("unreachable retry state")
