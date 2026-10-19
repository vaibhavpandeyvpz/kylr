"""The jumbotron's own colliders, for collision.py (which imports this module when it sits next to it).

The displays (SK_JumbotronScreen) and the marquee bands (SK_JumbotronMarquee) get no collider: they lie flush in
the body's recesses and bands, so the body's convex pieces already close over them.
"""

engine = None  # (collision.py, set on import)

CUSTOM = {"SK_JumbotronScreen": lambda rig, mesh: [], "SK_JumbotronMarquee": lambda rig, mesh: []}
