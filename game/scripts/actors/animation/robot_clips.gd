class_name RobotClips
extends RefCounted

const VICTORIES := [
	"victory_chicken_dance", "victory_dancing_twerk", "victory_gangnam_style",
	"victory_hip_hop_dancing", "victory_house_dancing", "victory_locking_hip_hop_dance",
	"victory_macarena_dance", "victory_rumba_dancing", "victory_silly_dancing",
	"victory_snake_hip_hop_dance", "victory_tut_hip_hop_dance", "victory_twist_dance",
	"victory_wave_hip_hop_dance"]

static func uses_weapon(key: String) -> bool:
	return not key.begins_with("common/")

static func direction(input: Vector2) -> String:
	var motion := input.normalized()
	var forward := "forward" if motion.y < -0.38 else "backward" if motion.y > 0.38 else ""
	var side := "right" if motion.x > 0.38 else "left" if motion.x < -0.38 else ""
	return forward + ("_" if forward != "" and side != "" else "") + side

static func travel(input: Vector2, speed: float, crouched: bool, family: String, turn: float) -> String:
	var heading := direction(input)
	if heading == "": return idle(crouched, false)
	if crouched: return "crouch_walk_" + heading
	# Actual displacement rarely equals a requested speed exactly; use gait midpoints.
	var gait := "sprint" if speed >= (ArenaTuning.RUN_SPEED+ArenaTuning.SPRINT_SPEED)*0.5 else "run" if speed >= (ArenaTuning.WALK_SPEED+ArenaTuning.RUN_SPEED)*0.5 else "walk"
	if family == "pistol" and gait != "sprint" and absf(turn) >= 0.015 and heading in ["forward", "backward"]:
		return gait + ("_backward" if heading == "backward" else "") + "_arc_" + ("right" if turn < 0 else "left")
	return gait + "_" + heading

static func idle(crouched: bool, aiming: bool, family := "", settled := false) -> String:
	if crouched and not aiming and family == "pistol" and settled: return "kneeling_idle"
	return "idle_crouching_aiming" if crouched and aiming else "idle_crouching" if crouched else "idle_aiming" if aiming else "idle"

static func takeoff(family: String, moving: bool, charged: bool) -> String:
	if family == "pistol" and not charged: return "jump_running" if moving else "jump"
	return "jump_up"

static func landing(long_fall: bool) -> String:
	return "falling_to_landing" if long_fall else "jump_down"

static func turn(crouched: bool, delta: float) -> String:
	return ("crouch_" if crouched else "") + "turn_90_" + ("right" if delta < 0 else "left")

static func death(cause: String, local_incoming: Vector3, crouched: bool) -> String:
	if cause == "Fall off map": return "falling"
	if cause == "Lava": return "death_front"
	if cause == "rocket_launcher": return "death_flying_back"
	var behind := local_incoming.z > 0.25
	if "headshot" in cause:
		if crouched: return "death_crouching_headshot"
		return "death_back_headshot" if behind else "death_front_headshot"
	if local_incoming.x > 0.5: return "death_right"
	return "death_back" if behind else "death_front"

static func victory(robot_id: int, match_number: int) -> String:
	return VICTORIES[posmod(robot_id + match_number, VICTORIES.size())]
