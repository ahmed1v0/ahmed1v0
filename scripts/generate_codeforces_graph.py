#!/usr/bin/env python3
"""Generate a small SVG rating-history chart from the official Codeforces API."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen


API_URL = "https://codeforces.com/api/user.rating"

WIDTH = 1100
HEIGHT = 330
PAD_LEFT = 70
PAD_RIGHT = 28
PAD_TOP = 54
PAD_BOTTOM = 52

BG = "#0b0d12"
GRID = "#263244"
TEXT = "#94a3b8"
TITLE = "#e6e8ef"
LINE = "#22d3ee"
POINT = "#a78bfa"
AREA = "#7c3aed"


def fetch_rating_history(handle: str) -> list[dict]:
    query = urlencode({"handle": handle})
    request = Request(
        f"{API_URL}?{query}",
        headers={"User-Agent": "github-profile-rating-chart/1.0"},
    )

    with urlopen(request, timeout=20) as response:
        payload = json.load(response)

    if payload.get("status") != "OK":
        raise RuntimeError(payload.get("comment", "Codeforces API request failed"))

    return payload["result"]


def scale(value: float, in_min: float, in_max: float, out_min: float, out_max: float) -> float:
    if in_max == in_min:
        return (out_min + out_max) / 2
    ratio = (value - in_min) / (in_max - in_min)
    return out_min + ratio * (out_max - out_min)


def nice_rating_bounds(values: list[int]) -> tuple[int, int]:
    low = min(values)
    high = max(values)

    low = max(0, ((low - 100) // 200) * 200)
    high = ((high + 199) // 200) * 200

    if high - low < 400:
        high = low + 400

    return low, high


def escape(text: str) -> str:
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def generate_svg(handle: str, history: list[dict]) -> str:
    if not history:
        return f"""<svg xmlns="http://www.w3.org/2000/svg" width="{WIDTH}" height="{HEIGHT}" viewBox="0 0 {WIDTH} {HEIGHT}">
  <rect width="100%" height="100%" rx="18" fill="{BG}"/>
  <text x="50%" y="46%" text-anchor="middle" fill="{TITLE}" font-family="Inter,Segoe UI,Arial,sans-serif" font-size="24" font-weight="700">Codeforces Rating History</text>
  <text x="50%" y="57%" text-anchor="middle" fill="{TEXT}" font-family="Inter,Segoe UI,Arial,sans-serif" font-size="16">No rated contests found for {escape(handle)}.</text>
</svg>"""

    ratings = [int(item["newRating"]) for item in history]
    timestamps = [int(item["ratingUpdateTimeSeconds"]) for item in history]

    min_rating, max_rating = nice_rating_bounds(ratings)
    min_time, max_time = min(timestamps), max(timestamps)

    plot_left = PAD_LEFT
    plot_right = WIDTH - PAD_RIGHT
    plot_top = PAD_TOP
    plot_bottom = HEIGHT - PAD_BOTTOM

    points: list[tuple[float, float]] = []
    for timestamp, rating in zip(timestamps, ratings):
        x = scale(timestamp, min_time, max_time, plot_left, plot_right)
        y = scale(rating, min_rating, max_rating, plot_bottom, plot_top)
        points.append((x, y))

    polyline = " ".join(f"{x:.1f},{y:.1f}" for x, y in points)
    area_points = f"{plot_left},{plot_bottom} {polyline} {plot_right},{plot_bottom}"

    y_ticks = list(range(min_rating, max_rating + 1, 200))
    grid_lines = []
    for rating in y_ticks:
        y = scale(rating, min_rating, max_rating, plot_bottom, plot_top)
        grid_lines.append(
            f'<line x1="{plot_left}" y1="{y:.1f}" x2="{plot_right}" y2="{y:.1f}" '
            f'stroke="{GRID}" stroke-width="1"/>'
            f'<text x="{plot_left - 12}" y="{y + 5:.1f}" text-anchor="end" fill="{TEXT}" '
            f'font-family="JetBrains Mono,Consolas,monospace" font-size="12">{rating}</text>'
        )

    first_date = datetime.fromtimestamp(min_time, tz=timezone.utc).strftime("%b %Y")
    last_date = datetime.fromtimestamp(max_time, tz=timezone.utc).strftime("%b %Y")

    last_x, last_y = points[-1]
    current = ratings[-1]
    peak = max(ratings)
    contests = len(history)

    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="{WIDTH}" height="{HEIGHT}" viewBox="0 0 {WIDTH} {HEIGHT}">
  <defs>
    <linearGradient id="area" x1="0" y1="{plot_top}" x2="0" y2="{plot_bottom}" gradientUnits="userSpaceOnUse">
      <stop stop-color="{AREA}" stop-opacity=".35"/>
      <stop offset="1" stop-color="{AREA}" stop-opacity=".02"/>
    </linearGradient>
  </defs>

  <rect width="100%" height="100%" rx="18" fill="{BG}"/>

  <text x="{plot_left}" y="31" fill="{TITLE}" font-family="Inter,Segoe UI,Arial,sans-serif" font-size="20" font-weight="700">
    Codeforces Rating History · {escape(handle)}
  </text>
  <text x="{plot_right}" y="31" text-anchor="end" fill="{TEXT}" font-family="JetBrains Mono,Consolas,monospace" font-size="12">
    current {current} · peak {peak} · {contests} rated contests
  </text>

  {''.join(grid_lines)}

  <polygon points="{area_points}" fill="url(#area)"/>
  <polyline points="{polyline}" fill="none" stroke="{LINE}" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"/>

  <circle cx="{last_x:.1f}" cy="{last_y:.1f}" r="5.5" fill="{POINT}" stroke="{BG}" stroke-width="3"/>

  <text x="{plot_left}" y="{HEIGHT - 18}" fill="{TEXT}" font-family="JetBrains Mono,Consolas,monospace" font-size="12">{first_date}</text>
  <text x="{plot_right}" y="{HEIGHT - 18}" text-anchor="end" fill="{TEXT}" font-family="JetBrains Mono,Consolas,monospace" font-size="12">{last_date}</text>
</svg>"""


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--handle", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    history = fetch_rating_history(args.handle)
    svg = generate_svg(args.handle, history)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(svg, encoding="utf-8")


if __name__ == "__main__":
    main()
