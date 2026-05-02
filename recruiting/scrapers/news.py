import re
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple

import feedparser
import requests


class NewsScraper:
    """
    Finds Healthcare AI companies with recent funding from:
      - TechCrunch RSS           (free, no key)
      - MobiHealthNews RSS       (free, no key)
      - FierceHealthcare RSS     (free, no key)
      - NewsAPI                  (optional, NEWSAPI_KEY)

    Targets companies in the same space as Qualified Health, Ambience Health,
    and HeartFlow: ambient AI, prior auth AI, clinical documentation AI,
    medical imaging AI, etc.
    """

    RSS_FEEDS = [
        "https://techcrunch.com/feed/",
        "https://www.mobihealthnews.com/rss.xml",
        "https://medcitynews.com/feed/",
    ]

    NEWSAPI_QUERIES = [
        '"healthcare AI" raises million Series',
        '"health AI" funding round',
        '"clinical AI" Series',
        '"ambient AI" healthcare',
        '"medical AI" raises',
        '"prior authorization AI" raises',
    ]

    # Keywords that indicate a Healthcare AI company in the target space
    RELEVANCE_KEYWORDS = [
        "healthcare ai", "health ai", "clinical ai", "medical ai", "ambient ai",
        "clinical documentation ai", "prior authorization ai", "radiology ai",
        "pathology ai", "cardiac ai", "imaging ai", "clinical decision support",
        "physician ai", "hospital ai", "digital health ai", "care management ai",
        "ambient clinical intelligence", "autonomous coding", "ai scribe",
        "ai-powered health", "ai-driven clinical", "predictive health ai",
        "revenue cycle ai", "ai in healthcare", "healthcare artificial intelligence",
    ]

    # Well-known large companies and our seed companies to skip
    EXCLUDE_NAMES = {
        "google", "microsoft", "amazon", "apple", "meta", "ibm", "oracle",
        "salesforce", "epic systems", "cerner", "meditech", "nuance",
        "qualified health", "ambience health", "heartflow",
    }

    def __init__(self, newsapi_key: str = None):
        self.newsapi_key = newsapi_key

    def find_recent_funding_announcements(self, days_back: int = 365) -> List[Dict]:
        seen: Dict[str, Dict] = {}  # normalized_name -> company dict

        for feed_url in self.RSS_FEEDS:
            for company in self._scrape_rss(feed_url):
                key = re.sub(r"[^a-z0-9]", "", company["name"].lower())
                if key not in seen:
                    seen[key] = company

        if self.newsapi_key:
            from_date = (datetime.now() - timedelta(days=days_back)).strftime("%Y-%m-%d")
            for query in self.NEWSAPI_QUERIES:
                for company in self._search_newsapi(query, from_date):
                    key = re.sub(r"[^a-z0-9]", "", company["name"].lower())
                    if key not in seen:
                        seen[key] = company
                time.sleep(0.3)

        return list(seen.values())

    # ── RSS ───────────────────────────────────────────────────────────────────

    def _scrape_rss(self, feed_url: str) -> List[Dict]:
        results = []
        try:
            feed = feedparser.parse(feed_url)
            for entry in feed.entries[:150]:
                title = entry.get("title", "")
                summary = entry.get("summary", "") or entry.get("description", "")
                if not self._is_relevant(f"{title} {summary}"):
                    continue
                company = self._extract_company({
                    "title": title,
                    "description": summary,
                    "url": entry.get("link", ""),
                    "publishedAt": entry.get("published", ""),
                })
                if company:
                    results.append(company)
        except Exception:
            pass
        return results

    # ── NewsAPI ───────────────────────────────────────────────────────────────

    def _search_newsapi(self, query: str, from_date: str) -> List[Dict]:
        results = []
        try:
            resp = requests.get(
                "https://newsapi.org/v2/everything",
                params={
                    "apiKey": self.newsapi_key,
                    "q": query,
                    "from": from_date,
                    "language": "en",
                    "sortBy": "relevancy",
                    "pageSize": 20,
                },
                timeout=10,
            )
            resp.raise_for_status()
            for article in resp.json().get("articles", []):
                text = f"{article.get('title', '')} {article.get('description', '')}"
                if self._is_relevant(text):
                    company = self._extract_company(article)
                    if company:
                        results.append(company)
        except Exception:
            pass
        return results

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _is_relevant(self, text: str) -> bool:
        """True if text is about a Healthcare AI company receiving funding."""
        tl = text.lower()
        has_domain = any(kw in tl for kw in self.RELEVANCE_KEYWORDS)
        has_funding = bool(re.search(
            r"rais(?:es?|ed)|fund(?:ing|ed)|series\s+[a-e]|invest(?:ment|ed|ing)|round",
            tl,
        ))
        return has_domain and has_funding

    def _extract_company(self, article: Dict) -> Optional[Dict]:
        title = article.get("title", "")
        description = article.get("description", "") or ""

        name = self._extract_name(title)
        if not name:
            return None
        if name.lower() in self.EXCLUDE_NAMES:
            return None
        if not (2 <= len(name) <= 60):
            return None

        amount, round_name = self._extract_funding(f"{title} {description}")
        pub = (article.get("publishedAt", "") or "")[:10] or None

        return {
            "name": name,
            "description": description[:500] if description else None,
            "funding_amount": amount,
            "funding_round": round_name,
            "funding_date": pub,
            "website": None,
            "source": "news",
            "source_url": article.get("url") or article.get("link") or None,
        }

    def _extract_name(self, title: str) -> Optional[str]:
        """Extract company name from an article headline."""
        if not title:
            return None
        patterns = [
            r"^([A-Z][A-Za-z0-9\s\.&\-]{1,35}?)\s+(?:raises?|lands?|closes?|secures?|announces?|nabs?|bags?|gets?)\s+",
            r"^([A-Z][A-Za-z0-9\s\.&\-]{1,35}?)\s*,\s*(?:a|an|the)\s+[a-z]",
            r"^([A-Z][A-Za-z0-9\s\.&\-]{1,35}?)\s+(?:gets?|receives?)\s+\$",
        ]
        for pattern in patterns:
            m = re.match(pattern, title)
            if m:
                name = m.group(1).strip().rstrip(".,")
                words = name.split()
                if 1 <= len(words) <= 5 and len(name) >= 3:
                    return name
        return None

    def _extract_funding(self, text: str) -> Tuple[Optional[str], Optional[str]]:
        amount = None
        round_name = None

        m = re.search(r"\bSeries\s+([A-E])\b", text)
        if m:
            round_name = f"Series {m.group(1)}"
        elif re.search(r"\bSeed\b", text, re.I):
            round_name = "Seed"

        for pattern in [
            r"\$\s*([\d,]+(?:\.\d+)?)\s*(billion|million|B|M)\b",
            r"([\d,]+(?:\.\d+)?)\s*(billion|million)\s+(?:in\s+)?(?:funding|raise|round)",
        ]:
            m = re.search(pattern, text, re.I)
            if m:
                num_str = m.group(1).replace(",", "")
                unit = m.group(2).lower()
                try:
                    num = float(num_str)
                    amount = f"${num:.1f}B" if unit in ("b", "billion") else f"${num:.0f}M"
                except ValueError:
                    pass
                break

        return amount, round_name
