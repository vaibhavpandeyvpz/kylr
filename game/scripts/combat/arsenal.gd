class_name Arsenal
extends RefCounted

const HEADS = ["projector", "sentinel", "porthole", "raptor", "arachne"]
static var WEAPONS: Dictionary = ContentRegistry.weapons()
const EMP_FULL_RANGE := 20.0
const EMP_MAX_RANGE := 25.0
const ORB_DIAMETER := 0.10
const PROJECTILE_LIFETIME := 20.0

static func orb_secondary(weapon: String) -> bool:
	return weapon in ["lightning_gun", "flamethrower"]

static func mode_value(weapon: String, key: String, secondary := false) -> float:
	var profile: Dictionary = WEAPONS[weapon]
	var prefix := "secondary_" if orb_secondary(weapon) else "scoped_"
	return float(profile.get(prefix+key,profile.get(key,0.0)) if secondary else profile.get(key,0.0))

static func projectile_range(weapon: String) -> float:
	return mode_value(weapon,"range",orb_secondary(weapon))

static func shot_cue(weapon: String, secondary: bool) -> String:
	return weapon + "_secondary" if orb_secondary(weapon) and secondary else weapon

static func shield_split(damage: float, shield: float) -> Vector2:
	return Vector2(damage * 0.2, minf(shield, damage * 0.8)) if shield > 0 else Vector2(damage, 0)

static func emp_damage(distance: float) -> float:
	return float(WEAPONS.emp_gun.damage) * emp_opacity(distance)

static func emp_opacity(distance: float) -> float:
	return clampf((EMP_MAX_RANGE - distance) / (EMP_MAX_RANGE - EMP_FULL_RANGE), 0.0, 1.0)

static func splash_damage(distance: float) -> float:
	return minf(10.0, 11.0 - distance) if distance <= ArenaTuning.ROCKET_SPLASH_RADIUS else 0.0

static func winners(entries: Array, score_key: String, time_key: String) -> Array:
	var result: Array = []
	var score := -1
	var reached := INF
	for e in entries:
		if e[score_key] > score or (e[score_key] == score and e[time_key] < reached):
			score = e[score_key]
			reached = e[time_key]
			result = [e]
		elif e[score_key] == score and e[time_key] == reached:
			result.append(e)
	return result

