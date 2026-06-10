"""Feed-based sources — sites with working RSS or iCal endpoints.

Each class is just configuration; the heavy lifting is in rss_adapter / ical_adapter.
"""
from .rss_adapter import RSSAdapter
from .ical_adapter import ICalAdapter


class NAIOPSVScraper(ICalAdapter):
    """NAIOP Silicon Valley — full iCal feed via The Events Calendar plugin.
    Best signal in the entire pipeline: structured data including descriptions,
    locations, and accurate datetimes."""
    name = "NAIOP Silicon Valley"
    region = "Silicon Valley"
    source_url = "https://naiopsv.org/events/"
    feed_url = "https://naiopsv.org/?post_type=tribe_events&ical=1&eventDisplay=list"


class IIDASoCalScraper(RSSAdapter):
    """IIDA SoCal — event-specific RSS feed (only events, no general news).
    Covers both the LA and San Diego chapters; no fallback region so events
    that don't name an in-market city (i.e. the LA ones) get dropped."""
    name = "IIDA SoCal"
    region = ""
    source_url = "https://iida-socal.org/san-diego/"
    feed_url = "https://iida-socal.org/events/feed/"
    require_event_keyword = False  # already an event-only feed


class DBIANationalScraper(RSSAdapter):
    """DBIA national — main site RSS. Mixed news + events; we filter for event terms."""
    name = "DBIA (national)"
    region = ""  # national feed: keep only items that classify into a kept submarket
    source_url = "https://dbia.org/conferences/"
    feed_url = "https://dbia.org/feed/"


class BisnowScraper(RSSAdapter):
    """Bisnow RSS — high-volume national real estate news/events feed.
    No fallback region: only items that name an in-market city survive,
    which doubles as the noise filter for this feed."""
    name = "Bisnow Events"
    region = ""
    source_url = "https://www.bisnow.com/events"
    feed_url = "https://www.bisnow.com/rss"


class SDBIAScraper(RSSAdapter):
    """San Diego Building Industry Association — main RSS, mixed news/events."""
    name = "San Diego BIA"
    region = "San Diego"
    source_url = "https://biasandiego.org/bia-events/"
    feed_url = "https://biasandiego.org/feed/"
