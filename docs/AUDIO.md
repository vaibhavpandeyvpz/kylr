# KYLR — audio and robot callouts

Audio should make combat legible before the player reads the HUD. It belongs to the same arena-control world as [DESIGN_LANGUAGE.md](DESIGN_LANGUAGE.md): precise electronic interfaces, powered machinery, metal robots, and short, characterful speech. Every important event has a distinct cue family, but repeated fire must not turn the mix into constant noise. [WEAPON_EFFECTS.md](WEAPON_EFFECTS.md) owns animation/gizmo timing; [WEAPONS.md](gameplay/WEAPONS.md) owns shot cadence and damage.

Normal application shutdown stops music and voices and allows the mixer to
retire them before quitting. Audio runs through official Godot 4.7.2. Validate
playback, bus routing and clean shutdown in the exported package; headless
checks do not verify audible mixing or establish gameplay FPS.

Spatial low-pass buses have fixed sends configured before playback: each world
slot has World, Critical and Announcer routes; ambience and speech slots have
their own routes. Reusing a voice selects a player bus and its filter without
changing mixer bus sends. Voice limits and mix destinations remain explicit in
the audio director.

Audio occlusion keeps all three geometry rays live for each sample. Their
query parameters are reused only within that synchronous sample; contacts and
material transmission are never retained between samples. Voice updates share
one current listener position within a physics callback. Moving listeners,
emitters and geometry are sampled again on subsequent updates. These allocation
savings do not change acoustic cadence, ray budgets, voice priorities or cues.
Inactive weapon loops still receive their normal stop request, but no longer
look up an unused muzzle socket each rendered frame. Active loops continue to
read the current muzzle and follow its live position.

The rendered diagnostic's optional `--costs` mode records inline audio timing:
voice updates, acoustic samples and total physics-callback time, plus callback
and sample counts. Total time includes the other stages; do not add them together.
These timers observe normal execution without replacing callbacks, adding rays
or changing scheduling. They are disabled during ordinary play and the preset
FPS matrix. Instrumented timings are diagnostic evidence, not FPS acceptance.

## Sound hierarchy

| Priority | Events and treatment |
|---|---|
| Critical | Low EP, shield break, flag take/drop/return/capture, match end. Preserve these through ducking and sidechain priority. |
| High | Own shot/reload, nearby weapon impacts, enemy steps, portal/launch, arena movement warning. Spatialize world sounds; keep interface confirmations in a clear local channel. |
| Medium | Distant shots, robots' short contextual callouts, pickups, barricade motion, thrusters. Reduce density when many sources overlap. |
| Bed | Map ambience, thruster hum, music, distant machinery. Sidechain under speech and critical alerts. |

Weapon impact clips sound at the struck robot or surface; there is no separate local hit-confirmation or damage-taken sound. The screen-edge damage indicator conveys attacker direction. Do not play a kill confirmation until the authoritative elimination event arrives. In online play, locally predict only harmless shot/footstep presentation; reconcile visual hits and score cues with the server.

## Spatial sound model

World sounds are **3D positional sources**. Their perceived level falls smoothly with distance: a nearby shot, step, explosion, portal, or thruster is louder; the same event far away is fainter. Use a perceptually smooth distance curve with per-family near and far ranges, rather than a single hard cutoff. Stereo/surround direction follows the source position. Pitch and spectral filtering can carry distance, but must not make a far rocket sound like a different weapon. Map geometry and a closed barricade muffle and attenuate a blocked path; an open portal may carry its own localized entry/exit cue but does not transmit a perfect enemy location through walls.

The listener is anchored to the **local robot's head/ears** for both FPV and TPV. Moving the TPV camera behind cover does not move the listener or grant extra hearing. The local robot's own weapon, footsteps, and interface confirmation use a controlled near-field mix so they remain clear without an excessively loud 3D emitter. HUD/announcer audio is nonspatial; objective world sounds remain spatial unless an explicit team-radio line is sent. Spawn protection and death do not move the listener to the cinematic camera; during the opening/results camera, use a deliberate cinematic mix that does not pretend to provide combat positional information.

The death camera does not move the positional listener. Keep live objective and match-end cues audible during the death animation and one-second hold, with captions for critical events. Match results replace the death view and play their own cue.

Author attenuation profiles by cue family: footsteps have short reach, gunfire and explosions travel farther, thruster beds span a larger area, and UI clicks never attenuate. Set actual metre ranges while playtesting each map's dimensions. Cap distant repeated shots and low-priority emitters before cutting a nearby actionable cue. Validate left/right/front/back localization, verticality on jump platforms, wall occlusion, and audibility with ten robots firing at once.

## Weapon cue contract

| Weapon | Fire and motion | Hit, reload, and idle identity |
|---|---|---|
| Pistol | Crisp suppressed report, compensator/vent gas, slide and casing event. | Sharp ballistic impact, compact grip/holster, no empty-ammo click in normal play. |
| Rifle | Stronger ballistic report, ejection and bolt; scoped report has a tighter tail. | Distinct body/head confirmation only after valid hit; two-second pack change and optic motion. |
| Minigun | Six-barrel motor spin-up, eight discrete reports per second from alternating barrels, casings and spin-down. | Rotor motor remains audible at low level while turning; avoid a single continuous buzz that hides individual shots. |
| Lightning gun | Continuous crackling beam with pitch tied to contact, prong arcs, heat vents. | Beam contact changes texture; orb launch has a separate charged transient and traveling hum. Stop beam sound immediately on release, dry ammo, death, or switch. |
| EMP gun | Air intake and compressed pulse at each shot, whoosh traveling with the charge projectile. | Charge fades with its visual/damage tail between 20 and 25 m; hit has a short electromagnetic snap. |
| Rocket launcher | Tube index, launch, backblast, and impact explosion. | The launch report and spatial explosion supply the audio; the flying rocket has visual exhaust but no flight sound. |
| Flamethrower | Pilot flame while held, ignition, sustained gas/flame roar, fume vent. | Contact crackle and weakening smoke tail; pilot and stream stop on unequip/death, with a two-second reload cue. |

The `Muzzle`, `ShellEject`, `Backblast`, `Exhaust`, `Warhead`, `Vent*`, `PilotFlame`, and other exported gizmos provide event positions; do not attach every sound to the robot root. Loop state must follow fire-start, sustain, stop, reload, death, and camera switch in FPV/TPV. The two camera modes change mix perspective, not gameplay reach or damage.

Every fired weapon has two spatial events when it connects: its report or sustained fire originates at the firing robot's current muzzle, and a separate world impact originates at the actual collision point on a robot or surface. A miss has no impact cue. Hitscan weapons emit the report before the resolved impact; projectile impacts wait until collision. Rockets use their own explosion hit sound at the impact point; if that rocket's launch report is still playing at impact, stop it before the explosion. EMP charges sound at their first direct robot or surface contact. The local shooter's controlled near-field report does not replace the world impact. Pistol, rifle, minigun, EMP and rocket reports and impacts use their corresponding curated weapon clips, including three separately selected pistol impact variants. A discrete weapon hitting an invulnerable robot uses the shared curated shield impact instead of its ordinary hit. Lightning and flame use separate curated continuous loops at the muzzle and contact point; contact loops follow the target and stop immediately on a miss, release, death, or invulnerable target. They play no shield impact against an invulnerable robot. Keep impact ranges shorter and quieter than gun reports, and preserve their actual world positions in event diagnostics.

## World and movement

Every collected dropped Energy Core uses the same `world/pickup_item` recording
as an item-table Energy Core. Homing and contact collections each emit one cue
per Core; full-EP contacts emit none. Cluster arrival sounds are queued 80 ms
apart so cue cooldown does not merge them. Online authority publishes each
collection reliably; the collector hears the local mix and other listeners
hear the positional cue at the robot's body centre.

Repair uses the three recordings from `library/sounds/gameplay`: `repair_ready.wav` is the spatial ready hum, `repair_weld.wav` loops only during welding (seconds 1–6), and `repair_start_stop.wav` plays on activation and again when deactivation begins at six seconds or an earlier interruption stops repair. There is no separate completion chime or recharge sound. Ready and welding loops stop on finish, cancellation and shutdown. `tools/prepare_world_audio.py --source ../library/sounds --repair-only` trims leading/trailing silence, converts to 48 kHz mono 16-bit PCM and smooths loop seams. Recharging remains silent; no synthetic fallback audio is generated.

The runtime footstep loop and its cadence follow measured horizontal displacement while grounded, including slowing against collision. Requested input speed does not keep steps playing when the robot is blocked, and airborne motion stops the loop.

Footsteps reflect surface material (metal deck, grating, concrete, moving platform), gait (walk/run/sprint), and whether the listener is the local robot or another robot. Landings, normal and charged jumps, powered jump-platform launches, portal entry/exit, pressure plates, barricade movement, pickups retracting/reopening, shield activation/expiry, flag interactions, and map assembly have dedicated cues. A repair station has a spatial **ready hum**, a **one-second shield activation** cue, a **five-second** mechanical-arm and welding sequence, the shared start/stop recording as its **one-second shield deactivation** begins at the AH/EP refill, and a silent **recharging** state after release. Welding sparks should have short, varied crackles; their loop stops on completion or interruption. Thrusters have a low bed at distance and a louder, directional flare near their effects. Every authored arena reconfiguration gets a ten-second warning siren motif and a localized mechanism sound. Do not let decorative particle emitters spawn unbounded audio voices.

Continuous prop audio follows the corresponding animation state: a thruster's exhaust bed persists under its `idle` or directed-vector motion, an active portal has a restrained field/flywheel bed, deployed holders and item tables have a quiet motor rotation, and the jumbotron has a distant rotor/spotlight mechanism bed. Start and stop these sounds with the same authoritative prop state that selects the visual loop; a pickup's retract cue replaces its rotation loop until redeploy. Anchor emitters to the moving prop or exported effect marker, spatialize and attenuate them, and virtualize distant repeated machinery before cutting nearby combat or objective cues. A late join should enter the current loop at an appropriate phase without restarting the opening start sound.

## Music and match flow

Use one musical identity across menu, lobby, assembly, live combat, and results. The lobby theme is spacious and mechanical, leaving room for idle robot sounds. The five-second opening countdown accompanies robot emergence on the already assembled map. The active match uses intensity layers driven by **objective pressure**, not raw kill count alone: close score, low time, contested flag, or major arena event may raise intensity. A capture, lead change, match point, victory, draw, or cancellation gets a short stinger that resolves back to the appropriate layer. Music never masks low-EP or flag warnings. Instant Action pause freezes musical timing; online Settings/menu overlays do not pause the match audio world.

Music sources are normalized to -18 LUFS with -3 dBTP headroom. Main beds and
stingers play at 0 dB authored gain; the pressure layer peaks at -6 dB relative
to its source. One-second crossfades, the user's Music volume, critical/speech
ducking and master limiter still apply. Music does not use the combat playback
boost. The default 60% Music setting is an additional user-level attenuation.

## Robot voice and callout rules

Short speech gives robots character and useful information. Bots may say lines like **“I'm hit,” “Got it,” “Cover me,” “Flag down,” “Returning it,”** or a restrained taunt such as **“You like that?”** only at the event that supports it. A callout is **not** a secret sensor: bots never announce an unseen enemy's exact position or a hidden flag carrier. The local human robot may play equivalent automatic pain, pickup, and objective barks, using the equipped robot voice set. Victory emotes can include an authored voice line on the results stage, never as a gameplay advantage.

| Trigger | Audience and content |
|---|---|
| Significant AH hit or shield break | The affected robot may react; an ally hears only if within voice range or if a team-radio line is explicitly designated. |
| Pickup/reload/low EP | Usually local acknowledgement. “Got it” applies only after successful pickup, never after a rejected contact. |
| Enemy eliminated | A living killer delivers one random brief quip, below objective and damage warnings. No speech for suicides, friendly kills, uncredited falls, EP deaths or posthumous kills. |
| Flag take/drop/return/capture; arena event | Team or all-player announcer line with the exact authoritative state. Distinguish home and dropped flags. |
| Match point, time warning, victory/draw/cancellation | Announcer line aligned to the same state and time as HUD/scoreboard. |

Cap ordinary robot barks to **one per robot per 8 seconds** and **two per team per 5 seconds**; critical objective and announcer lines bypass the robot cap and replace preceding announcer audio. Do not repeat the same line twice consecutively for one robot. Limit ordinary speech to one announcer line and two robot lines at a time; replace stale speech instead of queuing it. Contextual repair/energy lines and kill quips use the per-speaker rule below. Use speaker-labeled subtitles and team colours. Provide separate volume sliders for music, effects, interface, announcer, and robot voices; subtitles and voice-callout frequency are Settings options.

## Production and accessibility

### Runtime implementation

The native Godot audio director is split into `scripts/presentation/audio/{director,voice,mix,cues}.gd`, with event profiles in `data/audio/cues.json`. The registry specifies gain, near/far range, priority, per-cue voice limit, emitter cooldown, pitch variation, bus, and optional dedicated loop asset. The curated weapon and world audio is bundled under `assets/audio/weapons/{shots,hits}/` and `assets/audio/world/` as trimmed 48 kHz mono PCM16; the continuous shot and contact loops have end-to-start joins. The authoring scripts `tools/prepare_weapon_audio.py` and `tools/prepare_world_audio.py` reproduce those game assets from supplied source WAVs. Their provenance is recorded in `assets/audio/catalog.json`.

The pool reserves **24 world voices, 9 ambience voices, 10 reserved spatial robot-voice slots, and 8 near-field voices**. Machinery beds use the separate ambience pool so combat cannot repeatedly steal and restart them. A higher-priority audible cue can steal a lower-priority voice within its pool; distant sources are culled. Cooldowns are keyed by emitter, so one robot's shot cannot suppress another's merely because they share a weapon. World one-shots use a bounded sound-travel delay at 343 m/s. Continuous beams, flame, thrusters, and welding have persistent keyed emitters with 60 ms gain ramps.

Spatio is the game's acoustic propagation layer in `scripts/presentation/audio/spatio.gd`. It samples three narrow paths between the robot's head and each active emitter, with a global budget of fifteen physics rays per 50 ms acoustic tick. The path stops just short of the emitter to avoid treating its own surface as cover. Hit geometry has `spatio_material` metadata: concrete, metal, glass, grate, fabric, and open have distinct low/high frequency transmission. Imported collision meshes receive a material based on their authored mesh name; maps default to concrete and fixtures default to metal. Acoustic coefficients and the listening result blend over time so opening a barricade does not cause a sudden volume jump. Authors may set `spatio_material` on a collision body to override the inferred material. Spatio uses gameplay collision, so moving geometry automatically affects propagation. It does not simulate full multi-bounce reverb or use OpenAL Soft; Godot's 3D player handles positioning and panning. Faceoff's basement acoustic zones smoothly increase shared world reverb; no sound is transmitted through portals. Critical cues duck world voices and sidechain the music bus. A master limiter preserves headroom, and the Effects compressor adds 6 dB of makeup gain in reduced-dynamic-range mode. Effects, music, interface, announcer, and robot-voice controls remain separate.

The local robot's `AudioListener3D` follows its head height and yaw/pitch each physics frame. This keeps directional audio aligned to the player's aim in FPV and TPV, independent of the cinematic or third-person camera. Keep physical material assignments and headphone localization in the map playtest checklist.

World voices use one authored near/far attenuation curve while Godot supplies positional panning. At the near distance, the cue plays at its calibrated gain; it falls smoothly to 30 dB below that level at the far distance before virtualization. The bundled clips receive a shared 12 dB playback lift because their source levels and original cue gains left the full combat mix too quiet. This lift does not change the user's volume sliders.

The curated walk recording loops only during grounded travel. Its playback rate is 1× for the 3 m/s walk, about 1.27× for the 6 m/s run, and 1.8× for the 12 m/s sprint; landing uses its own curated cue. Curated portal entry and exit, item/weapon/ammo pickups, reload, repair, thruster, interface, jump-pad launch, and distinct barricade open/close recordings are bundled in the game. The repair station plays the supplied `repair_start_stop` cue as its shield activates before welding and again as welding ends; its supplied `repair_ready` hum runs only while available. A short event history supports audio diagnostics. Tests cover contention, cooldown identity, loop release, and opening/closing occlusion. Review spatial cues, speech and music on headphones and speakers.

Build a cue registry keyed by gameplay event and asset animation event, with variants for material, distance, FPV/TPV perspective, and robot voice identity. Author a small consistent set first, then increase variation. Review the mix under ten-player minigun/rocket/flame combat, not just isolated weapons. Maintain headroom, cap simultaneous voices by priority, avoid painful high-frequency alarms, and expose a reduced-dynamic-range mix. Essential cues also have visible HUD/world feedback, and captions identify off-screen objective and announcer events. A missing audio asset must never block a damage, pickup, or score event.

## Caption and callout delivery

`ArenaCallouts` receives accepted flag take/drop/return/capture, arena warning, low/critical EP, repair/pickup, significant surviving armor-hit, and match-finish events. Speaker/team captions expire after four seconds and never infer hidden enemy or flag-carrier positions. Nearby ordinary robot captions are limited to 25 m. The feed shows natural dialogue with speaker names and team colours; it omits direction suffixes, internal ARENA/POWER tags and textual team/debug labels. Full frequency permits one ordinary line per robot per eight seconds and two per team per five seconds; Reduced uses sixteen seconds and one per team per five seconds; Off suppresses ordinary lines. Consecutive repeated robot lines are suppressed. Critical lines bypass those caps, replace earlier announcer captions while retaining unexpired robot dialogue, and remain independent of volume settings. Caption visibility is controlled by the shared caption preference; objective feed and resource readouts remain available when captions are off.

Bundled ElevenLabs recordings supply robot speech and announcer lines through the same accepted-event delivery path as captions.

Each accepted enemy kill selects one quip on the authority, using a cosmetic RNG
and excluding that killer's previous quip. All listeners receive the same line
and voice identity. Generic lines are available for every weapon; **Boom baby!**
is available only for rocket-launcher or grenade-launcher credit, including a
fall credited to either weapon. **Headshot!** is available only for a rifle
headshot finishing hit. Gun Game uses the finishing weapon before switching.
Every `robot_00`–`robot_09` bank contains all twelve quips in its existing voice,
using ElevenLabs `eleven_multilingual_v2`, the same source processing, pitch,
Voices bus, -8 dB cue gain and shared playback lift as its other speech.

Repair completion says **Let's go!**; low EP says **Finding energy core.**;
critical EP says **Emergency!** in all ten banks. These contextual lines trigger
for human and AI robots and use the same moving spatial source and killfeed
delivery as quips. Resource readouts retain the exact EP state, and the local
low-energy warning cue remains separate.

These lines are spatial even for the local speaker. Their source follows the
robot's current head height and position until playback finishes; distance
attenuation and geometry occlusion use that moving source. Releasing or reusing
a pooled voice clears its emitter reference. These lines bypass ordinary robot
and team timing caps; the next line replaces that speaker's unfinished line
rather than building a stale queue. They remain bounded by the world voice pool
and below critical cues. Callouts Off suppresses them and the 25 m listener
range applies. Matching sentences appear in the killfeed with the usual
speaker/team styling, expiry and subtitle preference. They are live events and
are not replayed on late join.

## Authored playback integration

`data/audio/music.json` registers lobby, assembly, active, pressure, victory, draw and canceled beds plus capture/result stingers. `ArenaMusic` crossfades beds over one second and raises pressure near the time/score limit, on a contested CTF flag, or during an arena warning. The existing Music bus and volume/ducking controls own playback. `data/audio/speech.json` maps accepted announcer/robot text to authored recordings; playback follows the same listener filtering as captions. Critical speech replaces the prior announcer line; ordinary remote speech has a two-voice cap. Online servers publish cues without playing duplicate speech.

Both manifests now use ElevenLabs recordings: 170 robot clips across ten distinct voices, fifteen announcer clips and eleven instrumental music cues. Original MP3 sources and generation/voice IDs are retained in the library. `tools/prepare_speech_audio.py` trims and peak-normalizes 48 kHz mono PCM16; `tools/prepare_music_audio.py` prepares stereo Vorbis at -18 LUFS with headroom and smooth boundaries. `tools/sync_authored_audio_catalog.py` rejects incomplete banks. The curated walk loop still lacks material-specific variants; ten-player headphone/speaker audition remains a review gate.

### Authored speech production

The selected recording provider is ElevenLabs. `library/sounds/speech/recording_plan.json` owns the spoken lines and ten original robot voice directions. `data/audio/speech.json` maps stable event keys to recording IDs under `assets/audio/`, with exactly ten robot banks. At match admission, the authority assigns each robot a random voice from a shuffled ten-voice deck, including human and AI robots. The first ten assignments are distinct. That assignment persists through respawns and is replicated in actor snapshots and speech events, so every listener hears the same voice; caption names remain account names. Dynamic pickup, flag and winner text resolves to a fixed generic spoken line while the caption retains the full authoritative detail. Distinct provider voices are preferred; a per-bank bounded pitch scale supports the approved fallback. All seventeen robot event lines and fifteen announcer event lines have recordings; unknown event keys stay silent. Music is ducked under announcer and robot speech for the actual recording duration.

Flamethrower and lightning gun use the renamed `_primary` shot/contact recordings for their retained continuous loops. Their `_secondary` shot and impact recordings play once per accepted fireball/orb launch or collision, including world hits, with no primary contact loop on those impacts. Secondary muzzle audio follows shot prediction/replication; impact audio follows authoritative discrete audio events. `prepare_weapon_audio.py --only flamethrower_primary flamethrower_secondary lightning_gun_primary lightning_gun_secondary` prepares just these eight source recordings: trim edge silence, retain 10 ms attack / 80 ms release padding and convert to 48 kHz mono PCM16. The four primary loops blend their final 80 ms into the opening for smooth loop seams. The four secondary recordings receive no added fades or crossfades; their audible samples are preserved after format conversion. Original library sources remain intact.

All weapon shot and hit/impact cues, including primary contact loops, secondary shots/contacts, pistol impact variants and shield contacts, play at **0 dB source gain**. They bypass the global +12 dB playback boost rather than compensating with negative per-cue gain. Spatial distance/transmission, user volume controls and shared mix dynamics still apply; impacts are no longer separately lowered relative to muzzle reports.

Speech captions use the upper-right event feed's body font and fading rows
rather than a separate panel in the lower center. Preserve
speaker names, team colours and the existing listener, priority and subtitle controls.
Pickup captions distinguish a weapon from its ammunition; both retain the
shared generic pickup recording through the stable `acquired` event suffix.

Accepted robot callout text is presented in the kill/event feed as a bold,
team-colored speaker followed by “said:”. Announcer speech uses the same feed as “Announcement: …” with a neutral bold prefix. Both respect Subtitles; audio, listener filtering, frequency
limits and expiry are unchanged. Robot callouts are not repeated in center text.

Live speech and late-join critical captions retain structured speaker/team/text
metadata for feed formatting. Strip ARENA/POWER tags and add sentence punctuation
only for display; original text still selects the authored recording.

## Benchmark preparation

The short arena stress benchmark exercises real combat while warming GPU weapon
and effect pipelines behind the loading overlay. Mute Master before creating
its menu/match audio; restore its previous mute state only after the prepared
scene has been presented. Measurement clocks and counters start after this
reveal. This silence applies only to automated benchmark preparation, and does
not change live match mixing, priorities, acoustics or normal menu music.

Local kill accolades use five emphatic Retro Robot recordings generated with ElevenLabs eleven_v4. Double Kill, Triple Kill, Mega Kill, Champion and Death Bringer accompany chain kills two through six. They play nonspatially on Announcer only for the credited local player, at -8 dB cue gain with the shared playback boost, source headroom, music ducking, limiter and user volume controls. Higher accolades replace the preceding announcer playback rather than accumulating a queue. Kill confirmations have no separate sound or spoken victim name.

## Match result announcements

Elimination uses the flag announcer's Matilda voice for **Eliminated**. The
announcement is private to the eliminated player. Result speech says **You won
the match** only for the local winning robot or winning team member; a draw
says **Match ended in draw** to every participant. Retained source clips,
provider IDs, text and checksums live in the speech source manifest. The
runtime speech bank contains 185 recordings, including the five kill accolades.

Robot recordings use -8 dB cue gain with the shared playback lift and the user's
Voices slider. All robot dialogue follows the speaker's head, including the
local robot. Its ten reserved spatial voice slots cannot be stolen or occupied
by combat or machinery. A speaker has one current line; new dialogue replaces
that speaker's unfinished line. The local speaker also bypasses the ordinary
simultaneous remote-speech cap. Range, callout frequency and subtitle preferences
still apply; objective announcements retain their separate channel.

Feed entries are ordered by immutable event timestamps in match time, with
stable ties. Caption expiry uses its own clock without changing row order.
New announcements preserve unexpired robot dialogue. Rows keep their existing
bounded lifetimes and final fade; no direction metadata is rendered.
