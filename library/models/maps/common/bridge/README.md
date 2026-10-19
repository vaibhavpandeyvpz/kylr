# Modular 5×5 m bridge

`bridge` connects platform edges directly across a **5 m gap**, with a
**5 m wide deck**. The closed 0.8 m casting, flush traction panels, side vents
and recessed belly reinforcement match the floating platforms. No thrusters,
baked lights or sand obstruct the connector. Default total budget is **5,000
triangles**, including both railings and the cover; the current build is 4,697.

Coordinates are metres, +Z up, front -Y. The rear deck-edge centre is the
origin. Deck bounds are x=-2.5..2.5, y=-5..0, z=-0.8..0. Both entrances are
fully open. These are library assets; game integration is a separate task.

## Direct docking

The parametric platform authors `BridgePlug*` frames on eligible exposed 5 m
lands. A proposed integral extension can carry the connecting land; omit its
border across the bridge width. Align the complete native socket frames.

The bridge exports `BridgeSocketRear` (identity at origin) and
`BridgeSocketFront` (y=-5, rotated 180° about Z). Use the full exported frames:

`bridge_world = first_platform_plug_world × inverse(bridge_socket_rear_local)`

`second_platform_world = bridge_socket_front_world × inverse(second_platform_plug_local)`

This joins both decks and bellies flush without scaling, overlap or a height
change. Select an opposing edge on the second platform. For end-to-end bridge
segments, oppose the two sockets with an additional 180° turn:

`next_bridge_world = current_front_socket_world × rotation_z(180°) × inverse(next_rear_socket_local)`

These are placement gizmos,
with no physical pin projecting into an unoccupied platform edge.

A full-width bridge occupies the fascia where some sconces would otherwise
sit. Each platform bridge plug records `omit_fixture_mounts`: skip those
fixture gizmos **only when that connection is occupied**. Union the omission
lists when attaching bridges on several edges. Unoccupied edges retain their
authored, symmetric lamp layout. This applies to lamps inside the actual
bridge footprint; ordinary lip connections keep their existing clearances.

## Independent options

| Render mesh | Corresponding collision mesh | Option |
| --- | --- | --- |
| `SK_Bridge5X5Deck` | `SK_Bridge5X5DeckCol` | Always enabled |
| `SK_Bridge5X5RailingLeft` | `SK_Bridge5X5RailingLeftCol` | Optional left railing |
| `SK_Bridge5X5RailingRight` | `SK_Bridge5X5RailingRightCol` | Optional right railing |
| `SK_Bridge5X5Cover` | `SK_Bridge5X5CoverCol` | Optional roof and upper columns |
| `SK_Bridge5X5SideFrameLeft` | `SK_Bridge5X5SideFrameLeftCol` | Shared left toe frame and end posts |
| `SK_Bridge5X5SideFrameRight` | `SK_Bridge5X5SideFrameRightCol` | Shared right toe frame and end posts |

All meshes are rigidly weighted to the same static Root. Toggle the render
mesh **and its collider** together. The generated rig JSON records every
option/collider pair. All eight left/right/cover combinations are supported.
Each shared side frame is enabled when its railing **or the roof** is enabled.
The rig JSON records this as `enabled_if_any`. Instantiate the shared frame
once, not once per option. Roof-only uses these end posts without guard infill;
bare deck hides all five optional meshes and their colliders. The full
configuration is exported by default. There are no animation clips.

`SconceLightMountLeft` and `SconceLightMountRight` place the authored
`sconce_light` at each side's centre: x=±2.5, y=-2.5, z=-0.4. No lamps are
placed at the front or rear entrances. Their backplates sit on solid fascia
between the recessed service vents; neither the railings nor cover affects
their clearance. The bridge exports fixture gizmos only, and previews import
the actual authored lamps at those frames. Instantiate the props with an
identity local transform under the respective mounts.

The side structure is one load path. Each shared toe frame has two end posts;
the removable guard infill supplies three intermediate stanchions and retained
horizontal tubes. Split, bored saddles clamp the stainless handrail onto its
stanchions. The roof columns stack directly onto the same end posts at z=1.09,
with identical 80 mm by 180 mm sections. Paired splice cheeks and two retained
through-bolts bridge each joint; seated bearing saddles transfer roof loads.
The guard reaches 1.12 m, and the clear walkway is at least 4.51 m wide.

These are fixed structural parts: no unmotivated belt drive, rail cable, roof
hydraulic actuator or service manifold. Joint seating, bored cheeks and retained
fasteners follow the authored item cradle and Tensor rather than copying their
motors onto stationary architecture. Six faceted, canted impact shields form a sacrificial outer layer spaced
above the continuous inner skin. Each panel has two physical mounting seats
and recessed captive hold-downs aligned with those seats. Open inter-panel
gaps and protected centre-seam retainers express the layered lunar debris
shielding construction. The lower load plate is flat: underside z=2.84 m, upper surface z=2.94 m.
Only the spaced outer plates carry the roof taper. The roof remains
supported with guard infill removed. Minimum headroom is 2.84 m, and the highest
inner ceiling stays below 3 m. Both entrances remain open.

`BattenLightMount` is centred at (0, -2.5, 2.84) m on the flat roof underside.
A 90 degree Z turn aligns the authored batten's long local X axis with bridge
Y, front to back. The mount's `required_mesh` is `SK_Bridge5X5Cover`; instantiate
and remove the fixture with the roof. The bridge exports only the gizmo; all
previews use the authored batten model. Its mounting feet sit on the flat plate
and its lowest surface is approximately 2.738 m above the deck.

The collider companion has six named meshes: exact deck (12 tris), left/right
shared side frames (36 each), guard infill (72 each), and roof/upper columns
(372). Small mounting gaps use solid convex proxies. Render and collision use
the same option dependencies, preserving all eight configurations.

## Build and QA

Run from `library/`, after generating the platform family for assembly previews:

```powershell
& ./.venv/Scripts/python.exe models/maps/common/build_platforms.py
& ./.venv/Scripts/python.exe models/maps/common/bridge/build.py
```

The bridge runner also accepts `--stage build`, `validate` or `preview`.
The standard studio previews include underside and orthographic views. Four
option-state beauty images and two assembly images use actual exported
platform, sconce and thruster models, positioned by their docking/mount frames.

The native round-trip validator checks GLB/FBX mesh counts, materials, UVs,
unit scale, rigid Root, socket frames, closed underside, collider pairs, and
all eight option states. It loads the authored Tensor mesh envelope and checks
traversal width and canopy headroom along the full bridge. The platform audit
also proves bridge docking bounds and authored fixture clearance after applying
the explicit lamp omission list.

Bridge load frames, guard stanchions and canopy use the shared platform-border
`M_Secondary` paint and its unchanged native roughness/metallic settings. There
is no bridge-specific black `M_Metal` finish. Deck paint, stainless handrails and
functional recessed vent backings retain their native material roles.
