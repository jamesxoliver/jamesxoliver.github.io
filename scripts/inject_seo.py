#!/usr/bin/env python3
"""Post-build SEO: inject JSON-LD, canonical URLs, RSS feed, sitemap lastmod."""

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from xml.etree import ElementTree as ET

SITE_DIR = Path("site")
SITE_URL = "https://jamesxoliver.github.io"

# Google Search Console verification (URL prefix method).
# Set this to your verification meta tag content value, e.g.:
#   SEARCH_CONSOLE_VERIFICATION = "your-verification-code-here"
# Then inject_seo.py will add <meta name="google-site-verification" content="...">
# to every page. Leave as None to skip.
SEARCH_CONSOLE_VERIFICATION = "Cm624WsCoCiwmhsfLdbV-yrMIAtb4R9b6QUa_aG3K_Q"


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

    # Google Search Console verification
    if SEARCH_CONSOLE_VERIFICATION and 'google-site-verification' not in html:
        injections.append(
            f'<meta name="google-site-verification" content="{SEARCH_CONSOLE_VERIFICATION}" />'
        )

    # Canonical URL
    if f'<link rel="canonical"' not in html:
        injections.append(f'<link rel="canonical" href="{canonical}" />')

    # RSS feed link
    if 'application/rss+xml' not in html:
        injections.append(
            f'<link rel="alternate" type="application/rss+xml" title="James Oliver" href="{SITE_URL}/feed.xml" />'
        )

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


def generate_rss_feed():
    """Generate an RSS 2.0 feed from essay HTML files."""
    essays = []

    for html_file in sorted(SITE_DIR.rglob("*.html")):
        if "/essays/" not in str(html_file):
            continue
        html = html_file.read_text(errors="replace")
        meta = extract_meta(html)
        if not meta["title"] or not meta["date"]:
            continue

        rel = html_file.relative_to(SITE_DIR)
        if rel.name == "index.html" and rel.parent != Path("."):
            url = f"{SITE_URL}/{rel.parent}/"
        else:
            url = f"{SITE_URL}/{rel}"

        essays.append({
            "title": meta["title"],
            "description": meta["description"],
            "url": url,
            "date": meta["date"],
            "updated": meta["updated"],
        })

    # Sort by date descending
    essays.sort(key=lambda x: x["date"], reverse=True)

    # Build RSS XML
    now = datetime.now(timezone.utc).strftime("%a, %d %b %Y %H:%M:%S +0000")
    items = []
    for e in essays[:50]:  # cap at 50 items
        pub_date = datetime.strptime(e["date"], "%Y-%m-%d").strftime("%a, %d %b %Y 00:00:00 +0000")
        desc_escaped = e["description"].replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        title_escaped = e["title"].replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        items.append(f"""    <item>
      <title>{title_escaped}</title>
      <link>{e["url"]}</link>
      <guid>{e["url"]}</guid>
      <pubDate>{pub_date}</pubDate>
      <description>{desc_escaped}</description>
      <author>James Oliver</author>
    </item>""")

    rss = f"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:atom="http://www.w3.org/2005/Atom">
  <channel>
    <title>James Oliver</title>
    <link>{SITE_URL}</link>
    <description>Essays on systems, science, and structure — finding simplicity in complexity.</description>
    <language>en-us</language>
    <lastBuildDate>{now}</lastBuildDate>
    <atom:link href="{SITE_URL}/feed.xml" rel="self" type="application/rss+xml" />
{chr(10).join(items)}
  </channel>
</rss>"""

    (SITE_DIR / "feed.xml").write_text(rss)
    print(f"RSS feed generated with {len(items)} items")


def inject_sitemap_lastmod():
    """Inject <lastmod> dates into sitemap.xml using essay publication dates."""
    sitemap_path = SITE_DIR / "sitemap.xml"
    if not sitemap_path.exists():
        return

    # Collect date info from essay HTML files
    url_dates = {}
    for html_file in SITE_DIR.rglob("*.html"):
        html = html_file.read_text(errors="replace")
        meta = extract_meta(html)
        date_str = meta.get("updated") or meta.get("date")
        if not date_str:
            continue

        rel = html_file.relative_to(SITE_DIR)
        if rel.name == "index.html" and rel.parent != Path("."):
            url = f"{SITE_URL}/{rel.parent}/"
        elif rel.name == "index.html":
            url = f"{SITE_URL}/"
        else:
            url = f"{SITE_URL}/{rel}"
        url_dates[url] = date_str

    if not url_dates:
        return

    # Parse and update sitemap
    ET.register_namespace("", "http://www.sitemaps.org/schemas/sitemap/0.9")
    tree = ET.parse(sitemap_path)
    root = tree.getroot()
    ns = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}

    updated = 0
    for url_elem in root.findall("sm:url", ns):
        loc = url_elem.find("sm:loc", ns)
        if loc is None:
            continue
        loc_text = loc.text
        if loc_text in url_dates:
            lastmod = url_elem.find("sm:lastmod", ns)
            if lastmod is None:
                lastmod = ET.SubElement(url_elem, "lastmod")
            lastmod.text = url_dates[loc_text]
            updated += 1

    tree.write(sitemap_path, xml_declaration=True, encoding="UTF-8")
    print(f"Sitemap updated with {updated} lastmod dates")


def main():
    count = 0
    for html_file in SITE_DIR.rglob("*.html"):
        inject_into_html(html_file)
        count += 1
    print(f"SEO injected into {count} HTML files")

    generate_rss_feed()
    inject_sitemap_lastmod()


if __name__ == "__main__":
    main()
