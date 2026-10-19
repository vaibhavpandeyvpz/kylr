# Hub

The [shared architecture dimensions contract](../README.md#door-and-interior-dimensions)
owns current door and inside-height limits. Delivered dimensions and mechanical
travel are recorded in the regenerated `_rig.json`. Run `../verify_dimensions.py` after rebuilding.

Four-way lunar architecture, centred at ground level, front −Y. The render budget is **10,000-triangle total ceiling**, including optional lunar
surface dressing; each render mesh remains below 5,000 triangles. The complete
building, ramps and optional apron stay within a **6 × 6 m** ground envelope.

The selected design retains straight vertical door housings, pale formed armour,
grey access plates, black guides and amber exterior indicators. The recessed
side panels meet continuous walls without extra vertical strips at their corners.
Inboard roof ties connect the storage towers to the central crown. These are
exact Boolean unions in the pressure shell, rather than intersecting exports.
Only the source scripts are versioned.

## Doors and mechanics

Each cardinal entrance has 1.50 m clear width and 1.935 m nominal clear height,
above the 0.12 m deck. Grounded ramps meet that deck at all four approaches.
The hollow room provides unobstructed crossing between opposite entrances.

Each blast door has two rigid telescoping leaves, with separate depth lanes.
The upper leaf travels 0.968 m and the lower 1.935 m, upward on full-height slotted
guides with replaceable bearing shoes. Crossheads have bored rod sockets and
retaining nuts. Both actuator pairs mount to flat overhead flanges. Lower-leaf
actuators have independently rigged hollow intermediate sleeves; cylinder bores,
rod lengths and pockets preserve at least 150 mm of rod/sleeve engagement and
clear the crossheads through the full stroke. Translation uses linear bearings;
there is no artificial rotary hinge on a sliding leaf. Service conduits have
bored wall-supported saddle/end glands and no unsupported runs.

There are 17 rigid bones: `Root`, eight leaf bones and eight intermediate sleeve
bones. All vertices have exactly one weight of 1.0. Each action is 96 frames at
30 fps (3.2 seconds), with restrained acceleration and deceleration:

- `open_front` / `close_front`
- `open_left` / `close_left`
- `open_rear` / `close_rear`
- `open_right` / `close_right`
- `open` / `close` (all four entrances together)

Independent clips key only their own leaves and sleeves in native GLB and FBX;
they preserve other entrances' current poses. The showcase makes a full camera
turn while opening each entrance, then closing all four.

## Runtime companions

`SK_HubStructure` carries fixed shell, floor, roof and hardware.
`SK_HubDoors` carries moving leaves and actuators.
`SK_ArchitectureRegolith` is the optional perimeter, using `M_Regolith` and
`Root` weights, consistent with bunker/cistern/lodge. Hide or remove it without
altering the building or collision. Its narrow apron keeps four approaches
level and does not extend beyond the 6 m envelope.

Roof windows use `M_Glass`: RGB black, alpha **0.10**. Interior lights are
attachment gizmos only (`BattenLightMount`, `SconceLightMountNorthEast`,
`SconceLightMountSouthWest`), ray-fitted to real interior surfaces. No interior
lamp geometry or light nodes are exported. Exterior status strips are geometric
emissive inserts. Collision uses convex architectural slabs with an empty room
and four real passage voids, moving leaf companions and no regolith collider.

## Regeneration and verification

Run from `library/` with Blender 5.2:

```powershell
$hubBlender = (Get-Command blender -ErrorAction Stop).Source
& $hubBlender --background --factory-startup --python models/architecture/hub/model.py
& $hubBlender --background --factory-startup --python models/architecture/hub/preview.py
& $hubBlender --background --factory-startup --python models/architecture/hub/collision.py -- --no-render
& $hubBlender --background --factory-startup --python models/architecture/hub/validate.py
& $hubBlender --background --factory-startup --python models/architecture/hub/inspect.py
& $hubBlender --background --factory-startup --python models/architecture/hub/animate.py
```

`model.py` checks closed manufactured parts, exact solid intersections, rigid
connectivity, every animation frame, shared-plane z-fighting, triangle budgets
and unique material UV layouts. Cardinal transforms use exact integer matrices,
avoiding numerical wedges at shared planar construction joints. `validate.py`
round-trips render and collider GLB/FBX, comparing animated skin matrices and
testing that independent clips leave the other three entrances untouched.
`inspect.py` checks standing traversal volumes and renders room/mechanical views.

`--draft` makes an unvalidated design-review blend; `--audit-rest` checks the
closed assembly only. Neither substitutes for the complete build. Optional
`--surface-only` regenerates only the apron on a previously validated build.
Godot import and gameplay integration remain a later task.
