"""Generate the bookmarkable HTML page from aggregated events.

v3 features:
  - Filter pills at top (region, source, "new only", "this month")
  - Live filtering with no page reload — pure client-side JS, no framework
  - "New" pulse badge on events first seen in the last 7 days
  - Empty state when filters yield nothing
"""
from datetime import datetime, timezone
from typing import List
import html
import json

from scrapers.base import Event


REGION_COLORS = {
    "NorCal": "#0a66c2",
    "SoCal":  "#ec4899",
    "Other":   "#10b981",
}


def _render_region_pills(events: List[Event]) -> str:
    """Region filter pills — count of events per region."""
    counts = {}
    for e in events:
        counts[e.source_region or "Other"] = counts.get(e.source_region or "Other", 0) + 1
    parts = ['<button class="pill active" data-filter="region" data-value="all">All Regions</button>']
    for region in ["NorCal", "SoCal", "Other"]:
        if region in counts:
            color = REGION_COLORS.get(region, "#6b7280")
            parts.append(
                f'<button class="pill" data-filter="region" data-value="{region}" '
                f'style="--pill-color: {color};">{region} <span class="count">{counts[region]}</span></button>'
            )
    return "".join(parts)


def _render_source_pills(sources: list, events: List[Event]) -> str:
    """Source filter pills — one per source, with count."""
    counts = {}
    for e in events:
        counts[e.source] = counts.get(e.source, 0) + 1
    parts = ['<button class="pill active" data-filter="source" data-value="all">All Sources</button>']
    # Order: most events first
    for source in sorted(sources, key=lambda s: -counts.get(s, 0)):
        c = counts.get(source, 0)
        parts.append(
            f'<button class="pill" data-filter="source" data-value="{html.escape(source)}">'
            f'{html.escape(source)} <span class="count">{c}</span></button>'
        )
    return "".join(parts)


def _render_body(events: List[Event]) -> str:
    sections = []
    current_key = None
    current_buf = []

    def flush():
        if current_key and current_buf:
            year_month = events_in_section[0].start.strftime("%Y-%m") if events_in_section else ""
            sections.append(
                f'<div class="month-section" data-month="{year_month}">'
                f'<h2 class="month-header">{html.escape(current_key)}</h2>'
                + "\n".join(current_buf)
                + "</div>"
            )

    events_in_section = []
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


def _empty_body() -> str:
    return ('<div class="empty"><p class="empty-title">No upcoming events found.</p>'
            '<p class="empty-sub">The aggregator may be having trouble — '
            'check back tomorrow.</p></div>')


def _render_event(ev: Event) -> str:
    day = ev.start.strftime("%-d")
    dow = ev.start.strftime("%a")
    region = ev.source_region or "Other"
    region_color = REGION_COLORS.get(region, "#6b7280")
    is_new = getattr(ev, "is_new", False)
    new_badge = '<span class="new-badge">NEW</span>' if is_new else ''

    time_part = ""
    if ev.start.hour != 0 or ev.start.minute != 0:
        local_time = ev.start.strftime("%-I:%M %p")
        time_part = f'<span class="time-badge">🕐 {local_time}</span>'

    location_part = ""
    if ev.location:
        loc_short = html.escape(ev.location[:80])
        location_part = f'<span class="location">📍 {loc_short}</span>'

    title_html = html.escape(ev.title)
    url = html.escape(ev.url or "#")
    source_attr = html.escape(ev.source)

    return f'''<div class="event{' is-new' if is_new else ''}"
  data-source="{source_attr}"
  data-region="{region}"
  data-new="{str(is_new).lower()}">
  <div class="event-date">
    <div class="day">{day}</div>
    <div class="dow">{dow}</div>
  </div>
  <div class="event-body">
    <a class="event-title" href="{url}" target="_blank" rel="noopener">{title_html}</a>{new_badge}
    <div class="event-meta">
      <span class="source-tag" style="background: {region_color}22; color: {region_color};">{source_attr}</span>
      {time_part}
      {location_part}
    </div>
  </div>
</div>'''


PAGE_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>BD Events — Bay Area &amp; San Diego</title>
<link rel="alternate" type="text/calendar" title="Subscribe (iCal)" href="events.ics">
<style>
@import url('https://fonts.googleapis.com/css2?family=DM+Serif+Display&family=DM+Sans:wght@400;500;600;700&display=swap');
* {{ margin: 0; padding: 0; box-sizing: border-box; }}
body {{ font-family: 'DM Sans', sans-serif; background: #0f1419; color: #e7e9ea; line-height: 1.6; }}
.container {{ max-width: 980px; margin: 0 auto; padding: 48px 24px 80px; }}

.hero {{ border-bottom: 1px solid #2f3336; padding-bottom: 32px; margin-bottom: 28px; }}
.badge {{ display: inline-block; font-size: 11px; font-weight: 700; letter-spacing: 2px;
  text-transform: uppercase; color: #f59e0b; border: 1px solid #f59e0b33; padding: 4px 12px;
  border-radius: 20px; margin-bottom: 16px; }}
h1 {{ font-family: 'DM Serif Display', serif; font-size: 42px; color: #fff; line-height: 1.15; margin-bottom: 8px; }}
.subtitle {{ color: #71767b; font-size: 15px; margin-bottom: 24px; }}

.meta-bar {{ display: flex; flex-wrap: wrap; gap: 12px; align-items: center; margin-top: 16px; }}
.subscribe {{ display: inline-flex; align-items: center; gap: 8px; background: #0a66c2;
  color: white; padding: 10px 18px; border-radius: 10px; text-decoration: none;
  font-weight: 600; font-size: 14px; transition: background 0.15s; }}
.subscribe:hover {{ background: #0958a8; }}
.stat-pill {{ background: #16181c; border: 1px solid #2f3336; border-radius: 20px;
  padding: 6px 14px; font-size: 13px; color: #cfd4d8; }}
.stat-pill strong {{ color: #fff; }}
.stat-pill.new-pill {{ background: #f59e0b22; border-color: #f59e0b66; color: #fbbf24; }}

/* Filter bar */
.filters {{ background: #16181c; border: 1px solid #2f3336; border-radius: 14px;
  padding: 16px 20px; margin-bottom: 32px; }}
.filter-group {{ margin-bottom: 12px; }}
.filter-group:last-child {{ margin-bottom: 0; }}
.filter-label {{ font-size: 11px; font-weight: 700; letter-spacing: 1.5px; text-transform: uppercase;
  color: #71767b; margin-bottom: 8px; display: block; }}
.pill-row {{ display: flex; flex-wrap: wrap; gap: 6px; }}
.pill {{ background: transparent; border: 1px solid #2f3336; color: #cfd4d8;
  padding: 6px 14px; border-radius: 16px; font-family: inherit; font-size: 13px;
  font-weight: 500; cursor: pointer; transition: all 0.12s;
  display: inline-flex; align-items: center; gap: 6px; }}
.pill:hover {{ border-color: #4b5563; }}
.pill.active {{ background: #f59e0b; color: #0f1419; border-color: #f59e0b; font-weight: 600; }}
.pill[data-filter="region"].active {{ background: var(--pill-color, #f59e0b); border-color: var(--pill-color, #f59e0b); }}
.pill .count {{ background: rgba(255,255,255,0.15); padding: 1px 7px; border-radius: 10px;
  font-size: 11px; font-weight: 700; }}
.pill.active .count {{ background: rgba(0,0,0,0.18); }}

/* Search input */
.search-box {{ width: 100%; background: #0f1419; border: 1px solid #2f3336; color: #e7e9ea;
  padding: 10px 14px; border-radius: 10px; font-family: inherit; font-size: 14px; }}
.search-box:focus {{ outline: none; border-color: #f59e0b; }}
.search-box::placeholder {{ color: #4b5563; }}

.month-section {{ margin-bottom: 48px; }}
.month-header {{ font-family: 'DM Serif Display', serif; font-size: 26px; color: #fff;
  margin-bottom: 16px; padding-left: 14px; border-left: 3px solid #f59e0b; }}

.event {{ background: #16181c; border: 1px solid #2f3336; border-radius: 12px;
  padding: 18px 22px; margin-bottom: 10px; display: grid;
  grid-template-columns: 80px 1fr; gap: 18px; align-items: start;
  transition: border-color 0.15s; position: relative; }}
.event:hover {{ border-color: #4b5563; }}
.event.is-new {{ border-color: #f59e0b66; }}
.event.is-new::before {{ content: ''; position: absolute; left: -1px; top: 18px; bottom: 18px;
  width: 3px; background: #f59e0b; border-radius: 2px; }}

.event-date {{ text-align: center; padding-top: 4px; }}
.event-date .day {{ font-family: 'DM Serif Display', serif; font-size: 32px;
  color: #f59e0b; line-height: 1; }}
.event-date .dow {{ font-size: 11px; color: #71767b; text-transform: uppercase;
  letter-spacing: 1.5px; margin-top: 4px; font-weight: 600; }}

.event-body a.event-title {{ color: #fff; font-size: 16px; font-weight: 600;
  text-decoration: none; line-height: 1.35; display: inline; margin-bottom: 6px; }}
.event-body a.event-title:hover {{ color: #f59e0b; }}
.new-badge {{ display: inline-block; background: #f59e0b; color: #0f1419;
  font-size: 10px; font-weight: 800; letter-spacing: 1px; padding: 2px 7px;
  border-radius: 4px; margin-left: 8px; vertical-align: 2px;
  animation: pulse 2.5s ease-in-out infinite; }}
@keyframes pulse {{ 0%, 100% {{ opacity: 1; }} 50% {{ opacity: 0.65; }} }}

.event-meta {{ display: flex; flex-wrap: wrap; gap: 10px; margin-top: 8px;
  font-size: 12px; color: #71767b; align-items: center; }}
.source-tag {{ font-weight: 600; font-size: 11px; padding: 3px 10px; border-radius: 12px;
  letter-spacing: 0.4px; }}
.location {{ color: #a0a4a8; }}
.time-badge {{ color: #cfd4d8; font-weight: 500; }}

.empty {{ text-align: center; padding: 60px 20px; color: #71767b; background: #16181c;
  border: 1px dashed #2f3336; border-radius: 12px; margin-top: 20px; }}
.empty-title {{ font-size: 16px; color: #cfd4d8; margin-bottom: 6px; }}
.empty-sub {{ font-size: 14px; }}

footer {{ margin-top: 64px; padding-top: 24px; border-top: 1px solid #2f3336;
  color: #71767b; font-size: 12px; line-height: 1.7; }}
footer a {{ color: #cfd4d8; }}

@media (max-width: 600px) {{
  h1 {{ font-size: 32px; }}
  .event {{ grid-template-columns: 60px 1fr; gap: 12px; padding: 14px 16px; }}
  .event-date .day {{ font-size: 26px; }}
  .filters {{ padding: 12px 14px; }}
}}
</style>
</head>
<body>
<div class="container">
  <div class="hero">
    <div class="badge">BD RESOURCE LIBRARY — 12</div>
    <h1>BD Events</h1>
    <p class="subtitle">Aggregated AEC industry events — Bay Area &amp; San Diego. Updated automatically.</p>
    <div class="meta-bar">
      <a class="subscribe" href="events.ics" download>📅 Subscribe in Outlook (.ics)</a>
      <span class="stat-pill"><strong id="visibleCount">{event_count}</strong> upcoming events</span>
      <span class="stat-pill"><strong>{source_count}</strong> sources</span>
      {new_pill_html}
      <span class="stat-pill">Updated {updated_at}</span>
    </div>
  </div>

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
      <div class="pill-row">{source_pills}
        <button class="pill" data-filter="new" data-value="true" style="--pill-color: #f59e0b;">✨ New only</button>
      </div>
    </div>
  </div>

  <div id="eventsContainer">
    {body}
  </div>

  <div id="emptyState" class="empty" style="display: none;">
    <p class="empty-title">No events match these filters.</p>
    <p class="empty-sub">Try clearing one of the active filters above.</p>
  </div>

  <footer>
    Generated by the BD Events Aggregator. The .ics feed at
    <a href="events.ics">events.ics</a> can be subscribed in Outlook, Apple Calendar, or
    Google Calendar — events update automatically every few hours.<br>
    Sources tracked: {sources_list}
  </footer>
</div>

<script>
(function() {{
  const filters = {{ region: 'all', source: 'all', new: 'all', search: '' }};

  function applyFilters() {{
    const events = document.querySelectorAll('.event');
    const search = filters.search.toLowerCase();
    let visible = 0;
    events.forEach(ev => {{
      const region = ev.dataset.region;
      const source = ev.dataset.source;
      const isNew = ev.dataset.new === 'true';
      const text = ev.innerText.toLowerCase();
      let show = true;
      if (filters.region !== 'all' && region !== filters.region) show = false;
      if (filters.source !== 'all' && source !== filters.source) show = false;
      if (filters.new !== 'all' && !isNew) show = false;
      if (search && !text.includes(search)) show = false;
      ev.style.display = show ? '' : 'none';
      if (show) visible++;
    }});
    // Hide month sections that have no visible events
    document.querySelectorAll('.month-section').forEach(sec => {{
      const anyVisible = sec.querySelector('.event:not([style*="display: none"])');
      sec.style.display = anyVisible ? '' : 'none';
    }});
    document.getElementById('visibleCount').textContent = visible;
    document.getElementById('eventsContainer').style.display = visible ? '' : 'none';
    document.getElementById('emptyState').style.display = visible ? 'none' : '';
  }}

  document.querySelectorAll('.pill[data-filter]').forEach(btn => {{
    btn.addEventListener('click', function() {{
      const dim = this.dataset.filter;
      const val = this.dataset.value;
      // For 'new' the pill is a toggle, not part of a group
      if (dim === 'new') {{
        const isOn = this.classList.toggle('active');
        filters.new = isOn ? 'true' : 'all';
      }} else {{
        // Deactivate siblings in same dimension
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
}})();
</script>
</body>
</html>
"""


def write_html(events: List[Event], path: str) -> None:
    """Override the placeholder above with full implementation including the new_pill."""
    sources_seen = sorted({e.source for e in events})
    new_count = sum(1 for e in events if getattr(e, "is_new", False))
    new_pill_html = (
        f'<span class="stat-pill new-pill"><strong>{new_count}</strong> new this week</span>'
        if new_count else ''
    )

    body = _render_body(events) if events else _empty_body()
    region_pills = _render_region_pills(events)
    source_pills = _render_source_pills(sources_seen, events)

    page = PAGE_TEMPLATE.format(
        event_count=len(events),
        source_count=len(sources_seen),
        new_pill_html=new_pill_html,
        updated_at=datetime.now(timezone.utc).strftime("%b %d, %Y at %H:%M UTC"),
        body=body,
        region_pills=region_pills,
        source_pills=source_pills,
        sources_list=", ".join(html.escape(s) for s in sources_seen),
    )
    with open(path, "w", encoding="utf-8") as f:
        f.write(page)
    print(f"  Wrote HTML page to {path}")
