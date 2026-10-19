# Shared parametric platform

Import `platform_builder.build` from `models/maps/common/platform`.
There are no size-specific platform models or standalone lip helpers.
`models/maps/common/bridge` owns the separate native bridge and its collider.
Shared terrain, machining and preview-light utilities live in `common/`.

## Inputs and construction order

- `size`: base width/depth in metres; base centre is the origin, +Z up.
- `extensions`: proposed rectangles `[xmin, ymin, xmax, ymax]` in base axes.
  Each must share an edge with the resulting footprint, not just a corner.
- `omit_border`: exposed perimeter segments `[[x0,y0],[x1,y1]]` to leave clear,
  including a lip's bridge-facing edge or just the 5 m connecting span.
- `with_underbody`: retain the full native tapered chassis, 1.5 m below the
  0.8 m deck bottom. Integral extensions are closed deck cantilevers.

1. Exact Boolean union of the base and every proposed extension.
2. One continuous inset painted surface and 16 cm perimeter border following
   that union. No checker grid or internal lip seam. Omitted spans have no border.
3. Add the native tapered underbody when requested.
4. Add seeded, irregular 1.5–60 mm surface regolith, clipped to the union footprint.
5. Map machining cuts the casting, collision and dressing together. Sunken
   footprints have 1 mm clearance per side and cutters extend 0.5 m above the
   floor. Separate the machined regolith onto its own Root-frame gizmo afterward.

## Authoritative fixture plan

Thruster count uses the longest base span: below 5 m none, at least 5 m one
central unit, at least 15 m two diagonal units, at least 25 m four corner units.
The full native 5 m mounting discs must fit and remain disjoint. Corner/diagonal
mounts have uniform disc-to-belly-edge clearance, normally 0.5 m; narrower
rectangles reduce that clearance equally on both axes only as required to fit.
Invalid configurations fail instead of overlapping thrusters. The integral lips
never change the base's loadout or its native thruster axes.

Sconces and recessed fascia panels are co-planned on the final exposed perimeter.
Lamp positions are equally spaced within each land, with 1.1 m corner insets;
recesses require 40 cm clear housing-to-recess/edge spacing. Bridge docking spans
omit lamps and recesses. Ceiling battens use a uniform grid of at most 5 m and
are retained only where their actual backplates have solid support after cuts.
Sconces, battens, thrusters, pillars, pillar platforms and weapon walls remain
separate gizmo imports. No upper pillar platform is used.

`platform_footprint.py` plans the union perimeter and variable border offsets;
`platform_layout.py` consolidates the Figma base/extensions; `platform_placements.py`
owns thruster positions. Native bridge plugs are authored on exposed 5 m lands.
`validate_platform_castings.py` audits delivered render contents, triangle counts
and GLB/FBX socket matrices. `refresh_platform_mounts.py` handles socket-only
refreshes without altering geometry.

## Standalone use

Pass a JSON config with `name`, `size_m`, `extension_rects_m`,
`omit_border_segments_m` and `underbody` to `platform_builder.py -- --config PATH`.
Outputs live beside the config. Map builds call the same function, apply their
machining, and deliver matched collision exports. Run from library using the
supported Blender 5.2 executable. Preserve native materials and every structural
feature; split render delivery only for the 5K per-mesh limit.

## Regolith surfaces

Deposits are closed solids with their bases buried 1 cm into the deck. Union
overlapping deposits before footprint clipping and placement cuts; never export
intersecting open sheets. Visible relief stays 1.5–60 mm above the deck and uses
its actual faceted normals. `refresh_regolith.py` rebuilds the separate dressing
from delivered platform footprints/cutouts; `validate_regolith.py` checks both
GLB and FBX for overlapping visible sheets, relief and per-mesh limits.
`refresh_regolith_showcase.py` reimports these static assets on their existing
native gizmos while retaining the cinematic and rig actions.

Regolith deposits stay at least 20 cm from every native cutout edge, including
rotated wells. Omit whole intersecting deposits before union to preserve their
feathered contours. Placement cutters still retain the 1 mm fixture clearance
and reach 0.5 m above the deck. All dressing uses the shared lunar PBR set in
`textures/lunar_surface`, matching architecture aprons and crater terrain.
