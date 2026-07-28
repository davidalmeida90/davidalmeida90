"""Render the profile stats cards as static SVGs, in Meridian styling.

Runs in GitHub Actions on a daily cron. Queries the GraphQL API with the
workflow token, then writes four files into assets/:

    stats-light.svg  stats-dark.svg  langs-light.svg  langs-dark.svg

Standard library only, so the workflow needs no pip install.
"""

import json
import os
import urllib.request
from datetime import datetime, timezone

LOGIN = os.environ.get("PROFILE_LOGIN", "davidalmeida90")
TOKEN = os.environ["GITHUB_TOKEN"]
OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "assets")

QUERY = """
query($login: String!) {
  user(login: $login) {
    followers { totalCount }
    contributionsCollection {
      totalCommitContributions
      totalPullRequestContributions
      totalIssueContributions
      restrictedContributionsCount
      contributionCalendar { totalContributions }
    }
    repositories(ownerAffiliations: OWNER, privacy: PUBLIC, isFork: false, first: 100) {
      totalCount
      nodes {
        name
        stargazerCount
        languages(first: 10, orderBy: {field: SIZE, direction: DESC}) {
          edges { size node { name } }
        }
      }
    }
  }
}
"""


def fetch():
    body = json.dumps({"query": QUERY, "variables": {"login": LOGIN}}).encode()
    req = urllib.request.Request(
        "https://api.github.com/graphql",
        data=body,
        headers={
            "Authorization": "bearer " + TOKEN,
            "Content-Type": "application/json",
            "User-Agent": LOGIN + "-profile-cards",
        },
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        payload = json.load(r)
    if "errors" in payload:
        raise SystemExit("GraphQL error: " + json.dumps(payload["errors"]))
    return payload["data"]["user"]


# ---------------------------------------------------------------- theming

LIGHT = {
    "bg": "#FFFFFF", "line": "#C8C8C8", "title": "#0B2545", "label": "#454545",
    "value": "#0B2545", "note": "#7A7A7A", "rule": "#E2E2E2",
    "ramp": ["#0B2545", "#2A4E7E", "#3C6997", "#6590B8", "#8DA9C4", "#B8CAD9"],
    "track": "#E2E2E2",
}
DARK = {
    "bg": "#0B2545", "line": "#1E3A5F", "title": "#FFFFFF", "label": "#B8CAD9",
    "value": "#FFFFFF", "note": "#8DA9C4", "rule": "#1E3A5F",
    "ramp": ["#D9E2EC", "#B8CAD9", "#8DA9C4", "#6590B8", "#3C6997", "#2A4E7E"],
    "track": "#13315C",
}

FONT = "'IBM Plex Sans','Segoe UI',system-ui,-apple-system,Helvetica,Arial,sans-serif"
MONO = "'IBM Plex Mono','Consolas',Menlo,monospace"

W, H = 420, 196


def head(t):
    return (
        '<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" '
        'viewBox="0 0 {w} {h}" role="img">'
        '<rect x="0.5" y="0.5" width="{w1}" height="{h1}" rx="4" fill="{bg}" '
        'stroke="{line}" stroke-width="1"/>'
    ).format(w=W, h=H, w1=W - 1, h1=H - 1, bg=t["bg"], line=t["line"])


def title(t, text):
    return (
        '<text x="20" y="32" font-family="{f}" font-size="15" font-weight="600" '
        'fill="{c}">{s}</text>'
        '<line x1="20" y1="44" x2="{x2}" y2="44" stroke="{r}" stroke-width="1"/>'
    ).format(f=FONT, c=t["title"], s=text, x2=W - 20, r=t["rule"])


def note(t, text):
    return (
        '<text x="20" y="{y}" font-family="{f}" font-size="9" fill="{c}">{s}</text>'
    ).format(y=H - 16, f=FONT, c=t["note"], s=text)


def stats_svg(t, rows, updated):
    out = [head(t), title(t, "Activity, last 12 months")]
    y = 68
    for label, value in rows:
        out.append(
            '<text x="20" y="{y}" font-family="{f}" font-size="12" fill="{lc}">{l}</text>'
            '<text x="{xr}" y="{y}" font-family="{m}" font-size="13" font-weight="500" '
            'text-anchor="end" fill="{vc}">{v}</text>'.format(
                y=y, f=FONT, m=MONO, lc=t["label"], vc=t["value"],
                l=label, v=value, xr=W - 20,
            )
        )
        y += 22
    out.append(note(t, "Source: GitHub GraphQL API. Updated " + updated + "."))
    out.append("</svg>")
    return "".join(out)


def langs_svg(t, langs, updated):
    out = [head(t), title(t, "Public code by language")]
    total = sum(v for _, v in langs) or 1
    x, bar_y, bar_w = 20.0, 62, float(W - 40)
    for i, (_, size) in enumerate(langs):
        seg = bar_w * size / total
        if i == len(langs) - 1:
            seg = bar_w - (x - 20)
        out.append(
            '<rect x="{x:.2f}" y="{y}" width="{w:.2f}" height="8" fill="{c}"/>'.format(
                x=x, y=bar_y, w=max(seg, 0.0), c=t["ramp"][i % len(t["ramp"])]
            )
        )
        x += seg
    ly = 96
    for i, (name, size) in enumerate(langs):
        col = 20 if i % 2 == 0 else W // 2 + 4
        if i % 2 == 0 and i:
            ly += 20
        pct = 100.0 * size / total
        out.append(
            '<rect x="{x}" y="{y}" width="7" height="7" fill="{c}"/>'
            '<text x="{tx}" y="{ty}" font-family="{f}" font-size="11.5" fill="{lc}">{n}</text>'
            '<text x="{px}" y="{ty}" font-family="{m}" font-size="11.5" text-anchor="end" '
            'fill="{vc}">{p:.1f}%</text>'.format(
                x=col, y=ly - 7, c=t["ramp"][i % len(t["ramp"])],
                tx=col + 13, ty=ly, f=FONT, m=MONO, lc=t["label"], vc=t["value"],
                n=name, p=pct, px=col + (W // 2 - 28),
            )
        )
    out.append(note(t, "Source: GitHub API, bytes across public repositories. Updated "
                    + updated + "."))
    out.append("</svg>")
    return "".join(out)


def main():
    u = fetch()
    c = u["contributionsCollection"]
    repos = u["repositories"]["nodes"]
    stars = sum(r["stargazerCount"] for r in repos)

    sizes = {}
    for r in repos:
        if r["name"].lower() == LOGIN.lower():
            continue  # the profile repo itself is markup, not work
        for e in r["languages"]["edges"]:
            sizes[e["node"]["name"]] = sizes.get(e["node"]["name"], 0) + e["size"]
    langs = sorted(sizes.items(), key=lambda kv: -kv[1])[:6]
    if not langs:
        langs = [("No public code yet", 1)]

    # A row reading zero says nothing and reads as an empty account, so drop it.
    # Contributions, commits and repo count always stay, even at low counts.
    candidates = [
        ("Contributions", c["contributionCalendar"]["totalContributions"], True),
        ("Commits", c["totalCommitContributions"], True),
        ("Pull requests", c["totalPullRequestContributions"], False),
        ("Issues opened", c["totalIssueContributions"], False),
        ("Public repositories", u["repositories"]["totalCount"], True),
        ("Stars received", stars, False),
        ("Followers", u["followers"]["totalCount"], False),
    ]
    rows = [(l, "{:,}".format(v)) for l, v, keep in candidates if keep or v]

    updated = datetime.now(timezone.utc).strftime("%d %b %Y")
    os.makedirs(OUT, exist_ok=True)
    files = {
        "stats-light.svg": stats_svg(LIGHT, rows, updated),
        "stats-dark.svg": stats_svg(DARK, rows, updated),
        "langs-light.svg": langs_svg(LIGHT, langs, updated),
        "langs-dark.svg": langs_svg(DARK, langs, updated),
    }
    for name, svg in files.items():
        with open(os.path.join(OUT, name), "w", encoding="utf-8") as f:
            f.write(svg)
        print("wrote", name, len(svg), "bytes")
    print("contributions:", rows[0][1], "| restricted:", c["restrictedContributionsCount"])
    print("languages:", langs)


if __name__ == "__main__":
    main()
