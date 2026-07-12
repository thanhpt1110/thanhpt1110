#!/usr/bin/env python3
"""Generate static GitHub stats SVG cards for the README.

Replaces the rate-limited github-readme-stats.vercel.app images with
self-contained SVGs rendered from the GitHub GraphQL API. Run by the
"Update GitHub stats" workflow on a daily schedule.

Usage: GITHUB_TOKEN=<token> python3 scripts/generate_stats.py
"""
import html
import json
import os
import sys
import urllib.request

LOGIN = "thanhpt1110"
OUT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "assets")

QUERY = """
query($login: String!) {
  user(login: $login) {
    name
    followers { totalCount }
    contributionsCollection {
      totalCommitContributions
      restrictedContributionsCount
    }
    pullRequests { totalCount }
    issues { totalCount }
    repositoriesContributedTo(
      first: 1
      contributionTypes: [COMMIT, ISSUE, PULL_REQUEST, REPOSITORY]
    ) { totalCount }
    repositories(ownerAffiliations: OWNER, first: 100) {
      nodes {
        isFork
        stargazerCount
        languages(first: 10, orderBy: { field: SIZE, direction: DESC }) {
          edges { size node { name color } }
        }
      }
    }
  }
}
"""

THEMES = {
    "light": {
        "bg": "#ffffff", "border": "#d0d7de", "title": "#467100",
        "text": "#1f2328", "muted": "#57606a", "accent": "#76B900",
        "track": "#eaeef2",
    },
    "dark": {
        "bg": "#0d1117", "border": "#30363d", "title": "#8fd11e",
        "text": "#e6edf3", "muted": "#9aa4af", "accent": "#76B900",
        "track": "#21262d",
    },
}

FONT = "'Segoe UI', Ubuntu, 'Helvetica Neue', Sans-Serif"


def fetch():
    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    if not token:
        sys.exit("GITHUB_TOKEN is required")
    req = urllib.request.Request(
        "https://api.github.com/graphql",
        data=json.dumps({"query": QUERY, "variables": {"login": LOGIN}}).encode(),
        headers={"Authorization": f"bearer {token}", "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        payload = json.load(resp)
    if payload.get("errors"):
        sys.exit(f"GraphQL errors: {payload['errors']}")
    return payload["data"]["user"]


def stats_card(user, theme_name):
    t = THEMES[theme_name]
    contrib = user["contributionsCollection"]
    stars = sum(r["stargazerCount"] for r in user["repositories"]["nodes"] if not r["isFork"])
    rows = [
        ("Total Stars Earned", stars),
        ("Total Commits (last year)", contrib["totalCommitContributions"] + contrib["restrictedContributionsCount"]),
        ("Total PRs", user["pullRequests"]["totalCount"]),
        ("Total Issues", user["issues"]["totalCount"]),
        ("Contributed to", user["repositoriesContributedTo"]["totalCount"]),
        ("Followers", user["followers"]["totalCount"]),
    ]
    width, pad, row_h, top = 450, 25, 26, 59
    height = top + row_h * len(rows) + 18
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}" role="img" aria-label="{html.escape(user["name"])}\'s GitHub stats">',
        f'<rect x="0.5" y="0.5" width="{width - 1}" height="{height - 1}" rx="10" fill="{t["bg"]}" stroke="{t["border"]}"/>',
        f'<text x="{pad}" y="35" font-family="{FONT}" font-size="18" font-weight="600" fill="{t["title"]}">{html.escape(user["name"])}\'s GitHub Stats</text>',
    ]
    for i, (label, value) in enumerate(rows):
        y = top + row_h * i + 14
        parts.append(f'<rect x="{pad}" y="{y - 9}" width="6" height="6" rx="1" transform="rotate(45 {pad + 3} {y - 6})" fill="{t["accent"]}"/>')
        parts.append(f'<text x="{pad + 16}" y="{y}" font-family="{FONT}" font-size="14" fill="{t["text"]}">{html.escape(label)}</text>')
        parts.append(f'<text x="{width - pad}" y="{y}" text-anchor="end" font-family="{FONT}" font-size="14" font-weight="600" fill="{t["title"]}">{value}</text>')
    parts.append("</svg>")
    return "".join(parts)


def langs_card(user, theme_name, top_n=6):
    t = THEMES[theme_name]
    totals, colors = {}, {}
    for repo in user["repositories"]["nodes"]:
        if repo["isFork"]:
            continue
        for edge in repo["languages"]["edges"]:
            name = edge["node"]["name"]
            totals[name] = totals.get(name, 0) + edge["size"]
            colors[name] = edge["node"]["color"] or "#8b949e"
    ranked = sorted(totals.items(), key=lambda kv: -kv[1])[:top_n]
    total = sum(v for _, v in ranked) or 1

    width, pad = 450, 25
    bar_y, bar_h = 55, 10
    legend_top, cell_h, cols = 82, 24, 2
    rows_n = (len(ranked) + cols - 1) // cols
    height = legend_top + rows_n * cell_h + 12
    bar_w = width - pad * 2

    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}" role="img" aria-label="Most used languages">',
        f'<rect x="0.5" y="0.5" width="{width - 1}" height="{height - 1}" rx="10" fill="{t["bg"]}" stroke="{t["border"]}"/>',
        f'<text x="{pad}" y="35" font-family="{FONT}" font-size="18" font-weight="600" fill="{t["title"]}">Most Used Languages</text>',
        f'<rect x="{pad}" y="{bar_y}" width="{bar_w}" height="{bar_h}" rx="5" fill="{t["track"]}"/>',
        f'<defs><clipPath id="bar"><rect x="{pad}" y="{bar_y}" width="{bar_w}" height="{bar_h}" rx="5"/></clipPath></defs>',
        '<g clip-path="url(#bar)">',
    ]
    x = float(pad)
    for name, size in ranked:
        seg = bar_w * size / total
        parts.append(f'<rect x="{x:.2f}" y="{bar_y}" width="{max(seg - 2, 2):.2f}" height="{bar_h}" fill="{colors[name]}"/>')
        x += seg
    parts.append("</g>")
    col_w = bar_w / cols
    for i, (name, size) in enumerate(ranked):
        cx = pad + (i % cols) * col_w
        cy = legend_top + (i // cols) * cell_h
        pct = 100.0 * size / total
        pct_label = "<0.1" if 0 < pct < 0.1 else f"{pct:.1f}".rstrip("0").rstrip(".")
        parts.append(f'<circle cx="{cx + 5}" cy="{cy - 4}" r="5" fill="{colors[name]}"/>')
        parts.append(f'<text x="{cx + 18}" y="{cy}" font-family="{FONT}" font-size="13" fill="{t["text"]}">{html.escape(name)}</text>')
        parts.append(f'<text x="{cx + col_w - 14}" y="{cy}" text-anchor="end" font-family="{FONT}" font-size="13" fill="{t["muted"]}">{html.escape(pct_label)}%</text>')
    parts.append("</svg>")
    return "".join(parts)


def main():
    user = fetch()
    os.makedirs(OUT_DIR, exist_ok=True)
    for theme in THEMES:
        for name, svg in (
            (f"github-stats-{theme}.svg", stats_card(user, theme)),
            (f"top-langs-{theme}.svg", langs_card(user, theme)),
        ):
            path = os.path.join(OUT_DIR, name)
            with open(path, "w", encoding="utf-8") as f:
                f.write(svg + "\n")
            print(f"wrote {path}")


if __name__ == "__main__":
    main()
