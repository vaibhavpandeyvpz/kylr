# KYLR — arena and interaction design

This document owns map structure, authored markers, traversal, and dynamic arena behavior. [RULES.md](../RULES.md) owns scoring and match state; [WEAPONS.md](WEAPONS.md) owns pickup eligibility and restock.

### Speed-ramp traversal and presentation

Skyfall's two speed ramps use the native SK_SpeedRampTrigger and LaunchOrigin.
Trigger entry engages magnetic traction along the inclined belt to the lip,
then releases a 12.6 m/s impulse along the delivered belt axis, scaled by the
square root of the match gravity multiplier. Horizontal momentum persists
through the ballistic flight and clears on landing. This runtime impulse is
configured by map data, independently of the library's original belt-speed study.
The motor state replicates for online prediction and resets at respawn.

Both ramps reach the higher Island 2 deck. Directed speed_ramp links are
available below 50 EP and appear in both bot and baked navigation. The graph
checks the complete capsule flight and supported landing before exposing a
link. Bots approach the native trigger, ride to the lip, then replan on landing.
Lethal lunar terrain is excluded from baked navigation source geometry.

Four cyan chevrons travel along the native belt slope toward its lip. They
sit above the actual belt surface, fade at the ends and add no collision or
shadow. Each is a closed 2 cm thick mesh, 30 cm long, at 35 cm pitch: 5 cm clear gaps. Reduced Motion
freezes the chevrons, including when the setting changes during play. Native
convey animation loops again after each launch clip.

## Arena design and interactions

Ramparts has a 75 × 75 m arena inside a Martian crater lake. Its two rocky mainland summit cores are
25 × 25 m at 10 m above sea level, with rounded eroded shoulders beyond the
blueprint core and level fixture seats. Fractured cliffs descend to a closed base
17 m below the water. Two 15 × 15 m thruster-supported side islands, six
10 × 10 m floaters and the central 22.5 m cross share the 10 m initial deck datum.
Native cisterns, containers, hub, pickups, stasis chambers, spawn hatches,
repair stations, barricades, plates and speed ramps occupy authored markers.
Each zone has five spawns, one flag base, one Shield Core and one repair station.
Two regular hatch spawns sit inside each cistern; three stasis chambers occupy
the exterior spawn locations and face the cistern centre. The recessed hatch
pairs face each other. Cistern
floors and underlying terrain contain matching stepped hatch wells.
The corpse-follow death camera freezes its position at 1 m above the sea and
continues looking at the falling body.

Each floater shuttles at 1 m/s along the long axis of its designated
10 × 17.5 m span, giving 7.5 m of centre travel. It starts at the authored
endpoint and reverses at the opposite endpoint. Vertical bob is
`0.5 × sin(2 × elapsed_seconds)` metres: ±0.5 m amplitude, 1 m/s peak
vertical speed. Native thruster vector clips direct the exhaust against travel.
The junction rotates clockwise from overhead at 0.5 m/s at the 11.25 m arm tip
(approximately 141.37 seconds per revolution). Its hub, pickups, thruster and
collision rotate together. Gameplay motion uses the replicated match clock;
Reduced Motion freezes cosmetic ocean animation while retaining carrier motion.

Carrier collision uses AnimatableBody3D and native machined shells, including
fixture wells with 1 mm clearance per side. Navigation samples follow their
carrier transforms; cross-deck links refresh at 2 Hz after support and jump-arc
clearance checks. Pickup contact points follow their mounted fixtures.
The two side speed ramps release toward supported spots on the opposing
mainland; map data specifies the ballistic speed and landing position.
Ramparts uses gravity multiplier 1.0. Crossing the water datum at 0 m reduces
AH to zero through the ordinary fall hazard. The lake supplies no walkable
collision. CTF bases use authored nonblocking capture volumes on cistern floors.

Ramparts uses a dusty peach Martian daytime sky, warm sunlight and sky ambient
fill. Pole lights are excluded from the generated placements. The atmosphere is authored in
`library/models/maps/ramparts/settings.json` and handed off into map data.
Side-platform barricades and
pressure plates share a quarter-turn orientation with the plates facing their
nearer deck edge. Containers face the larger clear deck area; front doors open,
rear doors stay closed, and the repair bay entrance follows the container front.
These layout rules also drive the regenerated fixture wells and colliders.
Cliffs, summit ground, platform
regolith and prop aprons share one original Martian PBR texture set. Terrain,
elevation, material selection and lighting recipes remain generator-owned.
Ramparts and Skyfall platform sconces retain their emissive models without
illumination or mesh shadow casting, including under the High preset. Their
source handoffs own this map policy independently of interior architecture lights.

Ramparts occupies a circular crater lake 150 m across and 15 m deep. A continuous
mountain rim surrounds the water, with dunes and geometric fractured stones.
Terrain3D bakes the basin and deposits; closed native meshes own runtime
rendering and collision. Mesas extend below the lake bed, while all deck and
fixture elevations retain their 10 m datum. The crater floor and mountain rim
are scenery outside the traversal bounds; water contact remains lethal.

Ramparts uses the original `lake.gdshader` surface:
analytic swells and derivatives, distance-filtered capillary ripples, dielectric
reflection, depth absorption, foreground-guarded refraction, shore wash, crest
foam and submerged caustics. Rock shading uses world-space strata and wetness.
The water's fine central mesh joins a flat horizon ring; surface normals are
evaluated per fragment across both meshes.

Skyfall is a 75 × 75 m lunar map. Its floating lower decks are at 22 m, higher decks at
26 m and rooftops at 30 m. The depressed lunar impact basin, fissures and
surrounding fractured rim are lethal scenery. There is no playable common ground or perimeter wall. Floating floors instance the library's shared map
platform and bridge builders on authored gizmos, with native collision companions.
Stacked decks omit optional underbodies.

Map geometry ownership: only integral platform and bridge castings, integral weapon walls,
pillar mounting pads above/below platforms, and required Boolean cuts/wells belong
to the map geometry budget. Separate authored models (pillars themselves, thrusters,
sconces/battens, architecture, weapons, ammo and gameplay fixtures) never count
toward that budget: place named gizmos, then import the native assets in previews
and runtime with identity local transforms. Lunar scenery is a separate gizmo
instance. Preserve every native detail. Skyfall has a 75,388-triangle map-owned budget; other map builds
use the 25,000 default. Report imported asset counts separately.

Every sunken placement uses its native outer footprint plus **1 mm per side** in
both visual and collision Boolean cutters. Thus a 1 × 1 m fixture gets a
1.002 × 1.002 m opening. Apply the same rule to rotated/wall-mounted recesses;
do not scale the prop or move its authoritative gizmo to obtain clearance. Platform/lip cutters extend 0.5 m above the surface and are applied before separating regolith for import.

Each map may set `gravity_multiplier` in its catalog entry. The match reads it before creating the arena or robots (default 1.0); a match setup can set `gravity_multiplier_override` before adding the match node. Skyfall uses 0.8; Faceoff uses 1.2. Skyfall therefore has powered release heights of 1.25 m for normal jumps, 2.5 m for charged jumps and 12.5 m for pads. Faceoff uses approximately 0.833 m, 1.667 m and 8.333 m respectively, followed by momentum-driven coast. Higher gravity reduces these heights; lower gravity increases them. The resulting gravity applies to actors, projectiles, falling world objects, casings, and bot jump routes. Jump heights and powered jump-platform travel scale by the same multiplier.

Skyfall Mainland 1 higher-ground decks have no barricades or pressure plates
(Figma update 2026-10-15); their former wells are solid floor. Both zones retain
the Mainland 1 lower-ground and Mainland 2 higher-ground barricade pairs.

Floating deck carriers retain their assembled relative heights during a rigid
rise. Imported architecture and fixture rigs inherit their source gizmos.
There is no separate hatch foundation, MapMount lift or service pit.

Faceoff has graded cover banks and shallow channels around level native building
and fixture seats; its 75 × 75 m play boundary is unchanged. Skyfall overlooks a
deeper impact basin. Both static landscapes use six height-blended original PBR
layers, baked through Terrain3D and machined in Blender, with matching collision.
Navigation bakes only the catalog route footprint, excluding distant scenery.
See [planetary terrain](../library/PLANETARY_TERRAIN.md) for source ownership and rebuilds.

The arena sits on lunar terrain under the original dark starfield and slowly drifting grey wisps in `shaders/original/lunar_sky.gdshader`. Reduced Motion freezes drift. Regolith uses untinted sRGB albedo, OpenGL normal and linear packed AO/roughness/metallic (R/G/B, metallic zero), with world triplanar repeat 0.24 per metre and normal strength 0.55. Low/Medium fixtures are emissive-only; High enable illumination and shadow casting by default. Effect lights remain disabled. Cool moonlight (energy 0.28, pitch -48 degrees/yaw -32 degrees) casts shadows; ambient fill 0.26 retains sheltered visibility. Raster reflection fill uses the shared industrial panorama at strength 0.45 only on authored metallic/glass materials. Authored reflection maps and ambient/raster GI remain enabled in every preset. Diffuse architecture has no specular response. Glass uses the original thin-dielectric shader with authored tint and opacity, including 25% core shells. Static metadata enables shared unskinned geometry for declared-static props while preserving native mounts and parent motion. Preserve readable robot silhouettes and pickups against the dark sky.

Thruster presentation uses `NozzleExhaust` at the animated `ExhaustOrigin` gizmo along local Godot -Z. Original flame envelopes and vortex membranes fit within a 5.5 m length and 0.75 m radius budget, with emission 0.65 and no point light. Rocket exhaust shares this thermal family within 15 cm length and 5 cm diameter. The native `SK_ThrusterExhaust` bore receives the original warm thermal surface without vertex displacement. `NozzleExit` remains the physical exit anchor. Thrusters have no collision model or gameplay collision.

Maps provide match-type-specific spawn points and, for CTF, one flag base per team. DM samples spawn points across the whole map without assigning a robot to a zone. TDM/CTF assign each team to a zone and sample only that zone's spawn points; team membership is balanced under [RULES.md](../RULES.md). Spawn selection should support rapid re-entry to fights without placing a robot directly into an unavoidable attack. Use readable silhouettes, cover, multiple routes, and sightline breaks. The same map may support several match types through separate match-type data; map geometry does not determine scoring rules.

Every map has designated placement **gizmos/markers** for its interactable content. Map data identifies each marker's type and configuration, rather than deriving gameplay positions from decorative geometry:

- **Weapon holder markers** place a holder and assign its weapon. Fit the authored claw grip table to the weapon mesh in the lower 12 cm receiver band within the fingers' 11.4 cm longitudinal reach, rather than the maximum width of the entire gun. Retain that clamp during deployment and spinning, including Reduced Motion. Use the fixture specified in Figma: wall-mounted holders or freestanding item cradles. Payloads inherit the native WeaponMount/ItemMount rig socket.
- A wall-mounted pickup keeps an accessible floor-level collection point separately from its housing gizmo. Import the housing with identity local axes into the raised wall's milled opening.
- **Ammo-pack ground markers** assign the ammo type and place its pack on the ground. The authored `_ammo_col` mesh supplies a nonblocking pickup overlap area; it must never create solid world collision that obstructs robots.
- **CTF flag markers** reserve a continuous 2 m × 2 m floor spot. Skyfall's rooftop flag gizmos align with the bunker/dome's actual floor. The map collision companion carries SK_SkyfallFlagCaptureTrigger_A/B: nonblocking 2 m diameter, 0.1 m high volumes above that floor. Install them as Area3D on layer 0 with robot mask 2 and exclude them from navigation geometry. Persistent team rings mark destinations independently of flag state.
- **Item-table markers** place an item table and assign an Energy Core or a zone Shield Core.
- **Repair-station markers** place exactly one **2 m × 2 m** repair bay in each zone, with an entry direction, occupant center, shield boundary, welding-arm pivots/targets, sparks/fume origins, status lights, and a safe walk-out path. Keep its working volume clear of walls, pickups, spawns, and CTF capture triggers.
- **Portal markers** place portals and link each one to its configured destination. An alive robot may enter either the front or back face and always emerges from the **front face** of the linked destination portal.
- **Spawn markers** place eligible robot spawn positions and identify their applicable zone and match type. Their authored facing determines robot yaw; Convert Blender's local -Y forward to Godot +Z when reading the imported prop orientation, and apply the visible robot body yaw when assigning its spawn. Keep robots hidden until the hatch opens, then use crouched idle on the rising plate until it reaches the deck. DM can use all map-wide DM markers; TDM/CTF use only markers in the robot's assigned team zone.
- **Pressure-plate and barricade markers** place and link plates to the barricade each controls.
- **Jump-platform markers** place launch platforms with their intended surface orientation, including slanted platforms.
- **Opening-camera markers/path** identify a center view and a wide view that covers both spawn zones, with the path through the map's five-second assembly animation.
- **Thruster markers** place the rocket thrusters beneath floating map pieces. Each thruster defines **fire, flame, and fumes origin markers** for its effects.
- **Arena mounts** place the chosen map at the arena's `MapMount` and the jumbotron at the arena's `JumbotronMount`. Attach both with identity local transforms so the exported gizmos own height, orientation, and motion. The arena/crater rests on world ground; its floor opens and the map rises on its mount. The jumbotron stays on its own arena mount, independently of map assembly. Its screen content targets and lighting zones belong to the jumbotron asset. Keep it clear of projectile and player traversal paths.
- **Jumbotron heights:** Skyfall's authored placement is 35 m, 5 m above its 30 m rooftop level. Faceoff's authored placement is 10 m above ground. The short arena benchmark alone raises Faceoff's jumbotron to 20 m; Skyfall keeps its authored height. Change the source map gizmo when changing normal gameplay placement.

- **Flag capture visuals:** `FlagBaseEffect` uses an original circular interference field on the library axial card, retaining the two-metre footprint, team tint and independent instance materials. Reduced Motion freezes animation.

Stepping onto a pressure plate toggles its linked barricade: an open barricade closes, and a closed barricade opens. If a barricade has stayed open for **30 seconds**, it closes automatically. A later plate activation can reopen it and begins a new 30-second open interval. The plate uses its authored `SK_PressurePlateTrigger` collision area on the animated `Plate` bone; the first eligible entrant plays `press`, the last departure plays `release`, and standing on it does not repeatedly toggle the barricade. The repair station uses its authored `SK_RepairStationPadTrigger` area on `Root` to establish pad contact before checking AH and movement. Do not replace these footprints with center-distance thresholds. See [RULES.md](../RULES.md) for the state rule.

Stepping onto a jump platform launches the robot **away from its surface**, along the direction opposite the angle its surface faces; a slanted platform sends the robot along that slant. The launch speed is **10 m/s**, with a target of **10 m of upward travel at gravity 1.0**, scaled by the match gravity value like other jumps. The robot can steer while airborne. The powered-lift method is specified below.

The library currently includes ground/wall weapon pickers, barricades, jump platforms, pressure plates, and portal gates. Their shared exit, safety, trigger, and feedback rules are below. Define each interactable's reset behavior in map data before using it in a map. An inactive or unimplemented prop must not appear to promise an interaction that does not work.

Routes must let players reach combat, pickups, and objectives without a single mandatory chokepoint on every approach.

### Continuous prop motion during play

The map assembly **starts** arena machinery; it must remain animated for the rest of the match. During Active play, play each prop's exported loop on its animated rig and layer it with state changes. Use the action names and bone attachments exported by the asset library, rather than replacing them with whole-node rotation or hand-authored pivots:

| Prop | Active-play loop | State transitions and attachment rule |
|---|---|---|
| Platform thruster | `idle` station-keeping gimbal motion, with continuously emitting exhaust/flame/fumes from its nozzle markers. | Use `sweep` for a showcase or an authored moving-map event; blend back to `idle` when the event finishes. `vector_*` poses are available for directed thrust. Decorative vectoring does not move a platform or change gravity unless the map event explicitly does so. |
| Portal gate | `active`: field carriages sweep and flywheels spin; the portal field shader remains live on both faces. | Play `activate` before the first `active` loop and `deactivate` only when the portal is intentionally disabled. The collision/teleport trigger is enabled only in the gameplay-active portal state; visual motion never changes the front/back entry and front-face exit rule. |
| Weapon holder | `spin` while deployed and holding an available weapon. The mounted weapon follows `WeaponMount`; claws retain the grip angle for that weapon. | `deploy` reveals the weapon. On successful pickup, stop `spin` at its authored zero-degree boundary, release the weapon, play `retract`, and begin the 60-second restock. At restock, deploy the same designated weapon and resume `spin`. |
| Item table | `spin` while deployed with an available Energy or Shield Core following `ItemMount`. | On successful pickup, stop `spin` at its authored zero-degree boundary, play `retract`, and begin the 60-second restock. Deploy the assigned item and resume `spin` when ready. An ineligible touch does not interrupt the loop or start restock. |
| Jumbotron | Layer rotor `hover` with steady spotlight `flood`. Its screen and marquee materials display live match time, score, and concise arena notices. | Start rotors with `spin_up`, enable lights with `lights_on`, and hold `flood` throughout play and results, including Reduced Motion. At match end, show results, then use `lights_off` and `spin_down` only when shutting down the arena. Screens do not become a second source of scoring truth. |

These are **visual loops**, not repeated gameplay interactions. Pickup eligibility, restock, portal transfer, score, and actual moving-map geometry remain authoritative state. An interrupted or late-joined online client receives each prop's state and loop start/phase time so it displays the same deployed, recharging, or active condition without resetting a holder or portal to its opening animation. Cosmetic loop phase may be reconstructed locally from the server clock; clients never send prop state changes. Keep mounted payloads, collision, trigger volumes, exhaust origins, spot beams, and audio emitters attached to their exported bones/gizmos so they follow motion. Loops must join their transitions without a visible snap, stay inside each asset's checked motion envelope, and have distance-based animation, light, particle, and sound budgets. A low-quality setting may reduce decorative effects or spotlight motion, but cannot hide a ready pickup, active portal, arena-event warning, or objective state.

Weapon holders and item tables transition from completed `deploy` into their authored looping `spin` animation while stocked. A successful collection grants the item immediately, hides its payload, and starts the 60-second cooldown; the empty holder finishes its current four-second turn at the authored zero-degree boundary before `retract`. Cooldown prevents a late deploy-completion event from restarting it. Restocking plays `deploy` again, then resumes the spin loop. Holder claw angles are fitted from the asset's grip table to the weapon's exported width and retained through deploy, spin and retract. Payload and collision remain attached to the animated mount, for floor and wall installations alike.

Portals play `activate` for two seconds before `active`. Both linked gates must have completed activation and the match must be Active before teleportation is available. Only the inward-facing emitter lenses use the dedicated `M_PortalStatus` material: red while unavailable, green while usable. Outer strips and the header keep their authored `M_Emissive` finish. The field is visible only while travel is available. Leaving the match disables travel and turns the lenses red immediately; machinery finishes its current loop before `deactivate`.

The jumbotron starts `spin_up` and `lights_on` with arena assembly, then independently drives rotor `hover` and steady spotlight `flood` during Active play. Imported static tracks are removed from the other channel so lighting cannot overwrite rotors. Before play, during results, and with reduced motion, lights hold `flood`. Results keep rotors running and display the authoritative winner/draw text and score. Returning to the menu fades lights with `lights_off` and completes the current rotor turn before `spin_down`; arena teardown waits for those transitions. Screen and marquee textures refresh four times per second, or once per second beyond 60 m; arena warnings appear on the marquee for ten seconds.

The current presentation budgets are provisional tuning values: decorative rig samples run at physics rate within 25 m, 10 Hz from 25–60 m and 4 Hz beyond 60 m, while clocks and one-shot transition completion always advance at physics rate. Reduced motion holds decorative loops at their stable first pose, freezes portal swirl, and uses the jumbotron's flood pose without disabling interactions. Thruster exhaust retains its flame core; distant/reduced effects omit ribbons and use 25% of particles (50% at medium distance). Spatial audio retains its existing distance culling and bounded voice pool. All twelve authored jumbotron beam mounts remain active regardless of camera distance, cast shadows against map decks and robots, and use energy 4.0 with attenuation 1.0; maps can tune the energy through `machinery.jumbotron_light_energy`. Camera distance only budgets decorative rig sampling, never gameplay illumination. These budgets must not obscure ready pickups or portal status. `PropMotion.snapshot/restore` preserves clip, loop phase and queued transition for interrupted presentation; delivery of those states to late-joining clients still belongs to the pending online match transport.

### Repair-station placement and presentation

The projected barrier uses the dedicated `repair_barrier.gdshader`, with a faint shield-green membrane, fine hex grid, slow scanning pulse and independent station protection. It preserves the native barrier shape; Reduced Motion freezes the scan. It is visible from one second through deactivation, then hides immediately on release or abort. An approach label names Ready, Shield Activating, Repairing, Shield Deactivating, Recharging, or Unavailable and shows the current phase's remaining time. Nearby HUD feedback distinguishes eligibility from protection; station protection is labelled separately from SH. Ready has the ready hum, welding uses the repair loop, and the start/stop recording marks activation and deactivation. Recharging is silent.

The match owns station termination: finish/cancellation, shutdown, robot removal and invalid geometry use the same idempotent abort path. Missing/freed occupants, missing or disabled trigger/body collision, and movement of the assembled station invalidate a use before any refill. Arena events must call `set_repair_geometry_valid(station, false)` before removing safe station geometry, and restore it with `true` only after the bay and exit are safe. Restoration preserves any recharge remaining. A new match clears occupancy, recharge and exit history; an ordinary completed use requires its previous occupant to leave the bay before reuse. `ArenaMatch.remove_robot(id)` releases repair before removing a disconnecting robot and resolving roster cancellation; network transport remains responsible for calling this roster hook.

Repair-station status surfaces (pad/emitter rings, tower cells, and carriage indicators) use a separate `M_RepairStatus` material. They glow green only when the match is Active and the bay is unoccupied with no recharge remaining. They turn red immediately when activation claims an occupant, remain red through welding, deactivation and the 60-second recharge, and return to green when recharge finishes. Countdown, results, interrupted use and arena shutdown also show red. The welding arc and overhead downlights retain their authored materials; the projected barrier shares the robot shield shader; status tint never changes repair timing, eligibility, protection or refill rules. Welding glow, flashes and sparks use the rig's animated `TorchTip` and exported stroke windows; see [WEAPON_EFFECTS.md](../WEAPON_EFFECTS.md) for emission and distance budgets.

The repair station is a clearly marked 2 m square bay, articulated arms facing an upright robot, a floor status ring, and a projected barrier that encloses the occupant without hiding it. The station needs distinct **ready, shield activating, welding, shield deactivating, and recharging** states readable from an approach. Author one-second shield activation and deactivation animations around the five-second welding animation. Welding tips, spark/heat/fume emission points, shield perimeter, entry/exit, and robot alignment are authored markers on the asset, not offsets guessed in gameplay code. During map assembly, power its floor ring and arms with the other fixtures; no robot can use it until Active play.

Place it where a damaged robot must leave a fight to reach it, with visible approaches from at least two directions and cover that supports entry without making the station an unassailable CTF base. Do not put it on a moving piece unless the piece can keep the occupant, barrier, and exit safe through every event phase. The barrier is solid to incoming combat traces/projectiles only after its one-second activation finishes and until its one-second deactivation finishes; it must not block a mandatory route for other robots. Once deactivation ends, the robot is immediately vulnerable while walking out; do not add a second exit shield. The station's **60-second recharge** starts when deactivation finishes or the use is interrupted and is independent of map-pickup restock.

## Signature arena events

The opening assembly establishes that the arena is a live machine. Each launch map should also author **one readable mid-match reconfiguration**—for example, a bridge translating, a cover bank rotating, or a route opening as a thruster fires. The event is scheduled by the map and server, not by random local client timing. It alters navigation and sightlines, **never the score rule**. At least **10 seconds** before movement, show an in-world light/siren and a compact HUD callout; show the destination path with motion cues during the event. The machine must not crush or drop a robot without a visible escape route. A robot standing on moving ground rides with it. Keep at least two traversable routes between the two zones and common ground before, during, and after the event. CTF bases and flags remain reachable throughout.

Map events are content, not mandatory chaos: a development/test map without an authored, validated transition stays static after assembly; **release maps require one**. Events cannot begin during the five-second movement-locked opening countdown; later individual respawns do not postpone a scheduled event. Pickup timers, projectiles, flag state, and match clock continue through the event. The server publishes its start and end times; bot navigation switches to the appropriate route graph. A late join receives the current piece state and event phase before control begins.

## Interaction safety and feedback

- Pickups and grounded CTF flags use **contact** on an eligible robot. A holder is not ready until its deploy animation finishes. Show pickup labels only while the corresponding item is present, ready, and eligible for the local robot; hide labels while a holder is closed or restocking. The holders' authored `M_Emissive` surfaces glow green while available and blink red while unavailable. Show a brief type/name and amount on successful collection. Ineligible contact leaves the object available and may show a small reason cue to the local player. The same contact frame can grant an item only once. A home or returned flag stands on its `GroundMount` legs with its team-colored cloth waving at 75% opacity; carrying folds it with `stow`, then loops `flutter`. Team-color updates retain that opacity. Its metal and painted hardware keep the asset's authored materials.
- Energy and Shield Cores retain the current library models on native ItemMount sockets: a blue Energy Core cube with a lightning bolt and a green Shield Core cube with a shield symbol. Both have a 25 cm hollow glass cube, 5 mm walls, 25% opacity, corner supports and base within 26 cm bounds. Preserve native materials and the counter-rotating Outer/Inner spin animation. Death drops use the separate 10 cm rounded energy_core_pickup model, including online replicas; no spherical VFX replacement hides the pickup cubes. Falling deaths leave no drop.
- Portals accept either face, then place the robot clear of the **destination front face**, oriented along that face's outward normal while preserving its movement intent. If the exit volume is occupied or blocked, seek the nearest safe marked offset; if none exists, cancel transfer and leave the entrant on the source side. Apply a **0.5-second** re-entry lock after a successful exit to prevent an immediate loop. Carrying a CTF flag does not block portal travel.
- Pressure plates react to an eligible robot's entry edge, including multiple robots entering separately. A barricade emits a clear warning cue before its 30-second automatic close and never closes through a robot; wait until the closing volume is clear, then close. Plate activation and open timers remain server authoritative.
- A jump platform launches at **10 m/s** along its authored outward direction and applies a short powered lift until the robot reaches the specified **10 m / gravity value** vertical travel target, then hands off to ordinary gravity. This powered phase resolves the otherwise incompatible 10 m/s initial speed and 10 m height under normal ballistic gravity. The robot can steer laterally throughout; a ceiling or collision can stop the lift early. Show a charge/launch cue from the platform before and at contact. A CTF carrier can use it.
- For **every initial spawn and respawn**, first filter to the match type's valid markers: all DM markers across the map, or only markers in the robot's assigned TDM/CTF zone. Exclude markers inside collision, overlapping another robot, crossing a fall boundary, or otherwise immediately lethal; choose **uniformly at random** from the remaining markers, with no preference for the previously used point. Reserve selected markers for simultaneous opening spawns so robots cannot overlap. If none is safe, wait briefly and retry within the **same eligible set** rather than spawning in the opposing team's zone or an unsafe location. Online servers and the Instant Action match controller own the random choice; clients and bots do not pick their own spawn.
- Spawn points and portal exits cannot place a robot inside collision or immediately across a fall boundary. Spawn invulnerability never protects against leaving the playable map: crossing the fall boundary returns the robot to a newly selected safe spawn immediately, resets its five-second protection, and awards no death or kill. This prevents spawn-camping through a bad marker while keeping combat invulnerability rules unchanged.

## Map acceptance gate

For each supported match type, verify playable spawns for 2–10 robots, fair first pickup access, the five per-zone weapon types, each ammo type, Energy Cores, two Shield Cores, one per zone, **one repair station per zone**, rocket contention, CTF flag routes where used, portal exit safety, jump trajectories, barricade timeout, and 60-second pickup restock. Test repair eligibility at 50/51 AH, one-robot occupancy, vulnerability during the first second, protection during welding and deactivation, refill at six seconds, release at seven seconds, EP-drain pause, recharging, both-team access, CTF carrier handling, and safe walk-out. Test low EP travel time between Cores, long rifle/rocket sightlines, and the mid-match event with 10 robots and bots. Validate navigation in every piece state, flag reachability, and that the opening camera never clips into geometry. Map-specific counts and coordinates live in map resources; this guide defines the shared contract.

Flush fixture cutouts must use the prop footprint in the mount local frame: jump pad 1 × 1 m, pressure plate 2 × 1 m, spawn point 2 × 2 m, barricade 4.11 × 2.126 m, floor weapon holders and core tables 1 × 1 m. The visible deck and map collider must both leave these openings clear; do not lift props above the floor to hide overlapping geometry. Jump-pad and pressure-plate faces include embossed metal tread diamonds, which are intentional geometry.
Map side-weapon walls and raised pillar sockets are fused into the deck shell. Their sides meet the ground surface squarely, without a base chamfer or a separate-looking seam; the visual and collision exports share that geometry.

## Skyfall

The map follows the refreshed 75 × 75 m Figma layout. Each zone has a lower
mainland, higher floors, rooftops and islands. Native bridge modules connect
the lower mainland to its first island. Pillars support stacked floors; thrusters
mount under closed tapered base-platform chassis. The deepest chassis
bottom is 19.7 m above the lunar ground. Adjacent deck tops are 4 m apart.
Pillars hold the native 2.25 m pose between 0.10/0.85 m mounting pads. Jump pads and portals connect levels and
common ground. Collision recesses include every intersecting module and support
pad, with closed wells beneath sunken fixtures.

Every imported prop's origin and axes align with its source gizmo. Each ammo
pack has a separate gizmo; pair origins are 20 cm apart. Payloads attach to the
holder/table's own rigged payload gizmo. Common-ground props face the map centre,
and contained placements rotate with their building. Long containers hold both
native open poses; short containers hold only rear_open, with the front closed.

Common-ground pulse guns belong to teams A/B and target the nearest opposing
robot within 20 m. They fire once per second for 10 base damage (10 AH against an unshielded robot). They are disabled in DM. Their native yaw/elevation rig and
baked piston action drive aiming. Shots use the Galaxy Coldcase pulse behaviour,
visuals, audio and hit effect, with a swept projectile collision and cover check.

Jump pads carry square mint energy pulses with closed 2 cm thick outlines that rise and fade. Their inner and outer walls remain visible edge-on. Reduced Motion
freezes decorative phases; headless matches omit these render meshes. Map
fixtures retain their authored idle animations during play.

**Open decision:** Skyfall remains static after assembly; its refreshed design
specifies no mid-match event.

### Portal field presentation

Portal fields use the original blue interference shader with procedural turbulence and a separate soft glow pass. Both layers retain the native skinned field, skeleton and bind transform without expanding outside the authored opening. Both faces render. Availability still requires both linked gates ready in Active play; Reduced Motion freezes shader clocks. Triggers, teleport destinations, navigation links and model exports are unchanged.

Flag capture pads use the original circular field shader on the two-metre library card. Team-tinted interference and subdued glow retain their footprint; Reduced Motion freezes the clock. The effect has no light, collision or capture-rule authority.

`tools/preview_portal_vfx.gd` captures both portal faces and Reduced Motion in `reports/portal-{front,back,reduced}.png`. Effect composition and lifecycle are described in [WEAPON_EFFECTS.md](../WEAPON_EFFECTS.md).

### Map surface materials

Imported architecture platforms retain their native finish, materials and
painted UVs. Lunar landscapes use six blended planetary PBR layers; platform regolith retains its canonical material. Integral pickup walls
and pillar mounting pads share the map floor finish on every face. Runtime
lighting remains dynamic. Collider companions have no rendered material role.

All pads target 10 m upward travel at gravity 1.0, including Skyfall lower-mainland pads. At the release height, powered lift ends while upward velocity stays intact: the robot coasts higher, slows to its apex, then falls naturally. Ceilings can stop it earlier. Platform and architecture luminaire gizmos import native emissive-only sconce/batten models with identity transforms. Docked internal seams omit intersecting lamps.

Thrusters attach directly to the base platform’s native ThrusterMountNN socket
with identity local transforms. Figma supplies counts and platform assignment;
map XY does not override the authorized socket layout. The map metadata
records parent_fixture/parent_socket and matching world gizmos for inspection.

Bots on Skyfall use vertical pad departure until they clear the destination
deck, then steer inward. Higher-ground landings stay outside rooftop overhangs.
Architectural threshold climbing uses the lowest clear lift up to the shared
maximum step height, preserving clearance beneath low native door lintels.

### Native platform attachments and chamber departures

Skyfall thrusters attach directly to the imported platform's authorized
`ThrusterMountNN` sockets. Source placement gizmos record those exact frames;
no map-specific XY overrides or fallback transforms are permitted. Sconce and
batten models likewise use native architectural light sockets and their
`LightProjection` frames.

The stasis chamber's native `PlayerMount` defines the standing position and
front axis. Navigation reserves a directed departure through its door, then a
short drop from the 0.53 m pedestal to the surrounding deck. The one-metre
floor grid must not send a spawned robot toward a sample behind the chamber.
The door may be closed while navigation is baked; robots remain in spawn
protection until the native opening animation finishes. A short drop completes
only once feet reach the landing height, not while still on the pedestal.

Skyfall links each lower-mainland portal to the rooftop portal in the same zone.
Both directions stay within that zone; crossing to the enemy zone uses map routes.
No navigation cell or drop route treats the lunar surface as playable. Native
lunar/dune collision bodies carry lethal_surface metadata: authoritative contact
causes an environmental fall death, including flag return. Spawn protection
returns the robot safely without scoring a death. SurfacePlacement excludes
these colliders from corpse, core and flag landing selection.

### Native-map geometry

Skyfall owns 75,228 triangles (16 integral platform castings and four native bridge halves, including required machining); its geometry budget is 75,388 triangles. Faceoff owns 3,259 additional machining triangles under its 25,000 default. Separate authored props and lunar scenery are excluded and imported on authoritative native gizmos. Platform underbodies extend 1.5 m below the 0.8 m deck, making the lowest Skyfall belly 19.7 m above the nominal zero datum. Platform/lip cutters use 1 mm clearance per side and extend 0.5 m above the surface, clearing regolith before its separate export. The stitched planetary scenery is a closed volume with an irregular rim and circular outer footprint. Empty stasis chambers are closed; spawning opens them and full clearance of the native swinging door closes them once.

Faceoff keeps a bounded 75 x 75 m playable lunar area: invisible perimeter walls at +/-37.5 m extend from -2 m to 100 m, containing airborne routes as well as walking. Its graded playable terrain blends into the exterior impact rim. Skyfall has no play-area perimeter and lunar contact is lethal.

Cradle payload origins and all axes align to the native `ItemMount` gizmo, parented to `ItemSocket`, with identity local transforms. Occupied cradles hold the native `close` pose; empty cradles use `open`. On respawn, close the claws before showing the payload. Previews and showcases use the same occupied pose.

Shared platform tops are continuous within a perimeter border, with no internal checker grid. Fascia lamps and service recesses share a symmetric spacing plan with at least 40 cm housing-to-recess clearance. Sconce geometry remains a separate native import; gizmo-only previews hide it.

### Native mechanical architecture and fixture beams

Skyfall imports `pillar_platform` only below each pillar and
`weapon_holder_wall` at its eight raised pickups. The ram and holder are children
of the delivered `PillarMountTop` / `WeaponHolderMount`, with identity local
transforms. No upper pillar block is used. A 1 m base and 2.2 m native eased ram
span the 3.2 m clearance beneath the next 0.8 m deck. These architecture props
have independent budgets; Skyfall's placement rig has zero render triangles and
its floor-helper/machining total is 75,388.

All luminaire geometry is imported on original model sockets. Room/ceiling lights
face the authored inward normal; the lunar dome has one top-center sconce.
Platform ceiling batten grids retain only physically supported mounts after
machining. Each pole-light head and each animated jumbotron beam uses its native
projection gizmo, cone and range. Runtime fixtures retain their emissive materials and native rig animation without creating local Light3D nodes. Blender preview lights align their -Z to the source projection's +Y. Gizmo-only map previews omit imported lamp geometry and beams.

## Shared builders and lunar crater

Shared scripts live in `models/maps/common/platform/` and `models/maps/common/bridge/`.
The single dimensional platform builder unions proposed extensions before laying
out its perimeter, adds the optional 1.5 m underbody and surface regolith, then
applies placement cuts.
Both maps use a continuous lunar crater with an irregular raised rim and shallow,
walkable faceted stones. Faceoff retains its play boundary; Skyfall lunar contact
remains lethal. Imported scenery and props are excluded from map geometry totals.

### Walkable ground detail

Small stones and gravel use native terrain collision, with visible interior
peaks at most 0.24 m. Fixture seating and approaches are kept clear. Walk-route
clearance tests the robot motor's supported step height and the whole raised
capsule, including headroom. Low stones between navigation samples remain
walking edges; taller obstructions and low lintels remain blocked.

Skyfall lunar contact kills the robot and scatters its physical body assemblies against the lunar collision surface for four seconds. A separate grenade-style impact cloud uses reduced dust and no extra flying fragments. The local player receives the red screen-edge impact flash and a bounded camera shake, disabled by Reduced Motion. Only genuine falls into the void continue below the arena.

Normal and charged jumps use the same powered-rise/coast handoff: their release cutoffs are 1 m and 2 m divided by the map gravity multiplier. Launch speed sqrt(2 * effective gravity * release cutoff) therefore stays independent of that multiplier. Jump pads retain 10 m/s through their 10 m divided by multiplier cutoff. None zero vertical velocity at release. At 1.0 gravity the approximate unobstructed apexes are 2 m, 4 m and 12.55 m; Skyfall (0.8) gives 2.5 m, 5 m and 15.69 m; Faceoff (1.2) gives 1.67 m, 3.33 m and 10.46 m. Collision can shorten these arcs.

Static/fixed-pose mesh sharing must wait until the posed skin palette has reached the renderer. Cache pillars only after their native support extension is sampled, and key cached geometry by mesh, skin and full pose. Snapshot eligible mesh instances before deferring the bake so subsequently attached animated props remain animated. Keep all native sockets, colliders and per-instance material overrides.

Skyfall Mainland 2 rooftop flak pickups at Figma nodes 2011:242 and 2011:415 use item cradles. Item-table ItemMount is authored 20 cm above its plate surface; runtime consumes that native socket without an added offset.

Cargo lift descent checks the swept native platform bounds against living robot capsules before sampling the next moving pose. A robot underneath reverses the lift upward from its current height; protected and airborne robots are also obstructions. Riders standing above the deck continue to be carried normally.

The Faceoff habitat pod resolves its reversed Figma footprint axis before orienting the native front toward the lunar centre. Rocket ammo stays in front of its cradle. The native cabin is raised approximately 20 cm and each landing foot moves inward 20 cm; pickup heights and entry jump links follow its floor metadata.

The Faceoff Shield Core cradle inside the common cargo container inherits the native 0.16943 m walkable floor height, including when its Figma marker is outside the container's group. Its exported placement drives both the visible base and pickup socket.

Item cradles export a fixed BaseCol and four separately named Claw<Tag>Col objects bound to their native Clamp<Tag> bones. Collection disables all four claw bodies immediately (deferred safely to the physics boundary), along with hidden weapon payload bodies; the plinth stays solid. Closing and showing a respawned item restores collision per instance. Online fixture snapshots use the same transition.

High enable managed fixture illumination and shadows by default. Sconces and battens use rectangular area lights at sconce and batten LightProjection sockets, matching their emitting faces (0.36 x 0.22 m and 1.10 x 0.16 m). Pole heads and the twelve jumbotron heads retain native cone angles, range and animated orientation. Outward offsets clear guards and glass. Light and shadow settings apply live to existing and late-created fixtures in local/online matches. Low/Medium leave runtime fixture lights hidden with zero illumination mask. Effect lights remain disabled. All presets use Forward+ raster rendering.

### Faceoff upper-floor pickup fixtures

The first-floor Flamethrower pickups in Bastion and Laboratory use native
item_cradle models on their authored floor gizmos. Attach each weapon to the
cradle's ItemMount, preserve the native close/deploy behavior and four claw
colliders, and do not machine recessed weapon-holder pits beneath them.
The source placements follow Figma nodes 2004:106 and 2001:34.

Stasis-chamber spawns face the chamber’s front opening, using the imported PlayerMount +Z axis projected onto the floor. Initial spawns and respawns reset body, view and aim to that frame. Local mouse input and online look commands cannot change facing during chamber deployment or the opening countdown. Normal aiming resumes once the chamber deployment and countdown are complete; ordinary active-play protection does not lock aiming.

Gun Game retains ammo, Energy/Shield Cores and repair fixtures. Its weapon
holders remain retracted with closed, collidable hatches and no pickup payload;
freestanding weapon cradles are absent. Validate both maps in this loadout.
