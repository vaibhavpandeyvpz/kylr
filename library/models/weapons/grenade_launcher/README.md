# Grenade launcher

Single-barrel launcher with a turned cylindrical receiver and a
separate circular grenade drum. The editable model source is `model.py`; it reuses the library's generic
geometry, rigid rig, collision checks, UV packing and export framework.

## Design

The launcher has exposed pressure plumbing, a retained drum, machined bearings
and an open shoulder brace. The lathed receiver supports a curved drum saddle,
concealed vertical magazine ways and seated unions. The
receiver and drum use M_Primary in sRGB `#746b5a`; black, titanium, stainless steel
and bronze distinguish the moving mechanisms. The side screen is emissive,
recessed and has no text. Twelve radial cooling ports pass through a stepped,
lathed stainless jacket around the intact pressure tube. Radial compression
fittings seat the bronze pipes; a recessed seal joins the fused trunnion and
receiver. The firing grip follows the lightning gun's position and size;
the support palm rests on the drum's machined underside.

Metres, forward -Y, Z up, origin on the bottom plane and centred along the gun.
Budgets: weapon 5,000 triangles, drum 1,500, grenade 500. Runtime exports are
`grenade_launcher.glb`, `grenade_launcher_ammo.glb` and
`grenade_launcher_grenade.glb`, each with FBX and Blender companions. The
identical `_rocket` aliases satisfy the existing projectile/collider pipeline.
The separate drum's origin is on its underside; the grenade's is its sealed
rear face. Generated files are ignored build outputs.

## Mechanical rig and animations

A single Barrel slide runs in a concentric trunnion. `fire` gives it 10 mm of
short recoil and returns over 30 frames. The loaded grenade moves forward and
hides on frame 4, where the game spawns the separate ballistic
projectile at Muzzle1. The FeedRam retracts 153 mm through coaxial glands and
returns to battery. Its rear guide connects into the shoulder brace; the
short-recoil envelope carries the pusher with a loaded barrel.

The circular cassette has six stations: five retained grenades and one empty
feed station corresponding to the chambered round. Witness bores expose the
rounds without glass. A spring follower advances ammunition internally;
continuous ammunition state belongs to gameplay. The
pickup represents this authored loaded state. The through-pinned cam catch
opens before the pack drops 15 mm down its concealed ways. The piston clears
the rear inspection plate before removal and closes after reinsertion.

Actions: `idle`, `fire`, `cycle`, `mag_release`, `mag_insert`, at 30 fps.
Seven rigid weapon bones; the separately authored grenade has its own fixed
GrenadeBody bone. Muzzle1, both hand sockets, AmmoMount and AmmoHandSocket
follow the library conventions. Backblast is a receiver-purge marker;
the grenade is unpowered and has no fin-deployment animation. ShellEject is a
caseless service/purge location.

## Regeneration and review

From the library repository, run Blender 5.2 headless on `model.py`,
`preview.py`, `validate.py` and `collision.py`. Run `animations/retarget.py --
'grenade_launcher/*'` before `animate.py` for the standalone, held and FPS
showcases. The generic companion scripts derive their asset name from this
folder. Check connectivity, axes, palm contacts, all action frames and joint
sweeps, budgets, UV atlases, fresh GLB/FBX round trips, rendered poses,
projectile and drum previews, collision companions and Tensor's holds.

`collision_extras.py` defines the pickup collision LOD. The four large lathed
body sections use filled outer hulls; deep receiver/barrel bores are omitted
from physics. Grip and stock openings retain normal decomposition, while the
travelling ram and chambered grenade retain their moving bones. The cassette
has a circumscribed octagonal solid drum, integral palm flat and two tangs.
Inspection ports and retained cartridges are render detail. These choices do
not change the render meshes or their animations.

The collider uses spatially ordered, lazy hull merging with the original
standoff tests. Run `collision.py -- --profile --no-render` to record inclusive
stage timings in the ignored `grenade_launcher_collision_profile.json`.
Run `validate_collision.py` for its GLB/FBX budget and motion round trips.
