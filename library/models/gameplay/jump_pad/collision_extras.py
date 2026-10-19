"""The jump pad's own collider, for collision.py (which imports this module when it sits next to it).

    SK_JumpPadTrigger    an area (not a solid) over the plate, on its bone so it rises with it: play launch when
                              a player enters it (and give the impulse on the up-stroke; re-trigger once it is down)
"""

engine = None  # (collision.py, set on import)

EXTRAS = [lambda rig: engine.trigger_on_bone(rig, "Plate", "SK_JumpPadTrigger", height=0.10)]
