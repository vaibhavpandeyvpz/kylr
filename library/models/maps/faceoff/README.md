# Faceoff

Authored from Figma file `0pxQrXAGeHplJ0ANVYwD8e`, frame `143:891` on page
`143:890`. Both flag placements use the actual added node IDs and transforms.

Native architecture, fixtures, weapons, ammo, lights and lunar scenery are
separate assets imported at named map gizmos with identity local transforms.
Each ammo pack has its own gizmo; pair origins are 20 cm apart. Held payloads
attach to the holder/table's live rotating-bone socket.
All eight floor spawn-pit gizmos face the front of their Bastion or Laboratory
host. Their PlayerMount axis is opposite to the stasis chamber's axis; the two
upper-floor stasis chambers retain their door-facing orientation. Spawn rotations
do not change the positions or the symmetric square recesses.
Both Bastion and Laboratory derive their two storage-rack gizmo rotations from
the host building frame: native +Y backs face the building's +X wall, with
the open shelves facing the room. Validate all four exported gizmos after regeneration. The habitat pod retains
its native ceiling batten and has no rear sconce mount.

The habitat pod faces the lunar centre. Its Figma footprint uses the reverse
axis of the native pod: resolve that host orientation before rotating contained
placements, retaining rocket ammo at the front and its cradle at the rear.
The raised cabin deck is approximately 0.746 m above ground; native landing
feet are 0.20 m closer to the centre on each side. Runtime jump links and pickup
heights follow the regenerated native floor metadata.

For gizmo-only updates with unchanged Boolean holes, run model.py with
`-- --placements-only`, then validate.py and prepare_faceoff_runtime.py
`--placements-only`. A changed recess deliberately requires a full rebuild.

Ungrouped item cradles inside a cargo container's native footprint inherit that
container's measured floor height before host rotation. The Shield Core cradle
in the common container therefore rests on its 0.16943 m deck rather than ground.

Only required Boolean machining belongs to this map's geometry budget; native
architecture retains its own budget. Machined variants report the native budget
and added Boolean triangles separately. Visual and collision cutouts add 1 mm
on each side of the native fixture footprint (1.002 m for a 1 m fixture).

The laboratory and bastion cargo lifts use their native CargoLift rig and
LiftSurfaceMount gizmos. Flag bases sit on their upper floors. Pulse guns are
disabled in DM; in TDM/CTF each targets the closest opposing robot within 20 m.
Lunar common ground is playable here; Skyfall's lethal-ground rule is separate.

Run headless Blender from library: architecture_variants.py, model.py,
collision.py, validate.py, preview.py, animate.py. Then run
tools/prepare_faceoff_runtime.py with the library Python venv and reimport in
Godot. Validation covers placement axes and visual/collision GLB/FBX recesses.

Faceoff has a 75 x 75 m playable boundary, implemented by four invisible perimeter walls at +/-37.5 m, extending from -2 m to 100 m to contain jump-pad and charged-jump routes. The lunar surface remains continuous through these walls into the surrounding geological rim. Skyfall has no perimeter walls and lunar contact is lethal.

Current map-owned geometry is 3,259 machining triangles against the 25,000 default; imported architecture/scenery/props remain excluded. The habitat pod has bidirectional normal-jump routes through its native doorway, with crouching only after takeoff and a waypoint clearing the cradle. Occupied cradles match their native closed pose and attach payload axes directly to ItemMount.

## Shared builders and lunar crater

Shared scripts live in `models/maps/common/platform/` and `models/maps/common/bridge/`.
The single dimensional platform builder unions proposed extensions before laying
out its perimeter, adds the optional 1.5 m underbody and surface regolith, then
applies placement cuts. Standalone lip and size-specific helpers are retired.
Faceoff uses graded terrain banks, shallow channels, level native building seats
and a broken impact rim. Six original PBR layers describe dust, basalt, exposed
bedrock, rubble, compacted ground and scorch. Skyfall's deeper basin remains
lethal. Terrain is separate scenery, excluded from map machining totals.

Before rebuilding map geometry, generate textures and run
`tools/build_planetary_terrain.py faceoff` with the library Python environment.
After native model/collision/round-trip validation, use
`tools/handoff_planetary_terrain.py` for geometry-preserving runtime delivery.
See [the terrain contract](../../../../docs/library/PLANETARY_TERRAIN.md) for
SDK setup, source ownership, UVs, packed channels and required validation.

## Jumbotron placement

The central jumbotron placement gizmo is 10 m above ground in the game. The temporary arena benchmark alone raises its instance to 20 m.
All four pole-light gizmos face outward from the lunar centre, illuminating
the surrounding play area while the jumbotron lights the centre.

First-floor flamethrower pickups in Bastion and Laboratory use native item
cradles, per Figma nodes 2004:106 and 2001:34 (143:891, checked 2026-10-15).
These freestanding pickups do not create recessed weapon-holder floor pits.
