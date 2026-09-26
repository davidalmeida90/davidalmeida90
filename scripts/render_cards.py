"""Render the two profile cards as static SVGs, in GitHub's dark theme.

Runs in GitHub Actions on a daily cron and writes into assets/:

    github-stats.svg       Stars, Forks, All-time contributions, Lines of code
                           changed, Repository views (past two weeks),
                           Repositories with contributions. Same counting as
                           jstrieb/github-stats: stars and forks are summed over
                           every repository with a contribution, not only owned
                           ones.
    activity-overview.svg  Commits, code review, issues and pull requests over
                           the last 12 months, drawn like the activity overview
                           on a GitHub profile (each arm scaled to the largest
                           share).

Only public repositories are counted. The views row needs a token with push
access to every owned repository (traffic data is owner-only): set it as the
STATS_TOKEN secret. Without it the row is left out.

Lines changed come from /stats/contributors, which answers 202 while GitHub
computes. Per-repository results are cached in assets/lines-cache.json, so a
repository still computing keeps its last known value.

Icons are Primer Octicons (MIT). Standard library only.
"""

import json
import os
import time
import urllib.error
import urllib.request

LOGIN = os.environ.get("PROFILE_LOGIN", "davidalmeida90")
NAME = os.environ.get("PROFILE_NAME", "David Arias")
TOKEN = os.environ["GITHUB_TOKEN"]
STATS_TOKEN = os.environ.get("STATS_TOKEN") or ""
OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "assets")
CACHE = os.path.join(OUT, "lines-cache.json")


def request(url, data=None, token=TOKEN):
    req = urllib.request.Request(
        url,
        data=data,
        headers={
            "Authorization": "bearer " + token,
            "Content-Type": "application/json",
            "Accept": "application/vnd.github+json",
            "User-Agent": LOGIN + "-profile-cards",
        },
    )
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.status, json.load(r)


def graphql(query, **variables):
    body = json.dumps({"query": query, "variables": variables}).encode()
    _, payload = request("https://api.github.com/graphql", body)
    if "errors" in payload:
        raise SystemExit("GraphQL error: " + json.dumps(payload["errors"]))
    return payload["data"]["user"]


def rest(path, token=TOKEN):
    try:
        return request("https://api.github.com/" + path, token=token)
    except urllib.error.HTTPError as e:
        return e.code, None


PROFILE = """
query($login: String!) {
  user(login: $login) {
    repositories(ownerAffiliations: OWNER, privacy: PUBLIC, isFork: false, first: 100) {
      nodes { nameWithOwner stargazerCount forkCount }
    }
    contributionsCollection {
      contributionYears
      totalCommitContributions
      totalPullRequestContributions
      totalIssueContributions
      totalPullRequestReviewContributions
    }
  }
}
"""

YEAR = """
query($login: String!, $from: DateTime!, $to: DateTime!) {
  user(login: $login) {
    contributionsCollection(from: $from, to: $to) {
      contributionCalendar { totalContributions }
      commitContributionsByRepository(maxRepositories: 100) { repository { ...r } }
      pullRequestContributionsByRepository(maxRepositories: 100) { repository { ...r } }
      issueContributionsByRepository(maxRepositories: 100) { repository { ...r } }
      pullRequestReviewContributionsByRepository(maxRepositories: 100) { repository { ...r } }
    }
  }
}
fragment r on Repository { nameWithOwner isPrivate stargazerCount forkCount }
"""


def lines_changed(repos):
    """Additions plus deletions by LOGIN on each repository's default branch."""
    try:
        with open(CACHE, encoding="utf-8") as f:
            cache = json.load(f)
    except (OSError, ValueError):
        cache = {}
    for name in repos:
        for _ in range(6):
            status, data = rest("repos/{}/stats/contributors".format(name))
            if status == 200 and isinstance(data, list):
                mine = [c for c in data if (c.get("author") or {}).get("login", "").lower() == LOGIN.lower()]
                cache[name] = sum(w["a"] + w["d"] for c in mine for w in c["weeks"])
                break
            if status != 202:
                break
            time.sleep(4)  # GitHub answers 202 while it computes the stats
    kept = {k: v for k, v in cache.items() if k in repos}
    with open(CACHE, "w", encoding="utf-8") as f:
        json.dump(kept, f, indent=1, sort_keys=True)
    return sum(kept.values())


def views(repos):
    """Views over the past 14 days, or None unless every owned repository answered."""
    if not STATS_TOKEN:
        return None
    total = 0
    for name in repos:
        status, data = rest("repos/{}/traffic/views".format(name), token=STATS_TOKEN)
        if status != 200 or not data:
            return None
        total += data.get("count", 0)
    return total


# ---------------------------------------------------------------- drawing
# Colours sampled from a jstrieb card and a GitHub activity overview in dark mode.

FONT = "-apple-system,BlinkMacSystemFont,'Segoe UI',Helvetica,Arial,sans-serif"
BG = "#0D1117"
BORDER = "#373C40"
TITLE = "#58A6FF"
TEXT = "#C9D1D9"
ICON = "#8B949E"
GREEN = "#39D353"
FILL = "#26A641"
W, H = 360, 210

ICONS = {
    "star": "M8 .25a.75.75 0 0 1 .673.418l1.882 3.815 4.21.612a.75.75 0 0 1 .416 1.279l-3.046 2.97.719 4.192a.751.751 0 0 1-1.088.791L8 12.347l-3.766 1.98a.75.75 0 0 1-1.088-.79l.72-4.194L.818 6.374a.75.75 0 0 1 .416-1.28l4.21-.611L7.327.668A.75.75 0 0 1 8 .25Zm0 2.445L6.615 5.5a.75.75 0 0 1-.564.41l-3.097.45 2.24 2.184a.75.75 0 0 1 .216.664l-.528 3.084 2.769-1.456a.75.75 0 0 1 .698 0l2.77 1.456-.53-3.084a.75.75 0 0 1 .216-.664l2.24-2.183-3.096-.45a.75.75 0 0 1-.564-.41L8 2.694Z",
    "fork": "M5 5.372v.878c0 .414.336.75.75.75h4.5a.75.75 0 0 0 .75-.75v-.878a2.25 2.25 0 1 1 1.5 0v.878a2.25 2.25 0 0 1-2.25 2.25h-1.5v2.128a2.251 2.251 0 1 1-1.5 0V8.5h-1.5A2.25 2.25 0 0 1 3.5 6.25v-.878a2.25 2.25 0 1 1 1.5 0ZM5 3.25a.75.75 0 1 0-1.5 0 .75.75 0 0 0 1.5 0Zm6.75.75a.75.75 0 1 0 0-1.5.75.75 0 0 0 0 1.5Zm-3 8.75a.75.75 0 1 0-1.5 0 .75.75 0 0 0 1.5 0Z",
    "push": "M2 2.5A2.5 2.5 0 0 1 4.5 0h8.75a.75.75 0 0 1 .75.75v3.5a.75.75 0 0 1-1.5 0V1.5h-8a1 1 0 0 0-1 1v6.708A2.493 2.493 0 0 1 4.5 9h2.25a.75.75 0 0 1 0 1.5H4.5a1 1 0 0 0 0 2h4.75a.75.75 0 0 1 0 1.5H4.5A2.5 2.5 0 0 1 2 11.5Zm12.23 7.79h-.001l-1.224-1.224v6.184a.75.75 0 0 1-1.5 0V9.066L10.28 10.29a.75.75 0 0 1-1.06-1.061l2.505-2.504a.75.75 0 0 1 1.06 0L15.29 9.23a.751.751 0 0 1-.018 1.042.751.751 0 0 1-1.042.018Z",
    "diff": "M8.75 1.75V5H12a.75.75 0 0 1 0 1.5H8.75v3.25a.75.75 0 0 1-1.5 0V6.5H4A.75.75 0 0 1 4 5h3.25V1.75a.75.75 0 0 1 1.5 0ZM4 13h8a.75.75 0 0 1 0 1.5H4A.75.75 0 0 1 4 13Z",
    "eye": "M8 2c1.981 0 3.671.992 4.933 2.078 1.27 1.091 2.187 2.345 2.637 3.023a1.62 1.62 0 0 1 0 1.798c-.45.678-1.367 1.932-2.637 3.023C11.67 13.008 9.981 14 8 14c-1.981 0-3.671-.992-4.933-2.078C1.797 10.83.88 9.576.43 8.898a1.62 1.62 0 0 1 0-1.798c.45-.677 1.367-1.931 2.637-3.022C4.33 2.992 6.019 2 8 2ZM1.679 7.932a.12.12 0 0 0 0 .136c.411.622 1.241 1.75 2.366 2.717C5.176 11.758 6.527 12.5 8 12.5c1.473 0 2.825-.742 3.955-1.715 1.124-.967 1.954-2.096 2.366-2.717a.12.12 0 0 0 0-.136c-.412-.621-1.242-1.75-2.366-2.717C10.824 4.242 9.473 3.5 8 3.5c-1.473 0-2.825.742-3.955 1.715-1.124.967-1.954 2.096-2.366 2.717ZM8 10a2 2 0 1 1-.001-3.999A2 2 0 0 1 8 10Z",
    "repo": "M2 2.5A2.5 2.5 0 0 1 4.5 0h8.75a.75.75 0 0 1 .75.75v12.5a.75.75 0 0 1-.75.75h-2.5a.75.75 0 0 1 0-1.5h1.75v-2h-8a1 1 0 0 0-.714 1.7.75.75 0 1 1-1.072 1.05A2.495 2.495 0 0 1 2 11.5Zm10.5-1h-8a1 1 0 0 0-1 1v6.708A2.486 2.486 0 0 1 4.5 9h8ZM5 12.25a.25.25 0 0 1 .25-.25h3.5a.25.25 0 0 1 .25.25v3.25a.25.25 0 0 1-.4.2l-1.45-1.087a.249.249 0 0 0-.3 0L5.4 15.7a.25.25 0 0 1-.4-.2Z",
}


def frame():
    return (
        '<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}">'
        '<rect x="5.5" y="5.5" width="{rw}" height="{rh}" rx="6" fill="{bg}" '
        'stroke="{b}" stroke-width="1"/>'
    ).format(w=W, h=H, rw=W - 11, rh=H - 11, bg=BG, b=BORDER)


def stats_svg(rows):
    out = [frame(),
           '<text x="28" y="36" font-family="{f}" font-size="14" font-weight="600" fill="{c}">'
           "{n}'s GitHub Statistics</text>".format(f=FONT, c=TITLE, n=NAME)]
    step = 24 if len(rows) >= 6 else 26
    for i, (icon, label, value) in enumerate(rows):
        y = 50 + i * step
        out.append(
            '<path transform="translate(26 {iy})" fill="{ic}" d="{d}"/>'
            '<text x="50" y="{ty}" font-family="{f}" font-size="12" fill="{c}">{l}</text>'
            '<text x="262" y="{ty}" font-family="{f}" font-size="12" fill="{c}">{v}</text>'.format(
                iy=y, ty=y + 12, ic=ICON, c=TEXT, d=ICONS[icon], f=FONT, l=label, v="{:,}".format(value)
            )
        )
    out.append("</svg>")
    return "".join(out)


def activity_svg(counts):
    total = sum(v for _, v in counts) or 1
    share = {k: v / total for k, v in counts}
    top = max(share.values()) or 1
    cx, cy, ax, ay = 180, 106, 72, 58
    arms = {"Code review": (0, -1), "Issues": (1, 0), "Pull requests": (0, 1), "Commits": (-1, 0)}
    out = [frame()]
    out.append(
        '<line x1="{x1}" y1="{cy}" x2="{x2}" y2="{cy}" stroke="{g}" stroke-width="2" stroke-linecap="round"/>'
        '<line x1="{cx}" y1="{y1}" x2="{cx}" y2="{y2}" stroke="{g}" stroke-width="2" stroke-linecap="round"/>'.format(
            x1=cx - ax, x2=cx + ax, y1=cy - ay, y2=cy + ay, cx=cx, cy=cy, g=GREEN
        )
    )
    pts = [(cx + dx * ax * share[k] / top, cy + dy * ay * share[k] / top) for k, (dx, dy) in arms.items()]
    out.append('<polygon points="{}" fill="{f}" fill-opacity="0.6" stroke="{g}" stroke-width="2" '
               'stroke-linejoin="round"/>'.format(" ".join("{:.1f},{:.1f}".format(x, y) for x, y in pts),
                                                  f=FILL, g=GREEN))
    for x, y in pts:
        out.append('<circle cx="{:.1f}" cy="{:.1f}" r="3.5" fill="#FFFFFF" stroke="{}" stroke-width="2"/>'.format(
            x, y, GREEN))

    def label(name, x, y):
        pct = "{}%".format(int(round(100 * share[name])))
        return (
            '<text x="{x}" y="{y1}" font-family="{f}" font-size="12" text-anchor="middle" fill="{c}">{p}</text>'
            '<text x="{x}" y="{y2}" font-family="{f}" font-size="12" text-anchor="middle" fill="{c}">{n}</text>'
        ).format(x=x, y1=y, y2=y + 14, f=FONT, c=TEXT, p=pct, n=name)

    out.append(label("Code review", cx, cy - ay - 22))
    out.append(label("Pull requests", cx, cy + ay + 16))
    out.append(label("Commits", cx - ax - 32, cy - 2))
    out.append(label("Issues", cx + ax + 26, cy - 2))
    out.append("</svg>")
    return "".join(out)


def main():
    u = graphql(PROFILE, login=LOGIN)
    own = u["repositories"]["nodes"]
    repos = {r["nameWithOwner"]: r for r in own}

    # All-time totals: GitHub caps a contributions collection at one year.
    contributions = 0
    for year in u["contributionsCollection"]["contributionYears"]:
        c = graphql(YEAR, login=LOGIN, **{"from": "{}-01-01T00:00:00Z".format(year),
                                          "to": "{}-12-31T23:59:59Z".format(year)})["contributionsCollection"]
        contributions += c["contributionCalendar"]["totalContributions"]
        for kind in ("commit", "pullRequest", "issue", "pullRequestReview"):
            for e in c[kind + "ContributionsByRepository"]:
                if not e["repository"]["isPrivate"]:
                    repos.setdefault(e["repository"]["nameWithOwner"], e["repository"])

    seen = views([r["nameWithOwner"] for r in own])
    rows = [
        ("star", "Stars", sum(r["stargazerCount"] for r in repos.values())),
        ("fork", "Forks", sum(r["forkCount"] for r in repos.values())),
        ("push", "All-time contributions", contributions),
        ("diff", "Lines of code changed", lines_changed(sorted(repos))),
    ]
    if seen is not None:
        rows.append(("eye", "Repository views (past two weeks)", seen))
    rows.append(("repo", "Repositories with contributions", len(repos)))

    cc = u["contributionsCollection"]
    counts = [
        ("Commits", cc["totalCommitContributions"]),
        ("Code review", cc["totalPullRequestReviewContributions"]),
        ("Issues", cc["totalIssueContributions"]),
        ("Pull requests", cc["totalPullRequestContributions"]),
    ]

    os.makedirs(OUT, exist_ok=True)
    for name, svg in (("github-stats.svg", stats_svg(rows)), ("activity-overview.svg", activity_svg(counts))):
        with open(os.path.join(OUT, name), "w", encoding="utf-8") as f:
            f.write(svg)
        print("wrote", name, len(svg), "bytes")
    for _, label, value in rows:
        print("  {:34s} {:,}".format(label, value))
    print("  activity:", counts)


if __name__ == "__main__":
    main()
