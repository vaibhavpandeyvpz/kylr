# KYLR game guidance

Before changing gameplay code, scenes, UI, or maps, read [docs/GAMEPLAY.md](../GAMEPLAY.md), [docs/RULES.md](../RULES.md), and the relevant focused guide from [docs/gameplay/README.md](../gameplay/README.md). Before changing weapon presentation, effects, animation sync, or camera attachments, also read [docs/WEAPON_EFFECTS.md](../WEAPON_EFFECTS.md). Before changing any menu, lobby, HUD, or screen UI, also read [docs/DESIGN_LANGUAGE.md](../DESIGN_LANGUAGE.md) and [docs/SCREENS.md](../SCREENS.md). Before changing audio, read [docs/AUDIO.md](../AUDIO.md). Before changing online login, accounts, matchmaking, server joins, or deployment, also read [docs/ONLINE.md](../ONLINE.md). [docs/PLAYTESTING.md](../PLAYTESTING.md) owns verification procedures.

For bot AI, traversal, map collision or fixtures, match objectives, and movement-performance changes, also follow [docs/PLAYTESTING.md](../PLAYTESTING.md): profile DM, TDM, CTF, Elimination and Gun Game at 2, 4, 6, 8 and 10 combatants, run every CTF case for at least 120 simulated seconds, and inspect physical route use and objective progress before calling the work done.

- `docs/GAMEPLAY.md` describes the player experience and links to detailed contracts.
- `docs/RULES.md` defines match states, match-type objectives, scoring, and edge cases.
- `docs/gameplay/WEAPONS.md` owns weapon profiles, ammunition, recoil, damage and pickup rules.
- `docs/gameplay/OFFLINE.md` owns Instant Action setup and local flow.
- `docs/gameplay/ONLINE.md` owns the Online Multiplayer player and match flow.
- `docs/gameplay/BOTS.md` owns AI perception, decisions, difficulty and match-specific tactics.
- `docs/gameplay/ARENAS.md` owns map markers, traversal, interaction safety and moving-map events.
- `docs/ONLINE.md` defines account identity, the Flask API and matchmaker, join tickets, and container responsibilities.
- `docs/SCREENS.md` defines screen flow and the Online Multiplayer lobby, Customise screen, in-match HUD, and Settings screen layouts, interactions, and states.
- `docs/DESIGN_LANGUAGE.md` defines the shared visual theme, semantic tokens, typography, component states, and motion used by every screen and HUD element.
- `docs/WEAPON_EFFECTS.md` maps each weapon's exported gizmos and animation events to Godot effects in FPV and TPV.
- `docs/AUDIO.md` defines weapon, movement, environment, music and robot/announcer voice cues.
- **Game modes** are Instant Action and Online Multiplayer. **Match types** are DM, TDM, CTF, Elimination, and Gun Game. Preserve this distinction in menus, data, and code.
- A **robot** is any player/character in the match. A **bot** is specifically an AI-controlled robot; a human controls a robot in either game mode. Instant Action fills the other slots with bots. Do not use “bot” for every robot. Keep match-type rules in one place so the HUD and match controller cannot disagree.
- When changing a rule or mechanic, update the relevant document in the same change. Keep map-specific data in map resources rather than hard-coding it into shared rules.

The asset pipeline lives in `library/`. When importing or changing assets, also follow [`../library/AGENTS.md`](../../library/AGENTS.md). Its generated `.glb` files and animation manifest are the source of asset contracts; this document does not redefine them.

For every model change, edit its source Python generator in `library/` first, regenerate and validate the model there, then copy the generated files into `game/assets/models/`. Never treat a copied GLB, FBX, Blender file, or imported Godot resource as the editable source of a model.

## Map ownership and recessed placements

Map geometry ownership: only integral platform and bridge castings and required Boolean cuts/wells belong
to the map geometry budget. Separate authored models (pillars themselves, thrusters,
sconces/battens, architecture, weapons, ammo and gameplay fixtures) never count
toward that budget: place named gizmos, then import the native assets in previews
and runtime with identity local transforms. Lunar scenery is a separate gizmo
instance. Preserve every native detail. Skyfall has a 75,388-triangle map-owned budget; other map builds
use the 25,000 default. Report imported asset counts separately.

Every sunken placement uses its native outer footprint plus **1 mm per side** in
both visual and collision Boolean cutters. Thus a 1 × 1 m fixture gets a
1.002 × 1.002 m opening. Apply the same rule to rotated/wall-mounted recesses;
do not scale the prop or move its authoritative gizmo to obtain clearance. Platform and lip cutters extend 0.5 m above the walkable surface to clear overlapping regolith, with the required pit depth retained below it. Apply cuts before separating regolith for gizmo imports.

Native mechanical architecture placements: use `pillar_platform` only below the pillar, and sample the native ram extension to meet the next floor underside. Use `weapon_holder_wall` for raised holder placements; its native `WeaponHolderMount` owns the holder aperture and axes. These are separate gizmo imports in populated previews/runtime, excluded from map-owned triangles.

## Godot runtime

Use official Godot 4.7.2 for game runs, imports, validation and exports. Resolve
executables through `GODOT` or PATH. Use matching official export templates.
Run Git commands at the root and game tools from `game/`. Keep binary overrides
out of Git.
