# Combustion and dust atlas sources

The three PNG atlases in this folder are editable source assets and stay in Git.
They contain 4 × 4 frames with transparent margins around each sprite:

- `fireball_atlas.png`: expanding combustion and cooling soot.
- `grenade_atlas.png`: brief detonation and pale dust.
- `fire_contact_atlas.png`: surface fuel flame and dissipating wisps.

`export_fireball.py` validates alpha, frame occupancy and tile edges, records
content hashes and copies pixels without resampling. Shader sampling uses
normalized quarter-cell coordinates. Preserve RGBA values and transparent
margins; runtime alpha rejection suppresses low-opacity fringe pixels.
