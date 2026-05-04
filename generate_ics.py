"""Generate a single iCal (.ics) file from aggregated events."""
from datetime import datetime, timezone
from typing import List
from icalendar import Calendar, Event as ICalEvent

from scrapers.base import Event


def write_ics(events: List[Event], path: str) -> None:
    cal = Calendar()
    cal.add("prodid", "-//BD Events Aggregator//bd-events//EN")
    cal.add("version", "2.0")
    cal.add("x-wr-calname", "BD Events — Bay Area & San Diego")
    cal.add("x-wr-caldesc", "Aggregated AEC industry events from associations Tyler tracks for BD.")
    cal.add("x-wr-timezone", "America/Los_Angeles")
    cal.add("refresh-interval;value=duration", "PT6H")
    cal.add("x-published-ttl", "PT6H")

    for ev in events:
        ical_ev = ICalEvent()
        ical_ev.add("uid", ev.uid)
        ical_ev.add("summary", f"[{ev.source}] {ev.title}")
        ical_ev.add("dtstart", ev.start)
        if ev.end:
            ical_ev.add("dtend", ev.end)
        if ev.url:
            ical_ev.add("url", ev.url)
        if ev.location:
            ical_ev.add("location", ev.location)
        desc_parts = []
        if ev.description:
            desc_parts.append(ev.description)
        desc_parts.append(f"\nSource: {ev.source}")
        if ev.url:
            desc_parts.append(f"Link: {ev.url}")
        ical_ev.add("description", "\n".join(desc_parts))
        ical_ev.add("dtstamp", datetime.now(timezone.utc))
        cal.add_component(ical_ev)

    with open(path, "wb") as f:
        f.write(cal.to_ical())
    print(f"  Wrote {len(events)} events to {path}")
