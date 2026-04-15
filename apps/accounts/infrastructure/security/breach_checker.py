from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Dict

import requests


@dataclass(slots=True)
class BreachChecker:
    """
    Infrastructure service for password breach detection
    using HaveIBeenPwned k-anonymity API.
    """

    api_base_url: str = "https://api.pwnedpasswords.com/range"
    timeout_seconds: int = 5

    # simple in-memory cache (prefix -> response text)
    _cache: Dict[str, str] = None

    def __post_init__(self):
        self._cache = {}

    def is_pwned(self, password: str) -> bool:
        normalized = password.strip()

        sha1_hex = hashlib.sha1(
            normalized.encode("utf-8")
        ).hexdigest().upper()

        prefix, suffix = sha1_hex[:5], sha1_hex[5:]

        response_text = self._get_prefix_data(prefix)

        return self._suffix_exists(suffix, response_text)

    # -------------------------
    # INFRA HTTP LAYER
    # -------------------------
    def _get_prefix_data(self, prefix: str) -> str:
        if prefix in self._cache:
            return self._cache[prefix]

        try:
            response = requests.get(
                f"{self.api_base_url}/{prefix}",
                timeout=self.timeout_seconds,
                headers={"User-Agent": "LinkaPro/1.0"},
            )
            response.raise_for_status()
        except requests.RequestException:
            # FAIL CLOSED would be safer in high-security systems
            return ""

        self._cache[prefix] = response.text
        return response.text

    # -------------------------
    # PURE MATCH LOGIC
    # -------------------------
    def _suffix_exists(self, suffix: str, body: str) -> bool:
        if not body:
            return False

        # optimized lookup (no tuple unpacking)
        for line in body.splitlines():
            if not line:
                continue

            if line.startswith(suffix + ":"):
                return True

        return False