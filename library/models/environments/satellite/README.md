# Satellite communications dish

Ground prop, authored in metres: aperture **−Y**, up **+Z**,
foundation centre at floor **z=0**. Nothing is copied into the game. Tensor is
the 1.753 m scale model; `scale_preview.py` loads his actual authored body
and head without rescaling them.

The spun reflector has a 2.0 m aperture and 0.30 m depth, on a 2.42 × 1.44 m
foundation. Overall dimensions are approximately 2.633 × 1.581 × 3.020 m,
including the service drive and receiver. The perimeter ring is 2.05 m across.
The fixed frame and moving reflector are separate render meshes, each capped
at 5,000 triangles. Native Tensor finishes are
off-white and grey paint, matte black, stainless steel, and cyan service lamps.
The conducting annulus is a material region of the continuous reflector skin,
without decorative overlapping discs.

## Construction

- Closed parabolic reflector, 22 mm double skin, rolled rim. Feed phase centre
  at its analytic focus, 0.833 m from the vertex (y = −0.713333 m). Three bipods
  terminate on surface-fitted bolted shoes and separate receiver sockets.
  Shouldered, blind-bored sleeves receive both ends of every tube; no spar
  simply penetrates a shell or receiver.
  RF/power routes internally through the hollow support tubes to the backend.
- Eight rear ribs transfer load to a lofted hub and two trunnion beams. The
  120 mm retained shafts run in coaxial bored bearings, with radial clearance
  throughout the angular range, thrust washers and retaining caps. A sealed
  reduction drive and rotary coax/data feedthrough avoid rigid wires across
  the hinge.
- Planar foundation deck, bolted tower flanges and tapered bearing columns.
  Fore/aft knee braces use double-ear clevises, bored link eyes and retained
  pins at both ends. Diagonal members seat in shouldered sockets on bolted
  tower flanges and meet a central gusset. The drive seats on a fixed bearing
  flange while the rotating shaft has separate axial retainers.
  Unions describe continuous castings or
  weldments. Separate components meet at exact seats. A control cabinet has
  pocketed cover/lamp inserts; its loom has connector glands and three saddles.

`Root → Elevation` has rigid skinning, one influence per vertex. The hinge
axis is X through `(0, 0.26, 2.0)`, limits −35°..+10°. Negative angles tip the
aperture upward. Root stays fixed; there are no bone-scale or root-motion keys.
This installation has fixed azimuth.

| Clip | Duration | Loop | Motion |
| --- | --- | --- | --- |
| `track` | 6 s | Yes | Smooth 0° → −16° → 0° scan |
| `service_raise` | 4 s | No | Ease from front-facing to −35° |
| `service_return` | 4 s | No | Ease back to front-facing |

The generator checks every animation frame and a one-degree limit sweep,
exact solid intersections, part connectivity, coplanar overlaps, and the render
budget. It culls unseen faces and prepares per-material 2048 px UV atlases.
FBX sampling retains every key. `validate.py` independently reimports GLB/FBX
and collision companions, checking scale, bounds, rigid weights, UVs, materials,
the two-bone hierarchy and every frame of all three clips.

The collision companion is a conservative set of rigid convex pieces within
500 triangles. It fills small fasteners, cable apertures and side brace bays,
while preserving the central frame passage and reflector concavity. Sampled
surface coverage is checked independently against both render assemblies.

Validated delivery: 4,410 frame triangles, 3,951 reflector triangles, 211
connected manufactured parts, and 469 checked motion states. The collider
has 44 convex pieces and 496 triangles. Both GLB and FBX round trips verify
all frames of the three clips.

## Regenerate

From `library/`, using Blender 5.2:

```powershell
$blender = (Get-Command blender -ErrorAction Stop).Source
& $blender --background --factory-startup --python models/environments/satellite/model.py
& $blender --background --factory-startup --python models/nvidia_render.py -- models/environments/satellite/preview.py
& $blender --background --factory-startup --python models/nvidia_render.py -- models/environments/satellite/scale_preview.py
& $blender --background --factory-startup --python models/nvidia_render.py -- models/environments/satellite/inspection.py
& $blender --background --factory-startup --python models/environments/satellite/collision.py
& $blender --background --factory-startup --python models/environments/satellite/validate.py
& $blender --background --factory-startup --python models/nvidia_render.py -- models/environments/satellite/animate.py
```

Generated models, rig metadata, UV guides, studio/pose/scale previews, colliders,
reports and `satellite_showcase.mp4` remain beside the generators, ignored by
Git. The showcase plays the authored clips sequentially in the other props'
studio. Engine verification belongs to a future user-requested game handoff.
