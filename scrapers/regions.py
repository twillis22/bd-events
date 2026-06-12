"""Per-event geographic classification into submarkets.

Replaces the old per-source NorCal/SoCal/Other buckets. Every event runs through
`classify()` in the aggregator, which returns one of the KEPT_BUCKETS or None.
None means "drop this event" — that is how Los Angeles / Orange County / out-of-state
events get excluded even when their source feed is otherwise in-market.

Matching order (first hit wins):
  1. location text against submarket city tables, then against drop markers
  2. title text the same way
  3. online/virtual markers anywhere
  4. generic "Bay Area"-ish markers anywhere
  5. the source's fallback default (if it names a kept bucket), else drop
Location is checked before title because it is the more reliable signal.
"""
import re
from typing import Optional

# Filter-pill buckets, in display order.
KEPT_BUCKETS = (
    "San Francisco",
    "Silicon Valley",
    "East Bay",
    "Sacramento",
    "San Diego",
    "Bay Area",
    "Online",
)

# City / keyword tables per submarket. Word-boundary, case-insensitive.
# Listed in match-priority order: specific submarkets before catch-alls.
_SUBMARKET_CITIES = {
    "San Francisco": (
        "San Francisco", "SF", "SOMA", "Presidio", "Embarcadero", "Fisherman's Wharf",
    ),
    "Silicon Valley": (
        "San Jose", "Santa Clara", "Mountain View", "Palo Alto", "Sunnyvale",
        "Cupertino", "Menlo Park", "Redwood City", "San Mateo", "Fremont",
        "Milpitas", "Los Gatos", "Los Altos", "Campbell", "Saratoga",
        "Foster City", "Burlingame", "Stanford", "Silicon Valley",
    ),
    "East Bay": (
        "Oakland", "Berkeley", "Walnut Creek", "Emeryville", "Pleasanton",
        "Dublin", "San Ramon", "Concord", "Livermore", "Hayward", "Richmond",
        "Alameda", "San Leandro", "Lafayette", "Orinda", "Danville", "East Bay",
    ),
    "Sacramento": (
        "Sacramento", "Roseville", "Folsom", "Davis", "Elk Grove",
        "Rancho Cordova", "Rocklin", "Citrus Heights", "Auburn",
    ),
    "San Diego": (
        "San Diego", "La Jolla", "Carlsbad", "Chula Vista", "Oceanside",
        "Escondido", "Del Mar", "Coronado", "Encinitas", "Solana Beach",
        "National City", "Poway", "Vista", "San Marcos", "Mission Valley",
    ),
}

# Bay Area events with no identifiable submarket city (North Bay, generic
# "Bay Area" venues, etc.) land in the Bay Area catch-all instead of dropping.
_BAY_GENERIC = (
    "Bay Area", "Northern California", "NorCal", "Marin", "Sausalito",
    "San Rafael", "Novato", "Mill Valley", "Napa", "Sonoma", "Santa Rosa",
    "Petaluma", "Vallejo", "Fairfield", "Half Moon Bay",
)

_ONLINE_MARKERS = (
    "Online", "Virtual", "Webinar", "Zoom", "Livestream", "Live stream",
    "Microsoft Teams", "GoToWebinar", "WebEx",
)

# Explicit out-of-market: LA / Orange County / Inland Empire / SoCal-not-SD,
# plus major non-CA cities that show up in national feeds.
_DROP_PLACES = (
    "Los Angeles", "L.A.", "Hollywood", "Santa Monica", "Pasadena", "Burbank",
    "Culver City", "Long Beach", "Beverly Hills", "Glendale", "Marina del Rey",
    "El Segundo", "Inglewood", "Woodland Hills", "Universal City", "Downey",
    "Torrance", "Pomona",
    "Orange County", "Anaheim", "Irvine", "Costa Mesa", "Newport Beach",
    "Santa Ana", "Huntington Beach", "Fullerton", "Garden Grove",
    "Riverside", "San Bernardino", "Inland Empire", "Palm Springs",
    "Palm Desert", "Temecula", "Ontario",
    "Bakersfield", "Fresno", "Santa Barbara", "Ventura", "Oxnard",
    # Central Coast / Central Valley — out of market. "Central Valley Chapter"
    # stays specific (CSHE's Fresno-area chapter) so a future Sacramento-based
    # "AIA Central Valley" source isn't collateral damage.
    "Central Coast", "Central Valley Chapter", "Monterey", "Salinas",
    "San Luis Obispo", "Modesto", "Stockton",
    "New York", "NYC", "Brooklyn", "Manhattan", "Chicago", "Boston", "Atlanta",
    "Miami", "Dallas", "Houston", "Austin", "Denver", "Seattle", "Portland",
    "Phoenix", "Scottsdale", "Las Vegas", "Nashville", "Charlotte",
    "Philadelphia", "Washington, D.C.", "Washington DC", "Minneapolis",
    "Detroit", "Salt Lake City", "Toronto", "Vancouver", "Mexico City",
)

# ", XX" state suffixes for every US state except California (catches
# addresses like "Phoenix, AZ 85004" in national feeds).
_NON_CA_STATES = (
    "AL AK AZ AR CO CT DE FL GA HI ID IL IN IA KS KY LA MA MD ME MI MN MO MS "
    "MT NC ND NE NH NJ NM NV NY OH OK OR PA RI SC SD TN TX UT VA VT WA WI WV WY DC"
).split()


def _word_re(terms) -> re.Pattern:
    return re.compile(
        r"\b(" + "|".join(re.escape(t) for t in terms) + r")\b", re.IGNORECASE
    )


_SUBMARKET_RES = {bucket: _word_re(cities) for bucket, cities in _SUBMARKET_CITIES.items()}
_BAY_GENERIC_RE = _word_re(_BAY_GENERIC)
_ONLINE_RE = _word_re(_ONLINE_MARKERS)
_DROP_RE = _word_re(_DROP_PLACES)
# State abbreviations are case-sensitive and must follow a comma ("Reno, NV").
_NON_CA_STATE_RE = re.compile(r",\s*(" + "|".join(_NON_CA_STATES) + r")\b")


def _match_submarket(text: str) -> Optional[str]:
    for bucket, pattern in _SUBMARKET_RES.items():
        if pattern.search(text):
            return bucket
    return None


def _is_out_of_market(text: str) -> bool:
    return bool(_DROP_RE.search(text) or _NON_CA_STATE_RE.search(text))


def classify(location: str, title: str = "", source_default: str = "") -> Optional[str]:
    """Map an event to a submarket bucket, or None to drop it entirely."""
    for text in (location, title):
        if not text:
            continue
        bucket = _match_submarket(text)
        if bucket:
            return bucket
        if _is_out_of_market(text):
            return None

    combined = f"{location} {title}".strip()
    if combined:
        if _ONLINE_RE.search(combined):
            return "Online"
        if _BAY_GENERIC_RE.search(combined):
            return "Bay Area"

    if source_default in KEPT_BUCKETS:
        return source_default
    return None
