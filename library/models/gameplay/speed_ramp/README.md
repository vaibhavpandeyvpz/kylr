# Speed ramp

Powered launch cartridge: **1 × 1.5 × 0.75 m** (length Y × width X × height Z).
The origin is centred on its base at ground Z = 0. The entire render assembly,
belts, integral housing feet and solid collision companion are above ground, with no
mounting cutout or underground machinery. A uniform 0.5 delivery scale is baked
into meshes, rest bones, animation translations and placement metadata; object
scales remain one. The incline is solved from the exact requested envelope.

## Construction and appearance

The ramp stands directly on its integral off-white housing feet. There is no
perimeter rim or separate metal platform. The grey slab in previews represents
the ground and is excluded from runtime exports and authored bounds.

Two 43 cm reinforced elastomer tread lanes wrap the entry and launch drums.
Each moulded traction rib shares vertices with its carrier; there are no separate
floating pad meshes or duplicate buried contact faces. The carriers bend in the
gaps between the rigid rib stations. Stainless slider beds support the straight
runs, while transverse bulkheads sit below the return belts. A formed stainless
centre spine continues around the launch drum as a single nose guard, with
boolean-cut directional inlays.

The off-white side armour is lofted through changing shoulder sections, not an
assembly of overlapping blocks. Both sides have equally spaced horizontal vent
cuts, a rectangular service bay, protected gland-ended power looms with bolted
clips, and recessed continuous green rail lenses. The protected looms sit near
the housing feet, below the service panels with a clear gap. The service covers
align beside the vent banks with a 4 cm gap. The four evenly spaced vent slots
share the service pocket’s top and bottom edges on both sides. Cover knuckles pivot on
retained pins supported by two housing lugs. Motor caps and mounting anchors have
real counterbores for their flush fasteners. Bearing pedestals are boolean-unioned
before their common coaxial bore is machined.

The materials are the existing jump pad/Tensor slots: `M_Primary` off-white paint,
`M_Secondary` grey paint, `M_Frame` matte black, `M_Joint` stainless steel, and
`M_Emissive` green. No cyan/yellow palette is introduced.

The common keyed shaft couples both tread lanes. Coaxial torque-motor cartridges
drive the launch drum; the other drum is an idler. The controller is housed behind
the hinged service panel. Hidden motor internals are deliberately omitted.
The steel beds also serve as electromagnetic hold-down shoes: switched preload
on compatible metal robot soles supplies the normal force needed for the short,
high-acceleration run, then releases at the launch tangent. Ordinary rubber grip
alone would not provide that acceleration over this distance. Cosmetic tread motion is separate from the game's launch impulse and collision rules.

## Rig and motion

`RIG_SpeedRamp` has `Root`, `Drive`, `Idler`, two service-cover hinges, and
24 tread stations per lane: **53 bones**. Every vertex has exactly one unit-weight
influence. Steel parts and moulded ribs stay rigid; the carrier faces between
stations flex. The baked station matrices follow one closed tangent racetrack;
both drums rotate by travelled distance divided by pitch radius. Its perimeter
equals five drum circumferences, so a full circuit closes both the belt and rotor
poses exactly. There are no engine-dependent drivers or constraints in exports.

Clips use dense 480 fps keys for fast wrap motion; the showcase plays at 30 fps:

| Clip | Duration | Behaviour |
| --- | --- | --- |
| `convey` | 3.2 s, looping | One complete belt circuit; five drum revolutions. |
| `launch` | 1.933 s | Three circuits with smooth acceleration/braking; returns to the same phase. |
| `service_open` | 1 s | Both retained-pin covers open outward 35°; belts stopped. |
| `service_close` | 1 s | Covers return to their recessed seats; belts stopped. |

The launch clip's nominal peak tread speed is about 6.34 m/s. With 9.81 m/s²
gravity, the authored release angle/height and no slip, the calculated range
is recorded in `speed_ramp_rig.json`. This is an illustrative asset calculation;
runtime traction, impulse and cooldown remain future integration work.
`LaunchOrigin` is fixed at the straight run's tangent release point. Opening a
cover requires the drive stopped; the exported maintenance clips enforce that.

## Collision companion

`speed_ramp_col.glb/.fbx` uses the same skeleton and clips:

- `SK_SpeedRampCol`: low-poly convex islands for the straight riding plane,
  wrapped ends, side envelopes, front bulkhead, integral housing feet and hinged covers.
  Belt/rib motion uses a stable smooth Root collider to avoid catching robot feet.
  Cosmetic vents and inaccessible service openings are bridged.
- `SK_SpeedRampTrigger`: a **separate named mesh**, one closed convex inclined
  area spanning the straight riding runs, from 4 mm below to 6.5 cm above them.
  It is Root-weighted and is an area detector, not a solid blocker.

## Build and validation

Run from `library/`, using the Blender 5.2 executable specified in `AGENTS.md`:

```powershell
& $blender --background --factory-startup --python models/gameplay/speed_ramp/model.py
& $blender --background --factory-startup --python models/gameplay/speed_ramp/preview.py
& $blender --background --factory-startup --python models/gameplay/speed_ramp/collision.py
& $blender --background --factory-startup --python models/gameplay/speed_ramp/validate.py
& $blender --background --factory-startup --python models/gameplay/speed_ramp/animate.py
```

`model.py -- --draft` builds a provisional review scene without visibility culling
or exports; it is not a delivery. `--animations-only` rebakes a previously built
mesh when only clip timing changes. The normal build always regenerates everything.
The source checks contacts, bored bearing alignment, retained-pin hinges, the
authored bounds, cover travel, a full drum rotation and 97 belt phases. Only the ground-contact underside is removed analytically; the housing feet remain; the remaining frame uses
the shared room-visibility pass, with conservative occluders inside the carrier's
opaque straight runs. Every carrier face is visible as it circulates around the
track, so it is retained. `validate.py` checks evaluated frame/belt separation,
coplanar seams, GLB/FBX round trips, weights, materials, UV bounds, loop closure,
cover travel and closed/outward/convex collider islands.

Generated blends, exports, rig JSON, atlases, previews and the showcase are ignored.
The Python scripts remain the editable source. Final counts and results live in
`speed_ramp_rig.json` and `speed_ramp_validation.json` after the validated build.

Regenerated counts, exact above-ground bounds and fresh import results are
recorded in `speed_ramp_rig.json` and `speed_ramp_validation.json`.
