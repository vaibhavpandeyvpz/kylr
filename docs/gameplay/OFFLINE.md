# KYLR — Instant Action

Instant Action is the local game mode: one human-controlled robot and AI bots in every remaining slot. It offers DM, TDM, and CTF match types under [RULES.md](../RULES.md); bot behavior is specified in [BOTS.md](BOTS.md). It does not require an account or a network service.

## Setup and start

1. Ask for a local display name only if no valid one is saved. It is 1–20 ASCII letters, digits, dots, or underscores (`[A-Za-z0-9._]{1,20}`). This name is independent of online identity.
2. Select a map, match type, difficulty, total robot count, goal score, and time limit. Restore the last valid choices on later visits. An unavailable saved map falls back to a valid map with an explanatory notice. Nothing starts until the human selects **Start Match**.
3. Validate the map's chosen match-type contract (spawns, routes, pickups, objective bases if CTF, and cinematic path), create the bot roster, assign zones and teams, and load the full map and begin the five-second movement-locked spawn countdown. Start the match clock and normal control when the countdown and initial protection end.

| Setting | Allowed | First-run default |
|---|---|---|
| Bot difficulty | Noob, Hobbyist, Skilled, Impossible | Hobbyist |
| Total robots, including human | 2, 4, 6, 8, 10 | 10 |
| Goal | Integer 1–999 | 25 |
| Time limit | Whole minutes 5–60 | 15 |

The goal counts individual kills in DM, team kills in TDM, and captures in CTF. Use the same score/time end conditions as online. The human has unmodified damage and aim. Difficulty affects every bot through the table and behavior in [BOTS.md](BOTS.md), without changing weapons or scoring.

## Roster and appearance

Use the five Tensor heads in the character catalog. Assign heads randomly at match start. In TDM/CTF, enforce unique heads **within each team**; across opposite teams a head may repeat. Team colors are two distinct random choices from yellow, green, blue, red; the primary armor shows the assigned team color and the secondary uses its library-authored contrasting accent. DM retains the authored neutral secondary. Distribute team/zone membership evenly, with difference at most one when an odd roster occurs through a future variant. Randomize which team receives the extra participant in an odd roster. Do not reroll a robot's head or team on respawn.

## Local flow and practice

The setup can display a short, nonblocking map briefing: layout sketch, flag bases, portal/jump links, and the map's special event. The first local match may show dismissible control hints during the opening sequence and first life. These hints never pause the match, award resources, or obscure the reticle. The player can turn them off in Settings. Use Instant Action as the safe place to learn the game's EP cycle and dynamic arena before online play, without adding a third game mode.

Pause freezes the entire local simulation, including timers, bot logic, projectile motion, pickups, and music transition clock. Resume restores the same state. Leaving an Instant Action match returns to Main Menu without counting a winner. A completed match holds its scoreboard until **Return to Main Menu**; no automatic rematch starts.

When the human-controlled robot dies, show its death in third person, hold the finished animation for one second, then respawn. Bots and the local simulation continue at normal time during this view; pause suspends the whole local simulation.

Valid setup choices are saved immediately, including a valid newly entered call sign, without waiting for Start Match. Subsequent visits display the saved call sign without prompting again. Saved odd robot counts round up to the next supported even count, bounded to 2–10, with an explanatory setup notice. Removed saved arenas reset to the first available arena, save that replacement, and explain the reset before a match can start.
