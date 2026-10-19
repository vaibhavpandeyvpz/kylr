# Pulse gun

Grounded pulse turret. The editable source is `model.py`; generated
Blender, GLB, FBX, rig JSON, collider, previews and video remain ignored outputs.
The base and the complete swept assembly fit a 1 × 1 m ground patch. Units are
metres; origin is ground centre, front is Blender -Y. The final render mesh is
7,474 triangles within the explicitly approved 7,500-triangle budget, with
84 manufactured parts, rigid skinning and seven material slots. Finishes match
the project's weapons: off-white and grey paint, black housing, stainless steel,
bronze bearings, black insulated conduit and cyan emission. No glass or lights
are authored; the side console and power indicators are blank emissive surfaces.

## Assembly

A fused perimeter chassis sweeps into four curved retaining bridges. Four
lofted quadrant armour shells each incorporate a tapered protective buttress;
the pillar roots start wholly inside the casing and are fused into the shell,
with a checked minimum 10 mm root-perimeter clearance before union. Their bottom
caps are completely enclosed, leaving no exposed underside or unsupported foot.
Separate wear strips, recessed indicators and compression-ended coolant loops
seat against their actual surfaces. A stationary power housing carries a bronze
slew cartridge and stainless rotor. The flared turntable includes a machined
hydraulic clevis pocket. Two single-profile yokes follow the weapon holder's carving workflow: a radiused
bearing crown, constant 76 mm flank thickness, a centred relief, and flared foot
are carved as one member. Both silhouettes, bores and recessed foot bolt patterns
share the bearing's Y = 40 mm datum. Uniform 3 mm flank bevels leave complete flat
lands under the separate bearing covers. Their back faces seat flush at X = ±198 mm.
The four retaining bridges use a constant 54 mm width throughout their swept
profiles. Guard posts use a consistent central section with shaped end transitions.

The cylindrical pulse breech has an integral recessed console land, separate
gasket, removable bezel and emissive display. Its tapered hollow accelerator
shell has sixteen radiused through-windows and two milled energy channels.
A bored stainless waveguide with integral induction cooling fins rides in two
tapered guide bushes; the forked muzzle shroud and rear finned heat exchanger
are distinct mechanical components. Rear pipes terminate in bored compression
bosses. Both rear loops use the same 8.4 mm diameter and six-sided cross-section;
parallel-transported frames preserve that section through vertical runs and bends,
with a radius assertion at every station. Each colour denotes a separate manufactured component.

The hydraulic cylinder and rod are stainless steel, with no emissive sleeve.
Elevation uses an explicitly pinned hydraulic actuator: the cylinder eye is
captured by the turntable's integrated clevis, and the rod eye by a flange under
the accelerator. The rod remains telescoped into the cylinder throughout the
0–60° sweep with more than 35 mm minimum overlap. Circular bores allow for the
inscribed radius of polygonal bearings, so shafts remain clear through rotation.
Electrical transfer through the slew/elevation joints is enclosed in the bearing
cartridges; there is no external cable spanning the rotating joints.

## Rig and animations

`Root → Yaw → Elevation → Barrel` controls full 360° yaw, 0–60° elevation and
10 mm recoil. `ElevatorCylinder` and `ElevatorRod` are additional deform bones;
two native anchor helpers drive their alignment and are omitted from exports.
The clips bake the actuator rotations, so runtime playback needs no Blender
constraints.

| Clip | Duration | Elevation | Behaviour |
| --- | --- | --- | --- |
| `armed` | 1 s | 15° | Static ready pose, yaw zero, recoil home |
| `unarmed` | 1 s | 60° | Static upward parked pose, yaw zero, recoil home |

These are named poses, without deployment transitions or firing loops. Runtime
may blend them or drive the joint channels after integration is agreed. Joint
hinges use local X rotation; the recoil slide uses local Y translation.

`GroundMount` is on Root; `AimOrigin` and `DisplayMount` are on Elevation;
`Muzzle` is on Barrel. Gizmos use Godot local -Z forward and +Y up. The runtime
contract is an autonomous zone turret that engages enemy trespassers in range;
range, acquisition, damage, fire rate and effects remain deferred gameplay work.
There is no ammunition pack.

## Regenerate and verify

Run from `library/` using the Blender 5.2 executable in `AGENTS.md`:

1. `model.py`: build, solid/connectivity checks, piston clearance, 712 motion
   states, actual-mesh symmetry and cover seating checks, swept placement,
   coplanar-face audit, visibility culling, unique UV
   atlases, GLB/FBX exports and rig metadata.
2. `preview.py` and `inspection.py`: eight studio views, pose views and close-ups
   of bearings, supports, display, coolant, accelerator and hydraulic attachment.
3. `collision.py`: project-standard collider builder with asset-specific convex
   proxies in `collision_extras.py`: 480 triangles in 13 convex pieces on four
   bones, covering 100% of the intended blocking surfaces. Mechanical piston
   bones are excluded. The 500-triangle cap requires bridging fine pockets and
   bearing reliefs; measured maximum proxy standoff is 52 mm, bounded at 55 mm
   in the source. Consult the collision report before runtime integration.
4. `validate.py`: fresh render/collider GLB and FBX imports, geometry/UV/skin,
   mounts, both pose clips, hydraulic pin alignment and muzzle kinematics.
5. `animate.py`: a short showcase video playing `armed` and `unarmed`.

Inspect the generated `pulse_gun_*_report.json` files. Visibility comparison
against the unculled mesh changes no pixel by more than six RGB levels in
current rest and pose views. A separate temporary Godot 4.7.2 project checks
render import, six deform bones, seven material surfaces, both clips and muzzle
orientation; it does not integrate this asset into the game repository.
