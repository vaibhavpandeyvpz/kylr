# Cistern

The [shared architecture dimensions contract](../README.md#door-and-interior-dimensions)
owns current door and inside-height limits. Delivered dimensions and mechanical
travel are recorded in the regenerated `_rig.json`. Run `../verify_dimensions.py` after rebuilding.

Walkable architecture. Metres, front −Y, up +Z, origin at grade
centre. The circular foundation is exactly 15 × 15 m. The asset uses the low circular silhouette, radial roof joints, eight
buttresses, industrial doorway and external pipe skid. Finishes follow the
existing KYLR props: off-white `M_Primary`, grey `M_Secondary`, matte-black
`M_Frame`, stainless `M_Joint`, and cyan `M_Emissive`. There is no glazing.
Optional `SK_ArchitectureRegolith` / `M_Regolith` perimeter dressing is
exported independently, rigidly weighted to Root, and excluded from collision.
Hide or remove that mesh to omit it. See [the shared contract](../README.md).

## Construction and moving interfaces

The walkable maintenance chamber sits above a sealed below-grade reservoir;
buried storage geometry is omitted. Its continuous 100 mm deck, 350 mm wall,
lofted compression crown, roof and eight footing-connected buttresses carry
the building. The wall is a continuous machined shell, without the decorative
tile grid; roof expansion joints retain their geometric relief. The central
inspection cover rests on a machined annular ledge,
with retained fasteners over that ledge. Roof seam bridges, crown clamps and
buttress straps have fasteners on their flat seats.

Two exterior sconce gizmos sit at the centres of the left and right wall bays,
halfway between the adjacent buttresses. Each position has a shallow machined
flat seat across the wall's facet junction, fully supporting the lamp backplate.

The external service plate and complete skid follow the circular perimeter
tangent at −105°, in the clear bay between buttress and doorway. Its pump, return
pipe, instrument and conduit mount on bored clamps, flange seats and retained
glands. No service pad cuts across the pillar. Trimmed interfaces use a
0.2 mm manufacturing allowance; moving faceted bearings have radial sweep
clearance. Mounts are kept inside their flat supporting lands.

Both front and rear clear entrances are 1.5 m wide × 2.1 m high. A 600 mm approach rises 77.78 mm,
meeting the internal deck without a raised threshold. The internal ceiling is
2.411 m above grade, giving 2.333 m clear headroom. Each door swings outward on
three interleaved bored hinges, retained through-pins and a coaxial geared
drive. The locking rod runs in an enclosed internal bore without breaking
either door face. The pull and return pipe use constant-radius sections with
parallel-transport frames to prevent twist or pinched transitions.
Allow approximately 2 m clear approach space outside the foundation
for the door sweep; the 15 m diameter describes the fixed building.

Front and rear entrances each have their own retained hinges, geared drive,
lock, landing collar and ramp. `open_front` / `close_front` and
`open_rear` / `close_rear` are independent 96-frame actions at 30 fps.
Only the selected door and lock have tracks, preserving the opposite pose.
Legacy `open` / `close` control the front; `open_both` / `close_both` control
both entrances. A captive shoot bolt retracts 180 mm before each leaf swings
outward to 110°. Closing seats the leaf before extending its bolt.
Rigid weights are 1.0 to one bone: Root, Door, Lock, RearDoor, RearLock.
No idle motion is added to stationary machinery.

Four ceiling batten and three wall-sconce gizmos seat on actual interior
surfaces with local +Z into the room. No interior fixtures or runtime lights
are authored. The north wall mount is clear of the rear opening.

## Verification

Regenerate from `model.py`, run the asset validators and collision checks,
perform fresh GLB/FBX round trips, and inspect the native previews.
The generated rig metadata records delivered dimensions, budgets,
materials, attachment frames and animation clips.

## Regeneration

Run from `library/` with Blender 5.2, `--background --factory-startup --python`:

1. `models/architecture/cistern/model.py`.
2. `models/architecture/cistern/collision.py`.
3. `models/architecture/cistern/validate.py`.
4. `models/architecture/cistern/preview.py`.
5. `models/architecture/cistern/inspection.py`.
6. `models/architecture/cistern/scale_check.py`, then repeat with `-- --rear`.
7. `models/architecture/cistern/animate.py`.

`scale_check.py` reads the actual Tensor and existing idle/rifle walk/run
clips, tests both headings and three lateral lanes against render and
collision geometry, and renders Tensor at the entrance without rescaling him.
