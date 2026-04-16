"""Retry utility with exponential backoff for transient API failures."""

from __future__ import annotations

import random
import time
from typing import Callable

from rich.console import Console

console = Console()


def retry_api_call(
    func: Callable,
    *args,
    max_retries: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 30.0,
    **kwargs,
):
    """Execute func with exponential backoff retry on transient failures.

    Retries on: ConnectionError, TimeoutError, HTTP 429, HTTP 5xx.
    Does NOT retry on: ValueError, HTTP 4xx (except 429).

    Backoff: delay = min(base * 2^attempt + jitter, max_delay)
    """
    attempt = 0
    while attempt <= max_retries:
        try:
            return func(*args, **kwargs)
        except (ConnectionError, TimeoutError) as e:
            if attempt >= max_retries:
                raise
            console.print(
                f"  [yellow]Network error (attempt {attempt + 1}/{max_retries + 1}): {e}[/yellow]"
            )
            _exponential_backoff(attempt, base_delay, max_delay)
            attempt += 1
        except Exception as e:
            if not _is_transient_error(e):
                raise
            if attempt >= max_retries:
                raise
            console.print(
                f"  [yellow]Transient error (attempt {attempt + 1}/{max_retries + 1}): {e}[/yellow]"
            )
            _exponential_backoff(attempt, base_delay, max_delay)
            attempt += 1


def _is_transient_error(exc: Exception) -> bool:
    """Check if an exception represents a transient (retryable) error."""
    exc_name = exc.__class__.__name__
    exc_str = str(exc)

    # requests library exceptions
    if exc_name in ("Timeout", "ConnectionError", "HTTPError"):
        if hasattr(exc, "response") and hasattr(exc.response, "status_code"):
            status = exc.response.status_code
            return status == 429 or status >= 500
        return exc_name in ("Timeout", "ConnectionError")

    # openai library exceptions
    if "openai" in exc_name.lower() or "RateLimit" in exc_name:
        return True

    # google genai exceptions
    if "google" in str(type(exc).__module__).lower():
        return "429" in exc_str or "500" in exc_str or "ResourceExhausted" in exc_name

    # Generic HTTP status codes in string representation
    if "429" in exc_str or "rate limit" in exc_str.lower():
        return True
    if any(f"50{i}" in exc_str for i in range(10)):
        return True

    return False


def _exponential_backoff(attempt: int, base_delay: float, max_delay: float):
    """Sleep with exponential backoff and jitter."""
    exp_delay = base_delay * (2**attempt)
    jitter = random.uniform(0, exp_delay)
    delay = min(exp_delay + jitter, max_delay)
    console.print(f"  [dim]Retrying in {delay:.1f}s…[/dim]")
    time.sleep(delay)
