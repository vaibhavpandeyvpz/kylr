# Gameplay guide

Start with [GAMEPLAY.md](../GAMEPLAY.md) for the player experience and [RULES.md](../RULES.md) for match state and scoring. These focused documents own implementation detail:

| Area | Source of truth |
|---|---|
| Weapons, ammo, damage, recoil and pickup rules | [WEAPONS.md](WEAPONS.md) |
| Instant Action setup and lifecycle | [OFFLINE.md](OFFLINE.md) |
| Online Multiplayer player flow and match continuity | [ONLINE.md](ONLINE.md) |
| AI-controlled robots | [BOTS.md](BOTS.md) |
| Arena layouts, traversal and dynamic events | [ARENAS.md](ARENAS.md) |
| Online account and match service architecture | [service ONLINE.md](../ONLINE.md) |
| Weapon asset sockets, animation and visual effects | [WEAPON_EFFECTS.md](../WEAPON_EFFECTS.md) |

**Game modes** are Instant Action and Online Multiplayer. **Match types** are DM, TDM and CTF. A **robot** is any playable character; a **bot** is an AI-controlled robot. **EP** is Energy Points, while an **Energy Core** is a pickup. Rules and defaults in these documents are design targets; balance changes should be recorded in data and in the owning document.
