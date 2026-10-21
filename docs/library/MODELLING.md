# Scripted Modelling Workflow

Every asset in this library is **built by a Python script run in headless Blender**. Nothing is modelled by hand in the Blender UI. The scripts are the source of truth. `.blend`, `.glb`, `.fbx`, `_rig.json` and `.png` files are build outputs: they are gitignored and can always be regenerated.

Target engine: **Godot 4**, which uses the `.glb` files. The FBX files are written alongside as a fallback and for other tools.

Maps reuse the native platform and bridge builders under `models/maps/common/`.
Keep their authored materials and UVs when machining map-specific apertures.
Map-only lunar terrain and integral mounting pads use the materials defined by
the map generator. Embedded textures and material roles are recorded in the
export metadata. Geometry changes rebuild collision companions. See
[Skyfall's authoring contract](../../library/models/maps/skyfall/README.md) for the current
standalone lunar map, native socket placement, and map-owned triangle accounting.

## Layout

### Robot energy surface

Robot protection and hit feedback use a runtime overlay on the native animated mesh, displaced 5 cm along its normals. No separate shield export or collision companion is required. The robot rig, geometry and animations are the contour source. The shared shader and visual lifecycle are owned by [weapon effects](../WEAPON_EFFECTS.md).

```
models/
  <category>/                 # characters/, weapons/, gameplay/ (the props the game's rules drive: the item table,
                              # weapon holder, pressure plate, barricade, jump pad, spawn point, portal gate, CTF flag,
                              # repair station), environments/ (the thruster and jumbotron), ...
    <name>/                   # lowercase, folder name == asset name
      model.py                # builds the asset -> .blend, .glb/.fbx, _rig.json
      preview.py              # renders the .blend -> <name>_*.png (model-agnostic)
      animate.py              # showcase video -> <name>_showcase.mp4 (model-agnostic): a prop's own actions;
                              # Tensor's: the animation library's showreel; each weapon's: _showcase.mp4 (alone,
                              # turning once round), _held.mp4 (held through its clips), _fps.mp4 (from his eye)
      <name>.blend            # generated
      <name>.glb / .fbx       # generated: third-person / main mesh
      <name>_ammo.blend/.glb/.fbx # generated (weapons): the detachable pack as its own model (square to its own
                              # axes, its real size): hung on the weapon's AmmoMount gizmo; the ammo pickup
      <name>_rocket.glb/.fbx  # generated (projectile weapons): the projectile on its own rig
      collision.py            # (weapons) builds the colliders from the .blend -> <name>_col.glb/.fbx (same skeleton),
                              # <name>_ammo_col / <name>_rocket_col (separate, as their models are), <name>_col_*.png
      <name>_rig.json         # generated: joints, limits, mechanical constraints, animations
      <name>_*.png            # generated previews
```

## Running

Use Blender **5.2 LTS**. Add its executable directory to PATH so `blender`
resolves to that version. Python orchestration tools also accept
`BLENDER_EXECUTABLE`; set it locally when Blender is installed elsewhere.
Keep machine-specific configuration outside source control.

Run asset commands from `library/`, with `--background --factory-startup`:

```powershell
$blender = (Get-Command blender -ErrorAction Stop).Source
& $blender --background --factory-startup --python models/characters/tensor/model.py
& $blender --background --factory-startup --python models/characters/tensor/preview.py
& $blender --background --factory-startup --python animations/retarget.py                # the animation library
& $blender --background --factory-startup --python models/characters/tensor/animate.py   # its showreel
```

```
animations/
  source/                     # Mixamo downloads (the inputs): loose FBX files and three packs (zips)
  retarget.py                 # retargets them onto Tensor and each weapon -> target/
  showreel.py                 # the showreels (Tensor's and the weapons' animate.py use it)
  target/                     # generated (gitignored): tensor/<group>/<clip>.glb, weapons/<weapon>/<clip>.glb,
                              # blend/ (each baked action, for the showreels), manifest.json
```

- `--factory-startup` ignores the user's preferences and add-ons, so every build is reproducible.
- Don't use the Microsoft Store build of Blender. Its launcher swallows stdout and exit codes, so a broken script looks like it succeeded.
- A run has succeeded when the exit code is 0, there is no `Traceback` or `Warning` in the output, and the script's own `[<name>] ...` lines are printed. model.py prints the triangle counts and the piston strokes.

## Material UV atlases and complete regeneration

Every rendered model, including the Energy and Shield Cores, retains its native
material assignments and finishes. `models/material_uv.py` unwraps and packs one
unique 0..1 layout per used material at 2048px, across all parts in an exported
asset. Ammo packs and the rocket get their own layouts. Tensor's shared body, six upper bodies and five
head variants share its eleven original material atlases. Emission, transparency, geometry, normals,
rigs, skinning and existing actions remain unchanged by UV preparation.

Construction seams and curved openings define charts. Planar panels use exact
projection. Exceptional folded boolean faces get isolated charts; rigid chart
packing handles n-gons which the native triangle packer distorts. Validation
checks finite 0..1 coordinates, non-degenerate rendered triangles and overlapping
triangle interiors at 2048px. The gutter is 0.004 UV units, approximately eight
pixels. Generated `<stem>_uv_<material>.png` masks and
`<stem>_uv_<material>_wireframe.png` checker guides stay beside their generators.

Portal fields, exhaust linings, display screens, marquee/ribbon boards, flag
cloth, core spheres/symbols and the repair shield preserve their analytic runtime
UV0. Their unique
painting layouts use the second UV layer, `MaterialAtlas`; map painting layouts also use `MaterialAtlas` on UV1, while their primary UV0
is `TiledSurface` for repeating PBR textures. Other surfaces use UV0. The UV guides show the painting layer. Materials still use their authored
runtime shader coordinates until a shader explicitly opts into UV1.

Full `model.py` builds prepare UVs before exporting. To regenerate only UVs on an
existing validated procedural build, standard generators and maps support
`-- --uv-only`; this checks unchanged geometry, normals, skin weights and effect
UV0, then runs native exports and GLB/FBX round trips. The two cores run their
small full generators and `validate.py`. Geometry-independent UV changes do not
require retargeting unchanged skeletons or animation clips.

Architecture walls and mechanical panels use authored flat PBR paint/metal finishes.
Use flat paint/metal finishes on these surfaces. Keep
intentional image textures such as the canonical regolith PBR set and screens.
UV painting layouts, glass, emission and material classifiers remain intact.

Map landscapes use the [planetary terrain pipeline](PLANETARY_TERRAIN.md):
Terrain3D bakes source height fields before Blender machining, closed-volume
collision export and painting UV validation. Runtime landscape materials blend
six original packed PBR layers; platforms and architecture retain canonical regolith.

Every exported regolith apron uses `architecture/lunar_material.py`, including
the bunker and shelter, which construct their perimeter meshes directly. A
preview-only procedural dust shader is insufficient for the delivered GLB.
`tools/handoff_lunar_materials.py` shares the three canonical game textures and
compacts obsolete images, texture entries and samplers without changing geometry,
skinning, placement, UVs or animation. Repeated compaction is idempotent.
Run `.venv/Scripts/python.exe tools/audit_game_handoff.py --report <fresh-report.json>`
to check all bundled model exports against their native counterparts, the shared
texture hashes, flat architectural/weapon finishes and missing/unused texture
bindings. This read-only audit does not replace native round trips, rendered
previews or Godot import and appearance checks.

`tools/rebuild_library.py` records the Blender executable hash, the versioned
source/input snapshot (including shared helpers and textures), imported native
asset hashes, and fresh output hashes. A resumed job is reused only when its
source snapshot, dependencies and recorded outputs still match. Receipts require matching source, dependency and output fields. These input/output checks complement
the model validators and rendered review; they do not establish visual quality.

Weapons export their authored flat PBR finishes through `models/weapon_materials.py`.
The shared export boundary removes finish image maps and restores the source
`MATERIALS` colors, metallic strengths and roughness. Glass and emissive effect
materials retain their authored behavior. Keep mechanical animation baking and
all UV layers; neither is texture baking. To refresh an existing validated weapon
without rebuilding geometry, run Blender with
`--python models/weapon_materials.py -- pistol` (substitute the weapon folder).
This checks unchanged geometry, normals, skin weights, UV layers, rig and clip
names, plus GLB and FBX round trips. Material role aliases are restored to their
source names for game paint and effect consumers.

```powershell
& $blender --background --factory-startup --python models/weapons/pistol/model.py -- --uv-only
& ./.venv/Scripts/python.exe models/regenerate.py --stage all
```

`regenerate.py` runs complete previews and showcases, including each weapon's
showcase, held and first-person videos. UV-only changes retain the existing
colliders; use `--stage colliders` explicitly after geometry changes.
It uses `models/nvidia_render.py`: NVIDIA OptiX (CUDA fallback) for Cycles,
GPU Eevee for previews/videos, and persistent render data. GPU jobs run serially
to fit laptop VRAM. Map image-sequence encoding uses NVIDIA
NVENC when its probe succeeds, with software H.264 fallback. Use `--stage previews` or
`showcases` for individual render passes. Use optional
`--only <asset names>` for a focused rerun. Logs and status reports live in the
ignored `target/regeneration/` folder. The cores have a ten-second showcase of
their authored counter-rotating `spin` animation and camera turntable.

## Conventions

| Topic | Rule |
|---|---|
| Units | 1 Blender unit = 1 metre. Metric, `scale_length = 1.0` |
| Facing | The character faces **-Y** (Blender "front"). Up is +Z. The character's left side is +X |
| Origin | At the feet, at the world origin. The mesh stands on z = 0 |
| Budget | ≤ 15,000 triangles per exported mesh (body), and ≤ 2,500 per swappable head variant. model.py fails the build if a mesh is over |
| Style | Sculpted hard surface: armour is lofted shells (`loft`, `zloft`, `axis_loft` through faceted sections) carved with exact booleans (`carve`: fairings fused in first with `union=`, so a shroud and its pods are one shell, then cylinder, box and prism cuts, the insides taking `M_Frame`), over rigid mechanics of chamfered boxes and 6–14-sided cylinders; sharp edges above 40°. Keep a shell's lines straight between its sections and centre every detail on the flat it sits on. Mounts, lugs, pads and supports sit wholly on a flat, never on a chamfer or half in the air, and nothing overlaps coplanar with another part (z-fighting) |
| Object names | `SK_<Name>` for skinned meshes, `RIG_<Name>` for the armature, `CAM_*` and `LGT_*` for preview-only objects |
| Bone names | Godot `SkeletonProfileHumanoid` names (`Hips`, `LeftUpperArm`, `RightIndexDistal`, …). Extra mechanical bones use the same `Left`/`Right` prefix |
| Paths | Always relative to the script: `HERE = Path(__file__).resolve().parent`. Never depend on the current working directory |

## Character design: rigid mechanical rig

Robots are built from **rigid parts**, not a deforming skin:

- **One spec is the source of truth.** Joint positions, bone chains and rotation limits live in tables at the top of `model.py` (`J`, `BONE_SPECS`, `FINGERS`, `PISTON_SPECS`). The mesh and the rig are both generated from them, so they can't drift apart.
- **Rigid skinning.** Every part is weighted 1.0 to exactly one bone, so there is 1 influence per vertex and nothing stretches. All parts still end up in a single skinned mesh.
- **Model the left side only.** Author the left side at +X. The kit mirrors parts (`mirror=True`) and bones (`Left*` → `Right*`) automatically.
- **Hinge axes are explicit.** Each bone has a `flex` direction, which is where its tip moves for +X rotation. The bone roll is set so that local X is the hinge axis. Mechanical hinges (knee, finger segments) are `hinge(lo, hi)`: X is limited, Y and Z are locked. The elbow is a hinge followed by the forearm's roll (see the stages below). Blender enforces the limits with `LIMIT_ROTATION` constraints.
- **Mirrored limits.** Mirroring flips the sense of rotation about local Y and Z, and `mirror_limits` handles that. Test poses are written for the left side and mirrored the same way.
- **Pistons** are two deform bones:
  - the barrel sits on the parent (end A) and the rod on the child (end B);
  - each aims (`DAMPED_TRACK`) at a non-deform anchor bone at the other end, which avoids a dependency cycle;
  - model.py sweeps the child joint through its X limits to find the stroke, and sizes the barrel and rod so the rod never leaves the barrel. If the mounts are wrong, the build fails.
- **Actuators must be mechanically valid across the full range. The build enforces this:**
  - `check_piston_clearance()` sweeps each piston's joint through its X limits. The build fails if the piston line crosses, or comes within `PISTON_MIN_ARM` of, the hinge axis. It also fails if the piston passes through any solid part (box or cylinder) of the parent bone or of the moving chain.
  - `check_bar_clearance()` sweeps the hinges in `BAR_CHECK_JOINTS`. It fails if a guard bar or roll cage on one side of a joint hits a part or bar on the other side.
  - `check_connectivity()` compares the exact part meshes. Every part must touch the rest of its own bone, so it forms one rigid piece: nothing floats. Every bone must touch its parent: hub in yoke, barrel eye on its mount pin, rod eye on its horn. Every rod must sit in its barrel, and both ends of every bar must sit on a structural surface of the same bone, square to it, on a flange. Between those ends, a bar must stand clear of its own body along its whole length. Long runs are held off the armour by standoff posts (`solid=False`). Failures report the `build_*` source line.
  - Degenerate geometry is rejected. `obox` raises if its `up` vector is parallel to its length, and any part with zero thickness fails the build. A collapsed part is invisible in renders and can fool the checks.
  - `check_joint_alignment()` covers every single-axis joint (hinges, the neck yaw shaft, and the primary axes of the ankle and thumb base). The moving bone needs a rotor cylinder that is coaxial with the real axis and centred on the pivot. The joint's axis must pass through a part of the parent, such as a bearing, yoke or knuckle fork.
  - `check_motion_clearance()` sweeps the hinges. No part of the moving chain may hit a part of the parent that it doesn't already touch at rest. Thick links limit how far a joint can fold, so the limits are the ranges this geometry actually allows: elbow 0..140° (deepened from 120 so a shouldered weapon's forend is in his other hand's reach) with the forearm's roll ±90°, knee 0..105°, ankle pitch −30..40° and roll ±15°, hip flex −30..100° (see the envelopes), and upper arm swing −60..80°, raise −95..55°, the clavicle's shrug ±5° (its motor in the chest's socket; `check_clavicle_clearance`). Change the geometry, not the check. The waist's stages are swept together by `check_waist_clearance`.
  - Piston eyes turn on pins parallel to the driven hinge axis, because the linkage moves in the hinge's plane. The moving link must fit inside its yoke: the forearm has a slim tongue, and the top of the shin is narrower than the knee yoke. Nothing may sit in the fold zone near a joint.
  - Machined parts built with `prism()`/`plate()` have no box or cylinder collision volume. Actuator clearance tests them against their exact mesh (`Part.hits`, ray parity), so boolean-cut bodies can't be missed.
  - Mounts, lugs and crank horns are `solid=False`, because pistons are meant to touch them.
  - **Crank rule:** a single linear actuator across a wide hinge (elbow, knee) has to drive a crank horn that sits outside the joint's own yoke: on an axle stub above the elbow yoke, or outboard of the knee bearing. At the elbow the horn is a wishbone lever: an A-frame plate bolted flat on the saddle block over the roll housing, carried by the axle boss, with a lightening cut-out and a square pad under the rod-end pin (wider than the rod eye, so the eye lands on a flat, never on a point). The crank rides the elbow's hinge stage, so the forearm's roll never moves the piston. The piston lies on the upper arm's top face. The horn's rest direction balances the moment arm over the range (it bisects the range when the piston's line runs through the pivot; the elbow's barrel sits a centimetre off the arm's axis, so its horn is turned 1.5° further), so the moment arm never changes sign and stays over `PISTON_MIN_ARM` at both ends; the barrel is anchored far enough back for its stroke (`PISTON_MIN_OVERLAP`). Each eye turns on its pin just above its mount: the elbow barrel's on a pedestal out of the upper arm's top flat, the rod's on the crank's pad (a mount block cut through the eye). A piston in the hinge plane in front of or behind the joint will pass through it somewhere in the range. Don't "fix" that by shrinking the check.
  - Every accessory must have a job and be anchored on the one rigid part it belongs to. Examples: bearing caps centred on their joint axis, bolts at plate corners, guard bars with both ends on the same bone. Nothing decorative may cross a joint.
- **Multi-axis joints are serial rotary stages whose axes meet at the pivot.** The stages are helper bones listed in `MECH_STAGES`, driven by constraints from the humanoid bones. Animations only drive the humanoid bones. `MECH_PARENT` records the physical load path for the checks, and `_rig.json` `mech_stages` (plus `markers`) tells Godot how to rebuild the drivers:
  - **Shoulder**: pitch (lateral axis, a motor on the clavicle), then roll (fore-aft, a hub between the pitch stage's ears), then twist (a rotor in the roll housing). Pitch is a Locked Track and roll a Damped Track on the arm's tip.
  - **Hip**: a Cardan joint under a yaw motor. Yaw (vertical motor on the hip beam) carries a fork, the fork's bosses hold the spider's fore-aft roll arms, and the thigh knuckle turns on the spider's lateral pitch arms. A non-deform marker bone (`LeftHipAxis`) on the thigh's pitch axis drives both stages: yaw is a Locked Track (lock Y, track X; `TRACK_NEGATIVE_X` on the right) and roll is a Damped Track. This is exact for any thigh orientation.
  - **Ankle**: a Cardan cross. The pitch hub turns in the shin's yoke and carries level fore-aft roll stubs. The foot's clevis bosses grip the stubs, and its cheeks are rooted in the foot plates. The Foot bone is horizontal (ankle to a point straight ahead), so the roll axis is square to the hub and parallel to the sole. The pitch stage is a Locked Track (lock X) on the foot's tip. Its Euler order is `YXZ` (`ROT_ORDER`, and `euler_order` in `_rig.json`), so the Foot's X and Y channels are exactly pitch and roll.
  - **Elbow**: hinge, then the forearm's roll. The hinge stage (`LeftElbowHinge`, a child of the upper arm) carries the hub in the yoke, the axle and crank, the tongue, and a round roll housing with a saddle block sunk into its top, out on the tongue 11–14 cm from the pivot; the upper arm tapers to the yoke and its end is as tall as the yoke and nearly square, so the yoke's lugs come out of it flush (they sat on its outside) and the forearm folds to 140° clear of it. The forearm starts at a stainless steel rotor turning against the housing's face, the same pattern as the wrist rotator in the forearm's wrist housing. The stage is a Locked Track (lock X) on the forearm's tip, and `HINGE_STAGES` maps it to the LowerArm hinge it turns with. The LowerArm's Euler order is `YXZ`, so its X and Y channels are exactly hinge and roll. `check_motion_clearance` sweeps hinge × roll with the stage and forearm as separate groups against the upper arm, and `check_piston_clearance` samples the roll for the parts that roll. The roll gives the arm the forearm rotation a human has: without it, turning the palm up needs the shoulder twist and the wrist twist both at their stops, so a palm-up support hand under a rifle forend was unreachable.
  - The sweeps resolve every stage exactly as the constraints do. A verification script in the live rig must show 0° error between each stage axis and the joint axis it carries.
- **Coupled limits (`LIMIT_ENVELOPES`).** A box limit per axis lets extreme combinations meet, for example full hip flexion plus full abduction driving the knuckle into the fork. The box stays as the hull, and the real workspace is a union of boxes: for the hip, straddle up to 75° near neutral flexion, 40° abduction up to 60° flexion, and deep flexion (to 100°) with the legs close. The hip sweep samples every envelope box, and every stage group is checked against the others as well as against the pelvis. `_rig.json` exports them as `limit_envelopes_deg`, and animation or IK must stay inside them (animate.py and `check_poses` enforce this).
- **Bars end on flanges.** Every guard bar or roll cage ends exactly on a structural surface, with its end segment square to that surface. A bar's sharp bends (over 45 degrees) are rounded a little (no pointy corners on handles and hooks): `tube()` turns each in two half-steps; hoses (free curves) and the roll cage (gentle bends) skip it. `tube()` adds a flange foot there, and the check enforces it. Bar sections are carried round bends with a minimal rotation and true mitres, so they don't twist.
- **Upper body.** The chest is one keeled shield (`CHEST`, `chest_half`): a sternum ridge and pectoral facets in front, flat flanks, a chamfered back, wide at the shoulders and narrowing to the waist (a man's chest, 0.31 m across). Round sockets in its flanks seat the shoulders' pitch motors (with cooling fins) and give the clavicle its shrug; a well in its top takes the neck; a recessed hexagonal intake with slanted louvres, a unit-number plate in `M_Secondary` and slanted vents centred on each flank under its socket are cut into it; a recess in its underside takes the abdomen's cup and the chest's ball joint. The shoulder's front corner and pectoral break stay inside the arm's forward sweep (the check found them). A neck collar (`COLLAR`, user: the original model's) rises out of the shoulders' top in a half circle round the back of the neck (side to side, a true half circle from above), fused into the shield: full height but for its last fifth each side, where it eases flush into the top, its inner face clear of the head hydraulics' swing at full yaw; the lamp pods' fairings sink into the shoulders just before its ends. The floodlights are round pods on the shoulders' tops, half out of the shield and fused into it (`LAMP`, `LAMP_FAIRING`: lofted from a full round at the lens, shrinking and sinking back into the shoulder; user: one smooth unibody, like a lofted shroud), a stainless steel bezel and a lit lens on each. On its back a lofted power pack (heat-sink grooves, a grab handle whose bar carries the `FlagMount` gizmo, two bolts wholly on its back flat, clear of its edges) with two bearing caps (titanium, bronze) on its top inboard of the power trunks, which curve from the pack's top into the chest's back. The roll cage (`M_Secondary`) springs from flanges square on the upper pectoral facets, runs down them on standoffs, inboard of the arms' forward swing, and loops before the waist. The waist is exposed mechanics: a stainless steel spine column with titanium vertebra discs, the abdomen block on the Chest bone (plain), and the two rear struts.
- **Pelvis, waist and legs.** The pelvis is a lofted girdle, plain (no grooves, slots or vents on it), over open bays: under it, each hip's yaw motor (matte black) sits in a bay, and a bay over the crotch keel, so a flexed thigh rises into them (shorten the hip supports; the bays let the thigh start 9 cm under the hip pivot instead of 11, found by bisection with the sweeps, the keel limiting it). The bays break through the girdle's bottom band, so every face of its cuts is `M_Primary` too (`inner=PRI`). Its back is chamfered from z 1.02, clear of the struts. The crotch keel is a plain lofted codpiece. The hip's Cardan (yaw fork, spider, knuckle) is matte black with titanium bosses. The waist is two ball-jointed stages with two rear struts, close behind the body; each strut end is a rod-end housing on a spherical bearing, pinned between the cheeks of a clevis lug (`strut_lug`: two cheeks tapering from a flat to a round end centred on the pin, a web between them), the lower one on the girdle's back face, the upper one on the abdomen's upper back flat. A strut must stroke both stages' full limits (`chain_poses`), so it can't be shorter than about 0.2 m this close to the spine (the barrel and rod must still overlap at full extension); `check_waist_clearance` sweeps the three stages together over every corner of their limit boxes against each other and the pelvis. The thighs are lofted shells centred on the hip axis, keeled in front (five slanted vents cut across the keel's ridge with a screw on its facets at each corner, user: no plate; a grab handle across the upper front), slanted vents centred over a recess on the outer side, looms down the back. Each thigh's outer side swells up toward the hip in a rounded hump like a kneecap (`HUMP`, fused in with `union=`, user), outboard of the knuckle's outer cheek; the thigh knuckle is a titanium boss on each spider pitch arm, on a matte black cheek down into the shell, each boss 2 mm proud of its cheek so no faces are coplanar. The knee is a clevis of two lug plates (straight sides running tangent into a round end on the axis, `KNEE_R`), inside the thigh's section; the knee hub turns between their inner faces and its crank axle runs out through the titanium bearing on the outer lug into the horn, whose square pad carries the piston's rod eye. The shin is a closed lofted armour boot (no windowed frames, springs or stray lines): a knee block between the lugs on the boot's top, a keeled front with a stripe, the front rising on past the boot's top into the kneecap, close under the thigh (one shell fused with `union=`, user), with two screws near its top, four slanted vents and a grab handle down it above the stripe, a centred access hatch with vents under it on the outer side, and a calf that swells below the knee (slim under it, so it clears the lugs and the thigh at full flexion) with a channel carved down its back where the ankle actuator runs, its upper rod end on a pin through the channel's cheeks (an Achilles drive). The toe hinge is a knuckle hinge in the open between the instep armour and the toe cap (`TOE_HINGE`, user: not buried): the foot base stops short of it and two lugs carry the foot's outer knuckles, the toe's titanium centre knuckle turns between them on a web from the toe cap, and a steel pin runs through all three, its ends showing. Gaps at every joint are the least the sweeps allow.
- **Cables and hydraulic lines (`hose()`).** A run never spans a joint. It stays on one rigid part: it leaves a face square through a gland (the tube's flange foot), runs free in a curve (a cubic with a sag and a bulge, not a straight metal bar), and dives back in square at the other end, as if routed on through the hollow joint. The bar rules (square ends on a surface, clear of the body in between) and every joint sweep apply to them. Place runs where a segment stays open when its joint folds: the back of the upper arm and forearm, the back of the thigh. Looms are `M_Wire` (copper) and hydraulic lines `M_Hose` (yellow), fixed colours. Current runs: power trunks from the pack into the chest, a loom and a line from the neck's base collar into its column, and a loom and a line along each upper arm and thigh (the forearms have none: their gauntlets are too short since the roll housing moved out on the tongue; user).
- **Neck and head variants (`HEAD_VARIANTS`).** The neck (the previous model's assembly) is a yaw shaft on its bearing deep in the chest's well: a conical bearing boot at the well's mouth, a stainless steel clamp ring on it (the base collar), a cable collar higher up, and a short pitch yoke on the shaft's top, two cheeks holding the head's axle. A copper loom and a yellow line leave glands on the base collar and curve up into the column's back facets under the cable collar. The head hydraulics have a clevis at each end (`clevis`: two cheeks, the pin visibly through them), the lower ones on the boot, the upper ones under the mount plate. Players choose a head. Each head is its own skinned mesh (`SK_<Name>Head<Variant>`), built on `head_mount()`: the pitch axle between the yoke's cheeks, a saddle up into the mount plate, the hydraulics' upper clevises; every head sits on the plate (its underside at z 1.636), nothing above 1.753 m. The default head runs the full check suite; every other one is checked on the neck and upper body. Every detail sits wholly on a flat, clear of the chamfers . Current variants: projector (default: a wide sensor box, a perforated grille over a lit array), sentinel (a low housing with twin lens barrels), porthole (a tall rounded helm with one round eye, a slot pair either side spaced evenly between the eye and the face's edges), raptor (a swept faceted cranium with a crest seated in its crown, sensor canisters centred on its side flats), arachne (a cluster of lens barrels, their backs sunk into the housing). The projector, sentinel and porthole carry a bolted hatch recessed in the crown (`crown_hatch`, user). The user removed a visor helm.
- **Lossless triangle optimisation (`Kit.optimise()`, run after the checks, before each mesh is built).** It culls every face that can never be seen: the whole face, nudged 0.2 mm outward, lies inside one other part of the same bone. That covers cylinder caps sunk into hubs, box bottoms seated on plates, tube glands pressed on surfaces and coincident faces between touching parts. Parts of one bone never move apart, so these stay hidden in every pose and animation. A face only covered by another bone's part at rest is kept, because it can show when the joint moves. For a convex covering part the test is exact: all the face's vertices inside it put the whole face inside it. For a non-convex part, dense edge samples must all be inside it too. A union of several parts never counts, since gaps between them could show through. Sampling a face only near its centre is wrong: it once removed the floodlight's thin cooling-fin rims. Across a single-axis joint (`rotary_joints`), a face is also culled when it lies wholly inside a coaxial true cylinder of the other bone, within its inscribed radius and length, such as an axle in its bearing: turning about that axis keeps it covered at every angle. Culling must never change shading. A face is kept if it contributes to a kept neighbour's smooth vertex normal, that is, if an edge between them is neither flat nor harder than `SHARP_ANGLE`. Without that rule, culling a buried side of a smooth cylinder visibly reshades its exposed neighbours. The pass also dissolves collinear or coplanar leftovers of boolean cuts. It was verified by pixel-diffing un-optimised and optimised builds over 40 views, at rest and in crouch, straddle, wide and fully bent poses. About 9% comes off the body.
- **Budget tricks.** Parts under 1 cm radius (bolts, pins, knuckles) go 4-sided on the third-person body, parts under 2 cm skip bevels there, and each boolean cut can set its own side count.
- **Servos and rotors** are split: the housing belongs to the parent bone and the rotor face to the child bone, so the rotor visibly turns with the joint.
- **Collision models (`collision.py`, the weapons', unchanged; `collision_extras.py`):** `tensor_col.glb/.fbx` on his own skeleton. The body is convex pieces on his humanoid bones only (`COLLISION_BONES`: each finger joins its hand and each toe its foot, each mechanical stage the limb it turns; the pistons and struts get none, `NO_COLLIDER`: they aim, so a piece joined to a limb stuck out of it in a crouch; the game drives only the humanoid bones). His rig has no actions (his clips are the animation library's), so the motion tests sample his preview poses. The user asked for 2 cm, 1,500 triangles and 100 pieces, which can't all hold (2 cm took about 4,200 triangles in 170 pieces; 1,500 / 100 about 5 cm), and chose the middle ground: 3.5 cm, about 2,200 triangles and 120 pieces. Each head variant is one fitted hull on the `Head` bone (`SK_TensorHead<Variant>Col`: the game takes the one he wears; one shape per head shot).

### Materials (team colours)

Every character uses the same eleven slots, in the same order (the weapons' materials):

| Slot | Use |
|---|---|
| `M_Primary` | The armour shells, one colour all over (no black undersides). Off-white by default ; **team colour 1** in play: a military paint |
| `M_Secondary` | Roll cage, grab handles, piston barrels, number plate, stripes, crests, hatches. Grey by default; **team colour 2** in play: a military accent contrasting with the primary |
| `M_Frame` | Matte black (the metallic black looked weird): chassis, yokes, forks, lugs, the insides of every cut |
| `M_Joint` | Stainless steel: rods, pins, axles, hubs, rotor faces, a face mask |
| `M_Emissive` | Sensors and lamps |
| `M_Wire` | Power and signal looms: copper. Fixed, never team-coloured |
| `M_Hose` | Hydraulic lines: industrial yellow. Fixed, never team-coloured |
| `M_Titanium` | Matte titanium: motors, bearing housings, bosses, kneecaps, hatches |
| `M_Bronze` | Bearing caps, bushings |
| `M_Alu` | Brushed aluminium: damper bodies, piston glands |
| `M_Black` | Matte black rubber: soles |

Tensor exports all eleven original material slots above, preserving their face
assignments, flat PBR colours, metallic values and roughness. No finishes are
combined into `M_Other`, and no baked finish textures are required.
`model.py` calls the shared `models/material_uv.py` to mark construction seams, open curved patches,
unwrap, equalise island scale, and pack one independent unique 0..1 layout per
material, including emissive. Each layout spans the body and all alternative
heads and upper bodies without overlapping one another. Packing uses a 0.004 UV margin (about
eight pixels at 2048px). Emissive colour and strength stay unchanged.
Generated `tensor_uv_<material>.png` and
`tensor_uv_<material>_wireframe.png` files show all eleven 2048px layouts for
texture authoring (`<material>` is the lowercase slot name without `M_`).
The build checks UV bounds, non-degenerate rendered triangles, and overlapping
triangle interiors at atlas resolution before exporting. Tensor has no
separate FPS arm mesh; the game uses its body in first-person view.
Teams swap only `M_Primary` and `M_Secondary`. The default (the `MATERIALS` values,
what the previews and the showcase show) is off-white with a grey accent .
The team variants live in `TEAM_COLORS`, military shades only : green with
coyote tan, red with desert sand, yellow with military blue, blue with military
yellow and are exported as `team_presets` in `_rig.json`. In Godot, give each team
duplicated `M_Primary` and `M_Secondary` material overrides on the mesh surfaces.

### `<name>_rig.json`

Neither GLB nor FBX can carry Blender constraints, so the mechanics are exported as data for the engine to rebuild:

- `bones[]` lists each bone's head, tail, parent, `flex_axis`, `limits_deg` per local axis, `euler_order`, and `limit_envelopes_deg` where limits are coupled.
- `mech_stages[]` and `markers[]` describe the helper stage bones and their constraint drivers.
- `pistons[]` lists `cylinder`/`rod` bone names, their parents, which bone each aims at (the other one's origin), the stroke, and the barrel and rod lengths.
- Coordinates are in Blender space. In glTF/Godot a point becomes `(x, z, -y)`.

A Godot `SkeletonModifier3D` (or a small script) should, every frame, aim each piston bone at the other's global origin, and clamp joints to their limits if gameplay needs that.

## `model.py` contract

1. `reset_scene()` calls `bpy.ops.wm.read_factory_settings(use_empty=True)`, then sets metric units. Start from nothing, every time.
2. Build the materials, resolve the spec (bones, pistons), and build the rig.
3. Build meshes with the `Kit` helpers (`obox`, `box`, `cyl`, `tube`, `prism` for flat profiles, and `plate` for plates with boolean-cut openings such as wishbones), with one `build_<region>()` function per body region.
4. Run the clearance checks, then skin, unwrap, and check the triangle budget.
5. Export GLB and FBX from the selected objects only, and write `<name>_rig.json`.
6. Write the preview metadata, then save `<name>.blend` with `preferences.filepaths.save_version = 0`, so no `.blend1` backups are left behind.

Use `bpy.data` / `bmesh` for geometry. Keep `bpy.ops` calls in the setup and teardown steps, because operators depend on context.

### Export settings

```
FBX:  global_scale=1.0, apply_unit_scale=True, apply_scale_options="FBX_SCALE_ALL"
      axis_forward="-Z", axis_up="Y", bake_space_transform=False
      use_mesh_modifiers=False, mesh_smooth_type="OFF" (authored split normals)
      add_leaf_bones=False, primary_bone_axis="Y", secondary_bone_axis="X"
      use_armature_deform_only=True, bake_anim=False, path_mode="COPY", embed_textures=True
GLB:  export_format="GLB", use_selection=True, export_yup=True, export_skins=True
      export_def_bones=True, export_animations=False, export_materials="EXPORT"
```

Only deform bones are exported, so the anchor bones stay in Blender. Change these settings for all assets at once, not per asset, unless the asset documents why it is different.

## `preview.py` contract

`preview.py` is **model-agnostic**. It takes the name from the folder name, so you can copy it unchanged into a new asset folder.

- It opens `<name>.blend` and exits with an error if the file is missing. It never saves the file.
- It frames the evaluated (posed) vertices of all renderable meshes, with a 12% margin.
- It re-aims a sun rig (key, fill, rim and a kick from the other side) per camera, so every view is lit from the front.
- It renders in a studio (`build_studio`; user: the old grey background mixed with the models and hid the stainless steel): the camera sees a near-white sweep, so dark paints and matte black read against it, while lighting and reflections see a studio of grey walls, a darker floor, a bright strip light round the horizon and a softbox overhead, so stainless steel reads silver with crisp highlights instead of mirroring black. Eevee's ray tracing is on and the view transform is AgX, look Punchy. Every asset's `preview.py` has the same studio.
- It renders with Eevee, picking `BLENDER_EEVEE_NEXT` when that engine exists and `BLENDER_EEVEE` otherwise.

| View | Camera direction from subject | Projection | Resolution |
|---|---|---|---|
| `top` | +Z | ortho | 1024² |
| `bottom` | −Z | ortho | 1024² |
| `right` | −X | ortho | 1024² |
| `left` | +X | ortho | 1024² |
| `front` | −Y | ortho | 1024² |
| `back` | +Y | ortho | 1024² |
| `front_left` | (+1, −1, 0.35) | 70 mm persp | 1920×1080 |
| `rear_right` | (−1, +1, 0.35) | 70 mm persp | 1920×1080 |

View names are the model's own sides: it faces −Y, so its left is +X and `left` is seen from +X (Blender's viewport names are the other way round, and a weapon's `left` preview showed its right side). The exports agree: in glTF / Godot every asset faces +Z (`MODEL_FRONT`) with its left on +X (`MODEL_LEFT`), and the clips' root motion goes the same way (`walk_forward` +Z, `walk_left` +X).

It also renders these extra images, from the `front_left` camera, when model.py leaves the metadata:
- `armature["preview_poses"]` (JSON `{pose: {bone: {"rot": [x,y,z] deg, "loc": [...]}}}`) produces `<name>_pose_<pose>.png`. Test poses exercise the joint limits, the pistons and the finger curl. `check_poses` fails the build if a pose leaves its limits or envelopes. Standing poses must keep the feet on the floor, so take leg angles from animate.py's IK.
- `armature["preview_pose_views"]` (JSON `{pose: [view, ...]}`) renders that pose from each listed view as `<name>_pose_<pose>_<view>.png`. The straddle is standard from `front`, `back`, `front_left` and `rear_right`. A pose entry may also carry `"scale": [x, y, z]` (the repair station's shield grows by its bone's scale).
- `armature["preview_pose_show"]` (JSON `{pose: [object, ...]}`, the props' preview.py) shows those objects, hidden from every other render, in that pose's renders: the repair station's stand-in Tensor and its shield. The props' `animate.py` shows the objects in `scene["preview_show"]` in the showcase.
- `scene["preview_team_colors"]` (JSON `{team: {material: [r,g,b]}}`) produces `<name>_team_<team>.png`.
- `scene["preview_variants"]` (JSON `{slot: {"default", "objects": {variant: mesh}}}`) renders each variant of a swappable slot on its own: `<name>_<slot>_<variant>.png` (a 3/4 close-up framed on it), `_side.png` (profile) and `_full.png` (the whole character). Tensor has five heads and six upper bodies.
- `scene["preview_frame"]` (JSON `{"lo": [x,y,z], "hi": [x,y,z]}`) frames every view on that box instead of on all renderable meshes. Props set into a floor or wall use it to frame the part the player sees, with the preview-only floor or wall slab around them.
- `scene["preview_solo"]` (JSON `{tag: {"objects": [mesh, ...], "pose": {bone: {"rot": ...}}, "views": [...]}}`, the weapons' preview.py) renders those meshes alone, every other mesh hidden and their armature posed, as `<name>_<tag>_<view>.png`. A projectile is hidden from the other renders (`hide_render`) and shown this way, folded and deployed.

## Animation library (`animations/`)

Tensor's animations are retargeted from Mixamo downloads, not keyframed by hand (learn natural locomotion from
the sources; discard the hand-found holds and the hand-made showcase). `animations/retarget.py` (after Tensor's and
the weapons' model.py) builds `animations/target`: one GLB per clip for Godot, each holding only the rig (import them
as animation libraries onto Tensor's and each weapon's skeletons), with a `manifest.json` (frames, fps, loop, root
motion, source, the worst hand miss and the lowest point per clip). `-- <group/clip pattern>` limits a run.

- **Sources** (`animations/source`): loose FBX files (idle, falling, the spawn landing, a death, the defeat and
  thirteen victory dances) and three packs: the Pro Rifle Pack (idles, 8-way walk, run, sprint and crouch walk, turns,
  jumps, six deaths), the Basic Shooter Pack (fire, reload, hit reaction, grenade toss) and the Pistol Handgun
  Locomotion Pack (walk, run, strafes and arcs, jumps, kneel). Only the clips of combat with a weapon in hand are
  weapon clips ; the packs' deaths and the grenade toss are Tensor's own (`tensor/common`), without a weapon. Mixamo's rest is a T-pose as Tensor's is, its hips 1.4 cm
  higher and shoulders 2.5 cm.
- **Retarget.** Each Mixamo bone's world rotation change from its rest goes onto Tensor's humanoid bone, top-down, then
  is clamped to the bone's limits in its Euler order (and the hips' coupled envelopes); a clamped parent's lost rotation
  passes to its child (the neck's pitch to the head, a knee's twist to the foot). The mechanical stages, bearings,
  struts and pistons follow through their constraints and are baked with everything else.
- **Root motion.** The hips' travel, scaled by leg length (so strides fit Tensor's legs), goes on the Root bone: linear
  over a loop, smoothed over a one-shot, and turns carry their yaw; the hips keep the rest.
- **Feet and the floor.** Upright (the torso within 60° of vertical, `UPRIGHT`: a crouch or a squat too), a foot low and still in the retargeted motion is
  planted: held flat where it landed while each leg is solved onto it (hip 3, knee 1, ankle 2, within their limits),
  easing in and out over 3 frames; where a sole would go below the floor, the hips lift. The floor is Tensor's whole
  shell (`body_points`: each bone's extreme vertices of SK_Tensor): lying or sitting on the ground the hips lift only
  as far as the shell above the knees needs (his chest is deeper than the actor's), then a shin or foot still in the
  floor folds out of it (the ankle and toes within their limits, then the leg, `fold_feet`; lying is judged by the torso,
  not the hips' height, which a crouching turn or a dance's squat also brings under 0.5 m); the lift is smoothed
  and never less than a frame needs. (User: a corpse rose off the ground as it settled, lifted 0.3 m by a pointed toe
  through the floor, when only the soles counted.)
- **Weapon families.** The rifle family (rifle, EMP gun, lightning gun, rocket launcher) and the heavy family
  (minigun, flamethrower) take the Pro Rifle Pack's motions, the pistol its own pack (its strafes and arcs named by
  where they go) and the rifle motions it lacks. Every weapon gets every movement of combat with it in hand.
- **Where each weapon sits** (weapons are carried at the right side of the body, the left hand only the support;
  and they were held too low; then: the rocket launcher's hold, aim and positions are gold, make every weapon the
  same). In its family's aiming idle each weapon is level, pointing where Tensor faces. Every long gun takes the
  rocket launcher's hold (`HOLDS`, `REFERENCE`): its firing wrist exactly where the rocket launcher's is (its centreline
  10 cm right of his chest's middle, the wrist 22 cm ahead of his right shoulder joint and 5 cm below it), so the firing
  arm, the aim, the fire and the body motion are the same for every one and only the support hand goes to each gun's
  own grip; the pistol keeps its own pack's hold (held out at arm's length, a little right of his middle). What made
  that possible: his elbow (it folded only to 120°, so his wrist came no nearer than 28 cm to his shoulder and a
  raised weapon's forend was out of his other hand's reach: the user had it deepened to 140°), his chest (a deep
  shield: a stock has to sit well ahead of the shoulder joint; the rifle's and the EMP gun's stocks were shortened)
  and the grips' spacing (the rifle's support grip moved from its handguard back onto its magwell). Earlier the families
  were placed under the actor's hands (9, 14 and 19 cm lower, the minigun and flamethrower at the hip); that ran the
  weapons down his middle, even left of it, their grips under the shoulder on a hanging arm, and the stocks through
  his chest.
- **Holding.** Each weapon is calibrated in its family's aiming idle (`calibrate`): level and straight ahead in the
  firing hand, then moved to its place. The firing arm reaches for that placement, and the weapon hangs from wherever
  the firing hand lands (weapon = RightHand × RightHandSocket⁻¹, exactly as the game attaches it). The support hand goes
  exactly onto its socket, position and turn (LeftHandSocket; user: the sockets are the grips and the animation plugs
  into them, so the holds are deterministic instead of reworked clip by clip), within `TOL_HAND` (3 mm) and `TOL_TURN`
  (3°). It stays on in every clip (the hands stick to their sockets; it had let go wherever the actor's hands
  parted, in sprints, turns and jumps); only a reload lets it go (while the source's hand is off its two-handed grip),
  the ammo socket taking over. The aiming idle is first held by walking the weapon in steps from the actor's hand to
  its place (`seat`), each step from the one before; that pose is the holds' start (from the actor's arm the solver
  stuck short of a raised weapon).
- **Arms never go through a weapon** (an arm ran through a weapon; the hands were exactly on their sockets
  whichever way round the arm went). The solver works locally, so where an arm misses its socket from the actor's arm
  and the frame before, or reaches it through the weapon, it starts again from a global search (`arm_starts`: the
  elbow's and the wrist's joints sampled within their limits, the upper arm's turn solved for the hand's, the nearest
  wrists kept). Each candidate is scored by its hand's miss and its arm's depth in the weapon (`arm_clash`: the upper
  arm and the forearm as capsules round their bones against the weapon's vertices, the wrist's last 6 cm left out;
  `CLASH_TOL` 4 mm, `CLASH_W`); the manifest records each clip's deepest arm (`arm_clash_m`).
- **The chest and the head face front** with a weapon in hand (chest, head and weapon always look front; only
  looking up and down may turn them, back and forth, never left or right). The source's rifle stance is bladed (hips
  and chest turned about 50°): `face_front` takes the upper chest's turn and side roll from the facing to nothing with
  the spine's twist and side bend (its lean kept), and the head's with the neck's turn (its nod kept); where the hips
  turn further than the spine's 60° can take back (a strafe, a sprint), the hips turn the rest and the feet are
  planted again (`squared`). The aiming idle the families are calibrated in is squared the same way, and the helpers
  that move the torso only lean it (`TORSO_DOFS`: pitch). The chest ends within 4° of front, the head within 0.3°.
- **The weapon points straight where Tensor faces** (in runs and sprints it swung sideways with the actor's rifle;
  then, no turn, roll or pitch at all while it's held, in any clip). Its grip follows the source's hand (or the chest,
  below) but its frame is exactly the Root's facing (`aligned`); only an aim pose pitches it, about Tensor's own
  sideways axis (the facing's, not the bladed chest's, which tilted it sideways), never turning or rolling it. The firing hand is solved for the weapon's turn as firmly as
  its place (`AIM_W`), from the aiming idle's arms as well as the source's (`seed`), and where it can't, the torso and
  both arms help; the manifest records how far each clip's weapon ends up turned (`aim_miss_deg`) and which hold it
  took (`hold`). Each clip is held three ways and the best kept (the hands' and the weapon's misses, a degree of the
  weapon's turn counting as 5 mm, the weapon straight above all, and a reload's pack): from the source's hand (`native`, first, kept whenever it is exact so the source's own weapon motion stays),
  or riding the upper chest as in the aiming idle, pointing where Tensor faces, its place turned with the facing
  (`chest_facing`) or its grip kept where the aiming idle has it on the chest (`chest`). The chest holds carry the
  fire, hit-reaction and most reload clips, whose actor (the Basic Shooter Pack's) holds the rifle unlike the aiming
  idle's (from the hand the weapon ended up turned 18–27°); a sprint carries the rifle across the chest, so it takes
  only the chest holds. On a chest hold a reload first puts the source's free hand against the weapon as it was
  against the weapon held from the source's hand (`free_hand_on_weapon`), so it reaches this weapon's pack.
  So a socket has to be where Tensor's arm reaches: a support socket is fitted over its family's stance clips (a
  search over its roll round the grip, its turn about the palm and its slide along the grip, scoring the exact miss),
  and the palm check keeps it on the grip. The minigun's and the rocket launcher's side grips are taken turned 35° and
  32° round their axis, wrapping them from the front (`LGRIP_ROLL`: exact from +30° to +40°, 73–88 mm off unturned);
  the flamethrower's side grip was placed by the same fit (its position along the left flank and its height, then
  its roll, 48°, at the hip carry it had then); the rifles' and the pistol's forend sockets land exactly as modelled. A
  fit can also show that no socket on a grip works: the flamethrower's first grip, a bail on top, missed by 110–130 mm
  at every roll, turn and carry position tried, and the only reachable hold, from under the bar, sank into the body. A forward pass solves each frame from the one before, a backward pass
  retries a miss from the frame after, a lone miss is retried from its neighbours, and a hand still off its grip gets
  the torso's twists and lean and the firing arm to help (`TwoHandIK`, the torso kept near the source's). The fingers
  close to the weapon's grip poses.
- **Aim poses** (the weapon, and the head with it, points at the crosshair as the player looks up and down;
  the game turns the whole player to look left and right). Each weapon gets `aim_<pitch>` poses (`AIM_PITCH`: −45° to
  +45° every 15°, `aim_down45` … `aim_level` … `aim_up45`; user: 45° is as far as the game aims) from its aiming idle: the chest leans `AIM_CHEST_SHARE` (10 %)
  of the pitch and the arms raise or lower the weapon about the shoulders for the rest, the clavicles, shoulders,
  elbows and wrists solved with both hands back on it; the head nods to keep the eyes on the line of fire. Each way is
  solved as a ramp from level in `AIM_STEP` (5°) steps, each from the one before, so every pose is reached smoothly.
  In Godot they blend additively (an AnimationTree BlendSpace1D, base `aim_level`) on the upper body over any movement,
  driven by the aim's pitch; the pistons and bearings are baked into each pose.
- **Reload.** The support hand takes the ammo pack by its socket (`AmmoHandSocket`, riding the pack): the pack runs
  out of its well (`mag_release`) and the hand eases onto the socket over `AMMO_EASE` (6) frames where the source's
  hand, off its grip, first passes closest; the pack rides the hand exactly (pack = hand × socket⁻¹); the hand eases
  back onto the socket where the released pack goes in (the source hand's last close pass), pushes it home
  (`mag_insert`'s travel, retimed to end before the source's hand moves on to the charging handle; the upper body holds
  still meanwhile, then eases back into the source's motion) and lets go. The grab is taken on the frame near the
  source hand's first pass where the arm lands on the pack. Where the arm alone can't reach the socket, the torso and
  the firing arm help (`TwoHandIK`). Held where he aims it, no weapon's pack was within his left hand's reach (31
  to 133 mm off). Reloads come in two reused variants (one reload, guided by the gizmos): bottom, every pack
  underneath, where the weapon goes into the rocket launcher's reload carry (its firing hand where the rocket
  launcher's is, `reference_carry`, the left hand to this weapon's own AmmoHandSocket, eased off the carry only as far
  as the pack needs), and top (`TOP_RELOAD`: the lightning gun, whose pack is on top). Each has a reload carry (`reload_carry`, solved once in its aiming idle), where the firing hand
  holds it and the left hand takes the released pack exactly, found by both arms and the torso toward guides lowered,
  drawn in and rolled toward the support hand (it rolls 15–50°, as a real reload turns the magazine well to the hand),
  an arm in the weapon or the weapon in his torso (`body_clash`: boxes round his torso's bones) counting against it.
  Through a reload the weapon goes from its chest hold into that carry while the support hand is off (`carry_phase`),
  riding the upper chest wholly so it stays in reach as the chest leans and twists; the hand's path is the actor's
  against his own rifle (`actor_weapon`, `free_hand_on_weapon`), and its solve onto the pack starts from the arm's global
  search too (from the actor's arm it landed turned right round). A reload may turn and tilt the weapon (nothing is shot meanwhile; the hands' accuracy first): it is held six ways, the three above and each blended by the support hand's grip (straight while both hands hold it, as the source's hand has it while the support hand is off: `blend_places`, `off_grip`), the torso may twist and bend sideways to help the hands (`RELOAD_TORSO`), and the pack's miss counts in the choice.
- **The weapon's bones.** Each weapon clip exports the weapon's own clip in sync: its idle through movement, its fire
  loop through a fire clip, and through a reload the pack where the reload has it (on its actions, or in the hand by
  its socket); the Mag bone's rail limit (`LIMIT_LOCATION`, 0 to `MAG_TRAVEL`) is dropped for a
  reload clip and in the showreels, since the pack out of its well is free and the clip places it).
- **Showreels.** Tensor's `animate.py` renders every clip of his (his own clips, then each family's stance clips, no
  weapon shown). Each weapon's `animate.py` renders three videos : `<name>_showcase.mp4`, the weapon on its own
  in the dark studio, the camera orbiting it once right round over the whole video (the lights turning with it) while
  it plays every one of its own actions (`preview_actions` in order, then any it leaves out); `<name>_held.mp4`,
  Tensor holding it through all its library clips, the weapon's bones playing their synced clips; and
  `<name>_fps.mp4`, the animated weapon pinned at bottom right with the character hidden. Pass `-- showcase`, `held` or `fps` to render
  one. The held and FPS reels use `animations/showreel.py`: the clips end to end on an NLA track (short loops twice, the
  last pose held 8 frames between clips), captioned, a static camera at Tensor's front left following the hips (no orbit, so the poses read), in the
  previews' studio, 1280×720 at 30 fps (`-- --no-render` lays the reel out and stops). In Blender 5.x, video output
  needs `image_settings.media_type = "VIDEO"` before `file_format = "FFMPEG"`.

## Architecture dimensions

The shared map [parametric platform builder](../../library/models/maps/common/platform/PLATFORMS.md)
lives in `models/maps/common/platform/`. Pass base dimensions, proposed rectangular
extensions, omitted border spans and an optional underbody. Union extensions into
one casting before laying out a continuous top and perimeter border. There are no
standalone lip or size-specific helpers. Deck thickness is 0.8 m; the optional
tapered chassis extends uniformly 1.5 m below the deck bottom. Preserve native
service bays, fins, doors and closed structural faces. Split delivery meshes to
retain the 5K per-mesh limit; report map-owned castings and machining separately
from imported props and scenery.

Native thruster sockets use the longest base span: below 5 m none, at least 5 m
one central unit, at least 15 m two diagonal units, at least 25 m four corner units.
Use uniform disc-to-belly-edge clearance and reject overlapping configurations.
Fascia sconces and recesses share an evenly spaced plan with 40 cm minimum clear
spacing. Roof battens require supported backplates after machining. Every fixture
is a gizmo import in populated previews and game, hidden in gizmo-only previews.
Seed shallow 1.5–60 mm surface regolith before placement Boolean cuts; cutters
add 1 mm per side and reach 0.5 m above the deck. Export the machined regolith
separately, excluded from map-owned geometry and blocking collision.

The shared map [5×5 m bridge helper](../../library/models/maps/common/bridge/README.md)
joins platform edges across a 5 m gap through `BridgePlug*` and two opposing
`BridgeSocket*` gizmos. Its complete 5K-budget configuration has a closed deck,
optional left/right guard infill and roof. Shared side frames contain the toe
rails and end posts: enable each once when its guard or the roof is selected
(`enabled_if_any` in rig JSON). Each of six render meshes has its own collider.
The clear walkway is at least 4.51 m, guards reach 1.12 m and minimum headroom
is 2.84 m. The roof stacks onto matching-width guard end posts via bolted splice
cheeks and bearing saddles. Bored handrail clamps, captive bolts and underside ties serve structural
functions. Six canted faceted impact shields stand on physical seats over a
closed inner skin, with recessed hold-downs aligned to those seats and protected
centre-seam retainers. Joint details follow
item cradle and Tensor; ornamental belt drives and unconnected services are
omitted. The complete bridge is 4,697 triangles.
The lower roof plate is flat at z=2.84..2.94; taper comes from the raised shields.
`BattenLightMount` at (0,-2.5,2.84) points the authored batten longitudinally
along bridge Y. Its `required_mesh` is the roof; hide the fixture when the roof
is disabled. The gizmo exports in GLB/FBX and the authored lamp is imported in populated previews and runtime.
Two authored sconce gizmos sit centred on the left/right fascia at z=-0.4;
front and rear entrances have none. Actual lamps are imported in populated previews and runtime.
Occupied bridge plugs identify covered fascia lamps in `omit_fixture_mounts`;
skip those fixtures for that connection. Integral extension bridge-facing borders are omitted on the connecting span.
Use `models/maps/common/bridge/build.py` through the project Python venv.

Derive wall/foundation cutouts and ramp widths from the delivered frame,
including its feet. Resizing a door must not leave an earlier wide notch or
unsupported sill-side gaps.

All walkable building props, including cargo `container` and `container_long`,
live in `models/architecture/`. Their shared [delivery contract](../../library/models/architecture/README.md)
owns the dimensions and audit commands.

- Single doors and doorways: at most **1.5 × 2.1 m** (width × height).
- Double doors: normally **2.0 × 2.1 m** for the complete opening.
- Inside rooms, levels and cabins: at most **3.0 m**, floor top to ceiling
  underside. Check the maximum height across sloped/vaulted ceilings and each
  occupied storey independently. Exterior roof equipment does not count.
- Fit the original 1.753 m Tensor and standing game capsule through the usable
  aperture, including chamfers, hinges, handles, thresholds and colliders.
  Open shelter approaches and cargo-lift shafts are not door openings or rooms.
- Dimensions are baked by the source generators into geometry and rigs with
  unit object scales. The shared `dimensions.py` provides authoring frames,
  joint/clip travel conversion and machine-readable delivered dimensions.
  Rebuild collision companions after resizing. `verify_dimensions.py` checks
  actual open apertures and inside surfaces in Blender, GLB and FBX; run the
  existing Tensor traversal audits too. Do not scale Tensor to fit.

## Bastion architecture

The [Bastion](../../library/models/architecture/bastion/README.md) is a
walkable duplex on a metallic foundation within a 15 x 15 m placement envelope.
Its exterior uses broad chamfered corners, continuous braced
panoramic glazing, dark lower armor and a stepped machinery crown. The upper
deck has 150.069 m2 usable area. A rear open 3 x 3 m CargoLift travels 3.191 m;
SK_BastionLiftPlatformTrigger is its separate occupancy area. The compact
1.5 x 2.10 m entrance has a single retained inward-hinged door with a
sequenced locking bolt and a 2 m approach. Its window material is black
at 10% opacity. Full jamb and roof cassette mounting lands are checked against
actual host triangles; wall/window surrounds have one consistent finish.
Interior lighting is supplied as gizmos only. Total render budget is 10,000 triangles including optional
SK_ArchitectureRegolith; each render mesh stays below 5,000. Run model,
collision, both export round trips, single-door/surface audits, Tensor traversal,
previews, inspection and showcase scripts before handoff.

## Lodge architecture

The [Lodge](../../library/models/architecture/lodge/README.md) is a low square
15 x 15 m lunar building, with a continuous pressure shell, formed roof shoulder,
bolted roof equipment and three window bays per side. Each bay contains two
1.30 m wide windows with equal 393.33 mm edge and centre gaps.
Black glazing is 10% opaque. The user requested a continuous roof centre and
smooth shoulder and clean front/rear exterior walls: omit the central plate,
slope ribs and external X gussets with their fasteners. Equipment flange
screws must fit completely between the flange and pod corner chamfers; the
generator checks the full head radius. Interior pressure walls use one finish,
independent of Boolean triangle heights. Two 1.5 x 2.088 m entrances reuse the
cistern's supported hinge/lock cartridge and independent front/rear action
contract. Four ceiling and two wall fixture gizmos are surface-seated; do not
author interior lamps. The 10,000-triangle render ceiling includes optional
SK_ArchitectureRegolith; retain 5,000 triangles per mesh. Run its native-format,
surface, independent-action, mount and Tensor traversal audits, previews,
inspection and showcase before any handoff.

## Hub architecture

The [Hub](../../library/models/architecture/hub/README.md) is a four-way
walkable lunar building within a 6 x 6 m ground envelope. The budget is
10,000 total render triangles including `SK_ArchitectureRegolith`, retaining
5,000 triangles per mesh. Its selected housings are straight and its blast doors
lift vertically in two separate storage lanes, with guided crossheads, hollow
telescopic cylinders and independently rigged sleeves. Front/left/rear/right
open/close actions preserve peer states in both native export formats.

Pocket cutters stay behind the housing chamfers, leaving continuous skins.
Pillar-wall lands and inboard roof ties are fused into the pressure shell.
Side cassette recesses and inserts share their clipped-corner outlines. Shell
paint is uniform across wall/roof junctions; finish regions use whole-face
manufacturing boundaries, rather than Boolean triangle centroid guesses.
Windows are black at 10% opacity; interior lighting uses surface-fitted gizmos
only. Regenerate model, preview, collision, round-trip, traversal/inspection and
showcase scripts before delivery.

## Animated props

The [`satellite/`](../../library/models/environments/satellite/README.md)
is a ground-mounted 2 m parabolic communications dish facing −Y. A rigid
`Root → Elevation` rig drives `track`, `service_raise` and `service_return`.
Its seated feed bipods, rear ribs, retained trunnions and sealed geared drive
use the same lofted-shell framework, with a 5K limit for each of its two
manufactured render assemblies and a 500-triangle collision companion.
Build previews, Tensor scale comparisons, collision companions, both export
round trips and the showcase before a handoff. Its README owns
the dimensions, mechanical construction and regeneration commands.

Props live in two categories : `models/gameplay/` for the ones the game's rules drive (the turrets, switches, barricade, jump pad, spawn point, portal gate, and the CTF flag and repair station under [Gameplay props](#gameplay-props)) and `models/environments/` for the set around the play (the thruster and jumbotron). They share one framework and the rules below.

The static environment luminaires (`batten_light`, `sconce_light`, `pole_light`)
share `models/environments/light_common.py`: lofted castings, recessed emissive
diffusers, seated gaskets, flush indicators and physically connected mounting
hardware. The batten is ceiling-mounted, the sconce wall-mounted, and the
4.189 m pole carries six fixed-aim heads. Each exports its projection gizmo(s),
one fixed Root bone and separate convex collision companions, with no animation
actions or showcase script (no animations). Their mounting origins,
GLB local -Z projection frames, dimensions, regeneration and QA contracts are
documented in [Static industrial lights](../../library/models/environments/LIGHTS.md).
These assets remain until a game handoff is requested.

The animated gameplay prop `models/gameplay/stasis_chamber/` follows the same industrial
solid framework: a lofted pressure enclosure, seated cyan glazing, service
cabinet, retained hinge hardware and connected coolant lines. Its viewing
panel faces −Y; its actual Tensor idle fit, dimensions, generation commands
and validation are documented in [Stasis chamber](../../library/models/gameplay/stasis_chamber/README.md).
Its foundation establishes an exact 1.5 m length Y x 1.25 m width X ground
footprint. It is with a fixed Root and a supported vertical-axis Door hinge.
The complete door opens outward 120 degrees; open/close each last 1.5 seconds.
The collider leaves the cavity open and moves the door on the same clips.

The architecture [`container/`](../../library/models/architecture/container/README.md)
and [`container_long/`](../../library/models/architecture/container_long/README.md)
share a scripted cargo enclosure generator: formed wall/roof sheets, lofted
door leaves, three retained hinges per leaf and opposing captive shoot bolts.
The short body is 2.2595 × 2.991 × 2.4388 m; the long body is 6.058 m deep with
independent doors at both ends. Both face -Y, stand at floor z=0, and use
Tensor's map-generic finishes. Horizontal pulls seat wholly on reinforcement
flats; lock receivers are recessed into the header and sill. The short rig has
`open`/`close`; the long rig has separate front/rear open/close clips. The long
chassis, formed wall/roof skin and two door assemblies are separate meshes on one rig,
each capped at 5K triangles. Build previews, scale comparisons, colliders,
round trips and showcases. After the unchanged generic collider script, run
`model.py -- --exports-only` before validation to retain every FBX sample;
default FBX simplification can drift across the stationary unlock interval.

The [`solar_tower/`](../../library/models/environments/solar_tower/README.md)
is a 3 m tracker facing −Y, with ten photovoltaic modules, manually indexed
panel hinges, a lattice mast and a geared pedestal. Its rigid Root → Azimuth →
Elevation hierarchy exports `track` (8 s loop), `service_lower` and
`service_raise` (6 s each). It retains the 5K render / 500 collider triangle
limits. Run its model, previews, collision, round-trip validator and showcase
scripts before any handoff; the README owns its dimensions and
mechanical/animation contracts.

The Energy Core and Shield Core are separate scripted gameplay props. The
Energy Core is a **0.25 m hollow chamfered blue cube with 5 mm walls**,
authored by `energy_core/model.py` and `energy_core/cube.py`. It has 25% opacity,
independent corner supports projecting 5 mm beyond the cube, a unified lower
support/base casting, and a tall bold solid lightning prism with symmetric pointed ends.
Filled support envelopes are Boolean-subtracted from the solid cube blank;
only then is the cavity cut to form 5 mm walls. Supports are not derived by
cutting the outer cube. Its assembled hardware envelope is
0.26 x 0.26 x 0.26 m. Its origin stays at the centre for pickup sockets.
The complete housing rotates horizontally +360° on `Outer`, with the symbol
counter-rotating −360° on `Inner` about Blender +Z (Godot +Y), continuously
over a five-second loop. Filled seats have 0.5 mm clearance; complete-solid
intersection checks enforce zero glass/support overlap. The symbol clears the
hollow cavity. See
[Energy Core](../../library/models/gameplay/energy_core/README.md). The [Shield Core](../../library/models/gameplay/shield_core/README.md) uses the same
hollow cube, 5 mm walls, fitted supports and base, with green materials and
a solid bilaterally symmetric shield replacing the bolt. Both reuse
`energy_core/cube.py` and retain the same two-bone counter-rotation `spin` clip. Regenerate previews,
showcases and GLB/FBX round-trip validation before a handoff.

The [Energy Core pickup](../../library/models/gameplay/energy_core_pickup/README.md) is
its 10 cm spherical variant: one hollow blue sphere with 5 mm radial walls,
25% opacity, no supports/base and the same solid bolt scaled uniformly to 40%.
The symbol clears the 45 mm cavity radius by 5.64 mm. It retains the same
horizontal counter-rotation clip and centred pickup origin.

The current authored rest envelopes (length Y x width X x height Z, metres) are
owned by `models/gameplay/dimensions.py`: weapon holder 1 x 1 x 2; repair station
2 x 2 x 2; pulse gun 1 x 1 x 0.6; pressure plate 1 x 2 x 0.2; jump pad
1 x 1 x 0.25; item table 1 x 1 x 2; item cradle 1 x 1 x 0.5; barricade
2 x 4 x 1.5; speed ramp 1 x 1.5 x 0.75; energy/shield core assemblies 0.26 x 0.26 x 0.26
(0.25 m cube plus projecting supports); stasis chamber 1.5 x 1.25 x 2.679. Measure render geometry at rest,
including below-floor machinery but excluding preview floors, payloads, triggers
and the repair station's optional shield effect. The speed ramp rests wholly
above ground (Z 0..0.75), while the unpressed pressure plate is flush (Z -0.2..0);
its diamond crowns meet ground and press travel is 5 cm downward. Preserve the
pressure tray's underside so its physical depth survives export and culling.
The item table uses six jack stages and a 0.35 m weapon clearance; the weapon
holder uses eight stages. The shared framework below their spec blocks remains
identical. `verify_dimensions.py` audits natives and fresh GLB/FBX imports.

Asset: [`models/gameplay/item_table/`](../../library/models/gameplay/item_table) (a turret that rises from a floor pit: a spinning drum, a chamfered triangular base 0.1 m off the floor, three slim (3 cm) single-stage hydraulic rams on its corners carrying a round platform whose `ItemMount` is 0.20 m above its surface; retracted the rams are their 0.2 m bodies, extended their rods lift the platform to 0.3 m above the base; no claws) and [`weapon_holder/`](../../library/models/gameplay/weapon_holder) (the same turret with claws, on the floor too since the user asked for it ground up like the item table (the game turns it onto a wall where it needs one; it was authored on a wall), with the same distances: platform 0.1 m off the floor, two 0.25 m arms whose ends are 0.3 m up from it, with claws on their ends either side of the gun, which stands upright, spinning it over the hatch). The two `model.py` files share every line below their `=== SPEC ===` block: change the shared code in one and copy it to the other, keeping each file's docstring and spec. Environment props follow the same rules as characters (scripted, rigid parts on bones, booleans for exact shapes, every mechanism logical and checked), with these differences:

- **Budget:** ≤ 5,000 triangles per exported mesh. Spend them where the player looks: the inside of the pit is barely visible through the hatch, so it is an open box and the centre jack, nothing more. The item table and the weapon holder have no looms or hoses, so they carry five material slots (no `M_Wire` or `M_Hose`); a prop that routes lines adds those slots back and follows the characters' conduit rules.
- **Unseen-face cull (`cull_unseen`, after skinning, before UVs and export).** On top of `Kit.optimise()`, every prop except maps deletes the faces no player can ever see. Maps are exempt at the user's request; their integral mounting geometry and floor-helper instances use the documented map-owned budget without the cull; separately imported props and lunar scenery are excluded. It poses the prop in every state `check_motion` uses (every animation frame and the joint sweeps, so anything a motion or a combination of motions uncovers counts), with the level's surface round the cut-out in the scene. From points over each face (about every 2 cm, and every 1 cm just inside its edges, since a slit shows only an edge strip), rays go out in every direction on both sides (the exported materials are double-sided), plus fans close to the cut-out frame's axes, the only directions a narrow running gap is seen through. A ray shows the face if it reaches air a viewer can be in, however low: it flies off out of the surface, or lands on the level's surface from the room side before meeting the prop. Rays into the ground or the wall show nothing, so the outside of a tray or frame below the floor, and faces sealed inside the mechanism, go. A face that shares a smooth-shaded corner with a seen face stays, so shading never changes. For speed, faces whose own rigid body (plus the level, for the fixed body) blocks every ray are settled once at rest, a hidden face is re-tested only in states where the bodies hiding it have moved relative to it, and the most different poses are tried first. A prop build takes about 1 to 11 minutes. It was verified by pixel-diffing every preview against an unculled build: every view from the room side is unchanged (the only changes are views from under the floor or behind the wall, and 1-pixel edge-on columns in orthographic views). It takes 12–39% off: item table 2,499 → 2,091, weapon holder 3,652 → 3,340 (on the floor), pressure plate 1,262 → 736, barricade 2,382 → 1,788, jump pad 2,404 → 1,944. `Kit.to_object()` no longer recalculates normals after `optimise()`: `optimise()` has already wound every closed part outward, and recalculating flipped open fragments the cull leaves (the jump pad's ring inlay top faced down).
- **Map-generic finish in Tensor's materials, no team colours** (props, weapons and characters in one theme, one world): `M_Primary` Tensor's off-white paint (armour), `M_Secondary` its grey accent (pit liner, piston barrels), `M_Frame` its matte black, `M_Joint` stainless steel (axles, rods, jack stages); `M_Emissive` for the status lights and the frame's light strips. There are no team presets or team renders.
- **Placement:** the origin is where the prop meets the level. For a floor prop, that is the floor surface (z = 0) at the hatch centre, and the pit hangs below. Both turrets are floor props ; `HATCH` could still author one on a wall (the wall surface the XZ plane at y = 0, the room at −Y, the recess into +Y), but the game turns a floor prop instead. Both use the same patch: a 1 × 1 m square frame (no corner chamfer) round a centred 0.5 × 0.9 m hole, and the pit or recess stays inside the patch's footprint, so the frame covers the level's cut. `_rig.json` gives the cut-out (`cutout_m`: patch, hole, depth, and the longest weapon the hole passes). Frames and closed doors sit flush with the surface.
- **Props set into a cut-out have square outside corners. This is a hard rule.** The level cuts a plain rectangular hole, so the prop's outside must be exactly that rectangle in plan: no chamfer or round on any outside corner, and nothing reaching past it. Chamfers and rounds belong only inside (pockets, and the plates or doors that move in them). `check_footprint(kit, lo, hi, levels, frame)` enforces it: in the cut-out's frame, nothing lies outside `lo`..`hi` at rest, and the fixed body has a vertex at each outside corner at every listed level (the surface and the frame's bottom). Every prop's `main` calls it.
- **Hatch and pit, authored once in hatch coordinates** (a = across the hole, b = the long axis, n = out of the surface). `HATCH` maps them to world space, and `Kit.frame()` builds parts in a local frame, including each door's open pose. Each thick side of the frame carries one light strip, centred with the same gap to every edge of that side. The doors are two leaves hinged on the hole's long edges (a hinge joint each, barrels in grooves cut along the edges, bearings in the frame's ends): shut they are flush; open they hang down against the pit's sides. A sliding door can't park inside a 0.25 m side, so hinges are what keep the pit inside the patch. Everything that passes through, the turret included, stays within `PASS_A` of the centre, clear of the hanging doors, and the stroke leaves its top below the doors' swing. The pit is an open grey box inside the patch (`Kit.shell`: five quads, 10 triangles, no top face or chamfer, facing inward), so the inside reads dark through the open hatch. An open shell has no inside for the checks. On its floor stands a telescopic centre jack: a fixed barrel and `JACK_STAGES` (4) nested stages, 8-sided tubes, each sliding `JACK_STEP` in the one below and staying `JACK_OVERLAP` inside it at full reach. The top stage is the carriage the turret spins on, below the hanging doors. The stages are slide joints grouped with the carriage, so the carriage value is one stage's travel and the pit is only as deep as the collapsed jack needs.
- **The turret is authored in hatch coordinates too**, both sides explicitly (`SIDES`: Left/Right on the floor; nothing relies on the kit's X mirror). Its geometry derives from the spec: the claw pivot, pads, hooks and weapon socket follow the nominal weapon and which way it stands (`WEAPON`, `GUN_UP`), and the stroke follows the turret's height. On the item table `WEAPON`'s height is the tallest weapon it takes, 0.5 m: its stroke carries a 0.25 × 0.75 × 0.5 m weapon lying on the platform below the doors' swing (26 mm clear), which makes the pit 1.88 m deep.
- **Joints (`JOINT_SPECS`)** are `hinge` (bone local X = axis, pose `rotation_euler.x` in degrees), `slide` (bone local Y = axis, pose `location.y` in metres) or `fixed`, listed for both sides. Rotation axes mirror as pseudo-vectors, so the same value on both sides gives mirrored motion, and animations key the first side and copy it to the second. The rest pose is the deployed, holding state (doors open, claws closed on the nominal weapon). Door values measure how far a door has closed, and the carriage value is negative going in. The spec picks the head: `ARMS` (moving arms by azimuth, each with its hand and the direction it closes in, built in its own turned frame; the weapon holder) or `RAMS` plus `TOP_PLATE_R` (hydraulic rams under a round platform; the item table), and `BASE_SHAPE` (octagon or chamfered triangle). On both, the base platform is a 6 cm block (`BASE_TOP - DRUM_TOP`) with a 1 cm top chamfer (`BASE_CHAMFER`), one lofted shell (the props in the weapons' unibody language too) that flares from the drum's round section up into the outline over `FLARE_H` (`loft_rings` through the outline resampled every ~6 cm and the same azimuths on a circle inside every face, so the corners sweep down into the drum), with slanted vents centred on its plain faces (`base_outline` returns them: the triangle's corner faces, the octagon's ±b faces). On the item table the rams rise out of pods fused into its top (`POD_R`, `POD_TOP`, `union=`; their bores 1 mm over the ram bodies' so the two don't z-fight) round a deck pocket holding the ready light (`DECK_POCKET_R`); the chamfer's side profiles rise straight up inside the chamfer so they don't trim the pods. The weapon holder keeps its deck plate, which the arms' clevises stand on. The item table's top platform is one lofted shell too: a faceted 24-gon disc with a chamfered lip, its underside stepping in to a flat over the rams (their gland collars meet it retracted), a black field flush in its top and the lit disc under its centre. A ram is a `RAM_D` body `RAM_BODY` long on the turret and a rod on the platform that slides `RAM_RAISE` in it, so retracted only the body shows. The rods and the platform are one slide joint on the turret. Claw animations, the grip table and the claw sweeps exist only when there are arms. Each claw arm is one unibody shell in the weapons' language (like the lofted shells, not boxes arranged together; `build_claw_arm`): its side profile (a knuckle round about the hinge, a pillar tapering up from it, a head turning in along the top to a nose round about the hand axle, the inside corner filleted and the outer one chamfered) extruded across the arm and carved by `carve()` (the props' version: exact booleans through `machine()`, the uncut surface `M_Primary`, the cuts' faces `M_Frame`, every convex outline edge round the `flanks` chamfered, the openings of cuts left sharp). It is tilted by one piston that runs from a lug near the middle of the deck up into a slot in the pillar's inner face (the lug's width), with a long lever about the hinge; the rod eye turns on a pin through the slot's cheeks whose ends show on the flanks. Slanted vents are cut into the middle of the pillar's outer face (it was plain), a through axle turns the knuckle in the deck's clevis, and a bearing ring on each side of the nose marks the claw's axle. The hands are mounted on the arms' ends, outside the arm length. `carve()` triangulates its faces before they become parts: the parts' BVH fans an n-gon, and a concave one (an L-shaped flank, a claw's U-shaped heel) would read as solid across its gap and fail the motion check; `optimise()` merges the flat triangles again. It tells the uncut surface from the cuts' faces exactly (`in_polygon`: the face lies in an original face's plane, facing the same way, and inside its outline), not by a BVH's closest point, which is computed in floats and drifts up to a millimetre on long thin faces: on the barricade it painted the hinge edge's 4 m facets as cut faces, a black strip between two knuckles .
- **Adaptive claws (weapon holder):** the two claws' fingers are interleaved, so they can close past rest (`CLAW_CLOSE`) onto thin weapons and fold open to 105°. `grip_table()` closes each claw from open on the real finger meshes until it meets a weapon box of each width in `GRIP_WIDTHS`, and `_rig.json` exports the angles (`grip`), so the engine closes the claws onto whatever weapon is held; `claw_close` ends at the nominal grip. Each claw is one shell too (`build_claw`): its side profile (a boss round the axle, a finger tapering to a raked tip, a heel) extruded across both fingers, then everything between them cut away but the yoke, an arc bar under the nose concentric with it (`YOKE`, 5 mm clear of the nose at every angle), so the two fingers and the yoke are one piece; stainless steel pads on the fingers' faces. The hands sit on the ends of the arms with their fingers rising beside the weapon; there is no ledge under it (a rising finger would lift a ledge into the weapon as it opens), so the pads always make first contact.
- **Checks:** `check_rig_fk` proves the live rig moves every body exactly as the checks' kinematics do. `check_connectivity` includes the line rules. `check_joint_alignment` checks hinges (coaxial rotor and bearing) and slides: the slider must bear on its guide over the whole travel. `check_piston_clearance` checks every hinge-spanning piston. `check_motion` places every body on every frame of every animation, read back from the real f-curves, and across joint-range sweeps (spin × claw or ram states, the full lift, the doors swinging with the turret down). It fails if a part hits a part of another body it doesn't already touch at rest. `check_footprint` fails the build if an outside corner is chamfered or anything leaves the cut-out (see Placement). `check_coplanar` fails the build on z-fighting: two faces of different pieces of the final mesh lying in the same plane, facing the same way and overlapping (for example a boss exactly as wide as the member it sits on). Offset one of them by a millimetre or two.
- **Animations are part of the asset.** Each action (`ANIMATIONS`: `deploy`, `retract`, the looping `spin`, `raise` / `lower` where there are rams, and `claw_open` / `claw_close` where there are claws; on the item table `deploy` ends by raising the platform and `retract` starts by lowering it) is exported as its own glTF animation and FBX take. Only the channels an action keys are exported, so actions layer (the claws can open mid-spin). Piston rotations are baked into the actions that move them. The rig's constraints are removed for export (the glTF exporter warns on any constraint) and restored afterwards, so the GLB plays exactly as the checks saw it. This is the documented exception to the export settings: `bake_anim=True` and `bake_anim_use_all_actions=True` for FBX, and `export_animations=True` with `ACTIONS` mode for glTF.
- **Previews:** preview-only objects are prefixed `PRV_` and never exported: a 5 cm diamond marker (an octahedron, 8 triangles, standing on the weapon mount, so it moves with the animations) and a floor or wall slab around the frame. The item table and the weapon holder carry no weapon, not even in previews. `PREVIEW_STATES` become `pose_*` renders (retracted, halfway, spinning, raised or claws open), and `preview_frame` frames the views. `animate.py` (the props version) plays the actions in `scene["preview_actions"]` one after another, each holding until the next takes over, with a camera swinging gently round the front. It writes `<name>_showcase.mp4`, and `-- --no-render` only sets it up.
- **Mount gizmos:** the item table exports `ItemMount` 0.15 m above its platform; the weapon holder exports `WeaponMount` between its claws. Each is an empty (an invisible node in game) parented to the `WeaponSocket` bone, whose head is at the same point. Its origin is where the payload's bottom goes (`MOUNT`); the holder's claws close on the weapon's sides symmetrically whatever its thickness. The payload's up points out of the surface (`GUN_UP`). The gizmo's local +Y is forward and +Z is up in Blender, so in glTF / Godot −Z is forward and +Y is up. Godot imports it under a `BoneAttachment3D`, so it follows every animation.
- **Engine:** put the payload on the appropriate mount by its bottom origin. Stop `spin` at 0° before `retract` (both), because it only fits the hatch lengthwise (up to `cutout_m.max_weapon_length`, 0.88 m). On the weapon holder, close the claws to the grip-table angle for the held weapon; on the item table the item hovers above the platform at `ItemMount`.
- **Collision models:** every prop runs the weapons' `collision.py` unchanged (see "Collision models" under Weapons): `<name>_col.glb/.fbx`, convex pieces on its own skeleton with its actions, the portal gate's passage left open. Where the prop's job needs the game to detect a player, `collision_extras.py` adds an area (not a solid) with the engine's helpers, rendered on its own (`_col_<name>_*.png`): `trigger_on_bone` (the convex footprint of a bone's parts, from 1 cm under their top to 10 cm over it, riding the bone) makes `SK_PressurePlateTrigger` (press when the first player enters, release when the last leaves), `SK_JumpPadTrigger` (launch on entry) and `SK_SpawnPointTrigger` (on the lift plate: retract once the spawned player leaves it); `slab` makes `SK_PortalGateFieldTrigger` in place of a collider for the field quad: the field's rectangle 0.5 m through, so a sprinting player can't cross it between two physics frames (teleport on entry, by the side he came from). The thruster has no collider (it is mounted under a platform, which carries the collision). The jumbotron's displays and marquees get none (they lie flush in its body). Two props leave out what is sunk in their cut-out, where nobody reaches: the pressure plate's tray below the plate's travel (`CLIP_BELOW`, −7 cm), and the spawn point's frame and shaft, built as boxes of the surfaces a player can reach (`BONE_OVERRIDE`: the frame's top round the hatch as deep as the housing, the shaft's walls and floor behind their faces, its corner rails), its panels' carriages in the housing's pockets left out; decomposing the housing with its hidden pockets took 1,600 triangles. The barricade's pit is never reached either (lowered, the slab fills it; raised, the slab's foot and the deck cover it): its Root is the frame's rim round the pit's opening, four 5 cm boxes flush with the floor, and its deck one box riding the Deck bone (decomposing the open liner and the notched deck took most of 20 minutes a pass); the slab and the telescopic struts (cylinder, stages, rod) keep their convex pieces. The item table, the weapon holder and the barricade need no area: the weapon on a mount brings its own collider.

The [item cradle](../../library/models/gameplay/item_cradle/README.md) is a
configured exception to the prop render budget: **up to 5,500 triangles**,
enforced by its generator and round-trip validator. Other props retain 5,000.
It is a
freestanding circular pickup fixture facing −Y. Its complete outer footprint
is exactly 1 x 1 m, with cardinal casting ribs reaching +/-0.5 m on X and Y.
Its deck is 0.926 m across and hooked clamp tips are 0.500 m high. Every motion stays inside the 1 x 1 m tile.
Four rigid lofted clamp shells open outward on retained shafts in bored
pedestal clevises, driven by coaxial geared motors. `open` and `close` are
event actions; there is no spinning platform. Its fixed `ItemMount` gizmo
places a payload by its bottom origin, 0.185185 m above the floor. Recessed
service wells, terminated wiring, skirt vents and floor-contacting casting ribs use
Tensor's neutral material palette with cyan status lights. Run its model,
preview, collision, round-trip validator and showcase before a handoff; it is not yet installed in the game.

The [weather sensor](../../library/models/environments/weather_sensor/README.md)
is a 2.5 m freestanding weather station facing −Y. Its pinned tripod supports
a lofted logger enclosure, protected wiring, telemetry dish and weather probes.
Legs and braces have bored eyes, clevis seats and retained pins; crossarm
beams terminate at sockets and bolted pedestal flanges. Inspect its close-up
joint renders as well as the standard previews.
Vertical bearing bones animate the hollow cup anemometer and wind vane through
the looping `measure` and `gust` clips. Run its model, preview, collision,
round-trip validator and showcase scripts before any handoff.

### Pressure plate, barricade, jump pad, spawn point, portal gate, thruster and jumbotron

[`pressure_plate/`](../../library/models/gameplay/pressure_plate) and [`barricade/`](../../library/models/gameplay/barricade) are a switch and the thing it drives: the game plays the plate's `press` / `release` as players step on and off, and toggles the barricade (`raise` / `lower`) on a press. [`jump_pad/`](../../library/models/gameplay/jump_pad) is a launch pad (`launch`). Each `model.py` is its own spec, joints, animations and builders around the item table's and the weapon holder's generic framework (kinematics, pistons, mesh kit, checks, rig, action baking, export), copied from `item_table/model.py`; a function a prop defines itself replaces the framework's. `preview.py` and `animate.py` are the item table's and the weapon holder's too. A fix to the framework goes into all seven props (the portal gate below too, which adds the weapons' tessellated parts and lofts, the thruster, which copies the portal gate's, and the jumbotron, which copies the thruster's, and the CTF flag and the repair station under [Gameplay props](#gameplay-props), which copy the thruster's and the flag's). All six props share the unibody helpers (`machine()`, `carve()` with `union=` fairings and `intersect=` profiles, `loft_rings()`, `prism_bm()`, `fillet()`, `arc_xz()`; user: every prop in the weapons' unibody language), and `Kit.plate` machines through `machine()`.

- **Square outside corners** (the hard rule under Placement), so they fill their cut-outs and sit flush against walls, tiles and each other.
- **Pressure plate** (1 × 2 × 0.2 m (L × W × H)): a metallic-black tray set into a floor cut-out (`cutout_m`: 2 × 1 m, 20 cm deep), one carved block: its rim and tread crowns flush with ground at rest, with a notch in the middle of each long side. The rim's edges stay sharp (a chamfer on the ramp's crest and the pocket's mouth caught the light as whitish outlines). The tread plate is one slide joint (`Plate`, −5 cm = pressed), 1 mm clear of the pocket's walls, one carved piece with its top edges chamfered (`PLATE_BEVEL`): its face is embossed with 5 mm stainless steel diamonds (alternating ±45° like diamond plate) centred on it, and four small lit arrows are inlaid in arrow-shaped pockets cut in from its sides, pointing inward, their faces 1 mm down (`INLAY_DROP`); nothing else is lit. The gas springs' cylinders, their rods and the switch are turned parts, each one piece. Four gas springs carry and guide it (rods on the plate in cylinders on the pocket floor, still 4 cm engaged at rest), and a striker under its centre stops 2 mm above a switch button at full press. `press` takes 4 frames, `release` 7.
- **Barricade** (exact 4 × 2 m complete outer frame/pit footprint): the inset block is 3.890 × 1.873 m and 0.3 m thick. Lowered it lies flush in a pocket; raised it stands 1.773 m tall behind its hinge, its top face now the front. The block is one unibody shell carved from its side profile (`build_slab`), its long edges and ends chamfered (`CHAMFER`); its front carries three armour panels recessed with 45-degree walls and nothing through it (no vents, holes in a barricade's front defeat it). The hinge runs along the front long edge, `HINGE_C` in from the front and top faces, and that edge is rounded about the axis so it turns in place. Three 8-sided knuckles on the frame (their top edge flush with the floor, each on a web from the rail) turn in 16-sided coaxial notches in the edge, on a pin through the block (the rotor); the notch is rotation-invariant, so it clears the knuckle at every angle. The block's back-bottom edge swings back as it starts to rise, so the pocket's back gap is `BACK_GAP`, not `GAP`. The generator solves the inset slab depth from that sweep, both running gaps and both rims, and checks the full moving assembly stays inside the 4 × 2 m footprint. Strut pins and rear load-frame extents are inset with the slab; the resting assembly is 1.5 m deep.
  - **Struts:** two three-stage telescopic hydraulic struts at the block's ends (`STRUT_X`), visible from the sides when it is up and bracing it like a kickstand. Each barrel's eye turns on a cross pin in a slotted clevis on a pedestal in the pit; each rod's eye in a slotted lug under a spine beam on the block's back, the lug fused into the beam (a round-ended web about the pin with 45-degree root gussets); the pedestals are round about their pins too. Both slots open toward the strut over its whole swing, and the pins run through both cheeks, their ends showing. The lever about the hinge stays over 0.5 m throughout.
  - **Load frame on the back, milled out of the block** (unibody, not bars laid on): a raised field (`FRAME_Y`, ±0.85 m along the back, its outer edge chamfered) fused into the block, with pockets cut between the ribs (`frame_bays()`, four filleted triangles round the X in each bay, `POCKET_IN` into the block), leaving the spine beams (just wider than the lugs they carry), ribs and cross beams in a grid of equal bays (`FRAME_GRID`: 4 columns × 2 rows) centred on the back and an X (`BRACE_W`) crossing at each bay's centre, the rib tops the block's paint and the pockets matte black. Any longer and the frame's end would meet the rising deck.
  - **Deck:** under the lowered block, a deck on four hydraulic rams waits `DECK_CLEAR` under its load frame (the struts hold the block). `raise` flips the block up (9 frames) and then lifts the deck flush with the floor behind it (10 more), so there is ground to take cover on; `lower` drops the deck first. The deck is notched at its ends where the struts and lugs pass: `deck_notch()` finds the notch by sweeping each strut's axis and lug through the block's swing (deck down) and the deck's rise (wall up), and `check_rams_clear` proves the struts miss the deck in every motion state.
- **Jump pad** (1 × 1 m, 1,660 triangles): a matte black tray filling a 1 × 1 m cut-out (26.5 cm deep; surviving render envelope 25 cm), its top flush with the floor and its outside a plain box; only the jumper plate in its pocket has chamfered corners. The plate is one unibody shell (the weapons' language), 1 mm clear of the pocket: a block with a chamfered top, hollowed from below into a top slab and a skirt down its sides that stays in the pocket at full lift and guides it (the slide's guide check counts the 1 mm running gap as bearing); slanted breather slots through each side of the skirt, centred on it. Its face has a lit ring (the only lit part) round an off-white disc embossed with stainless steel diamonds. `launch` fires it 15 cm up in 4 frames (easing out), holds 2, and brings it down at half that speed (8 frames, easing in and out; every frame keyed, linear); the game gives the jump impulse on the up-stroke. The pocket is empty: with the skirt round the plate nothing under it is ever seen, so the ram, the four dampers and the scissor linkage (with its coupled joints and `check_scissor`) were removed to save triangles . The plate is the only moving bone.
- **Spawn point** ([`spawn_point/`](../../library/models/gameplay/spawn_point), 2 × 2 m, 1,682 triangles): a spawn lift. A 2 × 2 m matte black frame, flush with the floor and carrying a lit square ring, surrounds a 1 × 1 m hatch over a 1.5 m shaft (grey liner, a lit strip recessed down each wall). The cut-out is stepped: 2 × 2 m down 0.22 m for the housing, then a 1.04 m square shaft to 1.5 m. `check_footprint_tiers` checks square corners at both tiers. `open` → spawn the player on `PlayerMount` → `raise` (or `deploy`, the two in one, with the player spawned at frame 40): the lift plate brings them up 1.2 m to flush. When they step off, `lower` → `close` (or `retract`).
  - **Doors:** four off-white panels, two a side (a 2 × 2 m frame round a 1 × 1 m hole). A single 0.5 m leaf can't park under a 0.5 m side, so the panels telescope. Each side's outer panel drops 23 mm under the frame's 2 cm lip and its inner panel drops 66 mm, under that one. Both then slide out into a pocket under the side, the inner one twice as far (0.51 m), so the two stack. Shut, all four sit flush. Each panel is one carved shell (two top grooves, chamfered top edges) with an end tab fused into its lower band at each end. Each tab reaches through a slit into a carriage slot behind the shaft's ±y walls. There, a carriage (a tubular linear motor's off-white forcer on a stainless steel thrust rod) carries a grey lift cylinder whose rod holds the tab. A panel slides down on its front carriage, and its back carriage moves with it.
  - **Coupled joints (`COUPLED`, `expand()`):** one driver per motion. The left outer front carriage drives the other carriages (the inner ones at a ratio of 2), and the left outer panel's lift drives the other lifts (the inner ones at 66/23). The animations key the drivers, and the followers get the same keys scaled, so their Bézier curves are the driver's curves scaled. `_rig.json` exports the couplings.
  - **Rest pose:** the item table's convention: the hatch open (panels parked) and the plate down. That lets `raise` and `lower` play on their own; door values measure how far a door has closed.
  - **Plate:** the jump pad's shell. A slab with chamfered corners and a skirt 0.25 m down its sides, 1 mm clear of the walls. Its face has a lit ring round a black field and nothing directional (the player may step off either way). In each shaft corner a black mast carries a stainless steel guide rail, and the skirt's chamfered corners run 1 mm off the rails. The masts stop under the panels' sweep, and the frame's corner fills cover them.
  - **What was simplified :** as on the jump pad, nothing under the plate is ever seen, so the lift drive is not modelled. A first version drove the plate with a rack-and-pinion hoist (involute pinions in gearboxes under the plate); the user had it simplified to the plate and its corner rails. The door carriages sit behind the shaft wall, and the cull removes them from the export.
  - **Cull states (`cull_states`):** the cull runs on the check states binned by the drivers' values (1 cm of slide, 5 mm of drop, 3 cm of plate travel), 75 states instead of about 480. The re-tests of hidden faces at every plate height made a full cull run for over half an hour; the build now takes about 14 minutes.
  - **`check_coplanar` fix:** the check now takes each plane group's projection axis from the group's rounded normal. It had taken each face's own axis, so two 45° faces in one plane at diagonally opposite shaft corners were compared in different coordinates and falsely overlapped. The other props still have the per-face version, which has never misfired on them.
- **Portal gate** ([`portal_gate/`](../../library/models/gameplay/portal_gate), 1.5 × 0.1 × 2 m, 3,084 triangles; user: thin, 0.1 × 1.25 m on the ground, 2 m high, after a first 0.5 m deep, 2.25 m tall version): a freestanding walk-through teleporter, symmetric left to right and front to back so it is entered from either side. It stands on the floor (no cut-out, so no `check_footprint`; its outside corners are chamfered). Its opening is 1.25 m wide and 1.85 m high over a 2 cm threshold, so Tensor (1.753 m) clears it; `check_envelope` fails the build if anything leaves the 1.5 × 0.1 × 2 m box in any state or stands in the passage (`PASSAGE`: 1.12 m wide up to 1.76 m, 0.9 m up to 1.83 m). Its tri count is from a build with the cull.
  - **Frame:** one unibody (the user asked for lofted, shroud-like unibody shells built with as many booleans and unions as needed). Two towers are lofted up through octagonal sections (`PILLAR`): a grey plinth, a band in to a slimmer column, then a flare out to a tower head with a sloped roof. The header between them is lofted along X, with a crown over its middle 6 mm prouder front and back, its top rising in 45° ramps. A raised pod sits on each column's outer face. All of it is fused with exact unions (`boolean`), then machined (`machine`):
    - a black channel down each inner face;
    - through-bores in the crown;
    - grooves for the lit strips down the columns' front and back faces (the tower heads are unlit: user);
    - slanted vents in the header, and two batches of five horizontal vents in each pod (not vertical), above and below the handle, their ends slanting out toward the top so they read the same from the front and the back;
    - a grab-handle pocket in each pod.

    `machine` colours each face at its triangles' centres against the uncut solid. The cuts are matte black, the plinths and pods grey, the rest off-white. A ring-shaped face's median lies in its hole, which once blacked out the column's face round the pod.
  - **Field:** its own mesh (`SK_PortalGateField`), one double-sided quad at y = 0 with its own material slot `M_Portal`, UVs 0..1 across it (u toward +X, v up). The game puts its portal shader there. In previews it is emissive. It floats 1 inch (25.4 mm, `FIELD_GAP`) clear of the frame all round , 1.199 × 1.779 m. An earlier version sat its edges in a slot round the opening and had 45° gussets in the top corners; both went, since a rectangle can't keep an even gap inside chamfered corners.
  - **Mechanics:** in each inner channel, two tubular linear motors, one each side of the field: stainless steel rods between bolted grey mounts, with off-white carriages. The mounts and carriages are the field's clips: they reach 1 cm past its side edges, one in front of it and one behind (a lit lens on each, facing across the opening) riding them 0.7 mm clear (`Carriage<Left|Right><Front|Back>`, slides, 1.316 m of travel). In the crown are two counter-rotating flywheels (`FlywheelLeft/Right`, hinges about ±Y with no limits): black discs with pocketed stainless steel faces on stainless axles, turning in bronze hubs on three-armed grey spiders just inside both faces. Each pivot is at a hub, so the bearing check finds it. There are no coolant lines: they were in the deep version, and at 10 cm there is no room beside the carriages.
  - **Animations:**
    - `activate` (60 frames): the flywheels' speed ramps linearly to 12°/frame, which ends on one whole turn.
    - `active` (a 120-frame loop): the carriages sweep the field's height and back, easing at the ends, and the flywheels make 4 turns.
    - `deactivate` (60 frames): the flywheels spin down, again over one whole turn.

    The rest pose is inactive, with the carriages parked at the bottom. Start `deactivate` at the end of an `active` loop.
  - **Gizmos:** `SpawnFront` / `SpawnBack` on the floor 0.6 m either side, facing away from the field (where a traveller arrives), and `FieldCenter`.
- **Thruster** ([`thruster/`](../../library/models/environments/thruster), 5 m round, 4,790 triangles): a lift thruster for the game's floating platforms, many of them under each map piece. Its top face is bolted flat to the platform's underside: the origin is that face's centre (z = 0) and it hangs below, the exhaust pointing down, 4.61 m deep at rest and 4.98 m at full vectoring. `check_envelope` fails the build if anything leaves a 2.5 m radius or 5 m depth in any state. It isn't set into a cut-out, so there's no `check_footprint`. The cull's level surface is set far above it, so nothing is treated as hidden by the platform: the top face stays, and the previews carry no platform slab (not needed). Its `model.py` is the portal gate's framework with its own spec and builders; every round shell is 32-sided (the gimbal ring 24), turned half a side so a flat is centred on each axis and every mount sits on one.
  - **Body** (`Root`): one lofted unibody (`BODY`): a grey mounting flange with eight nuts under its rim, a grey band of eight status lamps, an off-white drum and a chamfer to a flat grey underside. Fused into it are eight grey ribs under the lamps, grey doubler pods at ±X and the two hanger lugs under the pods. It is machined with a pocket on each diagonal for a stainless steel propellant tank (its bronze end necks seated on the pocket's top and bottom), a channel up each side at ±Y for a pitch actuator, and slanted vents over the pods and the channels.
  - **Thrust vectoring: a Cardan gimbal**, both axes crossing on the thruster's axis at `Z_P`:
    - The matte black gimbal ring (`GimbalRing`, a chamfered box section) turns ±10° about X (pitch; + swings the exhaust to the back). Its stainless trunnion pins run through the hanger lugs and bronze bushings, nutted outside.
    - The engine (`Nozzle`) turns ±10° about Y in the ring (yaw; + swings the exhaust to the right). Its trunnions at ±Y turn on pins in the ring's titanium bosses.
    - Pivots sit in the bushing and the boss, so the bearing check finds them. The ring's outer face and the lugs' inner faces are square to X, which pitch never changes, and the nozzle's round trunnions don't change under yaw. The nozzle's top stays under the body's underside at every corner of the range.
    - Four single-stage hydraulic actuators, each spanning one hinge (the framework's pistons): the pitch pair from pins across the body's channels down to clevis cheeks fused on the ring's top at ±Y, and the yaw pair from cheeks under the ring at ±X down to cheeks fused on the bell. The framework's piston check sweeps only its own hinge, so `check_actuators` also sweeps every actuator's line over the whole gimbal (a 9 × 9 grid plus every animation frame) against every solid part.
  - **Engine**: one unibody of revolution (`NOZZLE_OUT`, `NOZZLE_IN`): an off-white domed top and collar with four lamps, a waist, then a titanium bell with six ribs, a raised exit band with eight notches, and the bore up to a flat injector face. The trunnions and the yaw cheeks are fused into it.
  - **Exhaust surface:** its own mesh (`SK_ThrusterExhaust`, material `M_Exhaust`, yellow and emissive in previews; user: the game sets the flame shader), 160 triangles. It lines the bore 1 mm in front of it, meets it at the exit rim, and closes over the injector in a shallow cone. UVs are analytic: u runs 0..1 round the bore from +X toward +Y, and v runs from 0 at the exit rim up to 1 at the injector's centre. It is built in the kit on the nozzle bone (so the checks and the cull see it) and split off after the cull. The bore and injector faces behind it are then deleted (`drop_bore`): they never show, and they meet the rest only on sharp edges. The cull alone keeps them, because samples on the exit rim see past the lining where the two meet.
  - **Gizmos** on the nozzle bone, pointing out along the exhaust (in Godot −Z along the exhaust, +Y to the thruster's front): `ExhaustOrigin`, midway up the bore on the axis, where the flame starts , and `NozzleExit` at the exit plane.
  - **Animations:** `idle` (a 150-frame loop, a figure of eight about 2° wide, as if station-keeping), `sweep` (a 120-frame figure of eight over the whole range, for showcases) and the poses `vector_front` / `vector_back` / `vector_left` / `vector_right` (full deflection, named by where the exhaust swings, for a 2D blend space). Both loops start and end centred. The game can also drive the two joints directly and aim the actuators (`_rig.json`: joints, pistons, the gimbal's sign conventions, the exhaust's profile and UVs).
- **Jumbotron** ([`jumbotron/`](../../library/models/environments/jumbotron), 10 × 10 m, 4,772 triangles + 8 for the displays and 96 for the marquees): a floating screen and lighting rig for the middle of the map, lifted by four ducted rotors 10 m square , with placement defined by the map metadata. The origin is the centre of the belly pan's flat underside, on the rig's axis: align its Y with the map's long axis and use the map's height metadata. `check_envelope` fails the build if anything leaves the 10 × 10 m square in plan in any state (4.28 m over the origin to 1.10 m under it). It isn't set in a cut-out (no `check_footprint`), and the cull's level surface is far above it, as on the thruster. Its `model.py` is the thruster's framework with its own spec and builders, and the spawn point's `check_coplanar` (the thruster's per-face projection misread the spots' 45° faces). The round shells are 24-sided, the ducts 16 and the pods 8, turned so faces are centred on the axes.
  - **Body** (`Root`): one lofted unibody fused by exact unions. Bottom up: a round belly pan (the spots' mount); the lower marquee band running up into the display box's underside; the display box (an octagon in plan, its edges chamfered, a 3.1 × 1.744 m, 16:9 display recessed 4 cm in each face); a wide grey ring over it carrying the upper marquee band between two lips; and the fuselage drum with a beacon on its flat top. From the drum, four keeled arms (a flat top, the sides chamfered in to a narrower bottom) run out on the diagonals to the motor pods. At each pod is a duct (a straight bore, a rounded inlet lip, a grey outer wall), fused to the arm and to two more spokes that dip onto its lip: a Y over the rotor. A pad under each duct's outer corner carries a spot. The unibody is machined with the display recesses and three slanted vents in each drum face between the arms. Colours: off-white drum, arms, pods, duct lips, box and belly; grey rings, lips and duct walls; the bores and every cut matte black.
  - **Rotors** (`Rotor<Diagonal>`, hinges about Z, no limits): a titanium motor can sunk under each pod, then on the rotor a stainless shaft up into it, a stainless spinner and five twisted grey blades seated in it. Each blade's leading edge is raised in its sense of turning, so it drives air down through the duct; the tips run 4 cm inside the bore's flats. Diagonal pairs turn the same way so their torques cancel: front-left and back-right counter-clockwise from above.
  - **Spots**: twelve moving heads, eight round the belly 1.55 m out and four under the ducts' outer corners. Each has three stages:
    - a titanium pan motor sunk into its mount;
    - `Spot<Position>Pan` (±270° about Z): a stainless rotor boss sunk into the motor, a matte black yoke, a titanium tilt motor on one arm (the axle's bearing is in the other);
    - `Spot<Position>Tilt` (±80° about the arms' axis, + swings the beam out, away from the rig's axis): a stainless axle through both arms and an off-white tapered can with a black bezel round an `M_Lamp` lens (warm white, emissive).

    The joints' pivots sit in their motors, so the bearing check finds them. `check_spot_spacing` fails the build if two spots' swept volumes (round their pan axes, over the whole tilt range) come within 2 cm, so no combination of their motions can make them collide; the motion check sweeps them all together over pan × tilt.
  - **Lighting** (enough to light a 25 × 75 m map). The map's long axis is on the rig's Y, tiled 2 × 6 in 12.5 m zones. Each spot is given the zone it reaches best: an exact assignment by least total squared tilt (Kuhn–Munkres). `flood` aims each spot at its zone's middle (the pan and tilt solved in closed form, the solution with the least pan). `_rig.json` gives each spot its cone half-angle (the zone's corners plus 4° of overlap, 17–24°) and range (34–50 m), for a SpotLight3D under its `Spot<Position>Beam` gizmo (at the lens's middle, riding the head; in Godot −Z along the beam). `check_lighting` proves, through the joints' kinematics, that every beam points at its zone's middle and leaves the rig without meeting a part. Verified in Godot 4.7.2 (headless import): each `Spot<Position>Beam` imports under a `BoneAttachment3D` on its head bone, and a `SpotLight3D` added under it with no transform shines straight down at rest and exactly on its zone's middle in `flood`, riding every animation. Its +Y is the head's outward side (the way + tilt swings it). There are no gizmos on the displays . A scratch render of the flood over a 25 × 75 m floor lit every zone, the zones' corners in the cones' soft fringe (hence the 4° overlap).
  - **Displays and marquees:** after the cull they are split off into their own meshes, white and emissive (the game's textures go there later):
    - `SK_JumbotronScreen`: the four recesses' floors, `M_Screen`, each 0..1 (u from its left to its right as seen from in front, v up);
    - `SK_JumbotronMarquee`: the two bands, `M_Marquee`, each band u 0..1 once round counter-clockwise from above (text scrolled along u reads left to right from outside) and v 0..1 up it.

    They are the body's own faces, so nothing lies behind them and nothing z-fights. The build fails if the cull removes any of them.
  - **Animations:** the rotors and the spots are keyed in separate actions, so they layer.
    - The rotors: `hover` (a 60-frame loop, 5 turns, 150 rpm), `spin_up` and `spin_down` (96 frames and 4 turns each, the speed ramping).
    - The spots: `lights_on` and `lights_off` (45 frames, eased), `flood` (a pose), and `show` (a 240-frame loop). In `show` each spot's aim runs a figure of eight through its zone's middle, mirrored on alternate spots, starting and ending on flood (every frame solved, each solution continuing from the last; at most 1.25°/frame of pan).

    The showcase plays `lights_on`, `show` and `lights_off` over `hover`. The jumbotron's `animate.py` adds `scene["preview_under"]` for this: looping actions repeated under the whole sequence, since a held action would freeze the rotors.
  - **Budget:** the twelve spots are 40% of it (about 160 triangles each), and a floating rig is seen from every side, so the cull takes only about 100 off. To fit, the ducts went to 16 sides and the pods to 8, the hub's profile lost two stations, and the blades are seated in the spinner rather than fused to it (the unions' seams cost about 70 a rotor). The lower marquee also lost its upper lip, and the spot heads are tapered cans.
  - **Collision:** the weapons' `collision.py`; `collision_extras.py` gives the displays and marquees no collider (they lie flush in the body, whose pieces close over them).
- **Skyfall map:** the standalone 75 × 75 m lunar map replaces the retired arena foundations and previous maps. Floating floors use native platform/lip/bridge helpers under `models/maps/common/` through placement gizmos. See [Skyfall's source contract](../../library/models/maps/skyfall/README.md).
- **Telescopic pistons (framework):** a `PISTON_SPECS` entry may end with a stage count. The barrel still sits on the parent and the rod on the child, each aiming at the other's anchor; between them the stage tubes (`<name>Stage<i>`, children of the barrel bone) nest by radius, each sliding an equal share of the A–B distance's change from rest along the barrel's axis. Every tube is as long as fits between the eyes collapsed, and `PISTON_MIN_OVERLAP` applies at every joint at full reach. The live rig drives the stages with drivers, added after the actions are baked; the actions key them, and export removes the drivers along with the constraints. The barrel is `M_Secondary` and the stages and rod stainless steel (`M_Joint`), with a gland collar where each tube comes out. `_rig.json` lists each strut's stages with their slide rule.

## Gameplay props

The [pulse gun](../../library/models/gameplay/pulse_gun/README.md) is a
grounded turret within a 1 × 1 m swept footprint, with an explicit configured
7,500-triangle render budget (7,474 exported). It has lofted castings, a hollow
vented accelerator shroud, bored waveguide, supported bearings and a pinned
hydraulic elevator. Its rigid `Root → Yaw → Elevation → Barrel` chain supports
full yaw, 0–60° elevation and 10 mm recoil; two additional deform bones carry
the cylinder and rod. It exports one-second `armed` (15°) and `unarmed` (60°
upward park) pose clips with baked actuator alignment, and a barrel-mounted
`Muzzle` gizmo. It has no ammo pack. Its README owns the assembly, regeneration
and validation contract.

The [`speed_ramp/`](../../library/models/gameplay/speed_ramp) is a straight
inclined launch cartridge, **1.5 m across X and 1 m forward along -Y, 0.75 m high**, with a
integral housing feet fully above ground, with no separate platform or mounting cutout. Two ribbed elastomer tread lanes wrap supported
drums on a common shaft; recessed coaxial motor caps, lofted off-white shrouds,
horizontal vents, retained-pin service covers, protected power looms, green rail
lenses and a formed stainless centre/nose guard use the existing prop materials.
The former hydraulic shoe is replaced by the powered conveyor. Every vertex keeps
one unit-weight influence: ribs and steel stay rigid while the carrier faces flex
between 24 rigid stations per lane. `convey`, `launch`, `service_open` and
`service_close` bake the coupled belt/drum and cover motion at 480 fps; the showcase
plays at 30 fps. The low-poly `SK_SpeedRampCol` has a stable smooth riding surface
and hinged covers; the separate stepped-on `SK_SpeedRampTrigger` is one inclined
Root-weighted convex area. See its README for the illustrative launch design,
clearance checks and round trips.

Repair-station pad/emitter rings, tower status cells and carriage indicators use `M_RepairStatus`, red in the inactive source asset. The game duplicates this surface for ready-green/unavailable-red feedback. The overhead downlights and welding arc retain `M_Emissive`, and the projected shield keeps `M_Shield`. Material separation leaves the geometry, rig and collision unchanged.

The portal gate's inward-facing carriage lenses have their own `M_PortalStatus` slot, red in the inactive source asset. The game duplicates only that surface to show red while travel is unavailable and green while usable. Its outer strips and header retain `M_Emissive`; never recolor that shared decorative slot to indicate portal availability. The material split does not change geometry, rig, animations or colliders.

The props carried or worked on by players, in `models/gameplay/` with the others there. They follow the props' rules (scripts, rigid parts on bones, the unibody helpers, every mechanism checked, ≤ 5K triangles, the props' finish in Tensor's materials, their own animations in the GLB, the props' `preview.py` and `animate.py`), with the differences below.

- **CTF flag** ([`gameplay/ctf_flag/`](../../library/models/gameplay/ctf_flag), 2,668 triangles + a 304-triangle cloth): the capture-the-flag flag, carried on a player's back and standing on the ground on its own tripod. Size : the flag unit is 1.0 m long with its legs folded (`STOW_LENGTH`) and stands 1.25 m tall on them (`HEIGHT_DEPLOYED`: the legs lift the pole's bottom 0.25 m off the ground); the pole is at most 5 cm across (`POLE_W`, its pods included). `check_envelope` and a width check in `build_spine` fail the build otherwise. Its `model.py` is the thruster's framework with its own spec, parts and checks. The origin is on the ground under the pole, between the feet. The flag's front is −Y and the cloth flies to its back (+Y).
  - **Pole** (`Root`): one lofted unibody through chamfered-hexagon sections (`SPINE`: flats facing the three legs, the front and the back, corners at ±X; the core's y scaled 1.2 so it is deeper than wide). Bottom up: a grey hub, a slim grey shaft with a lit ring in a groove, an off-white core flaring out of the shaft and tapering back in, a grey upper shaft, an off-white collar and a lit beacon on top. Fused in: the legs' clevis lugs on the hub, side pods on the core (a lit cell window in a pocket, a bolt above and below it), a black D-grip on its back, two grey cloth arms and the hook on its front. Machined: the grip's opening, the ring's groove, the cells' pockets, slanted vents in the core's front and back. Each face takes the colour of the surface it lies on (the loft's by height, a fused part's its own), found by distance from the unfused solids. Colouring by position painted a pod's and an arm's faces next to the core and the collar off-white . The loft is triangulated first: the core's tapers change its depth, so their quads aren't flat, and the distances must be measured to the same triangles.
  - **Ground mount: a tripod** (`LegBack`, `LegFrontLeft`, `LegFrontRight` at azimuths 90, 330 and 210, so the back leg stands under the cloth). Each leg is a grey unibody (a knuckle, a tapering shaft grooved down its outer face, an ankle) with a black rubber pad. It turns on a stainless pin in a clevis lug outside the pole: two cheeks fused into the hub, round about the pivot. A titanium hinge motor (bronze end cap) sits on one cheek's outer face; the motor's housing is the bearing. A nut on the pin runs 0.5 mm off the other cheek: it turns with the leg, and flush on the cheek, floating-point noise read the contact as a collision mid-swing. Hinge 0 is deployed, the pads' soles flat on the ground at z = 0 (38.6° out from straight down). At `FOLD` (141.4°) the leg lies straight up along the shaft, clear of the core. No pistons: a 141° swing is a motor's job.
  - **Back mount**: the hook's pocket (`BAR`, radius 9.5 mm) drops over the grab handle on Tensor's power pack, and a stainless latch swings shut under the J (`Latch`, 0 open, 90° shut). The latch is two side plates outside the hook's faces and a crossbar, turning on a pin in a bronze bushing in the hook's wall. The attachment is gizmo to gizmo : the flag's `BackMount` lies inside the lock, on the pocket's axis at the unit's centre (0.75 m up standing). Tensor's `FlagMount` (his model.py: `FLAG_MOUNT`, on `UpperChest`, the middle of the handle bar's axis; the handle is built from the same constant) has the same axes. The game matches the two, and the hook seats on the bar. Carried, the flag keeps his orientation: its front toward his back, the cloth streaming behind him.
  - **Carry check** (`check_carry`): the flag's model.py reads `FlagMount` from `tensor_rig.json`, and his body and default head from `tensor.blend` at rest. So build Tensor first. It places the stowed flag by matching the gizmos, exactly as the game does. The build fails if anything of the flag enters him, if the pocket is more than 3 mm off the bar (it bears 1.5 mm over its flats), or if anything but the hook and latch comes within 5 mm of him (the rest keeps 26 mm). The check covers his rest pose only, not his animations.
  - **Cloth** (an emissive material, tinted with the team's colour in game): its own mesh `SK_CtfFlagCloth`, one double-sided `M_Flag` slot (off-white, emissive). UVs run u 0 at the luff to 1 at the fly and v 0 at the bottom edge to 1 at the top. It is a 0.5 × 0.33 m sheet (18 × 8 quads) flying from a sleeve round the stainless luff rod. The rod turns in bronze bushings in the two arms' eyes (`Swivel`, about Z, ±40°: the flag weathervanes). The sheet hangs on four rows of six-bone hinge chains about the vertical (`Cloth<row>_<seg>`, row 0 at the bottom edge, segment 0 at the luff, each hinge ±35°). It is the one smooth-skinned mesh in the library, the documented exception to rigid skinning: bilinear across the rows and the segments' middles, up to four influences a vertex, while the sleeve is rigid on the swivel. `check_cloth` deforms the cloth through every frame of `wave` and `flutter` (and every sixth frame with the swivel at its limits) using the joints' kinematics. It fails if a vertex comes within 2 mm of a rigid part (a hit is confirmed by distance or by `buried()`'s two rays, since the framework's single parity ray grazed an arm's edge), rises over 1.25 m, comes within 1 cm of Tensor when carried, or if a sheet edge stretches or shrinks more than 8% (1.6% now).
  - **Animations**: `stow` (24 frames, picked up: the legs fold, then the latch shuts), `deploy` (22 frames, dropped: the latch opens, then the legs swing down and stand), and the loops `wave` (90 frames, standing in a breeze) and `flutter` (30 frames, carried at a run). The loops are travelling waves from the luff to the fly: each segment's absolute angle is `A(s) sin(phase − k s − lag)`, growing toward the fly, with the top row leading. The swivel sways once a loop. The cloth loops key only `Swivel` and the cloth bones, and `stow`/`deploy` only the legs and the latch, so they layer.
  - **Gizmos** : `GroundMount` at the origin (where the flag stands) and `BackMount` inside the lock (matched to Tensor's `FlagMount`). Both have −Z toward the flag's front and +Y up its pole in Godot. `_rig.json` gives the mounts, the Tensor gizmo `BackMount` goes on, the cloth's bones and UVs, and the team-tinted slots (`M_Flag`, `M_Emissive`).
  - The cull's level surface is set far away, as on the thruster: the flag is carried and dropped anywhere, so its pads' soles and hub show.
- **Repair station** ([`gameplay/repair_station/`](../../library/models/gameplay/repair_station), 2 × 2 m, about 4.8K triangles + a 520-triangle shield): Tensor walks onto its pad and stands; a shield rises round the bay (it blocks hits while he is repaired) and two robotic arms work over him. Its `model.py` is the CTF flag's framework with its own spec, parts, planner and checks. It stands on a 2 × 2 m floor tile and matches it exactly : the deck is a 6 cm block with square outside corners (`check_footprint` at the floor and the deck's top), and nothing leaves the tile in any state. The origin is on the floor at the tile's centre; front −Y.
  - **Deck** (`Root`): grey, an off-white pad (r 0.585 m) in a black groove, lit broken rings and a centre lamp in its pockets (their floors lit, walls black), the emitter groove round the pad (r 0.945–0.975 m, its floor lit) and slanted vents across the corners.
  - **Towers** at ±X, one lofted unibody each: a grey plinth, an off-white column with lit cells in its front and back and horizontal vents stacked up its outer face (not vertical ones), a grey head with a hood hooking in over the pad (a downlight under its tip), and a channel down its inner face for the linear axis: two stainless rods between grey mounts.
  - **Arms: SCARA.** A carriage (`Carriage<Side>`, slide, 1.03 m down and 0.14 m up from its high park) rides the rods in bores 0.7 mm clear, with a shelf fused on top carrying the titanium shoulder motor. Under it the shoulder (`Shoulder<Side>`), elbow (`Elbow<Side>`) and wrist (`Wrist<Side>`) turn about vertical axes: 0.37 + 0.33 m links, the forearm stacked under the upper link so it folds right under it, a titanium motor over the elbow and a bronze bearing ring under the wrist. The right arm is the left one turned half round about the station's axis, so the same joint values move it alike (the axes are all +Z). Stowed (the rest pose), the left arm lies along its tower pointing to the front and the right one to the back, clear of the entry corridor (`CORRIDOR`: nothing but the deck within |x| < 0.47 m). The shoulder's range stops at +35°, where the upper link would meet its column's corner. The left tool is a welding torch (a lit arc at its tip); the right a gripper that rolls about its axis (`GripperRollRight`) with two pinned fingers (`FingerRight1/2`).
  - **Paths planned against Tensor.** model.py loads Tensor's body and default head from `tensor.blend` and his `common/idle` clip from the animation library (so build Tensor and run `animations/retarget.py` first), stands him on `PlayerMount` and samples ten idle frames into one BVH. His idle stands turned about 35° to his left with his left foot forward: his chest faces the left tower and his back the right. Each arm works two spots (`SPOTS`: a height, a line of approach and its direction): the torch the chest and the left upper arm; the gripper the power pack and the right upper arm. `probe()` casts rays along the approach across the tool's width and height and stops the tip `STANDOFF` short of the first surface. The clips are timed to the game : `activate` (shield on) 1 s, `repair` (the weld and fix while he stands there) 5 s, `deactivate` (shield off) 1 s. `repair` (150 frames, keyed every frame, ending where it starts so it can loop; each spot `SPOT_T`: approach 12, work 39, back off 10, travel 14 frames) eases the tip between rests (travel bowed out 6 cm away from him), and `ik()` solves the arm in closed form, the elbow always out on the side away from him. The torch welds an 8 cm seam upward, weaving, on frames 12–51 and 87–126 (`_rig.json` `effects`: when to run the sparks on `TorchTip`); the gripper grips, turns 60° and lets go at each of its spots. The carriages park high (the tools at 1.4 m, where he is slim), so in `activate` each arm unfolds there, backs off along its first approach, comes down and closes in within the second while the shield grows (20 frames); `deactivate` plays the arms backward while the shield sinks over its last 20 frames. `check_patient` fails the build if any part of an arm comes within 1.5 cm of him (vertex and face-centre distances, plus BVH overlap) on any frame; 28 mm is the nearest now. The paths assume he is unarmed and idle.
  - **Shield**: its own mesh (`SK_RepairStationShield`, `M_Shield`: the game's shader replaces it; 90% transparent and emissive in previews, user), a wall r 0.96 m to 1.95 m and a half-ellipse dome to 2.5 m, its foot in the emitter groove. It is rigid on the `Shield` bone, whose local-Y (height) scale grows 0.001 → 1 in `activate` and shrinks back in `deactivate`. At rest (the bind pose) it is full size, so the game hides it while the station is idle. `check_envelope` keeps everything over the deck 1 cm inside it in every state. UVs: u round from +X toward +Y, v 0 at its foot to 1 at the apex.
  - **Gizmos** (for the game's particle effects): `PlayerMount` (the pad's centre, facing the front), `TorchTip` (the welding arc, along the torch: sparks), `GripperCenter` (between the fingertips), `ShieldCenter`, and `DownlightLeft` / `DownlightRight` (under the hoods, pointing down).
  - **Previews:** the stills show the station alone, stowed. The `ready`, `weld`, `grip` and `rising` poses show a static stand-in of Tensor in his idle (`PRV_Tensor*`, never exported) and the shield; `reach` shows the arms without him. The showcase plays activate, repair twice and deactivate with him standing inside.
- **Collision models:** both props run the weapons' `collision.py` unchanged (see "Collision models" under Weapons), and so gets `<name>_col.glb/.fbx` on its own skeleton with its actions. The flag's cloth, the one smooth-skinned mesh, gets none . An asset's own colliders live in `collision_extras.py` next to it (`CUSTOM`: a mesh's collider made its own way instead of convex pieces; `EXTRAS`: more collider objects), kept out of the convex solve and rendered on their own (`_col_<name>_*.png`). The repair station's are both user requests. `SK_RepairStationShieldCol` is the shield's: a closed, 12-sided thick shell on the `Shield` bone (it grows and sinks with the shield), its outer face the shield's tangent polygon swept by a circumscribed one (it contains the shield, its corners still on the tile), its inner face inscribed in the render mesh. It stops hits while the shield is up. It is hollow, since the patient stands inside it, so the game uses it as a concave (trimesh) shape on a layer that only hits test. `SK_RepairStationPadTrigger` is an area, not a solid: a flat 16-sided disc 10 cm tall on the pad at `PlayerMount`. Its radius is the pad's (0.585 m) less the player's capsule radius (`PLAYER_RADIUS`, 0.3 m), so the capsule overlaps it once the player's centre is over the pad; that starts the repair. The station's own collider takes up to 1,000 triangles (`TRI_MAX` in its `collision_extras.py`; 914 now, its hull tolerance 14 mm), and its arms come as near as 1.5 cm to the patient, so the arms' pieces overlap him: keep them off the patient's layer while he is repaired.

## Weapons

Asset: [`models/weapons/minigun/`](../../library/models/weapons/minigun) (hitscan), [`models/weapons/rocket_launcher/`](../../library/models/weapons/rocket_launcher) (projectile), [`models/weapons/lightning_gun/`](../../library/models/weapons/lightning_gun) (a beam weapon) and [`models/weapons/pistol/`](../../library/models/weapons/pistol) (a sidearm with a moving slide) and [`models/weapons/rifle/`](../../library/models/weapons/rifle) (a designated marksman rifle: auto fire, and a zooming optic for the sniper mode), [`models/weapons/flamethrower/`](../../library/models/weapons/flamethrower) (a stream weapon with an always-lit pilot burner and a twin-can pack) and [`models/weapons/emp_gun/`](../../library/models/weapons/emp_gun) (a pulse weapon: a sliding waveguide, an actuated air intake, a drop-out battery). Every body is a lofted unibody shell. A weapon's `model.py` is its own spec, joints, animations and builders around the props' generic framework (kinematics, pistons, mesh kit, checks, rig, action baking, export), copied from `jump_pad/model.py`. As with the props, a function the weapon defines after the framework replaces the framework's. `preview.py` is the props' own (the rocket launcher's adds solo renders); `animate.py` (model-agnostic for weapons) renders Tensor holding the weapon through its clips of the animation library (see "Animation library"), leaving out anything hidden from renders, such as a projectile. Weapons follow the same rules as props (scripted, rigid parts on bones, booleans for exact shapes, every mechanism logical and checked), with these differences:

The [bio rifle](../../library/models/weapons/bio_rifle/README.md) is a bio
cluster asset: a radiused dark-grey receiver with an exposed lathed chamber
and matching cassette, turned
pressure barrel, raised skeletal stock, independent half-filled liquid volume
and green glass at 10% opacity. `SK_BioRifleLiquid` uses only `M_BioLiquid` for a
later game shader; its closed volume is retained within the 5K weapon budget.
Its vessel supplies collision, so `collision_extras.py` excludes the liquid.
At the user's explicit request, the cassette also uses 10%-opaque glass and
separate half-filled `SM_BioRifleAmmoLiquid` / `M_BioAmmoLiquid`, within its
1.5K budget; this is an exception to the general no-glass magazine rule.
The fixed heavy delivery line has a machined collar land, enlarged compression
fitting and a rigged shutoff lever (`BioValve`); its service loom uses aligned
glands, constant-height routing and bored clamps. Six rigid bones carry nine
mechanical actions. It takes rifle-family clips and the standard bottom reload
through `animations/retarget.py`. Runtime registration and shader work remain

- **Size and placement:** every weapon fits 0.25 m wide × 0.75 m long × 0.35 m high (`WEAPON_MAX`). The muzzles point −Y (glTF's +Z). The origin is on the gun's bottom plane, midway along it, so the item table's `ItemMount` and the weapon holder's `WeaponMount` take it by its bottom. `check_envelope` fails the build if the gun at rest leaves the envelope, its lowest point is off z = 0, or it isn't centred along its length. The minigun is 0.115 × 0.722 × 0.319 m, the rocket launcher 0.192 × 0.722 × 0.306 m (both slimmed at the user's request: they had been 0.204 and 0.227 wide), the lightning gun 0.111 × 0.748 × 0.312 m, the pistol 0.077 × 0.305 × 0.201 m the rifle 0.081 × 0.750 × 0.319 m and the flamethrower 0.135 × 0.696 × 0.347 m, the EMP gun 0.102 × 0.724 × 0.324 m (a full-size pistol's proportions at 1.25, its front housing enlarged at the user's request). To fit the height the launcher steps its belly: the pack docks under a lower front belly, and the pistol grip hangs from a raised rear belly, high enough over the hand that the thumb clears it, with the pommel and the pack's underside both on z = 0. The minigun's hexagon puts its flat belly at that rear height all along, so its pack is taller instead.
- **Budget:** ≤ 5,000 triangles for the gun, ≤ 1,500 for a detachable magazine or ammo pack, which is its own mesh, and ≤ 500 for a projectile. The [flak cannon](../../library/models/weapons/flak_cannon/README.md) has a configured 7,500-triangle gun limit; its pack retains the 1,500-triangle limit.
- **Finish:** no team colours; every body colour is a military one : the minigun's green, the lightning gun's blue, the pistol's yellow, the rifle's beige, the rocket launcher's red, the flamethrower's red and yellow, and the minigun's and the rocket launcher's bodies are one colour all over ("the black looks so ugly" of a black lower body under the red; grips, buttpads and small housings stay matte black), the EMP gun's gloss white and matte black. The EMP gun is gloss white metallic (`M_Primary`) over matte black rubber (`M_Secondary`) on everything the body touches (the lower flange under the hands, the grip, the stock and buttpad, the battery's bumper; user), with a metallic black waveguide, titanium for the muzzle head, bezel, coil plates, dock and intake door, bronze for the coil, capacitor, contacts and feeds, stainless steel pins, rods and bolts, and cyan lights (the emitter behind the aperture, the charge display, the battery's gauge). The minigun uses eight slots: `M_Primary` military green, `M_Secondary` matte black, `M_Frame` matte titanium, `M_Joint` stainless steel, `M_Emissive`, `M_Bronze`, `M_Glass` (alpha 0.25, exported as a glTF `BLEND` material) and `M_Wire` (copper). The minigun's shell is banded titanium, military green and matte black. The rocket launcher's `M_Primary` is military red (its shell) and it adds `M_Metal`, metallic black (its frame, the strap along its top, its pack and rockets); its tubes are titanium. The lightning gun's `M_Primary` is military blue (the shroud's upper part, the prongs and the cells) over matte titanium, with `M_Metal` for the pack's sled and bands and the actuators' clevises and yokes. The pistol's `M_Primary` is military yellow (its whole front housing, underside included) over `M_Metal`, a dark gunmetal grey (the hook, the cartridge; the user asked for dark grey, not black); its slide, frames, barrel and suppressor cap are matte titanium (the cap the body's finish, user). The rifle is the user's palette, split along its length rather than in bands (not a "vertical dual tone"): military beige (`M_Primary`) on the shell ahead of a slanted split line just behind the magwell (leaning forward toward the top), on the magwell and on the skeleton stock's opening walls and cheek riser; matte black on the shell behind the split, the grip, trigger housing, stock, magazine, rail, the lamp and the optic (the user asked for the optic not to take the body's colour); metallic black (`M_Metal`) on the machined walls, the objective housing, the buttpad and the controls. The shell is lofted once and made in two pieces, each carved with the same machining and intersected with the half-space on its side of the split plane (`split_region`), so the colour line is exact. Only the barrel and its flash hider are titanium (the user found a black muzzle ugly). The flamethrower is military red and military yellow : a red nose and grip head, a yellow body, a matte black domed head, grip, sleeve, heat shield and pump; its gas cans are brushed aluminium (`M_Alu`) with matte black domes and bands, a dual tone the user asked for instead of the body's colours; it adds `M_Red` and `M_Ceramic` (the pilot's insulator), its bronze is shinier (the cans' crossover pipe), and its lights are amber (the fuel display on the grip's head, the gauge's dial).
- **Lofted unibody shells.** Each weapon's body is one shell from its front face to its buttpad, lofted through a ring function (`loft()` through `shroud_ring()` or `shell_ring()`). Every station has the same points, so the flanks, corners, chines and colour splits run as straight lines. It is machined with the same exact booleans as a plate (`carve()`: cylinders, boxes and profiles cut away, and optionally a per-face material). A buttpad is exactly the shell's end section. The user turned down a first lightning gun that repeated the minigun's and launcher's boxy receivers with bolted square panels and vent slots, asking for "a smoother, longitudinal shape". They then liked its lofted shroud and asked for the same treatment on the other two, so no weapon has bolted armour panels or a bolted-on fire-control box now.
- **No glass on ammo packs, no rotor without a job (user rules).** A pack shows its rounds through slots or vents cut through its wall into a cavity, not a window under glass (the pistol's cartridge; the rocket launcher's pack has two rows of slots over its rockets). The user removed a cooling fan from the pistol's flank ("wrongly designed"): every rotor, dial and cap must do something (the pistol's gas regulator dial meters the expansion chamber's bleed through its gas line). They also removed a glass-looking ejection window from the flank (the case now leaves through the crown) and ask for features centred on their bands (the pistol's fin windows level with its display and vents, the dial centred in the lower band).
- **Every weapon looks different (user rule).** Don't reuse another weapon's body or cover design. The shells share the method, but each has its own section, colour split and details:
  - The lightning gun is a machined section, no rounded corners (its rounded-rectangle shroud and soft cowl hump looked "toyish"; the flamethrower's and the pistol's industrial look is the aim): a titanium chassis (a flat keel, two big chamfers at each lower corner, upright flanks) under a narrower military blue housing stepped in 3 mm at the seam (a real ledge, not a colour line), its flanks leaning in 4 degrees and its top corners chamfered 45 degrees; a straight 45-degree ramp up to the cowl's flat crest; the nose and the rear end chamfered all round. The chassis' flanks carry finned heat-sink pockets and the housing's bolts under the ledge; each housing flank a capacitor (a can clamped to it, bronze terminals, a bronze line from its front bending into the housing; the two capacitors' backs linked by a black cable over the housing's top behind the pack's bay; every bend rounded (`fillet()`), not a blunt 90 degrees: user, not wired to the regulator's cap, and a link over the cowl crowded the front). The regulator's cap sits behind it centred on the seam's ledge, its boss seated across the step (it overlapped the capacitor on the housing).
  - The user found the old minigun and rocket launcher "too fat and toyish, not much mechanical/industrial/logical" and asked for slimmer, mechanically accurate bodies in the flamethrower's and lightning gun's language, with distinct shapes. So their sections now follow their barrels: the minigun's six barrels sit in a regular hexagon, the launcher's three tubes in a triangle.
  - The minigun's receiver is a regular hexagon round the bore axis (a flat top for the display, a flat belly for the pack and the grip, its corners at the sides), the same at every station from the front face to the buttpad, so every line runs straight; its front edge is chamfered. It is green all over, the machined faces bare titanium. Six barrels ride one rotor: a metallic black bolt drum in the front bore (a blind bore per barrel, the recoil stop), a bronze 18-tooth ring gear on its rear, a stainless steel tie rod to the muzzle and two hexagonal titanium clamps, one corner over each barrel. The motor lies in a cradle along the lower left face (the gear assembly on the left), its pinion meshing through the cradle's window; the ejection port and its sliding cover, under lipped rails, and the cover's actuator lie on the upper right face; cooling slots across the upper left face show the drum turning, slanted vents run down the rear of both lower faces, as many a side (their insides metallic black; the user found a second row on the upper left face weird), and a bronze bearing ring is set into the front face. Its barrels, bores and tie rod are hexagonal (six-sided: the theme, and the budget).
  - The pistol's front housing (military yellow) has a vaulted crown over flat flanks stepped in along their length, a raked nose, and hangs a dark grey hook (the suppressor's expansion chamber, lofted on its own, exhaust slots across its front) ahead of a cartridge as wide as the housing; the yellow-over-grey line runs straight along both. It carries bezelled windows onto the barrel's bronze fins (they move with the recoil), vertical gas vents, the compensator slots, a reflex sight, the gas regulator's dial (left, low; user: moved from the right) and the display (left, high). Behind it the titanium slide rides the upper frame; the lower frame is one bevelled plate (guard, trigger block, grip core with black grooved panels, a lanyard hole). Its support hand holds the cartridge from below, palm up, as on the lightning gun , tangent to the true-arc lower left edge of the cartridge and the hook, the fingers turned 55° up the far side; the socket is fitted where Tensor's arm puts the hand exactly with his whole closed hand behind the front face, clear of the muzzle and the hook's exhaust vents, and under the gas vents (the fingers reached past the front), and the build checks it (`HAND_BOXES`, his closed hand boxed in its bone's frame; the palm's seat counts the cartridge); both hands reach with the origin up to z 1.28, the bore at shoulder height.
  - The rifle's shell has a stepped section: a metallic black upper band set in over a beige lower band (the step straight down both flanks), 45-degree faceted shoulders to a flat top that is one straight line from the nose to the stock, and true-arc lower edges. It is slim at the front (the handguard) and widens and deepens in one faceted ramp into the receiver (the user asked for the front to narrow toward the barrel). The handguard is cut half open at the front (a long cut through both upper flanks onto the barrel and its bronze heat-sink collars) with a row of slanted vents behind it, their ends parallel; the walls the machining cut are metallic black (`shell_mat` tells them from the outer skin by their depth inside the section), the recessed access panels' floors keep the skin's colour so they don't read as patches. Out of the nose the barrel is machined in steps (multi-level cuts and punctures, as a real barrel): a jacket with ring grooves, starting a centimetre ahead of the nut so it clears it recoiling, the bare neck, a lock collar and a flash hider with four tines slotted back from its face, side ports and a compensator port. A floodlight (its length halved at the user's request) hangs under the nose from a clevis mount, on a hub on a stainless steel pin across the clevis's cheeks (a `Lamp` hinge the game may tilt), ahead of the support hand's fingers; `Flashlight` marks its beam. The ejection port is on the right flank under a hinged dust cover, the charging slot on the left shows the bronze bolt carrier, and the ammo display stands on the left flank. The optic is faceted too (octagonal sections) and is its own mesh (`SK_RifleOptic`) on its own slide bone (`Optic`): a full-length rail runs along the top and the optic's two clamp mounts ride it (clear of the shell's top, their clamp screws over the rail), so the game sets it farther or closer, or slides it off the rail's front end to take it off and hides the mesh (user request); its zoom sleeve is a child slide on it and `ScopeEye` moves with it. The stock rides two stainless steel rods out of the shell's rear face (the user chose to keep it that way, open in the centre like the lightning gun's). The rifle is 10 cm shorter behind the grip than it was (shorten the stock, so Tensor shoulders it with the handguard in his other hand's reach): the receiver ends close behind the grip and the stock keeps a real rifle's proportions behind it (a stub of a stock behind a long receiver looked wrong). The rifle and the EMP gun are authored where they were and moved back along Y at export so their origin stays midway along them (`check_envelope` gives the shift, `shift_gun` moves the bones and meshes; the rig JSON's positions, the pickup's origin and the preview markers move with them).
  - The flamethrower's body is a pressure vessel: a round section with four machined flats (the crown the firing grip stands on, a flat down each flank for the fittings and the side grip, the keel its pack plugs into), a straight cone to the nose, a full-size front chamber, a 45-degree shoulder down to a slimmer rear and a faceted domed head (the loft's rings are the one flatted section scaled, `body_section`), a bolted titanium flange over the nose's joint. The user asked for real vents, bosses and bevels instead of dark strips (its first flutes along the arcs read as black lines): the rear's flanks carry vent slots with round ends cut into them, the crown a bolted inspection boss, the right flank a louvred exhaust (three slats on stainless steel pins through a titanium bezel, `Louvre1..3`, swinging out while firing) ahead of a pressure gauge (`Needle`), the left flank a relief valve and the fuel pump (two cylinders whose stainless steel rods stroke in turn into a bolted pump block, `PumpA`/`PumpB`). Out of the nose the nozzle runs in a perforated heat shield (hexagonal holes onto its bronze fins) between titanium collars; under its tip a pilot burner like a spark plug (a shell through a spot-faced lug, a stainless steel hex, a ceramic insulator, its jet aimed up into the stream) is fed by a thin bronze line from its back into the keel, clipped under the shield (user design: the pilot always burns and lights the stream). It is held like the minigun: the support hand on a side grip standing on a titanium arm out of the left side flat (centred on it, on a bolted flange), a round black grip in a titanium collar under a titanium cap, taken thumb up (the user first had both hands on top, the support hand on a bail over the front, but with the hands put exactly on their sockets Tensor's arm couldn't reach it in the hip carry, 116 mm off on average; the user chose the side grip, which a fit placed where the arm lands on it exactly), the firing hand on an upright grip, a pistol grip standing on the crown with its head (military red) where a pistol's frame is, carrying the trigger housing and the fuel display, tilted back to face the gunner (it faced forward at first). Its trigger was the first with the lever turned round (the old lever, its front convex and its tip hooked back, looked the wrong way round; every gun now has it): its face is concave, leaning forward from the pivot and curving back to where the index finger lies at its 36-degree curl, its tip turned forward. It cannot hook forward under the finger: Tensor's curled index fills the lever's plane from 29 to 47 mm under the pivot, the middle finger just below it (a two-way finger check found both a mirrored lever and a longer hooked one sinking in). The pack is two smaller gas cans side by side (the user replaced one big can), pitched 12 degrees nose-down, joined at their front domes by a bronze crossover pipe , on a bolted manifold yoke whose valve neck plugs up into a socket block under the keel and is held by a cross-bolt catch in a groove round it; a bronze line runs from the socket to the pump. Each can is built in its own tilted frame (`can_frame`), lifted so its lowest ring vertex is on z = 0.
  - The EMP gun's receiver has an I-beam section (it carries the muzzle's I-shaped aperture down the gun): a rubber lower flange with keel chords, a web band recessed 6 mm down both flanks (its lower edge the rubber / white split), a white upper flange and 45-degree top chamfers, each of them one height all along so every edge is one straight line from the turret's face to the rear (lines that stepped where the section narrowed looked wrong); its top is one straight incline from the turret's root to the rear (a wedge, not the lightning gun's ramp and crest), and both ends are chamfered. The front is the user's tall, thin cuboid turret, the shell carried forward on the keel's line (the bare bar looked weird), its web band deeper so that it reads as an H, and an H cut (two windows through the turret's and the flare's web, a bar of shell between) onto the waveguide inside. The waveguide is: a titanium grey block (not black) with an H section, a channel down each flank with a dark rib and screws in it, coming out of the turret only 10 cm  through a titanium seal bezel, recoiling 1 cm; on its end a lipped titanium head with the aperture, two Ys facing each other , cut through onto a lit emitter plate. The user asked for a ventilation intake with its own gizmo: a titanium door flush in a pocket on the top, hinged at its back, its front lifted 24 degrees while firing by two actuators (barrels on clevises ahead of it, rods on horns at its front corners, pinned high enough for a 24 mm lever arm round the hinge: the piston check wants 15 mm), a grille of fins under it; it breathes 3 degrees at idle. A window through the web band right over the battery (it was on the upper flange) shows the bronze capacitor, slanted exhaust slots cut the rear upper flanks, bolts sit within the web's recess and grip grooves are cut into the forend's rubber. The battery is the user's wide, flat solid-state cell (80 × 56 × 80 mm with its bumper, wider than the receiver): a white case on a rubber bumper, grip ribs and grooves, a lit gauge on its left, four bronze contact blades and a stainless steel lock post on top, plugged up into a titanium dock under the belly ahead of the trigger guard (as far forward as the support hand's palm allows) and held by a cross-bolt catch in the post's groove (the flamethrower's catch); a bronze feed runs from each side of the dock up into the lower flange, its bends rounded (`fillet()`). The stock is a rubber thumbhole frame from the receiver's rear face to the buttpad, its strut down into the grip's pommel, one width all along (it thinned toward the grip); 5.5 cm shorter than it was , so its butt meets Tensor's chest where the forend is in his other hand's reach.
  - The rocket launcher has three tubes ("3 barrels instead of 4") in a drum inside a triangular shroud (the front half of the lofted unibody triangular): three flat faces round the drum, the upper two at 30 degrees, its corners truncated and chamfered. Behind the drum it becomes the receiver: the same two upper faces and ridge carry on as its roof to the buttpad, and its flanks drop straight to the belly, so the ridge and the roof's edges are straight lines from the muzzle to the shoulder. It is red all over, the machined faces bare titanium. The index motor lies in a cradle along the ridge, its bronze pinion meshing with the ring gear through a notch across the ridge; the ring gear's bore cuts slots in the three faces, through which its teeth show. Two windows through each upper face show the tubes, the backblast slots cross the ridge over the top tube, the lock's actuator stands square on the left face at the front, the loader's cap on the lower right corner, slanted vents run down both upper flanks of the receiver (their insides metallic black) and the rocket counter stands low on the left flank (the plain sides needed "slant vents", and the flank's plate went). The drum's front plate is matte black .

  Keep the lines straight and parallel: on the lightning gun the user rejected a version whose bulged head, narrowed neck, dipping belly and wavy colour line looked "irregular, not consistent", so it has one width, a flat bottom from the nose to the stock, a straight colour split on its ledge (military blue above, titanium below, `shroud_mat`), one straight ramp up the cowl and a straight slope to the stock. Its vents are finned pockets (metallic black fins standing on the pocket's floor); it once had recessed seams and slanted vent slots (no insert behind them: `optimise()` samples only a face's corners, edges and centre, so a plate behind slots makes it delete the slots' floors and the plate's face though both show through); the user also removed lit strips along the flanks and a lit ring behind the muzzle, so keep emissive parts to what works (the emitter, the cells, the display, and at most one light on each side). Flat flanks still need detail with a job (user rule, "the sides look very plain"): the lightning gun's carry a recoil buffer (a lug on the barrel out through a slot drives a stainless steel rod into a damper on the flank, so it moves with the recoil), a charge regulator's cap (boss, bronze bearing ring, stainless steel hub and nut, its lit ring the side's one light), (the user removed plain black armour and data plates, "they look like patches", and a raised bezel round the vents, which read as a pale rectangle over them). Raise displays as consoles standing on the body, not pockets in it (user rule). Make an ammo pack a designed module, not bare cells (user rule: two big cylinders read as AA batteries, and an open caddy of cells was not it either): the lightning gun's is an enclosed power module, a lofted shell between black bumpers on runners, a screwed cover with a vent grille cut into the shell, grip ribs, a pull loop, and a charge gauge and test button on its back facing the gunner. Ahead of the shroud the mechanism is exposed, a rail section like a railgun's (the user liked it and asked for it back), made as heavy as the forend (two small coils on thin rails read as a fiddly claw on a big body): a hexagonal end plate on the nose, three coils with hexagonal titanium flanges and bronze windings, the tri-point collar and the muzzle block (both spiders of lobes, `star()`), on two black rails bearing on the hexagons' flat sides, bronze-lined and bolted into the plates; two black feeds leave bronze glands in the cowl's ramp, rest along the forend's top and drop square onto the rear coil's winding (a tube's line may not sink into a part, and each end must sit square on a surface: start a cable on its gland's face). The stock is a metallic black octagonal tube into a black upright, a titanium lock collar at it, a black strut under it. Plates can take `bevel=` to chamfer their outline on both sides (the stock, the buttpad, the pack's bands); a buttpad matches its stock's back face exactly and the stock's top and its opening's front edge are straight (user rule). Leave out parts the game draws itself: the user removed a glass lightning core (the game's shaders and particles make the lightning).
- **Gizmos (exported empties, invisible in game):**
  - Each muzzle gets an empty 1 cm in front of its face, on its barrel's own bone, so it turns and recoils with the barrel. It marks the hitscan origin or the projectile's spawn point, and where to spawn the muzzle flash.
  - A shell-ejection empty sits on the ejection port (the minigun; the rifle's on its right flank's port; the pistol's on the port in its housing's crown, pointing up, right and back); a backblast empty on the vent (the rocket launcher); the pistol also has `CompVent` (the compensator slots) and `HookVent` (the expansion chamber's exhaust); on the lightning gun an `ArcTip` on each prong's tip (arcs to the beam) and a `Vent` on each flank's vents (heat shimmer); on the flamethrower `PilotFlame` on the pilot's jet (forward along its axis, into the stream ahead of the nozzle: the game's small, always-on flame) and `FumeVent` on the louvred exhaust (out and down, smoke while the louvres are open); on the EMP gun `AirIntake` in the mouth the intake door opens (forward up the top's incline: air is drawn in against it) and `VentLeft` / `VentRight` on the exhaust slots, its `Muzzle` 1 cm ahead of the aperture on the waveguide's bone (the pulse's origin and the muzzle's air effects).
  - In Blender an empty's local +Y is its forward and +Z its up, so in glTF/Godot −Z is forward and +Y is up.
  - The rifle's `ScopeEye` is the sniper's eye point, 75 mm behind the optic's eyepiece on its axis, looking along it: the game moves the camera there for the marksman mode (user request).
  - Previews mark each one with a 1 cm orange diamond (`PRV_`, never exported).
- **Hand sockets (`LeftHandSocket`, `RightHandSocket`, `AmmoHandSocket`):** the animation library puts Tensor's hands
  exactly on them (a deterministic grip, not reworked clip by clip), so each is designed as a grip the arm can
  reach (see "Animation library").
  - `AmmoHandSocket` rides the ammo pack's bone (`Mag`): the support hand's grip on the pack for a reload, a wide grip
    (user, not a C cup): the palm flat on the pack's outer end (the face away from the gun; the lightning gun's pack
    is on top, so its top), the fingers spread across it (`AMMO_ACROSS`, to the right) and over its far edge
    (`AMMO_GRIP` short of it), the thumb up its front, centred along the pack, the palm resting where the pack stands
    out furthest under it (rays from the palm's footprint). `check_ammo_socket` fails the build if the palm sinks into
    the pack or sits more than 1.5 mm off it, or, with the pack released (`MAG_TRAVEL` out), sinks into the gun (the C
    grip on the flank first tried did, on the pistol, the EMP gun and the lightning gun). Its entry in `_rig.json`
    (`ammo_hand_socket`) has the grip pose too (`AMMO_GRIP_POSE`, spread).
  - Each socket's glTF/Godot basis is the character's `Hand` bone basis for that grip, and its origin is the wrist pivot. Blender's exporter keeps a bone's axes but converts an empty's (+Y to −Z, +Z to +Y), so in Blender the empty's local axes are (X, −Z, Y) of the bone frame.
  - In Godot, set the hand bone's global pose to the socket's transform and solve the arm. Alternatively, carry the gun in the right hand with `gun = hand_bone_global * RightHandSocket_local.inverse()`.
  - Tensor's hand frame: X along the knuckle line (the left thumb on −X, the right on +X), Y from the wrist to the knuckles, Z out of the palm. The palm is 0.09 wide, its face 16 mm off the bone line, and it spans 0.01–0.104 m from the wrist.
  - The grip's axis runs across the palm, far enough from the wrist that the curled fingers clear it: 0.070 m on a carry bar and on a pistol grip (there the grip sits in the palm's front half, the palm heel behind the backstrap, so the thumb can wrap).
- **Hand checks:**
  - `check_hand_sockets` puts Tensor's palm, as a box, at each socket. The build fails if the palm sinks into the gun or sits more than 1.5 mm off its grip.
  - The grip pose (`GRIP_POSE`: each finger's curl, Tensor's proximal / ×1.1 / ×0.8 split, and the thumb) is exported as `grip_pose_deg` per socket in `_rig.json`; the animation library closes Tensor's fingers to it on the grips.
  - The firing thumb wraps round the back of the pistol grip onto its far (left) side, opposite the fingers, as a real hand holds it: its first joint flexed 50° and turned −25° (Tensor's limits), the rest curled. Tensor's thumb root is only 25 mm from the wrist, so the grip's back is machined with a web relief (`WEB`) under the beavertail, where the thumb's first knuckle passes behind it; without it the knuckle sinks 5–9 mm into the backstrap. Support hands on a vertical grip wrap the same way (thumb behind the grip, tip on the far side); on a bare forend the support thumb lies along its near flank. Every gun's trigger is the pistol's small curved lever (user rule, retrofitted to the minigun, the rocket launcher and the lightning gun): the same outline and pull (12°), its face concave and its tip turned forward (the first outline, convex with its tip hooked back, faced the wrong way; the flamethrower's 13-point outline, and on the other guns a 9-point one on or inside it so it costs no triangles, in a 20 mm slot), pivoting in a block under the belly 59.5 mm ahead of and 51.5 mm above the firing hand's centre on the grip's axis, so the index finger meets it the same way on every gun (right index curl 36°), with room ahead of it for the curled finger's tip. It sits in a trigger housing (`build_trigger_housing`, or the pistol's lower frame): the guard's front bar ahead of the trigger and a bottom bar under it that ends just short of the fingers. The guard is open at the back because Tensor's four fingers lie flush along the grip's front strap, so no guard bar can join the grip without passing through a finger (the pistol's did, through the middle finger; the rifle's first bar, 1 cm longer, into the middle finger too). A gun still needs a guard (user rule); the user rejected an arm running on down to the pommel.
- **Holding:** Tensor holds a weapon through the animation library (see "Animation library"): the weapon hangs
  from his firing hand by its RightHandSocket, the support hand is exactly on its LeftHandSocket, in every movement
  of its family.
  Grips are designed for that: a support hand on a vertical grip takes it thumb up (the minigun's side grip hangs from
  an arm square out of the receiver's upper left face, down past the motor on the lower one, user: downwards so the gun
  takes less height; the rocket
  launcher's hangs from an arm out of its left flank; the flamethrower's stands on an arm out of its left side flat), and a support hand without a handle (the lightning gun's)
  holds the forend from below on its lower left keel chamfer, as in an FPS rifle viewmodel.
- **Actuators:** no rotation may be faked. A piston's ends turn on cross pins that visibly pass through their clevis cheeks. A cover or lock that only translates is a slide joint driven by a coaxial linear actuator (barrel on the fixed body, stainless steel rod on the moving one), so nothing has to pivot. Rods are stainless steel (`M_Joint`) and barrels matte black. Show some stainless steel rod at rest. The minigun's ejection port has a dust cover on lipped rails, pushed forward by such an actuator while firing; the rocket launcher's drum lock is a radial bolt, the rod of an actuator standing on the bearing ring between two bolted cheeks, its cross pin clear over the stroke. The lightning gun's prongs are hinges, each opened by the framework's piston across it (`PISTON_SPECS`, baked into the actions); its `build_pistons` sizes the eyes and pins to the small actuators (a pin 1 mm past each cheek), the barrel's eye sits in a slotted lobe of the tri-point collar (the lobe's two sides are its cheeks), the rod's in a yoke on the prong far enough forward that it never swings into the muzzle block.
- **Coupled rotors:** a gear pair is a coupled joint. The weapon's own `expand()` derives the driven gear from the driver, `pinion = −ratio × carrier` for an external mesh, for states and animation keys alike. Straight-flanked teeth interfere on a small pinion. `check_gears` sweeps one tooth pitch in 0.25° steps on the exact outlines and fails on any contact, even pairs that touched at rest (check_motion skips those). The minigun's 18/6 pair uses stub teeth (addendum 0.7 m, dedendum 0.9 m, 34 % thickness) and clears by 1.5 mm; the rocket launcher's 24/8 pair the same teeth, clearing by 1.0 mm (the minigun's by 0.9 mm). An indexing drum's step must end on whole teeth of both gears (the launcher's third of a turn is 8 of 24, one whole turn of its 8-tooth pinion), so every tooth is back where it was and the action can start again from rest.
- **Spinning actions:** keys go on every frame (linear) and every per-frame step stays under 180°, so the engine's slerp between samples turns the right way.
  - `spin_up` ramps speed as 1 − (1 − u)⁴ and `spin_down` as (1 − u)². Both end every rotor on whole turns, so `spin_up` → `fire` (loop) → `spin_down` chain without a jump.
  - A weapon with nothing spinning still idles: the lightning gun's prongs breathe 3° open and shut over 2 s (`idle`, looped) and flicker ±1.2° while firing, each at a whole number of cycles per loop so every loop starts and ends where the next action begins.
  - The minigun fires at a rotor rate of 10°/frame, looping in 36 frames (one turn: each barrel fires once as it passes the top, 6 frames apart, so its 1 s recoil is home before it fires again; a six-fold rotor looks the same at any rate 60° per frame apart). `spin_up` takes 45 frames and `spin_down`, its speed falling straight to rest, 72, each a whole turn.
- **Barrel recoil:** every barrel, as it fires, recoils 1 cm back into the body and returns, over 1 s (user rule: 1 cm, not more): 0.5 s back (fast, then slowing) and 0.5 s home (smoothstep). The rifle's is short recoil too (an automatic's barrel cannot take 1 s per shot at 600 rounds a minute): it rides the bolt carrier's first centimetre, locked to the bolt face, and the carrier brings it home (`Barrel` = min(`Bolt` as fired, 1 cm)); the charging handle pushes the carrier back by its lug without moving the barrel (`Bolt` = max(`Bolt`, `Charger`)). A pistol's is short recoil, as the user asked for a real pistol's action: its barrel rides the slide's first centimetre locked to the breech face and stops there while the slide runs on, and the slide brings it home, the whole cycle in about 0.3 s (`expand()` derives `Barrel` = min(`Slide`, 1 cm)). Its hammer is coupled to the slide the same way: at least as far back as the slide cams it (`hammer_cam()`), so it rides home on the slide's rear face. Each barrel is its own slide bone on its carrier (the minigun's `Barrel1..Barrel6`, the launcher's `Tube1..Tube3`), its muzzle gizmo on it. It slides in bores in phase with it, and is held in them at both ends at rest, never ending in thin air: the minigun's barrels run in a blind bore in their breech collar (5 mm in at rest), the front collar and the muzzle clamp, all a sliding fit (0.05 mm, same polygon phase, so the bores' walls cull); the launcher's tubes run in the front plate's bores and in counterbores in the breech plate. The flamethrower's nozzle pulses the same way through its 30-frame `fire` loop, sliding in the body's bore and the heat shield's front collar. The lightning gun's barrel runs in a blind bore in its shroud and in the coils', the collar's and the muzzle block's bores; firing its continuous beam, it pulses back once a second (one recoil per 30-frame `fire` loop), and its orb shot (`fire_orb`) recoils once. Fully back, a barrel stops short of the bore's floor. A recoil longer than the gap between one barrel's shots overlaps the next: the minigun fires every 6 authored frames and loops in 36, so its fire loop starts with earlier shots still settling, and `fire_start` (the first pass, no earlier shots) leads into it; `spin_down` lets the last ones settle. KYLR's gameplay fires at four shots per second, so game playback retimes this authored loop to preserve barrel order and event sync.
- **Projectiles:** the projectile is its own asset in the same `model.py`, built by swapping its spec in (`rocket_spec()`: its joints, actions and preview states replace the launcher's for its build), so the framework's rig, action and check code serves it unchanged; it has its own rig, checks, cull and export (`<name>_rocket.glb/.fbx`), its origin at its tail and its nose −Y. Give no bone of the weapon the name of one of the projectile's: the glTF exporter exports every action whose channels match, so a clash leaks the weapon's action into the projectile's file. The loaded round that leaves is its own bone: `fire` runs it up its tube and scales it to 1e-3 (constant keys, still invertible) on the frame the game spawns the projectile at the muzzle gizmo (`_rig.json` gives the frames). The rocket's four fins lie folded forward in slots in its tail and flip out 95° on stainless steel pins across the slots (`deploy`).
- **Detachable pack:** a slide joint, `Mag`, whose travel is only the length it stays on its rails (the guide check needs contact over the whole travel). Past that the game detaches it. A hinged latch hooks a notch in it. The pack is its own model (break the packs out): `<name>_ammo.blend/.glb/.fbx`, unskinned, its origin at its bottom centre, square to its own axes (the flamethrower's cans levelled, the lightning gun's module untilted), its real size; the weapon's own files carry no pack mesh but an `AmmoMount` gizmo on `Mag`, the model's frame where it rides, so the game (and the previews, videos and showreels, which bring the model in) parent it there unmoved and it follows the pack's actions. The same model is the ammo pickup. FPV pins the weapon to the bottom-right camera view; TPV attaches its `RightHandSocket` to the robot’s firing hand. Weapon assets carry no camera gizmo.
- **Collision models (`collision.py`, after model.py; model-agnostic, copied unchanged into each weapon's folder and
  the gameplay props', with an asset's own colliders in an optional `collision_extras.py`, see "Gameplay props"):**
  ultra low poly colliders for the game (100–500 triangles by the geometry's complexity, the fewer the better,
  losing no geometry). `<name>_col.glb/.fbx` holds a collider mesh for each of the weapon's meshes (`SK_<Mesh>Col`:
  `SK_RifleCol` and `SK_RifleOpticCol`, so the optic's goes with it) on the weapon's own skeleton, with its actions;
  the ammo pack's (`<name>_ammo_col`, unskinned, in the pack model's frame: hang it on `AmmoMount`, also the
  pickup's) and the projectile's (`<name>_rocket_col`, on the rocket's own rig) are separate, as their models are
  . Each collider is a set of convex pieces, each a closed island rigidly weighted to one bone, so the engine
  can make one convex shape per piece. They are built from the render mesh at rest: a bone that moves under 12 mm
  against its parent over its joint's range and every action (a barrel's recoil, a trigger, a latch) joins its
  parent; each part's convex hull is split (up to 8 levels) while it stands more than the tolerance off the model
  (a point inside the solid, by winding number, counts as on it; the model is the bone's own parts and those of
  bones moving under 5 cm, since a lift down in its shaft or a hatch's shut panels fill gaps at rest that open when
  they move), neighbouring pieces of a bone merge while their hull stays within it, a piece under 5 cm across may
  join a neighbour up to three times it (many small pieces in a small area make one bounding collider), a
  piece its own or an ancestor bone's pieces cover to within half of it in every pose of its motion is dropped (a
  pinion in its cradle goes, the rocket's folded fins, which deploy, stay), and each hull is fitted with a polytope
  of supporting planes that contains it, so nothing pokes out (the build prints the worst poke-out, a few
  millimetres, and the share of the surface inside). A collider stands at most `ALLOWANCE` off its mesh (2 cm
  is fine; the hull takes half of it and the fit the other half, which leaves fewer triangles than a tighter fit),
  more only where a collider would be over 500 triangles. Previews: `<name>_col_<view>.png` (the colliders over the model,
  translucent, a colour per piece), `_col_solo_*` (alone), `_col_pose_<pose>` (in the model's test poses, following
  its bones) and `_rocket_col_*`. `-- --no-render` skips them.
- **Tessellated checks:** the weapon's `Part` ear-clips its faces before building the BVH. `BVHTree.FromPolygons` fans an n-gon from its first corner, so a concave face, such as a ring's face round its bores, claims the holes and reports contacts that aren't there.
- **Unseen-face cull (`cull_unseen_free`, after skinning, before UVs):** the props' cull with no level surface, since any ray that leaves the mesh reaches a viewer.
  - It runs over every animation frame and joint sweep.
  - It adds rings of rays square to the bore axis, because the running gaps between rotor discs are seen only edge-on.
  - Glass hides nothing, so the lit screen and the rounds behind it stay.
  - The pack is culled only against itself, because it detaches.
  - Verify it with `model.py -- --no-cull` (an unculled comparison build: it reports but does not enforce the budget) and a pixel diff of the previews.

## Adding a new asset

1. Create `models/<category>/<name>/`.
2. Copy `model.py` from `models/characters/tensor/` (characters) or `models/gameplay/item_table/` (animated props). Set `NAME` and the docstring run path, then replace the spec tables and the `build_<region>` functions. Static props can drop the rig and the pistons.
3. Copy `preview.py` unchanged. Fix only the run path in its docstring.
4. Run `model.py`, then `preview.py`. Both must exit 0 with no traceback or warning.
5. Check the result (next section).

## Verification (required after every change)

Agents must do these checks themselves rather than assume the build worked:

1. **Outputs exist**, with fresh timestamps: `.blend`, `.glb`, `.fbx`, `_rig.json` and all preview PNGs.
2. **Look at the previews**: at least `front_left`, one ortho view, every `pose_*` and one `team_*`. Check that the silhouette is in frame, and that there are no inverted normals, missing parts or stray objects.
3. **Mechanics in the poses:** hinges bend on the right axis, in the right direction, and within their limits; pistons stay connected (rod inside barrel); rotors turn with their joint.
4. **Export round-trip**: re-import each GLB and FBX in a fresh factory scene and check:
   - the objects and their dimensions (in metres), that scale is 1, and that min z ≈ 0 (props: the bounds match their placement);
   - the triangle count is within budget and the asset's documented material slots are present (Tensor: all eleven original slots above; the item table and the weapon holder: their five);
   - the bone count, humanoid bone names present (characters), no anchor bones, and for animated props every action present;
   - every vertex is weighted, with a maximum of 1 influence.

   Put throwaway check scripts in a scratch or temp directory, not in the repo.
5. Report what was checked and what failed. Don't only report success.

## Gotchas

- `World.use_nodes` and `Material.use_nodes` are deprecated in 5.x, because node trees always exist. Only set them when `node_tree is None`.
- Two bones that aim at each other create a dependency cycle. Aim at anchor bones parented to the other side instead.
- `edit_bone.align_roll(v)` points the bone's local Z at `v`. With Z = flex, +X rotation moves the tip towards `flex`.
- Mirroring a vector flips cross products. That is why the right side's Y and Z limits are negated and swapped.
- `bpy.ops.object.origin_set` / `transform_apply` / `uv.smart_project` act on the selection and active object. Select explicitly before each call.
- `obj.bound_box` is in local space and ignores the armature pose. For framing, use evaluated vertices.
- In top and bottom camera views, `to_track_quat` is degenerate. Set the rotation explicitly.
- Sun lights ignore their position. Only rotation matters.
- Blender's glTF importer adds an `Icosphere` bone-shape object on import. It is not in the file.
# Map placement assets

Map geometry ownership: only platform, bridge and lip castings and required Boolean cuts/wells belong
to the map geometry budget. Separate authored models (pillars themselves, thrusters,
sconces/battens, architecture, weapons, ammo and gameplay fixtures) never count
toward that budget: place named gizmos, then import the native assets in previews
and runtime with identity local transforms. Lunar scenery is a separate gizmo
instance. Preserve every native detail. Skyfall has a 75,388-triangle map-owned budget; other map builds
use the 25,000 default. Report imported asset counts separately.

Every sunken placement uses its native outer footprint plus **1 mm per side** in
both visual and collision Boolean cutters. Thus a 1 × 1 m fixture gets a
1.002 × 1.002 m opening. Apply the same rule to rotated/wall-mounted recesses;
do not scale the prop or move its authoritative gizmo to obtain clearance. Platform and lip cutters extend 0.5 m above the walkable surface to clear overlapping regolith, with the required pit depth retained below it. Apply cuts before separating regolith for gizmo imports.

For any placement whose asset has its own model (including pillars), export a
named gizmo and asset identity in the map, not a copy of the asset mesh. Import
the actual library model only in map previews and showcases, positioned from
that gizmo and playing its own rig/action. The gizmo's full transform is the
authoritative placement frame: align the imported model's origin and axes to
it with an identity local transform. A deliberate gameplay offset, such as the
two ammo packs on one pickup area, requires two separate gizmos with 20 cm origin spacing. A payload held
by another prop uses the prop's own exported mount gizmo, parented to its
rotating rig bone. Preview attachments must be children of that live gizmo,
with identity local transform for imported payloads; do not bake sampled mount
poses into a second locator. Keep integral raised ground, recesses,
mounting bosses, and other load-bearing architecture in the map model. Gameplay
uses the same gizmo transform to instance the separate asset.

### Native platform mounts in maps

Reusable platform, bridge and lip source helpers live in `models/maps/common/`.
They are construction helpers rather than architecture catalog assets. Map
builders retain each helper’s docking frames and light gizmos. Thruster counts
and host platforms follow the layout; native `ThrusterMountNN` positions and
axes are authoritative. Attach a separate thruster with identity local
transforms in both preview and runtime, never override XY or reshape a chassis
around the map marker. Thruster-bearing bases retain the tapered chassis;
stacked upper floors omit it. Skyfall’s lowest platform bottom is 19.7 m above
the lunar surface, with deck tops at 22/26/30 m.

All thruster-bearing platform underbodies extend uniformly 1.5 m below the 0.8 m deck underside: their nominal total depth is 2.3 m. Preserve native mounting socket frames when regenerating them.

Cradle payload origins and all axes align to the native `ItemMount` gizmo, parented to `ItemSocket`, with identity local transforms. Occupied cradles hold the native `close` pose; empty cradles use `open`. On respawn, close the claws before showing the payload. Previews and showcases use the same occupied pose.

Native mechanical architecture placements: use `pillar_platform` only below the pillar, and sample the native ram extension to meet the next floor underside. Use `weapon_holder_wall` for raised holder placements; its native `WeaponHolderMount` owns the holder aperture and axes. These are separate gizmo imports in populated previews/runtime, excluded from map-owned triangles.

Material classifiers are explicit per-model MATERIAL_CLASSIFIERS declarations using _Metallic, _Glass, _Emissive and _Diffuse suffixes. Export preparation applies those names while preserving colours, textures, geometry and animation. Only _Metallic and _Glass receive environment reflections in the game; _Glass selects the purchased glass shader with authored tint and opacity. Architecture and map castings are diffuse except their explicitly authored glass/emissive surfaces. All core outer glass surfaces use 25% opacity. Material-only regeneration reuses validated geometry and performs GLB/FBX delivery round trips without preview renders.

## Tensor upper-body assemblies

The Tensor generator exports six interchangeable `SK_TensorUpperBody<Variant>`
meshes: `default`, `aegis`, `lamellar`, `vesper`, `conduit` and `reactor`.
Show exactly one together with `SK_Tensor` and one head mesh. The shared mesh
contains the pelvis, limbs, neck and actuators. Each upper-body mesh contains
rigidly weighted Spine, Chest and UpperChest parts, retaining the native joint
frames, shoulder sockets, neck bearing and FlagMount interface. Existing animation
clips drive every assembly without retargeting.

Default has its raised collar, paired lamps and frontal protective bar. Aegis
uses a continuous breast casting and recessed status strip. Lamellar has four
relieved breast courses and twin finned rear radiator banks. Vesper has split
pectoral cartridges, a recessed sternum bus and paired rear canisters. Conduit
exposes its collector pipes and supported wiring through inspection windows.
Reactor has a recessed radial heat exchanger and a rear power cassette protected
by painted rails. All retain the original metallic, primary-paint and
secondary-paint material roles.

Service covers are clipped from the actual loft facets and seated in matching
pockets with 0.7 mm perimeter clearance. Their mating floor is 3 mm below the
shell; their exposed faces stand 2.5 mm proud and retain the shell's contour
breaks. Vesper's vent openings cut through those covers into deeper backing
cavities. Fasteners use the supporting facet normal. Rear radiator castings and
protective rails retain the back's facets; cooling grooves are machined into
continuous castings. Vesper's canisters have bored cradles and annular clamps.
Default retains its native cage and adds retaining fasteners to its service plate.

Run `models/characters/tensor/validate.py` in headless Blender after export. It
ray-tests the delivered GLB for shell breakthrough through Vesper's covers,
accent leakage beyond Aegis's physical panel and stray cuts below Reactor's core.

Each upper body is limited to 4,500 render triangles; shared body plus the selected
assembly must remain within the 15,000 body budget. Every head is checked against
every assembly, alongside piston, rigid connectivity, arm, clavicle and waist
clearance checks. Collider generation fits assemblies independently and exports
one collider mesh per choice. Preview metadata exposes the upper-body slot.
