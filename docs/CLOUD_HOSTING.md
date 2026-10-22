# Multiplayer hosting

KYLR uses Render for the HTTPS account/matchmaking API, MongoDB Atlas for
persistent accounts and Edgegap for authoritative Linux ENet servers. Clients
connect directly to the assigned Edgegap UDP endpoint. Render does not carry
gameplay packets or launch local containers.

## Atlas

Create an Atlas Free cluster near the Render region. Create a database user with
`readWrite` on `kylr` only. Store its driver URI in Render's secret `MONGO_URI`,
including the database name if desired (the API defaults to `kylr` when omitted):

```text
mongodb+srv://<user>:<url-encoded-password>@<cluster>/kylr?retryWrites=true&w=majority
```

Add Render's outbound IP ranges to Atlas Network Access. Do not disable TLS
verification or put this URI in the game. Allow a developer IP separately for
intentional remote tests; never run tests against live accounts.

Atlas Free allows 0.5 GB storage, 500 connections and 100 read/write operations
per second. The API caps its pool at 20, bounds concurrent password hashing and
matchmaking, shares cleanup work and expires sessions, rate counters and match
requests through TTL indexes. Gameplay snapshots and physics stay off Atlas.
Monitor throttling/storage and arrange account backups as in [ONLINE.md](ONLINE.md).

## Render

Use the root [render.yaml](../render.yaml) Blueprint or its settings for an
existing Docker service. Docker context: `game/`; Dockerfile:
`game/services/deploy/Dockerfile.api`; health check: `/healthz`.
The unprivileged container listens on Render's `PORT` without a Docker socket.

| Variable | Setting |
|---|---|
| `MONGO_URI` | Secret Atlas URI; defaults to database `kylr` when no name is supplied |
| `JWT_SECRET` | Random secret of at least 32 characters |
| `CONTROL_TOKEN` | Different random administrative secret of at least 32 characters |
| `SCHEDULER` | `edgegap` |
| `EDGEGAP_API_KEY` | Secret management token, never a client setting |
| `EDGEGAP_APPLICATION` | App name, normally `kylr` |
| `EDGEGAP_VERSION` | Exact immutable app version from Edgegap |
| `GAME_API_URL` | Optional explicit HTTPS origin; Render supplies `RENDER_EXTERNAL_URL` automatically |
| `EDGEGAP_MAX_DEPLOYMENTS` | `1` for the free trial |
| `SERVER_START_SECONDS` | `180` |
| `MATCH_TIMEOUT_SECONDS` | `180` |
| `TRUST_PROXY_HOPS` | `1` on Render's managed ingress; `0` for direct/local listeners |

For a manually created service, generate each signing/control secret separately
and paste the two different values into Render's Environment settings:

```powershell
$bytes = New-Object byte[] 48
$rng = [Security.Cryptography.RandomNumberGenerator]::Create()
$rng.GetBytes($bytes)
$rng.Dispose()
[Convert]::ToBase64String($bytes)
```

An ignored local `.env` is not uploaded to Render. Set its runtime variables in
Render explicitly, or use the Blueprint's generated values.

Render supplies its own public callback URL on the first deployment, so `GAME_API_URL`
is not required there. The Blueprint generates independent signing/control secrets. Preserve them on
redeploy. Game servers receive instance-specific control credentials whose hashes
are stored in Atlas, not the management key, JWT secret or database URI. Control
callbacks use HTTPS and the matching instance credential.

Render Free sleeps after 15 minutes without inbound traffic; the first request
can take about a minute to wake it. Clients allow 75 seconds and show a recoverable
error if unavailable. Live games send real five-second heartbeats; do not add
artificial traffic to defeat free limits. API restarts can interrupt matchmaking;
expired requests permit a fresh retry. Deployment records survive in Atlas.

## Edgegap server image

The image downloads checksum-pinned official Godot 4.7.2 for Linux and imports
the restored game assets. Keep its
registry private because it contains separately licensed runtime assets.

Configure the existing R2 secrets/variables for private asset restoration, plus:

- GitHub secret `EDGEGAP_API_KEY` from Edgegap's API tokens page.
- GitHub secrets `EDGEGAP_REGISTRY_USERNAME` and `EDGEGAP_REGISTRY_TOKEN` from the
  Edgegap Container Registry page.
- GitHub variable `EDGEGAP_APPLICATION` for the existing app name.
- GitHub variable `EDGEGAP_IMAGE`, for example
  `registry.edgegap.com/<organization>/kylr-server`, without a tag.

Run **Verify multiplayer and build dedicated server** in Actions. It tests the API
against MongoDB, restores assets, downloads official Godot, imports the
project and checks the server script. Enable `publish` to push to the private
registry with the source commit as its immutable image tag, then registers that
commit as an Edgegap app version with UDP port 25000, 1.5 vCPU, 3 GB memory,
60-minute duration and restart policy Never. The default only validates/builds.
Publishing never allocates a live match or overwrites an existing version.

The workflow registers the version automatically. When creating an app version manually, configure its registry credentials and:

- Linux/AMD64, **25000 UDP**, port name **gameport**.
- Restart policy **Never**, so failed matches cannot silently restart with stale admission state.
- Resources within the account allowance; measure memory before reducing allocations.
- Maximum duration within the hosting account limit. The free trial currently
  allows one concurrent deployment and 60 minutes per deployment. A 30-minute
  round's continuation does not extend that platform deadline.

The trial also limits the account to one app and two app versions. Remove an
unused version in the dashboard before publishing a third distinct build; the
workflow deliberately does not delete versions that may still serve players.

Set Render's `EDGEGAP_VERSION` to that version. The backend uses the v2 deployment
API and status API to resolve the public UDP mapping. Admission requires both
provider mapping and a game heartbeat. Join tickets remain single-use and expire
after 30 seconds. The internal container port is never given to remote clients.

`EDGEGAP_GAME_PORT`/`EDGEGAP_PORT_NAME` override the internal port/mapping name
when the app version agrees. `EDGEGAP_LATITUDE`/`EDGEGAP_LONGITUDE` select placement
coordinates (default Mumbai); configure them near the initial player population.
Clients cannot submit arbitrary provider arguments.

Each deployment runs one DM/TDM/CTF match of up to ten humans. At the default cap,
a different match type or full server returns a capacity message. Empty servers
exit after 60 seconds; stale owned deployments are stopped. Heartbeat loss denies
admission, and disconnected clients return to the lobby. An ambiguous creation
timeout reconciles the deployment by its ownership tags rather than repeatedly
creating servers. Inspect Edgegap's dashboard if provider reconciliation is unavailable.

## Client builds and live checks

Set GitHub variable `KYLR_PUBLIC_API_URL` to the Render HTTPS origin. Windows
packaging writes it into the game before export. For source builds, from the root:

```powershell
python tools/configure_online.py --url https://<service>.onrender.com
```

This edits `game/project.godot`; commit the public origin if source builds should
use it by default. Clients read `network/services/api_url`, with `KYLR_API_URL`
as a runtime override. Unconfigured source builds use loopback for local testing.
No hosting, account or database secret belongs in either setting.

After deployment, check `/healthz`, create two test accounts and join the same
match type from separate clients. Check countdown, movement/fire, late join,
disconnect/cancellation, results/continuation and return to lobby. Repeat DM/TDM/CTF.
Local tests and successful builds do not establish live internet connectivity.

Provider limits: [Render](https://render.com/docs/free),
[Atlas](https://www.mongodb.com/docs/atlas/reference/free-shared-limitations/),
[Edgegap](https://edgegap.com/resources/pricing).
