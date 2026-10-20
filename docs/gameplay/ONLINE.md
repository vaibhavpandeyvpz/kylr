# KYLR — Online Multiplayer play flow

Online Multiplayer is the human-only game mode. It offers DM, TDM, CTF, Elimination, and Gun Game under [RULES.md](../RULES.md). The game server owns the map, roster, team assignment, score, and match state. [ONLINE.md](../ONLINE.md) owns Flask/MongoDB/Docker architecture, identity, JWTs, reservations, and join tickets; [SCREENS.md](../SCREENS.md) owns the lobby and results UI.

## From menu to match

1. Open Online Multiplayer. Restore a valid account session if available, otherwise show Login/Create Account. Account creation requires a valid, unique display name before submission.
2. In the lobby, show the account's saved robot and last selected match card. First-time selection defaults to DM. Only DM/TDM/CTF/Elimination/Gun Game cards and Play determine the request; there is **no map choice or adjustable online match option**.
3. Play asks matchmaking for a ready server with a slot, or starts one if necessary. Show Search/Start/Connect/Join progress and a Cancel route. The client connects with a player-specific ticket and receives server-approved name, appearance, team, and match state before control.
4. A new match runs the five-second deployment countdown. A late join receives a current snapshot and spawns with five-second protection. All online matches have a **30-minute** clock and a goal score of **2 × current roster size**, recalculated on joins and leaves.
5. A completed match displays results for **15 seconds**, with Return to Lobby. Staying begins a fresh match on a server-chosen random eligible map and its full cinematic. A canceled match shows the reason and returns remaining players to the lobby without automatic Play.

## Teams, identity, and appearance

The online roster can contain 2–10 robots and may be odd. TDM/CTF use two distinct randomly chosen team colors from yellow, green, blue, red; team sizes differ by at most one. The next join goes to the deficient side. Existing members do not switch team when someone leaves. The authoritative match name comes from server player info and feeds into lobby, scoreboards, and kill feed. The chosen head and victory emote persist through the match; duplicate chosen heads are allowed on a team. Free-for-all types use saved primary/secondary armor colors, while TDM/CTF override the primary with the team color and the secondary with its library-authored contrasting accent. None of these cosmetics alter hitboxes or stats.

## Continuity and fairness

Active matches except Elimination may admit players while a slot is free. A joiner gets the current clock, scores, flag state, pickup timers, moving-map phase, and roster before spawn. Players cannot join a Finished or Canceled match. A disconnect or leave removes that robot immediately, emits a feed event, and drops any carried flag. If DM or Gun Game falls below two robots or a team falls to zero, cancel without winner/MVP. If it remains viable, the next Play request can join an available server; no silent reconnection or slot hold is promised.

The server validates movement, combat, pickups, objective contact, timers, and results. FPV/TPV, input preferences, and UI settings remain local and cannot change what the server considers a hit. The client may predict its own movement and audiovisual shot feedback, then reconcile to the authoritative state. Critical hit, kill, pickup, flag, and score cues wait for server confirmation. The [AUDIO.md](../AUDIO.md) spatial listener remains at the local robot's head in either view.

For a death of **any human player**, the server keeps that victim dead through the death animation and a one-second final-pose hold, then permits respawn unless Elimination lives are exhausted, and starts five-second spawn protection when control returns. The victim's third-person death camera is local presentation; it never slows the server, other clients, match clock, or objectives. Match results interrupt the death view.

Server map selection uses only maps validated for the chosen match type. If at least two are eligible, avoid repeating the immediately previous map on the same server; otherwise use the sole eligible map. Random selection is server seeded and logged so a result can be reproduced during debugging.
# Runtime implementation

Online uses the authenticated API and a dedicated authoritative ENet server. A player can restore a Windows-protected session, register/sign in, choose DM/TDM/CTF/Elimination/Gun Game, cancel matchmaking or connection, retry with a fresh ticket, customise/save/revert their account loadout, and join a human-only match. Match fields and appearance come from the account/ticket response, not client identity input. Local deployment is documented in [the protocol guide](../ONLINE_PROTOCOL.md); public deployment uses [Render, Atlas and Edgegap](../CLOUD_HOSTING.md).

Elimination admits players only during Waiting/Countdown. Eliminated robots spectate until results; other match types admit during Active as well.

Late joins receive complete map/clock/roster/objective/resource/fixture snapshots before control. Disconnects abort repair and drop flags. DM, Gun Game and team modes update the score target and cancel undersized or empty-team matches. Active Elimination keeps its starting goal and ends when one participant remains. Normal results retain the roster and start a new round after 15 seconds. Faceoff and Skyfall are eligible in DM/TDM/CTF/Elimination/Gun Game. The server selects a different compatible map at normal continuation. Countdown and continuation also reject invalid rosters; canceled results return to the lobby after three seconds with their reason.
