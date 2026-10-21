# Combustion and dust atlas sources

The PNG atlases in this folder are editable source assets and stay in Git.
They contain 4 × 4 frames with transparent margins around each sprite:

- `fireball_atlas.png`: projected flamethrower flame/fume particles.
- `rocket_explosion_atlas.png`: directional rolling orange warhead fireball,
  dark soot mantle and cooling embers, dedicated to rocket impacts.
- `flak_dust_atlas.png`: dedicated compact abrasion dust used by flak contacts.
- `grenade_combustion_atlas.png`: tiny, brief grenade ignition cooling into
  neutral grey lunar dust, with transparent margins around all sixteen frames.
- `fire_contact_atlas.png`: surface fuel flame and dissipating wisps.

Authoring prompts: [grenade](grenade_combustion_prompt.md) and
[rocket](rocket_explosion_prompt.md), generated with the built-in image tool.

`export_fireball.py` validates alpha, frame occupancy and tile edges, records
content hashes and copies pixels without resampling. Shader sampling uses
normalized quarter-cell coordinates. Preserve RGBA values and transparent
margins; runtime alpha rejection suppresses low-opacity fringe pixels.
