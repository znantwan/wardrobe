import time
from typing import Dict, List, Optional

import requests


class CrunchbaseScraper:
    """
    Searches Crunchbase for Healthcare AI companies with recent funding.
    Requires a Crunchbase Basic API key (crunchbase.com/account/api).

    Targets companies similar to Qualified Health, Ambience Health, HeartFlow:
    - Category: Health Care + Artificial Intelligence
    - Last funding type: Series B, C, D, or E
    - Last funding date: 2023-01-01 or later
    """

    BASE_URL = "https://api.crunchbase.com/api/v4"

    FUNDING_ROUND_MAP = {
        "series_a": "Series A",
        "series_b": "Series B",
        "series_c": "Series C",
        "series_d": "Series D",
        "series_e": "Series E",
        "seed": "Seed",
        "angel": "Angel",
        "pre_seed": "Pre-Seed",
        "convertible_note": "Convertible Note",
        "corporate_round": "Corporate Round",
    }

    # Two passes: Series B+ first, then Series A for smaller earlier-stage cos
    SEARCHES = [
        {
            "field_ids": [
                "short_description", "funding_total", "last_funding_type",
                "last_funding_at", "homepage_url", "linkedin",
            ],
            "query": [
                {"type": "predicate", "field_id": "facet_ids",
                 "operator_id": "includes", "values": ["company"]},
                {"type": "predicate", "field_id": "category_groups",
                 "operator_id": "includes",
                 "values": ["Health Care", "Artificial Intelligence"]},
                {"type": "predicate", "field_id": "last_funding_at",
                 "operator_id": "gte", "values": ["2023-01-01"]},
                {"type": "predicate", "field_id": "last_funding_type",
                 "operator_id": "includes",
                 "values": ["series_b", "series_c", "series_d", "series_e"]},
            ],
            "order": [{"field_id": "last_funding_at", "sort": "desc"}],
            "limit": 25,
        },
        {
            "field_ids": [
                "short_description", "funding_total", "last_funding_type",
                "last_funding_at", "homepage_url", "linkedin",
            ],
            "query": [
                {"type": "predicate", "field_id": "facet_ids",
                 "operator_id": "includes", "values": ["company"]},
                {"type": "predicate", "field_id": "category_groups",
                 "operator_id": "includes",
                 "values": ["Health Care", "Artificial Intelligence"]},
                {"type": "predicate", "field_id": "last_funding_at",
                 "operator_id": "gte", "values": ["2024-01-01"]},
                {"type": "predicate", "field_id": "last_funding_type",
                 "operator_id": "includes",
                 "values": ["series_a"]},
            ],
            "order": [{"field_id": "last_funding_at", "sort": "desc"}],
            "limit": 25,
        },
    ]

    def __init__(self, api_key: str):
        self.api_key = api_key
        self.session = requests.Session()
        self.session.params = {"user_key": api_key}  # type: ignore[assignment]

    def find_healthcare_ai_companies(self) -> List[Dict]:
        results: List[Dict] = []
        for body in self.SEARCHES:
            try:
                resp = self.session.post(
                    f"{self.BASE_URL}/searches/organizations",
                    json=body,
                    timeout=15,
                )
                resp.raise_for_status()
                for entity in resp.json().get("entities", []):
                    company = self._parse_entity(entity)
                    if company:
                        results.append(company)
                time.sleep(1)
            except requests.HTTPError as e:
                if e.response.status_code == 401:
                    raise RuntimeError("Invalid Crunchbase API key") from e
                if e.response.status_code == 429:
                    time.sleep(10)
            except Exception:
                continue
        return results

    def _parse_entity(self, entity: Dict) -> Optional[Dict]:
        props = entity.get("properties", {})
        name = props.get("identifier", {}).get("value")
        if not name:
            return None

        funding_round = self.FUNDING_ROUND_MAP.get(props.get("last_funding_type", ""))

        funding_total = props.get("funding_total", {})
        funding_amount = None
        if isinstance(funding_total, dict):
            usd = funding_total.get("value_usd", 0) or 0
            if usd >= 1_000_000_000:
                funding_amount = f"${usd / 1_000_000_000:.1f}B"
            elif usd >= 1_000_000:
                funding_amount = f"${usd / 1_000_000:.0f}M"

        permalink = entity.get("identifier", {}).get("permalink", "")

        return {
            "name": name,
            "description": props.get("short_description"),
            "funding_amount": funding_amount,
            "funding_round": funding_round,
            "funding_date": props.get("last_funding_at"),
            "website": props.get("homepage_url"),
            "crunchbase_url": f"https://www.crunchbase.com/organization/{permalink}" if permalink else None,
            "source": "crunchbase",
            "source_url": None,
        }
