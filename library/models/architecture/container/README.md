# Cargo container

The [shared architecture dimensions contract](../README.md#door-and-interior-dimensions)
owns current door and inside-height limits. Delivered dimensions and mechanical
travel are recorded in the regenerated `_rig.json`. Run `../verify_dimensions.py` after rebuilding.

Industrial cargo prop. Doorway faces Blender -Y, up +Z, origin
at the centre of the floor footprint. Metres throughout. External structural envelope: **2.2595 m wide × 2.991 m deep × 2.4388 m high**.
These proportions follow a 10-foot storage container.
This is a fictional sci-fi cargo enclosure, not a certified transport product.
Tensor's authored height is 1.753 m. The structural opening is 2.0 m wide
and 2.1 m tall, with a 0.1694 m sill; hinge/collider allowances narrow the
usable aperture slightly. Pull grips and service conduit are exterior hardware.

The load frame, corner towers, headers and deck form one lofted casting.
Eight recessed lifting sockets interrupt the corner castings. The side walls,
rear bulkhead and roof are continuous formed sheets, 8 mm thick, with bent
strengthening flutes and exact frame seats. Door leaves are broad lofted
unibodies with recessed bays, chamfer transitions, stiffening crossmembers,
retained pull grips and fasteners. The finish uses the existing off-white
paint, grey paint, matte black and stainless steel, with a flush cyan lock
status diffuser; it has no team colour variants.

The horizontal pulls sit wholly on the reinforcement flats, outboard of the
actuator cylinders: 168 mm free grip, 65.89 mm finger clearance and two integral
mounting feet with captive screws. Receiver bushes are recessed wholly into
the header and sill; no receiver lip projects into the opening.

Each door has three interleaved knuckle/fork hinges with a stainless through
pin and retaining caps. Two opposing powered shoot bolts engage bored frame
receivers. Guide bushes and fitted actuator saddles support the rods. Their
drive internals are enclosed in the cylinder bodies; power distribution is
enclosed in the header, upper hinge rotary contacts and door crossmembers.
The fixed junction cabinet has a supported conduit with retained end glands.
No exposed wire spans a moving hinge.

The thirteen-bone rigid skeleton is Root, front LeftDoor/RightDoor, rear
RearLeftDoor/RearRightDoor, and TopBolt/BottomBolt children for every leaf.
Each vertex has exactly one bone influence. Both ends use the same interlocked
door construction. Four meshes keep each render mesh below 5,000 triangles.
The vertical door pivots are at x=±1.079, y=-1.468, z=1.2955 m. Leaves swing
outward 105°. Bolt translation is 65.89 mm into the captive guide system.

Four event clips, each 96 frames / 3.2 seconds at 30 fps:

- `front_open` / `rear_open`: withdraw the end's four bolts, pause, then swing its leaves.
- `front_close` / `rear_close`: return the end's leaves before extending its bolts.

Skyfall holds `rear_open`; the front end remains closed. The long container holds
both open actions. Consumers combine complete endpoint poses on the native rig.

There is no continuous idle motion: a parked cargo container has no mechanism
that should run continuously. Use the complete clips for the interlock;
arbitrary door motion with extended bolts is mechanically invalid. The Root
has no motion. The showcase sequences opening and closing with held endpoints.

`model.py` is the editable source. It checks closed manufactured solids, exact
intersection volumes, connected parts, sampled rig/FK agreement, every clip
frame, independent door sweeps, and coplanar faces. Visibility culling precedes
unique per-material UV atlases and GLB/FBX export. `collision_extras.py` retains
the hollow cargo space using convex structural slabs and separate moving door
and bolt pieces; small sheet folds and sealed hardware cavities are filled.
`validate.py` imports render and collision GLB/FBX in fresh scenes, checking
bounds, triangle counts, material slots, UVs, rigid weights, bone names, both
clips and sampled animated transforms against the authored Blender rig.

Run from `library/`:

```powershell
$blender = (Get-Command blender -ErrorAction Stop).Source
& $blender --background --factory-startup --python models/architecture/container/model.py
& $blender --background --factory-startup --python models/architecture/container/preview.py
& $blender --background --factory-startup --python models/architecture/container/scale_preview.py
& $blender --background --factory-startup --python models/architecture/container/collision.py
& $blender --background --factory-startup --python models/architecture/container/model.py -- --exports-only
& $blender --background --factory-startup --python models/architecture/container/validate.py
& $blender --background --factory-startup --python models/architecture/container/animate.py
```

Tensor must already be built for `scale_preview.py`. The comparison loads his
authored body, default head and rig at original scale without exporting him.
`-- --draft` skips full visibility culling, atlas packing and exports.
Generated scenes, exports, previews, video and QA reports stay ignored.

Run `--exports-only` after the unchanged generic collider script to preserve
every FBX animation sample. Default FBX simplification can otherwise drift
across the stationary bolt-release interval. This refreshes existing render
and collision exports without rebuilding geometry or UV atlases.

Verified delivery: 4,773 render triangles, 132 collider triangles. Static
solid intersections, connectivity, 260 animated/sweep states, coplanar faces,
material atlases and render/collision GLB/FBX round trips pass. Previews include
front, rear, both side profiles, open/unlocked poses and authored Tensor scale.
The 1280×720, 30 fps showcase is 8.23 seconds; all 247 frames decode.

[`container_long`](../container_long/README.md) reuses this source with a
6.058 m body and separately operable doors at both ends.
