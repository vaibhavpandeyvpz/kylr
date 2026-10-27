# KYLR — AI robot behavior

Bots fill every nonhuman Instant Action slot. They obey the same collision, EP, AH, SH, ammunition, reload, spawn protection, pickup, portal, jump, and objective rules as humans. No bots enter Online Multiplayer. [OFFLINE.md](OFFLINE.md) owns difficulty selection; [WEAPONS.md](WEAPONS.md) owns weapon statistics; [RULES.md](../RULES.md) owns scoring.

## Design goal

The player should read a bot's intention from its movement and target choice. Bots should use the arena's routes, contest resources, and create fights without tracking through walls or receiving hidden information. Difficulty modifies execution and tactics, never the permitted actions or resource rules. A bot may make a smart play at any difficulty; a higher level performs it more consistently.

## Perception and decision loop

Ramparts route samples store carrier-local positions for moving decks. The
steering pass resolves current source, landing, entry and via points before
executing each step, including during a committed flight. Cross-deck links
refresh against physical support and jump clearance; launch-pad tiles expose
their authored launch route rather than an ordinary charged-jump departure.
This retains the shared decision cadence, priorities and jump/EP rules.

Movement continuity is an acceptance requirement: keep pursuing a committed
decision until it completes, becomes invalid, or a significant event changes
the priorities. Damage, crossing health/energy or ammo thresholds, a useful
weapon opportunity and changed flag state can justify a new decision. A routine
decision tick alone should not cause repeated goal switching. Preserve the BT
structure and cadence unless a specific defect is demonstrated. Optional
`--bot-trace` now includes actual `goal_commit` events with elapsed time,
destinations and resource state to diagnose churn before changing the policy.

Brief loss of sight retains an unfinished combat movement route for at most
two existing decision intervals (currently 0.5 seconds). It retains only the
previously chosen destination, never an unseen target's live position. Aiming
and firing lose the target immediately. Completed/missing routes, recent hit
reactions and higher-priority repair/energy decisions bypass the grace. Sustained
occlusion resumes the ordinary last-seen search. This changes movement goal
selection, not the BT structure, priorities or update frequency. All-roster and
rendered movement qualification remains required.

- Sense visible robots through a line-of-sight test from the bot's eyes, with occlusion by assembled map geometry and closed barricades. A spawn-invulnerable robot is absent from bot targeting, threat, and pursuit until protection ends. Hearing may reveal an approximate position after a nearby shot, projectile impact, portal use, or flag event; it never supplies perfect aim or an identity through walls.
- Reassess objectives at **4 Hz**. Sample a currently visible target at the selected difficulty's observation interval and turn toward that observed position at its aim response rate. Use a short remembered last-seen position for search, then return to the objective. Never retain exact target coordinates after sight is lost.
- An observer following a bot does not change its sight ray or aiming pose. Bots use their own eye and aim direction; the local human player's crosshair continues to use the actual camera ray, including its shoulder offset.
- Choose in order: survive an immediate hazard; respond to a nearby objective emergency; reach an available repair station when AH is at most 50 and the route is viable; seek an EP Core before depletion; fight a reachable visible opponent; pursue the current match objective; improve equipment or position. Distance, route risk, team needs, and current weapon range break ties. This order is a priority framework, not a forced path: a bot already carrying a flag values extraction over a low-value duel.
- Use traversable navigation links for ordinary jumps, EP-eligible charged jumps, safe drops, launch platforms, and portals. A traversal edge has an approach and physical execution phase; a bot must not steer directly toward its distant landing or portal exit before performing that action. Replan from its actual landing or portal exit, and when a barricade changes or a piece moves. If a jump pad physically launches the bot while it is finishing a short jump onto that pad, complete the stale jump edge immediately and replan for the powered flight; otherwise the bot can rise and fall over the pad indefinitely. A route that does not select a portal steers around its trigger. A bot does not activate a pressure plate repeatedly while standing on it, and does not use an unknown or blocked portal exit as a shortcut.
- Use the shared **3 m/s walk** speed as the base: **2× run (6 m/s)** by default and **4× sprint (12 m/s)** on clear travel routes above 50 EP. Walk for careful repair approaches and edge braking. Repair approaches continue until the robot stands inside the authored station pad trigger; stopping 0.65 m from its center leaves Tensor's capsule outside it. Spawn protection forces walking. Jump reach uses the shared run speed; steering checks stopping distance and brakes into nearby waypoints so faster travel does not authorize unsafe edge crossings.
- Cargo-lift users wait on supported room flooring outside the native platform footprint while the deck is absent or moving. Nearby bots clear an empty shaft even when pursuing another goal, retaining that goal and route. Board only after the deck is stationary at the boarding floor; riders stay aboard during travel. Keep the lift's anti-crush reversal active for all robots.
- Accept the match controller's randomly selected valid spawn; the bot does not choose one by tactical preference. DM can start or restart it at any safe map spawn, while TDM/CTF keep it inside its assigned team zone. During five-second invulnerability, **walk only** toward a useful lane; do not target, fire, pick up, jump, sprint, trigger plates, or use portals. After protection ends, resume the current objective from the reached position.

## Combat and resources

- Aim ordinary fire at a visible target's torso rather than automatically aiming at its eyes. Scoped rifles may deliberately aim at an exposed authored head collider when motion and difficulty allow; the normal ray still has to hit that collider to award a headshot. Predict projectile travel using only sampled observed movement, with difficulty-dependent lead. Bot shot direction includes the weapon's ordinary recoil; it cannot bypass recoil through a separate aim vector. Fire only with a valid line or weapon shape, after acquisition delay and within the difficulty's burst window. Bot shots use the difficulty accuracy roll on each firing event: a failed roll offsets intended aim by exactly **5°** in a uniformly random azimuth. Roll once per continuous-fire damage second, holding that offset through the second. Accuracy is not a guarantee of a hit; cover, range, motion, and projectile travel still matter.

  If the torso is covered, use a visible head point instead of firing at the hidden torso. Eye visibility alone never authorizes fire: check the muzzle's intended and current recoil/turn lane against architecture and props, including projectile thickness. A blocked bot stops firing and seeks a nearby supported, reachable firing position; it continues along that route without duel pauses. If none exists locally, replan toward the visible opponent. Survival, carried flags and committed traversal retain priority. Difficulty accuracy misses still apply to otherwise valid shots.

  Scoped rifles can keep scope held between primary shots without bypassing their firing interval. Rocket bots hold scope through the normal 0.4-second lock acquisition and only launch a scoped rocket after its target lock completes. Both lightning and flamethrower use their orb/fireball secondary beyond stream range, or at the configured distance when remaining stream ammunition is low; projectile lead uses each weapon's actual travel speed. Alternate-trigger shots respect burst pauses.

  Grounded navigation enters the graph through a physically reachable sample on the same side of nearby walls. Final approaches follow checked walk segments rather than cutting directly through props toward a nearby goal. An empty route counts toward stuck recovery so a bot cannot remain idle indefinitely with an unreachable destination.

  Lightning and flame cache the roll and azimuth on trigger start and each uninterrupted one-second boundary. The miss follows the bot's changing intended aim without rerolling, and flame damage, contact and visual endpoint use that same offset. Release/restart begins a new roll. The accuracy clock is independent of ammunition and damage-tick intervals; human aim is unchanged.
- Apply difficulty damage after hit-location and falloff damage, then apply SH/AH split. Noob: **80% aim / 50% damage**; Hobbyist: **90% / 75%**; Skilled: **90% / 100%**; Impossible: **100% / 125%**. Fractional damage is retained internally and rounded only for HUD text.
- Prefer an equipped weapon when its effective range and ammunition suit the target. Compare all acquired weapons with loaded ammo or spare packs and select a suitable one, retaining the ordinary hold and hysteresis. Use the pistol when no stocked gun suits the engagement. An empty equipped gun with a spare retains its rig until the shared automatic reload begins, and an owned empty gun can be selected and reloaded from banked spares. Reloads remain locked. Seek useful new weapons and matching ammo for owned guns; eligibility also permits unowned ammo, but bots avoid those shopping detours. Collect a map EP Core when eligible and a Shield Core when eligible, accounting for travel and exposure. A bot may contest a dropped EP Core, but a nearby credited killer's auto-attraction rule still wins according to [RULES.md](../RULES.md).
- A damaged bot may path to either zone's neutral repair station, but only if it is ready and unoccupied. It must reach the marked bay and stop to start repair; it remains vulnerable during the one-second shield activation. Suspend combat decisions throughout the seven-second use: one second to activate the shield, five seconds to weld, and one second to deactivate it. After release, walk out before choosing the next objective. Bots do not reserve a station from afar or block a teammate's exit. Difficulty can change how well they judge the route risk, never the 50 AH threshold, sequence durations, or station recharge.
- Strafe, use cover, break sight to reload, and avoid standing in a live flame cone, rocket blast area, or fall hazard. Do not dodge an unseen shot based on authoritative hit data. Short reaction delays and route variation make movement readable; avoid instantaneous 180° aim snaps.
- Combat steering uses a useful weapon distance: pistol 11 m, rifle 20 m, minigun 14 m, rocket 13 m, and short-range energy/flame weapons 7 m. Strafe for 0.7–1.5 seconds before reversing, close or back away to maintain range, and weave while advancing on flag objectives. Noob and Hobbyist pause between strafes during an ordinary duel, giving the player readable aim windows; these deliberate pauses do not trigger stuck recovery. Objective advance and explicit jump, drop, pad and portal execution continue without those pauses.
- TDM bots outside the opposing zone keep their advance route while shooting, rather than settling into a ranged duel across the centre. After entering, they can choose a moving engagement at their weapon's preferred distance. Range and cover-distance tuning lives in `data/ai/difficulty.json`; edge safety checks for tactical movement are throttled to about 8 Hz, while the existing collision steering continues every tick.
- After its difficulty reaction delay, a bot observing an opponent firing toward it can request a brief 0.45-second crouch or normal running jump. Maneuver probability and cooldown scale with difficulty; a declined roll still starts its cooldown, so it cannot retry every frame. Validate support along the jump runway and standing/jump headroom first. Air steering keeps the chosen dodge direction until landing. Charged jumps remain available through EP-eligible traversal routes. These are player input requests, using ordinary capsule changes, acceleration, jump physics and EP limits.
- When reloading or under visible fire below 70 AH, check a bounded set of nearby supported cover positions. Use one only if geometry actually breaks sight at crouched eye height and a route can reach it. Move there, crouch briefly, then reengage; do not park beside an open barricade. Sprint to cover, during extraction/recovery, or toward repair when critically hurt, subject to player EP rules and edge braking. AH at most 50 still gives repair priority, and flag carriers keep their emergency extraction/recovery priority.
- Raise a barricade as cover only when it lies between the bot and a visible nearby threat. Closed barricades block their footprint in both navigation graphs; opening them restores those nodes, and bots replan on either change rather than waiting at an obsolete route.
- After three failed 1.5-second movement attempts, exclude the blocked destination for six seconds and let the behavior tree select another reachable goal. This prevents an obstructed pickup approach from trapping the bot in repeated route retries. If EP falls to 50 or below before a charged traversal launches, cancel the charge and replan without charged links.
- No difficulty gets extra EP, AH, SH, ammo, speed, pickup priority, objective points, or knowledge of hidden opponents. Difficulty may shorten reaction delay and improve route/weapon choices, within the same rule set.
- Bots may make short speech callouts on their actual damage, pickup, kill, and objective events. Their words, audible range, team-radio rules, subtitles, and anti-spam limits follow [AUDIO.md](../AUDIO.md). Speech never changes a decision or leaks unseen opponent positions.

## Match-specific goals

| Match type | Bot priorities |
|---|---|
| DM | Seek favorable duels, protect a lead when near the limit, avoid feeding the leader, rotate between contested weapon and EP locations. |
| TDM | Favor crossfire and nearby teammate support, avoid blocking allies, regroup after a wipe, defend the team's likely route when the score lead is fragile. No friendly fire. |
| CTF | Assign attack, escort, defense, and recovery roles dynamically; switch roles when a flag state changes. A carrier takes safer routes to its base and can fight. A teammate can recover its team's dropped enemy flag and continue. A defender returns its own dropped flag on contact. If its own flag is away, a carrier seeks its dropped flag or pursues the thief instead of waiting at home, because capture requires the own flag at home. |

For an odd team roster, the larger team does not receive an extra tactical bonus. Reassign roles and routes when the roster changes. Bots never manipulate team membership or score directly.

A lone CTF bot attacks and recovers rather than staying in the permanent defender role; dedicated defense requires a teammate available to attack.

The CTF coordinator refreshes at the configured decision interval and immediately when a flag state, carrier, roster or teammate availability changes. Eligible bots are alive, unprotected and outside repair/spawn locks; human teammates are not assigned AI duties, although their carried flag can receive an escort. A carrier extracts; one available bot recovers an away own flag, one escorts a friendly carrier, and one defends a home flag only when another attacker remains. Remaining bots attack. Assignment ranks distance to the public objective/friendly carrier, own health/equipment readiness, role weights and a small previous-role preference to avoid thrashing; IDs only break exact cost ties. An enemy carrier is pursued at a position verified by the bot's own sight, then at its frozen last-seen position for the configured memory duration. Once memory expires, interception searches a public base-to-base extraction route. Project that public search point onto a reachable route endpoint so an interpolated point over the void or above a bridge cannot reject the emergency goal. Neither the carried flag's live point nor an occluded thief's transform supplies a goal.

DM bots protect a lead of at least two kills when within five kills of the goal or 45 seconds of the time limit. They seek eligible protection/resources, prefer repair at AH ≤50, and retreat from unfavorable visible duels (AH below 70, reload, or pistol against a pickup weapon). Nonleading bots apply the same retreat and target-choice penalty to avoid feeding the visible score leader; a healthy, equipped robot still contests it. These thresholds are provisional tuning data, not scoring or damage modifiers. Resource candidates always pass the arena's live `can_collect` predicate, including deployed readiness, visible payload, capacity and matching type; repair retains its separate eligibility rules. Candidate costs account for travel distance and proximity to a currently visible threat, weighted by the selected difficulty's route risk.

## Tuning and validation

### Runtime behavior trees

Identical traversal capsule sweeps can share their Boolean result within one
synchronous behavior-tree update. That scope ends before per-tick motor work;
no result survives into another update or physics tick. Planning tasks must not
mutate collision geometry while this query scope is open.

LimboAI 1.8.1 runs a separate `BTPlayer` on each offline bot. Editable DM, TDM, and CTF trees live in `data/ai/trees`, with a shared survival subtree. The match's physics loop manually evaluates each tree at 4 Hz. Construction and spawn/reset use the configured robot-ID decision phase offset. The default single-phase schedule evaluates bots together; increasing the diagnostic phase count spreads decisions across the interval. Per-tick aim and traversal remain in the robot controller so behavior-tree evaluation cannot change weapon cadence or physics speed.

The tree observes opponents, then selects spawn egress, objective emergency, repair/energy survival, tactical cover control, combat, match objectives, equipment, last-seen search, or patrol. CTF places its flag objective ahead of routine combat movement while continuing to fire at visible opponents. TDM advances toward the opposing zone when no reachable opponent is visible; combat pursuit follows a route into weapon range, then strafes rather than stopping for a stationary duel. DM rotates into contested lanes after equipping. Elimination and Gun Game share the DM behavior tree and free-for-all target policy. Gun Game keeps its assigned gun and seeks ammo without selecting another weapon; eliminated robots cannot act. A destination needs a route ending within 2 m before its task succeeds; an unreachable station or resource falls through to another candidate/branch. The blackboard exposes intent, destination, visible-target state, and route-node count for LimboAI's debugger. Each robot owns its runtime blackboard. Protected spawns do not acquire targets. Online matches never create bot trees. Validate behavior and performance with the full [playtesting matrix](../PLAYTESTING.md).

Versioned difficulty data lives in `data/ai/difficulty.json` (schema 1, dated revision). Its four profiles supply perception radius, reaction delay, decision interval, memory duration and route risk; the tactical section supplies objective weights, role stability, bounded candidate counts, combat distances and DM lead thresholds. Runtime loading validates the locked accuracy/damage table. Reaction delays are **0.65 / 0.45 / 0.30 / 0.20 s** for Noob / Hobbyist / Skilled / Impossible; tune through playtests without changing that table. Enable `--bot-trace` in a debug build to log selected goals, target visibility, route-node count, eligible pickup decisions, team role changes and shot rolls. Verify no wall tracking, no targeting protected spawns, CTF role changes, navigation through portal/jump links, and stable behavior after an arena event. Measure match completion, bot deaths from falls, and time spent stuck as quality signals, not as score modifiers.

Revision `2026-10-02.3` gives the four levels distinct execution profiles. These are provisional playtest values, separate from the locked accuracy/damage percentages:

| Execution parameter | Noob | Hobbyist | Skilled | Impossible |
|---|---:|---:|---:|---:|
| Aim response rate | 3.0 | 3.5 | 6.0 | 9.0 |
| Visible movement sample interval | 0.20 s | 0.18 s | 0.08 s | Every tick |
| Projectile lead fraction | 0% | 40% | 80% | 100% |
| Fire burst / pause | 0.8 / 1.1 s | 1.2 / 0.6 s | 2.0 / 0.2 s | Continuous |
| Minimum time between rifle trigger presses | 1.0 s | 0.8 s | 0.65 s | 0.5 s |
| Pause between duel strafes | 1.2 s | 0.4 s | None | None |
| Dodge chance per opportunity | 12% | 40% | 80% | 100% |
| Maneuver cooldown, before ±15% variation | 8 s | 5 s | 3.5 s | 3 s |

New targets and lost sight reset observation and fire-window state. Rifle primary and secondary fire obey the same pause and deliberate trigger spacing, timed from actual shots rather than requests. A fire pause releases a continuous weapon's trigger normally; it does not modify its ammo/damage cadence or accuracy-roll rule. Lower levels turn their visible body more slowly along with their aim. Lightning's primary beam does not use projectile lead; rockets and EMP use the actual 15 m/s flight speed and a bounded one-second prediction horizon. All levels retain identical health, shields, movement limits, resource rules and legal traversal. Horizontal waypoint proximity only stops movement when the destination is also on the current floor; an unfinished drop must continue past the upper ledge. Controlled duel measurements qualify execution, not final human difficulty or time-to-kill; human playtesting is still required.

### Equipment and secondary-fire planning

Revision `2026-10-02.4` adds an equipment policy shared by all three behavior trees. Spawn egress, flag emergencies and health/energy survival retain priority. Critical ammunition or an empty pickup slot can trigger a bounded equipment trip before ordinary combat; routine upgrades and shields run before a routine objective only when no enemy is currently targeted. Flag carriers and bots extracting, recovering, intercepting or escorting accept only a critical refill within four route metres, rather than abandoning their assignment to shop. The DM lead-protection branch uses this same equipment policy. Pickups must pass live readiness, full-pack capacity, matching type and reachable-route checks.

The policy estimates loaded plus spare ammunition in **seconds of full-trigger use**, using ordinary per-shot or continuous-stream costs. Burst pauses do not inflate its reserve estimate. Nearby ammo can be pursued before the critical threshold when the estimated trip would consume the remaining margin. It does not fill spare slots simply because capacity exists. Route costs include actual walk/jump/drop travel, portal entry and a small crossing cost, and charged-jump preparation; endpoint proximity alone cannot make an upstairs or opposite-zone pickup a cheap detour. Exposure to a visible enemy adds the existing difficulty route-risk penalty.

Weapon utility is a provisional heuristic using effective damage/cadence, scope/beam/orb mode, range, exposed head opportunities, observed motion and projectile flight uncertainty. A close rocket self-blast or any geometry or robot blocking the first five metres makes the rocket unsuitable. EMP utility uses the shared direct-projectile falloff: 10 damage through 20 m, fading to zero at 25 m; a weak distant charge can lose to the pistol. Feasible nearby rocket pickups can beat a poorly suited current gun; a first pickup may add a usable weapon even when its immediate damage rate ties or falls below the pistol. Later upgrades must clear the difficulty-specific improvement margin. All pickups retain distance/exposure and physical reachability checks. Flak utility accounts for the pellet volley and its spread at the observed engagement distance. The policy retains owned ammo while using the pistol, and rejects unnecessary sidegrades. Switching uses a 1.25-second hold and score hysteresis; an unusable gun can bypass the hold, but accepted projectile/casing events and its firing animation finish before the rig changes. The normal pickup rule still equips a newly collected gun immediately.

Manual reload is requested only with a spare pack, a low magazine, no current visible target, and enough time since sight was lost. It uses the shared two-second reload, including the ordinary loss of remaining loaded ammo, and both guns remain unable to fire during it. Empty-pack automatic reload/fallback keeps the shared player behavior. Bots return to a loaded pickup when it suits the engagement, and use the pistol when the pickup is dry, unsafe, out of range or less useful. A reload is never canceled to obtain free ammunition.

Rifles use scope beyond 22 m, including the 90 m scoped reach, while retaining deliberate shot spacing. Head opportunities are chosen once per acquired target/actual shot, not rerolled every frame, and require an exposed authored head shape and sufficiently slow observed motion. Head-shape object handles are weak and collider centres are cached in local coordinates; live pose transforms and occlusion are checked at aiming time. Lightning uses its beam at close range and can select an orb outside 25 m, or nearer the beam boundary when low ammo makes discrete shots useful. Orb aim receives projectile lead; beam aim does not. Projectile uncertainty can instead favour a hitscan gun against a fast opponent. This policy never bypasses the orb's 0.75-second cooldown, actual projectile speed, normal recoil, ammo or hit resolution.

| Equipment parameter | Noob | Hobbyist | Skilled | Impossible |
|---|---:|---:|---:|---:|
| Critical full-trigger ammo horizon | 4 s | 6 s | 8 s | 10 s |
| Safe manual reload at or below loaded fraction | 15% | 25% | 30% | 35% |
| Minimum elapsed time since losing sight for that reload | 1.7 s | 1.3 s | 1.0 s | 0.75 s |
| Maximum normal equipment trip cost | 16 m | 20 m | 24 m | 28 m |
| Required replacement utility ratio | 1.50 | 1.30 | 1.20 | 1.15 |
| Low-ammo orb option begins at | 24 m | 22 m | 20 m | 18 m |
| Scoped head-attempt probability per opportunity | 8% | 20% | 40% | 65% |
| Maximum observed target speed for head attempt | 1 m/s | 2 m/s | 4 m/s | 6 m/s |

These are configurable execution heuristics, not changes to shared weapon statistics or a claim of final human balance. The head attempt can miss, and an occluded head reverts to body aim. The ordinary difficulty acquisition delay, accuracy roll, burst window, recoil and shot-spacing limits still apply.

### Walkable ground detail

Launch routes retain the authored pad centre as their entry target, independently
of the nearest navigation grid sample. Bots enter the activation radius before
waiting for powered lift and use that same centre for vertical departure.

Small stones and gravel use native terrain collision, with visible interior
peaks at most 0.24 m. Fixture seating and approaches are kept clear. Walk-route
clearance tests the robot motor's supported step height and the whole raised
capsule, including headroom. Low stones between navigation samples remain
walking edges; taller obstructions and low lintels remain blocked.

Projectile avoidance scans nearby visible rockets, grenades, fireballs, EMP/lightning orbs, flak and pulse shots every 0.12 seconds. It predicts closest approach (including grenade gravity), waits the selected difficulty's reaction delay, then uses its dodge chance and cooldown. A lateral dodge requires a supported, unobstructed runway with stopping room and cannot cross portals, interrupt committed traversal, or run off a ledge. It does not read projectiles through cover or behind the robot, and ignores the robot's own projectiles and allied pulse bolts.

Identical navigation-node paths share a bounded 1,024-entry cache per graph (charged-jump and low-energy graphs stay separate). Barricade changes invalidate both successful and failed paths before replanning; route selection and physical safety checks remain unchanged.
Initial construction and respawns distribute decisions over four cohorts. Each
robot retains its difficulty's decision interval and update frequency; resetting
a spawn does not synchronize every native tree onto one physics tick.

Moving-platform paths cache node IDs and read their current positions when
building routes. Docking-connection changes invalidate the cache; continuous
platform motion updates coordinates at the physics rate. Ramparts corridor
assignments have separate cache keys and filter the other corridor during search.
Balancing counts actual corridor entries and pending assignments. Flag carriers
use the ordinary safe objective route without a balancing detour.
Floater itineraries come from the map's `floater_paths`. Bots board the next
reachable deck, wait for its docking window, then advance to the following deck;
they do not require the entire moving chain to be connected simultaneously.
Docking collision checks run in small batches and publish one consistent graph
revision. Bots recheck inter-deck walking support and moving jump reach before
crossing. Graphs without portals use native Euclidean AStar costs and estimates;
portal graphs retain the shortcut-aware solver.
Ramparts reuses immutable navigation capsule shapes while creating fresh query
parameters for each sweep and contact test. Shape reuse is owned by the source
map's `reuse_navigation_query_shapes` setting.

Bots request rocket secondary scope beyond 15 m and acquire locks through the same visible-target trace and delay as human robots. The scoped rocket retains its 100 m aiming range; it does not inherit the orb range or rifle headshot policy. Traversal clearance and dodge runway estimates include powered jump ascent followed by the longer ballistic coast.

Grenade aim solves a low ballistic arc using the current map gravity. Firing
clearance sweeps the projectile along that arc, so low cover can be cleared
while a ceiling or unreachable target prevents firing. A final muzzle check
after movement and pose updates verifies the actual launch direction before
the shared trigger; newly obstructed shots prompt repositioning.

Faceoff and Skyfall portal planning combine cached native `AStar3D` walking
segments with a small shortest-path graph of portal endpoints. Portal edges
retain their three-metre cost, direction and disabled-point checks. Normal and
charged graphs remain separate. Moving connections and blockers synchronize
the native mirror incrementally; restored snapshots create independent solvers.
Loading prepares both planners and their endpoint paths. A conservative walking
component check skips disconnected searches.
Endpoint walking paths survive edge removals that do not touch their directed
path. Added edges retain a cached endpoint path only when a weighted distance
lower bound proves that the edge cannot shorten it. Other walking queries and
disabled-point changes invalidate their applicable caches.

Skyfall keeps navigation coordinates in platform rest frames and projects active
route points into the current physical frames. Graph edge weights use the rest
geometry; current-world capsule sweeps validate dynamic crossings and departures.
Spatial candidate pairs are cached because bobbing preserves horizontal positions.
Baking includes diagonal, directed normal and EP-eligible charged jumps, with
ballistic arrival times for different-height landings. The 12 m candidate radius
covers the longest physically possible charged descent between its sampled
floors; current gravity, launch impulse and capsule sweeps reject infeasible arcs. Pads, ramps and portals
retain their authored links. Crossing discovery refreshes under a bounded physics
budget; departure checks use the current physical platforms. DM hunt targets
are snapped to supported deck navigation at the flag-home elevation. Impossible
vertical destinations are rejected before a moving-map path search.
Ramparts retains live-coordinate navigation and corridor balancing for horizontal and rotating carriers.

Skyfall binds route points using the planner's known node IDs and cached carrier
frames. Off-grid continuations retain physical nearest-point projection; binding
hints are removed after local frames are assigned. Resource-cost evaluation and
commitment share a route only within the same synchronous planning epoch, before
movement or collision changes. Normal/charged reclassification preserves full
walking caches when connectivity stays unchanged; real edge changes invalidate
the affected graph. Walks within one rigid assembly retain their baked geometry
checks, while departures between independently moving assemblies are checked live.
