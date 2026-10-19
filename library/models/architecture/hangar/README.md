# Hangar

The [shared architecture dimensions contract](../README.md#door-and-interior-dimensions)
owns current door and inside-height limits. Delivered dimensions and mechanical
travel are recorded in the regenerated `_rig.json`. Run `../verify_dimensions.py` after rebuilding.

Walkable industrial architecture. Metres, front −Y, up +Z,
origin at the centre of the ground footprint. Do not copy into the game yet.

## Construction

The asset has an extruded octagonal hangar, four heavy wraparound
ribs, stepped door surround, recessed divided armour, terminated external utility
lines, and an illuminated octagonal entry. The three-quarter studio camera is
slightly elevated, with telephoto compression and broad soft light. Materials use:
off-white `M_Primary`, grey `M_Secondary`, matte black `M_Frame`, stainless
`M_Joint`, cyan `M_Emissive`. The finish is neutral, without team colours.

The building has an integral grey floor, 9 m wide × 10.18 m deep, with
no surrounding metallic platform. Its local 2.22 m wide entrance ramp rises
0.15 m over 0.42 m (19.65°). The pressure shell is 9 × 10 m; ribs reach
9.32 m width. Building height is approximately 3.395 m. The pressure opening is 2.0 m wide
with 2.1 m central headroom. The closed room has 78.96304 m² of clear floor:
an 8.20 × 9.56 m chamber and a 0.57104 m² entrance recess.
The moving building remains within the established 10 × 11 m envelope.
Optional perimeter dressing is separate from that envelope.
All movement must remain within the ground footprint. Tensor is 1.753 m tall;
the geometric entry audit uses his actual mesh and locomotion poses as well as
the standing game capsule. No character is included in exports.

**Approved budget:** 10,000 rendered triangles total and 5,000 per mesh.
The current build has 9,965 triangles across five meshes, including 192
triangles in optional `SK_ArchitectureRegolith` / `M_Regolith`.
GLB primary, FBX fallback, one rigid
influence per vertex, unique per-material 2048 px UV painting atlases. Source
generators use the project's headless Blender 5.2 workflow. The visible shell
is lofted and machined, with an actual pressure-room void and entry cutout.
Rib sections, inset panels and fittings have shared seating geometry; boolean
unions form structural shells and lugs rather than intersecting exported solids.

## Mechanics

Paired doors open inward 105° on vertical axes. Three interleaved, bored hinge
sets on each door have retained through pins. A sealed coaxial reduction drive
bolts to each stationary jamb and couples directly to its hinge shaft. Each door
has an upper captive shoot bolt: it retracts 120 mm before the leaf can move.
Paired `open` / `close` and independent `open_left` / `close_left`,
`open_right` / `close_right` actions are 96 frames at 30 fps, in place,
non-looping. Independent clips contain only their own leaf and bolt tracks.
There is no gratuitous continuous movement on the stationary building.

Utilities terminate in bolted service boxes with socket glands and bored saddle
clamps. Flush cyan inserts occupy real machined recesses. An interior overhead
pair of `BattenLightMountFront` / `BattenLightMountRear` gizmos and four
`SconceLightMount*` wall gizmos permits separate fixtures to be installed later.
Each point is ray-seated on the actual surface with its local +Z directed into
the room, and is bone-parented to Root. No integral ceiling/wall light fixtures
are included. Inspection-only studio lamps are never saved into the asset.

## Finish and inset fit

Broad vertical wall surfaces are off-white `M_Primary`. The roof, its chamfers,
structural ribs and window/door frames are grey `M_Secondary`. Twelve side-wall
and roof-chamfer insets are true windows through the pressure shell, using
black `M_Glass` with alpha 0.10, metalness 0, roughness 0.15 and IOR 1.46.
Their edges seat directly in continuous retaining rims. Sconce gizmos occupy
opaque wall lands between window bays.

The doorway's outer face is a constant 0.44 m parallel offset from the opening;
its root flange is a 0.59 m offset. Both terminate at the floor plane. The cyan
guide is a consistent 0.024 m strip. Numeric edge-distance assertions verify
these offsets. Door pockets and rear-cover pockets follow the eight-edge plate
outline with constant 5 mm and 2 mm base clearance respectively. Door plate
bevels use parallel offsets too, so their visible corner gaps stay consistent.

## Regeneration

Run from `library/` using the Blender executable in `AGENTS.md`, in this order:
`model.py`, `preview.py`, `inspection.py`, `collision.py`, `validate.py`,
`scale_check.py`, and `animate.py` in this folder. Geometry, solid intersections,
connectivity, every action frame, hinge sweeps, coplanar faces, ground envelope,
UVs, and both export round trips are checked. Collision uses convex wall/roof
slabs and separately animated doors, preserving the room and entry void.
Generated blends, runtime exports, reports, images and video remain ignored.
The default visibility pass removes buried mating surfaces and the floor's
ground-facing underside while retaining the accessible room. The optional
`--ray-cull` pass is available but was not completed for this candidate.

Local skills: blender-director, hard-surface, environment-artist, materials,
rigging, animation, rendering, collision-proxy, godot-export, qa-review.

The separate `SK_ArchitectureRegolith` mesh can be hidden or removed without
affecting the building. It is Root-weighted and excluded from blocking collision.
See the shared [architecture contract](../README.md).
