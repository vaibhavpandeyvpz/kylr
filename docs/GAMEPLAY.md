# KYLR — gameplay

## Vision and scope

KYLR is a fast-paced arena shooter in which players control robots fighting other robots across multiple maps, with switchable first-person (FPV) and third-person (TPV) views. Its **game modes** are **Instant Action** and **Online Multiplayer**. Each game mode offers the **match types** deathmatch (DM), team deathmatch (TDM), capture the flag (CTF), Elimination, and Gun Game. A **robot** is any player/character in a match. A **bot** is a robot controlled by AI; a human-controlled robot is still a robot, never a bot. **EP** means **Energy Points**, the robot's power resource; **Energy Core** remains the pickup's name.

This document describes how a match should feel and what actors can do. [RULES.md](RULES.md) is authoritative for scoring, win conditions, and match state.

For implementation detail, use the [gameplay guide](gameplay/README.md): [weapons](gameplay/WEAPONS.md), [Instant Action](gameplay/OFFLINE.md), [Online Multiplayer](gameplay/ONLINE.md), [bots](gameplay/BOTS.md), and [arenas](gameplay/ARENAS.md). [AUDIO.md](AUDIO.md), [SCREENS.md](SCREENS.md), and [DESIGN_LANGUAGE.md](DESIGN_LANGUAGE.md) complete the presentation contract. [PLAYTESTING.md](PLAYTESTING.md) defines repeatable verification.

## Core match loop

1. Choose the Instant Action or Online Multiplayer game mode. Instant Action asks for a local display name if needed, then lets the player select a map and match type. Online Multiplayer requires account login, then opens a lobby where the player selects a match type and presses Play to request a server running it. The match type determines teams, spawns, objectives, and score display. A match supports 2–10 robots; an odd count is valid.
2. Before combat begins, receive a Tensor head. Instant Action assigns one randomly; Online Multiplayer uses the account's selected head. Team match types also assign one of two randomly selected team colors and distribute robots as evenly as possible between the teams.
3. Wait through the five-second spawn countdown on the fully loaded map. Then take control of a robot with a pistol (a random assigned weapon in Gun Game) and full EP, navigate the arena, collect weapons for the inventory and Energy Cores as needed, and fight for the match-type objective.
4. On death, present the robot's death, wait the one-second cleanup delay, then respawn. Rocket, grenade and EMP kills, plus lethal terrain impacts, scatter physical body assemblies for a total four-second corpse lifetime; other deaths play their authored animation and hold its final pose for one second. Elimination removes the robot on its fifth death; Instant Action ends immediately when that is the local player. The local death camera never slows simulation. Each playable spawn begins a five-second invulnerable state; a respawn preserves the robot's match head and team color.
5. Continue until the match type's configured score limit or time limit ends the match. Elimination also ends when only one robot has lives left. Show a full scoreboard with the winner, MVP, and the contributions that produced them. In Instant Action, offer **Return to Main Menu**. Online, show a **15-second** countdown to a new match on a server-chosen random map and offer **Return to Lobby** during the countdown.

The pace comes from short travel routes back to combat, clear weapon feedback, and objectives that pull participants into encounters. Movement and weapon handling should remain responsive during normal combat. Avoid unannounced movement locks or hidden scoring rules.

### Match opening

Load the complete map in its assembled play pose, with all fixtures present. Hold a **five-second movement-locked countdown** while robots deploy at their spawn points. Phantom Camera presents the local player's spawn from the robot's front-left, with obstruction checking. There is no map-rise or flythrough sequence. At five seconds, restore the saved FPV/TPV view and enable normal actions, the match clock and scoring. Initial protection is contained within this countdown; do not add another five-second walk-only sequence afterward. Active-play respawns retain their existing protection behavior.
## Game modes

**Instant Action** fills all remaining slots with AI bots. The player chooses map, match type, difficulty, robot count, goal score, and time limit. [OFFLINE.md](gameplay/OFFLINE.md) owns setup, defaults, local flow, and match start; [BOTS.md](gameplay/BOTS.md) owns AI perception, combat, resources, and DM/TDM/CTF/Elimination/Gun Game tactics.

**Online Multiplayer** uses human-controlled robots and the same DM/TDM/CTF/Elimination/Gun Game rules. Account login opens the lobby; the selected match card and Play request an authoritative server without map or match-option selection. [gameplay/ONLINE.md](gameplay/ONLINE.md) owns the player and match flow, [ONLINE.md](ONLINE.md) owns the service architecture and authentication, and [SCREENS.md](SCREENS.md) owns lobby layout and states.

### Player settings

The main menu has a **Settings** option, separate from Instant Action's match setup and Online Multiplayer's match-type selection. Settings are local player preferences and apply in both game modes; they do not change server match rules or let an online player choose a map.

[SCREENS.md](SCREENS.md) defines the Settings screen's tabs, row interactions, contextual help, Apply/Defaults/Back behavior, and presentation guidance.

| Category | Settings to expose |
|---|---|
| Controls | Rebind movement, walk modifier, jump/charged jump, primary/secondary fire, weapon switching, interactions, and **FPV/TPV camera toggle**; adjust look sensitivity. |
| Audio | Adjust master, music, effects, and interface volumes. |
| Graphics | Choose display mode, resolution, and visual-quality settings; control effects such as sprint edge blur and speed lines. |

Save preferences so they persist between sessions. Remember the most recently used **FPV or TPV camera mode** across both game modes and restore it after each five-second spawn cinematic; **FPV** is the first-run default. Also remember the last chosen **game mode** and restore its focus/selection on the Main Menu at launch, without automatically entering a lobby, starting Instant Action, or pressing Play. [SCREENS.md](SCREENS.md) defines the complete remembered-choice behavior. Settings can open during a match: Instant Action pauses the local simulation, while an online match continues and its robot remains vulnerable. Audio and accessibility options follow [AUDIO.md](AUDIO.md) and [SCREENS.md](SCREENS.md).

### End-of-match presentation

At match end, show a scoreboard for the completed map. In **DM**, the robot with the most kills wins; in **TDM**, the team with the most kills wins; in **CTF**, the team with the most captures wins. In every type, the individual robot with the most kills is **MVP**, even if their team lost. If the leading robots or teams tie on the relevant total, the one that reached that total in the **least elapsed match time** wins the tie; apply the same rule to an MVP kill tie. If score and score-reaching time both tie exactly, show a **draw** instead of choosing a winner; an exact MVP tie shows joint MVPs. Show the winner or draw, MVP result, team or individual scores, kills, deaths, CTF captures where applicable, and the elapsed time used to resolve any tie.

Instant Action leaves the results visible with a **Return to Main Menu** button. Online Multiplayer displays a **15-second** post-match countdown on the results screen and a **Return to Lobby** button, which returns to the match-type cards and rotating robot preview. If the player stays, the server begins a new match on its randomly chosen next map when the countdown ends; the new map then plays its five-second spawn countdown. If an active online DM roster drops below **two robots**, or either TDM/CTF team drops to **zero**, end that match as **Canceled** with no winner or MVP and no automatic next-map countdown.

## Player and robot controls

- The player controls one robot's movement, view/aim, firing, weapon selection, reloading, and interaction with eligible arena objects.
- Horizontal aim turns the robot; vertical aim raises or lowers its weapon. Use the asset library's additive aim poses for the supported pitch range when those animations are available.
- The controlled robot can **switch between FPV and TPV during normal play** in either game mode. FPV pins the equipped weapon and its animated machinery to the bottom middle 25% camera region, placing its center at 57.5% of screen width, with its lower portion cropped below the screen and its barrel aligned to the reticle target. TPV shows the controlled robot's full third-person model and its held weapon from behind/over the shoulder; other robots always use their full third-person models. Preserve the chosen view through death and respawn, and return to it after temporary cinematics. The view switch does not change aim authority, hit detection, recoil, weapon range, damage, movement, or interaction rules. TPV starts over the right shoulder at **2 m** camera distance, shortens its boom against walls, and shows a blocked-shot reticle when the weapon muzzle lacks a clear path. Switch views with a **0.2-second** camera blend; the reticle remains tied to the same weapon trace.
- Bots in Instant Action use the same health, movement, weapons, pickup, respawn, and objective rules as human-controlled robots. Difficulty changes their decision-making and execution within those rules.
- Default keyboard/mouse bindings are WASD movement (run by default), hold Ctrl to sprint, Space for an immediate normal jump, hold and release Q for a charged jump, hold Shift to walk, hold C to crouch, left mouse primary fire, right mouse secondary fire, 1 pistol, 2 second owned weapon, 3–9 subsequent slots, 0 tenth slot, mouse wheel to cycle all owned weapons, R reload, and V FPV/TPV toggle. Rebind keyboard and mouse-button actions, including both fire modes, in Settings. Mouse aim has no automatic target assistance.

### Movement and jumping

Before each match starts, set its **gravity value to 1.0** unless the map or a match option supplies another value. Divide powered jump heights by the gravity value, including jump-platform launches. At 1.0, pressing **Spacebar** immediately makes a normal jump powered through **1 m**; holding **Q** for **at least 2 seconds** while grounded and then releasing it makes a charged jump powered through **2 m** only while EP is **above 50%** (above 50 of 100). At **50% EP or less**, charged jump is unavailable, including a charge already in progress; normal jump remains available. Normal jump accepts input up to 0.10 seconds before landing and up to 0.08 seconds after leaving a ledge. Base jump gravity is 19.6 m/s² and all jumps retain upward velocity at the end of their powered rise, then coast naturally under gravity. The 1 m / 2 m values are release heights, not apex clamps; unobstructed apexes are approximately 2 m / 4 m at gravity 1.0. The jump-platform powered-release target is **10 m of upward travel** at gravity 1.0. [ARENAS.md](gameplay/ARENAS.md) defines its powered lift.

Default movement is **running at 2× the 3 m/s walk speed (6 m/s)**. Holding **Sprint (Ctrl by default)** while moving gives **4× walk speed (12 m/s)** only while EP is **above 50%** (above 50 of 100). Holding the **Walk modifier (Shift by default)** overrides sprint with **walking at 3 m/s**. At **50% EP or less**, sprinting falls back to running; walking remains available. Sprint visuals end when sprinting is blocked, overridden, or released. Reduced-motion Settings may turn off sprint visuals without altering speed. Spawn invulnerability still permits walking only at **3 m/s**. Ground acceleration and braking are stronger than air steering; small obstacles up to 0.4 m can be stepped onto when the raised path and landing are clear.

Holding **Crouch (C by default)** lowers the robot's collision capsule and eye height, and permits crouched movement at **2.5 m/s**. Crouching blocks jumping and sprinting. Releasing Crouch restores standing only if the full-height capsule has clearance. The animation controller selects directional walk/run/sprint/crouch clips from the actual input direction, with separate takeoff, airborne, landing, turn, fire, reload and hit responses. Aim poses remain layered over the upper body. The pistol's authored kneel transitions and curved-path locomotion play when those motions occur.

### Spawn invulnerability

When a pistol-equipped robot finishes deploying, play its authored pistol reload
animation once during protection. This is cosmetic: it spends no ammunition or
reserve pack and does not start an ammunition reload. Fit the animation into
the remaining opening countdown, or use two seconds during active-play respawn
protection. Protected walking retains its leg animation. Gun Game keeps its
assigned weapon and does not substitute a pistol for this presentation.

Every robot enters a **five-second invulnerable state** when it spawns, including respawns. For the initial roster, protection is contained in the five-second movement-locked opening countdown and ends when control begins. A respawn during active play starts its timer immediately. During active-play respawn protection, show the local player a third-person spawn cinematic that follows their robot and permits **walking only** as a gameplay action: no running, sprinting, jumping, firing either weapon, collecting pickups or flags, activating pressure plates or jump platforms, or entering portals. The camera switch is unavailable during this cinematic and does not overwrite the saved view preference. Hits against the robot deal **no damage**. Bots must ignore it as a target or opponent while the state lasts. When the timer ends, return to the player's last chosen FPV or TPV view and normal play **at the position reached while walking**, without returning to the spawn marker.

The match controller chooses a **random valid spawn point each time**. DM draws from the whole map; TDM and CTF draw only from the robot's assigned team zone. The same selection rule applies to match start, late joins, respawns, and a protected robot returned from a fall boundary. [ARENAS.md](gameplay/ARENAS.md) defines safety filtering and simultaneous-spawn handling.

### Death and respawn

At death, switch immediately to a third-person camera on the local robot. Rocket launcher, grenade launcher and EMP kills, plus lethal terrain impacts, use `death_explode`: scatter the head, torso, pelvis and limb assemblies from the current pose, with tighter EMP scatter. Pieces spin, collide with the arena and fall under map gravity; they neither obstruct combat nor damage robots. Follow the chest with the death camera and remove all debris together after four seconds, then respawn at a safe eligible marker. Other deaths show the authored death animation and hold its final pose for one second. The match, other robots, pickups, flags, and clock continue at normal speed. Start five-second spawn protection when the robot returns to play.

A robot that falls beyond the map boundary dies where it is. Its visible body continues downward in the looping falling pose; it is never moved back to a safe floor and drops no weapon or Energy Core. A carried flag returns home immediately. The local death camera follows that body until the camera reaches 25 m below the arena surface, then holds its position and keeps looking at the body as it falls away. The bottom five metres of the 50 m service pit contain black volumetric fog. The saved FPV/TPV preference returns after spawn protection; match results interrupt the death view if the match ends first.

## Combat and equipment

Every robot starts with 100 AH and 100 EP, a fixed infinite-ammo pistol, and one empty pickup slot. See [WEAPONS.md](gameplay/WEAPONS.md) for the authoritative weapon, ammo, recoil, damage, pickup, and death-drop details. [WEAPON_EFFECTS.md](WEAPON_EFFECTS.md) maps their animated asset gizmos to presentation.

## In-match HUD

[SCREENS.md](SCREENS.md) specifies the detailed HUD layout, state feedback, and match-type variants. The locations and information below are the gameplay contract it presents.

| Location | Content |
|---|---|
| Bottom left | **Shield Health (SH), Armor Health (AH), and EP**. Show SH and its remaining duration when a shield is active. |
| Bottom center | The fixed **pistol slot** and **picked-up weapon slot**, each occupied slot using a readable **side-profile weapon silhouette**, with the equipped slot highlighted. Show the equipped weapon's **loaded ammo versus spare ammo packs**; the pistol displays infinite ammo. Show reload state here. |
| World view | In **FPV**, show the held first-person weapon at bottom right, following its first-person alignment contract. In **TPV**, show the full local robot holding its weapon; do not overlay a second first-person weapon model. Neither view replaces the bottom-center slot/ammo display. |
| Top center | The current score, goal, and remaining match time. **DM** shows the controlled robot's individual score; **TDM/CTF** show the two opposing team scores, with team colors and CTF capture totals. |
| Left side | A live **top-five kills leaderboard**, ranked by individual kill count only across all robots, including bots in Instant Action. Show fewer than five entries if the match has fewer than five robots. |
| Upper right kill feed | Event messages naming **who killed whom and with which weapon**, **who died by falling off a map platform**, **who joined or left an online match** (including disconnects as leaving), and **who won**, or that the result was a **draw** or **cancellation**. Routine entries last **5 seconds** with at most four visible rows. |

Keep team identity clear in TDM and CTF, and provide flag status and location cues in CTF. Show feedback for an invulnerable spawn, low EP, damage taken, successful hits, and a blocked sprint or charged jump when EP is at or below 50%.

## EP

EP powers every robot. A robot starts a match at **100 EP**. While it is active and alive outside an active repair station, EP drains by **1 EP per second**, reaching zero after **100 seconds** without a refill. Reaching zero kills the robot and leaves no dropped Energy Core. Weapon hits do not change EP. A **map Energy Core** pickup is available to a robot only when its EP has fallen by **at least 1 percentage point** from full, to **99 EP or less**; it then restores EP to 100 and begins a fresh 100-second depletion cycle. EP does not exceed 100 or fall below zero.

Maps have designated Energy Core pickup points. On a successful pickup, the point closes/retracts and is unavailable for **60 seconds**, then reopens with a new Energy Core. Keep EP visible in the HUD and provide a clear low-EP cue. A respawn starts a fresh life with full EP.

## Armor and shield

**AH** is the robot's normal damage pool, starting at 100 with a maximum of 100. Without an active shield, weapon damage goes to AH. A map has **one Shield Core pickup**, placed on shared ground outside the zones. It can be collected when there is no active shield or the active shield has lost **at least 1 percentage point of SH** (at **99 SH or less**). Picking it up sets SH to **100** and creates or refreshes a visible electromagnetic shield around the robot for **60 seconds**. The map Shield Core restocks **60 seconds after a successful pickup**.

While the shield is active, each weapon hit allocates **80% of its damage to SH** and **20% to AH**. If the remaining SH is less than the expected 80% portion, set SH to zero; the hit still deals **only its 20% AH portion**, with no overflow to AH. Remove the shield whenever SH reaches zero, including an exact depletion. Later hits are unshielded. The shield's remaining SH also disappears when its 60-second duration ends. A successful second Shield Core pickup at 99 SH or less refills SH to 100 and restarts its 60-second duration.

### Repair stations

Each of the map's two zones has **one 2 m × 2 m repair station**. An eligible robot with **50 AH or less** can walk into an available station and stand still to start a **seven-second sequence**: **one second** to raise the energy barrier, **five seconds** of welding and repair, then **one second** to lower the barrier. The station centers and holds the robot throughout. The local player sees the full robot and welding arms through a third-person cinematic camera; this temporary view does not change the saved FPV/TPV preference. It cannot move, fire, collect items, or use portals until the barrier has fully lowered. The barrier is a station effect, **not SH**; once fully raised, it blocks incoming attacks and prevents the occupant from attacking out until it fully lowers. The robot remains vulnerable during the first second while the barrier rises. EP drain pauses for the full seven seconds. Set **AH to 100 and EP to 100** when welding finishes at six seconds; release movement control and restore the saved FPV/TPV view only after deactivation finishes at seven seconds, so the robot can walk out. The robot's personal SH and its timer are unchanged.

Stations are neutral and admit one robot at a time, including an enemy or a CTF flag carrier. After shield deactivation **finishes or the use is interrupted**, that station is unusable by anyone for the **next 60 seconds**, counted from that last use's end. This recharge is separate from the 60-second map-pickup restock. A robot at more than 50 AH, a spawn-invulnerable robot, or a second robot cannot claim a busy station. [RULES.md](RULES.md) owns interruption and match-state cases, while [ARENAS.md](gameplay/ARENAS.md) owns placement and asset markers.

## Arena design and interactions

Maps are floating, thruster-supported arenas loaded in their fully assembled play pose. Thrusters, portals, available weapon holders and item tables, and the jumbotron continue their authored idle/active motion loops during gameplay rather than freezing after the opening reveal. Typed gizmos place weapons, ammo, cores, **one repair station per zone**, spawns, portals, pressure plates, barricades, jump platforms, cameras, thruster effects, and the central jumbotron. [ARENAS.md](gameplay/ARENAS.md) is the authoritative map, prop-motion, and interaction contract.

## Implementation contracts

- Use a common participant identity for scoring: stable participant/robot ID, controller type, and team ID when the match type uses teams.
- Store the effective Tensor head and armor colors per robot for the match and the selected team colors per team when teams exist. In Instant Action, assign heads under [RULES.md](RULES.md). In Online Multiplayer, retain the selected head; DM uses saved primary/secondary armor colors, while TDM/CTF use the assigned team primary color with the library-authored contrasting secondary accent. Apply the effective appearance to third-person and relevant first-person presentation; do not reroll or change it on respawn.
- Keep combat events separate from match rules. A match controller consumes elimination, damage, spawn, pickup, and flag events and applies [RULES.md](RULES.md). Snapshot EP and the credited killer at death for any dropped Core, then place it at the corpse's final position when the corpse disappears one second after its death animation ends; do not recalculate its value during the corpse period. A falling robot drops no Core.
- Store match-type settings and balance values as data: score limit, time limit, death-animation respawn timing, weapon statistics, and arena-object settings. Store each map's assembled geometry, event state and typed placement markers and links for weapon holders, fixed-type ground ammo packs, item tables with Energy Cores or the zone Shield Cores, one repair station per zone, portal entrances/exits, match-type/team/zone spawns, pressure plates, barricades, oriented jump platforms, opening-camera views/path, thrusters with their fire/flame/fumes origins, and the central jumbotron. Preserve the uniform **60-second map-pickup restock** rule across match types; the station has its own recharge timer. Start/stop prop loops from authoritative arena state while rendering their continuous motion locally.
- Send the HUD state derived from the match controller and participant state; do not compute a second score or flag state in UI code.
- Use Godot 4 conventions and the asset library's exported names, sockets, markers, and animations when integrating models. Consult [`../../library/AGENTS.md`](../library/AGENTS.md) for asset workflow.

## Balance and verification

Use the current weapon, bot, movement, and repair-station numbers as versioned baseline data. Tune camera comfort, map travel times, effect intensity, sound mix, and bot decision weights using the checks in [PLAYTESTING.md](PLAYTESTING.md). AH has no passive regeneration or healing pickup; the per-zone repair station restores it through a seven-second interaction with five seconds of welding. Falling is the shared environmental hazard. A map may add another hazard only with an explicit damage/feedback rule in [ARENAS.md](gameplay/ARENAS.md).

Stasis chambers are closed when empty. Spawn admission opens the native chamber door; it closes once the robot capsule fully clears the authored door-sweep bounds. It does not open merely because a robot approaches. The same native motion state is synchronized in multiplayer.
