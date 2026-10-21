# KYLR — match rules

This document is the single contract for match flow, scoring, and objectives. [GAMEPLAY.md](GAMEPLAY.md) covers controls, combat feel, equipment, and map design. **Instant Action** and **Online Multiplayer** are game modes; **DM**, **TDM**, **CTF**, **Elimination**, and **Gun Game** are match types. A participant's character is a **robot**. A **bot** is specifically an AI-controlled robot in Instant Action; human-controlled robots and bots follow the same match-type rules except for the stated difficulty modifiers. **EP** means **Energy Points**; **Energy Core** remains the pickup's name.

The main-menu **Settings** option changes local controls, audio, and graphics preferences as described in [GAMEPLAY.md](GAMEPLAY.md). These preferences apply in either game mode but do not modify match type, map selection, roster limits, scoring, weapon statistics, or server rules.

FPV/TPV is a local camera choice available in either game mode. Switching it does not change the robot's match identity, collision, hit detection, aim authority, damage, scoring, or any other match rule. Remember the last view and restore it when the five-second third-person spawn cinematic ends or the robot exits repair. Saved menu/setup selections prefill screens only; they never start or alter a match without the player's explicit action. [SCREENS.md](SCREENS.md) defines the remembered UI choices.

Choosing **Online Multiplayer** requires account login, then opens its lobby before joining a match. The lobby's left-side cards select a **match type** (DM, TDM, CTF, Elimination, or Gun Game); a prominent central robot preview alternates common idle with its selected or default victory animation; the **bottom-right Play** button sends the stored login JWT and selected match type to matchmaking. On success, join the assigned server using its player-specific authenticatable ticket and follow its Waiting/Countdown/Active flow. The server chooses the map and match settings. [ONLINE.md](ONLINE.md) defines identity, matchmaking, ticket, and recoverable failure responsibilities.

## Shared match state

`Waiting → Countdown → Active → Finished` is the baseline state flow. A match accepts participants and assigns teams/spawns while waiting. The **Countdown** phase holds the player at their spawn for five seconds; only after it finishes does the match enter **Active**, enable player control, start EP drain and the match time limit, and allow scoring and objectives. At finish, stop scoring, freeze the result, and present the winner or draw, MVP result, and scoreboard. An Online Multiplayer match can also finish with a **Canceled** outcome when its roster falls below the minimum. Re-entering a new match resets scores, flags, deaths, and per-match statistics.

The map and fixtures load fully assembled before a five-second countdown. Resource and renderer preparation behind the loading cover freezes this countdown; loading time never consumes the player's visible opening sequence. The local Phantom Camera holds a front-left view of the player spawn, with movement and gameplay actions locked. At five seconds, enable the saved gameplay view, normal actions, clock and scoring; initial invulnerability ends with the countdown. Active-play respawns retain their separate five-second protection flow.

A match has **2–10 robots**, including odd counts. In Instant Action, this total includes the human-controlled robot and all bots; its setup menu currently offers 2, 4, 6, 8, or 10. Do not start the countdown outside the 2–10 range. Tensor has **five available head variants**. In **Instant Action**, randomly assign a head to each robot. Free-for-all heads may repeat; TDM/CTF heads are unique **within each team**, with the same head permitted once on each opposing team. In **Online Multiplayer**, use each account's selected head in DM/TDM/CTF/Elimination/Gun Game and allow duplicates even within a team. Keep the resulting head for the entire match, including respawns.

For TDM and CTF, randomly select **two distinct** colors from yellow, green, blue, and red, then assign one color to each team. Balance robots between the two teams: their counts may differ by at most one. With an odd count, randomly choose which team gets the extra robot; the next joining robot goes to the smaller team. Each team has at most five robots. In **Instant Action**, assign a joining robot an unused head on its team. In **Online Multiplayer**, preserve the joining account's chosen head even if a teammate has the same one. For an online team match, apply the assigned team color to primary armor and its library-authored contrasting accent to secondary armor, overriding both saved custom colors for that match; keep the chosen victory emote. Team color and existing members' team assignments remain fixed through respawns. A new match makes fresh random team-color selections.

Only active, alive, non-invulnerable participants can deal combat damage, collect pickups, or carry a flag. A defeated participant cannot score further events until respawned. Every robot begins a match with 100 AH, 100 EP, a pistol, and an empty picked-up weapon slot. On death, **discard the picked-up weapon and all its remaining loaded and spare ammo**, play the death animation in third person, hold its final pose for one second, then respawn. A respawn restores 100 AH, 100 EP, and the pistol with an **empty picked-up weapon slot**, clears temporary combat effects and last-hit fall credit, and uses the same random spawn-point selection as an initial spawn: any map spawn in free-for-all types; a spawn inside the robot's assigned zone in TDM/CTF. Safety filtering and tie-breaking follow [ARENAS.md](gameplay/ARENAS.md). Gun Game instead retains its assigned weapon and cycle through respawns, and Elimination stops respawning after the fifth death. A robot that falls beyond the map boundary dies in the falling pose and drops nothing; its body keeps falling rather than returning to a safe floor.

Every spawn, including a respawn, gives the robot **five seconds of invulnerability**. For an initial spawn, protection runs within the movement-locked countdown and ends when control begins; for a respawn during active play, start it at respawn/control return. A robot awaiting respawn is still dead and absent from play, so no protection timer runs during its death animation or final-pose hold. During invulnerability, show a third-person spawn cinematic following the robot while allowing **walking only as a gameplay action**: disable running, sprinting, jumps, firing either weapon, collecting pickups or flags, and activation of pressure plates or jump platforms. Block portal travel. The player's saved FPV/TPV preference is unchanged; a view-switch input has no effect during the cinematic. Weapon and other incoming hits deal **zero damage** while invulnerability lasts. Exclude the robot from bots' perception and target selection; bots must not pursue or attack it. At expiry, restore normal actions, vulnerability, and the saved FPV/TPV view **at its current position**, with no snap back to the spawn marker.

The **only death conditions** are **EP reaching zero** or **AH reaching zero**. Hazards, self-inflicted damage, and other effects may cause death only by reducing AH or EP to zero under their defined damage rules; they must not trigger a separate instant-death path. Shield Health reaching zero does not itself kill the robot.

As soon as either death condition is met, start the death animation and turn off every emissive part on the robot and its visible equipped gear. Keep the dying robot and its corpse dark; restore normal emissive state only on the newly respawned robot. This visual rule applies to both first-person and third-person models and does not depend on which resource reached zero.

An ordinary corpse disappears **one second after its death animation ends**. It falls onto the nearest valid collider below the death position rather than snapping to the map's ground level. If death was caused by **AH reaching zero** and EP was **greater than zero at that instant**, spawn a dropped Energy Core on that surface at the corpse's position when the corpse disappears. Snapshot the exact remaining EP at death; do not drain it during the corpse period. Death from EP reaching zero produces no dropped Core. A void fall keeps the body falling and creates no drop. Lethal lunar contact immediately holds the final lying death pose on that surface, without replaying a standing collapse or producing a drop. Preserve the normal death/respawn duration while holding that pose. Remove an uncollected dropped Core **15 seconds after it appears**.

A dropped Core transfers its stored EP **additively** to a living collector, capped at 100 EP; it does not refill to 100 by itself. Contact with the Core collects it once. While it exists, continuously check whether the credited killer's living robot is within **10 m in world space**. If so, the Core automatically flies to that robot and transfers its EP when it arrives. If it is unclaimed at the end of its 15-second lifetime, it vanishes. A death without a credited killer can still leave a contact-collected Core when it was caused by AH reaching zero with EP remaining. Dropped Cores have no map pickup point or 60-second restock timer.

Elimination credit normally goes to the participant whose valid damage event reduced AH to zero. EP depletion, self-inflicted AH depletion and uncredited environmental damage give no opponent a kill. A robot must not receive duplicate elimination credit from one death.

For a **fall-off-map** death, credit the last robot that dealt an accepted hit in this life only when that hit used the **grenade launcher, rocket launcher or EMP gun**. Direct and splash damage both qualify. Every later accepted hit replaces this record, including an ineligible weapon, self-hit or environmental hit. Rejected protected/friendly hits and zero damage do not replace it. There is no additional expiry timer within the life; respawning clears the record. A self-hit or a source no longer in the match gives no opponent credit. A source that subsequently died can still receive posthumous credit.

A credited fall adds the ordinary kill, applicable TDM team point, assists and local kill feedback, and advances Gun Game normally. In CTF it remains a kill statistic rather than a capture point. The kill feed names the attacker, victim and qualifying weapon while retaining the fall cause.

Crossing the map's fall boundary or contacting Skyfall's lethal lunar surface or dunes reduces AH to zero and preserves the fall hazard. A void-fall corpse continues falling at its actual location. On lethal lunar contact, it slams onto the contacted surface and remains there through its death animation. Neither leaves a pickup, including credited falls. A spawn-invulnerable robot crossing the boundary returns to a safe spawn with fresh five-second protection, with no death, kill or dropped Core.

An **assist** is an informational statistic for a robot whose accepted pre-shield-split damage to the victim totaled at least **20 points** in the preceding **10 seconds**, provided it did not receive the kill. Assists add no match score or MVP kills.

The configured goal score or time limit ends an active match. If both occur in the same update, process already accepted scoring events, then resolve the result once. Instant Action offers a goal score from 1 to 999 (default 25) and a time limit from 5 to 60 minutes (default 15). Online Multiplayer has a **30-minute** time limit and a goal score of **2 × the current player count**. Recalculate and show the goal when a player joins or leaves, except that active Elimination keeps its starting target. The goal counts individual kills in free-for-all types, team kills in TDM, or team captures in CTF. Elimination also ends at the last surviving robot, and its remaining-life ranking is specified below.

For a tie at the highest final score, compare the **elapsed active-match time when each tied robot or team first reached that final score**; the shorter time wins. Free-for-all types compare individual kills, TDM compares team kills, and CTF compares team captures. Elimination ranks remaining lives first unless the kill goal was reached. If the tied scores were reached at **exactly the same elapsed time**, the match is a **draw**. In **every completed match**, the individual robot with the most kills is **MVP**, independent of the winning team; an MVP kill tie uses the same earliest-to-score rule. If both MVP kill count and time are exactly tied, show the tied robots as **joint MVPs** rather than choosing one arbitrarily. Instant Action's local elimination exit shows current standings without a final MVP. Record the score-reaching times as scoring events occur, so the result does not depend on scoreboard display order.

Show the completed map's scoreboard at match end with the winner or draw, MVP result, each participant's kills and deaths, team totals in TDM/CTF, captures in CTF, and the elapsed time when each relevant final score was reached. In **Instant Action**, keep the results visible and offer **Return to Main Menu**. In **Online Multiplayer**, start a **15-second post-match timer** on the results screen and offer **Return to Lobby** during that window. Returning to the lobby exits the next-match transition. If the player remains, the server randomly chooses the next map and starts a fresh match of the selected type when the timer expires; that match runs its five-second spawn countdown before active play. If the roster is invalid at that point, cancel the next match rather than starting it.

In an **active Online Multiplayer** match, immediately end with a **Canceled** outcome if the roster drops below **two human-controlled robots** in DM/Gun Game, or if either team has **no human-controlled robot** in TDM/CTF. Elimination instead resolves the final surviving participant after a departure; an empty server has no winner. A canceled match has **no winner or MVP**, and its scores are not treated as a completed result. The normal 15-second next-map countdown does not run after cancellation. Show the reason, then return remaining players to the Online Multiplayer lobby with their last match card selected; matchmaking does not restart until they press Play.

The in-match HUD uses authoritative match events: the kill feed names killer, victim, and weapon for credited eliminations; reports uncredited **fall-off-map** deaths by victim and cause; announces **who joined or left** an online match; and announces the winning robot/team, a **draw**, or **cancellation** at finish. Online names in the lobby and kill feed come from the game server's player info, bound to the authenticated account; clients cannot supply a different match name. A disconnect counts as leaving for the feed. The top-five kills leaderboard ranks **individual robots by kill count only** in DM, TDM, CTF, Elimination, and Gun Game; captures, deaths, assists, and team totals do not affect that ranking. The top-center score is the controlled robot's individual kills in free-for-all types, plus remaining lives in Elimination, or the **two team scores** in TDM/CTF. Show the goal and remaining match time alongside it. The bottom-left weapon tray uses the loaded-ammo and spare-pack state from the weapon inventory.

## Movement rules

- Establish the match's gravity value **before the match starts**. Use **1.0** unless the map or a match option specifies another value. Divide powered-ascent cutoffs by this value: immediate normal Spacebar jump **1 m / gravity**, charged jump **2 m / gravity**, and jump-platform upward target **10 m / gravity**. Retain vertical velocity when power ends; subsequent coasting adds height under gravity. A charged jump requires holding Q while grounded for **at least 2 seconds** and then releasing it while EP is **above 50%** (more than 50 of 100). At **50% or below**, disable charged jump and cancel any charge in progress; normal jump remains available. [ARENAS.md](gameplay/ARENAS.md) defines the powered jump-platform lift.
- Default movement is **running at 2× the 3 m/s walk speed (6 m/s)**. Hold Sprint (Ctrl by default) while moving to move at **4× walk speed (12 m/s)**, only while EP is **above 50%** (above 50 of 100). Holding the **Walk modifier (Shift by default)** overrides running or sprinting with **walking at 3 m/s**. At **50% EP or less**, sprinting falls back to running; walking remains available. Sprint visuals end when sprinting is blocked, overridden, or released. Reduced-motion Settings may turn off sprint visuals without altering speed. Spawn invulnerability still permits walking only at **3 m/s**.

## EP rules

- Every robot starts a life with **100/100 EP**. While active and alive outside an active repair station, it loses **1 EP per second**. Clamp EP to 0–100; an uninterrupted full charge lasts **100 seconds**. EP drain pauses throughout the station's seven-second use; welding completion restores EP to 100. Weapon hits never reduce EP. Reaching zero kills the robot.
- A **map Energy Core** is eligible only when the robot's EP is **at least 1 percentage point below full**: **99 EP or less** out of 100. A successful pickup restores the robot to **100 EP**, restarting its depletion cycle. Core points occupy designated map positions and are distinct from weapon points and temporary dropped Energy Cores.
- A Core point begins available. On successful pickup, grant one refill, close/retract the point, and start a **60-second** timer. It cannot grant another refill while closed. When the timer expires during the match, reopen it with a new Core. Reset Core points to available for a new match.
- A failed or ineligible Core pickup—including contact above 99 EP—does not close the point or start its timer.

## Armor and shield rules

- Every robot starts a life with **100/100 Armor Health (AH)**. AH cannot exceed 100. Without an active shield, a weapon hit deducts its damage from AH. Reaching zero AH kills the robot. Weapon damage is defined by the profiles below.
- Each map has **two Shield Core pickups**, one in each zone. Each point has its own independent 60-second restock timer. It is eligible when the robot has no shield or its active shield has lost **at least 1 percentage point of SH**: **99 SH or less** out of 100. A successful pickup sets SH to **100**, creates or refreshes the visible electromagnetic shield, and starts a fresh **60-second** shield duration. Restock the Shield Core at its map point **60 seconds after a successful pickup**. When the shield duration ends, remove it and any remaining SH.
- While the shield is active and has SH, split each weapon hit's damage: **80% from SH, 20% from AH**. Neither portion reduces EP. If the 80% portion exceeds remaining SH, set SH to zero; still deduct **only the 20% portion from AH** for that hit. Do not spill unused shield damage into AH. Remove the shield whenever SH reaches zero, including exact depletion. Subsequent hits apply without a shield.
- A robot with an active shield at more than 99 SH cannot collect the Shield Core; an ineligible contact leaves the Core available and does not start its restock timer.

## Repair-station rules

During repair use the robot's unarmed common idle pose and hide its equipped weapon, ammo model, and weapon collision. Retain its weapon slot, loaded ammunition and spare packs, then restore the same equipment when released into active play. The activation phase blocks voluntary movement while preserving physical impact push; leaving the bay interrupts the use. Welding and deactivation block damage and impact push.

- Each zone has **one 2 m × 2 m repair station**. It is a reusable arena fixture, **not** a pickup and not the robot's personal Shield Core. It is neutral in DM/TDM/CTF/Elimination/Gun Game: any eligible team may use either station. Only one robot can occupy a station for repair at a time.
- An active, alive, non-spawn-invulnerable robot is eligible when its **AH is 50 or less** and the station is ready. It must enter the marked bay and stop moving to claim it. The server atomically assigns the occupant and starts a **seven-second** use: **one second Shield Activating → five seconds Welding → one second Shield Deactivating**. The station is occupied throughout; its separate **60-second** recharge begins only when this use ends. A rejected entry grants no protection or refill.
- During the entire use the occupant remains in the match roster but is immobilized and cannot fire, reload, switch weapons, collect pickups/flags, interact with plates/portals/jump platforms, or score a capture. Cancel any reload in progress on activation without consuming its spare pack. The barrier becomes protective **after the first second**, when activation completes; before then the robot can still take damage and impact push, and a death aborts the use. Once protective, it prevents **all incoming damage and impact push** to the occupant, including direct hits, splash, flame, EMP, and projectile impacts, until deactivation completes at seven seconds. It protects **only its assigned occupant**, not robots standing beside the bay, and is absent while the station is merely ready or recharging. It is independent of personal SH and does not spend or replenish SH. Pause the occupant's ordinary **1 EP/s drain** for the entire seven-second use. Existing personal SH duration continues normally.
- At **six seconds**, when welding finishes, atomically set the occupant to **100 AH and 100 EP** and stop welding effects. Animate barrier deactivation for the final second, keeping the occupant protected and immobilized. At **seven seconds**, remove the barrier, release movement control, and let the robot walk out. The station then enters **Recharging for 60 seconds from the end of deactivation** and is unusable by every robot until that timer ends. No personal SH is added or refreshed. Do not grant a second refill while the same robot remains on the station; it must leave the bay and the station must finish recharging before a later use.
- On death during shield activation, disconnect, match end, cancellation, or loss of valid station geometry during an arena event, stop the use and remove any barrier immediately. Grant **no partial AH/EP refill** if interrupted before welding finishes; if interrupted during shield deactivation, retain the already completed refill. If the match continues after an interruption, enter **Recharging for 60 seconds from the interruption time**; a new match resets the station to Ready. A CTF carrier retains the flag while using the station and remains visible in flag status; the flag drops if that player dies or disconnects under the usual rule. A station cannot overlap a capture trigger.

## Weapons and arena interactions

[WEAPONS.md](gameplay/WEAPONS.md) is authoritative for weapon slots, ammo packs, reload, firing, range, damage, recoil, and weapon pickups. [ARENAS.md](gameplay/ARENAS.md) is authoritative for map placement, portal/jump/plate/barricade interactions, and arena events. All map pickup points restock 60 seconds after a successful pickup; temporary dropped EP Cores and CTF flags use their own lifecycle rules.

## Deathmatch (DM)

- Every participant competes individually. There are no teams or flags. The match supports 2–10 robots, including odd counts. On every initial spawn and respawn, select a random valid spawn point from the **whole map**; DM has no assigned home zone or zone-balancing requirement.
- An elimination of another participant awards one point to the attacker. EP depletion and AH depletion from self-inflicted or environmental damage award no point.
- Reaching the configured kill goal ends the match; otherwise it ends at the time limit. The participant with the most final kills wins, using the earliest-to-score tie break when needed.
- The scoreboard shows each participant's score, eliminations, and deaths.

## Team deathmatch (TDM)

- Participants belong to one of two balanced teams for the whole match. Team counts differ by at most one. The teams use two distinct randomly selected colors from yellow, green, blue, and red. Assign teams and colors before spawning; keep heads unique within each **Instant Action** team, while online robots use their selected heads even when duplicated. Identify teammates consistently in the world and HUD.
- An elimination of an opposing team member awards one point to the attacker's team and one elimination to the attacker. A kill of a teammate gives no point; friendly-fire damage is disabled by default. If friendly fire is enabled later, its scoring and penalties require an explicit rule change.
- Reaching the configured team kill goal ends the match; otherwise it ends at the time limit. The team with the most final kills wins, using the earliest-to-score tie break when needed.
- Assign each team to one map zone for the match. On every initial spawn and respawn, choose a random valid spawn point **within that robot's assigned team zone**; never send a team member to the opposing zone to fill a spawn. The scoreboard shows team score and participant eliminations/deaths.

## Capture the flag (CTF)

- CTF uses two balanced teams whose counts differ by at most one, with distinct randomly selected colors. Heads are team-unique in Instant Action; online robots retain their selected heads even when duplicated. Each team has one flag and one home base. A flag is in exactly one state: **at home**, **carried** by one opposing robot, or **dropped** at a world position.
- Assign each CTF team to the zone containing its home base. On every initial spawn and respawn, choose a random valid spawn point within that team's zone.
- An opposing robot can take a flag that is at home or dropped. A carrier may move and fight but cannot carry both flags. A carrier's own team flag is unaffected by carrying the enemy flag.
- When a carrier **dies, disconnects, or leaves the match** over a playable surface, the carried flag falls to the nearest valid collider below it and deploys its legs there. It stays until a robot interacts with it or the match ends; there is **no automatic return timer**. If no playable surface is below the carrier, or the carrier dies beyond the fall boundary, return the flag home immediately. A robot on the **former carrier's team** may pick it up and continue carrying it. A robot on the **flag's owning team** may pick it up to return it immediately to its home base. Dead or spawn-invulnerable robots cannot interact with the flag. Apply the flag drop before checking whether that departure cancels an online match.
- A capture occurs when an eligible carrier contacts their own base's round capture trigger **while their own flag is at home**. The trigger is 2 m in diameter and 10 cm high above the ground, inside the authored 2 m × 2 m flag spot. It detects the carrier's body without blocking movement or shots. Award one capture point to the carrier's team, return the captured flag home, and emit one capture event. A flag touch cannot score twice. The team-colored ground energy ring remains visible throughout CTF even while the home flag is carried or dropped.
- Reaching the configured capture goal ends the match; otherwise it ends at the time limit. The team with the most final captures wins, using the earliest-to-score tie break when needed. Eliminations do not add to the CTF team score, though they remain visible as statistics and determine MVP.
- The flags return home and carriers clear when a match ends or resets. Eligible flag take, handoff, and own-flag return use contact. A carrier may fire, use portals and jump platforms, and trigger plates, but cannot collect a second flag. A flag cannot be captured while its team's own flag is away.

## Elimination

Elimination is free-for-all with five lives per robot. It uses DM's map,
difficulty, robot count, kill-goal and time-limit settings in Instant Action.
Every death consumes one life, including falls and power depletion. Respawn
normally after the first four deaths; the fifth death permanently removes the
robot from play. Eliminated robots cannot move, fire, take damage or respawn.
The local player hears **Eliminated** in the flag announcer's voice.

The match ends at the configured kill goal, when only one robot has lives
remaining, or at the time limit. A reached kill goal uses DM's kill/time ranking.
Otherwise rank remaining lives, then kills, then earliest final-kill time;
an exact tie is a draw. If no lives remain, the result is a draw.

In Instant Action, the local player's fifth death ends play immediately and
shows **Eliminated**, with standings at that moment and no declared bot winner.
Online eliminated players watch a surviving robot until results. Active online
Elimination rounds accept no new joins; admission reopens in the next round's
Waiting/Countdown phase. The active round retains its starting kill goal after
departures; the final remaining participant wins by survival.

## Gun Game

Gun Game uses DM's free-for-all scoring, spawns, goal and time-limit options.
Each robot starts with one randomly assigned weapon. Every credited opponent
kill assigns a new random weapon from that robot's remaining cycle. All ten
weapons appear once per cycle; shuffle a new cycle after exhausting it and
avoid repeating the previous weapon at the cycle boundary. Uncredited deaths
do not advance the cycle. Respawning retains the assigned weapon and cycle.

Only the assigned weapon is owned. A new assignment or respawn fills its loaded
ammo pack; respawns clear reserve banks as usual. Weapon-holder hatches stay
closed with no payload or pickup trigger, and weapon item cradles are absent.
Ammo pickups remain at their authored locations, including precollection for
future weapons. Energy/shield pickups, repairs and map events work normally.
An empty assigned gun must reload from collected reserves; it cannot switch
to an unassigned pistol.

## Cross-match-type consistency

| Event | DM | TDM | CTF | Elimination | Gun Game |
|---|---|---|---|---|---|
| Opponent elimination, including credited fall | +1 attacker score | +1 attacker team score | Statistic only | +1 attacker score | +1 attacker score; next weapon |
| Uncredited death | Death only | Death only | Death; drop carried flag | Lose one life | Death; retain weapon assignment |
| Teammate damage | No teammates | Disabled | Disabled | No teammates | No teammates |
| Initial spawn and respawn | Anywhere on map | Own zone | Own zone | Anywhere; no respawn after fifth death | Anywhere on map |
| Winner at match end | Most kills | Most team kills | Most team captures | Kill goal, otherwise lives then kills | Most kills |

## Shared lifecycle rules

- Use each imported robot's authored death animation duration. Remove its corpse and respawn one second after that animation ends. A void fall uses three seconds of falling animation, followed by the same one-second hold. Lunar contact uses the grounded death animation duration instead.
- Death EP splits into randomly scattered Cores of at most **10 EP** each (final remainder retained), supported on the same floor with neighboring centers **25–35 cm** apart where space permits. Only actionable robots below 100 EP can collect. A dropped EP Core flies toward the body centre of an eligible credited killer at **2 m/s** after entering the 10 m attraction radius. Resolve all pickup claims in one authoritative simulation order: eligible killer auto-attraction claim, then ordinary contact, then expiry. Once claimed, it cannot grant EP twice.
- Active online matches other than Elimination accept joins while below ten robots; a joiner uses the deficient team/zone. Existing robots never change teams to rebalance. A departure that does not cancel the match leaves its team assignment vacant, and the next eligible join fills the deficiency. Preserve the **2 × current roster** online goal rule; active Elimination retains its starting target.
- Suicides and uncredited environmental deaths add a death but no kill or point. Eligible grenade/rocket/EMP fall credit follows the rule above. Deaths never subtract score.

Local kill chains count credited enemy eliminations within one life, with at most ten seconds of elapsed match time between successive kills. A longer gap restarts at one; any death clears the chain. Posthumous eliminations display their kill confirmation but cannot build a new chain. Kills two through six award Double Kill, Triple Kill, Mega Kill, Champion and Death Bringer respectively. Further kills continue the counter without repeating an accolade. These awards do not change score, damage or objectives. Online authority owns the counter and sends each live event reliably to its credited recipient; snapshots and late joins never replay awards.
