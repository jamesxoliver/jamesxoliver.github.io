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
        "site_description": "Essays on systems, science, and structure — finding simplicity in complexity.",
        "site_author": "James Oliver",
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
                "search.suggest",
                "search.highlight",
                "toc.integrate",
            ],
        },
        "nav": [
            {"Home": "index.md"},
        ] + nav_essays,
        "markdown_extensions": [
            "tables",
            "admonition",
            {"pymdownx.arithmatex": {"generic": True}},
            "pymdownx.highlight",
            "pymdownx.superfences",
            "pymdownx.details",
            "attr_list",
            "md_in_html",
            {"toc": {"permalink": True}},
            "pymdownx.emoji",
            "meta",
        ],
        "plugins": [
            "search",
        ],
        "extra_css": [
            "stylesheets/extra.css",
        ],
        "extra_javascript": [
            "javascripts/mathjax.js",
            "https://cdn.jsdelivr.net/npm/mathjax@3/es5/tex-mml-chtml.js",
        ],
        "extra": {
            "generator": False,
            "social": [
                {"icon": "fontawesome/brands/github", "link": "https://github.com/jamesxoliver"},
                {"icon": "fontawesome/brands/orcid", "link": "https://orcid.org/0009-0003-9912-095X"},
                {"icon": "simple/zenodo", "link": "https://zenodo.org/communities/jamesoliver/records"},
            ],
        },
    }

    yml_text = yaml.dump(config, default_flow_style=False, allow_unicode=True, sort_keys=False)

    # Replace pymdownx.emoji string entry with full config block (YAML tags can't go through yaml.dump)
    yml_text = yml_text.replace(
        "- pymdownx.emoji\n",
        "- pymdownx.emoji:\n"
        "    emoji_index: !!python/name:material.extensions.emoji.twemoji\n"
        "    emoji_generator: !!python/name:material.extensions.emoji.to_svg\n",
    )

    Path("mkdocs.yml").write_text(yml_text)
    print("mkdocs.yml generated")


if __name__ == "__main__":
    main()
