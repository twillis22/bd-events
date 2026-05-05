"""Generate the bookmarkable HTML page from aggregated events.

Styled to match Level 10 Construction's brand:
  - Warm charcoal bg (#262626) instead of cool blue-black
  - Sans-serif throughout (Inter via Google Fonts)
  - Brand orange accent (#ff671f) replacing amber
  - ALL CAPS section labels with orange underline accent
  - Card bg uses warmer #3d3935

Features (unchanged from prior v3):
  - Filter pills (region, source, "new only" toggle)
  - Search input
  - Live filtering with no page reload (vanilla JS)
  - "New" pulse badge on events first seen in last 7 days
"""
from datetime import datetime, timezone
from typing import List
import html

from scrapers.base import Event


# Level 10 brand palette
L10_BG          = "#262626"   # body background
L10_BG_CARD     = "#3d3935"   # secondary surfaces (filter bar, event cards)
L10_BG_DEEP     = "#1c1c1c"   # input fields, deeper layer
L10_TEXT        = "#f6f6f6"   # body text
L10_TEXT_MUTED  = "#9a9a9a"   # secondary text
L10_TEXT_DIM    = "#6b6b6b"   # tertiary, separators
L10_BORDER      = "#4a4744"   # subtle borders
L10_ORANGE      = "#ff671f"   # brand accent
L10_ORANGE_DEEP = "#934727"   # deeper brick orange (band)

# Region tag colors — keep distinct but tone down to fit the warm palette
REGION_COLORS = {
    "NorCal": "#5a8dd6",   # softer blue
    "SoCal":  "#d97a9a",   # softer pink
    "Other":  "#7fb59b",   # muted green
}


def _render_region_pills(events: List[Event]) -> str:
    counts = {}
    for e in events:
        counts[e.source_region or "Other"] = counts.get(e.source_region or "Other", 0) + 1
    parts = ['<button class="pill active" data-filter="region" data-value="all">ALL REGIONS</button>']
    for region in ["NorCal", "SoCal", "Other"]:
        if region in counts:
            color = REGION_COLORS.get(region, L10_TEXT_MUTED)
            parts.append(
                f'<button class="pill" data-filter="region" data-value="{region}" '
                f'style="--pill-color: {color};">{region.upper()} '
                f'<span class="count">{counts[region]}</span></button>'
            )
    return "".join(parts)


def _render_source_pills(sources: list, events: List[Event]) -> str:
    counts = {}
    for e in events:
        counts[e.source] = counts.get(e.source, 0) + 1
    parts = ['<button class="pill active" data-filter="source" data-value="all">ALL SOURCES</button>']
    for source in sorted(sources, key=lambda s: -counts.get(s, 0)):
        c = counts.get(source, 0)
        parts.append(
            f'<button class="pill" data-filter="source" data-value="{html.escape(source)}">'
            f'{html.escape(source).upper()} <span class="count">{c}</span></button>'
        )
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
                f'<div class="month-section" data-month="{ym}">'
                f'<h2 class="month-header">{html.escape(current_key.upper())}</h2>'
                + "\n".join(current_buf)
                + "</div>"
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


def _empty_body() -> str:
    return ('<div class="empty"><p class="empty-title">No upcoming events found.</p>'
            '<p class="empty-sub">The aggregator may be having trouble — '
            'check back tomorrow.</p></div>')


def _render_event(ev: Event) -> str:
    day = ev.start.strftime("%-d")
    dow = ev.start.strftime("%a").upper()
    region = ev.source_region or "Other"
    region_color = REGION_COLORS.get(region, L10_TEXT_MUTED)
    is_new = getattr(ev, "is_new", False)
    new_badge = '<span class="new-badge">NEW</span>' if is_new else ''

    time_part = ""
    if ev.start.hour != 0 or ev.start.minute != 0:
        local_time = ev.start.strftime("%-I:%M %p")
        time_part = f'<span class="time-badge">{local_time}</span>'

    location_part = ""
    if ev.location:
        loc_short = html.escape(ev.location[:80])
        location_part = f'<span class="location">{loc_short}</span>'

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
      <span class="source-tag" style="background: {region_color}1f; color: {region_color}; border-color: {region_color}55;">{source_attr}</span>
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
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');

* {{ margin: 0; padding: 0; box-sizing: border-box; }}
html {{ scroll-behavior: smooth; }}
body {{
  font-family: 'Inter', -apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, Arial, sans-serif;
  background: {bg};
  color: {text};
  line-height: 1.55;
  -webkit-font-smoothing: antialiased;
}}
.container {{ max-width: 1080px; margin: 0 auto; padding: 56px 28px 96px; }}

/* Hero */
.hero {{ padding-bottom: 36px; margin-bottom: 36px;
  border-bottom: 1px solid {border}; }}
.label {{ font-size: 12px; font-weight: 600; letter-spacing: 2.5px;
  text-transform: uppercase; color: {orange}; margin-bottom: 14px;
  display: inline-block; padding-bottom: 6px; border-bottom: 2px solid {orange}; }}
h1 {{ font-size: 56px; font-weight: 800; color: {text}; line-height: 1.05;
  letter-spacing: -0.02em; margin-bottom: 14px; text-transform: uppercase; }}
h1 em {{ font-style: normal; color: {orange}; }}
.subtitle {{ color: {text_muted}; font-size: 16px; max-width: 620px; margin-bottom: 28px; }}

.meta-bar {{ display: flex; flex-wrap: wrap; gap: 10px; align-items: center; margin-top: 8px; }}
.subscribe {{ display: inline-flex; align-items: center; gap: 8px; background: {orange};
  color: {bg}; padding: 12px 22px; border-radius: 4px; text-decoration: none;
  font-weight: 700; font-size: 13px; letter-spacing: 1.2px; text-transform: uppercase;
  transition: background 0.15s; }}
.subscribe:hover {{ background: #e85a14; }}
.stat-pill {{ background: transparent; border: 1px solid {border}; border-radius: 4px;
  padding: 10px 16px; font-size: 12px; color: {text_muted}; letter-spacing: 0.5px;
  text-transform: uppercase; font-weight: 500; }}
.stat-pill strong {{ color: {text}; font-weight: 700; margin-right: 4px; }}
.stat-pill.new-pill {{ background: {orange_deep}33; border-color: {orange}66; color: {orange}; }}
.stat-pill.new-pill strong {{ color: {orange}; }}

/* Filter bar */
.filters {{ background: {bg_card}; border-radius: 6px; padding: 24px 26px;
  margin-bottom: 40px; border-left: 3px solid {orange}; }}
.filter-group {{ margin-bottom: 18px; }}
.filter-group:last-child {{ margin-bottom: 0; }}
.filter-label {{ font-size: 11px; font-weight: 700; letter-spacing: 2px;
  text-transform: uppercase; color: {orange}; margin-bottom: 10px; display: block; }}
.pill-row {{ display: flex; flex-wrap: wrap; gap: 6px; }}
.pill {{ background: transparent; border: 1px solid {border}; color: {text};
  padding: 7px 14px; border-radius: 3px; font-family: inherit; font-size: 11px;
  font-weight: 600; cursor: pointer; transition: all 0.12s; letter-spacing: 0.6px;
  text-transform: uppercase;
  display: inline-flex; align-items: center; gap: 6px; }}
.pill:hover {{ border-color: {orange}; color: {orange}; }}
.pill.active {{ background: {orange}; color: {bg}; border-color: {orange}; }}
.pill[data-filter="region"].active {{
  background: var(--pill-color, {orange});
  border-color: var(--pill-color, {orange});
  color: {bg}; }}
.pill .count {{ background: rgba(255,255,255,0.12); padding: 1px 7px; border-radius: 8px;
  font-size: 10px; font-weight: 700; }}
.pill.active .count {{ background: rgba(0,0,0,0.18); color: inherit; }}

/* Search */
.search-box {{ width: 100%; background: {bg_deep}; border: 1px solid {border}; color: {text};
  padding: 12px 16px; border-radius: 4px; font-family: inherit; font-size: 14px;
  transition: border-color 0.15s; }}
.search-box:focus {{ outline: none; border-color: {orange}; }}
.search-box::placeholder {{ color: {text_dim}; }}

/* Month sections */
.month-section {{ margin-bottom: 52px; }}
.month-header {{ font-size: 13px; font-weight: 700; color: {orange};
  letter-spacing: 3px; text-transform: uppercase; margin-bottom: 18px;
  padding-bottom: 10px; border-bottom: 1px solid {border}; }}

/* Event cards */
.event {{ background: {bg_card}; border-radius: 4px; padding: 22px 26px;
  margin-bottom: 8px; display: grid;
  grid-template-columns: 70px 1fr; gap: 22px; align-items: start;
  transition: transform 0.12s, box-shadow 0.12s;
  border-left: 3px solid transparent; }}
.event:hover {{ transform: translateX(2px); box-shadow: -2px 0 0 {orange}; border-left-color: {orange}; }}
.event.is-new {{ border-left-color: {orange}; }}

.event-date {{ text-align: center; padding-top: 2px; line-height: 1; }}
.event-date .day {{ font-size: 38px; font-weight: 800; color: {text};
  line-height: 1; letter-spacing: -0.02em; }}
.event-date .dow {{ font-size: 11px; color: {orange}; text-transform: uppercase;
  letter-spacing: 1.5px; margin-top: 6px; font-weight: 700; }}

.event-body a.event-title {{ color: {text}; font-size: 16px; font-weight: 600;
  text-decoration: none; line-height: 1.35; display: inline; }}
.event-body a.event-title:hover {{ color: {orange}; }}
.new-badge {{ display: inline-block; background: {orange}; color: {bg};
  font-size: 10px; font-weight: 800; letter-spacing: 1.2px; padding: 2px 7px;
  border-radius: 2px; margin-left: 10px; vertical-align: 2px;
  animation: pulse 2.4s ease-in-out infinite; }}
@keyframes pulse {{ 0%, 100% {{ opacity: 1; }} 50% {{ opacity: 0.55; }} }}

.event-meta {{ display: flex; flex-wrap: wrap; gap: 10px; margin-top: 10px;
  font-size: 12px; color: {text_muted}; align-items: center; }}
.source-tag {{ font-weight: 600; font-size: 10px; padding: 3px 9px; border-radius: 2px;
  letter-spacing: 0.5px; text-transform: uppercase; border: 1px solid; }}
.location {{ color: {text_muted}; }}
.location::before {{ content: "·"; margin-right: 8px; color: {text_dim}; }}
.time-badge {{ color: {text}; font-weight: 600; }}
.time-badge::before {{ content: "·"; margin-right: 8px; color: {text_dim}; font-weight: 400;}}

/* Empty state */
.empty {{ text-align: center; padding: 72px 24px; background: {bg_card};
  border: 1px dashed {border}; border-radius: 4px; margin-top: 20px; }}
.empty-title {{ font-size: 16px; color: {text}; margin-bottom: 8px;
  text-transform: uppercase; letter-spacing: 1px; font-weight: 700; }}
.empty-sub {{ font-size: 14px; color: {text_muted}; }}

footer {{ margin-top: 72px; padding-top: 32px; border-top: 1px solid {border};
  color: {text_muted}; font-size: 12px; line-height: 1.7; }}
footer a {{ color: {orange}; text-decoration: none; }}
footer a:hover {{ text-decoration: underline; }}
.footer-label {{ display: block; font-size: 11px; letter-spacing: 2px; text-transform: uppercase;
  color: {orange}; margin-bottom: 10px; font-weight: 700; }}

@media (max-width: 720px) {{
  .container {{ padding: 40px 18px 64px; }}
  h1 {{ font-size: 38px; }}
  .event {{ grid-template-columns: 56px 1fr; gap: 16px; padding: 18px 18px; }}
  .event-date .day {{ font-size: 30px; }}
  .filters {{ padding: 18px 18px; }}
  .meta-bar {{ gap: 8px; }}
  .stat-pill, .subscribe {{ font-size: 11px; padding: 9px 14px; }}
}}
</style>
</head>
<body>
<div class="container">
  <div class="hero">
    <span class="label">BD Resource Library — 12</span>
    <h1>BD <em>Events</em></h1>
    <p class="subtitle">Aggregated AEC industry events across the Bay Area and San Diego. Updated automatically.</p>
    <div class="meta-bar">
      <a class="subscribe" href="events.ics" download>📅 Subscribe in Outlook</a>
      <span class="stat-pill"><strong id="visibleCount">{event_count}</strong>upcoming</span>
      <span class="stat-pill"><strong>{source_count}</strong>sources</span>
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
        <button class="pill" data-filter="new" data-value="true" style="--pill-color: {orange};">✦ NEW ONLY</button>
      </div>
    </div>
  </div>

  <div id="eventsContainer">
    {body}
  </div>

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
  const filters = {{ region: 'all', source: 'all', new: 'all', search: '' }};

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
      if (show) visible++;
    }});
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
}})();
</script>
</body>
</html>
"""


def write_html(events: List[Event], path: str) -> None:
    sources_seen = sorted({e.source for e in events})
    new_count = sum(1 for e in events if getattr(e, "is_new", False))
    new_pill_html = (
        f'<span class="stat-pill new-pill"><strong>{new_count}</strong>new this week</span>'
        if new_count else ''
    )

    body = _render_body(events) if events else _empty_body()
    region_pills = _render_region_pills(events)
    source_pills = _render_source_pills(sources_seen, events)

    page = PAGE_TEMPLATE.format(
        bg=L10_BG, bg_card=L10_BG_CARD, bg_deep=L10_BG_DEEP,
        text=L10_TEXT, text_muted=L10_TEXT_MUTED, text_dim=L10_TEXT_DIM,
        border=L10_BORDER, orange=L10_ORANGE, orange_deep=L10_ORANGE_DEEP,
        event_count=len(events),
        source_count=len(sources_seen),
        new_pill_html=new_pill_html,
        updated_at=datetime.now(timezone.utc).strftime("%b %-d, %Y at %H:%M UTC"),
        body=body,
        region_pills=region_pills,
        source_pills=source_pills,
        sources_list=", ".join(html.escape(s) for s in sources_seen),
    )
    with open(path, "w", encoding="utf-8") as f:
        f.write(page)
    print(f"  Wrote HTML page to {path}")
