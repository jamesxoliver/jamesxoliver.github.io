#!/usr/bin/env python3
"""Generate mkdocs.yml from base config and converted essays nav."""

import yaml
from pathlib import Path


def main():
    # Load nav fragment from conversion step
    nav_path = Path("docs/_nav.yml")
    if not nav_path.exists():
        print("No nav fragment found, skipping config generation")
        return

    nav_data = yaml.safe_load(nav_path.read_text())
    nav_essays = nav_data.get("nav_essays", [])

    config = {
        "site_name": "James Oliver",
        "site_url": "https://jamesxoliver.github.io",
        "site_description": "Finding simplicity in complexity",
        "theme": {
            "name": "material",
            "palette": [
                {
                    "media": "(prefers-color-scheme: light)",
                    "scheme": "default",
                    "toggle": {
                        "icon": "material/brightness-7",
                        "name": "Switch to dark mode",
                    },
                },
                {
                    "media": "(prefers-color-scheme: dark)",
                    "scheme": "slate",
                    "toggle": {
                        "icon": "material/brightness-4",
                        "name": "Switch to light mode",
                    },
                },
            ],
            "font": {"text": "Inter", "code": "JetBrains Mono"},
            "features": [
                "navigation.sections",
                "navigation.expand",
                "search.suggest",
                "search.highlight",
            ],
        },
        "nav": [
            {"Home": "index.md"},
            {"Essays": nav_essays},
        ],
        "markdown_extensions": [
            "tables",
            "admonition",
            {"pymdownx.arithmatex": {"generic": True}},
            "pymdownx.highlight",
            "pymdownx.superfences",
            "pymdownx.details",
            "attr_list",
            "md_in_html",
        ],
        "extra_javascript": [
            "https://cdn.jsdelivr.net/npm/mathjax@3/es5/tex-mml-chtml.js"
        ],
        "extra": {
            "generator": False,
        },
    }

    Path("mkdocs.yml").write_text(
        yaml.dump(config, default_flow_style=False, allow_unicode=True, sort_keys=False)
    )
    print("mkdocs.yml generated")


if __name__ == "__main__":
    main()
