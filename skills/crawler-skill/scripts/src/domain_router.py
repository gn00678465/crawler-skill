"""
domain_router.py – URL-to-tier routing based on hostname rules.

Determines which scraper tiers to use for a given URL by consulting a table
of domain-specific skip rules.  Any tier listed in a domain's skip set is
removed from the default ordered chain before returning.
"""

from urllib.parse import urlparse

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

DEFAULT_TIERS: tuple[str, ...] = ("firecrawl", "jina", "scrapling")

# Maps a canonical hostname to the set of tier names to skip.
# Sub-domain matching: a hostname H matches rule key K when
#   H == K  OR  H ends with "." + K
DOMAIN_RULES: dict[str, frozenset[str]] = {
    "medium.com":       frozenset({"firecrawl"}),
    "mp.weixin.qq.com": frozenset({"firecrawl", "jina"}),
}


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def get_tiers(url: str) -> tuple[str, ...]:
    """Return the ordered tuple of tier names to try for *url*.

    Tiers that are listed in ``DOMAIN_RULES`` for the URL's hostname are
    excluded.  The relative order of the remaining tiers is preserved.

    Parameters
    ----------
    url:
        A fully-qualified URL string (e.g. ``"https://medium.com/article"``).

    Returns
    -------
    tuple[str, ...]
        A non-empty tuple of tier names drawn from ``DEFAULT_TIERS``.
    """
    hostname = urlparse(url).hostname or ""
    skip: frozenset[str] = _match_rules(hostname)
    return tuple(tier for tier in DEFAULT_TIERS if tier not in skip)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _match_rules(hostname: str) -> frozenset[str]:
    """Return the skip set for *hostname*, or an empty frozenset."""
    for rule_host, skip_set in DOMAIN_RULES.items():
        if hostname == rule_host or hostname.endswith("." + rule_host):
            return skip_set
    return frozenset()
