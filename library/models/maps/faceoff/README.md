# Faceoff

Authored from Figma file `0pxQrXAGeHplJ0ANVYwD8e`, frame `143:891` on page
`143:890`. Both flag placements use the actual added node IDs and transforms.

Native architecture, fixtures, weapons, ammo, lights and lunar scenery are
separate assets imported at named map gizmos with identity local transforms.
Each ammo pack has its own gizmo; pair origins are 20 cm apart. Held payloads
attach to the holder/table's live rotating-bone socket.
The laboratory's two storage-rack gizmos turn 90 degrees from their Figma
footprint axes so their native +Y backs face its +X wall. The habitat pod retains
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

Faceoff has a 75 x 75 m playable boundary, implemented by four invisible perimeter walls at +/-37.5 m, extending from -2 m to 100 m to contain jump-pad and charged-jump routes. The lunar surface remains continuous through these walls into the surrounding dunes. Skyfall has no perimeter walls and lunar contact is lethal.

Current map-owned geometry is 7,855 machining triangles against the 25,000 default; imported architecture/scenery/props remain excluded. The habitat pod has bidirectional normal-jump routes through its native doorway, with crouching only after takeoff and a waypoint clearing the cradle. Occupied cradles match their native closed pose and attach payload axes directly to ItemMount.

## Shared builders and lunar crater

Shared scripts live in `models/maps/common/platform/` and `models/maps/common/bridge/`.
The single dimensional platform builder unions proposed extensions before laying
out its perimeter, adds the optional 1.5 m underbody and surface regolith, then
applies placement cuts. Standalone lip and size-specific helpers are retired.
Both maps use a continuous lunar crater with an irregular raised rim and shallow,
walkable faceted stones. Faceoff retains its play boundary; Skyfall lunar contact
remains lethal. Imported scenery and props are excluded from map geometry totals.

The crater scenery contains 389 distinct closed gravel/stone pieces,
with interior peaks at most 24 cm and protected fixture approaches. The
M_Regolith/M_RegolithLight/M_RegolithDark UV partitions share a continuous lunar
surface texture and uniform base paint. Platform dressing uses unioned closed deposits rather than
intersecting sheets; GLB/FBX visible-surface overlap checks pass.

## Jumbotron placement

The central jumbotron placement gizmo is 10 m above ground in the game. The temporary arena benchmark alone raises its instance to 20 m.

First-floor flamethrower pickups in Bastion and Laboratory use native item
cradles, per Figma nodes 2004:106 and 2001:34 (143:891, checked 2026-10-15).
These freestanding pickups do not create recessed weapon-holder floor pits.
