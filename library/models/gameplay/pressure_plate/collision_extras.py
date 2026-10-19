"""The pressure plate's own collider, for collision.py (which imports this module when it sits next to it).

    SK_PressurePlateTrigger   an area (not a solid) over the plate, on its bone so it sinks with it: play press when
                              the first player (or anything heavy) enters it and release when the last one leaves
"""

engine = None  # (collision.py, set on import)

EXTRAS = [lambda rig: engine.trigger_on_bone(rig, "Plate", "SK_PressurePlateTrigger", height=0.10)]

# The tray below the plate's lowest travel (5 cm down) is sunk in the level's cut-out, where nobody reaches: no
# collider there, so the tray's is its rim and its walls round the plate (-7 cm left fewer pieces than a cut just
# under the pressed plate's top).
CLIP_BELOW = -0.07
