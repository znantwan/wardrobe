#!/usr/bin/env python3
"""
Healthcare AI Recruiting Intelligence Tool

Finds companies in Healthcare AI that have recently raised significant funding
and have Stanford GSB alumni, then compiles contact information for outreach.

Usage:
    python main.py               # Show current database
    python main.py --discover    # Run full discovery pipeline
    python main.py --export leads.csv
"""
import argparse
import sys

from rich.console import Console
from rich.panel import Panel
from rich.progress import BarColumn, Progress, SpinnerColumn, TextColumn
from rich.table import Table

console = Console()


def banner():
    console.print(Panel.fit(
        "[bold cyan]Healthcare AI Recruiting Intelligence Tool[/bold cyan]\n"
        "[dim]Finds companies like Qualified Health, Ambience Health & HeartFlow[/dim]\n"
        "[dim]with recent funding and Stanford GSB alumni[/dim]",
        border_style="cyan"
    ))


def run_discovery(db, config):
    """Run the full 3-step discovery pipeline."""
    from scrapers.crunchbase import CrunchbaseScraper
    from scrapers.news import NewsScraper
    from scrapers.alumni import AlumniScraper
    from enrichers.contacts import ContactEnricher

    total_new_companies = 0
    total_new_contacts = 0

    # ── Step 1: Discover companies ────────────────────────────────────────────
    console.print("\n[bold]Step 1 of 3 — Company Discovery[/bold]")
    companies_found = []

    with Progress(SpinnerColumn(), TextColumn("{task.description}"), console=console) as p:
        # TechCrunch / MobiHealthNews RSS + optional NewsAPI (no key needed for RSS)
        t = p.add_task("Scanning funding news (RSS feeds + NewsAPI)...", total=None)
        news = NewsScraper(config.newsapi_key)
        found = news.find_recent_funding_announcements()
        companies_found.extend(found)
        p.update(t, description=f"[green]News:[/green] {len(found)} candidates found")

        # Crunchbase (requires key)
        if config.crunchbase_api_key:
            t = p.add_task("Searching Crunchbase...", total=None)
            cb = CrunchbaseScraper(config.crunchbase_api_key)
            found = cb.find_healthcare_ai_companies()
            companies_found.extend(found)
            p.update(t, description=f"[green]Crunchbase:[/green] {len(found)} candidates found")
        else:
            console.print("  [dim]Crunchbase: skipped (add CRUNCHBASE_API_KEY to .env)[/dim]")

    new_count = db.upsert_companies(companies_found)
    total_new_companies = new_count
    console.print(
        f"  [green]✓[/green] {len(companies_found)} candidates scanned, "
        f"[bold]{new_count} new[/bold] added to database"
    )

    # ── Step 2: Find Stanford GSB alumni ──────────────────────────────────────
    console.print("\n[bold]Step 2 of 3 — Stanford GSB Alumni Search[/bold]")

    if not config.google_api_key and not config.serpapi_key:
        console.print(
            "  [yellow]⚠[/yellow]  No search API configured — alumni search skipped.\n"
            "  [dim]Add GOOGLE_API_KEY + GOOGLE_CX_ID  or  SERPAPI_KEY to .env to enable.[/dim]"
        )
    else:
        alumni_scraper = AlumniScraper(
            google_api_key=config.google_api_key,
            google_cx_id=config.google_cx_id,
            serpapi_key=config.serpapi_key,
        )
        stale = db.get_companies_needing_alumni_search()
        console.print(f"  Searching {len(stale)} companies (recently-searched ones are skipped)")

        with Progress(
            SpinnerColumn(), TextColumn("{task.description}"), BarColumn(), console=console
        ) as p:
            t = p.add_task("Searching for alumni...", total=len(stale))
            for company in stale:
                alumni = alumni_scraper.find_stanford_gsb_alumni(company)
                new_count = db.upsert_contacts(alumni)
                total_new_contacts += new_count
                db.log_alumni_search(company["id"])
                p.update(t, description=f"Searching alumni... [{company['name']}]")
                p.advance(t)

        console.print(f"  [green]✓[/green] [bold]{total_new_contacts} new contacts[/bold] found")

    # ── Step 3: Enrich contact emails ─────────────────────────────────────────
    console.print("\n[bold]Step 3 of 3 — Email Enrichment[/bold]")

    if not config.hunter_api_key:
        console.print(
            "  [dim]Hunter.io: skipped (add HUNTER_API_KEY to .env to enable email discovery)[/dim]"
        )
    else:
        enricher = ContactEnricher(config.hunter_api_key)
        unenriched = db.get_contacts_without_email(limit=25)  # free tier: 25/month

        with Progress(SpinnerColumn(), TextColumn("{task.description}"), console=console) as p:
            t = p.add_task(f"Finding emails for {len(unenriched)} contacts...", total=None)
            enriched = 0
            for contact in unenriched:
                email = enricher.find_email(contact)
                if email:
                    db.update_contact_email(contact["id"], email)
                    enriched += 1

        console.print(
            f"  [green]✓[/green] Found emails for [bold]{enriched}/{len(unenriched)}[/bold] contacts"
        )

    console.print(
        f"\n[bold green]Discovery complete![/bold green]  "
        f"+{total_new_companies} companies  +{total_new_contacts} contacts\n"
    )


def show_summary(db):
    """Render current database as rich tables."""
    companies = db.get_companies_with_contact_count()
    contacts = db.get_all_contacts_with_company()

    if not companies and not contacts:
        console.print(
            "\n[yellow]Database is empty. "
            "Run  python main.py --discover  to start finding opportunities.[/yellow]"
        )
        return

    if companies:
        t = Table(
            title=f"Healthcare AI Companies ({len(companies)})",
            show_lines=True,
            header_style="bold cyan",
        )
        t.add_column("Company", width=26)
        t.add_column("Funding", width=11, justify="right")
        t.add_column("Round", width=9)
        t.add_column("Date", width=11)
        t.add_column("GSB Alumni", width=10, justify="center")
        t.add_column("Source", width=10)

        for c in companies:
            has_contacts = c["contact_count"] > 0
            t.add_row(
                f"[bold]{c['name']}[/bold]" if has_contacts else c["name"],
                c["funding_amount"] or "—",
                c["funding_round"] or "—",
                (c["funding_date"] or "—")[:10],
                f"[green]{c['contact_count']}[/green]" if has_contacts else "0",
                c["source"] or "—",
            )
        console.print()
        console.print(t)

    if contacts:
        t = Table(
            title=f"Stanford GSB Contacts ({len(contacts)})",
            show_lines=True,
            header_style="bold yellow",
        )
        t.add_column("Name", width=24)
        t.add_column("Company", width=24)
        t.add_column("Title", width=30)
        t.add_column("Email", width=30, style="green")
        t.add_column("LinkedIn", width=38)

        for c in contacts:
            t.add_row(
                c["name"],
                c["company_name"],
                c["title"] or "—",
                c["email"] or "[dim]not found[/dim]",
                c["linkedin_url"] or "—",
            )
        console.print()
        console.print(t)

    total_with_email = sum(1 for c in contacts if c.get("email"))
    console.print(
        f"\n[dim]Database: {db.db_path}  |  "
        f"{len(companies)} companies · {len(contacts)} contacts · "
        f"{total_with_email} with email[/dim]"
    )


def export_csv(db, output_file: str):
    """Export all contacts with company info to CSV."""
    import csv

    contacts = db.get_all_contacts_with_company()
    if not contacts:
        console.print("[yellow]No contacts to export.[/yellow]")
        return

    with open(output_file, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=contacts[0].keys())
        writer.writeheader()
        writer.writerows(contacts)

    console.print(f"[green]✓[/green] Exported {len(contacts)} contacts to [bold]{output_file}[/bold]")


def main():
    parser = argparse.ArgumentParser(
        description="Healthcare AI Recruiting Intelligence Tool",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "examples:\n"
            "  python main.py                     # show current database\n"
            "  python main.py --discover          # run full discovery pipeline\n"
            "  python main.py --discover --show   # discover then display\n"
            "  python main.py --export leads.csv  # export contacts to CSV\n"
        ),
    )
    parser.add_argument("--discover", action="store_true", help="Run full discovery pipeline")
    parser.add_argument("--show", action="store_true", help="Show database summary")
    parser.add_argument("--export", metavar="FILE.csv", help="Export contacts to CSV")
    parser.add_argument(
        "--reset", action="store_true", help="Reset database (requires confirmation)"
    )
    parser.add_argument(
        "--db",
        default="recruiting.db",
        metavar="PATH",
        help="SQLite database path (default: recruiting.db)",
    )
    args = parser.parse_args()

    banner()

    from config import Config
    from database import Database

    config = Config()
    db = Database(args.db)
    db.initialize()

    if args.reset:
        confirm = input("\nThis will DELETE all data. Type 'yes' to confirm: ")
        if confirm.strip().lower() == "yes":
            db.reset()
            console.print("[yellow]Database reset complete.[/yellow]")
        else:
            console.print("[dim]Reset cancelled.[/dim]")
        return

    if args.discover:
        run_discovery(db, config)

    # Always show summary unless only exporting
    if args.show or not args.export:
        show_summary(db)

    if args.export:
        export_csv(db, args.export)


if __name__ == "__main__":
    main()
