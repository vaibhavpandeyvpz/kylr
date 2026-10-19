# Solar tower

Solar tracking prop: 3.00 m tall, 1.899 m wide, with a 1.04 m
square foundation. Metres; origin at floor centre; photovoltaic front -Y,
up +Z. Tensor is 1.753 m tall. Five bowed rows carry ten flat modules, each 0.78 × 0.426 × 0.042 m. Lofted
painted castings, stainless hardware, black conduit and bronze gear faces use
the library's industrial finish. The non-emissive navy photovoltaic laminate
has a packed procedural cell/busbar texture, analytic SolarSurface UV0 and
unique MaterialAtlas UV1. There are six materials and 4,418 render triangles
within the 5,000-triangle cap. The collision companion has 484 triangles in
31 convex pieces, within its 500-triangle cap.

The welded foundation and diagonal webs support a sealed azimuth gearbox,
weather seal, toothed slew ring and retaining flange. The fork supports a
coaxial elevation shaft with seated thrust washers and retained ends. The
mast has four chords, alternating fish-mouthed diagonals, collars and five
crossrails. Each module has a recessed cell plate, rear hinge barrel, retained
shaft and two bearing ears seated on its rail. Three manual indexing wheels
have seated lock dogs. Rear terminal boxes and routed DC leads connect to a
protected mast trunk and central combiner. These module hinges remain manually
indexed; the powered motion is confined to the two main tracking axes.

Rigid skeleton: Root → Azimuth → Elevation. Each vertex has one normalized
bone influence. Azimuth rotates around +Z at z=0.359 m (±180°). Elevation
rotates around +X at z=0.635 m (-65° to +6°). All panels, their local wiring,
and the mast circuit move together, so no animated lead stretches across a
joint. Gearbox electrical transfer and elevation drive internals are enclosed.

Clips at 30 fps:

- `track`: seamless 8-second slow tracking loop, ±8° yaw and ±3° elevation.
- `service_lower`: 6-second eased move from upright to -65° service position.
- `service_raise`: 6-second eased return to upright.

`model.py` is the editable source. Its lofts and exact booleans are checked
for manifold geometry, solid intersections, connected seats and coplanar
faces. Motion clearance is checked at every animation frame and additional
joint-range combinations. Visibility culling considers those moving states.
The collision companion uses rigid convex pieces, retaining the foundation
openings and separate module wings while filling small lattice apertures.
Render and collision GLB/FBX exports retain the skeleton and all three clips.

Run from `library/`, with Blender 5.2 as specified in `../docs/library/MODELLING.md`:

```powershell
& $blender --background --factory-startup --python models/environments/solar_tower/model.py
& $blender --background --factory-startup --python models/environments/solar_tower/preview.py
& $blender --background --factory-startup --python models/environments/solar_tower/scale_preview.py
& $blender --background --factory-startup --python models/environments/solar_tower/collision.py
& $blender --background --factory-startup --python models/environments/solar_tower/validate.py
& $blender --background --factory-startup --python models/environments/solar_tower/animate.py
```

The previews include service and tracking-limit poses. `scale_preview.py`
loads Tensor's authored body, default head and rig at original scale.
`animate.py` renders the library studio showcase at 1280×720, sequencing
tracking, lowering and raising in a 22.23-second video. `validate.py` factory-imports both formats
for render and collision, verifying counts, bounds, UVs/materials, rigid
weights, bones and sampled animation transforms against the source pivots.
Generated scenes, exports, images, video and reports are ignored by Git.
`-- --draft` is a geometry check without culling, atlas packing or exports.
