import os

from dotenv import load_dotenv
from rich.console import Console

console = Console()
load_dotenv()


class Config:
    """
    Loads API keys from environment / .env file.
    All keys are optional — the tool degrades gracefully when keys are absent.

    Data sources by key:
      CRUNCHBASE_API_KEY  — company search + funding data (crunchbase.com/account/api)
      NEWSAPI_KEY         — recent funding news articles   (newsapi.org)
      GOOGLE_API_KEY      — LinkedIn alumni search via Google Custom Search
      GOOGLE_CX_ID        — Google Custom Search Engine ID (programmablesearchengine.google.com)
      SERPAPI_KEY         — alternative to Google CSE for LinkedIn search (serpapi.com)
      HUNTER_API_KEY      — email discovery per contact   (hunter.io)
    """

    def __init__(self):
        self.crunchbase_api_key = os.getenv("CRUNCHBASE_API_KEY")
        self.newsapi_key = os.getenv("NEWSAPI_KEY")
        self.google_api_key = os.getenv("GOOGLE_API_KEY")
        self.google_cx_id = os.getenv("GOOGLE_CX_ID")
        self.serpapi_key = os.getenv("SERPAPI_KEY")
        self.hunter_api_key = os.getenv("HUNTER_API_KEY")
        self._print_status()

    def _print_status(self):
        active, missing = [], []
        checks = [
            ("Crunchbase", self.crunchbase_api_key, "CRUNCHBASE_API_KEY"),
            ("NewsAPI", self.newsapi_key, "NEWSAPI_KEY"),
            (
                "Google Search",
                self.google_api_key and self.google_cx_id,
                "GOOGLE_API_KEY + GOOGLE_CX_ID",
            ),
            ("SerpAPI", self.serpapi_key, "SERPAPI_KEY"),
            ("Hunter.io", self.hunter_api_key, "HUNTER_API_KEY"),
        ]
        for name, value, key in checks:
            (active if value else missing).append((name, key))

        if active:
            console.print(f"[dim]Active sources: {', '.join(n for n, _ in active)}[/dim]")
        if missing:
            console.print(
                f"[dim]Not configured (optional): "
                f"{', '.join(k for _, k in missing)}[/dim]"
            )
        # TechCrunch RSS is always active (no key needed)
        console.print("[dim]TechCrunch / MobiHealthNews RSS: always active (no key needed)[/dim]")
