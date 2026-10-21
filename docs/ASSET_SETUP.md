# Separately installed assets

Install licensed assets locally before the first Godot import. Downloaded files,
retargeted animation binaries and their Godot import metadata are ignored by Git.
Existing local files remain available when these assets are removed from the index.
Code, asset generators, catalog metadata and setup scripts remain in the repository.

Run the following commands from the repository root unless stated otherwise.

## Original lunar textures

The original regolith PBR set and six planetary terrain PBR layers are included in the repository. No texture download
or external texture license is needed. Its source, generator and channel contract
are documented in [the lunar material source](../library/textures/lunar_surface/README.md).

Terrain3D is an authoring-only dependency; playing, importing and packaging the
game do not require its SDK. See the [terrain rebuild contract](library/PLANETARY_TERRAIN.md)
for the pinned authoring setup, procedural textures and static mesh handoff.

Create a Python environment for the setup tools:

```powershell
python -m venv engine/.local/build-venv
```

## Mixamo animation sources

Sign in to [Mixamo](https://www.mixamo.com/) with your own Adobe account.
Download the following packs and keep their ZIP filenames exactly as listed in
`library/animations/source/`:

| Mixamo pack | Local filename |
| --- | --- |
| Pro Rifle Pack | `Pro Rifle Pack.zip` |
| Basic Shooter Pack | `Basic Shooter Pack.zip` |
| Pistol Handgun Locomotion Pack | `Pistol_Handgun Locomotion Pack.zip` |

Use a consistent standard Mixamo biped with the complete humanoid/finger skeleton.
Download **FBX Binary**, **30 FPS**, **Without Skin**, with keyframe reduction set
to **None**. Retain travel/root motion rather than selecting In Place. Do not
rename FBX members inside pack ZIPs: the retargeter selects their exact names.
The [download specification](../library/animations/downloads.json) lists every
required pack member and individual clip.

Download these individual animations with the same settings and arrange them
relative to `library/animations/source/`:

| Mixamo animation | Local path |
| --- | --- |
| Flying Back Death | `combat/airborne_death/Flying Back Death.fbx` |
| Falling | `environmental/falling/Falling.fbx` |
| Idle | `idle/Idle.fbx` |
| Defeated | `results/defeat/defeated/Defeated.fbx` |
| Chicken Dance | `results/victory/chicken_dance/Chicken Dance.fbx` |
| Dancing Twerk | `results/victory/dancing_twerk/Dancing Twerk.fbx` |
| Gangnam Style | `results/victory/gangnam_style/Gangnam Style.fbx` |
| Hip Hop Dancing | `results/victory/hip_hop_dancing/Hip Hop Dancing.fbx` |
| House Dancing | `results/victory/house_dancing/House Dancing.fbx` |
| Locking Hip Hop Dance | `results/victory/locking_hip_hop_dance/Locking Hip Hop Dance.fbx` |
| Macarena Dance | `results/victory/macarena_dance/Macarena Dance.fbx` |
| Rumba Dancing | `results/victory/rumba_dancing/Rumba Dancing.fbx` |
| Silly Dancing | `results/victory/silly_dancing/Silly Dancing.fbx` |
| Snake Hip Hop Dance | `results/victory/snake_hip_hop_dance/Snake Hip Hop Dance.fbx` |
| Tut Hip Hop Dance | `results/victory/tut_hip_hop_dance/Tut Hip Hop Dance.fbx` |
| Twist Dance | `results/victory/twist_dance/Twist Dance.fbx` |
| Wave Hip Hop Dance | `results/victory/wave_hip_hop_dance/Wave Hip Hop Dance.fbx` |
| Falling To Landing | `spawn/falling_to_landing/Falling To Landing.fbx` |

Validate the complete download before starting the retarget pass:

```powershell
& engine/.local/build-venv/Scripts/python.exe tools/install_animations.py --check-sources
```

### Generate the game animation library

Blender 5.2 is required for retargeting. First generate Tensor and all ten weapons
from their authored sources. From `library/`, run each command serially:

```powershell
$Blender = (Get-Command blender -ErrorAction Stop).Source
& $Blender --background --factory-startup --python models/characters/tensor/model.py
$Weapons = @('pistol','rifle','minigun','lightning_gun','emp_gun','rocket_launcher','flamethrower','flak_cannon','bio_rifle','grenade_launcher')
foreach ($Weapon in $Weapons) {
    & $Blender --background --factory-startup --python "models/weapons/$Weapon/model.py"
    if ($LASTEXITCODE -ne 0) { throw "Weapon generation failed: $Weapon" }
}
& $Blender --background --factory-startup --python animations/retarget.py
if ($LASTEXITCODE -ne 0) { throw 'Animation retargeting failed' }
```

The full retarget pass is compute-intensive. It writes ignored per-clip Tensor
and weapon GLBs, Blender scenes and a manifest under `library/animations/target/`.
Return to the repository root, then install the completed output:

```powershell
& engine/.local/build-venv/Scripts/python.exe tools/install_animations.py --source library/animations/target
& engine/.local/build-venv/Scripts/python.exe tools/install_animations.py --check
```

The installer validates the required GLB inputs before copying the 567 clips
selected by the checked-in game manifest. Extra retarget output is not installed,
and the curated game manifest is not replaced.
Both downloaded FBX/ZIP files and retargeted GLBs stay local. The repository keeps
the animation manifest and source generators. Mixamo's terms govern the animation
data; conversion to a different rig or file format does not establish a right to
redistribute raw animation data publicly.

## Epidemic Sound effects

[The Epidemic MCP downloader](../tools/download_epidemic_audio.py) reads your own
MCP key from `EPIDEMICSOUND_API_KEY` (or `EPIDEMIC_SOUND_API_KEY`) in the environment
or ignored `.env`. Create the key under
[Epidemic account API keys](https://www.epidemicsound.com/account/api-keys).
It is sent only to the official MCP endpoint, never to audio download URLs.
The downloader does not save credentials, signed URLs or account history in Git.

Install the audio setup dependencies, then restore the game's verified effects:

```powershell
& engine/.local/build-venv/Scripts/python.exe -m pip install -r tools/requirements-audio.txt
& engine/.local/build-venv/Scripts/python.exe tools/install_epidemic_audio.py
& engine/.local/build-venv/Scripts/python.exe tools/install_epidemic_audio.py --check
```

The [audio recipe](../library/sounds/epidemic_manifest.json) pins 32 source IDs and
PCM checksums. It restores 37 library clips and recreates all 37 runtime WAVs
with their existing trim points, mono conversion, sample rate, fades and loop
crossfades. Restoration checks each generated PCM checksum before installing it.
Existing matching files are preserved; differing files require `--force`.
Use `--offline` with a previously verified cache or `--output-root <folder>`
to test a clean installation without touching the active game.

For catalog discovery or a private account-history comparison:

```powershell
& engine/.local/build-venv/Scripts/python.exe tools/download_epidemic_audio.py --search 'science fiction weapon'
& engine/.local/build-venv/Scripts/python.exe tools/download_epidemic_audio.py --id 'SOUND-EFFECT-UUID'
& engine/.local/build-venv/Scripts/python.exe tools/download_epidemic_audio.py --history 'engine/.local/download-history.json'
```

History downloads include sound effects and full music recordings when present.
Downloads are WAV files under ignored `library/.local/epidemic/`. The history
option accepts one history page, adjacent pasted JSON pages, or a list of entries
with `id` or `kosmosId`. Downloads resume using SHA-256-verified cache entries.
Use your own account and applicable in-game-use license. API access alone does
not establish game distribution or standalone asset redistribution rights.

After installing local assets, import with the custom engine:

```powershell
& engine/bin/godot.windows.editor.x86_64.console.exe --headless --path game --editor --import --quit
```

## Private assets for CI

For an authorized build runner, prepare a private ZIP whose root contains
`animations/` and `audio/`, with the same layout as `game/assets/`.
Include `animations/manifest.json`, all 1,110 manifest-listed animation GLBs,
and all 46 separately licensed catalog-listed WAV cues. This includes the
bio rifle, grenade launcher and flak cannon animation families, plus the nine
user-supplied projectile-weapon sounds. Prepared WAVs are mono, 16-bit, 48 kHz;
the catalog pins the additional sounds' PCM hashes. Keep this
bundle in access-controlled storage available only to authorized project users.
Do not put it in a public release or upload the raw bundle as a GitHub artifact.
The compiled game package has separate distribution/license requirements.

Create the archive from a validated local installation rather than selecting
files manually. The bundler includes only the installer's allowlisted paths:

```powershell
& engine/.local/build-venv/Scripts/python.exe tools/bundle_private_assets.py --output engine/.local/private-assets/KYLR-game-assets.zip
```

It writes a `.sha256` sidecar. The installer checks that every runtime weapon
family has aim/hit poses and every weapon cue belongs to the audio catalog.
Windows CI restores and validates the archive before compiling the editor.
Package inspection also checks every catalog-listed animation and audio resource.

The workflow downloads the ZIP directly from private R2 storage with the AWS CLI.
Create a bucket-scoped **Object Read only** R2 token. Configure these GitHub
repository secrets under Settings > Secrets and variables > Actions:

| Secret | Value |
| --- | --- |
| `R2_ACCESS_KEY_ID` | R2 S3 Access Key ID |
| `R2_SECRET_ACCESS_KEY` | R2 S3 Secret Access Key |
| `PRIVATE_GAME_ASSETS_SHA256` | SHA-256 of the uploaded ZIP |

For `PRIVATE_GAME_ASSETS_SHA256`, paste only the 64 hexadecimal characters,
without a filename, quotes, or the complete contents of a `.sha256` file.
Compute the value from the exact ZIP uploaded to R2:

```powershell
(Get-FileHash -Algorithm SHA256 -LiteralPath 'engine/.local/private-assets/KYLR-game-assets.zip').Hash.ToLowerInvariant()
```

Replacing the R2 ZIP requires updating this secret. The installer reports checksum,
missing-entry, manifest and audio validation failures separately; it never skips
verification. An archive's root must contain `animations/` and `audio/`, without
an enclosing `assets/` or project folder.

Configure these repository variables in the same settings area:

| Variable | Value |
| --- | --- |
| `R2_ENDPOINT_URL` | Bucket's HTTPS S3 API endpoint from Cloudflare |
| `R2_ASSET_URI` | `s3://<bucket>/<object-key>` for the prepared ZIP |

Only the two R2 S3 credentials are used; the Cloudflare management token and
Epidemic API key are not needed by the release runner. Credentials are supplied
through environment variables, never command-line arguments or checked-in files.
The Windows runner provides the AWS CLI. No presigned URL is stored or renewed.
The workflow checks configuration before compilation, downloads into runner
scratch space, verifies the SHA-256 before extraction, restores only manifest
paths, checks the animation manifest and audio PCM, and deletes the ZIP afterward.
No hosted build is qualified until the settings are configured and a run succeeds.

Local Epidemic authoring tools read the ignored repository-root `.env` or process environment.
Keep all local credentials there; do not create component `.env` files.

To validate or restore a prepared private folder locally:

```powershell
python tools/install_private_assets.py --check
python tools/install_private_assets.py --source 'engine/.local/prepared-game-assets'
python tools/install_private_assets.py --archive 'engine/.local/private-assets/KYLR-game-assets.zip' --sha256 '<archive-sha256>'
```
