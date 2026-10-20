# KYLR — UI design language

This is the visual and interaction foundation for **every game screen and the in-match HUD**. Read it with [SCREENS.md](SCREENS.md) for layout and screen behavior, [GAMEPLAY.md](GAMEPLAY.md) for mechanics, and [RULES.md](RULES.md) for authoritative match state. It describes the client UI, not new gameplay systems.

## Core idea: the arena control system

KYLR's interface should feel like the control system of the same machines that make the arenas: engineered, fast, and precise. Floating level plates, gimballed thrusters, robot armor, weapon holders, and readable energy indicators supply the visual vocabulary. The result is modern competitive FPS UI: strong hierarchy, few ornamented surfaces, crisp typography, controlled light, and fast feedback.

The asset library's neutral off-white and grey painted shells, matte black frames, stainless/titanium/bronze mechanics, and limited emissive details are the material palette. Translate their **construction logic** into UI: a main plate, an inset readout, a functional edge or joint, and light only where status or interaction needs attention. Avoid turning the entire screen into a glowing hologram. Use the existing asset silhouettes and animations as real focal content; do not cover them with imitation machinery.

Three principles guide every screen:

1. **Information before decoration.** The current objective, next action, and survival state are readable immediately. Decoration sits behind them.
2. **One system, different density.** Menus can show large art and generous spacing; combat HUD uses compact versions of the same colors, type, shapes, icons, and feedback.
3. **Meaningful motion and light.** Parts slide, lock, charge, or dim to communicate state. Long idle animations and constant pulsing never compete with aiming or reading.

## Color and material tokens

Use semantic tokens in a shared theme. These hex values are a starting palette for implementation and visual tuning; keep their **roles and relative contrast** consistent across screens.

| Token | Starting color | Use |
|---|---|---|
| `canvas` | `#0B1119` | Deep backdrop behind menus and overlays. |
| `plate` | `#17222D` | Main opaque panel, card, and HUD backing. |
| `plate-raised` | `#243341` | Raised or selected panel surface. |
| `line` | `#647685` | Panel edge, divider, inactive outline; use sparingly. |
| `text-primary` | `#F3F6F7` | Primary labels, scores, current values. |
| `text-secondary` | `#B9C9D1` | Explanations, metadata, unselected labels. |
| `action` | `#6FE5EA` | Primary action and keyboard/controller focus. Use dark text on a filled action button. |
| `action-hover` | `#A9F5F4` | Hover/raised emphasis, never a new semantic state by itself. |
| `caution` | `#FFC36A` | Low EP, pending change, countdown, and recoverable warning. |
| `danger` | `#FF7275` | Error, critical AH, denied action, and elimination danger. |
| `success` | `#8BDEAD` | Confirmed save, successful join, eligible pickup, and positive completion. |

The **team colors** remain the game-selected yellow, green, blue, and red. They are data, not global UI accents. In TDM/CTF, use a team's color on its score band, flag badge, world marker, and teammate identifier; pair it with a name, icon, or pattern. General selection and Play do not change color with the team. Do not use a team-color block behind long text.

Resource semantics stay stable: **SH** uses a cool shield tint, **AH** uses light neutral armor, and **EP** uses a warm energy tint, each with a label and number. Low EP changes to caution emphasis at the specified 50% threshold. A color theme or reduced-effects setting may change the tint, but never remove the label, number, or distinct shape. Check actual text/background combinations in the running game at normal and reduced brightness; thin grey text over animated scenes is unacceptable.

Use mostly opaque panels where text sits. Subtle translucency can reveal a lobby robot or paused world at the edge, but it must not make controls dependent on the background. A fine metallic grain, restrained edge highlight, or small inset shadow is enough material depth. Avoid heavy blur, broad bloom, chrome gradients, faux scratches, noisy hexagon wallpaper, and neon outlines on every object.

## Shape, grid, and depth

- Base layout on an **8-unit spacing grid**. Use 8 for close label/value spacing, 16 for related controls, 24–32 for panel interiors, and larger gaps between primary regions. At 1080p, keep a roughly 32 px safe margin; scale with viewport rather than pinning elements to raw screenshot coordinates.
- Menu plates, buttons, fields, tabs and selectable cards share an 8 px corner radius, 1 px seam and the same surface colors. Focus uses a transparent 2 px outline; selected cards retain a raised surface and action seam. These controls have no drop shadow. Dialogs sit above the page through opaque surfaces and a dimmed backdrop. Combat readouts retain their compact open rails.
- Use **three depth levels**: world/art backdrop, primary plate, and raised active control. Tooltips and dialogs sit above them. Depth should make click targets and hierarchy clear; it is not a stack of translucent boxes.
- Buttons have a solid silhouette and a comfortable hit area. Primary actions are visually dominant; secondary actions are outlined or quieter. A selected card and a focused card must be distinguishable from each other.
- Avoid copying a 3D prop's detailed bolts and pistons into small UI components. Borrow its bevel/assembly rhythm, then simplify until labels and icons remain clean at HUD size.

## Typography and numbers

Use **two type roles** across the game: a compact, squared or condensed display face for section titles, match scores, and major actions; and a highly legible sans-serif face for body text, controls, names, feed entries, and help text. Choose actual font files with a complete character set and suitable licensing when the asset library/UI assets are ready; the specific families are an **Open decision**. Do not use a distressed military stencil for paragraphs or a tiny futuristic font for live combat data.

At a 1080p viewport, start with approximately **30–40 px** primary screen titles, **22–30 px** key scores/CTA labels, **16–20 px** ordinary UI text, and **14–16 px** secondary metadata. Scale as a system for different viewports. Numeric readouts use aligned figures so timers, ammo, SH/AH/EP, and scores do not jitter when values change. Keep unit labels beside values: `EP 50 / 100`, `30:00`, `18 / 100`, and `3 packs` are clearer than bare numerals.

Use sentence case for explanations and controls, short uppercase only for compact category tags or match codes (`DM`, `TDM`, `CTF`, `SH`, `AH`, `EP`). Preserve display names as entered and allow up to 20 characters in their assigned space. Truncate only a visual label if necessary, with a way to see the full name in player info.

Menu actions and tab names use plain labels, without decorative serial numbers or selection glyphs prefixed to their text. Show selection through the component's filled surface and outline; retain meaningful numeric values and weapon hotkeys.

## Icons, imagery, and game assets

- Icons use a shared stroke weight, squared terminals, and simple filled areas. A pictogram must remain recognizable at its smallest HUD size. Pair unfamiliar symbols with a text label on menus and Settings; provide accessible names for icon-only HUD controls.
- Weapon slots use the **side-profile silhouettes** defined in [SCREENS.md](SCREENS.md). Keep silhouette orientation, baseline, and visual weight consistent across pistol, rifle, flamethrower, EMP gun, lightning gun, minigun, and rocket launcher.
- The lobby robot and map previews are lit like actual world objects, with broad readable shapes and restrained rim light. Backgrounds may show floating arena segments and thruster glow, but reduce contrast under text and keep the robot separate from the plate UI.
- Energy, shield, flag, portal, and pickup icons should reflect their real in-world objects. Use one visual identity for a concept across a pickup, HUD notice, help panel, and results screen. Do not imply a new ability, loot rarity, or currency through an attractive but unexplained icon.
- Results use a larger version of the HUD score/flag components so the winner, MVP, and statistics feel like a continuation of the match rather than a different application.

## Interaction states and feedback

Every interactive component uses the same state model:

| State | Appearance and response |
|---|---|
| Default | Quiet plate or outline; label fully readable. |
| Hover | Slightly brighter surface or seam; no large movement. |
| Focus | Strong visible `action` outline/marker that survives a busy background. Keyboard and controller focus receive the same clarity as mouse hover. |
| Selected | Persistent filled or inset marker with a label/shape change; distinct from temporary focus. |
| Pressed | Brief physical compression or light contraction, then immediate action feedback. |
| Busy | Hold the control in a non-repeatable state and show the current step (`Finding Match`, `Starting Server`, `Connecting`, `Applying`). |
| Disabled | Muted value plus an explanation where a dependency blocks it; no misleading hover/press animation. |
| Error / success | Short message tied to the action, matching `danger`/`success` semantics and readable without color. |

Start transitions quickly: roughly **0.12–0.18 s** for hover/focus/press and **0.2–0.35 s** for panel or tab changes. These are motion targets for the UI, not gameplay timings. Prefer directional movement consistent with a plate sliding into a bracket, a readout lighting, or a holder locking. Avoid bouncing menus, long camera sweeps for routine navigation, and constant pulsing of every actionable item. Respect reduced decorative motion and keep any crucial state change visible through shape/text when motion is reduced.

Sound follows the same logic: quiet mechanical ticks for focus and selection, a firmer lock for committing, restrained low-frequency feedback for failure. Use the existing master/effects/interface audio controls. Never rely on sound alone for a state change.

## Applying the system across screens

| Surface | Expression of the shared language |
|---|---|
| **Main Menu** | Strong KYLR identity, one arena/robot hero scene, two clear game-mode entrances, and a quiet Settings route. Large action plates but little dense text. |
| **Instant Action setup** | The same selected cards and readout rows as the online lobby; map choice and configurable options use compact inset controls. Bot difficulty is labelled as an Instant Action setting. |
| **Login / Create Account** | Centered plate and clean form fields. Validation appears at its field; the primary action follows the shared button states. Display-name rules are visible without crowding the form. |
| **Online lobby** | Robot remains the hero. DM/TDM/CTF cards use the panel shape, selected marker, and team-neutral action accent. Play is the largest control at bottom right. Search/connection states use the shared busy/status treatment. |
| **Customise** | The lobby robot expands into an interactive preview stage. Blender-rendered head/emote portrait tiles, torso finish previews, selection markers, and Save/Revert actions use the same plate geometry and semantic states; neutral lighting keeps armor colors honest. |
| **Settings** | Same plates, tabs, readouts, focus marker, and action bar, at a higher information density. The contextual help pane is an inset technical readout, not a separate visual theme. |
| **In-match HUD** | Open, holographic rails with only small dark translucent backings where bright scenery would obscure numbers. The top score, available resources, owned weapon silhouettes, leaderboard, and event feed inherit typography, icon rules, semantic colors, and brief animated feedback in both FPV and TPV. Hide unowned or inactive elements. Keep the center aim area clear; only the world-view robot/weapon presentation changes with camera mode. |
| **Scoreboard / results** | Expand HUD elements into larger cards and timelines. Use team colors only for team identity, distinguish winner/draw/cancellation with text and form, and keep Return to Main Menu/Lobby in the same CTA language. |

Menus and the HUD share tokens and component anatomy, but their opacity and scale differ: menus can hold a large scenic backdrop, while the HUD must surrender space to the world. A screenshot of either should still clearly belong to KYLR through plate geometry, typography, icon family, and state colors.

## Implementation and review contract

- Store colors, type roles, spacing, corner treatment, borders, focus states, and motion durations in shared Godot Theme/resources or equivalent reusable UI styles. Screen scenes consume these tokens; avoid per-screen copies with nearly identical values.
- Build reusable components for primary/secondary buttons, selectable match cards, tab strips, setting rows, resource bars, team badges, notifications, weapon slots, and dialogs. Each component owns all states above.
- Check the theme in **Main Menu, lobby, Customise, Settings, DM/TDM/CTF HUD, and results** at normal and reduced visual-effects settings. Verify bright/dark map backgrounds, selected focus, long names, low EP, damaged AH, active SH, team colors, armor-color swatches, silhouette tiles, and a burst of feed events.
- If an asset is unfinished, use a neutral silhouette or simple world render rather than inventing a clashing placeholder style. The asset library remains the source for actual models, materials, sockets, and animations; this document governs UI translation only.

Body text uses Inter; display labels and headings use Rajdhani SemiBold or Bold.

The combat lower edge reserves 40% for the right-aligned weapon tray, 5% space, 25% for the actual first-person weapon, 5% space, and 25% for SH/AH/EP bars. The tray supports five columns in two rows and scales slots down to fit; a single slot never exceeds 15% of viewport width.

Combat notices use the shared open message
scrim: softly fading ink at 24% opacity, outlined Inter text, and sparse semantic
accents. High contrast raises it to 74%. Keep full plates for menus, dialogs and
the scoreboard; transient messages must not look like modal black panels.

First-life tutorial panels match weapon-slot ink tint at 38% opacity, with a
cyan rail, cyan heading and Material Symbols outlined info icon. Body copy uses
outlined Inter; High Contrast raises the backing to 74%.

Robot and announcer speech share the kill/event feed as short sentences with
bold robot names or a bold “Announcement:” prefix. Only robot names take team colors in TDM/CTF. No separate
lower-center subtitle block; preserve the Subtitles preference and readable
Settings transcript.

`MenuSkin` owns menu color tokens, corner radius, seams, padding and every button state. Main Menu, Instant Action, Settings, online screens, results actions and loading recovery controls consume it. Primary actions retain dark labels across hover, focus and press; disabled actions use muted labels. Selected cards use a raised plate with an action seam, distinct from the transparent focus outline.

Boolean rows use `SettingsToggle` with explicit On/Off text and a switch indicator. Normal and checked rows share their plate; hover and checked-hover share a brighter plate. Every state is supplied explicitly for CheckButton, including disabled and focus, so native fallback styles cannot replace the shared geometry. HUD text and semantic accents consume the same palette as menus; opacity and density remain appropriate for combat.
