"""Source adapters — I/O only; never decide publish policy.

Concrete adapters live as modules under this package (overture, overpass,
scrape_bridge, social). There is no shared Protocol yet — each adapter
exposes its own fetch helpers.
"""
