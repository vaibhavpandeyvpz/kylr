# KYLR — weapons and combat equipment

This is the authoritative weapon, ammunition, recoil, damage, and weapon-pickup contract. [RULES.md](../RULES.md) owns match scoring and [WEAPON_EFFECTS.md](../WEAPON_EFFECTS.md) owns the asset/gizmo integration.

## Combat and equipment

Every robot starts with **100/100 Armor Health (AH)**. Weapon hits reduce AH according to weapon damage properties, unless an active shield splits the damage as described below. Hits never reduce EP. A robot dies **only** when AH or EP reaches zero. A weapon reports an attacker, a victim or impact, a damage event, and an elimination cause. The match system awards eliminations and assists from those events rather than from weapon-specific score code. Friendly-fire behavior is a match-type rule in [RULES.md](../RULES.md).

Every robot starts with the infinite-ammo **pistol in slot 1**. Keep every acquired weapon in acquisition order, up to **10 total weapons including the pistol**; the current catalog offers nine additional types. A new weapon equips automatically and retains every other weapon's loaded ammo and spare packs. Picking up an already owned weapon refills its loaded round/cartridge/magazine to its initial capacity without selecting it or adding a duplicate slot; reject the pickup if that loaded pack is already full. Retain its spares, subject to the per-type total cap. At the four-pack cap, one stored pack supplies the refill. Respawn clears all acquired weapons and all ammo, including ammo collected for unowned weapons.

Mouse wheel cycles the entire inventory in either direction. The configurable pistol and second-slot actions default to **1** and **2**; **3–9** select subsequent slots and **0** selects slot 10. Selection requires an owned slot and normal active control and is blocked during reload, protection and repair. Scheduled shot events finish before a requested switch. Online selection addresses inventory indices; the server checks ownership and action eligibility.

Each weapon exports animated bone-parented gizmos for muzzles, hand grips, ammo packs, and its own effects. FPV weapon framing is camera-relative and computed by the game. [WEAPON_EFFECTS.md](../WEAPON_EFFECTS.md) is the integration contract for Godot; use generated `_rig.json` data for exact transforms and event frames. Effects must follow idle, fire, reload, and projectile animations in both FPV and TPV without changing the damage or ammo rules below.

### Ammunition and reload

When an equipped acquired weapon is empty, reload automatically if a spare pack exists; otherwise equip the **previous distinct equipped weapon** if it has loaded ammo or a spare pack, and use the infinite-ammo pistol if that previous weapon is empty. Reload the previous weapon if only its spares remain. Keep every empty owned slot for later ammo collection. Finish an already accepted shot's scheduled projectile/casing events before changing its rig, even when the trigger is released after the final shot. A continuous stream finishes its already funded ammo interval before falling back.

Each non-pistol weapon uses its own ammo-pack type. Total carried ammo for a type, including the loaded pack and spare packs, is capped at **four times its initial amount**.

| Weapon | Initial ammo / amount added by one pack | Maximum total ammo |
|---|---:|---:|
| Rifle | 100 | 400 |
| Minigun | 100 | 400 |
| Flamethrower | 50 | 200 |
| Lightning gun | 50 | 200 |
| EMP gun | 50 | 200 |
| Rocket launcher | 20 | 80 |

A matching ammo-pack pickup adds its weapon's **full initial amount** only if that entire pack fits under the total cap. Otherwise reject the pickup and leave it available. Each map has designated pickup spots for **each of the six ammo-pack types**. A spot offers its assigned type; after a successful pickup it becomes unavailable for **60 seconds**, then offers the same pack again. Rifle, minigun, EMP pulse, rocket, lightning orb, and flamethrower fireball each spend **one ammo per shot/projectile**. Flamethrower primary fire and the lightning beam each spend **two ammo per second of active fire**. When the loaded pack is empty and a spare pack has been collected, **reload automatically**. A reload takes **2 seconds for every weapon that reloads**. During reload, the robot can take damage but **cannot fire either weapon**. With no spare pack, it cannot reload. **Switching weapons preserves all loaded and spare ammo. Death forfeits all acquired weapons and every ammunition bank.** Manual reload and ammo eligibility are specified below.

### Pistol profile

The pistol is a ballistic gun that fires bullets resolved by **hitscan** with a **40 m range**. It fires **four shots per second** (0.25 seconds between shots), applies **2° of recoil per shot**, and has **no secondary fire**. A valid bullet hit deals **10 base damage**: 10 AH without a shield, or 8 SH and 2 AH while an active shield can absorb its share. Each shot displays a **fast-travelling tracer with a visible tail** along the bullet path. The tracer is visual feedback; hit detection and damage occur when the shot is fired, without waiting for the tracer to arrive. It has no random weapon spread; AI aim accuracy is difficulty-dependent. It has no magazine or reload and no headshot bonus.

### Rifle profile

The rifle is ballistic and uses **hitscan** with the same **fast-travelling, tailed tracer** presentation as the pistol. Its normal range is **50 m**. It fires **four shots per second** (0.25 seconds between shots) with **2° recoil per normal shot**. A normal hit deals **10 base damage**, including a normal head hit; the tracer is visual and does not delay hit detection or damage.

The rifle's secondary action enters **sniping mode** with a **75 m range**. It uses **two shots per second** (0.5 seconds between shots) and applies **1° recoil per sniping shot**, compared with 2° for normal fire. In that mode, a body hit deals **25 base damage** and a headshot deals **100 base damage**. A headshot requires the ray to strike the equipped Tensor head variant's authored `SK_TensorHead*Col` collision object; target height alone does not qualify. The shared shield rule still splits each hit 80% to SH and 20% to AH while a shield can absorb its share. Hold secondary to remain scoped at 2.5× magnification; release to exit.

### Minigun profile

The minigun has **six rotating barrels**, fires **eight shots per second** (one shot every 0.125 seconds), and advances **one barrel position for every shot**: eight barrel-to-barrel advances per second. Consecutive shots fire from consecutive barrels in the six-barrel cycle. Each shot applies **2° of recoil**; there is **no secondary fire**. A valid hit deals **5 base damage**: 5 AH without a shield, or 4 SH and 1 AH while an active shield can absorb its share.

Its six barrels operate different stages of the firing cycle **in parallel**. One barrel fires while other barrels extract spent casings and load fresh rounds; the cycle is not completed serially by a single barrel. Its range is **50 m**. Each shot resolves its hit instantly by **hitscan**, as with the pistol. There is no random weapon spread; AI aim accuracy is difficulty-dependent. Each active muzzle has a brief tailed tracer.

### Lightning gun profile

The lightning gun's **primary fire is a continuous lightning beam** with a **25 m range**. Starting a beam applies **1° recoil once**, not again for each second it remains active. While the beam connects with a robot, it deals **15 base damage per second (1.5 AH per 100 ms without shield)**; it has no shot fire rate. With no shield, this reduces AH at 15 points per second. While an active shield can absorb its share, the beam drains 12 SH and 3 AH per second under the shared 80/20 rule.

Its **secondary fire** launches a charged electricity orb as a **travelling projectile** at **25 m/s**, at most **once every 0.25 seconds**, with **1° recoil per launch**. It travels normally through **40 m**, then begins to fall under gravity; it remains active and can still collide and deal damage beyond 40 m. A direct hit deals **25 base damage**: 25 AH without a shield, or 20 SH and 5 AH while an active shield can absorb its share. The orb launches on press when ready and has no splash or extra charge wait.

### EMP gun profile

The EMP gun fires a **direct, single-target travelling charge projectile** at **25 m/s**, at most **once every 0.25 seconds**, with **5° recoil**. It deals **15 base damage through 20 m**, then loses **3 damage per additional metre**: 21 m → 12, 22.5 m → 7.5, 24 m → 3, and **25 m → 0**. The projectile's core and shell remain fully visible through 20 m and fade linearly over the following 5 m, vanishing at 25 m. For distance `d`, damage is `15 × clamp((25 − d)/5, 0, 1)`. Measure distance at the actual collision point, including when a physics step would otherwise overshoot it.

The projectile strikes the **first robot hit collider or solid wall** along its swept flight segment, then terminates. It has no expanding hit volume, piercing or splash. Clamp its final sweep to 25 m so it cannot hit beyond its vanish distance. The cosmetic grey charge shell stays 15 cm long and 6 cm wide (half the original visual size), with a smaller emissive core; it does not grow during flight. Contacts use a transparent neutral-grey refractive charged burst. The shared 80/20 shield split still applies: an unshielded hit through 20 m removes 15 AH; a shielded hit removes 12 SH and 3 AH while the shield can absorb its share. Firing retains the shared **2.5 m/s backward recoil impulse**; an accepted direct hit retains **5 m/s horizontal push** and **1.5 m/s upward bounce** through the shared knockback controller.

### Rocket launcher profile

The rocket launcher fires a rocket projectile **once every 0.5 seconds** at **15 m/s** with **2° recoil**. It travels normally through **100 m**, then begins to fall under gravity; it remains active and can still collide and explode beyond 100 m. After each shot, its three-tube launcher rotates to the next barrel. Firing applies the shared **2.5 m/s backward recoil impulse**. A direct hit deals **50 base damage** (50 AH without a shield), with **11 m/s horizontal knockback** along rocket travel and a **4.5 m/s upward bounce**. The rocket explodes on impact at an epicenter, with splash reaching **other** robots within **10 m**. The directly struck robot takes only the 50 direct damage and one impulse, not splash from the same rocket.

Hold secondary fire to use the rocket launcher's **2.5× scope**. Keep a damageable opponent under the unobstructed reticle for **0.4 seconds** to acquire a server-authoritative lock (a configurable initial balance value). Releasing the scope, changing targets, losing line of sight, reloading or losing control resets acquisition. Primary fire captures the completed lock at trigger time; an unlocked shot flies straight. A scoped rocket launches at **20 m/s**, even if no lock was completed. A locked rocket pursues that opponent at 20 m/s with a **5 m minimum turning radius** (maximum angular change = distance travelled / 5). Solid cover still intercepts it. Target death breaks tracking permanently; it never transfers to a respawn or another robot. Guided flight suspends the normal post-100 m gravity fall while its target is alive, retaining the 20-second projectile lifetime. After tracking ends, ordinary range/gravity rules resume. Scope use changes launch speed from 15 to 20 m/s; damage, ammunition, recoil and the 0.5-second firing interval remain the same.

Splash starts at **10 base damage within 1 m** and weakens by **2 damage per additional 2 m** (equivalently 1 per metre): 2 m → 9, 3 m → 8, 5 m → 6, and 10 m → 1. For another robot at distance `d` metres from the epicenter, use `min(10, 11 − d)` for `0 ≤ d ≤ 10`, and zero beyond 10 m. Apply the shared 80/20 SH/AH split to direct and splash damage while a shield can absorb its share. Every accepted splash hit also pushes **outward from the epicenter** and upward, scaling the rocket impulse by `max(0.15, 1 − d/10)`. Solid cover blocks both splash damage and its impulse. Self-splash follows the same rule; friendly, protected and otherwise rejected hits impart no knockback.

Rocket, EMP and firing recoil share `Knockback` and the robot's collision-based velocity controller. Horizontal impulses decay at **12 m/s²**, stack up to **18 m/s**, and slide along walls; upward velocity is bounded to 18 m/s and falls under the match's effective map gravity. Movement input remains available during the push. Respawn and repair clear residual impulses. On a clear flat floor at standard gravity with no movement input, the first balance pass gives approximately **5 m rocket travel / 0.55 m bounce**, versus **1 m EMP travel / 0.07 m bounce**; actual travel depends on terrain, gravity, collisions and player input. All physical knockback values live in `ArenaTuning`.

### Flamethrower profile

The flamethrower emits a **continuous beam of fiery fumes** that eventually becomes smoke. Its **effective range is 10 m**, with a weakening tail to 15 m. Starting the stream applies **1° recoil once**, not on later damage ticks. Its damage cadence is **one tick per 100 ms**, dealing **1.5 base damage**
through 10 m. Direct damage fades linearly to zero at 15 m. Other robots take
1 base splash damage per tick within 1 m, fading to 0.2 at 5 m. A direct victim
does not take its own splash. Apply the shared shield split to every tick.

Secondary fire launches a **10 cm fireball** using the lightning orb rules: **10 m/s**, **0.25 seconds** between launches, **one ammo** and **1° recoil** per launch. It travels straight through **40 m**, then falls under map gravity; it stays active for **20 seconds** unless it hits something first. A first direct contact deals **25 base damage** with the shared shield split, at any distance, with **no damage falloff, size decay, splash, lingering burn or extra charge wait**. Secondary takes precedence over primary when both controls are held. Its explosion is cosmetic.

Direct contact uses a swept 0.17 m radius matching the visible outer beam at its endpoint; solid cover blocks it. Splash does not stack from multiple direct targets in one tick, and the smoke tail is visual only.

Every map zone has a designated pickup point for **each** of the rifle, flamethrower, EMP gun, lightning gun, and minigun. The rocket launcher pickup is generally placed on shared, contested ground rather than inside a zone. Each point is assigned a specific weapon by the map and always offers that same weapon when available. After a successful contact pickup, its device closes/retracts for **60 seconds**, then reopens with the same weapon. A closed point cannot be collected from. All map pickup points—weapon, ammo, Energy Core, and Shield Core—use the same **60-second** restock interval. Keep weapon statistics in data resources so balance changes do not alter match logic.

The library contains detachable ammo-pack models that can represent the matching pickups above. Use the ammo values in this document rather than inferring capacity from mesh size. Weapon points must show their assigned weapon and available/retracted state; ammo pickups must show their weapon type and availability.

## Resolved handling rules

- The pistol's infinite ammunition means **no magazine limit or reload**. Pistol, rifle normal fire, and minigun have no headshot multiplier; rifle sniping mode is the only defined headshot bonus. A hit on a robot's other body part uses that attack's body damage.
- Collect ammo packs for **any valid non-pistol type**, including types whose weapon has not been acquired. Reject a pickup if the full pack does not fit its type's cap. Ammo alone never grants a weapon or consumes a weapon slot. A new gun brings one full loaded pack and retains precollected spares; when four packs were banked, load one of those four to stay at the cap. Manual reload requires a spare and a loaded pack below capacity, takes two seconds, and discards the old loaded remainder when the spare is inserted. Consume the spare only at completion. A same-weapon pickup during its reload fills the loaded pack immediately and ends that reload without consuming a spare. A different new-weapon pickup ends the prior reload and preserves that weapon's ammo; ordinary manual selection remains locked during reload.
- For lightning beam and flamethrower stream, spend **one ammo at fire start** to fund up to half a second of firing, then one more at each uninterrupted half-second boundary. Releasing early forfeits unused time from that unit; restarting spends a new unit. This prevents free subsecond bursts. Lightning contact damage accrues continuously at 15/s for actual contact time. Flamethrower delivers its stated direct/splash tick immediately on eligible fire start and once per subsequent 100 ms, with that cadence preserved across short releases. No damage or visual stream continues once ammunition is exhausted.
- Holding the rifle secondary control enters sniping mode, with the asset's `ScopeEye` camera in FPV and a matching magnified aim overlay in TPV. Releasing it exits. Scope magnification is **2.5×** for the first balance pass. It changes view, rifle damage, range, and recoil, but not movement or robot visibility. An orb is fired immediately on secondary press when ready; it has no extra charge wait or splash.
- Weapon recoil is a view/weapon impulse of the stated number of degrees, with linear recovery to zero over **0.35 seconds** after the last impulse. Each impulse restarts that recovery from the accumulated pitch; recovery begins on the next simulation tick so the full new impulse is presented. The next shot can occur before recovery finishes; impulses add, but the resulting pitch is clamped to a tunable comfort cap (initially **15°**). Recoil never changes the registered shot direction retroactively. Continuous lightning/flame recoil happens once per trigger hold, as specified above.
- Secondary input is ignored for weapons without a secondary action, including while primary is held. When both controls are held on the lightning gun or flamethrower, the secondary orb/fireball takes precedence over the primary stream and uses its own **0.25-second** launch interval, independently of beam ammo consumption.
- The minigun's hitscan has a brief tailed tracer from its active barrel, like the other ballistic guns. The EMP charge mesh is cosmetic: direct hits use the normal swept ray against robot hit colliders and world cover, with 20 m full damage and 25 m vanish.
- At each 100 ms flamethrower damage tick, resolve the first collider intersecting the beam volume, then resolve existing splash around an eligible direct target. A robot already directly hit that tick takes no splash; a splash-only robot takes only the **highest** splash value from that tick, not a sum. The smoke tail has no blind, damage-over-time, or lingering hazard effect.
- For any attack with direct and area effects, a single robot receives at most the one highest applicable damage instance from that attack event unless the profile explicitly says otherwise. World geometry blocks hitscan, beam, pulse, flame, and explosion splash where it provides solid cover. The server resolves damage and ammo before the client displays confirmation.
- Rifle flashlight is an optional presentation feature of the imported asset and remains **off by default**. If exposed through Settings later, it is a local/world light with no stealth or detection effect. It cannot be used to blind opponents or alter bot perception until such a rule is authored.

Elimination should clearly identify the attacker, affected robot, and weapon or hazard where known. On death, play the death animation and **turn off all emissive parts on the robot**, including visible equipped gear; restore their normal emissive state only when that robot respawns. Hold the completed animation for one second, then remove the corpse and respawn. Falling robots leave no drops. Apply emissive state to both first-person and third-person presentation. Give the player immediate feedback for hits, damage taken, low resources, reload state, and death.

The dead robot's corpse disappears **one second after its death animation finishes**. If AH caused an ordinary death and the robot still had EP at that exact moment, **dropped Energy Cores** appear on the ground where the corpse
disappeared. Split the stored EP into chunks of **at most 10 EP**, with the final Core holding the remainder.
ProtonScatter's runtime modifier stack generates random positions within 2 m and projects them onto solid map colliders.
Select supported positions with neighboring Core centers **25–35 cm** apart, checking solid clearance and support beneath the
25 cm footprint. Keep them on the same floor; on a cramped ledge, supported positions take priority over spacing.
If no supported footprint exists within 2 m of the landing point, do not spawn Cores over void.
A fall death leaves no Cores. Each Core lasts **30 seconds** from appearance. Only living, actionable robots
with EP below 100 can collect them, adding their stored EP up to 100. If the credited killer is eligible and
within **10 m**, each Core independently flies toward that killer's body centre at **1 m/s**, following the
standing or crouched collision capsule. Otherwise eligible robots collect by contact. Stop collection when full.
This dropped Core differs from a map Energy Core: map Cores refill to 100, while dropped Cores transfer a stored amount. The dropped Core retains its native 25 cm rounded mesh, glass and spin animation. It shares the square Energy Core’s exact finished glass and emissive materials in every graphics preset; pickup models and shared finishes are prepared before matches.

### Galaxy-derived projectile weapons

Flak cannon uses Flock's ten pellets (10 damage each), 30 m/s speed, three
world bounces with 0.5 velocity retention, and its round shader/audio/hit effect.
Bio rifle uses Covid 90's deforming poison bolt, 15 direct damage and 5 damage
per second for 3 seconds; repeated poison refreshes the effect without stacking.
Grenade launcher uses Grenada's 20 m/s grenade, 9 m/s² gravity, 40 direct damage
and a 15-damage splash fading over 5 m. Bio/grenade impacts slow movement to
25% for 0.5 seconds. Pulse gun fires once per second and uses Coldcase's 10-damage, 15 m/s bolt and the
same short movement slow. The pulse gun is a team map fixture, disabled in DM.
Profiles, original shaders, audio and hit presets are bundled locally. Projectiles
use swept collision against robots and cover, with the shared shield handling.

Grenades apply no firing kickback. An accepted direct grenade hit adds 11 m/s
horizontal push along its flight direction and 4.5 m/s upward bounce. Other robots
inside the existing 5 m splash radius are pushed outward/upward, scaling that
impulse by max(0.15, 1 - distance/5). Splash damage remains 15 * (1 - distance/5);
the direct victim receives only its 40 direct damage and one impulse. Solid cover
blocks both splash damage and knockback, and protected/friendly rejected hits
receive neither. Self-splash uses the same outward impulse and damage rules.
Grenade impacts use the shared collision-based knockback controller and caps.

An accepted direct or splash hit from the grenade launcher, rocket launcher or
EMP gun can credit a subsequent fall death to its shooter. Use the victim's
last accepted damage event of the current life; a later ineligible hit removes
eligibility. Respawn clears it. Self-hits never award an opponent a kill.
Fall animation, lethal lunar contact and the no-drop rule remain unchanged.
[RULES.md](../RULES.md) owns scoring, assists and posthumous credit.

After the first ricochet, a flak fragment travels half its pre-impact distance before curving downward under 19.6 m/s² gravity scaled by match gravity. Each subsequent bounce resets the travelled distance and halves the previous allowance: a 20 m initial flight gives 10 m, then 5 m, then 2.5 m. Initial flight, three-bounce limit, restitution, damage and lifetime remain unchanged.

## Projectile and beam collision volumes

Physical projectiles sweep their full collision volume each simulation tick against map and robot colliders, including motion between frames. Authored rockets and grenades use the connected convex components of their library `*_col.glb` exports, retaining native dimensions, bone placement and current visible orientation. An opponent is hit when those volumes touch its authored collider even if the projectile centerline passes through a gap; a sufficiently large gap still permits passage. Shader-only attacks use their visible body envelope: EMP 6 x 6 x 15 cm box, flak 5 cm sphere, bio 30 cm sphere, elemental orbs 10 cm sphere, pulse a 10 cm long cylinder with a 5 cm radius, aligned along flight. Glow and trailing particles add no damage volume.

Lightning primary sweeps its 2 cm core radius; flame primary sweeps its 17 cm outer endpoint radius. The first solid contact blocks each beam. Damageable-target reticles and rocket acquisition use the same volume shapes rather than a different generous target cone. Hitscan bullets retain rays. Ricochets separate the projectile center from the contacted surface, preserving its body clearance and halving the distance allowance per bounce.

## Balance editing

`WEAPON_BALANCE.csv` records the reviewed per-mode values. Run `../library/.venv/Scripts/python.exe tools/apply_weapon_balance.py` from `game/` after editing it to update runtime weapon and map catalogs. CSV damage bases distinguish per-hit, per-pellet and per-second values; blank fire rates denote continuous fire, not the ammunition-consumption interval. Flamethrower CSV range is its full-damage reach, with the approved five-metre tail retained. Lightning damage remains proportional to actual contact time.

Flak fires twice per second with a 50 m travelled-distance cap. Bio fires four times per second at 25 m/s with a 50 m cap. Grenades fire twice per second with a 40 m travelled-distance cap. These three projectiles retain their eight-second lifetime. Both pulse-gun map variants deal 10 damage per shot.
