import re
import time
from typing import Dict, List, Optional

import requests


class ContactEnricher:
    """
    Enriches contact records with email addresses via Hunter.io.

    Free tier: 25 email-finder searches per month.
    Only calls Hunter.io when a company website domain is known.
    Only stores results with confidence score >= 50.
    """

    BASE = "https://api.hunter.io/v2"
    MIN_CONFIDENCE = 50

    def __init__(self, api_key: str):
        self.api_key = api_key

    def find_email(self, contact: Dict) -> Optional[str]:
        """Return an email address for the contact, or None."""
        domain = self._extract_domain(contact.get("company_website"))
        if not domain:
            return None

        parts = (contact.get("name") or "").strip().split()
        if len(parts) < 2:
            return None

        first, last = parts[0], parts[-1]

        try:
            resp = requests.get(
                f"{self.BASE}/email-finder",
                params={
                    "api_key": self.api_key,
                    "domain": domain,
                    "first_name": first,
                    "last_name": last,
                },
                timeout=10,
            )
            if resp.status_code == 200:
                data = resp.json().get("data", {})
                email = data.get("email")
                score = data.get("score", 0) or 0
                if email and score >= self.MIN_CONFIDENCE:
                    return email
            elif resp.status_code == 429:
                time.sleep(60)  # Hunter.io rate limit — back off
        except Exception:
            pass

        return None

    def get_domain_pattern(self, domain: str) -> Optional[str]:
        """
        Return the email pattern for a company domain (e.g. '{first}.{last}@acme.com').
        Useful for generating likely addresses when email-finder has no direct match.
        """
        try:
            resp = requests.get(
                f"{self.BASE}/domain-search",
                params={"api_key": self.api_key, "domain": domain, "limit": 1},
                timeout=10,
            )
            if resp.status_code == 200:
                return resp.json().get("data", {}).get("pattern")
        except Exception:
            pass
        return None

    def apply_pattern(self, name: str, domain: str, pattern: str) -> Optional[str]:
        """Generate an email from a Hunter.io pattern string."""
        parts = name.strip().split()
        if len(parts) < 2:
            return None
        first, last = parts[0].lower(), parts[-1].lower()
        replacements = {
            "{first}": first,
            "{last}": last,
            "{f}": first[0],
            "{l}": last[0],
            "{first_initial}": first[0],
            "{last_initial}": last[0],
        }
        address = pattern
        for placeholder, value in replacements.items():
            address = address.replace(placeholder, value)
        if re.match(r"[a-z0-9._%+\-]+", address):
            return f"{address}@{domain}"
        return None

    @staticmethod
    def _extract_domain(website: Optional[str]) -> Optional[str]:
        if not website:
            return None
        m = re.search(r"(?:https?://)?(?:www\.)?([a-zA-Z0-9\-]+\.[a-zA-Z]{2,})", website)
        return m.group(1).lower() if m else None
