# Healthcare AI Recruiting Intelligence Tool

Automatically finds **Healthcare AI companies** with recent funding that have
**Stanford GSB alumni**, then collects contact information so you can reach
out about internships.

Targets companies in the same space as:
- **Qualified Health** — prior authorization AI
- **Ambience Health** — ambient clinical documentation AI  
- **HeartFlow** — cardiac imaging / computational AI

---

## How It Works

1. **Discover** — Scrapes TechCrunch/MobiHealthNews RSS feeds (always free)
   plus optional Crunchbase and NewsAPI for Healthcare AI companies that have
   recently announced Series A–E funding.

2. **Alumni Search** — For each company, searches LinkedIn profiles via
   Google Custom Search API or SerpAPI to find people who list Stanford GSB
   in their background.

3. **Email Enrichment** — Uses Hunter.io to find email addresses for the
   discovered alumni contacts.

4. **Live Database** — Everything is stored in a local SQLite file
   (`recruiting.db`). Re-running the tool adds only *new* data — no
   duplicates, no overwriting existing info.

---

## Quick Start

```bash
cd recruiting
pip install -r requirements.txt
cp .env.example .env
# edit .env and add your API keys (see below)
python main.py --discover
```

---

## Commands

| Command | Description |
|---------|-------------|
| `python main.py` | Show current database |
| `python main.py --discover` | Run full discovery pipeline |
| `python main.py --discover --show` | Discover then display results |
| `python main.py --export leads.csv` | Export all contacts to CSV |
| `python main.py --reset` | Wipe database (asks for confirmation) |
| `python main.py --db myfile.db` | Use a custom database file |

---

## API Keys

All keys are **optional** — the tool works without any keys (using only free
RSS feeds), but each key you add unlocks a richer data source.

### Free / Recommended

| Key | Where to Get | What It Unlocks |
|-----|-------------|------------------|
| `NEWSAPI_KEY` | [newsapi.org](https://newsapi.org) — free tier | Full-text news search (100 req/day) |
| `GOOGLE_API_KEY` + `GOOGLE_CX_ID` | [console.cloud.google.com](https://console.cloud.google.com) + [programmablesearchengine.google.com](https://programmablesearchengine.google.com) — free tier | LinkedIn alumni search (100 queries/day) |
| `HUNTER_API_KEY` | [hunter.io](https://hunter.io) — free tier | Email discovery (25 searches/month) |

### Paid / Optional

| Key | Where to Get | What It Unlocks |
|-----|-------------|------------------|
| `CRUNCHBASE_API_KEY` | [crunchbase.com/account/api](https://www.crunchbase.com/account/api) | Structured company + funding data |
| `SERPAPI_KEY` | [serpapi.com](https://serpapi.com) | More reliable LinkedIn search (~$50/mo) |

### Setting Up Google Custom Search

1. Go to [console.cloud.google.com](https://console.cloud.google.com)
2. Create a project → enable **Custom Search JSON API** → create an API key → copy as `GOOGLE_API_KEY`
3. Go to [programmablesearchengine.google.com](https://programmablesearchengine.google.com)
4. Create a new engine → set "Search the entire web" → copy the CX ID as `GOOGLE_CX_ID`

---

## Database Schema

The SQLite database (`recruiting.db`) has two main tables:

**`companies`** — Healthcare AI companies with recent funding  
**`contacts`** — Stanford GSB alumni at those companies

Deduplication keys:
- Companies: `normalized_name` (lowercase, alphanumeric only)
- Contacts: `(company_id, normalized_name)` pair

---

## File Structure

```
recruiting/
├── main.py                  # CLI entry point
├── config.py                # API key loading from .env
├── database.py              # SQLite persistence layer
├── scrapers/
│   ├── crunchbase.py        # Crunchbase API (requires key)
│   ├── news.py              # RSS + NewsAPI funding news
│   └── alumni.py           # LinkedIn search via Google/SerpAPI
├── enrichers/
│   └── contacts.py         # Hunter.io email discovery
├── requirements.txt
├── .env.example             # Copy to .env and fill in keys
└── README.md
```

---

## Typical Workflow

```bash
# First run — discover everything available
python main.py --discover

# Export to CSV for your outreach tracker
python main.py --export leads.csv

# Run weekly to pick up new companies and contacts
python main.py --discover
```

The tool remembers which companies it has already searched for alumni
(re-searches every 7 days to catch new hires) and never creates duplicate
company or contact records.
