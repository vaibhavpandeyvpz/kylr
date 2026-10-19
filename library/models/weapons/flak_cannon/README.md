# Flak cannon

Library-authored weapon integrated into the game. Mechanical clips and the
standalone showcase are authored here; gameplay profiles and character playback
remain game-owned.

## Design and mechanical load path

Military-orange (`#d68c16`, sRGB converted to scene-linear material inputs)
lofted shroud, receiver and lower frame; a chrome blast plate set 6 mm behind
the nose, with 1.5 mm chamfers, a uniform 5 mm primary border and a
10 mm matte-black inset before the plate; a continuous black upper
cover, matte-black contact surfaces and thumbhole stock, stainless barrels and chamber tubes,
bronze bearings/cartridges and a recessed red status strip. The asset has the double-muzzle silhouette and windowed six-tube loading assembly;
the project's palette, dimensions and manufacturing language govern the mesh.

The chrome plate keeps the broad front face's tapered lower contour; only its narrow tongue
is omitted while the black inset and primary casting retain theirs.
Four corner screws sit 7.5 mm inward from both adjacent edges at each broad plate corner, in conical
chrome seats with recessed heads and continuous anchoring shanks. Barrel
mounts sit exactly 10 mm inside the plate's side and bottom edges. This final
edge-clearance request determines the muzzle spacing and height, superseding
the earlier 50 mm / 60% placement. The separate index
module retains its shroud clearance and hands cartridges to the fixed firing
breeches through an internal transfer stage. A stepped
longitudinal upper cover contains the status strip. Chamfered loader windows
expose the chamber tubes and indexing track. Recessed shroud bolts, fitted
receiver maintenance plates, cooling slots, clamp cams, blast-face screws
and stepped recoil bearing collars correspond to actual supporting geometry.
The receiver side is continuous; no arbitrary opening crosses its bevel.
The orange body is one lofted unibody casting. Its orange window frames, receiver
hatches and recessed chrome blast plate are independently closed fitted service parts;
the black upper cover is a separate casting. Interfaces are backed or flush,
without open slits. Full-length screw shanks cross the upper interface into blind
threaded seats. The clamp cams sit on the flat inset lower service land, clear
of the window screws; the unsupported lower body screws are omitted.
Exposed guides, bearings, pins and clamps remain separate metal components.

The six internal tubes are cartridge loading chambers, carried between two bored
spiders with a mid-span clamp. They rotate on a stationary through-shaft
supported in the forward web and rear bulkhead. A housed coaxial index drive
sits in the rear shoulder. Every 120-degree index puts the next adjacent pair
of loading tubes at the lower transfer station. Each cartridge holds multiple flak
fragments; a paired discharge sends a fragment cluster through each muzzle.
The exposed tubes are therefore a loader, while the two forward barrels remain
aligned with the firing ports. Stepped cartridge seats locate the cassette rounds inside the larger loading
tubes. Turned breech throats support the fixed firing chambers and barrel guides.
A flat matte-black disc sits 10 mm behind each muzzle front, as requested,
and follows its barrel bone. It is a visual bore occluder, not a solid part.
Dark firing breech faces back the firing pair. Independent barrel slides retain 10 mm of recoil
travel in fixed guide sleeves and the bored front web.
The bronze 12-notch ring at the rear of the rotor provides a positive indexing
track: the locating pin retracts 7 mm before the four-notch (120-degree) advance,
then seats to prevent chamber misalignment under firing loads. Its guide collar
is bored into the upper spine. The validation sweep retracts it before rotation.

The detachable six-cartridge cassette has two columns of three rounds, visible
through open slots without glass. Rounds seat on the wells' floor. Paired feed
wells pass through the cassette top and dock into the receiver's transfer
channels behind the rotor, rising to the two upper reload stations. The upper
gallery clears the coaxial index motor; the separate firing pair is backed by
closed breech faces. Extracted reusable canisters remain within this enclosed
transfer system, so there is no arbitrary external ejection port. The
central grooved lock post is retained by the EMP-style mechanical cross bolt;
two inner guide keys align insertion. The cassette is a separate, level model
at its real size, with its origin at its bottom centre; it is also the eventual
ammo pickup. Detailed internal transfer/extractor mechanisms are not modelled.
The arbitrary side ejection opening and its marker are omitted; the extraction interface is deferred with the internal mechanism.
Gameplay cadence, spread, damage and ammunition are defined by the game; visual
refinements preserve those rules.

A recessed console is fastened to the rear upper slope and faces the gunner.
A plain cyan emissive screen under a glass cover follows the rocket launcher
display treatment. It has no text or status graphics; runtime display behaviour
is deferred to game work.

## Hold, rig and delivery

The generator imports the EMP gun's mesh/rig/check/export framework, not its
built scene. Its exact lower keel, firing grip, curved trigger, stock, hand
contact frames and finger pose contract are reused. The forward shroud and
loader are authored here. Weapon origin is on the pommel plane, centred along
its length; muzzles face Blender -Y / glTF +Z. Envelope is at most
0.25 × 0.75 × 0.35 m; budgets are 7,500 gun / 1,500 cassette triangles. The gun budget is an explicit
configured exception to the library’s usual 5,000-triangle weapon limit.

Bones: `Root`, `LoadRotor`, `IndexLock`, `Barrel1`, `Barrel2`, `Trigger`, `Mag`, `MagCatch`.
Markers: `Muzzle1`, `Muzzle2`, `LoaderAxis`, `LeftHandSocket`,
`RightHandSocket`, `AmmoMount`, `AmmoHandSocket`. Muzzle markers ride their
individual barrel bones. The separate cassette attaches with identity local
transform to `AmmoMount`. No camera gizmo is authored.

The rigid mesh has one full-weight bone per vertex. Build checks cover
connectivity, axes, guides, hand/palm contacts, the size envelope, coincident
surfaces and rotor/recoil/trigger/latch/cassette motion sweeps. Exported in-place clips at 30 fps are `idle`, `fire`, `mag_release` and
`mag_insert`. Fire recoils both barrels, recovers, withdraws the lock, advances
the loader 120 degrees, then seats the lock. Fire is a non-looping indexing step.
Reload releases the catch before moving the
pack and closes it only after insertion. No root movement or bone scaling is
authored. Character hold clips are
deliberately deferred; socket contact checks do not verify all Tensor motions.

## Rebuild

Run from `library/`, with the installed Blender 5.2 executable:

```powershell
& (Get-Command blender -ErrorAction Stop).Source --background --factory-startup --python models/weapons/flak_cannon/model.py
& (Get-Command blender -ErrorAction Stop).Source --background --factory-startup --python models/weapons/flak_cannon/preview.py
& (Get-Command blender -ErrorAction Stop).Source --background --factory-startup --python models/weapons/flak_cannon/collision.py
& (Get-Command blender -ErrorAction Stop).Source --background --factory-startup --python models/weapons/flak_cannon/validate_exports.py
& (Get-Command blender -ErrorAction Stop).Source --background --factory-startup --python models/weapons/flak_cannon/animate.py -- showcase
```

Generated `.blend`, GLB, FBX, rig JSON, material UV guides and studio/collider
previews stay in this folder and are ignored. Source files are the deliverable.
Inspect the hero, side, front, indexed, recoiled and cassette-out views, and
round-trip both weapon and cassette GLB/FBX before handoff. The user has now
authorized visual refinement and game integration while preserving gameplay.
