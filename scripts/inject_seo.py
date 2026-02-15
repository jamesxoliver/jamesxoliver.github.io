#!/usr/bin/env python3
"""Post-build SEO: inject JSON-LD structured data and canonical URLs into HTML."""

import json
import re
from pathlib import Path

SITE_DIR = Path("site")
SITE_URL = "https://jamesxoliver.github.io"


def extract_meta(html: str) -> dict:
    """Extract title, description, and date from built HTML."""
    title_match = re.search(r"<title>(.+?)</title>", html)
    title = title_match.group(1).split(" - ")[0].strip() if title_match else ""

    desc_match = re.search(r'<meta name="description" content="(.+?)"', html)
    description = desc_match.group(1) if desc_match else ""

    date_match = re.search(r"Published:\s*(\d{4}-\d{2}-\d{2})", html)
    date = date_match.group(1) if date_match else ""

    updated_match = re.search(r"Updated:\s*(\d{4}-\d{2}-\d{2})", html)
    updated = updated_match.group(1) if updated_match else date

    return {"title": title, "description": description, "date": date, "updated": updated}


def build_jsonld(meta: dict, url: str) -> str:
    """Build JSON-LD Article structured data."""
    data = {
        "@context": "https://schema.org",
        "@type": "Article",
        "headline": meta["title"],
        "author": {
            "@type": "Person",
            "name": "James Oliver",
            "url": SITE_URL,
        },
        "publisher": {
            "@type": "Person",
            "name": "James Oliver",
        },
        "mainEntityOfPage": {
            "@type": "WebPage",
            "@id": url,
        },
    }
    if meta["description"]:
        data["description"] = meta["description"]
    if meta["date"]:
        data["datePublished"] = meta["date"]
    if meta["updated"]:
        data["dateModified"] = meta["updated"]

    return json.dumps(data, ensure_ascii=False)


def inject_into_html(html_path: Path):
    """Inject JSON-LD and canonical URL into an HTML file."""
    html = html_path.read_text(errors="replace")

    # Compute canonical URL from file path
    rel = html_path.relative_to(SITE_DIR)
    if rel.name == "index.html" and rel.parent != Path("."):
        canonical = f"{SITE_URL}/{rel.parent}/"
    elif rel.name == "index.html":
        canonical = f"{SITE_URL}/"
    else:
        canonical = f"{SITE_URL}/{rel}"

    # Skip if already injected
    if "application/ld+json" in html:
        return

    meta = extract_meta(html)

    # Build injection block
    injections = []

    # Canonical URL
    if f'<link rel="canonical"' not in html:
        injections.append(f'<link rel="canonical" href="{canonical}" />')

    # Open Graph tags (supplement what MkDocs Material generates)
    if 'og:type' not in html:
        injections.append('<meta property="og:type" content="article" />')
    if 'og:site_name' not in html:
        injections.append('<meta property="og:site_name" content="James Oliver" />')
    if meta["date"] and 'article:published_time' not in html:
        injections.append(f'<meta property="article:published_time" content="{meta["date"]}" />')
    if meta["updated"] and 'article:modified_time' not in html:
        injections.append(f'<meta property="article:modified_time" content="{meta["updated"]}" />')
    if 'article:author' not in html:
        injections.append('<meta property="article:author" content="James Oliver" />')

    # Twitter card
    if 'twitter:card' not in html:
        injections.append('<meta name="twitter:card" content="summary" />')

    # JSON-LD structured data (only for essay pages)
    if "/essays/" in str(html_path):
        jsonld = build_jsonld(meta, canonical)
        injections.append(f'<script type="application/ld+json">{jsonld}</script>')

    if not injections:
        return

    injection_block = "\n    ".join(injections)
    html = html.replace("</head>", f"    {injection_block}\n  </head>")
    html_path.write_text(html)


def main():
    count = 0
    for html_file in SITE_DIR.rglob("*.html"):
        inject_into_html(html_file)
        count += 1
    print(f"SEO injected into {count} HTML files")


if __name__ == "__main__":
    main()
