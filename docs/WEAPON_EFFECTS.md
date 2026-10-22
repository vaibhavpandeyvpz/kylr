# KYLR — weapon animation and effect integration

Weapon bodies, detachable ammo packs and projectiles use authored flat PBR colors, metallic strengths and roughness from the library generators. They carry no baked finish maps. Preserve glass/emission, per-face material roles, UVs and mechanical animation clips. The shared library export rule prevents baked finishes returning on regeneration.

This document is the game-side contract for attaching and timing weapon visuals. [GAMEPLAY.md](GAMEPLAY.md) defines weapon damage, range, fire rate, ammunition, and recoil; [RULES.md](RULES.md) defines match authority. Each weapon's `../../library/models/weapons/<name>/model.py` defines the asset, and its generated `<name>_rig.json` gives exact gizmo names, parent bones, transforms, animation clips, and event frames. Read the specific weapon's generated metadata before wiring it in Godot. Generated `.glb` and `_rig.json` are build outputs of the library scripts; do not edit them by hand.

## Shared attachment contract

Accepted rocket, grenade and EMP damage adds a brief local camera shake in FPV
and TPV, including direct, splash, shielded and self-blast hits. Use Shaker's
vendored 3D noise preset resources with a bounded fading envelope. Explosion
intensity falls linearly from 1 at the blast point to 0 at the blast radius,
using the robot body's center and full 3D distance, including height. EMP uses
a fixed 0.65 intensity for its directly hit target only, with a shorter envelope;
overlapping hits cannot exceed the cap (4 cm translation, 0.02 rad per axis).
Apply the cosmetic offset after Phantom Camera's base pose, and retain the
unshaken pose for weapon sight/aim queries. Never alter yaw/pitch input, recoil,
physics, damage or bot aim. Reduced decorative motion disables shake; cinematic
and menu views clear it, except the death camera retains the impact envelope.
The server replicates accepted impact feedback on the
presentation channel, so clients do not infer splash hits from distance alone.

Robot players share immutable playback animation variants by source resource,
loop policy and root-rotation filtering. Each player retains its own library,
playback clock, blending and skeleton state. Prepare a derived variant once;
never change its tracks or loop mode after sharing it. Keep the original clips
unchanged for locomotion and aim sampling. This avoids duplicating every clip
again for each robot and on every subsequent match.

Procedural projectile geometry is cached in `ProjectileResources` by complete
mesh recipe (shape, dimensions, subdivisions, and caps). Flak, bio, pulse, EMP,
and lightning shots reuse immutable meshes; their nodes retain independent
motion and lifetime. Fixed bio/pulse/lightning materials are shared. Flak fade
and color and lightning phase use instance shader parameters; mutable EMP fade
and effect palettes remain isolated. Fire-orb and exhaust
compositions reuse the library kit's mesh resources while keeping mutable materials
and particle controllers local. Never write a material onto a cached mesh:
assign a material override to the geometry instance instead.
Weapon contact effects also share fixed sphere, cylinder and quad geometry.
Their animated materials and particle process state remain per impact; curve-backed
debris trails retain their own mesh resource.

The local aim point is the first solid intersection of the camera-center ray, including TPV shoulder offset and current view recoil. All attacks converge from the authoritative muzzle toward that point; hitscan and stream traces are capped at their weapon range from the muzzle. A second muzzle-to-target trace preserves cover even when the camera can see over it. Flame presentation and its damage cone use this same aim solution; FPS presentation connects its displayed muzzle to the authoritative endpoint. Bots retain their eye-based perception/aim solution.

The character registry supplies an `aim_root` bone for upper-body aiming. Interpolate the copied `aim_down45` through `aim_up45` clips in 15-degree steps above that bone, preserving lower-body locomotion and compensating hip rotation against the authored neutral pose. Restore the underlying pose before each animation evaluation so pitch never accumulates. Reload, repair, and death retain their own poses. Advance the robot pose before sampling an accepted shot's muzzle.

Aim sample-to-bone bindings and neutral inverse rotations are cached per skeleton,
animation family and pitch interval; pitch interpolation, recoil, damage reactions
and hip compensation still use the live pose. Only the local player's pose needs
the camera-center sight query. Other robots keep their eye direction for pose
pitch, while accepted attacks retain their normal sight and muzzle collision traces.
Damage and hit feedback update immediately; nonlethal upper-body reactions are
sampled in the next regular physics pose update. Multiple hits in one tick must
not resample the entire skeleton at the reaction's zero-weight starting frame.
Damage-reaction bindings cache the idle frame's inverse rotations and positions;
only the live hit clip is sampled each frame. Baseline pose values are keyed by
weapon family and skeleton layout so weapon changes retain their authored poses.

Shield hit progress reads the current hit state each rendered frame and writes
the shader parameter only when its cached material value differs. Hit changes,
replacement materials and external parameter edits remain live. Avoid repeated
identical writes: the custom renderer invalidates its RT material cache on each
parameter write, even when the value is unchanged.

### Shared robot movement and reaction layers

Robot protection, Shield Health and accepted damage share `energy_surface.gdshader` as an overlay on the native skinned robot meshes. The vertex pass offsets the surface 5 cm along its normals; the live skeleton, selected head and animations supply the contour. No companion model, skeleton, animator, collision volume or shadow caster is added. A continuous procedural 3D pattern rotates and flows over that contour with thin emissive filaments, sparks and transparent gaps. The base robot remains visible. Depth testing preserves foreground occlusion; hiding the local body in FPV hides the effect. Spawn reveal and death clear it. Reduced Motion freezes the decorative field.

Protection and SH use the robot's current primary armor tint. A 0.2-second accepted-hit envelope uses the weapon color: lightning blue, pulse cyan, bio green, pistol/rifle/minigun yellow, grenade/rocket red, flak/flame orange and EMP grey. Hit tint temporarily takes precedence over protection tint. Damage presentation events carry the accepted weapon, and snapshots retain the latest hit weapon for remote feedback. These visuals do not alter damage, protection, expiry or hit regions.

Bots and human robots use the same body pose pipeline in FPV and TPV. The physical controller owns position, collision and yaw. A lower-body layer samples Root/Hips/leg tracks independently of the upper-body weapon animation: actual local displacement selects direction and gait, and distance travelled advances the foot cycle using the clip's authored horizontal root travel as its stride length. Imported root translation never moves the controller, and turn clips do not rotate the body a second time. Direction and gait changes preserve stride phase with a short pose blend; blocked robots settle into idle instead of running in place. Crouching and stationary turns follow the corresponding physical state.

Normal and charged jumps retain their intentional-jump state until floor contact: after takeoff, the folded-leg `jump_loop` keeps cycling through both ascent and descent, including weapon changes and firing/reloading. Passing the apex alone must not select the stretched-leg falling clip. Ledge falls use the falling pose; jump-pad launches and explosion bounces follow their external upward/downward motion. Landing and respawn reset the remembered jump cause. Stationary landings use their impact clip; moving landings blend the impact into the resumed stride. Lower-body motion continues during firing, reloading and damage. Aim is applied as a delta during fire and hit reactions so it preserves their authored upper-body motion. Accepted damage adds a short upper-body reaction without canceling firing or reloads; landing and crouch events also preserve an active upper-body weapon event. Restore both aim and reaction layers before evaluating the next pose to avoid accumulated transforms. Spawn, repair, death and results retain their full-body sequences.

Gizmos are invisible exported empties parented to named bones. Their transforms change as the weapon animates. In **Godot**, local **−Z is forward** and **+Y is up**. Read transforms from the imported gizmo or a bone attachment **at the event frame**, not from a rest-pose coordinate copied into gameplay code. Preview-only 1 cm orange `PRV_` diamonds are never exported and are not runtime effects.

| Gizmo | Parent and use |
|---|---|
| `Muzzle` or `Muzzle1..N` | On the corresponding barrel/slide bone, 1 cm ahead of its muzzle face. Origin and direction for a shot, beam, stream, pulse, orb, or rocket; spawn a muzzle flash there when appropriate. It rotates and recoils with that bone. |
| `RightHandSocket` | Root. Wrist-pivot grip frame. Attach the gun by `gun = hand_bone_global * RightHandSocket_local.inverse()`. |
| `LeftHandSocket` | Root. Support-hand wrist-pivot target; the synchronized Tensor hold animation reaches it. |
| `AmmoHandSocket` | `Mag`. Support hand's grip on the separate pack during release, carry, and insertion. |
| `AmmoMount` | `Mag`. Parent the matching `<name>_ammo.glb` pack here with no invented offset. The weapon's own exported model has no pack mesh. |

The hand sockets' `grip_pose_deg` metadata supplies the finger curls that close Tensor's hands on each grip. Use the exported character/weapon animation pair and these sockets rather than hand-placing a different grip in each view. The `AmmoMount` model is also the ammo pickup model; reload animation and the **gameplay's fixed two-second reload** must remain in sync. Pistol gameplay has infinite ammo, so its asset's `fire_empty` and magazine-swap clips are not used for ordinary pistol play.

## Animation-to-effect rule

Repair switches to Tensor's common idle pose at the exported `PlayerMount`, hiding the equipped world weapon and its collision plus the FPS rig. Release restores the same weapon and ammo inventory into the saved view. The station's authored barrier mesh uses its dedicated `repair_barrier.gdshader`: a faint shield-green membrane, stationary fine hex grid, slow rising scan and restrained rim/floor ring. Its native UV wraps the grid around the cylinder and dome, with pole fading and no vertex displacement. Reduced Motion freezes the scan. Station protection remains independent of personal SH; it appears only during protective welding/deactivation and hides immediately on interruption. Torch and downlight materials are unchanged.

- Keep **mechanics authoritative**: the server/match system determines whether a shot is allowed, ammo is spent, and a hit lands. The clip and gizmo place and time the visible effect. A muzzle flash or tracer cannot deal damage on its own, and a missed or blocked shot must not create a confirmed hit cue.
- Use the animation event/frame noted in that weapon's `_rig.json` for shot, case, backblast, pulse, and projectile spawn. Evaluate the moving gizmo transform at that frame. For a projectile, the spawned object then follows its own physics and effects; it does not remain attached to the weapon.
- **Gameplay cadence wins over source clip cadence.** Retiming, holding an idle pose, or scheduling the next clip may be needed to satisfy [GAMEPLAY.md](GAMEPLAY.md). Do not fire extra hits because an authored loop contains extra shot frames. Keep each visual flash, recoil, casing, and gameplay fire event together after retiming.
- Loop an idle animation while a weapon is equipped, including its mechanical breathing when authored. Continuous idle effects must be tied to the appropriate gizmo and equipment state; they do not consume ammo or imply a shot. On switching away, dropping the weapon, death, or match cleanup, stop or retire persistent effects. The common Tensor clips have no weapon hold: hide the equipped weapon and its collision while a common death, falling, victory, defeat, or results-idle clip plays; show it again on the next weapon-family pose. Death corpses carry no duplicate weapon. Death also turns off emissive parts as specified in [GAMEPLAY.md](GAMEPLAY.md).
- Show the same gameplay event in FPV and TPV without spawning duplicate world-visible particles for the same local shot. Remote robots use third-person weapon effects. Use short local prediction only for presentation if needed; online hit confirmation and damage come from authoritative events.
- For the local FPV observer, source flashes, tracers, beams, flames and travelling projectile visuals from the current animated camera-weapon muzzle toward the reticle's aim target. Sample its current pose before emission. World observers and TPV use the robot weapon's actual muzzle. Projectiles retain world positions, collision sweeps, damage, range and replication; offset only the local FPV visual launch and converge that path on the shared target. Retire the cosmetic offset at convergence or when showing TPV, and replicate shooter identity so clients apply it only to their own shots.

## Weapon-specific effect map

| Weapon | Idle/held state | Fire and other events |
|---|---|---|
| **Pistol** | `idle` holds its rest pose; no invented cycling motion or empty-ammo state. | `Muzzle` starts hitscan and tailed tracer, plus flash on the shot frame. Puff `CompVent` and `HookVent` on each shot. Spawn the casing from `ShellEject` on the asset's eject frame, after the slide reaches its rear position. The gameplay rate is **2/s**. The character fire clip retains aimed pistol spine, chest, neck and head poses while preserving shoulder/arm firing motion; the source rifle stance must not introduce a forward torso lean. |
| **Rifle** | `idle` and `idle_scoped` hold the rifle at rest. `Flashlight` is the lamp's movable spotlight origin; its on/off control is **not yet defined**, so do not silently turn it on for every player. | `Muzzle` starts the hitscan/tracer and flash for normal and marksman shots. `ShellEject` emits a case when the bolt carrier is fully back. `ScopeEye`, on the moving `Optic` bone, is the FPV camera point for sniping mode; after leaving the scope, restore the player's selected FPV/TPV camera mode. Normal and scoped shots obey the gameplay **4/s** rate, with 2° recoil normally and 1° when scoped. |
| **Minigun** | Rotor/spin animation and any mechanical idle state come from its asset clips. No muzzle or ejection effect runs merely because it is equipped. | Use `Muzzle1..Muzzle6` in barrel order, one firing barrel per shot; its gizmo follows rotor rotation and 1 cm barrel recoil. `ShellEject` emits cases from the upper-right port while the dust cover is open. The authored 30-fps loop has one shot every **6 frames** (**5/s**), while gameplay requires **8/s**. Retiming the firing loop to **160% authored speed** yields 0.125 s between those same ordered events; preserve spin-up/start/fire/spin-down continuity and the game's 8/s ammo/damage rate. |
| **Rocket launcher** | Show the loaded three-tube assembly without launch effects. | The currently top tube is `Muzzle1`; it flashes and `Backblast` emits upward/backward gas and smoke on the launch frame. Spawn `rocket_launcher_rocket.glb` at `Muzzle1` on the asset's **spawn frame**, after the loaded rocket advances, then let the launcher index for the next shot. On the projectile, `Exhaust` emits its motor flame/trail while flying and `Warhead` marks its impact point; play its fin-deploy animation on spawn. Gameplay permits **one rocket per 0.75 s**. |
| **Lightning gun** | Its `idle` loop makes the prongs breathe. Do not display a damaging beam during idle. | From `Muzzle`, draw the continuous primary beam after its `fire_start` cue and through `fire`; connect `ArcTip1..ArcTip3` on the moving prongs to the beam. `VentLeft`/`VentRight` may show heat shimmer/sparks while firing. Stop beam/arcs on `fire_end`. The secondary `fire_orb` spawns an orb from the current `Muzzle` transform at its orb frame. Beam damage/ammo accrue per second under gameplay rules; the orb has its separate **1 per 0.75 s** cadence. |
| **Flamethrower** | `idle` moves its gauge/pump subtly. A small `PilotFlame` remains lit **while the gun is held**, including idle, firing, and reload; turn it off when unequipped or dead. | `Muzzle` follows the pulsing nozzle and emits the flame cone from `fire_start` through sustained `fire`. `FumeVent` emits smoke/heat haze while the louvres are open, ending during `fire_end`. Damage/ammo tick **2/s** and use the gameplay range/falloff independent of particle density. |
| **EMP gun** | `idle` breathes its intake door; do not emit a damaging pulse during idle. | `Muzzle` emits the layered charge projectile and muzzle air effect on the authored pulse event. Draw cooling air **toward** `AirIntake` while the door is open, and puff hot air/shimmer from `VentLeft`/`VentRight` on each pulse. The projectile's travel, direct single-target collision, fade, damage, and **1 per 0.75 s** cadence come from gameplay rules. |

For the minigun and any other clip whose source timing differs from balance timing, verify the final **event timeline in Godot** rather than assuming the authored frame rate matches the match rule. Preserve the exact parent-bone attachment and effect direction while retiming.

## Integration checks

1. Equip every weapon in **FPV and TPV**; check the partially cropped bottom-middle weapon in FPV, hand closure in TPV, separate ammo-pack placement, camera/reticle alignment, and that effects follow animated bones rather than floating at rest coordinates.
2. Run idle, fire, stop, reload, switch, death, and respawn. Confirm that persistent flames/arcs/vents appear only in the correct states and stop when the weapon or robot state ends.
3. For each shot type, compare authoritative shot time with muzzle flash, tracer/projectile spawn, casing/backblast, recoil, ammo decrement, spatial impact sound, and visual hit feedback. Check the minigun's **eight shots per second** after retiming and the rocket's distinct launch/spawn frames.
4. Compare the weapon's source `model.py`, generated `_rig.json`, imported `.glb` hierarchy, and animation manifest whenever a gizmo, bone, or clip changes. Do not substitute guessed offsets for missing asset metadata.

## Asset and mix work

### Runtime VFX and timing

`WeaponVfx` resolves sockets on the displayed FPV gun or the world gun, with a single presentation emitter per robot. `ArenaEffects` shares card meshes and materials, uses an independent cosmetic random generator, and caps transient meshes at 160. Bullet marks are additionally capped at 64; retained weapon streams have 16 slots. Nozzle exhaust belongs to its authored fixture or live projectile and uses a fixed particle count. Socket attachments follow the animated transform and retire when that socket is hidden or freed. Surface marks retain their collision body's local transform, so they follow moving map parts. No effect creates damage or confirmed-hit feedback.

**FPV renders a camera-pinned weapon with its attached ammo pack in the middle 25% region. TPV uses the complete robot and its mounted world weapon.** Pin the weapon bounds center at 57.5% of screen width, within the 45–70% region. Frame the enlarged view model across 42–73%, using the adjacent spacers, and pull its center back toward the camera to 0.8 m. Keep its lower portion cropped below the screen, with framing from 60% to 112% of screen height so the weapon sits lower while the reticle and ammo HUD remain readable. After fitting, offset the camera weapon 10 cm backward (toward the camera) and 5 cm downward, retaining its fitted scale and muzzle convergence. Recompute framing when the weapon, viewport or FOV changes. The local body/world weapon and camera weapon are mutually exclusive. Spawn, repair, opening, death and results hide the camera weapon; other robots and visible corpses use their regular model. Copy the world weapon’s skeletal poses for firing, recoil and reload machinery, retaining the shared combat state. The camera weapon and its ammo cast no world shadows. Rifle scope mode hides the camera weapon.

Accepted shots seek to their authored event pose before sampling the muzzle. This skips pre-shot anticipation to preserve responsive gameplay, then plays the recoil/recovery. Pistol seeks frame 3 and ejects two frames later. Rifle normal fire runs at 0.4 authored speed (three source frames per 0.25-second shot); scoped fire runs at 3× speed, seeks frame 3, and ejects at frame 5. Minigun samples consecutive six-frame barrel events at 1.6 speed. Rocket fire runs at 2× speed: launch begins at frame 2 and projectile release follows two source frames later at frame 4; canceled/dead/unequipped shooters cannot release a pending rocket. Lightning orb fire runs at 1.5× speed and seeks frame 3. EMP samples its pulse-loop frame 0 at four-thirds speed. Continuous beam/flame weapon loops run at 2× source speed. Retained beam/flame meshes track endpoints every rendered frame independently of damage ticks; vent and prong accents sample at 20 Hz.

Each pistol, rifle, and minigun shot emits a very faint grey smoke puff at its active muzzle (5 cm initial diameter, 0.24-second life). The timed `ShellEject` event emits the brass casing and a smaller smoke puff together (3.5 cm, 0.18 seconds). Both puffs sample the currently displayed FPV/TPV socket, drift outward along its local −Z plus slight upward motion, and then dissipate independently in world space. They use the shared transient budget and do not build a lingering cloud during sustained fire.

| Weapon / object | Socket coverage and effect |
|---|---|
| Pistol | `Muzzle`: layered short incandescent gas flash and travelling tailed tracer. `ShellEject`: short-lived brass case. `CompVent`, `HookVent`: directional gas puffs. |
| Rifle | `Muzzle`, `ShellEject`: ballistic effects and timed case. `ScopeEye`: existing scoped camera alignment. `Flashlight`: reserved and off, as required by the gameplay contract. |
| Minigun | `Muzzle1..6`: selected by the accepted shot's barrel index before advancing it. `ShellEject`: directional cases. Animation retimed to eight shots per second; no extra shots from clip frames. |
| Rocket launcher | `Muzzle1`: launch flash from the authored firing tube. `Muzzle2/3`: indexed spare tubes, not additional firing origins. `Backblast`: gas puff along its upward/backward axis. |
| Rocket | `Exhaust`: layered authored flame envelope and vortex membranes, fitted inside a 15 cm length and 5 cm diameter behind the nozzle. Emission is 0.65; effect lights are disabled. `Warhead`: collision sweep begins at the nose. Imported mesh +Z rotates onto flight -Z. Fin deployment plays on release. |
| Lightning gun | `Muzzle`: three independently deformed arcs, with a continuous core and two outer strands, or a layered electricity orb. Secondary retains the owned fractured navy core, additive ice-blue current bands and cyan-white wake. Two library-authored curved ribbons and an independent dissolve shader provide local GPU filaments; they follow the projectile and retire with it. Primary retains two bounded surrounding emitters, converged endpoints and world-space clipping. `ArcTip1..3`: six small blue-white particles per receptor while a loaded gun is held during Active play. Switching, empty ammunition, death, repair or leaving Active play retires them. `VentLeft/Right`: heat exhaust during the stream. |
| Flamethrower | `Muzzle`: primary combines a narrow hot source, turbulent flame envelope, vortex sheets and two bounded projected flame/fume emitters, clipped to the actual solid-contact segment. Secondary launches a compact, approximately 10 cm layered amber fire orb at emission 0.8. Its separate contact pool presents spreading fuel tongues and cooling wisps. `PilotFlame`: a spark-free layered flame follows the gas-pipe gizmo toward the animated muzzle, including idle, fire and reload. It has a 9 mm radius budget and emission 0.35, ending 10% short of the muzzle. It retires on switching, death, repair or leaving Active play. `FumeVent`: outward fumes while streaming. |
| EMP gun | `Muzzle`: faint pulse flash and a neutral conductive capsule inside a softly animated induction envelope. The visual stays 15 cm long and 6 cm wide, fading between 20 and 25 m. Contacts have subdued neutral filaments and a separately expanding refractive volume. `AirIntake`: inward-moving air during the firing cycle. `VentLeft/Right`: outward puffs per pulse. |
| Shared sockets | `RightHandSocket`, `LeftHandSocket`: existing grip/arm alignment. `AmmoHandSocket`, `AmmoMount`: reload grip and separate pack attachment. Camera-relative framing is computed by the game. These are attachment frames, not particle emitters. |

Ballistic surface hits retain bounded yellow spark streaks, a brief core, smoke and ten-second randomized bullet marks, omitted on robots. Accepted damage animates the contour surface in the accepted weapon color. Lightning contacts use authored curved ribbons, a 0.4-second dissolve and an 18 cm white-blue core, capped at 16 simultaneous bursts; sustained contacts refresh every 0.12 seconds per weapon. EMP contacts keep neutral grey opacity 0.18 and emission scale 0.08, without smoke or decals. A separate expanding volume refracts and blurs the background for 1.2 seconds using alpha mixing and five mipmapped screen samples. It adds no splash damage or hit confirmation. Rocket and EMP effects retain separate reusable pools capped at 16 each; muzzle flashes have a separate 32-instance pool. Cosmetic casings are noncolliding and expire after 0.6 seconds. Authoritative servers replicate presentation events without constructing renderers.

Muzzle flashes combine four textured 3D library surfaces: an irregular outer
open flared gas envelope, a narrow inner jet, a broken annular mouth rim and
curled sheets. The outer layer widens toward its open front; the inner jet
extends through it. No sphere or disc closes that opening. The shader
wraps generated hot-gas albedo/density and matching normal/roughness detail over
the surfaces. The procedural gas atlas feathers the crown. Additive emission,
view-angle softening and texture erosion keep the flame readable without solid
primitive edges. The +X emission axis rotates onto the displayed socket's -Z;
geometry starts at that socket, depth-tests and follows its current transform.
Deleting the socket retires its flashes.

Editable `MuzzleFlashProfile` resources in `game/assets/effects/muzzle/` expose
independent outer-flame and inner-jet colors, radii and lengths, edge color,
emission and lifetime. Dimensions are metres in the weapon's socket frame;
FPV fitting retains the displayed weapon's scale. Size overrides fit the complete
envelope without mutating the shared profile. Each shot gets a new phase that
varies length, width, lobes and texture offsets, including pooled reuse. The jet
grows outward during the opening pulse; the curled envelope then erodes and fades.

| Profile | Outer length / radius | Jet length / radius | Lifetime |
| --- | --- | --- | --- |
| Pistol | 0.0725 / 0.055 m | 0.29 / 0.018 m | 0.10 s |
| Rifle | 0.105 / 0.075 m | 0.42 / 0.024 m | 0.10 s |
| Minigun | 0.15 / 0.10 m | 0.60 / 0.028 m | 0.18 s |
| Rocket launcher | 0.1425 / 0.15 m | 0.57 / 0.048 m | 0.14 s |
| Lightning orb | 0.055 / 0.055 m | 0.22 / 0.018 m | 0.10 s |

The presets keep the wide open outer cone at 25% of the full jet length; both
lengths remain independently editable.

The minigun's 0.18-second flashes overlap at its existing 8 shots/s cadence;
each retains its own phase, growth and fade. `tools/preview_muzzle_flashes.gd`
captures the actual FPV and world weapons, front openings, shape variants, growth phases and
overlap under `reports/muzzle-3d/`. Pass `-- --rt` with
`GODOT_DLSS_DIAGNOSTICS=1` for native ray-traced captures; add `--motion` for a
100-frame recording of real minigun firing. The probe checks accepted shot counts
and overlapping live instances.

Surface marks now use original procedural cavities, chips, dust and fine fractures with 64 seeded variants. The existing instance identifier, 9–16 cm footprint, surface anchor, 64-mark cap and ten-second lifetime remain unchanged; the final second fades away. Marks remain omitted on robots. No bitmap atlas is required.

Repair-station welding reuses the ballistic hit core shader and shared bounded spark pool, without damage, decals or hit confirmation. A 3.6 cm white-blue glow and a small shadowless light are children of the exported, animated `TorchTip`; 8.5 cm flashes remain anchored to that same live gizmo. Sparks emit from its current world transform and then move independently under gravity. Emission follows the asset's `effects.TorchTip.welding_frames` (12–51 and 87–126 at 30 fps within the five-second repair clip), stopping between strokes, on death/interruption, during deactivation, and outside Active play. Pulses run every 0.16 seconds within 25 m and every 0.5 seconds at 25–60 m; beyond 60 m they stop, and the local light is enabled only within 15 m. Reduced motion keeps a steady nib glow and suppresses flicker, repeated flashes and spark emission. The gripper's gizmo is not a welding nozzle.

Ordinary bullet hits, flak impacts, EMP impacts and repair welding share
`ImpactSparks` and one pool capped at sixteen bursts. Each burst batches at most
32 closed yellow cylinders in a MultiMesh, with shared immutable geometry and
material. Presets change only tracer count. Each cylinder is 1 cm in diameter,
launches at 2 m/s and grows from its source to a random maximum length between
2 and 5 cm. Arena-scaled gravity curves its flight downward; its short trail
follows the trajectory rather than remaining aligned to its launch direction. An even
spherical petal distribution gives the burst its outward flower shape. At 0.5 s
the nose stops and the tail feeds into it at 2 m/s, reaching zero length within
25 ms. Jolt sphere sweeps, with a 5 mm radius and no query margin, stop noses at
solid world geometry and authored robot hit hulls; a hit consumes the remaining
tail in the same way. The tracers cause no damage or physical impulse. Detached
welding sparks retain their launch origin as the torch moves. EMP retains its
pressure/refraction composition and flak retains its flash/dust; neither adds a
second spark emitter. Lightning, rocket/grenade debris and bio particles keep
their independent effects.

`tools/preview_shared_sparks.gd` records growth, flight and shrink phases for all
four presets under `reports/shared-sparks/`. Add `-- --rt` for Ray Reconstruction
with upscaling disabled. The fixture includes a solid floor for Jolt contacts.

Hit confirmation belongs to the accepted damage path for every weapon, including projectile, splash, EMP, lightning, and flame damage. It holds the outlined cyan reticle marks for 0.24 seconds; blocked, friendly, protected, self, and zero-damage contacts do not confirm. Incoming accepted enemy damage shows a brief soft red screen-edge tint plus a direction arc near the sightline and a wider edge bearing. The tint reduces intensity with reduced motion enabled. Directional damage feedback adds no aim deflection or confirmation sound; explosion and EMP camera shake follow the shared contract above.

The effects combine library-authored meshes, packed material textures, a dedicated flak dust atlas, procedural shaders and bounded GPU particles; they do not simulate fluid dynamics at runtime. Flamethrower primary integrates gas density through three closed, library-authored mesh envelopes: short hot core, full-length turbulent fuel flame and cooler outer curls. Four additional closed gas envelopes form irregular rotating flame tongues between the muzzle and half the beam length. Their width, curl, radial offset and density vary independently; their centers sit inside the beam boundary so at least half their width overlaps it. Four matching terminal tongues occupy the final 20% of the beam, with the same axial flow, rotation, wrapped material and embedded placement as the muzzle flares. Fine-scale density erodes the main flame near its end. World contacts and unobstructed ends retain a 14 cm opacity fade. Only a robot hull contact extends the rendered segment 15 cm beyond its hit point and suppresses the terminal fade, keeping the flame connected to the armor. Opaque depth still occludes gas inside the target; collision, damage and authoritative reach remain at the real surface. Each view ray samples a shared 3D density texture and wrapped generated flame albedo/density and normal/roughness maps. Density, heat and radial falloff provide depth from side, oblique and axial views without projected flame cards. Flow moves away from the nozzle at 6 m/s. The volume shader clips its ray interval against opaque scene depth and the presentation endpoint, including the robot-only 15 cm overlap and excluding the shooter. Full opacity through 8 m fades to zero at the 10 m maximum; both shader distances come from the weapon catalog. The core widens from a 3.5 cm source radius to 12 cm; outer layers widen from 5 to 17 cm. Trigger release and weapon switches hide the stream immediately. Thrusters use the same thermal family with fitted length/radius bounds and emission 0.65; secondary fireballs use emission 0.8 and pilot ignition 0.35. EMP uses a smooth capsule plus thin induction filaments, with neutral grey/silver/charcoal, shell emission 1.5 and a darker metallic core at emission 0.35. The EMP projectile retains its authored dimensions, direct collision and firing cadence. Travel and online snapshots update only opacity after 20 m and retire visuals at 25 m; pooled reuse restores full opacity. Exact vent-closing tails and complete minigun transition choreography remain animation-polish work; no spin-up firing delay is added.

Run the socket/lifecycle tests through `tools/verify.ps1`. A repeatable rendered contact sheet is available with:

```powershell
& $Godot --path . --fixed-fps 60 -s tools/preview_weapon_vfx.gd
```

It writes `reports/weapon-vfx.png` and exits. Check real matches in FPV and TPV as well: the contact sheet validates shape and shader compilation, not combat authority or camera transitions.

`tools/preview_lightning_beam.gd` captures the primary beam and its outer-strand sparkles in `reports/lightning-beam.png`. Run it with the same rendered command; add `-- --animation` for 24 frames at 12 fps.

`tools/preview_combat_feedback.gd` captures the larger flashes, a robot impact at 12 m, and the incoming-damage HUD in the assembled arena. Run it with the same rendered `--fixed-fps 60` command to write `reports/feedback-{fpv,tpv}-{pistol,rifle}.png` and `reports/feedback-incoming.png`. These are staged accepted-damage previews; use a live ten-robot match to check effect overlap and performance.

First-person presentation fits the equipped weapon and ammo pack into the bottom-middle 25% camera region. Its placement center stays pinned while the active muzzle rotates toward the actual camera-center aim target, and internal bones copy the live weapon’s firing and reload poses. Preserve the placement center through aim updates; the muzzle’s animated forward axis must point at the reticle target at near and far distances. Rifle sniping hides the view model so the opaque optic lens cannot cover the zoomed sight picture; the scope reticle stays visible. View-model placement changes neither authoritative muzzle position nor hit traces. Weapon-slot silhouettes are rendered from the copied weapon and ammo meshes by `tools/render_weapon_icons.gd`.

Establish the placement from the rear-view silhouette, then align its barrel with the reticle target each frame. The lightning gun retains its slightly lower vertical placement. All weapons share the 62.5% horizontal center anchor. Library FPV showreels use a nominal center target 20 m ahead.

Run `& $Godot --path . -s tools/preview_fpv_framing.gd` to capture each weapon at 60° FOV, plus rifle scoped, running, and firing views, in `reports/fpv-*.png`.

- The rifle flashlight stays off by default. It has no detection or blinding rule; if exposed later, it works in both camera modes without changing combat authority.
- Exact particle assets, light intensity, and quality scaling must preserve event timing and hit readability. [AUDIO.md](AUDIO.md) owns the spatial sound and callout contract; cue placement follows these gizmos.

`tools/preview_lightning_contacts.gd` renders loaded receptor sparks on the exported `ArcTip1..3` gizmos beside a repeated surface-contact burst. Run `& $Godot --path . --fixed-fps 60 -s tools/preview_lightning_contacts.gd` for `reports/lightning-contact.png`; add `-- --animation` for 24 frames at 12 fps.

## Interactive effects harness

Run `tools/weapon_effects_harness.tscn` with F6, or use
`tools/run_weapon_effects_harness.ps1`. The standalone scene reuses the real
Tensor, weapon sockets, animations, combat, audio, projectiles and effects.
Its 50 × 50 m floor has a stationary idle target at the center and a player
starting 10 m away. TPV Phantom Camera follows their midpoint from the side,
with framing based on separation, viewport aspect and height differences.
The player aims at the target automatically; head aim uses the authored
head collision hull rather than a guessed height. Mouse wheel cycles all
ten weapons, mouse buttons fire, H toggles body/head aim, T toggles target
shield, and R restores positions. Health/ammo refills and suppressed target
knockback permit repeated comparisons without changing match rules.
See the README for controls and the `--harness-smoke` verification command.

`tools/pulse_gun_bench.tscn` is a separate manual fixture bench, launched with
`tools/run_pulse_gun_bench.ps1`. The native ground-mounted pulse gun aims at a
stationary Tensor's central Spine bone, with the muzzle exactly 10 m away in
the neutral pose. The target has a random catalog head, upper body and paint;
R replaces it. Left mouse press fires one native pulse when the one-second
cooldown is ready. Holding the button never repeats firing. Automatic fixture
firing is disabled only in this authoring scene. Native aiming/piston animation,
swept collision, damage, slow status, audio and hit presentation remain in use.
Bench pulses travel at 1 m/s with a 12-second lifetime to reach the target;
match projectile settings retain their defaults. Target health refills for repeated comparisons.

Right-drag orbits, the wheel zooms, and 1/2/3 select overview, fixture and target
framing. Esc or F10 exits. Run the scene with `-- --pulse-bench-smoke` to check
distance, manual mouse input, cooldown, accepted hits, no automatic repeats and
target replacement. A rendered run also saves overview, flight and impact
captures under `reports/pulse-bench/`.

Portal fields and glow use original blue field shaders on the native skinned
field plate. Bindings, transforms, availability and Reduced Motion remain
preserved. No vertex displacement moves the field beyond its authored frame.

Fixture illumination/shadows follow the graphics preferences (enabled by default
in High and Ultra). Decorative VFX lights do not replace authoritative fixtures
or alter gameplay. See [renderer configuration](RENDERING.md).

## Shared glass and bio contact finish

All authored `_Glass` materials use the shared original thin-dielectric shader in `shaders/original/frosted_glass.gdshader`, preserving Blender diffuse tint and opacity. Core outer shells retain 25% opacity. Mild screen-space refraction, mipmapped frost and Fresnel response preserve readability; transparent layers do not write depth. This is not recursive ray-traced transmission. `_Metallic` retains its authored finish; `_Diffuse` and `_Emissive` disable specular and clearcoat while preserving diffuse/emission. Architecture and map castings use diffuse classifications except explicit glass/emissive surfaces.

Inactive EMP projectile visuals retain their two mesh nodes and per-shot materials
in a match-owned pool of at most 16 idle charges. Reuse resets the local transform
and travel fade; concurrent shots never share mutable opacity. Collision/range
retirement and online snapshot removal both return the visual. Match teardown
frees the pool. Projectile identity, collision and damage remain per launch.

Bio-rifle impact primary, secondary, core, haze and light colors are green to match the travelling projectile. Non-global light nodes remain non-illuminating under the match lighting policy.

Rocket secondary uses the scope reticle and hides the FPV model. The authoritative guided trajectory uses existing missile position/direction snapshots; scope lock feedback is replicated separately and never accepted from client input.

## Bio projectile resource sharing

Bio contact particles and core-ray particles share immutable process materials, gradient textures and draw materials keyed by their complete settings. Each projectile retains its own GPUParticles3D simulation, emission and playback state. Different sizes, speeds, colours and emission strengths must resolve to distinct recipes where those values affect the resource. The projectile-resource regression suite covers same-recipe reuse and variant isolation.

Rocket contacts use a 1.45-second spatial composition: six burning gas lobes,
six cooling soot lobes, a brief ignition core, a faint expanding pressure shell
and small tumbling hot metal fragments. Closed library meshes bound the gas;
the shader integrates density along the viewing ray and clips it against opaque
scene depth, including when viewed from inside. An immutable 64³ noise volume
supplies continuous turbulent density. Generated billow albedo/height and matching
normal/roughness maps supply soot relief and combustion breakup. Heat decays into
neutral grey smoke. Layer growth, drift and shader progress belong to each burst;
quality/distance budgets reduce integration samples while retaining complete
spherical coverage, fire, smoke and ignition. The composition is oriented back along
incoming flight and uses no camera-facing explosion cards.

Grenades use a separate 0.9-second spatial recipe: six neutral grey
dust lobes distributed around an expanding sphere, a compact ignition core, fast embers
and small tumbling metal casing chips. The dust reuses the immutable density
volume and material detail maps with its own geometry arrangement, erosion,
scattering and timing. Only a small region around the impact emits briefly;
the dust becomes non-emissive after the opening ignition. It has no sustained
burning lobes or camera-facing explosion cards. Flak uses the independent
`flak_dust_atlas.png` for compact abrasion dust. Each contact has its own reusable 16-burst pool. Grenades align +Y to the
reverse incoming flight direction, falling back to the contact normal without flight data.
Discrete presentation events replicate; damage, splash, bounce,
collision and effect-light policy are unchanged.

Fireball contacts form a compact 0.48-second 3D flare cloud. Six independently
curling, eroding flame membranes unfold outward around three faint inner gas
volumes, a short ignition core and one sparse cooling wisp. Generated flame and
smoke material sources supply linear albedo/density and normal/roughness maps,
packed by `library/models/effects/combat_effects/export_fireball_material.py`.
The flame dominates the silhouette; the contact has no billboard layer, flying
debris or lingering ground fire. Native hit position, damage and replication
retain their existing behavior.

While primary flamethrower fire contacts a robot or world surface, a smaller
version of this flare cloud loops at the actual hit point. Two retained copies
run half a cycle apart to avoid a fade gap, with subdued emission and no repeated
ignition flash. Robot hits anchor it at the end of the 15 cm visual extension;
world hits anchor it on the surface. The cloud follows the surface normal and moving contact point;
empty space, trigger release, weapon switching or loss of the stream hides it
immediately. Resuming contact reuses the same meshes and materials. It adds no
damage, impact sound or one-shot presentation events.

`tools/preview_combustion_impact.gd` captures six lifetime phases, side/back/above
views, low detail, an opaque foreground fixture, an inside view and a rotated
impact axis under `reports/rocket-3d/`. Add `--grenade` to capture the grenade
recipe under `reports/grenade-3d/`, or `--fireball` for the compact flare cloud
under `reports/fire_hit-3d/`. Pass `-- --rt` with `GODOT_DLSS_DIAGNOSTICS=1` for the native
ray-traced check. `export_rocket_cloud.py` in the library derives the packed
material maps from the tracked bitmap source. Add `--motion` to save a live
100-frame sequence at the engine's selected fixed frame rate. The maps' independent alpha channels
require lossless imports, mipmaps and disabled alpha-border repair.

Pulse contacts use a compact 3D cyan ion bloom over 0.52 seconds, with their own 16-burst pool and replicated `pulse_contact` event. A bright core, scalloped closed shell, three broken latitude bands and eight solid ion beads expand away from the contact plane. The 46 cm nominal footprint and blue cellular seams distinguish the contact; it contains no camera-facing cards. It reuses the library's immutable effect meshes with isolated per-impact shader progress. The projectile is a glowing cyan cylinder, 5 cm in diameter, with a brighter cyan core. Its nose advances from the muzzle while its tail stays there until it reaches 25 cm long; both then travel together. On contact the nose stops at the surface and the remaining length feeds into that point at projectile speed, shrinking to zero. Absorption is cosmetic and applies no additional damage. The swept cylinder follows the growing length behind its nose. Damage, cadence, energy cost and slowing behavior retain their gameplay settings.

Live bio/pulse visuals retain independent classes. Flak contacts use a brief friction flash and compact abrasion dust over 0.42 seconds, plus the shared yellow spark tracers; bio uses a 44.5 cm nominal green organic composition, including a compact outer shell and final splash; both small-particle layers stay within 1 m of the contact origin, including sprite extent and gravity. Both have independent 16-burst pools. Flak rounds use tumbling metal fragments with compact tails. `WeaponContactBurst` owns shared lifecycle and particle mechanics. `BallisticProjectile` continues to own flight, bounce, status and damage; `ArenaEffects` dispatches replicated contacts. Effect shaders live in `shaders/original/` alongside the combat shaders.

Verification covers immutable-resource sharing, per-instance fades, bounds, socket orientation, pooling and replicated contact events, with rendered raster/RT captures.

### RTX effects comparison

Run `tools/run-rt-effects-probe.ps1` with the custom engine to capture all ten primary weapons, lightning/flame secondary modes, shield hits, projectile visuals, nine contacts and five environment effects in raster and ray-traced modes. Its 43 cases also check independent instance shader parameters, unshaded colors, and opaque particle visibility/occlusion/foreground. It waits for asynchronous material compilation, checks firing/contact activity and rejects engine errors; inspect `reports/effects-*.png` for visual correctness. These sampled captures do not certify every camera, frame, multiplayer interaction or temporal artifact. The renderer must refresh invalid cached instance-transform descriptors after particle/motion-vector buffer recreation so transparent effects remain renderable on first RT activation and mode switches.

Use `-FlameOnly` for five focused cases: side framing, a side closeup, and the real FPV weapon at long range, near contact and upward aim. These captures include accepted damage and verify that the stream uses the displayed FPV muzzle.

### Armor hit overlay depth

The warm armor hit flash stays unshaded and additive. Its raster overlay is
expanded 1 mm along the live skinned surface normal to avoid coplanar depth
fighting against the RT opaque depth conversion. Depth testing remains enabled:
foreground map geometry must hide the flash. The overlay does not change the
robot's authored metallic materials, collisions, damage or hit duration.

## Robot breakup deaths

`RobotCorpse` constructs both animated corpses and `death_explode` presentation,
and owns their snapshot construction/restoration. Match logic owns expiry,
respawn, credit, flags and Energy Core drops. Rocket launcher, grenade launcher
and EMP kills select breakup; nonlethal and rejected contacts do not.

Lethal fall contact with terrain also selects breakup from the current pose,
using its own tighter upward/radial launch recipe. Ground impact consumes the
downward velocity; debris retains a quarter of horizontal movement. Void falls
retain their falling presentation. The independent `fall_impact.tscn` composition
uses the grenade cloud shader and shared immutable meshes, with six smaller
dust lobes at 45% opacity, a brief ignition core and no extra flying fragments.
Its exported dust size, opacity and duration can be tuned independently of
grenade impacts. The local impact emits the existing soft red edge tint without
an attacker bearing, and a 0.42-second bounded camera shake through the death
camera. Reduced Motion halves the tint and disables shake. Presentation events
replicate the cloud and victim feedback; none apply damage or change fall credit.
`tools/preview_robot_debris.gd -- --fall` captures the grounded breakup;
`tools/preview_combustion_impact.gd -- --fall` captures its cloud, with `--rt`
available for native ray-traced verification.

Rocket, grenade and fall-impact clouds distribute equal-sized lobes in all six
axial directions around a common centre. Both their offsets and volume radii
grow uniformly in three dimensions, giving a spherical expansion rather than
a flattened disc or an elongated jet. The incoming 3D flight direction defines
the orientation frame; surface normals supply the fallback for previews without
flight data. Low detail preserves all directions and reduces ray-march samples.
Opaque geometry clips the sphere naturally at contact surfaces. Each effect
retains its own radius, palette, smoke density and lifetime.

`RobotDebrisMesh` caches immutable bone-local render fragments from Tensor's
authored rigid skin during robot preparation. It preserves triangles, normals,
tangents, UVs and colors; each instance uses the equipped head/upper body and
its own extinguished painted materials, without protection/hit overlays.
Extinguished finishes are immutable and cached for the match lifetime; they do
not share mutable paint state with a live robot. Animated corpses use fresh
native visuals and their own animation clock, without live hit colliders.
No separate Blender animation or modified asset export is required.

`RobotDebris` groups the fragments into 15 independent assemblies: head, chest,
pelvis, and each upper/lower arm, hand, upper/lower leg and foot. Small mechanisms
follow their nearest assembly. Each body reuses the active robot's bone-local
convex collision shapes. Bodies occupy no gameplay collision layer and query
only world layer 1, so sibling debris, actors, triggers and shots ignore them.
Direct hits bias travel along incoming flight; splash uses the actual blast
position. Outward scatter, inherited movement, upward lift and seeded spin
complete the launch, with reduced EMP strength. Bodies use continuous collision
detection and match gravity. The chest supplies the death-camera focus.

Breakup has a three-second presentation interval plus the one-second cleanup
delay. Physics may continue during that delay; all pieces disappear together
at four seconds, including airborne and off-map pieces. Settling never changes
respawn or the corpse landing point used for Energy Core drops.

The authoritative snapshot includes the initial bone pose, launch recipe and
current assembly transforms/velocities. A newly receiving client starts from
that current state and simulates cosmetic physics locally. Further snapshots
do not restart debris. Final resting positions may differ between clients.
Headless authoritative servers simulate collision bodies without render
fragments. Match teardown and snapshot removal free all child bodies together.

`tests/test_robot_debris.gd` covers pose/geometry, active appearance, collision,
direction, EMP strength, replication and expiry. `tools/preview_robot_debris.gd`
captures each weapon's intact pose, flight and settled debris in a floor/wall
fixture under `reports/robot-debris/` using the custom engine.

## Effect asset pipeline

Effect meshes and procedural data textures are generated in
`library/models/effects/combat_effects/` and delivered to
`game/assets/models/effects/combat_effects/`. Runtime compositions live in
`game/scripts/presentation/vfx/original/`; their shaders live in
`game/shaders/original/` and `game/shaders/combat/`.
Keep mesh identities, atlas tile layout, RGBA data channels, UVs, bounds and
skin weights consistent through export/import. Each event keeps its own timing,
palette, geometry and particle budget. Shared geometry is immutable; animated
opacity and effect state are per instance. Persistent portal and capture fields
follow the arena presentation contract.

`tools/preview_energy_surface.gd` captures the live skinned robot with its primary protection tint, animated phase samples, seven distinct weapon-hit colors and the native green repair barrier under `reports/energy-surface/`. It defaults to native-resolution ray tracing; pass `-- --raster` for Forward+. `tools/probe_armor_overlay.gd` supplies the foreground-occlusion check using the same shader.

The weapon effects harness supports middle-mouse drag to orbit, Ctrl + wheel
to zoom, V to cycle scene/weapon/impact focus, and C to restore the side camera;
ordinary wheel input selects weapons.
`-- --harness-flame-preview` exercises orbit/zoom and captures the 3D stream
from side, oblique, raised and impact-close-up viewpoints under `reports/flame3d/`.

Editable effect bitmap sources live in `library/models/effects/combat_effects/source/`, with one Markdown prompt record per source image under `source/prompts/`. The material exporters record hashes and independent channel samples. `export_flak_dust.py` validates the dedicated color atlas without resampling.
