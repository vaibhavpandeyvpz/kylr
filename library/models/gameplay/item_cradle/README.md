# Item cradle

**Triangle budget exception:** the user explicitly approved up to 5,500
render triangles for this functional prop. This asset's build and round-trip
validator enforce that ceiling; other props retain the default 5,000 limit.

Freestanding sci-fi payload cradle, facing Blender -Y, +Z up.
The floor origin is at its centre. The complete outer footprint is exactly
1 x 1 m: the cardinal casting ribs reach +/-0.5 m on X and Y. All clamp
motion stays inside that tile. The circular deck is 0.926 m across;
closed hook tips are 0.500 m high, against Tensor's 1.753 m stature.

Four lofted hooked shells open outward 25 degrees on tangential axes. Each
21 mm shaft runs through bored pedestal clevises into coaxial geared motor
cases, with retained end caps. Arm cooling slots and tip status lenses are recessed; the service
wells contain attached terminals and gland-ended wiring. The perimeter ribs are boolean-fused into the floor-contacting casting. Deck retention bolts and geared-drive cover screws sit on flat seats. Cyan strips denote
status, in Tensor's off-white/grey paint, black frames and stainless hardware.
The central seat supports a payload; no payload mesh is exported.

`ItemMount` is an invisible, fixed placement node on `ItemSocket`, at
(0, 0, 0.400000) m in Blender. Follow the item table's gizmo convention: local
Y forward, Z up, converted to Godot -Z forward and Y up. Place a payload by
its bottom origin. The socket is exactly 10 cm below the 0.50 m closed hook top. Preview renders show labeled XYZ axes at this authored socket.

The GLB and FBX contain `open` (1.2 s) and `close` (1.4 s). Rest is closed.
There is no rotation/spin clip. The clamps may also be driven independently
within their 0..25 degree limits.

The collision companion contains `SK_ItemCradleBaseCol` and four independent
`SK_ItemCradleClaw<Tag>Col` objects (FrontLeft, RearLeft, RearRight, FrontRight).
Each claw retains its native Clamp<Tag> bone and exact generated convex pieces;
the total remains 438 triangles. Empty runtime cradles disable the claw bodies,
keeping the plinth solid; occupied cradles restore them after the closing clip.
After collecting a weapon, its hidden payload bodies also cease colliding.
These switches are per instance and shared by local and online pickup state.

collision.py supports `-- --exports-only` or `-- --previews-only` to retry
delivery from an already regenerated and checked native collision file.

Run from `library/` using the Blender 5.2 executable specified in AGENTS.md:

1. `model.py` — geometry, rigid rig, motion and assembly checks, UV atlases,
   native scene, GLB/FBX and rig metadata.
2. `preview.py` — standard studio and open/halfway pose images.
3. `collision.py` — convex companion and collider previews.
4. `validate.py` — fresh GLB/FBX round trips and pose seam checks.
5. `animate.py` — an open/close studio showcase.
