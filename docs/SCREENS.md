# KYLR — screen guide

Main-menu and lobby/customisation robot portraits use the same ArenaLighting
reflection panorama, ambient fill, directional key and tone mapping as matches.
Preview stages add real rectangular key, fill and rim lights so the robot remains
readable with ray tracing and disabled reflection maps; authored ambient fill is retained.
The main-menu pedestal uses the same regolith albedo, normal, ORM and world-scale
triplanar material as lunar surfaces in the arenas.
The main-menu pedestal turns slowly with the robot parented to its turntable;
the robot does not rotate independently of the surface. Anchor the pedestal's
regolith coordinates locally so the grain turns with it. Camera and studio
lights stay fixed. Reduced motion stops the turntable.
Menu and lobby previews alternate common idle with the selected victory animation; use the first available catalog victory when no valid selection exists. Do not cycle weapon holding animations. Customise emote selections play immediately, return to idle, then join this alternating loop.
Preview environments keep the dark menu background and omit distance fog; the
background does not replace the reflection sky. All views consume the same
classified authored materials and retain their chosen primary/secondary colours.
Head and emote choices use compact Blender-rendered portraits in the selected primary finish; armor tiles crop the chest, waist and upper arms.
During matches, when supported ray tracing and fixture illumination are both active, world views
disable raster sky reflections and the artificial chrome reflection panorama.
Ray-traced rays retain the visible authored sky and real scene reflections.
Turning off either option restores the authored reflection settings, including
Custom quality; unavailable RT leaves the raster recipe intact.

This document defines the screen flow, **Online Multiplayer lobby**, **Customise screen**, **in-match HUD**, and **Settings screen** for KYLR, including remembered selections and the FPV/TPV presentation. [DESIGN_LANGUAGE.md](DESIGN_LANGUAGE.md) is the shared visual and interaction theme for all these surfaces. [GAMEPLAY.md](GAMEPLAY.md) defines the game modes and player experience, [RULES.md](RULES.md) defines match rules, and [ONLINE.md](ONLINE.md) defines login, matchmaking, and server admission. Here, **Online Multiplayer** is a game mode; **DM**, **TDM**, and **CTF** are match types. A **robot** is the player's character. A **bot** is an AI-controlled robot in Instant Action.

## Screen route

```text
Main Menu
  ├─ Instant Action → local display-name prompt if absent → remembered map, match type, and options → match
  ├─ Online Multiplayer → Login if unauthenticated → Online Lobby with remembered match card
  │    └─ Create Account (from Login) → Login or Online Lobby after successful authentication
  │    └─ Customise → preview head, victory emote, and armor colors → save → Online Lobby
  │    └─ Play → Finding Match → Starting Server if needed → Connecting → online match
  │    └─ Return to Lobby from post-match results → Online Lobby
  └─ Settings → return to the screen that opened Settings
```

Account creation cannot complete without a valid, unique display name, even if that field was initially left empty. Login uses username and password and stores the returned JWT for protected API calls. The lobby is available only with a valid online session. On successful registration, create the authenticated session and open the lobby directly; on failure, keep form values except passwords and show the field error.

### Remembered choices at startup

Keep local convenience preferences distinct from account data and authoritative match state:

| Choice | Restore behavior |
|---|---|
| **Last game mode** | Focus/highlight the last chosen **Instant Action** or **Online Multiplayer** entry on the Main Menu at startup. The player still chooses to enter it. |
| **Instant Action setup** | Preselect the last map, DM/TDM/CTF match type, bot difficulty, robot count, goal score, and time limit. Keep this match type independent of the online card. An existing local display name remains saved. |
| **Online lobby** | Reopen with the last selected DM/TDM/CTF card. Continue to require a valid online session and an explicit Play press; the server still chooses map, goal, time, and roster. |
| **View and Settings** | Restore the most recently used **FPV/TPV** view for either mode and the saved controls, audio, graphics, and HUD preferences. FPV is the first-run view. |
| **Online robot appearance** | Load the saved account head, emote, and armor colors from the backend after authentication; local preview data is not the source of truth. |

Save changes when the player makes a valid choice or applies Settings, and load them before showing the relevant screen. If a saved map or option is no longer available, use a valid current default and explain the reset when its setup opens; do not silently start a different match. A corrupt/out-of-range saved value must not block startup. Remembering an online card, game mode, or login session never starts matchmaking automatically. JWT/session restoration follows [ONLINE.md](ONLINE.md); an expired or invalid session returns to Login without erasing the remembered online card. Keep gameplay preferences in a versioned local settings file and online credentials in the operating-system protected store described there.

## Online Multiplayer lobby composition

The layout is for a landscape display and scales with the viewport. Preserve the reading order and control anchors rather than relying on fixed screenshot coordinates.

| Area | Content and behavior |
|---|---|
| Top edge | KYLR identity; clear **Online Multiplayer** label; compact **Main Menu**, **Customise**, **Settings**, and account/profile access. Show the authenticated display name in the account area. Keep this bar subordinate to the match choice and Play action. |
| Left column | Three vertically arranged **DM**, **TDM**, and **CTF** cards. Each has its full match-type name, a short objective, and an explicit selected state. Selection changes only the requested match type. |
| Center stage | One large full-body Tensor robot preview, readable against the background. Keep an unhurried turntable presentation and alternate common idle with the selected victory animation (the default catalog victory when none is selected). Show the authenticated display name close to the robot. Use a grounded display platform or stage treatment if suitable assets exist. |
| Right/lower-right action area | Compact selected-match summary, then the largest interactive control: **Play** at the **bottom right**. Include concise fixed online-rule context if useful: server-selected map, 30-minute limit, and goal score of 2 × current roster. Do not present these as editable fields. |
| Background and peripheral space | Show KYLR's floating arena pieces and thruster mood without obscuring the robot or text. Keep decorative motion gentle. Leave room for status/error messaging near the Play area, without inventing shop, party, or progression panels. |

### Match cards

| Card | Short lobby description | Selection effect |
|---|---|---|
| **DM — Deathmatch** | Every robot competes individually; most kills wins. | Request a DM server. |
| **TDM — Team Deathmatch** | Two balanced teams; most team kills wins. | Request a TDM server. |
| **CTF — Capture the Flag** | Two balanced teams; capture the opposing flag. | Request a CTF server. |

Only one card can be selected. Selected state must be clear through more than color alone, such as a border, marker, or label. **DM is selected on the first visit**; later visits restore the last selected card. Changing a card updates the summary immediately and does not call matchmaking. The player's head comes from saved Customise choices; team colors, roster, and map are assigned by the match server rather than chosen on this screen.

### Primary interaction and states

| State | What the player sees | Allowed action |
|---|---|---|
| **Ready** | Selected card and **Play**. No map or match-option editor. | Select a match type, open Settings/account, return to Main Menu, or press Play. |
| **Finding Match** | Play area changes to a clear progress/status message. | Prevent duplicate Play requests. Offer **Cancel** while the request can still be withdrawn. |
| **Starting Server** | Explain that a server is being prepared when the matchmaker could not find a suitable open slot. | Keep progress visible; Cancel behavior follows the matchmaking service's cancellation contract. |
| **Connecting** | Server details and ticket have been received; client is joining. | Keep a connection status until admission succeeds or fails. |
| **Joined** | Transition to the server's Waiting/Countdown/Active flow. | Use the server-returned player info for names and match UI. |
| **Recoverable failure** | Specific short message for expired login, unavailable server, ticket rejection, or connection failure. | Return to the Ready lobby with retry, or to Login when reauthentication is needed. Do not show a successful join until the server admits the player. |

The matchmaker receives the selected **match type** and stored **JWT** when Play is pressed. It chooses a ready server with a free reserved slot or starts a game-server container, then returns connection details and a unique player-specific join ticket. The client presents the ticket to that server. The client never chooses a map or treats the ticket as proof of admission by itself. [ONLINE.md](ONLINE.md) defines reservation, ticket expiry, cancellation, and recoverable Retry behavior.

## Supporting screens and transitions

- **Login:** Username and password fields, Login action, and **Create Account** path. Keep account errors near the relevant form. A successful login enters the Online Multiplayer lobby with the backend's account display name.
- **Create Account:** Username, password, password confirmation, and display-name fields. Display name accepts **1–20 ASCII letters, digits, dots, or underscores** (`[A-Za-z0-9._]{1,20}`). The field may start blank, but submission stops and asks for it if still blank. Show an actionable error if the backend reports the name is already taken. Never create an account with an empty display name.
- **Instant Action setup:** This is a separate flow. It asks for a local display name only if absent, then preselects the remembered map, DM/TDM/CTF type, bot difficulty, participant count, goal, and time choices defined in [GAMEPLAY.md](GAMEPLAY.md). These controls do not appear in the Online Multiplayer lobby.
- **Online results:** Show the authoritative scoreboard and **Return to Lobby** during the 15-second next-map countdown. Returning lands on the same three-card Online Multiplayer lobby. If the countdown completes, the server starts a new match on its randomly chosen map.
- **Customise:** Accessible from the authenticated Online Multiplayer lobby. It edits the account's robot appearance and victory emote, then returns to the lobby. Its detailed screen contract appears below.
- **Settings:** Accessible from Main Menu, Online Multiplayer lobby, and the in-match pause overlay for local controls, audio, graphics, and HUD presentation. Settings do not change online match rules. An online match keeps running while Settings is open.

## Presentation and accessibility

- The robot is the focal point, followed by the selected match card and Play. Keep visual alerts and optional status panels smaller than these three elements.
- Text, selection, focus, disabled, loading, and error states must remain readable against animated backgrounds. Do not communicate selection or failures through color alone.
- Support mouse/keyboard and controller focus navigation among cards, Play, top-bar actions, and dialogs. The exact bindings and controller glyphs follow the controls/settings system.
- Make room for display names up to **20 characters** without hiding primary controls. Scale or truncate only the visual label when necessary; preserve the full name in player info.
- The robot preview reflects available character assets. Missing preview animations or cosmetics must not block login, matchmaking, or Play; use an available idle pose while the asset library is in progress.

## In-match HUD layout

Keep all persistent UI inside the display's safe area. The center of the screen and the travel path immediately around it remain mostly unobstructed. At a glance, the player should locate the objective at the top, survival resources at bottom right, weapon slots at bottom left, and recent events at the edge. Use open rails and sparse translucent backings rather than a block behind every readout. The score header and weapon tray use 10%-opaque black backings and black-outlined text, with no decorative corner strokes on the score. Short score flashes, easing resource bars, and brief feed entries give the display life. The same anchors apply in Instant Action and Online Multiplayer.

| Anchor | Required content | Display rule |
|---|---|---|
| **Top center** | Match type, current score, goal score, and remaining active-match time. | Align match type, timer, and goal over three consistent columns; align the team labels and values beneath them. Use a thin stopwatch mark. In DM, show the controlled robot's kills against the goal. In TDM, show the two team kill totals. In CTF, show the two capture totals. Team modes show both team names/colors and an identifying emblem or label so color alone is unnecessary. Online goal updates when roster changes. |
| **Inside the lower score header, CTF only** | Status of both flags: **Home**, **Carried** by a named robot, or **Dropped**. | Center each flag state below its owning team's score so it reads as part of the capture display. Distinguish carrier from ownership; any directional/world marker must follow the visibility rules chosen for CTF. No flag row in DM or TDM. |
| **Upper left / left side** | Live **Top Killers** leaderboard with up to five individual robots. | Rank robots by kills only in every match type, including CTF. Show fewer than five rows if fewer robots exist. Identify the local robot and team where relevant. Captures, assists, deaths, and team score never change this ranking. |
| **Upper right** | Compact **kill and match-event feed**. | Use natural sentences such as **ABC** killed **XYZ** with **Minigun**. Bold both names and the weapon; color player names by assigned team in TDM/CTF. Show falls and flag plays in plain language. Online join/leave and results may appear here when authoritative. Accepted robot callouts share this feed as **ABC** said: Cover me, with bold speaker names colored by team in TDM/CTF and neutral in DM. Retain listener filtering, callout limits and subtitle preference; announcer speech joins the same feed as **Announcement:** Cover banks reconfigured. The announcement prefix stays neutral. Do not duplicate speech in center subtitles. Routine pickups, assembly, and system narration stay out of this feed. |
| **Center and screen edge** | Small aim reticle and brief contextual feedback. | Reticle reflects aim; do not imply random spread because weapons have none. Show a hit confirmation only for a confirmed hit, and an elimination confirmation only after credited elimination. Show opponent diamonds and aimed-at names only when their robot is within 15 m of the active camera. A short danger-colored bar at the screen edge shows the bearing of a damaging attacker and tracks the current camera turn for 1.3 seconds. Merge nearby successive hits, limit simultaneous marks, and clear them on death; keep the aim point unobstructed. |
| **Bottom left, 0–40%** | All owned weapon slots, active highlight and ammo. | Right-align the tray within this region. Use up to five columns and two rows, at most ten total weapons. Each slot is at most 15% of screen width and shrinks proportionally as the tray grows; right-align a partial second row. Keep the pistol visible with ∞, and show each acquired gun's loaded ammo and spare count. Slots follow acquisition order and display keys 1–9,0. |
| **Bottom middle, 45–70%** | Actual first-person weapon aimed at the reticle. | Leave a 5% spacer on either side. Pin the model center at 57.5% of screen width. The larger view model can extend into the spacers (42–73% width), with its camera-relative center pulled back to 0.8 m. Crop its lower portion and preserve animated firing/reload machinery. TPV uses the held world weapon. |
| **Bottom right, 75–100%** | Shield, armor and energy bars. | Keep labels and numbers readable inside this quarter. AH and EP are out of 100; reveal SH and its duration only while active. Ease changes and lost-value trails; mark the 50 EP threshold. |

The HUD's score, roster, flag state, hits, and event feed come from the match controller or game server. The client displays those values; it must not compute a second scoring or flag truth from animations or local guesses. Source rules and exact values remain in [RULES.md](RULES.md) and [GAMEPLAY.md](GAMEPLAY.md).

### FPV and TPV presentation

- Provide an in-match **Switch Camera** input in both game modes and a binding row in Settings → Controls. A short `FPV` or `TPV` confirmation may appear near the lower edge after switching; the screen must never confuse it with a new match type or spectator mode.
- Preserve the same persistent HUD anchors, reticle, resource values, score, feed, and weapon-slot silhouettes in both views. In TPV, leave room around the visible robot and weapon without covering the reticle or weapon tray. In FPV, pin the equipped weapon inside the middle 25% region, place its center at 57.5% of screen width, crop its lower portion below the screen, and keep the reticle and ammo HUD clear. The weapon and attached ammo cast no world shadows.
- TPV is a behind/over-shoulder view of the **same controlled robot**, with the account's effective head/armor appearance visible online. Camera collision and aim presentation must avoid clipping through arena geometry or suggesting unobstructed fire through a wall. The authoritative firing and damage rules are identical in FPV and TPV.
- A view switch is permitted during normal play in either game mode. Death animation, spawn invulnerability, and repair use temporary **third-person cinematic cameras** that frame the full local robot. The opening uses a five-second movement-locked front-left spawn view; results retain their authored camera. During an active-play respawn cinematic the player may walk and steer, so the camera must follow without taking away directional control or hiding nearby fall edges. View switching is disabled during all temporary cinematics and does not change the saved preference. Restore the last chosen FPV or TPV view when spawn protection ends or the robot exits repair; the initial opening restores it immediately when its five-second countdown ends. TPV starts 2 m behind the right shoulder, shortens against walls, and blends in 0.2 seconds on normal view switches.

### Resource behavior and feedback

- **SH:** When a Shield Core is collected, reveal the SH row and its duration countdown. Hide the entire row immediately when the shield expires or reaches zero. The same weapon hit can reduce both SH and AH under the 80/20 rule, so animate both changed rows. Do not show unabsorbed shield damage spilling into AH.
- **AH:** Show 100/100 on a fresh life. On damage, indicate the amount lost and briefly signal the incoming direction without masking the reticle. A zero value precedes the death presentation and then resets on respawn.
- **Repair station:** At **50 AH or less**, mark a nearby ready station as available without promising protection on approach or during its first second of activation. Once the robot stops in the bay, switch to a third-person cinematic that keeps the entire robot, barrier, and welding arms visible, and show the seven-second sequence as **Shield Activating 1 s → Repairing 5 s → Shield Deactivating 1 s**, with disabled combat controls. Show the station-barrier indicator, distinct from SH, only when protection is actually active. EP drain pauses throughout; update AH and EP to full after the five-second welding phase, at six seconds. Prompt **Exit station**, restore movement and the saved FPV/TPV view only after deactivation ends at seven seconds. Show **Recharging** rather than an active-looking repair prompt during its subsequent 60-second timer.
- **EP:** Show 100/100 on a fresh life and update the bar continuously as the 1 EP/s drain progresses. At **50 EP or less**, change the EP row's emphasis and show that sprint and charged jump are unavailable; normal movement remains available. At zero, transition to death. A map Energy Core refills the row to 100; a dropped Energy Core increases it by its stored amount up to 100. A hit never drains EP.
- Use precise enough numeric display that a value near the **50 EP** action threshold or **zero** does not appear to contradict the actual allowed actions. Brief pickup text can distinguish a full map-Core refill from a partial dropped-Core transfer.
- Brief feedback for blocked sprint or charged jump, failed pickup, and a weapon with no ammo should explain the immediate reason without repeatedly spamming the center of the screen.

### Weapon and combat feedback

- Keep the pistol's fixed slot visible even when a picked-up weapon is equipped. Use consistent, side-on silhouettes that distinguish pistol, rifle, flamethrower, EMP gun, lightning gun, minigun, and rocket launcher at small HUD size; pair each with its weapon name or accessible label so silhouette alone is not the only identifier. Keep the slot number at the left and right-align the weapon name against the same right inset used by the spare-pack caption. Highlight the active slot, including when a pickup automatically switches from pistol to the new weapon. A same-weapon pickup leaves the slot unchanged. If final silhouette art is not yet in the asset library, use simple temporary outlines without changing the slot layout.
- Show **loaded ammo** and **spare packs** separately for every acquired weapon. Reflect pickups only after they succeed; a rejected full-pack pickup must not change the display. For continuous lightning-beam and flamethrower fire, decrement ammunition according to their two-ammo-per-second cost, not a fictional per-frame bullet count.
- During automatic reload, show progress for the full **2 seconds** and a clear disabled-fire state for both slots. If there is no spare pack, display an empty/no-reload state rather than a reload animation that cannot finish.
- Accepted damage from every weapon shows four outlined cyan diagonal marks, 8–16 px from the reticle center, for 0.24 seconds. Projectile, splash, EMP, lightning, and flame hits use the same authoritative confirmation path as bullets; blocked, friendly, protected, self, or zero-damage contacts do not confirm. Incoming enemy damage adds a brief soft red tint at the screen edges and a direction arc 54 px from the sightline, alongside the 1.3-second edge bearing. Reduced motion halves the tint intensity. No damage number or separate confirmation sound is required. An unconfirmed client prediction must not appear as a confirmed hit online. Recoil feedback follows the weapon profile and does not introduce random bullet spread.
- While the reticle points at a currently damageable robot, show that robot's name above its head, above any team marker. Remove the name as soon as the shot no longer qualifies, the robot is concealed, or the local player cannot act.
- Reticles are drawn in code from the weapon catalog: pistol and normal rifle use four cardinal bars; flamethrower uses corner brackets; minigun uses four diagonal strokes; scoped rifle uses a circle, cardinal ticks and center dot; EMP uses four separated arcs and a dot; lightning uses a chamfered diamond, cardinal ticks and dot; rocket uses four outward chevrons. White strokes have a subtle dark outline for contrast. Rifle and rocket launcher supply separate `scope_crosshair` profiles. Flak uses a segmented ring with inward diagonal strokes, bio rifle uses three arcs and a dot, and grenade launcher uses an upper arc with lower range ticks. Lightning and flame orb secondaries use a small ring with side ticks. Rocket scope shows an amber acquisition arc and SEEK/ACQUIRING text, turning green and reading LOCKED only when the authoritative lock is complete.
- When the current attack can reach a damageable robot, ease the reticle inward to 70% of its normal radius, and release smoothly when that condition ends. Use muzzle obstruction, attack range, teams, spawn protection, death and repair immunity; a normal shield still permits AH damage. Projectile reticles use their physical collision volumes; lightning and flame use their visible beam widths. Reloading, unavailable ammunition and inability to act keep the normal form. This is current target eligibility, not projectile prediction or confirmation of a future hit. Only authoritative hit feedback displays the separate brief cyan center marks. The center stays fixed during contraction and no aim assistance or weapon spread is introduced. Keep numeric floating damage **off by default**; an optional local setting may turn it on using authoritative hit results, without revealing a target behind cover.

### Match-type and event variants

| Situation | HUD response |
|---|---|
| **DM** | Top center shows the controlled robot's kill score, kill goal, and time remaining. The left leaderboard reveals the other leading robots. No team colors or flag row. |
| **TDM** | Top center shows both team kill totals, goal, and time. Use the two server-selected team colors with text/emblems; clearly mark the player's own team. The left list still ranks individual kills. |
| **CTF** | Top center shows capture totals, goal, and time; the flag row shows both flags' authoritative states. Flag pickup, carrier death/disconnect, drop, return, and capture trigger concise notifications and update any eligible world markers. Kills remain on the left leaderboard but do not increase capture score. |
| **Opponent markers** | In TDM and CTF, show a small diamond over each visible, active opponent in that opponent's assigned team color. Conceal it through map cover, during spawn reveal, and after death; show none in DM. The diamond shape keeps the cue identifiable without relying on color alone. |
| **Respawn invulnerability** | For a respawn during active play, use a third-person spawn cinematic that follows the robot while walking remains under player control. Show a visible **5-second** countdown and **Invulnerable — walk only** status. Blocked fire/pickup/portal actions do not create misleading success feedback. At expiry, remove the indicator and restore the saved FPV/TPV view at the robot's current position. |
| **Repair station** | Use a third-person cinematic and replace weapon-action prompts with phase and time remaining: **Shield Activating 1 s**, **Repairing 5 s**, then **Shield Deactivating 1 s**. Show the barrier separately from personal SH only once active. Keep match score/time visible. Update AH/EP to 100/100 at the end of welding, then remove the barrier cue and restore movement and the saved FPV/TPV view at the end of deactivation so the robot can walk out. |
| **Death and respawn** | Give immediate death-cause feedback and switch to a third-person camera on the local robot. Play its death animation, hold the final pose for one second, then respawn with restored AH/EP, pistol, cleared weapon and ammo inventory, and a fresh five-second third-person spawn cinematic with invulnerability countdown. A void fall keeps the falling body in the void with no drop; its camera descends only to 25 m below the arena surface and keeps looking at it. Lethal lunar impact uses a grounded death and frames the body resting on the contacted surface, without a pickup drop. An ordinary corpse's separate lifetime and possible dropped Energy Core are world events. |
| **Spawn countdown / results** | During the five-second opening countdown, prioritize the camera and clear phase label; do not show active timer or suggest combat controls are live. At finish or cancellation, replace the combat HUD with the full authoritative results screen and its applicable Main Menu/Lobby action. |

### Feed and objective presentation

- Use names from the local roster in Instant Action and from **server-returned player info** in Online Multiplayer. Never let client-supplied text replace an authoritative online display name in the feed or scoreboard.
- A feed event should identify **what happened** and **to whom** even when no killer exists. An EP-depletion death is a death without a weapon credit. A fall-off-map event names the victim and the fall cause. A disconnect is shown as leaving, with any carried flag drop reflected in the CTF status.
- Keep routine feed entries short and visible for **5 seconds**, with at most **four rows**. A burst of joins, deaths, and pickups must not cover the top-center score or center reticle. Reserve a more prominent but brief announcement for capture, match win, draw, or cancellation; a new critical event replaces an old routine row before being dropped.
- In CTF, always show own base and own-flag state to the team. Show an enemy flag carrier's world marker only while visible to a teammate; otherwise show its last known area briefly without updating its exact hidden position. Dropped flags show a marker to their owning and former carrier teams. Markers can clamp to the screen edge with direction and distance but never reveal a concealed current position. Their team, state, and relation to the top flag row must agree.

### Layout, readability, and settings

- Maintain anchors and hierarchy at common landscape aspect ratios, including ultrawide, while keeping text inside safe margins and out of the first-person weapon silhouette. Scale elements as needed; do not shrink numbers until they become unreadable.
- Pair every resource or team color with a text label, icon, shape, or numeric value. Shield, armor, and EP should not be confused by color alone. Support the 20-character display-name limit without allowing names to displace scores or timers.
- Effects such as low EP pulse, damage vignette, sprint edge blur, and speed lines may coexist. The HUD must remain legible through them. Graphics settings may reduce decorative effects without hiding essential status.
- Support HUD/text scale from **80% to 140%**, high-contrast plates, color-plus-pattern team markers, subtitles with speaker labels, and reduced decorative motion. Expose screen-reader labels for menu controls through the platform accessibility layer where available; critical match state must also be represented by readable text and icons. Keep HUD data separate from presentation so assistive output receives the same authoritative state.
- Do not add a minimap in the first release. Use map silhouettes, signs, world markers for known objectives, and callouts to orient the player without revealing hidden CTF carriers.

## Settings screen composition

Use the shared **arena control system** theme in [DESIGN_LANGUAGE.md](DESIGN_LANGUAGE.md): dark cut-corner plates, thin functional seams, restrained energy accents, and clear type. Team colors identify teams; a neutral focus treatment identifies controls. Dim the screen that opened Settings so its context remains recognizable without reducing contrast. Keep decorative movement quiet while adjusting sliders. Use the same layout whether Settings opens from Main Menu or the Online Multiplayer lobby.

| Region | Content and interaction |
|---|---|
| **Header** | Title **Settings**, then labelled tabs: **Controls**, **Audio**, **Graphics**, and **HUD & Accessibility**. Show the active tab with text, shape, and focus treatment, not color alone. |
| **Main list, left/center** | A scrollable list of labelled setting rows. Group related rows under short headings such as Mouse & Aim, Bindings, Display, Quality, and HUD. Put the current or pending value in a consistent right-hand column. Sliders show a numeric value; toggles show On/Off; choices show their selected label. |
| **Help pane, right** | Explain the focused setting in plain language, including any trade-off or dependency. A short visual preview may illustrate brightness, HUD scale, sprint blur, or speed lines when the relevant asset is available. It must never cover the list. |
| **Footer** | Fixed **Back**, **Restore Defaults**, and **Apply** controls plus a clear **Unsaved changes** indicator when appropriate. Keep these available while the list scrolls. Back returns to the exact screen that opened Settings. |

At narrow landscape widths, let the help pane collapse below the focused setting or open on demand; keep the setting name, value, and footer visible. The screen must work with mouse and keyboard navigation, and controller focus if controller input is supported. Use descriptive text labels beside icons. Avoid imitating either game's branding or adding shop, account statistics, or social settings without a KYLR feature behind them.

### Tabs and setting groups

| Tab | Groups and controls | Boundary |
|---|---|---|
| **Controls** | **Mouse & Aim:** look sensitivity and optional invert vertical look. **Camera:** FPV/TPV switch binding and current view. **Bindings:** movement directions; immediate normal jump (Space by default); charged jump (hold and release Q by default); Sprint modifier (hold Ctrl by default); Walk modifier (hold Shift by default); Crouch (hold C by default); primary fire; secondary fire; pistol and second-slot selection, 3–9/0 for subsequent slots, and wheel weapon cycling; interaction. If controller play is supported, show its look and binding subsection in the same tab. | Rebinding changes local input only. Changing view changes presentation, not weapon or match rules. Default movement runs at 2× the 3 m/s walk speed (6 m/s). Hold Sprint to move at 4× walk speed (12 m/s) above 50 EP; hold Walk to move at 3 m/s; hold Crouch to move at 2.5 m/s. Migrate a saved legacy sprint-modifier key to Walk; Controls Defaults restores Ctrl, Shift, Q, and C. |
| **Audio** | Master, music, effects, interface, announcer, and robot-voice volume sliders with visible numeric values; callout frequency (Full/Reduced/Off); subtitles (On/Off); and a reduced-dynamic-range mix option. A short preview/test cue can help the player hear the selected channel. | [AUDIO.md](AUDIO.md) defines the cue and callout hierarchy. Voice chat is outside the current feature set. Muting audio never changes gameplay or server events; critical cues still have visual alternatives. |
| **Graphics** | **Display:** display mode and resolution. **Quality:** a visual-quality choice/preset with supported detail options. **Motion effects:** sprint edge blur and speed lines, with clear intensity or On/Off controls. Camera FOV defaults to 60° and remains adjustable in the local settings. | These are local rendering preferences. They must not change map geometry, visibility rules, collision, match gravity, or server-selected map. Available values depend on the display and supported renderer. |
| **HUD & Accessibility** | HUD scale; interface contrast/readability; reduced decorative motion; and clear visual alternatives for team/resource colors. Keep SH/AH/EP numbers, team labels, timer, and objective state visible when visuals are reduced. | These settings change presentation, never score, player identity, weapon behavior, or the information the server permits the client to know. Exact controls and supported accessibility features need separate definition before implementation. |

The first three tabs implement the already specified Settings categories in [GAMEPLAY.md](GAMEPLAY.md). **HUD & Accessibility** gives presentation preferences a dedicated home for HUD/text scale, high contrast, color-plus-pattern team markers, subtitles, and reduced motion. If a feature is not implemented, omit its row rather than showing a working-looking control that does nothing.

### Row, binding, and dependency behavior

- A focused row has a clear outline and updates the help pane. Hover and focus are distinct from a committed value. Show pending values immediately in the row; label whether a change is only a preview until Apply.
- For key rebinding, selecting a binding enters a **Waiting for input** state. Show the current action and a Cancel route. Detect conflicts with an existing action and present a clear replace/cancel choice instead of silently losing a binding. Always leave a way to navigate back and restore usable controls.
- Use sliders for continuous values, toggles for binary values, and selectors for a short list of named choices. Support direct mouse manipulation and keyboard/focus steps; do not rely on arrow graphics alone.
- Grey out a dependent row only when another selected option makes it unavailable, and explain the dependency in the help pane. For example, resolution choices may depend on display mode or the connected display. Unimplemented options are omitted.
- A setting that impacts immediate visibility or performance should preview safely. Display mode and resolution changes require a **15-second** confirm/revert countdown; if the player does not confirm, revert automatically.

### Apply, defaults, and navigation

1. Opening Settings loads the player's saved **local preferences**. Selecting another tab retains pending changes; the footer clearly indicates when anything differs from saved values.
2. **Apply** commits valid pending changes and saves them for later sessions. Controls, audio, graphics, and HUD changes use the same predictable commit model. Temporary previews are reverted if not applied.
3. **Back** with no pending changes returns to the opening screen. With pending changes, offer **Apply**, **Discard**, or **Stay**; do not silently lose edits. A failed save leaves the values visibly pending and shows an actionable error.
4. **Restore Defaults** resets the **current tab's** pending values and marks them unsaved; it does not immediately overwrite the saved preferences. Apply commits the restored defaults. Baselines are FPV, 100% HUD/text scale, subtitles On, normal contrast, motion effects On, and 100% master/music/effects/interface/voice volumes. Choose display resolution from the current monitor and quality from a startup benchmark; never assume a resolution unsupported by that device.
5. Settings opened from the Online Multiplayer lobby returns there with the previously selected match card intact. Entering or leaving Settings does not request a server. Settings opened from Main Menu returns to Main Menu. Settings may also open from the in-match pause overlay: in Instant Action, pause freezes the local simulation; online, the match continues while the local robot remains vulnerable, with a persistent **Match still running** notice and live critical captions. Back restores the current FPV/TPV view.

### Readability and implementation boundaries

- Group controls by what the player is trying to change, not by engine subsystem. Show short descriptions that state the visible effect; avoid raw technical names when a familiar label will do.
- Preserve readable labels and controls at common landscape resolutions and ultrawide aspect ratios. Scroll the settings list, not the footer or category tabs. The help pane may collapse responsively.
- Pair color with text, icons, or shape. Keyboard focus, selected tab, disabled state, pending change, and validation error must each remain distinguishable without color alone.
- Apply graphics-effect preferences consistently in lobby, HUD, and match views as relevant. Reducing sprint blur/speed lines must never hide the HUD's low-EP cue, invulnerability timer, or other gameplay-critical information.
- Persist these settings locally for both game modes. Online login identity, matchmaking, map choice, roster size, bot difficulty, score limits, and match time are not Settings rows.

## Online Customise screen

Enter from a **Customise** action in the Online Multiplayer lobby's action footer. The screen uses the shared arena-control visual system in [DESIGN_LANGUAGE.md](DESIGN_LANGUAGE.md) and returns to the same lobby, preserving its selected DM/TDM/CTF card. Customisation is available only for an authenticated online account and does not call matchmaking.

| Region | Content and behavior |
|---|---|
| **Top bar** | **Customise** title and authenticated display name. Use the same identity treatment as the lobby. |
| **Category tabs** | Three labelled choices: **Head**, **Armor Colors**, and **Victory Emote**. Keep the active category and pending-edit state visible without relying on color alone. |
| **Choice pane** | For Heads, show five named, square Blender-rendered front-left close-ups in the selected primary color, with persistent selection/equipped states. Emotes use full-body posed portraits in the same primary color. Armor Colors has Primary/Secondary channel tabs and named torso portrait tiles: each tile shows its proposed finish together with the other currently selected channel. Crop closely to the chest, waist and upper arms; omit the head and legs. Keep selection text separate from the tile name. Do not require search/filter UI for this small head catalog. |
| **Character stage** | One large, full-body Tensor model on a simple turntable stage. Drag or use controls to rotate it; provide a reset-to-front view. Head changes swap the preview mesh; color changes affect only the primary and secondary armor material slots; emote selection plays that emote once, then returns to idle. Keep the whole robot visible with an optional closer head view while browsing heads. |
| **Fixed footer** | **Save**, **Revert**, and **Back**. Show Unsaved changes when preview differs from the saved account loadout. Save commits the full loadout; Revert restores the last saved preview; Back with edits offers Save, Discard, or Stay. |

### Choices and visual feedback

- **Heads:** Use silhouette art derived from each actual head's recognizable shape, not an unrelated portrait. The selected tile shows its name, a persistent equipped marker, and a separate preview/focus marker. Show the five currently exported head meshes (`projector`, `sentinel`, `porthole`, `raptor`, `arachne`). Add the planned sixth choice only after its mesh and thumbnail exist; do not show an equip-ready placeholder.
- **Victory emote:** Show each authored available emote as a high-contrast robot-pose silhouette. Selecting a tile previews the animation once on Tensor, then returns to idle; a Replay action repeats it. Show one equipped victory emote. On results, a winner or MVP may play its saved emote after the result is locked; never play an emote in combat. Do not show invented or unavailable emotes.
- **Armor colors:** Provide independently labelled **Primary** and **Secondary** swatch controls. The first-release palette contains graphite, silver, white, yellow, orange, red, magenta, violet, blue, cyan, teal, and green; the client sends stable palette IDs, not arbitrary colors. Apply the preview to the asset's `M_Primary` and `M_Secondary` armor slots, leaving matte-black frames, metal fittings, emissive parts, weapon materials, and team HUD labels unaffected. A small neutral-lighting preview helps judge both colors; avoid highly colored stage lighting that misrepresents the result. In online **DM**, both saved colors appear. In online **TDM/CTF**, the server-assigned team color drives primary armor and its library-authored contrasting accent drives secondary armor for that match; neither saved custom color appears on the robot. Explain this beside the controls.
- Keep camera motion and shader updates smooth but short. The robot remains readable while a head or color is changing; avoid full-screen flashes and unnecessary flyarounds. The stage lighting and background match the lobby's world and the design tokens in [DESIGN_LANGUAGE.md](DESIGN_LANGUAGE.md).
- Use **previewed**, **saved/equipped**, **unavailable**, and **saving/error** as distinct states. An unavailable or unfinished head/emote can be described but cannot be saved. Never show store pricing, purchase prompts, or fake lock icons for content that simply has not been authored.

### Save and match handoff

1. On open, load the saved account appearance from the backend and render it on the preview robot. If loading fails, show a recoverable error and do not overwrite saved values with defaults.
2. Local changes preview immediately. **Save** sends head ID, victory-emote ID, primary color, and secondary color through the authenticated API. The backend validates identifiers/colors and persists the accepted loadout against the account. Show a saving state and accept the backend response before declaring success.
3. Return to the Online Multiplayer lobby with the saved head/colors/emote reflected in its rotating robot preview. Revert and unsaved Back leave the persisted account loadout unchanged.
4. At server admission, the game server obtains or validates the account's saved loadout and returns the **effective** player info for the match. The match client uses that server-approved appearance rather than trusting locally edited preview data. In online TDM/CTF, the server keeps the chosen head and emote, permits duplicate heads on one team, and applies the assigned team primary and its library-authored contrasting secondary accent. The saved custom colors return in DM and the Customise preview. Show the effective match appearance accurately once admitted.

Customisation is cosmetic. It never changes hitboxes, AH/SH/EP, movement, weapon damage, team assignment, or matchmaking. The online match name still comes from authoritative player info, not from the Customise screen.

## Asset presentation

- Show the five available heads and the authored victory emotes. A winning robot or MVP may play its saved emote on the results stage after the result is locked; a draw shows no exclusive victory pose.
- Color selection uses the curated 12-swatch first-release palette with neutral-lighting preview. Team primary colors and authored secondary accents override saved colors in TDM/CTF.
- Graphics presets, FOV/sensitivity ranges and reticle art are controlled by the saved preferences and shared UI theme. They do not change server gameplay.

## Resource preparation

A lightweight centered spinner on the canvas background draws before loading
app.tscn. The same overlay covers Instant Action match preparation, return to
menu and graphics-setting changes. It blocks gameplay input while active and
uses a static ring for reduced motion. Models and animation resources remain
cached across matches; graphical resource I/O is threaded and scene assembly
cooperates with the main loop. Selected-map resources prefetch while the menu
is open. Headless runs use cooperative synchronous loading.
Instant Action preparation holds both the opening countdown and robot spawn
timers. Spawn fixtures begin only after the hold is released, so their opening
motion and cues cannot be consumed behind the loading overlay.

Ultra waits for the native engine to report a valid RT scene and zero pending
hit-group materials before revealing the scene. On a preparation timeout the
player can explicitly continue with raster lighting; automation fails instead.
Cold shader preparation and individual scene operations can still stall the
spinner; this mechanism covers preparation rather than promising instant loads.
Online scene preparation is owned by the network session.
### Rendering thread preference

Graphics includes a Separate rendering thread toggle. It defaults Off (Safe mode)
in every quality preset, including Ultra, and changing visual quality does not
overwrite an explicit thread choice. The setting is experimental, persists only
on Apply, and takes effect on the next game launch. Show the restart requirement
in the control label/help and the saved status; do not switch rendering servers
during a running match. Graphics Defaults resets it to Off. Discard retains the
previous saved startup mode.

## Ray-tracing graphics controls

DLSS Ray Reconstruction is the sole ray-tracing denoiser; Graphics settings has
no denoiser selector. Keep the Ray tracing and DLSS upscaling toggles, with
upscaling available only while supported ray tracing is selected. Ultra requests ray
tracing and fixture illumination by default, with DLSS upscaling enabled.
High uses raster rendering with fixture illumination and shadow casting enabled
by default. Low and Medium keep fixtures emissive-only. Manual illumination or
shadow edits select Custom; reselecting High restores both lighting settings.
Unsupported hardware or runtime disables the RT controls with an explanation
and uses raster rendering. Turning upscaling off retains native-resolution Ray
Reconstruction. Separate
rendering remains an independent option, off by default in every preset.

### Online presentation and responsive layout

Online screens use anchored margins, a scrollable content region and a fixed action
footer. Back/Revert stay at the left; Play/Save stay at the right. The preview stage
and choices share wide screens; smaller layouts reduce grid columns and stack
regions where needed. Footers remain reachable without scrolling the content.
Only one online preview is visible, with its own World3D, camera, studio lighting
and regolith turntable. Main-menu geometry is hidden while online previews are
shown and retired before joining the match. Returning to the menu resumes its
single preview. Platforms rotate with their robot; dragging rotates the online stage.

A connected player awaiting the minimum roster sees a Server Ready waiting screen,
not a combat HUD over the unassembled map. Joining and map continuation keep the
loading cover until the client world and selected renderer are ready. Portal
fields appear only when both linked gates are usable during active play.

Portrait generators: `library/tools/render_customisation.py`, followed by
`tools/install_customisation_thumbnails.py`. Runtime tiles are 192×192 WebP; the
264-image set covers five heads and five emotes in twelve primary colors, plus
all 144 armor finish combinations. PNG intermediates remain in ignored library build output.

Joining and waiting use the same Match staging layout, shared menu plates and fixed footer actions. Three labeled milestones show server discovery, secure admission and gathering players. Status follows backend and transport events without estimated percentages. Waiting shows the authoritative connected roster and the two-player start threshold; the world remains covered until countdown and renderer preparation finish.

Main-menu and online portrait studios share `MenuStudio`, which owns a separate raster-rendered viewport outside the gameplay scene. Its neutral lighting and authored PBR materials remain stable when gameplay switches ray tracing, DLSS or quality presets. The studio is retired explicitly on shutdown and rendered only on screens that display it.

Boolean settings use full-width switch rows with an explicit On/Off readout beside the switch. The whole row responds to mouse activation and native keyboard/controller input. The plate retains its geometry in every state; hover only raises the surface, focus adds an outline and the switch indicator alone conveys the value. Disabled rows keep a muted readable state and their dependency explanation. Changes remain pending until Apply.

Main Menu and online portraits use the same ambient fill, rectangular key/fill/rim lights, reflection recipe, tone mapping, native-resolution rendering and 4× MSAA. Gameplay quality and ray-tracing choices do not relight menu robots or pedestals. Main Menu uses its full-screen camera composition; online screens frame the robot within their preview column. Pause and results preserve the live match environment rather than adding studio lights.

Instant Action setup shows the selected map’s short overview and description above five player-free native-rendered photographs: a cinematic overview and four route, objective or fixture views. Images include the assembled map loadout, pickups, fixture lighting, shadows and environmental effects. The preview advances every two seconds and resets on map selection; numbered controls select a view directly. Reduced decorative motion stops automatic cycling. Gameplay energy rules remain in the first-life hints rather than repeated in setup. Setup keeps Back and Start Match in a fixed footer and scrolls its two content columns on smaller windows.
