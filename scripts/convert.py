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
            "-t", "markdown",
            "--wrap=none",
            "--markdown-headings=atx",
        ],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        print(f"  pandoc error for {tex_path}: {result.stderr[:200]}")
        return None
    return result.stdout


def clean_md(md_content: str, title: str, subtitle: str | None,
             published: str | None = None, updated: str | None = None) -> str:
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

    # Build header
    header = f"# {title}\n\n"
    if subtitle:
        header += f"*{subtitle}*\n\n"
    header += "**James Oliver**"

    # Add dates
    if published:
        date_line = f"Published: {published}"
        if updated and updated != published:
            date_line += f" · Updated: {updated}"
        header += f"  \n<small>{date_line}</small>"

    header += "\n"

    # Clean up some common pandoc artifacts
    md = re.sub(r"\n{3,}", "\n\n", md)

    return header + "\n---\n\n" + md + "\n"


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


def generate_homepage(essay_tree: dict):
    """Generate docs/index.md with a category-based table of contents."""
    lines = [
        "# James Oliver",
        "",
        "Finding simplicity in complexity.",
        "",
        "---",
        "",
    ]

    for top_cat in sorted(essay_tree.keys()):
        subs = essay_tree[top_cat]
        total = sum(len(v) for v in subs.values())
        lines.append(f"## {top_cat}")
        lines.append("")

        # Articles directly under the top category
        if None in subs:
            for title, path in sorted(subs[None]):
                lines.append(f"- [{title}]({path})")

        # Subcategories
        for sub_cat in sorted(k for k in subs if k is not None):
            lines.append(f"### {sub_cat}")
            lines.append("")
            for title, path in sorted(subs[sub_cat]):
                lines.append(f"- [{title}]({path})")
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

    # essay_tree: {top_category: {subcategory_or_None: [(title, path)]}}
    essay_tree = {}
    converted = 0
    failed = 0

    # Rename map for cleaner display of top-level dirs
    RENAME = {"1_Foundations": "Foundations"}

    for tex_file in sorted(PAPERS_DIR.rglob("*.tex")):
        rel = tex_file.relative_to(PAPERS_DIR)
        parts = rel.parts

        # Skip format/template files
        if parts[0] in SKIP_DIRS:
            continue
        if "template" in tex_file.name.lower():
            continue

        print(f"Converting: {rel}")

        tex_content = tex_file.read_text(errors="replace")

        # Extract metadata
        title = extract_title(tex_content)
        if not title or title == "Title":
            print(f"  Skipping (no title): {rel}")
            failed += 1
            continue

        subtitle = extract_subtitle(tex_content)

        # Get git dates
        published, updated = get_git_dates(rel)

        # Determine category hierarchy from directory structure
        top_category = RENAME.get(parts[0], parts[0])
        sub_category = None
        if len(parts) > 2:
            # Has a subcategory folder
            sub_category = parts[1]
            # Handle deep nesting (e.g. Health/Metabolism/01_theory/...)
            # Collapse to just the first subcategory level
            if len(parts) > 3:
                sub_category = parts[1]

        # Convert
        md_content = tex_to_md(tex_file)
        if md_content is None:
            failed += 1
            continue

        # Clean up
        md_content = clean_md(md_content, title, subtitle, published, updated)

        # Write output — mirror the hierarchy in the output path
        file_slug = slug(tex_file.name)
        top_slug = slug(top_category)
        if sub_category:
            sub_slug = slug(sub_category)
            out_dir = DOCS_DIR / top_slug / sub_slug
        else:
            out_dir = DOCS_DIR / top_slug
        out_dir.mkdir(parents=True, exist_ok=True)
        out_path = out_dir / f"{file_slug}.md"
        out_path.write_text(md_content)

        # Track for nav
        nav_path = str(out_path.relative_to(Path("docs")))
        if top_category not in essay_tree:
            essay_tree[top_category] = {}
        if sub_category not in essay_tree[top_category]:
            essay_tree[top_category][sub_category] = []
        essay_tree[top_category][sub_category].append((title, nav_path))

        converted += 1

    print(f"\nConverted: {converted}, Failed: {failed}")

    # Write nav fragment for mkdocs.yml
    nav_essays = build_nav(essay_tree)
    nav_fragment = {"nav_essays": nav_essays}
    nav_fpath = Path("docs/_nav.yml")
    nav_fpath.write_text(yaml.dump(nav_fragment, default_flow_style=False, allow_unicode=True))
    print(f"Nav fragment written to {nav_fpath}")

    # Generate homepage with category index
    generate_homepage(essay_tree)


if __name__ == "__main__":
    main()
