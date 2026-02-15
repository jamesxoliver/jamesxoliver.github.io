#!/usr/bin/env python3
"""Convert .tex files from the papers repo into MkDocs-ready markdown."""

import os
import re
import subprocess
import yaml
from pathlib import Path

PAPERS_DIR = Path(os.environ.get("PAPERS_DIR", "papers"))
DOCS_DIR = Path("docs/essays")
SKIP_DIRS = {"0_Format"}


def get_git_dates(tex_path: Path) -> tuple[str | None, str | None]:
    """Get first commit date (published) and last commit date (updated) from git log."""
    try:
        # First commit date (published)
        result = subprocess.run(
            ["git", "log", "--diff-filter=A", "--follow", "--format=%aI", "--", str(tex_path)],
            capture_output=True, text=True, cwd=PAPERS_DIR,
        )
        published = None
        if result.returncode == 0 and result.stdout.strip():
            dates = result.stdout.strip().split("\n")
            published = dates[-1][:10]  # earliest date, YYYY-MM-DD

        # Last commit date (updated)
        result = subprocess.run(
            ["git", "log", "-1", "--format=%aI", "--", str(tex_path)],
            capture_output=True, text=True, cwd=PAPERS_DIR,
        )
        updated = None
        if result.returncode == 0 and result.stdout.strip():
            updated = result.stdout.strip()[:10]

        return published, updated
    except Exception:
        return None, None


def extract_title(tex_content: str) -> str:
    """Extract the document title from \\newcommand{\\DocumentTitle}{...}."""
    match = re.search(r"\\newcommand\{\\DocumentTitle\}\{(.+?)\}", tex_content)
    if match:
        title = match.group(1)
        # Clean up LaTeX formatting in title
        title = title.replace("--", "\u2013")
        title = re.sub(r"\\textbf\{(.+?)\}", r"\1", title)
        title = re.sub(r"\\emph\{(.+?)\}", r"\1", title)
        return title
    return None


def extract_subtitle(tex_content: str) -> str:
    """Extract subtitle from \\newcommand{\\DocumentSubtitle}{...}."""
    match = re.search(r"\\newcommand\{\\DocumentSubtitle\}\{(.+?)\}", tex_content)
    if match:
        sub = match.group(1).strip()
        if sub and sub != "Subtitle" and sub != "":
            return sub
    return None


def tex_to_md(tex_path: Path) -> str | None:
    """Convert a .tex file to markdown using pandoc."""
    result = subprocess.run(
        [
            "pandoc",
            str(tex_path),
            "-f", "latex",
            "-t", "markdown-simple_tables-multiline_tables-grid_tables",
            "--wrap=none",
            "--markdown-headings=atx",
            "--shift-heading-level-by=1",
        ],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        print(f"  pandoc error for {tex_path}: {result.stderr[:200]}")
        return None
    return result.stdout


def extract_first_paragraph(md_content: str) -> str:
    """Extract the first real paragraph from markdown content for meta description."""
    for line in md_content.split("\n"):
        line = line.strip()
        # Skip headings, empty lines, metadata, images, lists
        if not line or line.startswith("#") or line.startswith("!") or line.startswith("-"):
            continue
        if line.startswith("**") and ("james oliver" in line.lower() or "author" in line.lower()):
            continue
        if line.startswith("*") and line.endswith("*"):
            continue
        if line.startswith("<") or line.startswith(":::") or line.startswith("---"):
            continue
        # Clean markdown formatting for plain text description
        desc = re.sub(r"\$[^$]+\$", "", line)  # remove inline math
        desc = re.sub(r"\*\*(.+?)\*\*", r"\1", desc)  # bold
        desc = re.sub(r"\*(.+?)\*", r"\1", desc)  # italic
        desc = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", desc)  # links
        desc = desc.strip()
        if len(desc) > 30:
            # Truncate to ~155 chars for meta description
            if len(desc) > 155:
                desc = desc[:152].rsplit(" ", 1)[0] + "..."
            return desc
    return ""


def estimate_reading_time(md_content: str) -> int:
    """Estimate reading time in minutes from markdown content."""
    # Strip markdown formatting for word count
    text = re.sub(r"\$\$[^$]*\$\$", " equation ", md_content)  # display math
    text = re.sub(r"\$[^$]+\$", " equation ", text)  # inline math
    text = re.sub(r"!\[.*?\]\(.*?\)", "", text)  # images
    text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)  # links
    text = re.sub(r"[#*_`~>|]", "", text)  # markdown chars
    text = re.sub(r"-{3,}", "", text)  # horizontal rules
    words = len(text.split())
    minutes = max(1, round(words / 200))
    return minutes


def extract_related_essays(tex_content: str) -> list[str]:
    """Extract related essay slugs from \\RelatedEssays{slug1, slug2}."""
    match = re.search(r"\\RelatedEssays\{(.+?)\}", tex_content)
    if match:
        slugs = [s.strip() for s in match.group(1).split(",") if s.strip()]
        return slugs
    return []


def clean_md(md_content: str, title: str, subtitle: str | None,
             published: str | None = None, updated: str | None = None,
             related_slugs: list[str] | None = None,
             slug_to_info: dict | None = None) -> str:
    """Clean up pandoc output for MkDocs."""
    lines = md_content.split("\n")
    cleaned = []
    skip_until_content = True

    for line in lines:
        # Skip pandoc-generated title block at the top
        if skip_until_content:
            if line.startswith("# ") or (line.strip() == "" and not cleaned):
                continue
            if line.strip().startswith("**") and any(
                x in line.lower() for x in ["james oliver", "author"]
            ):
                continue
            if line.strip() == "":
                if not cleaned:
                    continue
            skip_until_content = False

        cleaned.append(line)

    md = "\n".join(cleaned).strip()

    # Clean up pandoc artifacts
    md = re.sub(r"\n{3,}", "\n\n", md)
    md = re.sub(r"\s*\{#[^}]*\}", "", md)
    md = re.sub(r"^:{2,}\s*tcolorbox\s*$", "", md, flags=re.MULTILINE)
    md = re.sub(r"^:{2,}\s*$", "", md, flags=re.MULTILINE)
    md = re.sub(r"\[@([a-zA-Z0-9_]+)\]", "", md)
    md = re.sub(r"\\\\\s*$", "", md, flags=re.MULTILINE)
    md = re.sub(r"\n{3,}", "\n\n", md)

    # Fix em dashes: triple hyphens between words → —
    md = re.sub(r"(?<=\w)---(?=\w)", "\u2014", md)

    # Fix escaped quotes from pandoc
    md = md.replace('\\"', '"')

    # Remove stray \\ line breaks (mid-text, not in math)
    md = re.sub(r"(?<!\$)\\\\(?!\$)", " ", md)

    # Convert table captions to italic text below table
    md = re.sub(r"^: (.+)$", r"*\1*", md, flags=re.MULTILINE)

    # Collapse blank lines between list items
    prev = None
    while prev != md:
        prev = md
        md = re.sub(r"(\n-   .+)\n\n(-   )", r"\1\n\2", md)
        md = re.sub(r"(\n\d+\.\s+.+)\n\n(\d+\.\s+)", r"\1\n\2", md)

    # Extract meta description from first paragraph
    description = extract_first_paragraph(md)
    if not description and subtitle:
        description = subtitle

    # Reading time
    reading_time = estimate_reading_time(md)

    # Build YAML front matter for SEO
    front_matter = "---\n"
    # Escape quotes in description/title for YAML
    safe_desc = description.replace('"', '\\"') if description else ""
    safe_title = title.replace('"', '\\"')
    front_matter += f'description: "{safe_desc}"\n'
    front_matter += f'author: "James Oliver"\n'
    if published:
        front_matter += f'date: {published}\n'
    front_matter += "---\n\n"

    # Build visible header
    header = f"# {title}\n\n"
    if subtitle:
        header += f"*{subtitle}*\n\n"
    header += "**James Oliver**"

    if published:
        date_line = f"Published: {published}"
        if updated and updated != published:
            date_line += f" · Updated: {updated}"
        date_line += f" · {reading_time} min read"
        header += f"  \n<small>{date_line}</small>"
    else:
        header += f"  \n<small>{reading_time} min read</small>"

    header += "\n"

    # Build "See also" section from related essays
    see_also = ""
    if related_slugs and slug_to_info:
        links = []
        for rs in related_slugs:
            if rs in slug_to_info:
                info = slug_to_info[rs]
                links.append(f"[{info['title']}](/{info['path']})")
        if links:
            see_also = "\n\n---\n\n**See also:** " + " · ".join(links) + "\n"

    return front_matter + header + "\n---\n\n" + md + see_also + "\n"


def slug(name: str) -> str:
    """Convert a filename to a URL-friendly slug."""
    s = name.replace(".tex", "")
    s = s.lower()
    s = re.sub(r"[^a-z0-9]+", "-", s)
    s = s.strip("-")
    return s


def build_nav(essay_tree: dict) -> list:
    """Build nested nav structure for mkdocs.yml from the essay tree.

    essay_tree is: {top_category: {sub_or_none: [(title, path)]}}
    """
    nav = []
    for top_cat in sorted(essay_tree.keys()):
        subs = essay_tree[top_cat]
        cat_items = []

        # Articles directly under the top category (no subcategory)
        if None in subs:
            for title, path in sorted(subs[None]):
                cat_items.append({title: path})

        # Subcategories
        for sub_cat in sorted(k for k in subs if k is not None):
            sub_items = [{title: path} for title, path in sorted(subs[sub_cat])]
            cat_items.append({sub_cat: sub_items})

        nav.append({top_cat: cat_items})
    return nav


def generate_homepage(essay_tree: dict, essays: list):
    """Generate docs/index.md with recent section and collapsible categories."""
    lines = [
        "# James Oliver",
        "",
        "Finding simplicity in complexity.",
        "",
        "---",
        "",
    ]

    # Recent essays — top 5 by date
    dated = [e for e in essays if e.get("published")]
    dated.sort(key=lambda e: e["published"], reverse=True)
    recent = dated[:5]

    if recent:
        lines.append("**Recent**")
        lines.append("")
        for e in recent:
            lines.append(f"- [{e['title']}]({e['nav_path']}) <small>{e['published']}</small>")
        lines.append("")
        lines.append("---")
        lines.append("")

    for top_cat in sorted(essay_tree.keys()):
        subs = essay_tree[top_cat]
        total = sum(len(v) for v in subs.values())

        lines.append(f'??? "{top_cat}"')
        lines.append("")

        # Articles directly under the top category
        if None in subs:
            for title, path in sorted(subs[None]):
                lines.append(f"    - [{title}]({path})")
            lines.append("")

        # Subcategories as nested dropdowns
        for sub_cat in sorted(k for k in subs if k is not None):
            lines.append(f'    ??? "{sub_cat}"')
            lines.append("")
            for title, path in sorted(subs[sub_cat]):
                lines.append(f"        - [{title}]({path})")
            lines.append("")

        lines.append("")

    homepage = Path("docs/index.md")
    homepage.write_text("\n".join(lines))
    print(f"Homepage generated with {len(essay_tree)} categories")


def main():
    # Clean output directory
    if DOCS_DIR.exists():
        import shutil
        shutil.rmtree(DOCS_DIR)
    DOCS_DIR.mkdir(parents=True, exist_ok=True)

    # Rename map for cleaner display of top-level dirs
    RENAME = {"1_Foundations": "Foundations"}

    # --- Pass 1: collect metadata for all essays (needed for cross-links) ---
    essays = []  # list of dicts with all metadata
    slug_to_info = {}  # file_slug -> {title, path} for related-essay lookups

    for tex_file in sorted(PAPERS_DIR.rglob("*.tex")):
        rel = tex_file.relative_to(PAPERS_DIR)
        parts = rel.parts

        if parts[0] in SKIP_DIRS:
            continue
        if "template" in tex_file.name.lower():
            continue

        tex_content = tex_file.read_text(errors="replace")

        title = extract_title(tex_content)
        if not title or title == "Title":
            continue

        subtitle = extract_subtitle(tex_content)
        related_slugs = extract_related_essays(tex_content)
        published, updated = get_git_dates(rel)

        top_category = RENAME.get(parts[0], parts[0])
        sub_category = None
        if len(parts) > 2:
            sub_category = parts[1]

        file_slug_val = slug(tex_file.name)
        top_slug = slug(top_category)
        if sub_category:
            sub_slug = slug(sub_category)
            nav_path = f"essays/{top_slug}/{sub_slug}/{file_slug_val}.md"
        else:
            nav_path = f"essays/{top_slug}/{file_slug_val}.md"

        info = {
            "tex_file": tex_file,
            "rel": rel,
            "title": title,
            "subtitle": subtitle,
            "published": published,
            "updated": updated,
            "top_category": top_category,
            "sub_category": sub_category,
            "file_slug": file_slug_val,
            "nav_path": nav_path,
            "related_slugs": related_slugs,
        }
        essays.append(info)
        slug_to_info[file_slug_val] = {"title": title, "path": nav_path}

    # --- Pass 2: convert and write ---
    essay_tree = {}
    seen_titles = {}
    converted = 0
    failed = 0

    for info in essays:
        print(f"Converting: {info['rel']}")

        file_slug_for_title = info["file_slug"]
        title = info["title"]
        if title in seen_titles:
            seen_titles[title].append(file_slug_for_title)
        else:
            seen_titles[title] = [file_slug_for_title]

        md_content = tex_to_md(info["tex_file"])
        if md_content is None:
            failed += 1
            continue

        md_content = clean_md(
            md_content, title, info["subtitle"],
            info["published"], info["updated"],
            info["related_slugs"], slug_to_info,
        )

        top_slug = slug(info["top_category"])
        if info["sub_category"]:
            sub_slug = slug(info["sub_category"])
            out_dir = DOCS_DIR / top_slug / sub_slug
        else:
            out_dir = DOCS_DIR / top_slug
        out_dir.mkdir(parents=True, exist_ok=True)
        out_path = out_dir / f"{info['file_slug']}.md"
        out_path.write_text(md_content)

        nav_path = info["nav_path"]
        top_category = info["top_category"]
        sub_category = info["sub_category"]
        if top_category not in essay_tree:
            essay_tree[top_category] = {}
        if sub_category not in essay_tree[top_category]:
            essay_tree[top_category][sub_category] = []
        essay_tree[top_category][sub_category].append((title, nav_path))

        converted += 1

    print(f"\nConverted: {converted}, Failed: {failed}")

    # Disambiguate duplicate titles in essay_tree
    # Collect all (title, path) pairs across the entire tree
    all_titles = []
    for top_cat in essay_tree:
        for sub_cat in essay_tree[top_cat]:
            for title, path in essay_tree[top_cat][sub_cat]:
                all_titles.append(title)
    title_counts = {}
    for t in all_titles:
        title_counts[t] = title_counts.get(t, 0) + 1
    dupes = {t for t, c in title_counts.items() if c > 1}

    if dupes:
        print(f"Disambiguating {len(dupes)} duplicate titles: {dupes}")
        for top_cat in essay_tree:
            for sub_cat in essay_tree[top_cat]:
                new_items = []
                for title, path in essay_tree[top_cat][sub_cat]:
                    if title in dupes:
                        # Append the filename (without extension) to disambiguate
                        fname = Path(path).stem
                        # Convert slug back to readable: "glucose1" -> "Glucose1"
                        readable = fname.replace("-", " ").title()
                        new_title = f"{title} ({readable})"
                        new_items.append((new_title, path))
                    else:
                        new_items.append((title, path))
                essay_tree[top_cat][sub_cat] = new_items

    # Write nav fragment for mkdocs.yml
    nav_essays = build_nav(essay_tree)
    nav_fragment = {"nav_essays": nav_essays}
    nav_fpath = Path("docs/_nav.yml")
    nav_fpath.write_text(yaml.dump(nav_fragment, default_flow_style=False, allow_unicode=True))
    print(f"Nav fragment written to {nav_fpath}")

    # Generate homepage with category index
    generate_homepage(essay_tree, essays)


if __name__ == "__main__":
    main()
