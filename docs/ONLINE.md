# KYLR — online services and identity

This document is the shared contract for accounts, matchmaking, server admission, and container deployment. [GAMEPLAY.md](GAMEPLAY.md) defines the player experience and [RULES.md](RULES.md) defines match flow, scoring, and roster limits. **Online Multiplayer** is a game mode; **DM**, **TDM**, **CTF**, **Elimination**, and **Gun Game** are match types. A human-controlled match character is a **robot**, not a bot.

## Runtime components

| Component | Responsibility |
|---|---|
| Godot client | Shows login, account creation, lobby, and match UI; stores the returned JWT for authenticated API calls; requests a match; presents its join ticket to the assigned game server. |
| Python/Flask backend API and matchmaker | Creates and authenticates accounts, issues JWTs, returns account/player data, selects or starts a suitable match server, reserves a place, and issues a player-specific join ticket. |
| MongoDB | Persists accounts and the data the API needs for identity and matchmaking. The API, not the game client, accesses the database. |
| Game server | Runs an authoritative online match of a selected type, admits only valid ticket holders, maintains the roster and match rules, and returns authoritative player info to clients. |

Package the **game server** and **Python/Flask API** as separate Docker images. Public hosting uses Render for the API, MongoDB Atlas for account data and Edgegap for UDP game servers; [cloud hosting](CLOUD_HOSTING.md) owns setup and capacity limits. Local development supports Dockerized or native MongoDB. Provide API/database, authenticated API/game-server control and client/game-server connectivity. Do not embed database credentials, password material or signing secrets in the client.

Match-type IDs are `DM`, `TDM`, `CTF`, `ELIMINATION` and `GUNGAME`.
Elimination closes reservations and ticket consumption at Active, including
the interval before its next heartbeat. Its server also rejects late admission.
The scheduler treats a closed active round as occupied capacity, not a pending
launch, so another instance can start within the configured capacity limit.

## Names and accounts

- **Instant Action:** If no local display name has been saved, ask for one before starting a match and save it for later Instant Action sessions. It is a local preference and does not authenticate the player online.
- **Online Multiplayer:** Require login with **username and password** through the Flask API. Successful login returns a **JWT**; the client stores it and includes it with matchmaking requests and other protected API requests. Reject protected requests with missing or invalid authentication.
- On a later game launch, the client may restore its stored authenticated session and fetch the account profile before opening the online lobby, provided the session is still valid. An expired, missing, or rejected session returns the player to Login. Remembered lobby match-type selection is a separate local preference and must survive this login step; restoring either session or selection never sends a matchmaking request. Token lifetime, renewal, logout, and storage follow the service decisions below.
- The login screen offers **Create Account**. Ask for a username, password, password confirmation, and display name. The display-name field may be left blank initially, but if it is blank at submission, prompt the player to enter one before account creation proceeds. Do not create a nameless account or silently generate a name. Require the two password entries to match before registration is sent.
- A display name, whether local or online, must be **1–20 characters** and contain only ASCII letters, digits, dots, and underscores: `[A-Za-z0-9._]{1,20}`. Reject spaces, dashes, and every other character. The backend checks the online name again, enforces case-insensitive uniqueness across accounts, and rejects a registration whose name is already taken. A username must uniquely identify an account for login and follow the validation below.
- Store passwords as secure password hashes, never plaintext. The server derives a player's online identity from the authenticated account. The client cannot choose a different display name in a match request or join message.
- The lobby displays the authenticated account's display name returned by the backend. On joining a game server, consume its returned player info as the authoritative identity for that match. The server-provided display name must match the authenticated account and supplies the name shown in the joined lobby, scoreboard, and kill feed, including join/leave and elimination events.
- The authenticated account also stores its online robot customisation: selected head ID, upper-body ID, victory-emote ID, primary armor color, and secondary armor color. The client loads and saves this data through protected backend API calls. The backend validates the saved choices; a game server applies the effective match appearance at join and includes it in authoritative player info. Online DM uses the saved head, upper body and both colors. Existing accounts without an upper-body field receive Default; saving writes the complete choice. Online TDM/CTF keeps the chosen head, upper body and emote, permits duplicate heads on a team, and overrides saved armor colors with the assigned team primary and its library-authored contrasting secondary accent. [SCREENS.md](SCREENS.md) defines the Customise screen and preview flow.

## Play, matchmaking, and admission

1. The logged-in player selects **DM**, **TDM**, or **CTF** in the Online Multiplayer lobby and presses **Play**. The client sends that match type with its JWT to the Flask matchmaking service. Online players cannot request a map or alter match options.
2. The matchmaker validates the JWT and account. It searches for a **ready** game-server instance running that match type with an unreserved free participant slot. Selection must respect the **2–10 robot** roster limit and, for TDM/CTF, the team-balancing and team-head rules in [RULES.md](RULES.md).
3. Reserve a slot for this player so concurrent Play requests cannot overfill the same server. If no suitable server exists, the matchmaker starts a new game-server container configured for the selected match type, waits until it is ready for admission, and reserves a slot there. The server, not the client, chooses the map and uses the online match defaults: **30 minutes** and goal score **2 × current roster**.
4. Return the selected server's connection details and a **unique, authenticatable join ticket for this player and server/match**. The ticket must identify or securely bind the authenticated account and its reservation; possession of a copied or fabricated client name is not sufficient for admission. The client connects to the assigned server and presents the ticket.
5. The game server verifies the ticket before admitting the player, consumes or resolves the reservation, and returns authoritative player info including the display name. It assigns teams, head, and spawn according to [RULES.md](RULES.md), then follows the existing Waiting/Countdown/Active match flow. An invalid ticket or full/unsuitable server must not admit the client.

Ticket issuance and validation must be coordinated between the API and game server. Versioned endpoints, request/response schemas, and error codes must be defined before implementation. The ticket lifetime, replay policy, reservation expiry, and failure flow are specified below. Implementations must prevent forged tickets, wrong-server admission, and overfilled rosters.

## Match departure and continuity

Use the game server's roster as the source for join/leave events, team assignment, scoring, and player names. A disconnect or explicit leave removes that robot from the roster and emits a leave event. If a flag carrier departs, drop the flag before checking whether the match must be canceled. During an active online match, fewer than two robots in DM or an empty team in TDM/CTF cancels the match as specified in [RULES.md](RULES.md). A canceled result returns remaining players to the lobby with no automatic rematch. At a normal finish, the same server displays the results and begins a new match on its server-selected random map after the **15-second** countdown unless the player returns to the lobby. Empty servers retire under the policy below.

## Service decisions for the first playable release

- Username is **3–24 ASCII letters, digits, dots, or underscores**. Normalize username and display-name uniqueness with Unicode-invariant ASCII case folding, while preserving the player's chosen display casing. Passwords require at least 12 characters and are hashed with **Argon2id** using an application-reviewed current cost; never log passwords or bearer tokens. Registration and login use rate limiting. No display-name change UI ships in the first release; account support can address later changes.
- Issue a short-lived **15-minute access JWT** and a rotating refresh credential with a maximum **30-day** session. Store credentials in an operating-system protected credential store when available; do not keep them in a plaintext game preference file. Logout revokes the refresh session and deletes local credentials. A new access JWT alone does not create or start a match.
- A successful Play request makes a **30-second slot reservation**. Return a single-use, server-and-match-bound join ticket expiring after **30 seconds**. The game server verifies signature or backend-issued opaque token, account identity, target server/match, expiry, and unused state before admitting. Consuming a ticket is atomic. On failed admission, release the reservation and return a recoverable error to the lobby. Never expose signing keys to the client.
- The matchmaker can admit a player into an **Active** match with a free slot; the game server sends its current map, clock, score, objective, arena-piece phase, and roster before granting control. Its new robot receives the usual five-second spawn protection. It joins the deficient team/zone under [RULES.md](RULES.md), without moving incumbents. Do not place a player into Finished or Canceled state.
- Use a container scheduler with explicit readiness and health checks, one authoritative match process per game-server container, and an authenticated HTTPS control path between API and game servers. MongoDB uses persistent storage and backups. Keep database credentials, JWT keys, and ticket secrets in a server-side secret store; rotate them without a client release. Retire an empty server after a short idle period and drain it before shutdown. The public scheduler targets Edgegap and the local scheduler targets Docker or native development processes.
- The client shows Searching, Starting server, Connecting, and Joining states with Cancel and a bounded timeout. Cancel releases its reservation when possible. On launch failure, ticket expiry, or rejected join, show a plain reason and **Retry** in the lobby; Retry creates a fresh matchmaking request, never reuses a ticket. A disconnect emits the required leave event immediately. If the match remains active, the player can press Play for a new ticket; if the departure canceled it, the lobby explains that result. Reconnection does not silently preserve a roster slot.

Define versioned API schemas and machine-readable error codes before implementation. Keep duration and rate-limit values in server configuration so operations can tune them without changing the gameplay rules.

# Runtime deployment

The local Flask/MongoDB service, scheduler and Godot ENet client/server now live in `services/` and `scripts/network/`. The in-game Online entry restores an account session, offers login/registration, opens the authenticated DM/TDM/CTF/Elimination/Gun Game lobby and runs matchmaking through admission. Customise persists the five authored head/emote choices and independent primary/secondary palette IDs to the account API. Windows refresh credentials use CurrentUser DPAPI; unsupported platforms retain sessions in memory.

See [ONLINE_PROTOCOL.md](ONLINE_PROTOCOL.md) for exact endpoints, ownership boundaries, packet validation/snapshot behavior, launch commands and repeatable verification. `tools/start_online.ps1 -Build` is the local Docker entry point; MongoDB and API bind to loopback, and the API launches/leases individual match containers. Public hosting uses [Render, Atlas and Edgegap](CLOUD_HOSTING.md), where live internet and latency qualification must be performed against the deployed service.

## Local operations and account recovery

Accounts use schema version 1. API startup runs an idempotent forward migration, fills missing loadout fields without changing existing choices, and refuses a newer unknown schema. Public HTTP responses include an `X-Request-ID`; structured logs record request ID, method, route template, status and duration without account identifiers or credentials. The control-token-protected `GET /internal/status` reports schema, live/ready/stale servers and searching requests. `ONLINE_HEALTH` logs simulation time, phase, acknowledgments and input age; these are local diagnostics, not a metrics dashboard.

The scheduler checks owned containers every five seconds and stops stale instances after their database lease expires, including instances discovered after an API restart. Docker labels identify ownership; unrelated containers are not touched. Session revocation and released admission reservations remove their robots on the next heartbeat. Never publish the local Docker socket, API control token or MongoDB port.

For a consistent account backup, stop/quiesce account writes first. Run the repository interpreter:

```
services/.venv/Scripts/python.exe tools/account_backup.py backup --database kylr --file reports/online/accounts.gz
services/.venv/Scripts/python.exe tools/account_backup.py restore --database kylr_restore_review --file reports/online/accounts.gz
```

Use the actual configured database name. The gzip archive and `.sha256` sidecar contain account records including password hashes; protect them as credentials and keep them outside Git/release archives. Restore requires a completely empty, separate database, checks checksum/schema, migrates and recreates uniqueness indexes. It deliberately excludes sessions, reservations, tickets and server leases. Inspect the restored account count/loadouts, then plan an explicit service cutover; the tool never overwrites the live database. This local utility does not replace scheduled, encrypted production backups or a MongoDB snapshot policy.

`tools/verify_service_recovery.py` exercises account appearance across owned API/Mongo restarts and replacement of a test-owned crashed game server. It passed all three checks on the local Docker stack. Public hosting, automated secret rotation and production monitoring/backup retention remain deployment work.

### Custom engine deployment

Local server tools use the custom engine in `engine/`. Before building the game Docker image, build `engine/` for Linux (editor target, `use_streamline=no`) and place its executable at `game/build/linux/godot.linuxbsd.editor.x86_64`. The image imports with that executable.
