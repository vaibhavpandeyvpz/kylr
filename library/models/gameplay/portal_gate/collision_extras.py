"""The portal gate's own colliders, for collision.py (which imports this module when it sits next to it).

    SK_PortalGateFieldTrigger an area (not a solid) over the field's rectangle, FIELD_DEPTH through: while the portal
                              is active, a player entering it is teleported (to the other portal's SpawnFront or
                              SpawnBack, by the side he came from: his position against y = 0, the field's plane).
                              Deep enough that a sprinting player can't step over it between two physics frames
The frame's own collider (convex pieces) leaves the passage open.
"""

engine = None  # (collision.py, set on import)

FIELD_DEPTH = 0.5  # m: 25 cm each side of the field (a player at 15 m/s moves 25 cm in one 60 Hz frame)

CUSTOM = {"SK_PortalGateField": lambda rig, mesh: engine.slab(rig, mesh, "SK_PortalGateFieldTrigger", FIELD_DEPTH)}
