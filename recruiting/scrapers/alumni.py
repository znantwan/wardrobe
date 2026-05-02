import re
import time
from typing import Dict, List, Optional

import requests


class AlumniScraper:
    """
    Finds Stanford GSB alumni at a company by searching LinkedIn profiles
    through Google Custom Search API or SerpAPI.

    Each company is searched with three query patterns to maximise coverage.
    Results are deduplicated by LinkedIn URL within a single company.
    """

    QUERY_TEMPLATES = [
        'site:linkedin.com/in "{company}" "Stanford" "GSB"',
        'site:linkedin.com/in "{company}" "Stanford Graduate School of Business"',
        'site:linkedin.com/in "{company}" "Stanford GSB" MBA',
    ]

    def __init__(
        self,
        google_api_key: str = None,
        google_cx_id: str = None,
        serpapi_key: str = None,
    ):
        self.google_api_key = google_api_key
        self.google_cx_id = google_cx_id
        self.serpapi_key = serpapi_key

    def find_stanford_gsb_alumni(self, company: Dict) -> List[Dict]:
        seen_urls: set = set()
        results: List[Dict] = []

        for template in self.QUERY_TEMPLATES:
            query = template.format(company=company["name"])

            if self.serpapi_key:
                items = self._serpapi_search(query)
            elif self.google_api_key and self.google_cx_id:
                items = self._google_search(query)
            else:
                break

            for item in items:
                contact = self._parse_result(item, company)
                if contact and contact["linkedin_url"] not in seen_urls:
                    seen_urls.add(contact["linkedin_url"])
                    results.append(contact)

            time.sleep(1.5)  # stay within free-tier rate limits

        return results

    # ── Search backends ───────────────────────────────────────────────────────

    def _google_search(self, query: str) -> List[Dict]:
        try:
            resp = requests.get(
                "https://www.googleapis.com/customsearch/v1",
                params={
                    "key": self.google_api_key,
                    "cx": self.google_cx_id,
                    "q": query,
                    "num": 10,
                },
                timeout=10,
            )
            resp.raise_for_status()
            return resp.json().get("items", [])
        except Exception:
            return []

    def _serpapi_search(self, query: str) -> List[Dict]:
        try:
            resp = requests.get(
                "https://serpapi.com/search",
                params={
                    "api_key": self.serpapi_key,
                    "engine": "google",
                    "q": query,
                    "num": 10,
                },
                timeout=10,
            )
            resp.raise_for_status()
            return resp.json().get("organic_results", [])
        except Exception:
            return []

    # ── Parsing ───────────────────────────────────────────────────────────────

    def _parse_result(self, item: Dict, company: Dict) -> Optional[Dict]:
        link = item.get("link", "") or item.get("url", "")
        title = item.get("title", "")
        snippet = item.get("snippet", "")

        # Must be a real LinkedIn /in/ profile URL
        m = re.match(r"(https?://[a-z\-]+\.linkedin\.com/in/[a-z0-9\-]+)", link, re.I)
        if not m:
            return None
        linkedin_url = m.group(1)

        name = self._extract_name(title)
        if not name:
            return None

        return {
            "company_id": company["id"],
            "name": name,
            "title": self._extract_job_title(snippet),
            "email": None,
            "linkedin_url": linkedin_url,
            "school": "Stanford GSB",
            "source": "google_linkedin_search",
        }

    def _extract_name(self, title_str: str) -> Optional[str]:
        """Extract person name from a LinkedIn page title string."""
        if not title_str:
            return None
        # Strip "| LinkedIn" or "- LinkedIn" suffix
        cleaned = re.sub(r"\s*[|\-]\s*LinkedIn\s*$", "", title_str, flags=re.I).strip()
        # Take the part before the first " - " separator
        candidate = re.split(r"\s*[\-–—]\s*", cleaned)[0].strip()
        words = candidate.split()
        if (
            2 <= len(words) <= 4
            and len(candidate) <= 50
            and not any(ch.isdigit() for ch in candidate)
        ):
            return candidate
        return None

    def _extract_job_title(self, snippet: str) -> Optional[str]:
        """Try to extract current job title from a LinkedIn snippet."""
        if not snippet:
            return None
        # Strip boilerplate
        snippet = re.sub(r"View [A-Z].*?profile on LinkedIn.*", "", snippet, flags=re.I).strip()
        # "Title at Company" pattern
        m = re.search(r"([A-Z][^|·\n\-]{5,60}?)\s+at\s+[A-Z]", snippet)
        if m:
            return m.group(1).strip()
        # Fallback: first segment of first line
        first = snippet.split("\n")[0].split("·")[0].strip()
        if 5 < len(first) < 80 and not first.startswith("http"):
            return first
        return None
