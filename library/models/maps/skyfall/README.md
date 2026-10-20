# Skyfall

All ten spawn views face toward their zone's islands. Floor spawn-pad gizmos
include a 180-degree facing correction for their native PlayerMount axis;
stasis chambers retain their island-facing door orientation.

Figma source, inspected 2026-10-15.
Both zones use actual node IDs and transforms recorded in figma_inspection.json.
tools/read_skyfall_snapshot.py converts the audit to figma_layout.json.
Placement indices are retained across snapshot updates so deleting a fixture
does not rename unrelated runtime gizmos or platform modules.

The 2026-10-15 layout removes the Mainland 1 higher-ground barricade and its
pressure plate in both zones, beside the repair stations. Their native wells
are filled in both render and collision exports. The Mainland 1 lower-ground
and Mainland 2 higher-ground barricades and their controls remain as authored.

Common ground and its fixtures are removed. Continuous lunar terrain and
irregular dunes are lethal scenery with matching collision. There are no
invisible perimeter walls or playable lunar navigation cells. Deck tops remain
22/26/30 m, with the lowest tapered underbody at 19.7 m above lunar ground.

All 34 remaining floor openings use measured geometry, including 6 x 3 m mainland apertures
and 3 x 3 m island/rooftop holes. Layer names do not override actual dimensions.
Eight wall weapons use milled holder recesses and accessible collection gizmos.
Cradles are freestanding, without floor cuts. Separate props import onto their
gizmos with identity local transforms. Weapons/cores use native payload sockets.
Every ammo pack has its own gizmo; paired origins are 20 cm apart. All 16 thrusters
use authorized platform ThrusterMountNN sockets. Sconce/batten models use native
luminaire gizmos and LightProjection in previews and game.

Map geometry ownership: only integral platform and bridge castings and required Boolean cuts/wells belong
to the map geometry budget. Separate authored models (pillars themselves, thrusters,
sconces/battens, architecture, weapons, ammo and gameplay fixtures) never count
toward that budget: place named gizmos, then import the native assets in previews
and runtime with identity local transforms. Lunar scenery is a separate gizmo
instance. The validated restored map-owned total is **75,228 triangles** (native floor helpers and machining; the placement rig has no render triangles). Preserve every native detail. Skyfall has the user's explicit approval
to raise its map-owned limit to the measured restored total; ordinary map builds
retain the 25,000 default. Report imported asset counts separately.

Every sunken placement uses its native outer footprint plus **1 mm per side** in
both visual and collision Boolean cutters. Thus a 1 x 1 m fixture gets a
1.002 x 1.002 m opening. Apply the same rule to rotated/wall-mounted recesses;
do not scale the prop or move its authoritative gizmo to obtain clearance.

Maps are exempt from visibility culling. Helpers live in models/maps/common.

Each lower portal links to the rooftop portal in the same zone. Pairing-only
handoffs use `tools/prepare_skyfall_runtime.py --portal-pairs-only` from the
library root; geometry and weapon profiles are left intact. Lower-mainland pads use
a 5 m lift through the higher-floor openings and steer onto solid rims below
the roof; other pads retain 15 m travel. Drop routes never land on lunar ground.
Lunar contact is an environmental fall death; protected robots respawn safely,
carried flags return home, and lunar colliders are excluded from drop surfaces.

The two speed-ramp gizmos import native ramp triggers and launch lips. Runtime
map data specifies a 12.6 m/s ballistic impulse to the higher Island 2 decks.
Navigation validates each ramp's flight and exposes a directed speed_ramp edge
for low-EP routes. Directional cyan chevrons use the native belt slope; their
5 cm clear gaps and Reduced Motion behavior are game presentation effects.

## Pipeline

Run headless Blender 5.2 from library, in order:

1. platform_variants.py
2. model.py
3. collision.py
4. validate.py
5. preview.py
6. animate.py

Run tools/prepare_skyfall_runtime.py with library's Python venv afterward.
Reimport and verify in Godot. Validation covers source axes, native sockets and
all holes in visual/collision GLB/FBX round trips. Gizmo and populated previews
are separate. The 13-second showcase combines three-second assembly with a
continuous drone route through a rooftop opening and jump-pad ascent. Native
prop idle loops run throughout.

Platform and lip recess cutters extend 0.5 m above the floor to clear overlapping regolith before its separate export. Underbodies extend uniformly 1.5 m below the 0.8 m deck underside (2.3 m total), putting the lowest platform belly at 19.7 m. Lunar scenery is one seamless mesh with irregular dunes, imported on its own gizmo. Empty stasis chambers stay closed; only spawn admission opens them, and they close once the robot clears the native door sweep.

Shared platform/lip tops are continuous within a perimeter border, with no internal checker grid. Fascia lamps and service recesses share a symmetric spacing plan with at least 40 cm housing-to-recess clearance. Sconce geometry remains a separate native import; gizmo-only previews hide it.

## Native mechanical architecture

The eight raised weapon walls import `architecture/weapon_holder_wall`. Holders
attach directly to `WeaponHolderMount` with identity local transforms; the wall
owns its 1.002 m aperture. Each pillar has exactly one `pillar_platform` beneath
it, centered 0.5 m above its deck, with the pillar on `PillarMountTop`. No upper
block is imported. The 1 m block plus 2.2 m ram meets the upper deck underside
at 3.2 m above the lower surface. Sample the native eased open clip at
0.7166281755 s; do not scale geometry or change coupled stage strokes.
The showcases extend those rams during the second assembly second.

Original fixture gizmos import sconces/battens in populated previews and runtime.
There are 62 supported ceiling battens on the native stacked decks, plus native
room lights. The lunar dome uses one downward top-center sconce. Pole heads and
jumbotron moving heads project light using their native cone, range and axes;
projection geometry remains separate from map castings.

## Shared builders and lunar crater

Shared scripts live in `models/maps/common/platform/` and `models/maps/common/bridge/`.
The single dimensional platform builder unions proposed extensions before laying
out its perimeter, adds the optional 1.5 m underbody and surface regolith, then
applies placement cuts. Standalone lip and size-specific helpers are retired.
Both maps use a continuous lunar crater with an irregular raised rim and shallow,
walkable faceted stones. Faceoff retains its play boundary; Skyfall lunar contact
remains lethal. Imported scenery and props are excluded from map geometry totals.

The crater scenery contains 510 distinct closed gravel/stone pieces,
with interior peaks at most 24 cm and protected fixture approaches. The
M_Regolith/M_RegolithLight/M_RegolithDark UV partitions share a continuous lunar
surface texture and uniform base paint. Platform dressing uses unioned closed deposits rather than
intersecting sheets; GLB/FBX visible-surface overlap checks pass.

2026-10-14: Figma nodes 2011:242 and 2011:415 on the Mainland 2 rooftops specify freestanding item cradles for the flak cannon. Their former holder wells are omitted; both native roof modules and map/collision deliveries must be regenerated together.

## Jumbotron placement

The central jumbotron placement gizmo is 35 m above map origin: 5 m above the 30 m rooftop level. The benchmark retains this authored height.
