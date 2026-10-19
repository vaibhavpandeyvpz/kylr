class_name OnlineInput
extends RefCounted
const KEYS := ["generation","seq","move","yaw","pitch","walk","sprint","crouch","fire","secondary","held","jump","release","reload","slot"]

static func valid(command: Dictionary, generation: String, previous: int) -> bool:
	if command.size() != KEYS.size(): return false
	for key in KEYS:
		if not command.has(key): return false
	if command.generation != generation or not command.seq is int or command.seq <= previous or command.seq > previous+120: return false
	if not command.move is Vector2 or not command.move.is_finite() or command.move.length_squared() > 1.001: return false
	for key in ["yaw","pitch"]:
		if not (command[key] is float or command[key] is int) or not is_finite(command[key]): return false
	if absf(command.yaw) > PI or absf(command.pitch) > PI/4: return false
	for key in ["walk","sprint","crouch","fire","secondary","held","jump","release","reload"]:
		if not command[key] is bool: return false
	if not command.slot is String: return false
	if command.slot in ["","pistol","pickup"]: return true
	return command.slot.begins_with("slot:") and command.slot.substr(5) in ["1","2","3","4","5","6","7","8","9","10"]

static func apply(robot: ArenaRobot, command: Dictionary, predicted := false) -> void:
	robot.move_input = command.move
	robot.yaw = command.yaw
	robot.pitch = command.pitch
	robot.wants_walk = command.walk
	robot.wants_sprint = command.sprint and not command.walk
	robot.wants_crouch = command.crouch
	robot.wants_fire = command.fire
	robot.wants_secondary = command.secondary
	robot.jump_held = command.held
	robot.jump_release = command.release
	if command.jump: robot.jump_buffer = ArenaTuning.JUMP_BUFFER
	if not predicted:
		if command.reload: robot.start_reload()
		if command.slot == "pistol" and robot.can_act(): robot.select_weapon("pistol")
		elif command.slot == "pickup" and robot.can_act() and robot.owned_weapons.size()>1: robot.select_weapon(robot.owned_weapons[1])

		elif command.slot.begins_with("slot:"):
			var index: int = command.slot.substr(5).to_int()-1
			if index>=0 and index<robot.owned_weapons.size(): robot.select_weapon(robot.owned_weapons[index])

static func stop(robot: ArenaRobot) -> void:
	robot.move_input = Vector2.ZERO
	robot.wants_fire = false
	robot.wants_secondary = false
	robot.wants_sprint = false
	robot.jump_held = false
	robot.jump_release = false
