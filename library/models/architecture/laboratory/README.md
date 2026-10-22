# Laboratory

The [shared architecture dimensions contract](../README.md#door-and-interior-dimensions)
owns current door and inside-height limits. Delivered dimensions and mechanical
travel are recorded in the regenerated `_rig.json`. Run `../verify_dimensions.py` after rebuilding.

Duplex industrial architecture, authored in metres with front −Y,
up +Z and origin at grade beneath the centre of the building. `model.py` is the editable source; Blender and runtime files are
generated, ignored outputs.

Materials follow KYLR's existing props: off-white
`M_Primary`, grey `M_Secondary`, matte black `M_Frame`, stainless `M_Joint`,
cyan `M_Emissive` and black `M_Glass` with opacity 0.10. The full grey metal
roof matches the cistern, with recessed access covers. Integral column end
flanges seat on horizontal load rings. Parallel inner/outer chamfers retain
283 mm upper corner wall thickness. All four ground-floor walls are plain
pressure shell with two symmetric exterior sconce gizmos per face. Side pairs
sit at the same height and spacing as the front and rear pairs beside the
entrance or lift. Upper rear process banks remain mounted on their native skids.

The fixed building fits a **15 × 15 m** placement envelope. It has a regular
integral floor and grounded footings, with no surrounding metal platform.
Ground floor elevation is
0.2553 m; the upper floor is at 3.4468 m. The upper deck is 13 × 13 m before the
clipped corners and lift/machinery apertures, leaving **153.1442 m²** of usable
floor. The upper observation room has at least 2.1223 m headroom at its perimeter,
rising to 2.6968 m centrally. The integral entrance approach rises 0.2553 m over
0.60 m. The entrance is 2.00 m wide with 2.10 m central headroom.

The render budget is **15,000 triangles**. The current total is
**11,613 triangles**, including optional
regolith, across six meshes. Every mesh retains the 5,000-triangle maximum.
UV painting layouts are unique per material at 2048 px; GLB is the primary
export and FBX is the fallback.

## Mechanisms

Two lofted stainless steel pressure leaves open inward through 105°. Their
castings, armor inlays and moving hinge fittings use the existing M_Joint
stainless material; fixed frames retain their original finish. Each has three interleaved,
bored hinge sets, retained through-pins, a coaxial geared drive and an upper
shoot bolt. The bolts retract before the doors turn and engage only once the
leaves return home. The door kit shares the architecture hangar's audited
mechanism; the laboratory shell, floors and service assembly are its own.

The rear lift has a flat, open **3 × 3 m** deck with an integral rear crosshead,
two anchored guide rails, fitted C-shaped slide shoes and two simple fixed
shafts with enclosed powered nut carriages attached to the crosshead. Shaft
ends have grounded bearing pedestals and rear-wall top brackets. There are no
telescopic stages. Carriage bores provide running clearance around each shaft.

The lift travels **3.1915 m** between floor elevations. The floor opening fits its
platform with a 20 mm perimeter running gap; the rear strip accommodates the
crosshead, guide shoes and shaft carriages. Upper landing side guards leave
the front access lane open. Service pipes, vessels and roof conduit terminate
on saddles, flanges or gland boxes. Roof covers are bolted service access parts.

Eight event actions are exported at 30 fps, frames 0–96: paired `open` / `close`,
`lift_up` / `lift_down`, and independent `open_left` / `close_left` and
`open_right` / `close_right`. Each independent clip keys only its leaf and lock,
preserving the opposite leaf's pose. `../door_actions.py` filters exporter-added
rest tracks in GLB and native FBX bake data. No idle motion is added.

`laboratory_col.glb/.fbx` contains convex structural blocking pieces and
articulated door/platform blockers on the same skeleton and actions. Each
blocking mesh is limited to 500 triangles. The distinct
**`SK_LaboratoryLiftPlatformTrigger`** mesh is a 12-triangle occupancy volume
rigidly weighted to **`CargoLift`**, 16 cm high above the deck, inset 2 cm from
each platform edge. Import it later as an area, separately from solid blockers.

## Optional terrain and fixture mounts

`SK_ArchitectureRegolith`, using `M_Regolith` and rigid `Root` weights, is the
common optional perimeter node across bunker, cistern, hangar and laboratory.
Hide it independently to omit lunar dressing. Its 192 triangles count toward
the asset budget; it is excluded from blocking collision and traversal tests.
`optional_surface` and `building_bounds_m` in `_rig.json` distinguish the visual
apron from the fixed building. Export bounds include the apron.

Eight `BattenLightMount*` and four `SconceLightMount*` gizmos seat on actual
interior surfaces. Eight additional exterior sconce gizmos seat directly on the
plain ground-floor walls. No runtime lights or fixture meshes are included.

## Regeneration and inspection

Run from `library/` with the Blender 5.2 executable specified in `AGENTS.md`,
using `--background --factory-startup --python-exit-code 1 --python`, in order:

1. `models/architecture/laboratory/model.py`
2. `models/architecture/laboratory/collision.py`
3. `models/architecture/laboratory/validate.py`
4. `models/architecture/laboratory/preview.py`
5. `models/architecture/laboratory/inspection.py`
6. `models/architecture/laboratory/scale_check.py`
7. `models/architecture/laboratory/animate.py`

The build checks manufactured parts for manifold geometry, exact solid
intersections, structural connectivity, every animation frame, coplanar
artifacts, foundation envelope, material UVs and total/per-mesh budgets.
`validate.py` imports both native formats into fresh scenes and compares rigid
weights, dimensions, materials, all actions and sampled skin transforms.
`scale_check.py` checks the actual Tensor and existing idle/walk/run clips
against the opened entry and walkable interior in both directions, including
the lift's ground landing. No Tensor mesh is included in runtime exports.

Studio previews show the exterior, door poses and lift states. Inspection
renders expose both storeys and the cargo machinery using temporary cutaway
copies. The showcase opens/closes the entrance, then transitions to the
cutaway view while the lift travels up and down. Cutaways, studio lights and
scale models never modify the saved asset or enter runtime exports.

`model.py -- --surface-only` refreshes the optional apron and native exports.
Run `../verify_leaf_actions.py -- hangar laboratory cistern` for independent
controls and `../verify_surfaces.py` for the shared terrain-node contract.

## Chamfer collision

Collision wall loops use an explicit eight-point outline, independent of the
shared render helper's mutable corner tessellation. Lower-wall transitions now match the visual shell at 2.98/3.62 m
before architecture height scaling. Both GLB and FBX collider round trips test
all four corner walls at four heights. The blocker export has 916
triangles plus the separate 12-triangle lift occupancy trigger, within budget.
