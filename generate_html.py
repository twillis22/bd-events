"""Generate the bookmarkable HTML page from aggregated events.

Modern Level 10-inspired design (toned variant):
  - Solid warm-grey background (no ambient gradient); light theme via toggle
  - Each event card tinted by its region color (subtle)
  - Glow/bloom intensity halved across the page
  - Brand orange (#ff671f) still leads accent + interaction states

All colors flow through CSS custom properties on :root; the light theme is a
[data-theme="light"] override block, toggled client-side and persisted in
localStorage.
"""
from datetime import datetime, timedelta, timezone
from typing import List, Optional
from urllib.parse import quote
import html
import json
import re

from scrapers.base import Event
from scrapers.regions import KEPT_BUCKETS


# Level 10 brand palette (dark theme defaults)
L10_BG          = "#262626"   # solid warm grey body bg (matches Level 10)
L10_BG_DEEP     = "#1c1c1c"   # input fields
L10_TEXT        = "#f6f6f6"
L10_TEXT_MUTED  = "rgba(246, 246, 246, 0.62)"
L10_TEXT_DIM    = "rgba(246, 246, 246, 0.35)"
L10_BORDER_TR   = "rgba(255, 255, 255, 0.08)"
L10_BORDER_HARD = "rgba(255, 255, 255, 0.12)"
L10_GLASS       = "rgba(255, 255, 255, 0.04)"
L10_ORANGE      = "#ff671f"
L10_ORANGE_SOFT = "rgba(255, 103, 31, 0.10)"

# Muted, distinct tints per submarket — same restrained saturation family
# as the original NorCal blue / SoCal pink.
REGION_COLORS = {
    "San Francisco":  "#7eaee0",   # blue
    "Silicon Valley": "#9ec9b3",   # sage green
    "East Bay":       "#d4b483",   # warm tan
    "Sacramento":     "#d8c873",   # golden
    "San Diego":      "#e095b1",   # pink
    "Bay Area":       "#a8b2c4",   # neutral slate (catch-all)
    "Online":         "#b9a3d6",   # lavender
}


def _render_region_pills(events: List[Event]) -> str:
    counts = {}
    for e in events:
        counts[e.region] = counts.get(e.region, 0) + 1
    parts = ['<button class="pill active" data-filter="region" data-value="all">All Regions</button>']
    for region in KEPT_BUCKETS:
        if region in counts:
            color = REGION_COLORS.get(region, "#aaa")
            parts.append(
                f'<button class="pill" data-filter="region" data-value="{region}" '
                f'style="--pill-color: {color};">{region} '
                f'<span class="count">{counts[region]}</span></button>'
            )
    parts.append('<button class="pill" data-filter="new" data-value="true">✦ New only</button>')
    return "".join(parts)


# Source pills shown before the "+N more" expander kicks in.
VISIBLE_SOURCE_PILLS = 8


def _render_source_pills(sources: list, events: List[Event]) -> str:
    counts = {}
    for e in events:
        counts[e.source] = counts.get(e.source, 0) + 1
    ordered = sorted(sources, key=lambda s: -counts.get(s, 0))

    def pill(source):
        return (f'<button class="pill" data-filter="source" data-value="{html.escape(source)}">'
                f'{html.escape(source)} <span class="count">{counts.get(source, 0)}</span></button>')

    parts = ['<button class="pill active" data-filter="source" data-value="all">All Sources</button>']
    parts += [pill(s) for s in ordered[:VISIBLE_SOURCE_PILLS]]
    overflow = ordered[VISIBLE_SOURCE_PILLS:]
    if overflow:
        parts.append('<span class="more-sources">' + "".join(pill(s) for s in overflow) + '</span>')
        parts.append(f'<button class="pill more-toggle" id="moreSources" type="button">'
                     f'+{len(overflow)} more</button>')
    return "".join(parts)


def _render_body(events: List[Event]) -> str:
    sections = []
    current_key = None
    current_buf = []
    events_in_section = []

    def flush():
        if current_key and current_buf:
            ym = events_in_section[0].start.strftime("%Y-%m") if events_in_section else ""
            sections.append(
                f'<section class="month-section" data-month="{ym}">'
                f'<h2 class="month-header" role="button" tabindex="0" aria-expanded="true">'
                f'<span>{html.escape(current_key)}</span>'
                f'<span class="count">{len(events_in_section)}</span></h2>'
                f'<div class="month-body"><div class="month-body-inner">'
                + "\n".join(current_buf)
                + "</div></div></section>"
            )

    for ev in events:
        key = ev.start.strftime("%B %Y")
        if key != current_key:
            flush()
            current_key = key
            current_buf = []
            events_in_section = []
        current_buf.append(_render_event(ev))
        events_in_section.append(ev)
    flush()
    return "\n".join(sections)


def _render_past(past: List[Event]) -> str:
    """Collapsed archive of recently-passed events, most recent first."""
    if not past:
        return ""
    cards = "\n".join(_render_event(ev) for ev in sorted(past, key=lambda e: e.start, reverse=True))
    return (f'<details class="past-archive">'
            f'<summary>Recently passed <span class="count">{len(past)}</span></summary>'
            f'{cards}</details>')


def _empty_body() -> str:
    return ('<div class="empty"><p class="empty-title">No upcoming events found.</p>'
            '<p class="empty-sub">The aggregator may be having trouble — '
            'check back tomorrow.</p></div>')


def _display_end(ev: Event) -> Optional[datetime]:
    """End datetime for display, or None for single-day events.

    iCal all-day DTENDs are exclusive (midnight after the last day), so a
    midnight end is pulled back one day before comparing.
    """
    if not ev.end:
        return None
    end = ev.end
    if end.hour == 0 and end.minute == 0:
        end = end - timedelta(days=1)
    return end if end.date() > ev.start.date() else None


def _ics_escape(s: str) -> str:
    return (s or "").replace("\\", "\\\\").replace(";", "\\;").replace(",", "\\,").replace("\n", "\\n")


def _event_ics_href(ev: Event) -> str:
    """Single-event .ics as a data: URI — per-event add-to-calendar without
    generating per-event files."""
    all_day = ev.start.hour == 0 and ev.start.minute == 0
    lines = [
        "BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//BD Events Aggregator//bd-events//EN",
        "BEGIN:VEVENT", f"UID:{ev.uid}", f"SUMMARY:{_ics_escape(ev.title)}",
    ]
    if all_day:
        lines.append(f"DTSTART;VALUE=DATE:{ev.start.strftime('%Y%m%d')}")
        if ev.end:
            end = ev.end if (ev.end.hour == 0 and ev.end.minute == 0) else ev.end + timedelta(days=1)
            if end.date() > ev.start.date():
                lines.append(f"DTEND;VALUE=DATE:{end.strftime('%Y%m%d')}")
    else:
        lines.append("DTSTART:" + ev.start.astimezone(timezone.utc).strftime("%Y%m%dT%H%M%SZ"))
        if ev.end:
            lines.append("DTEND:" + ev.end.astimezone(timezone.utc).strftime("%Y%m%dT%H%M%SZ"))
    if ev.location:
        lines.append(f"LOCATION:{_ics_escape(ev.location)}")
    if ev.url:
        lines.append(f"URL:{ev.url}")
        lines.append(f"DESCRIPTION:{_ics_escape('Source: ' + ev.source + chr(10) + ev.url)}")
    lines += ["END:VEVENT", "END:VCALENDAR"]
    return "data:text/calendar;charset=utf-8," + quote("\r\n".join(lines))


def _render_event(ev: Event) -> str:
    day = ev.start.strftime("%-d")
    dow = ev.start.strftime("%a")
    region = ev.region or "Bay Area"
    region_color = REGION_COLORS.get(region, "#aaa")
    is_new = getattr(ev, "is_new", False)
    new_badge = '<span class="new-badge">NEW</span>' if is_new else ''

    end_disp = _display_end(ev)
    range_part = ""
    time_part = ""
    if end_disp:
        same_month = (end_disp.year, end_disp.month) == (ev.start.year, ev.start.month)
        end_txt = end_disp.strftime("%-d") if same_month else end_disp.strftime("%b %-d")
        range_part = (f'<span class="meta-item time-badge">'
                      f'{ev.start.strftime("%b %-d")} – {end_txt}</span>')
    elif ev.start.hour != 0 or ev.start.minute != 0:
        local_time = ev.start.strftime("%-I:%M %p")
        time_part = f'<span class="meta-item time-badge">{local_time}</span>'

    location_part = ""
    if ev.location:
        loc_short = html.escape(ev.location[:80])
        location_part = f'<span class="meta-item location">{loc_short}</span>'

    title_html = html.escape(ev.title)
    url = html.escape(ev.url or "#")
    source_attr = html.escape(ev.source)
    slug = re.sub(r'[^a-z0-9]+', '-', ev.title.lower()).strip('-')[:48] or "event"
    cal_part = (f'<a class="meta-item cal-link" href="{_event_ics_href(ev)}" '
                f'download="{slug}.ics" title="Download .ics (Outlook / Apple / Google)">'
                f'+ Calendar</a>')

    return f'''<article class="event{' is-new' if is_new else ''}"
  data-source="{source_attr}"
  data-region="{region}"
  data-date="{ev.start.strftime('%Y-%m-%d')}"
  data-new="{str(is_new).lower()}"
  style="--tint: {region_color};">
  <div class="event-date">
    <div class="day">{day}</div>
    <div class="dow">{dow}</div>
  </div>
  <div class="event-body">
    <a class="event-title" href="{url}" target="_blank" rel="noopener">{title_html}</a>{new_badge}
    <div class="event-meta">
      <span class="meta-item region-tag" style="--tag-color: {region_color};">{html.escape(region)}</span>
      <span class="meta-item source-tag">{source_attr}</span>
      {range_part}
      {time_part}
      {location_part}
      {cal_part}
    </div>
  </div>
</article>'''


PAGE_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>BD Events — Bay Area, Sacramento &amp; San Diego</title>
<link rel="alternate" type="text/calendar" title="Subscribe (iCal)" href="events.ics">
<script>try {{ var t = localStorage.getItem('bd-theme'); if (t) document.documentElement.setAttribute('data-theme', t); }} catch (e) {{}}</script>
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');

:root {{
  --bg: {bg};
  --bg-deep: {bg_deep};
  --text: {text};
  --text-muted: {text_muted};
  --text-dim: {text_dim};
  --border-tr: {border_tr};
  --border-hard: {border_hard};
  --glass: {glass};
  --orange: {orange};
  --orange-soft: {orange_soft};
  --on-orange: #1a1a1a;
  --card-base: rgba(255,255,255,0.02);
  --card-base-hover: rgba(255,255,255,0.04);
  --chip-bg: rgba(255,255,255,0.03);
  --count-bg: rgba(255,255,255,0.10);
  --search-focus-bg: rgba(0,0,0,0.4);
  --tag-text-mix: white;
  interpolate-size: allow-keywords; /* lets height:auto animate (details) */
}}
html[data-theme="light"] {{
  --bg: #f3f1ee;
  --bg-deep: #ffffff;
  --text: #262626;
  --text-muted: rgba(38, 38, 38, 0.66);
  --text-dim: rgba(38, 38, 38, 0.42);
  --border-tr: rgba(38, 38, 38, 0.10);
  --border-hard: rgba(38, 38, 38, 0.16);
  --glass: rgba(38, 38, 38, 0.04);
  --card-base: #ffffff;
  --card-base-hover: #fffdfb;
  --chip-bg: rgba(38, 38, 38, 0.04);
  --count-bg: rgba(38, 38, 38, 0.10);
  --search-focus-bg: #ffffff;
  --tag-text-mix: #262626;
}}

*, *::before, *::after {{ margin: 0; padding: 0; box-sizing: border-box; }}
html {{ scroll-behavior: smooth; }}
body {{
  font-family: 'Inter', -apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, Arial, sans-serif;
  background: var(--bg);
  color: var(--text);
  line-height: 1.55;
  -webkit-font-smoothing: antialiased;
  min-height: 100vh;
  transition: background 0.25s, color 0.25s;
}}

.container {{ max-width: 1080px; margin: 0 auto; padding: 64px 28px 96px; }}

/* Hero */
.hero {{ padding-bottom: 40px; margin-bottom: 40px;
  border-bottom: 1px solid var(--border-hard); }}
.label {{ font-size: 11px; font-weight: 600; letter-spacing: 2.5px;
  text-transform: uppercase; color: var(--orange); margin-bottom: 18px;
  display: inline-block; padding: 6px 14px;
  background: var(--orange-soft); border: 1px solid #ff671f33;
  border-radius: 999px; }}
h1 {{ font-size: 72px; font-weight: 800; color: var(--text); line-height: 1.0;
  letter-spacing: -0.035em; margin-bottom: 18px; }}
h1 em {{ font-style: normal; color: var(--orange); }}
.subtitle {{ color: var(--text-muted); font-size: 17px; max-width: 620px; margin-bottom: 32px;
  font-weight: 400; }}

.meta-bar {{ display: flex; flex-wrap: wrap; gap: 10px; align-items: center; margin-top: 8px; }}
.subscribe {{ display: inline-flex; align-items: center; gap: 8px;
  background: var(--orange);
  color: var(--on-orange); padding: 13px 24px; border-radius: 999px; text-decoration: none;
  font-weight: 700; font-size: 13px; letter-spacing: 0.4px;
  box-shadow: 0 4px 12px rgba(255, 103, 31, 0.12);
  transition: transform 0.18s, box-shadow 0.18s; }}
.subscribe:hover {{ transform: translateY(-1px);
  box-shadow: 0 6px 16px rgba(255, 103, 31, 0.18); }}
.stat-pill {{ background: var(--glass);
  border: 1px solid var(--border-tr); border-radius: 999px;
  padding: 10px 16px; font-size: 12px; color: var(--text-muted); letter-spacing: 0.3px;
  font-weight: 500; }}
.stat-pill strong {{ color: var(--text); font-weight: 700; margin-right: 6px; }}
.stat-pill.new-pill {{ background: var(--orange-soft); border-color: #ff671f40; color: var(--orange); }}
.stat-pill.new-pill strong {{ color: var(--orange); }}
button.theme-toggle {{ cursor: pointer; font-family: inherit;
  transition: border-color 0.15s, color 0.15s; }}
button.theme-toggle:hover {{ border-color: #ff671f66; color: var(--orange); }}

/* Filter bar */
.filters {{ background: var(--glass);
  border: 1px solid var(--border-tr); border-radius: 16px;
  padding: 26px 28px; margin-bottom: 18px;
  box-shadow: 0 4px 16px rgba(0, 0, 0, 0.15); }}
.filter-group {{ margin-bottom: 18px; }}
.filter-group:last-child {{ margin-bottom: 0; }}
.filter-label {{ font-size: 11px; font-weight: 600; letter-spacing: 1.8px;
  text-transform: uppercase; color: var(--text-muted); margin-bottom: 10px; display: block; }}
.pill-row {{ display: flex; flex-wrap: wrap; gap: 6px; }}
.pill {{ background: var(--glass);
  border: 1px solid var(--border-tr); color: var(--text);
  padding: 8px 16px; border-radius: 999px; font-family: inherit; font-size: 12px;
  font-weight: 500; cursor: pointer; transition: all 0.15s;
  display: inline-flex; align-items: center; gap: 7px; }}
.pill:hover {{ border-color: #ff671f66; color: var(--orange);
  background: var(--orange-soft); }}
.pill.active {{ background: var(--orange); color: var(--on-orange); border-color: var(--orange);
  font-weight: 600; box-shadow: 0 2px 8px rgba(255,103,31,0.12); }}
.pill[data-filter="region"].active {{
  background: var(--pill-color, var(--orange)); border-color: var(--pill-color, var(--orange));
  color: #1a1a1a;
  box-shadow: 0 2px 8px color-mix(in srgb, var(--pill-color, var(--orange)) 18%, transparent); }}
.pill .count {{ background: var(--count-bg); padding: 1px 7px; border-radius: 8px;
  font-size: 10px; font-weight: 700; min-width: 18px; text-align: center; }}
.pill.active .count {{ background: rgba(0,0,0,0.18); color: inherit; }}

/* Search */
.search-box {{ width: 100%; background: var(--bg-deep); border: 1px solid var(--border-tr);
  color: var(--text); padding: 14px 18px; border-radius: 12px;
  font-family: inherit; font-size: 14px; transition: all 0.15s; }}
.search-box:focus {{ outline: none; border-color: #ff671f66;
  background: var(--search-focus-bg); box-shadow: 0 0 0 2px var(--orange-soft); }}
.search-box::placeholder {{ color: var(--text-dim); }}

/* Collapsible calendar view */
.cal-view {{ margin-bottom: 44px; }}
.cal-view summary {{ cursor: pointer; list-style: none;
  display: inline-flex; align-items: center; gap: 10px;
  font-size: 11px; font-weight: 600; letter-spacing: 1.8px; text-transform: uppercase;
  color: var(--text-muted); padding: 10px 18px;
  background: var(--glass); border: 1px solid var(--border-tr); border-radius: 999px;
  transition: color 0.15s, border-color 0.15s; }}
.cal-view summary::-webkit-details-marker {{ display: none; }}
.cal-view summary::before {{ content: '▸'; color: var(--orange); transition: transform 0.15s; }}
.cal-view[open] summary::before {{ transform: rotate(90deg); }}
.cal-view summary:hover {{ color: var(--orange); border-color: #ff671f66; }}
.cal-card {{ margin-top: 12px; background: var(--glass);
  border: 1px solid var(--border-tr); border-radius: 16px; padding: 22px 24px; }}
.cal-nav {{ display: flex; align-items: center; justify-content: space-between;
  margin-bottom: 16px; }}
.cal-nav .pill {{ padding: 6px 14px; font-size: 14px; line-height: 1; }}
#calTitle {{ font-size: 14px; font-weight: 700; letter-spacing: 1.5px;
  text-transform: uppercase; color: var(--text); }}
.cal-grid {{ display: grid; grid-template-columns: repeat(7, 1fr); gap: 4px; }}
.cal-dow {{ text-align: center; font-size: 10px; font-weight: 700; letter-spacing: 1.2px;
  color: var(--text-dim); text-transform: uppercase; padding: 4px 0 8px; }}
.cal-day {{ min-height: 58px; border-radius: 10px; padding: 6px 8px;
  border: 1px solid transparent; font-size: 12px; color: var(--text-dim);
  display: flex; flex-direction: column; gap: 5px;
  transition: background 0.15s, border-color 0.15s, transform 0.12s;
  animation: fadeIn 0.25s ease both; }}
.cal-day.has-events:active {{ transform: scale(0.95); }}
.cal-day.in-month {{ color: var(--text-muted); background: var(--chip-bg);
  border-color: var(--border-tr); }}
.cal-day.today {{ border-color: var(--orange); }}
.cal-day.today .cal-num {{ color: var(--orange); font-weight: 800; }}
.cal-day.has-events {{ cursor: pointer; }}
.cal-day.has-events:hover {{ border-color: #ff671f66; background: var(--orange-soft); }}
.cal-day.has-events .cal-num {{ color: var(--text); font-weight: 700; }}
.cal-num {{ font-size: 12px; line-height: 1; }}
.cal-dots {{ display: flex; flex-wrap: wrap; gap: 3px; align-items: center; }}
.cal-dot {{ width: 7px; height: 7px; border-radius: 50%; display: inline-block; }}
.cal-more {{ font-size: 9px; font-weight: 700; color: var(--text-dim); }}

/* Month sections — headers toggle a smooth grid-rows collapse */
.month-section {{ margin-bottom: 56px; }}
.month-section.collapsed {{ margin-bottom: 28px; }}
.month-header {{ font-size: 14px; font-weight: 600; color: var(--text-muted);
  letter-spacing: 2.5px; text-transform: uppercase; margin-bottom: 20px;
  display: flex; align-items: center; gap: 16px;
  cursor: pointer; user-select: none; transition: color 0.2s; }}
.month-header:hover {{ color: var(--text); }}
.month-header::before {{ content: '▾'; color: var(--orange); flex-shrink: 0;
  transition: transform 0.25s ease; }}
.month-section.collapsed .month-header::before {{ transform: rotate(-90deg); }}
.month-header span {{ flex-shrink: 0; }}
.month-header .count {{ background: var(--count-bg); padding: 2px 9px;
  border-radius: 8px; font-size: 11px; letter-spacing: 0; }}
.month-header::after {{ content: ''; flex: 1; height: 1px;
  background: linear-gradient(to right, var(--border-hard), transparent); }}
.month-body {{ display: grid; grid-template-rows: 1fr;
  transition: grid-template-rows 0.35s ease; }}
.month-body-inner {{ min-height: 0; overflow: hidden; }}
.month-section.collapsed .month-body {{ grid-template-rows: 0fr; }}

/* Event cards — region-tinted bg, halved hover bloom */
.event {{
  background: color-mix(in srgb, var(--tint, white) 8%, var(--card-base));
  border: 1px solid color-mix(in srgb, var(--tint, white) 20%, var(--border-tr));
  border-radius: 14px;
  padding: 22px 26px; margin-bottom: 10px;
  display: grid; grid-template-columns: 70px 1fr; gap: 22px; align-items: start;
  transition: transform 0.18s, background 0.18s, border-color 0.18s, box-shadow 0.18s;
}}
.event:hover {{
  background: color-mix(in srgb, var(--tint, white) 12%, var(--card-base-hover));
  border-color: color-mix(in srgb, var(--tint, white) 30%, var(--border-hard));
  transform: translateY(-1px);
  box-shadow: 0 4px 14px rgba(0,0,0,0.18);
}}
.event.flash {{ outline: 2px solid var(--orange); outline-offset: 2px; }}

/* New events override the region tint with an orange tint */
.event.is-new {{
  background: color-mix(in srgb, var(--orange) 6%, var(--card-base));
  border-color: rgba(255,103,31,0.22);
}}
.event.is-new:hover {{
  background: color-mix(in srgb, var(--orange) 9%, var(--card-base-hover));
  border-color: rgba(255,103,31,0.32);
}}

.event-date {{ text-align: center; padding-top: 4px; line-height: 1; }}
.event-date .day {{ font-size: 38px; font-weight: 800; color: var(--text);
  line-height: 1; letter-spacing: -0.03em; }}
.event-date .dow {{ font-size: 10px; color: var(--orange); text-transform: uppercase;
  letter-spacing: 1.8px; margin-top: 8px; font-weight: 700; }}

.event-body a.event-title {{ color: var(--text); font-size: 16px; font-weight: 600;
  text-decoration: none; line-height: 1.4; display: inline; letter-spacing: -0.005em; }}
.event-body a.event-title:hover {{ color: var(--orange); }}
.new-badge {{ display: inline-block;
  background: var(--orange);
  color: var(--on-orange);
  font-size: 9px; font-weight: 800; letter-spacing: 1.2px; padding: 3px 8px;
  border-radius: 4px; margin-left: 10px; vertical-align: 2px;
  box-shadow: 0 1px 4px rgba(255,103,31,0.15);
  animation: pulse 2.4s ease-in-out infinite; }}
@keyframes pulse {{ 0%, 100% {{ opacity: 1; }} 50% {{ opacity: 0.7; }} }}

.event-meta {{ display: flex; flex-wrap: wrap; gap: 8px; margin-top: 12px;
  font-size: 12px; color: var(--text-muted); align-items: center; }}
.meta-item {{ display: inline-flex; align-items: center; gap: 5px;
  padding: 4px 10px; border-radius: 999px;
  background: var(--chip-bg); border: 1px solid var(--border-tr); }}
.region-tag {{ font-weight: 600; font-size: 11px;
  background: color-mix(in srgb, var(--tag-color) 14%, transparent);
  color: color-mix(in srgb, var(--tag-color) 78%, var(--tag-text-mix));
  border-color: color-mix(in srgb, var(--tag-color) 35%, transparent); }}
.source-tag {{ font-weight: 500; font-size: 11px; color: var(--text-muted); }}
.location {{ color: var(--text-muted); }}
.time-badge {{ color: var(--text); font-weight: 500; }}
.soon-badge {{ background: var(--orange-soft); color: var(--orange);
  border-color: #ff671f40; font-weight: 700; font-size: 11px; }}
a.cal-link {{ color: var(--text-dim); text-decoration: none; font-weight: 500; }}
a.cal-link:hover {{ color: var(--orange); border-color: #ff671f66; }}
.more-sources {{ display: none; }}
.more-sources.open {{ display: contents; }}
.pill.more-toggle {{ border-style: dashed; color: var(--text-muted); }}
.ago-badge {{ color: var(--text-dim); font-weight: 600; font-size: 11px; }}

/* Recently passed archive — muted, collapsed by default */
.past-archive {{ margin-top: 64px; }}
.past-archive summary {{ cursor: pointer; list-style: none;
  font-size: 14px; font-weight: 600; color: var(--text-muted);
  letter-spacing: 2.5px; text-transform: uppercase; margin-bottom: 20px;
  display: flex; align-items: center; gap: 12px; }}
.past-archive summary::-webkit-details-marker {{ display: none; }}
.past-archive summary::before {{ content: '▸'; color: var(--orange); transition: transform 0.15s; }}
.past-archive[open] summary::before {{ transform: rotate(90deg); }}
.past-archive summary .count {{ background: var(--count-bg); padding: 2px 9px;
  border-radius: 8px; font-size: 11px; }}
.past-archive summary:hover {{ color: var(--text); }}
.past-archive .event {{ opacity: 0.55; }}
.past-archive .event:hover {{ opacity: 1; }}

/* Empty state */
.empty {{ text-align: center; padding: 80px 24px; background: var(--glass);
  border: 1px dashed var(--border-tr);
  border-radius: 16px; margin-top: 20px; }}
.empty-title {{ font-size: 17px; color: var(--text); margin-bottom: 8px; font-weight: 600; }}
.empty-sub {{ font-size: 14px; color: var(--text-muted); }}

footer {{ margin-top: 80px; padding-top: 36px; border-top: 1px solid var(--border-hard);
  color: var(--text-muted); font-size: 12px; line-height: 1.7; }}
footer a {{ color: var(--orange); text-decoration: none; }}
footer a:hover {{ text-decoration: underline; }}
.footer-label {{ display: block; font-size: 11px; letter-spacing: 1.8px; text-transform: uppercase;
  color: var(--orange); margin-bottom: 10px; font-weight: 600; }}

/* Interaction polish */
@keyframes fadeIn {{ from {{ opacity: 0; transform: translateY(3px); }} }}
.pill:active, .subscribe:active, button.theme-toggle:active {{ transform: scale(0.96); }}
.cal-view summary:active, .past-archive summary:active, .month-header:active {{ transform: scale(0.99); }}
.meta-item, a.cal-link {{ transition: color 0.15s, border-color 0.15s, background 0.15s; }}
.event.flash {{ transition: outline-color 0.3s; }}
/* Smooth open/close for <details> panels (calendar, recently passed) in
   browsers that support ::details-content; harmless no-op elsewhere */
details::details-content {{
  transition: height 0.3s ease, content-visibility 0.3s allow-discrete;
  height: 0; overflow: clip; }}
details[open]::details-content {{ height: auto; }}

@media (prefers-reduced-motion: reduce) {{
  *, *::before, *::after {{
    transition-duration: 0.01ms !important;
    animation-duration: 0.01ms !important; }}
  html {{ scroll-behavior: auto; }}
}}

@media (max-width: 720px) {{
  .container {{ padding: 44px 18px 72px; }}
  h1 {{ font-size: 46px; }}
  .subtitle {{ font-size: 15px; }}
  .event {{ grid-template-columns: 56px 1fr; gap: 16px; padding: 18px 18px; }}
  .event-date .day {{ font-size: 32px; }}
  .filters {{ padding: 20px 20px; }}
  .meta-bar {{ gap: 8px; }}
  .stat-pill, .subscribe {{ font-size: 11px; padding: 9px 16px; }}
  .cal-day {{ min-height: 44px; padding: 4px 5px; }}
  .cal-dot {{ width: 5px; height: 5px; }}
}}
</style>
</head>
<body>
<div class="container">
  <header class="hero">
    <span class="label">BD Resource Library — 12</span>
    <h1>BD <em>Events</em></h1>
    <p class="subtitle">Aggregated AEC industry events across the Bay Area, Sacramento, and San Diego. Updated automatically.</p>
    <div class="meta-bar">
      <a class="subscribe" href="events.ics" download>📅 Subscribe in Outlook</a>
      <span class="stat-pill"><strong id="visibleCount">{event_count}</strong>upcoming</span>
      <span class="stat-pill"><strong>{source_count}</strong>sources</span>
      {new_pill_html}
      <span class="stat-pill">Updated {updated_at}</span>
      <button id="themeToggle" class="stat-pill theme-toggle" type="button" aria-label="Toggle light/dark theme">☀️ Light</button>
    </div>
  </header>

  <div class="filters">
    <div class="filter-group">
      <label class="filter-label">Search</label>
      <input id="searchInput" class="search-box" type="text" placeholder="Filter by title, location, or source...">
    </div>
    <div class="filter-group">
      <label class="filter-label">Region</label>
      <div class="pill-row">{region_pills}</div>
    </div>
    <div class="filter-group">
      <label class="filter-label">Source</label>
      <div class="pill-row">{source_pills}</div>
    </div>
  </div>

  <details class="cal-view" id="calView">
    <summary>Calendar view</summary>
    <div class="cal-card">
      <div class="cal-nav">
        <button id="calPrev" class="pill" type="button" aria-label="Previous month">‹</button>
        <span id="calTitle"></span>
        <button id="calNext" class="pill" type="button" aria-label="Next month">›</button>
      </div>
      <div class="cal-grid" id="calGrid"></div>
    </div>
  </details>

  <main id="eventsContainer">
    {body}
    {past_html}
  </main>

  <div id="emptyState" class="empty" style="display: none;">
    <p class="empty-title">No matches</p>
    <p class="empty-sub">Try clearing one of the active filters above.</p>
  </div>

  <footer>
    <span class="footer-label">About this page</span>
    Generated automatically by the BD Events Aggregator. The
    <a href="events.ics">.ics calendar feed</a> can be subscribed in Outlook, Apple Calendar, or
    Google Calendar — events refresh on their own every few hours.<br><br>
    Sources tracked: {sources_list}
  </footer>
</div>

<script>
(function() {{
  const REGION_COLORS = {region_colors_json};
  const filters = {{ region: 'all', source: 'all', new: 'all', search: '' }};

  // --- Theme toggle (persisted; pre-paint script in <head> avoids flash) ---
  const themeBtn = document.getElementById('themeToggle');
  function syncThemeBtn() {{
    const light = document.documentElement.getAttribute('data-theme') === 'light';
    themeBtn.textContent = light ? '🌙 Dark' : '☀️ Light';
  }}
  themeBtn.addEventListener('click', function() {{
    const light = document.documentElement.getAttribute('data-theme') === 'light';
    const next = light ? '' : 'light';
    if (next) document.documentElement.setAttribute('data-theme', next);
    else document.documentElement.removeAttribute('data-theme');
    try {{ localStorage.setItem('bd-theme', next); }} catch (e) {{}}
    syncThemeBtn();
  }});
  syncThemeBtn();

  function updateHash() {{
    const p = new URLSearchParams();
    if (filters.region !== 'all') p.set('region', filters.region);
    if (filters.source !== 'all') p.set('source', filters.source);
    if (filters.new !== 'all') p.set('new', '1');
    if (filters.search) p.set('q', filters.search);
    const s = p.toString();
    history.replaceState(null, '', s ? '#' + s : location.pathname + location.search);
  }}

  function applyFilters() {{
    const events = document.querySelectorAll('.event');
    const search = filters.search.toLowerCase();
    let visible = 0;
    events.forEach(ev => {{
      let show = true;
      if (filters.region !== 'all' && ev.dataset.region !== filters.region) show = false;
      if (filters.source !== 'all' && ev.dataset.source !== filters.source) show = false;
      if (filters.new !== 'all' && ev.dataset.new !== 'true') show = false;
      if (search && !ev.innerText.toLowerCase().includes(search)) show = false;
      ev.style.display = show ? '' : 'none';
      if (show && !ev.closest('.past-archive')) visible++;
    }});
    document.querySelectorAll('.month-section').forEach(sec => {{
      const anyVisible = sec.querySelector('.event:not([style*="display: none"])');
      sec.style.display = anyVisible ? '' : 'none';
    }});
    document.getElementById('visibleCount').textContent = visible;
    document.getElementById('eventsContainer').style.display = visible ? '' : 'none';
    document.getElementById('emptyState').style.display = visible ? 'none' : '';
    updateHash();
    renderCalendar();
  }}

  document.querySelectorAll('.pill[data-filter]').forEach(btn => {{
    btn.addEventListener('click', function() {{
      const dim = this.dataset.filter;
      const val = this.dataset.value;
      if (dim === 'new') {{
        const isOn = this.classList.toggle('active');
        filters.new = isOn ? 'true' : 'all';
      }} else {{
        document.querySelectorAll('.pill[data-filter="' + dim + '"]').forEach(b => b.classList.remove('active'));
        this.classList.add('active');
        filters[dim] = val;
      }}
      applyFilters();
    }});
  }});

  document.getElementById('searchInput').addEventListener('input', function(e) {{
    filters.search = e.target.value;
    applyFilters();
  }});

  // Collapsible month sections
  document.querySelectorAll('.month-header').forEach(h => {{
    function toggle() {{
      const sec = h.closest('.month-section');
      const collapsed = sec.classList.toggle('collapsed');
      h.setAttribute('aria-expanded', String(!collapsed));
    }}
    h.addEventListener('click', toggle);
    h.addEventListener('keydown', e => {{
      if (e.key === 'Enter' || e.key === ' ') {{ e.preventDefault(); toggle(); }}
    }});
  }});

  // "+N more" source pills expander
  const moreBtn = document.getElementById('moreSources');
  function showAllSources() {{
    const hidden = document.querySelector('.more-sources');
    if (hidden) hidden.classList.add('open');
    if (moreBtn) moreBtn.remove();
  }}
  if (moreBtn) moreBtn.addEventListener('click', showAllSources);

  // Relative date cues for events within 7 days either side (computed
  // client-side so they stay correct between daily rebuilds)
  const today = new Date(); today.setHours(0, 0, 0, 0);
  document.querySelectorAll('.event[data-date]').forEach(ev => {{
    const d = new Date(ev.dataset.date + 'T00:00:00');
    const days = Math.round((d - today) / 86400000);
    let label = null, cls = 'soon-badge';
    if (days === 0) label = 'Today';
    else if (days === 1) label = 'Tomorrow';
    else if (days > 1 && days <= 7) label = 'In ' + days + ' days';
    else if (days === -1) {{ label = 'Yesterday'; cls = 'ago-badge'; }}
    else if (days < -1) {{ label = (-days) + ' days ago'; cls = 'ago-badge'; }}
    if (label) {{
      const chip = document.createElement('span');
      chip.className = 'meta-item ' + cls;
      chip.textContent = label;
      const meta = ev.querySelector('.event-meta');
      meta.insertBefore(chip, meta.firstChild);
    }}
  }});

  // --- Collapsible calendar view (reflects active filters) ---
  let calY = today.getFullYear(), calM = today.getMonth();
  const todayStr = today.getFullYear() + '-' +
    String(today.getMonth() + 1).padStart(2, '0') + '-' +
    String(today.getDate()).padStart(2, '0');

  function visibleEventsByDate() {{
    const map = {{}};
    document.querySelectorAll('.event[data-date]').forEach(ev => {{
      if (ev.style.display === 'none') return;
      (map[ev.dataset.date] = map[ev.dataset.date] || []).push(ev);
    }});
    return map;
  }}

  function renderCalendar() {{
    const grid = document.getElementById('calGrid');
    if (!grid) return;
    document.getElementById('calTitle').textContent =
      new Date(calY, calM, 1).toLocaleString('en-US', {{ month: 'long', year: 'numeric' }});
    const map = visibleEventsByDate();
    grid.innerHTML = '';
    ['SUN', 'MON', 'TUE', 'WED', 'THU', 'FRI', 'SAT'].forEach(d => {{
      const h = document.createElement('div');
      h.className = 'cal-dow';
      h.textContent = d;
      grid.appendChild(h);
    }});
    const startDow = new Date(calY, calM, 1).getDay();
    const daysInMonth = new Date(calY, calM + 1, 0).getDate();
    for (let i = 0; i < startDow; i++) {{
      grid.appendChild(Object.assign(document.createElement('div'), {{ className: 'cal-day' }}));
    }}
    for (let d = 1; d <= daysInMonth; d++) {{
      const ds = calY + '-' + String(calM + 1).padStart(2, '0') + '-' + String(d).padStart(2, '0');
      const cell = document.createElement('div');
      cell.className = 'cal-day in-month';
      const num = document.createElement('span');
      num.className = 'cal-num';
      num.textContent = d;
      cell.appendChild(num);
      if (ds === todayStr) cell.classList.add('today');
      const evs = map[ds] || [];
      if (evs.length) {{
        cell.classList.add('has-events');
        cell.title = evs.map(e => e.querySelector('.event-title').textContent).join('\\n');
        const dots = document.createElement('div');
        dots.className = 'cal-dots';
        evs.slice(0, 4).forEach(e => {{
          const dot = document.createElement('span');
          dot.className = 'cal-dot';
          dot.style.background = REGION_COLORS[e.dataset.region] || '#aaa';
          dots.appendChild(dot);
        }});
        if (evs.length > 4) {{
          const more = document.createElement('span');
          more.className = 'cal-more';
          more.textContent = '+' + (evs.length - 4);
          dots.appendChild(more);
        }}
        cell.appendChild(dots);
        cell.addEventListener('click', function() {{
          const target = evs[0];
          const archive = target.closest('.past-archive');
          if (archive) archive.open = true;
          target.scrollIntoView({{ behavior: 'smooth', block: 'center' }});
          target.classList.add('flash');
          setTimeout(() => target.classList.remove('flash'), 1800);
        }});
      }}
      grid.appendChild(cell);
    }}
  }}

  document.getElementById('calPrev').addEventListener('click', function() {{
    calM--; if (calM < 0) {{ calM = 11; calY--; }}
    renderCalendar();
  }});
  document.getElementById('calNext').addEventListener('click', function() {{
    calM++; if (calM > 11) {{ calM = 0; calY++; }}
    renderCalendar();
  }});
  document.getElementById('calView').addEventListener('toggle', renderCalendar);

  // Restore filters from the URL so bookmarked/shared views stick
  (function restoreFromHash() {{
    const p = new URLSearchParams(location.hash.slice(1));
    const q = p.get('q');
    if (q) {{
      const input = document.getElementById('searchInput');
      input.value = q;
      filters.search = q;
    }}
    ['region', 'source'].forEach(dim => {{
      const val = p.get(dim);
      if (!val) return;
      const pill = document.querySelector('.pill[data-filter="' + dim + '"][data-value="' + CSS.escape(val) + '"]');
      if (!pill) return;
      if (pill.closest('.more-sources')) showAllSources();
      document.querySelectorAll('.pill[data-filter="' + dim + '"]').forEach(b => b.classList.remove('active'));
      pill.classList.add('active');
      filters[dim] = val;
    }});
    if (p.get('new') === '1') {{
      const pill = document.querySelector('.pill[data-filter="new"]');
      if (pill) {{ pill.classList.add('active'); filters.new = 'true'; }}
    }}
    applyFilters();
  }})();
}})();
</script>
</body>
</html>
"""


def write_html(events: List[Event], path: str) -> None:
    today = datetime.now(timezone.utc).date()
    upcoming = [e for e in events if e.start.date() >= today]
    past = [e for e in events if e.start.date() < today]

    sources_seen = sorted({e.source for e in events})
    new_count = sum(1 for e in upcoming if getattr(e, "is_new", False))
    new_pill_html = (
        f'<span class="stat-pill new-pill"><strong>{new_count}</strong>new this week</span>'
        if new_count else ''
    )

    body = _render_body(upcoming) if upcoming else _empty_body()
    past_html = _render_past(past)
    region_pills = _render_region_pills(events)
    source_pills = _render_source_pills(sources_seen, events)

    page = PAGE_TEMPLATE.format(
        bg=L10_BG, bg_deep=L10_BG_DEEP,
        text=L10_TEXT, text_muted=L10_TEXT_MUTED, text_dim=L10_TEXT_DIM,
        border_tr=L10_BORDER_TR, border_hard=L10_BORDER_HARD,
        glass=L10_GLASS,
        orange=L10_ORANGE, orange_soft=L10_ORANGE_SOFT,
        event_count=len(upcoming),
        source_count=len(sources_seen),
        new_pill_html=new_pill_html,
        updated_at=datetime.now(timezone.utc).strftime("%b %-d, %Y at %H:%M UTC"),
        body=body,
        past_html=past_html,
        region_pills=region_pills,
        source_pills=source_pills,
        sources_list=", ".join(html.escape(s) for s in sources_seen),
        region_colors_json=json.dumps(REGION_COLORS),
    )
    with open(path, "w", encoding="utf-8") as f:
        f.write(page)
    print(f"  Wrote HTML page to {path}")
