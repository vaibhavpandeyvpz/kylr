# Architecture delivery contract

## Door and interior dimensions

Single doors/doorways must be no larger than **1.5 × 2.1 m** (width × height).
Double-door openings normally measure **2.0 × 2.1 m**, across both leaves.
Door leaves must also fit these limits (combined width for doubles);
frames, seals and hinge hardware surround the structural opening.
These are structural opening dimensions; chamfers and hardware must still
leave Tensor's original mesh and standing capsule enough usable clearance.
Do not inflate doors just to make navigation easier.
Derive wall and foundation cutouts from the delivered door frame. Match the
approach ramp to the frame's feet; resizing a door must not leave the former
wide opening or unsupported gaps alongside its sill.

Every occupied room, level and cabin must have at most **3.0 m** from the
walkable floor top to the ceiling underside, including the highest point of
sloped ceilings. Outside roof equipment and door-storage towers are excluded.
Smaller spaces are retained when Tensor fits. Open shelter approaches and
cargo-lift shafts are not doors or additional rooms; service hatches are not
player entrances.

`container` and `container_long` are architecture assets. Their generators,
colliders, previews, videos and validation scripts live alongside the other
buildings here; the long variant still shares `container/model.py`.

| Asset | Complete doorway W × H (m) | Maximum designed interior height (m) |
| --- | --- | ---: |
| bunker | 1.35 × 2.056, single | 2.815 |
| lunar_dome | 1.02 × 1.94, single | 2.950 |
| hangar | 2.00 × 2.10, double | 3.000 |
| cistern | 1.50 × 2.10, front/rear singles | 2.364 |
| laboratory | 2.00 × 2.10, double | 3.000 ground / 2.697 upper |
| bastion | 1.50 × 2.10, single | 3.000 ground / 2.697 upper |
| lodge | 1.50 × 2.088, front/rear singles | 2.320 |
| hub | 1.50 × 1.935, four singles | 3.000 |
| habitat_pod | 1.20 × 2.10, single | 2.399 |
| container | 2.00 × 2.10, front/rear doubles | 2.200 |
| container_long | 2.00 × 2.10, front/rear doubles | 2.200 |
| shelter | Open front/side approaches | 2.700 (minimum approach 2.380) |

The source generators bake dimensions, mechanical pivots and travel into
unit-scale meshes/rigs before their solid/contact/motion audits. Colliders use
the same sizing frames. `_rig.json` records delivered `architecture_dimensions`.
Run `verify_dimensions.py` headlessly to ray-check the actual room surfaces and
open apertures in `.blend`, GLB and FBX, then run each asset's Tensor clearance
audit. `verify_traversal.py` covers unscaled Tensor idle/walk/run and the
standing capsule in both containers, the pod and all four hub entrances.
Reports under `target/architecture_dimensions/` are generated outputs.

The counts below include the optional regolith dressing. Current native-format
QA results are in each regenerated `_rig.json` and round-trip report.

The grounded architecture assets listed with regolith below export one
optional perimeter dressing mesh,
`SK_ArchitectureRegolith`, using `M_Regolith`, rigidly weighted to `Root`.
Hide or remove that mesh to omit the lunar apron without changing the building,
its rig, or its blocking collision. The apron has no collision companion.
Its bounds can extend beyond the fixed building; approaches remain clear.
Its triangles count toward the existing asset budget.
The raised, freestanding habitat pod has no regolith apron; its four landing
pads define its ground contact.

| Asset | Total triangles | Regolith triangles | Budget |
| --- | ---: | ---: | ---: |
| bunker | 4,733 | 178 | 5,000 |
| lunar_dome | 4,929 | 0 | 5,000 |
| hangar | 9,925 | 192 | 10,000 |
| cistern | 11,572 | 240 | 12,000 |
| laboratory | 12,973 | 192 | 15,000 |
| bastion | 8,383 | 192 | 10,000 |
| lodge | 9,483 | 84 | 10,000 |
| hub | 8,387 | 144 | 10,000 |
| shelter | 4,178 | 96 | 5,000 |
| habitat_pod | 7,426 | 0 | 7,500 |
| container | 8,654 | 0 | 10,000 |
| container_long | 8,730 | 0 | 10,000 |

Hangar and laboratory two-leaf entrances export independent `open_left`,
`close_left`, `open_right`, and `close_right` actions, in addition to paired
`open` and `close`. Independent actions contain only the selected leaf and
its lock tracks, preserving the other leaf's current pose.

Bastion has a single inward-hinged door and exports `open`, `close`,
`lift_up`, and `lift_down`. Its 1.95 m approach serves the 1.5 m clear entrance.

Cistern has front and rear entrances. Use `open_front` / `close_front` and
`open_rear` / `close_rear` independently. Legacy `open` / `close` control the
front entrance; `open_both` / `close_both` control both. Lodge follows that
same front/rear action contract. Bunker has one entrance.

Hub has four cardinal entrances, with independent `open_front`, `open_left`,
`open_rear`, `open_right` and matching close actions. `open` / `close` control
all four telescoping doors together. Its optional apron stays within its
6 × 6 m envelope.

Shelter is open and walkable from front, left and right on a 5 × 5 m envelope.
Its canopy and piers share a continuous machined profile. One top side access
plate remains on each side; the inclined side arms have no lining or plates.
Its sealed coolant cartridges export `circulate`; the rear service leaf exports
`service_open` / `service_close`. Pump sight glasses are black at 10% opacity.
One `BattenLightMount` on the roof underside and one `SconceLightMount` on the
inside back wall are fixture gizmos only. See [Shelter](shelter/README.md).

Run `verify_surfaces.py` in headless Blender to check the common optional
surface contract in native GLB and FBX and its exclusion from collision.
Run `verify_leaf_actions.py` to check independent motion in render and
collision exports. Each asset's own validation and scale checks still apply.

Habitat pod has a single outward-hinged entrance and captive header lock,
with `open` / `close` event clips. Its 0.55 m threshold is reached by jumping;
there is no ramp. Window and door-insert wells follow their chamfered inserts.
Its paired front hydraulic braces, fixed rear struts and external thermal
assemblies stay rigid while parked. Its render budget is 7,500 triangles.
See [Habitat pod](habitat_pod/README.md).

Platform, bridge and lip construction helpers live under
[models/maps/common](../maps/common/platform/PLATFORMS.md). Map generators use their
native docking frames, optional tapered chassis and luminaire sockets; they
are not standalone architecture catalog entries.

### Native room lights in assembled maps

Original model fixture empties own lamp position and axes; room lights face into
the supported interior, ceiling lights down. Laboratory and bastion floors use a
uniform 2 x 2 ceiling batten layout per floor. The lunar dome has exactly one
sconce at its crown. `refresh_lighting.py` regenerates only source light sockets
and exports without altering authored geometry; `validate_lighting.py` audits
GLB/FBX source matrices and emitter direction. Maps import luminaire geometry on
these sockets and use the native LightProjection cone/range in previews and game.

`pillar_platform` and `weapon_holder_wall` are now authorized for map integration.
Use the former only at the bottom of a pillar. Its top socket accepts the native
ram; choose the native open pose that reaches the next floor, without a top block.
The wall's WeaponHolderMount owns its recessed holder's position and axes.

## Lunar finish and socket previews

Optional regolith aprons use `textures/lunar_surface` via the shared
`lunar_material.py`, matching map deposits and crater terrain in previews and
runtime. Prop preview scripts render authored socket axes and names using
`models/preview_gizmos.py`; these helpers are render-only and never exported.
