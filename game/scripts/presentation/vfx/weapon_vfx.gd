class_name WeaponVfx
extends Node

var robot: ArenaRobot
var emit_time := 0.0
var pilot: FlamePilot
var pending: Array[Dictionary] = []
var last_weapon := ""
var was_streaming := false
var stream_age := 0.0
var beam_target := Vector3.ZERO
var beam_hit: Dictionary = {}
var stream: CombatStream
var contact_time := 0.0
var receptor_sparks: Array[LightningSparks] = []
var receptor_gun: WeakRef

func _ready():
	# Sample both camera rigs after their current-frame pose updates.
	process_priority = 330

func stop_stream():
	if is_instance_valid(stream): stream.release()
	stream = null

func _exit_tree():
	if is_instance_valid(stream): stream.queue_free()
	clear_receptor_sparks()
	clear_pilot()

func clear_pilot():
	if is_instance_valid(pilot):
		pilot.hide()
		pilot.queue_free()
	pilot = null

func update_pilot():
	var world = robot.arena_match
	var enabled: bool = robot.alive and robot.equipped == "flamethrower" and world.phase == "Active" and robot.spawn_remaining <= 0 and robot.repair == null
	if world is ArenaMatch and world.replicating and world.authority: enabled = false
	var model := gun() if enabled else null
	var source := Assets.socket(model, "PilotFlame") if is_instance_valid(model) else null
	var target := Assets.socket(model, "Muzzle") if is_instance_valid(model) else null
	if not is_instance_valid(model) or not model.is_visible_in_tree() or not source or not target:
		clear_pilot()
		return
	if is_instance_valid(pilot) and pilot.get_parent() != source: clear_pilot()
	if not is_instance_valid(pilot):
		pilot = FlamePilot.new()
		source.add_child(pilot)
	pilot.update_target(target)

func clear_receptor_sparks():
	for sparks in receptor_sparks:
		if is_instance_valid(sparks):
			sparks.hide()
			sparks.queue_free()
	receptor_sparks.clear()
	receptor_gun = null

func update_receptor_sparks():
	var world = robot.arena_match
	var enabled: bool = robot.alive and robot.equipped == "lightning_gun" and robot.loaded >= 1 and world.phase == "Active" and robot.spawn_remaining <= 0 and robot.repair == null
	if world is ArenaMatch and world.replicating and world.authority: enabled = false
	var model := gun() if enabled else null
	if not is_instance_valid(model) or not model.is_visible_in_tree():
		clear_receptor_sparks()
		return
	if receptor_gun and receptor_gun.get_ref() == model: return
	clear_receptor_sparks()
	receptor_gun = weakref(model)
	for id in ["ArcTip1", "ArcTip2", "ArcTip3"]:
		var tip := Assets.socket(model, id)
		if not tip: continue
		var sparks := LightningSparks.new()
		sparks.continuous = true
		tip.add_child(sparks)
		receptor_sparks.append(sparks)

func effects() -> ArenaEffects:
	return robot.arena_match.effects

func gun() -> Node3D:
	var fp = robot.arena_match.first_person
	if robot == robot.arena_match.local_robot and is_instance_valid(fp) and fp.visible and fp.weapon_id == robot.equipped and is_instance_valid(fp.gun):
		return fp.gun
	return robot.gun

func socket(id: String) -> Node3D:
	return Assets.socket(gun(), id)

func muzzle_id() -> String:
	if robot.equipped == "rocket_launcher": return "Muzzle1"
	var names: Array = Arsenal.WEAPONS[robot.equipped].muzzles
	return names[robot.barrel % names.size()]

func origin() -> Vector3:
	var world = robot.arena_match
	if world is ArenaMatch and robot == world.local_robot and world.first_person is FirstPersonRig:
		world.first_person._process(0.0)
	var node := socket(muzzle_id())
	return node.global_position if node else robot.muzzle()

func play_at(clip: String, frame: float, speed := 1.0, loop := false):
	Assets.play(robot.gun, clip, loop, speed)
	var player := Assets.find(robot.gun, "AnimationPlayer") as AnimationPlayer
	if player and player.is_playing():
		player.seek(frame / 30.0, true)
		var skeleton := Assets.find(robot.gun, "Skeleton3D") as Skeleton3D
		if skeleton: skeleton.force_update_all_bone_transforms()

func begin_shot():
	robot.play_event("fire", 0.18)
	# Align accepted gameplay shots to authored events, skipping anticipation only.
	match robot.equipped:
		"pistol": play_at("fire", 3)
		"rifle": play_at("fire_marksman", 3, 3.0) if robot.wants_secondary else play_at("fire", 0, 0.4)
		"minigun": play_at("fire", (robot.barrel % 6) * 6, 1.6)
		"rocket_launcher": play_at("fire", 2, 2.0)
		"lightning_gun": play_at("fire_orb", 3, 1.5)
		"flamethrower": play_at("fire_start", 2, 2.0)
		"emp_gun": play_at("fire", 0, 4.0 / 3.0)
	var fp = robot.arena_match.first_person
	if robot == robot.arena_match.local_robot and is_instance_valid(fp): fp._process(0)

func shot():
	var weapon := robot.equipped
	if weapon == "rifle" and robot.wants_secondary and robot.human and robot.arena_match.uses_first_person(): return
	var muzzle := socket(muzzle_id())
	if weapon == "emp_gun":
		if muzzle: effects().sprite(muzzle.global_position, Color(1, 1, 1, 0.1), 0.24, 0.18, 2)
		for id in ["VentLeft", "VentRight"]: effects().vent(socket(id))
	elif weapon != "flamethrower":
		effects().muzzle(muzzle, weapon)
	if weapon == "pistol":
		for id in ["CompVent", "HookVent"]: effects().vent(socket(id))
	if weapon == "rocket_launcher": effects().vent(socket("Backblast"))
	if weapon in ["pistol", "rifle", "minigun"]:
		effects().shot_smoke(muzzle)
		var delay := 2.0 / 30.0
		if weapon == "rifle": delay = 2.0 / 30.0 / 3.0 if robot.wants_secondary else 1.0 / 30.0 / 0.4
		elif weapon == "minigun": delay = 2.0 / 30.0 / 1.6
		pending.append({"time": delay, "weapon": weapon, "action": func(): effects().casing(socket("ShellEject"))})

func schedule(delay: float, action: Callable):
	pending.append({"time": delay, "weapon": robot.equipped, "action": action})

func _physics_process(dt: float):
	for i in range(pending.size() - 1, -1, -1):
		var event := pending[i]
		if not robot.can_act() or robot.reload_time > 0 or robot.equipped != event.weapon:
			pending.remove_at(i)
			continue
		event.time -= dt
		if event.time <= 0:
			pending.remove_at(i)
			event.action.call()

func _process(dt: float):
	update_receptor_sparks()
	update_pilot()
	contact_time = maxf(0, contact_time - dt)
	if robot.equipped != last_weapon:
		stop_stream()
		last_weapon = robot.equipped
		was_streaming = false
		stream_age = 0
	var animation := Assets.find(robot.gun, "AnimationPlayer") as AnimationPlayer
	if robot.alive and robot.reload_time <= 0 and animation and not animation.is_playing():
		Assets.play(robot.gun, "idle_scoped" if robot.equipped == "rifle" and robot.wants_secondary else "idle", true)
	var active: bool = robot.can_act() and robot.reload_time <= 0 and robot.streaming
	var continuous: bool = robot.equipped in ["flamethrower", "lightning_gun"]
	if continuous and active != was_streaming:
		if active:
			play_at("fire_start", 2 if robot.equipped == "flamethrower" else 3)
		else: play_at("fire_end", 0)
		stream_age = 0
		was_streaming = active
	if active:
		stream_age += dt
		if continuous and stream_age - dt < 0.2 and stream_age >= 0.2: play_at("fire", 0, 2, true)
	if active and continuous:
		if not is_instance_valid(stream): stream = effects().stream("flame" if robot.equipped == "flamethrower" else "lightning")
		if stream:
			var start := origin()
			var end := beam_target
			var robot_contact := false
			if robot.equipped == "flamethrower":
				var segment: Dictionary = robot.arena_match.combat.flame_segment(robot,start)
				end = segment.point
				robot_contact = segment.robot_hit
			stream.update_endpoints(start, end, robot_contact)
	else: stop_stream()
	emit_time -= dt
	if emit_time > 0: return
	emit_time = 0.05
	if robot.alive and robot.equipped == "emp_gun" and robot.cooldown > 0.15:
		effects().vent(socket("AirIntake"), true)
	if not active: return
	if robot.equipped == "flamethrower":
		effects().vent(socket("FumeVent"))
	elif robot.equipped == "lightning_gun":
		var start := origin()
		for id in ["ArcTip1", "ArcTip2", "ArcTip3"]:
			var tip := socket(id)
			if tip: effects().arc(tip.global_position, start + (beam_target - start).normalized() * 0.25, 0.004)
		for id in ["VentLeft", "VentRight"]: effects().vent(socket(id))
		if not beam_hit.is_empty() and contact_time <= 0:
			effects().electric_contact(beam_target, beam_hit.normal)
			contact_time = 0.12
