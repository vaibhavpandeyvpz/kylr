# Bio rifle

Bio cluster rifle. Procedural source: `model.py`, using the shared
EMP mesh/rig/check/export framework and rifle contact dimensions.

## Assembly

A dark-grey radiused lower receiver and open upper frame carry a lathed batch
pressure chamber between front and rear bulkheads. Chamfered locking shoulders,
a captured bronze seal band, an axial service spine and a recessed circular
service plug replace the broad side hatches and top cover. A compact pedestal
supports the plain green side display. Independent material regions represent
separate physical components. The barrel has turned cooling lands, protective
collars, supported longitudinal rods and a slotted nozzle jacket with an
independent liner. The separate grooved firing grip retains the rifle's wrist
contract. The skeletal shoulder stock is raised 83 mm: its buttpad's vertical
centre is 0.257 m, the receiver's centre.

The glass accumulator sits on two bored, bolted saddle castings. Green `M_Glass`
is alpha 0.10 (10% opaque), with a 2.5 mm wall, captured end closures,
seal-retaining collars and a front service plug. Its bore clears the liquid
volume. No arbitrary loose cylinder or exposed fluid touches the fittings.

The heavy feed assembly is a 7 mm diameter stainless line with 10.5 mm bend radii,
an enlarged hex compression coupling and a shutoff valve spindle/lever. Its
upper fitting terminates on a flat machined into the fixed chamber collar;
the lower fitting terminates normal to the rear valve head. The whole pressure
line stays fixed, clear of the barrel's 10 mm recoil. The lever alone turns on
`BioValve` through 0–30 degrees. The receiver service loom has two aligned glands
normal to x=-0.032 m, a centreline at z=0.218 m and x=-0.041 m, 3 mm bend radii,
and two bored screw-fastened clamps. Its route follows the receiver's side plane.

A six-cartridge detachable cassette shares the receiver's `M_Receiver` dark-grey
finish and uses six glass cartridges behind inspection slots, keyed contacts,
a grooved lock post and a guided cross-bolt latch. `bio_rifle_ammo.glb/.fbx` is an
independent pickup at real scale; `AmmoMount` carries it in weapon previews.
The weapon export contains no pack mesh.

The conceptual fluid path is cassette feed, enclosed accumulator/metering stage,
short fixed delivery line, barrel sleeve's internal coupling, pressure bore and
replaceable nozzle. One metered batch disperses multiple acid flakes together.
Capsule transfer, internal seals/valves and fragmentation mechanisms are not
internally modelled. Gameplay damage, spread, effects and ammo economy are deferred.

## Liquid shader contract

`SK_BioRifleLiquid` is a separate Root-skinned mesh in the weapon GLB/FBX with
only `M_BioLiquid`. It is a closed half-cylinder, including both end faces and
the planar free surface; optimization does not remove its submerged faces.
Its 32 triangles are included in the weapon's 5,000-triangle budget.

The free surface is Blender z=0.207 m / Godot local y=0.207 m, through the tube
axis. Radius is 0.0172 m; length is 0.181 m. The generated rig JSON supplies its
shifted centre along the weapon and the 0.5 fill fraction. Apply the liquid
shader to this mesh/material independently of `M_Glass`. The vessel supplies
collision; `collision_extras.py` explicitly gives the liquid no collider.
Glass is exported as glTF BLEND with alpha 0.10. Bubbles, refraction and slosh
are left to the requested game shader.

The pack exports `SM_BioRifleAmmoLiquid` with only `M_BioAmmoLiquid`, separately
from `SM_BioRifleAmmo`. Six closed 12-sided liquid volumes fill the vertical
cartridges to their midpoint. Each radius is 4.5 mm and its surface is Blender
z=0.117 m in weapon placement, or local z=0.047 m in the standalone pickup
(Godot y). The glass uses the same 10%-opaque `M_Glass` as the front vessel.
The case and fluid follow the same `AmmoMount` during held/reload previews.
The liquid is excluded from collision fitting. This glass pack is the user's
explicit exception to the library's general open-slot magazine convention.

## Rig and actions

Six rigid bones: `Root`, `Barrel`, `BioValve`, `Trigger`, `Mag`, `MagCatch`.
Every mechanical action keys every moving channel, so standalone playback
cannot inherit a detached pack or open latch. All clips are in place at 30 fps.

| Action | Duration | Behaviour |
| --- | --- | --- |
| `idle` | 2.0 s, loop | Machinery rests closed and seated. |
| `fire_start` | 0.267 s | Pull trigger and open feed valve. |
| `fire` | 1.0 s, loop | One 10 mm recoil cycle; restrained valve pulse. |
| `fire_end` | 0.467 s | Release trigger and close valve. |
| `mag_release` | 0.8 s | Open latch, then slide cassette out. |
| `mag_insert` | 0.8 s | Seat cassette, then close latch. |
| `reload` | 1.8 s | Complete release, hold-out and insertion sequence. |
| `valve_open` | 0.8 s | Independent valve service action. |
| `valve_close` | 0.8 s | Independent valve service action. |

`fire_start -> fire (repeat) -> fire_end` has matching mechanical boundary
states; a cluster can be emitted at `fire` frame 0. This is an animation contract,
not a configured gameplay firing rate. `mag_release -> mag_insert` preserves the
open latch at their shared boundary. Firing is expected to finish before reload.

Markers: `Muzzle`, `BioFeed`, `LeftHandSocket`, `RightHandSocket`,
`AmmoHandSocket`, `AmmoMount`. The shared hand-bone basis and rifle firing wrist
are retained. `animations/retarget.py` registers the weapon in the rifle family
with the rocket launcher's common long-gun hold and bottom reload carry. Its
53 character clips and paired weapon clips include combat, locomotion, jumps,
turns, crouching and seven aim poses from -45 to +45 degrees. Generated clips
and manifest stay under ignored `animations/target/`; nothing is copied to game.

## Rebuild

Run from `library/` with Blender 5.2:

```powershell
& (Get-Command blender -ErrorAction Stop).Source --background --factory-startup --python models/weapons/bio_rifle/model.py
& (Get-Command blender -ErrorAction Stop).Source --background --factory-startup --python models/weapons/bio_rifle/preview.py
& (Get-Command blender -ErrorAction Stop).Source --background --factory-startup --python models/weapons/bio_rifle/collision.py
& (Get-Command blender -ErrorAction Stop).Source --background --factory-startup --python models/weapons/bio_rifle/validate_exports.py
& (Get-Command blender -ErrorAction Stop).Source --background --factory-startup --python animations/retarget.py -- 'bio_rifle/*'
& (Get-Command blender -ErrorAction Stop).Source --background --factory-startup --python models/weapons/bio_rifle/animate.py
```

Generated scenes, exports, rig metadata, validation reports and previews are
ignored. `animate.py` supports `showcase`, `held`, `fps` and `--no-render`.
