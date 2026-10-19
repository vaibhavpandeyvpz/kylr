# Double-ended long cargo container

The [shared architecture dimensions contract](../README.md#door-and-interior-dimensions)
owns current door and inside-height limits. Delivered dimensions and mechanical
travel are recorded in the regenerated `_rig.json`. Run `../verify_dimensions.py` after rebuilding.

Sibling of [`container`](../container/README.md), sharing its
scripted construction, Tensor materials, connected mechanics, corrected
horizontal pulls and fully recessed lock receivers.

External structural envelope: **2.2595 m wide × 6.058 m deep × 2.4388 m high**,
following 20-foot container proportions.
Metres; origin at floor centre, front -Y, up +Z. The opposite doorway faces +Y.
Tensor is 1.753 m tall; `scale_preview.py` loads his original authored mesh
and rig at unmodified scale. Front and rear apertures have the same 2.0 m
structural width, 2.1 m height and 0.1694 m sill as the short container.

Both ends have twin lofted cargo leaves, three retained pin hinges per leaf,
opposing 65.89 mm captive shoot bolts, guided actuator rods and bored receivers.
Each reinforced crossmember carries a two-foot horizontal pull with 168 mm
free grip and 65.89 mm hand clearance, clear of the bolt actuators. Each fixed
end jamb has a recessed status diffuser and supported power conduit. Internal
power transfer through the header and upper hinge is enclosed.

The rig has thirteen rigid bones. The front bones use the short container's
names; the rear bones prefix those names with `Rear`. Rear geometry is an exact
half-turn of the front assembly, with the corresponding pivots and axes.
All rendered vertices have one normalized influence. The four exported
meshes—Structure, FormedShell, FrontDoors and RearDoors—share this one skeleton, with a
5,000-triangle cap enforced separately on each mesh.

Four event clips, each 96 frames / 3.2 seconds at 30 fps:

- `front_open`, `front_close`: operate the front leaves and their locks.
- `rear_open`, `rear_close`: operate the rear leaves and their locks.

Each clip withdraws the bolts before the leaves move, or seats the leaves
before the bolts engage. Each end is independently operable; clips key only
that end's channels. The showcase opens the front, opens the rear, closes the
rear and closes the front, while the camera makes a full circuit of the prop.
No continuous mechanical idle animation is appropriate for a parked container.

The collision companion uses convex slabs around the hollow cargo passage and
independent rigid pieces for the four leaves and eight sliding bolts. It
retains both open ends, filling small fold reliefs and sealed mechanical
interiors. It carries the same skeleton and clips, within 500 triangles.

`model.py` configures the shared editable generator at `../container/model.py`.
The generator checks solid intersections, connectivity, FK transforms, every
animation frame, independent door sweeps, visibility and coplanar faces before
UV preparation and native exports. `validate.py` verifies fresh render and
collision GLB/FBX imports, including sampled animated transforms.

Run from `library/`, using the executable in `../docs/library/MODELLING.md`:

```powershell
& $blender --background --factory-startup --python models/architecture/container_long/model.py
& $blender --background --factory-startup --python models/architecture/container_long/preview.py
& $blender --background --factory-startup --python models/architecture/container_long/scale_preview.py
& $blender --background --factory-startup --python models/architecture/container_long/collision.py
& $blender --background --factory-startup --python models/architecture/container_long/model.py -- --exports-only
& $blender --background --factory-startup --python models/architecture/container_long/validate.py
& $blender --background --factory-startup --python models/architecture/container_long/animate.py
```

Generated exports, scenes, previews, video and reports remain ignored.

The `--exports-only` step preserves every sampled FBX key after the generic
collider export, keeping the stationary bolt-release interval exact.

Verified delivery: 8,745 render triangles total—Structure 4,436, FormedShell
1,019, FrontDoors 1,668 and RearDoors 1,622—and 192 collider triangles.
Static solid intersections, connectivity, 520 animated/sweep states, coplanar
faces, five material atlases and render/collision GLB/FBX round trips pass.
Both clips per end retain their sampled transforms after export. Previews
include both end profiles, the open passage and an authored Tensor comparison.
The 1280×720, 30 fps showcase is 15.43 seconds; all 463 frames decode.
