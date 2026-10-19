# Energy core

Energy cell with a **25 cm chamfered hollow cube** and **5 mm walls**.
The cube is 25% opaque blue; it has no nested layers or illuminated border cages.
The origin remains at the centre for the existing pickup socket convention.

The independent corner cups project **5 mm outside the cube faces**. Filled versions of their
outer envelopes are Boolean-subtracted from the solid cube blank to form the
seats; only afterwards is an offset cavity cut to produce the 5 mm walls.
The supports are not cut from the cube profile. The lower cups are unioned
with a plain 15 mm base. Their chamfers are applied before union, avoiding
inside fillets protruding into the glass. Filled seat cutters include a 0.5 mm
fitting clearance. Complete-solid intersection audits enforce zero glass/support
overlap in the native build and fresh GLB/FBX imports. The complete
hardware envelope is **26 × 26 × 26 cm**, including the outward supports.

The solid 3D bolt is a taller, bold lightning silhouette with pointed ends
and exactly balanced upper/lower halves (180-degree symmetry). It measures
13 cm wide × 19 cm high × 3.64 cm deep. There is no flattened or widened cap.
The cube material has no emission; runtime shaders own the energy
surface effects. Preview bloom demonstrates the bolt material only.

`RIG_EnergyCore` retains `Outer` and `Inner`. Each vertex has one unit-weight
influence. The whole housing spins on Outer while the symbol counter-rotates
on Inner. Both rotate horizontally about Blender +Z (Godot +Y): Outer turns
+360° and Inner −360° per cycle. `spin` is a continuous linear, five-second loop
at 24 fps (frames 1–121); the base stays underneath throughout the turn.
The resting dimensions describe the cube aligned to its axes; its rotation
has a larger swept envelope. The symbol's swept sphere clears the cavity
by approximately 22 mm. There is no solid collider companion.

Run from library using the Blender 5.2 executable in AGENTS.md:

```powershell
& $blender --background --factory-startup --python models/gameplay/energy_core/model.py
& $blender --background --factory-startup --python models/gameplay/energy_core/preview.py
& $blender --background --factory-startup --python models/gameplay/energy_core/validate.py
& $blender --background --factory-startup --python models/gameplay/energy_core/animate.py
```

The editable source is `cube.py`; it reuses shared core skinning, export and
animation utilities. The Shield Core uses this same cube generator, replacing
only the inner symbol and blue material colours with a shield and green. Validation
fresh-imports GLB and FBX and checks exact bounds, closed outward solids, UVs,
rigid weights, two bones, actual spin motion and loop closure. The source also
checks analytic symbol clearance throughout every relative rotation.
Generated exports, native files, UV atlases, previews and videos are ignored.
