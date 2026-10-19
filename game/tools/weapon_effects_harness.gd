extends ArenaMatch

# Standalone authoring scene. It reuses the real actors, combat, audio and
# effects without the arena assembly, match objectives or bot controllers.
const WEAPONS := ["pistol", "rifle", "minigun", "lightning_gun", "emp_gun", "rocket_launcher", "flamethrower", "flak_cannon", "bio_rifle", "grenade_launcher"]
@export_range(0.1, 30.0, 0.1) var projectile_speed_mps := 1.0
var target: ArenaRobot
var weapon_index := 0
var status: Label
var aim_head := false
var shield_target := false
var side := Vector3.BACK
var hits := 0
var last_damage := 0.0
var automated := false

class TestFloor extends ArenaMap:
	func _ready():
		config = {"fall_boundary": -10.0}
	func _process(_dt): pass

class TestCombat extends ArenaCombat:
	func aim_target(robot, _reach: float) -> Vector3:
		return game.target_aim_point() if robot == game.local_robot else robot.eye() + robot.aim_direction() * _reach

class StationaryTarget extends ArenaRobot:
	func apply_knockback(_impulse: Vector3) -> void: pass
	func hit(amount: float, attacker, cause: String, impulse := Vector3.ZERO) -> bool:
		var accepted := super.hit(amount, attacker, cause, impulse)
		if accepted:
			arena_match.hits += 1
			arena_match.last_damage = amount
		return accepted

func _ready():
	child_entered_tree.connect(configure_projectile)
	third_person = true
	phase = "Active"
	goal = 1000000
	time_limit = INF
	team_colors = [Color("3d8bff"), Color("ff4949")]
	combat = TestCombat.new(self)
	effects = ArenaEffects.new()
	effects.game = self
	add_child(effects)
	audio = ArenaAudio.new()
	audio.game = self
	add_child(audio)
	map = TestFloor.new()
	map.game = self
	add_child(map)
	build_floor()
	camera_rig = ArenaCameraRig.new()
	add_child(camera_rig)
	camera_rig.cameras["tpv"].tween_resource.duration = 0.0
	camera = camera_rig.camera
	local_robot = add_robot(0, "Player Tensor", 0, true, "projector")
	local_robot.tint = team_colors[0]
	Assets.paint(local_robot.body, team_colors[0], team_colors[0], local_robot.head)
	local_robot.listener.make_current()
	target = StationaryTarget.new()
	target.arena_match = self
	target.robot_id = 1
	target.display_name = "Idle target"
	target.human = true # No AI controller; only the player receives input.
	target.team = 1
	target.tint = team_colors[1]
	add_child(target)
	robots.append(target)
	target.set_physics_process(false)
	target.gun.hide()
	target.weapon_pose_visible = false
	for collider in target.gun.find_children("*", "CollisionObject3D", true, false):
		collider.collision_layer = 0
		collider.collision_mask = 0
	reset_positions()
	build_overlay()
	automated = "--harness-smoke" in OS.get_cmdline_user_args()
	if not automated: Input.mouse_mode = Input.MOUSE_MODE_CAPTURED
	update_side_camera()
	if automated: smoke.call_deferred()

func configure_projectile(node: Node) -> void:
	# Every projectile uses this authoring speed, including future weapon types.
	if node is ArenaProjectile: node.speed = projectile_speed_mps

func build_floor() -> void:
	var ground := StaticBody3D.new()
	ground.name = "Ground50x50"
	var collision := CollisionShape3D.new()
	var shape := BoxShape3D.new()
	shape.size = Vector3(50, 0.3, 50)
	collision.shape = shape
	ground.add_child(collision)
	var mesh := MeshInstance3D.new()
	var box := BoxMesh.new()
	box.size = shape.size
	mesh.mesh = box
	mesh.material_override = Assets.material(Color("454d54"))
	ground.add_child(mesh)
	ground.position.y = -0.15
	add_child(ground)
	for axis in 2:
		for index in range(-5, 6):
			var line := MeshInstance3D.new()
			var geometry := BoxMesh.new()
			geometry.size = Vector3(0.025, 0.002, 50) if axis == 0 else Vector3(50, 0.002, 0.025)
			line.mesh = geometry
			line.position = Vector3(index * 5, 0.002, 0) if axis == 0 else Vector3(0, 0.002, index * 5)
			line.material_override = Assets.material(Color("667079"))
			add_child(line)
	var environment := WorldEnvironment.new()
	environment.environment = Environment.new()
	environment.environment.background_mode = Environment.BG_COLOR
	environment.environment.background_color = Color("202934")
	environment.environment.ambient_light_source = Environment.AMBIENT_SOURCE_COLOR
	environment.environment.ambient_light_color = Color.WHITE
	environment.environment.ambient_light_energy = 0.65
	environment.environment.glow_enabled = true
	add_child(environment)
	var sun := DirectionalLight3D.new()
	sun.rotation_degrees = Vector3(-50, -30, 0)
	sun.light_energy = 1.2
	sun.shadow_enabled = true
	add_child(sun)

func build_overlay() -> void:
	var canvas := CanvasLayer.new()
	add_child(canvas)
	var panel := PanelContainer.new()
	panel.position = Vector2(16, 16)
	var style := StyleBoxFlat.new()
	style.bg_color = Color(0.06, 0.09, 0.12, 0.9)
	style.content_margin_left = 14
	style.content_margin_right = 14
	style.content_margin_top = 10
	style.content_margin_bottom = 10
	panel.add_theme_stylebox_override("panel", style)
	canvas.add_child(panel)
	status = Label.new()
	status.add_theme_font_size_override("font_size", 18)
	panel.add_child(status)
	var controls := Label.new()
	controls.text = "WASD move / Ctrl sprint / Shift walk / Space jump\nWheel or 1–7 weapon / LMB primary / RMB secondary\nAuto aim at target / H body-head / T shield / R reset\nEsc release mouse / click to resume / F10 exit"
	controls.position = Vector2(18, 0)
	controls.set_anchors_and_offsets_preset(Control.PRESET_BOTTOM_LEFT)
	controls.offset_left = 18
	controls.offset_top = -108
	controls.offset_bottom = -12
	controls.add_theme_font_size_override("font_size", 17)
	canvas.add_child(controls)

func reset_positions() -> void:
	for node in get_children():
		if node is ArenaProjectile: node.queue_free()
	for robot in robots:
		robot.position = Vector3(10, 0.01, 0) if robot == local_robot else Vector3(0, 0.01, 0)
		robot.velocity = Vector3.ZERO
		robot.knockback_velocity = Vector3.ZERO
		robot.applied_knockback = Vector3.ZERO
		robot.move_input = Vector2.ZERO
		robot.local_motion = Vector2.ZERO
		robot.measured_speed = 0
		robot.animation_lock = 0
		robot.airborne_from_jump = false
		robot.movement_pose.reset()
		robot.wants_fire = false
		robot.wants_secondary = false
		robot.streaming = false
		robot.weapon_vfx.pending.clear()
		robot.weapon_vfx.stop_stream()
		robot.ah = 100
		robot.ep = 100
		robot.contributors.clear()
		robot.contributors.clear()
		robot.alive = true
		robot.protection = 0
		robot.spawn_remaining = 0
		robot.last_safe = robot.position
		robot.pose("idle")
	target.yaw = -PI / 2
	target.body.rotation.y = target.yaw + target.character.forward_yaw
	local_robot.yaw = PI / 2
	local_robot.pitch = 0
	local_robot.previous_yaw = local_robot.yaw
	local_robot.update_aim_pose(0)
	hits = 0
	last_damage = 0
	update_side_camera()

func select_weapon(index: int) -> void:
	weapon_index = posmod(index, WEAPONS.size())
	local_robot.weapon_vfx.pending.clear()
	local_robot.weapon_vfx.stop_stream()
	local_robot.pickup_weapon = "" if weapon_index == 0 else WEAPONS[weapon_index]
	local_robot.equip(WEAPONS[weapon_index])
	local_robot.loaded = Arsenal.WEAPONS[local_robot.equipped].capacity
	local_robot.packs = 99
	local_robot.cooldown = 0
	local_robot.reload_time = 0
	local_robot.stream_time = 0
	local_robot.flame_time = 0

func _unhandled_input(event: InputEvent) -> void:
	if automated: return
	if event is InputEventMouseButton and event.pressed:
		if event.button_index == MOUSE_BUTTON_WHEEL_UP: select_weapon(weapon_index + 1)
		elif event.button_index == MOUSE_BUTTON_WHEEL_DOWN: select_weapon(weapon_index - 1)
		elif event.button_index == MOUSE_BUTTON_LEFT and Input.mouse_mode != Input.MOUSE_MODE_CAPTURED:
			Input.mouse_mode = Input.MOUSE_MODE_CAPTURED
	if event is InputEventKey and event.pressed and not event.echo:
		if event.keycode >= KEY_1 and event.keycode <= KEY_7: select_weapon(event.keycode - KEY_1)
		match event.keycode:
			KEY_ESCAPE: Input.mouse_mode = Input.MOUSE_MODE_VISIBLE
			KEY_F10: get_tree().quit()
			KEY_R: reset_positions()
			KEY_H: aim_head = not aim_head
			KEY_T: shield_target = not shield_target
			KEY_SPACE: local_robot.jump_buffer = ArenaTuning.JUMP_BUFFER

func _physics_process(dt):
	if not is_instance_valid(local_robot) or not is_instance_valid(target): return
	elapsed += dt
	for robot in robots:
		robot.ep = 100
		robot.contributors.clear()
		robot.ah = 100
		robot.protection = 0
		robot.sh = 100 if robot == target and shield_target else 0
		robot.shield_time = 100 if robot.sh > 0 else 0
	local_robot.loaded = Arsenal.WEAPONS[local_robot.equipped].capacity
	local_robot.packs = 99
	if absf(local_robot.position.x) > 24.5 or absf(local_robot.position.z) > 24.5:
		local_robot.position.x = clampf(local_robot.position.x, -24.5, 24.5)
		local_robot.position.z = clampf(local_robot.position.z, -24.5, 24.5)
	if local_robot.position.y < -2: reset_positions()
	var aim: Vector3 = combat.aim_target(local_robot, 100) - local_robot.eye()
	if Vector2(aim.x, aim.z).length() > 0.05:
		local_robot.yaw = atan2(-aim.x, -aim.z)
	local_robot.pitch = atan2(aim.y, Vector2(aim.x, aim.z).length())
	if not automated:
		var active := Input.mouse_mode == Input.MOUSE_MODE_CAPTURED
		local_robot.move_input = Vector2(float(Input.is_physical_key_pressed(KEY_D)) - float(Input.is_physical_key_pressed(KEY_A)), float(Input.is_physical_key_pressed(KEY_S)) - float(Input.is_physical_key_pressed(KEY_W))) if active else Vector2.ZERO
		local_robot.wants_fire = active and Input.is_mouse_button_pressed(MOUSE_BUTTON_LEFT)
		local_robot.wants_secondary = active and Input.is_mouse_button_pressed(MOUSE_BUTTON_RIGHT)
		local_robot.wants_sprint = active and Input.is_physical_key_pressed(KEY_CTRL)
		local_robot.wants_walk = active and Input.is_physical_key_pressed(KEY_SHIFT)

func _process(_dt):
	if not is_instance_valid(local_robot) or not is_instance_valid(target): return
	update_side_camera()
	if status:
		status.text = "WEAPON EFFECTS / 50 × 50 m\n%s  [%d / %d]  •  %.1f m\nProjectiles: %.1f m/s\nAim: %s  /  Shield: %s\nHits: %d  /  Last damage: %.1f  /  Infinite supplies" % [Arsenal.WEAPONS[local_robot.equipped].title, weapon_index + 1, WEAPONS.size(), local_robot.position.distance_to(target.position), projectile_speed_mps, "head" if aim_head else "body", "on" if shield_target else "off", hits, last_damage]

func target_aim_point() -> Vector3:
	if aim_head:
		for shape in target.body.find_children("*", "CollisionShape3D", true, false):
			if shape.get_parent().get_meta("hit_region", "body") == "head":
				return shape.to_global(shape.shape.get_debug_mesh().get_aabb().get_center())
	return target.global_position + Vector3.UP * 1.3

func update_side_camera() -> void:
	if not is_instance_valid(local_robot) or not is_instance_valid(target): return
	var between: Vector3 = local_robot.global_position - target.global_position
	var flat := Vector3(between.x, 0, between.z)
	if flat.length() > 0.75: side = flat.normalized().cross(Vector3.UP)
	var focus: Vector3 = (local_robot.global_position + target.global_position) * 0.5 + Vector3.UP * 1.1
	# Fit separation in the horizontal FOV and jumping in the vertical FOV.
	var aspect := float(get_viewport().get_visible_rect().size.x) / maxf(1, get_viewport().get_visible_rect().size.y)
	var distance := maxf(7, maxf((flat.length() * 0.5 + 2.8) / (tan(deg_to_rad(30)) * aspect), absf(between.y) * 1.1 + 5))
	var point := focus + side * distance + Vector3.UP * distance * 0.3
	var pose := Transform3D(Basis.looking_at(focus - point), point)
	camera_rig.set_gameplay("tpv", pose, 60, true)

func eliminate(victim, _killer, _cause: String):
	# Keep accepted hit reactions and confirmations, without target death or
	# corpse clutter terminating a repeated effects comparison.
	victim.ah = 100
	victim.alive = true

func smoke() -> void:
	for frame in 12: await get_tree().physics_frame
	assert(local_robot.position.distance_to(target.position) >= 9.9)
	var counts: Dictionary = {}
	for index in WEAPONS.size():
		reset_positions()
		select_weapon(index)
		local_robot.wants_fire = true
		var before := hits
		var frames := maxi(105, ceili(12.0 / projectile_speed_mps * 60.0)) if WEAPONS[index] in ["emp_gun", "rocket_launcher"] else 105
		for frame in frames: await get_tree().physics_frame
		local_robot.wants_fire = false
		counts[WEAPONS[index]] = hits - before
		if hits == before:
			push_error("Harness primary produced no accepted hit: " + WEAPONS[index])
			get_tree().quit(1)
			return
	for index in [1, 3, 6]:
		reset_positions()
		select_weapon(index)
		local_robot.wants_secondary = true
		local_robot.wants_fire = index == 1
		var before := hits
		var frames := maxi(105, ceili(12.0 / projectile_speed_mps * 60.0)) if index in [3, 6] else 105
		for frame in frames: await get_tree().physics_frame
		assert(hits > before)
		local_robot.wants_secondary = false
		local_robot.wants_fire = false
	select_weapon(1)
	aim_head = true
	local_robot.wants_fire = true
	local_robot.wants_secondary = true
	for frame in 35: await get_tree().physics_frame
	assert(last_damage == 100)
	aim_head = false
	local_robot.wants_fire = false
	local_robot.wants_secondary = false
	shield_target = true
	select_weapon(0)
	local_robot.wants_fire = true
	for frame in 35: await get_tree().physics_frame
	assert(target.shield_mesh.visible)
	shield_target = false
	local_robot.wants_fire = false
	local_robot.move_input = Vector2(1, 0)
	var start: Vector3 = local_robot.position
	for frame in 30: await get_tree().physics_frame
	assert(local_robot.position.distance_to(start) > 1)
	local_robot.move_input = Vector2.ZERO
	assert(target.position.distance_to(Vector3(0, 0.01, 0)) < 0.001)
	automated = false
	select_weapon(6)
	var wheel := InputEventMouseButton.new()
	wheel.pressed = true
	wheel.button_index = MOUSE_BUTTON_WHEEL_UP
	_unhandled_input(wheel)
	assert(local_robot.equipped == "pistol")
	wheel.button_index = MOUSE_BUTTON_WHEEL_DOWN
	_unhandled_input(wheel)
	assert(local_robot.equipped == "flamethrower")
	automated = true
	for point in [Vector3(24, 0.01, 24), Vector3(-24, 4, -24), Vector3(0.1, 0.01, 0)]:
		local_robot.position = point
		update_side_camera()
		for frame in 3: await get_tree().process_frame
		for robot in robots:
			for height in [0.1, 2.5]:
				var p: Vector3 = robot.global_position + Vector3.UP * height
				assert(not camera.is_position_behind(p))
				var viewport_rect := get_viewport().get_visible_rect()
				if not viewport_rect.grow(-minf(viewport_rect.size.x, viewport_rect.size.y) * 0.04).has_point(camera.unproject_position(p)):
					push_error("Harness framing failed: " + str({"point": p, "screen": camera.unproject_position(p), "viewport": get_viewport().get_visible_rect(), "camera": camera.global_position}))
					get_tree().quit(1)
					return
	reset_positions()
	select_weapon(4)
	for argument in OS.get_cmdline_user_args():
		if argument.begins_with("--harness-preview="):
			var preview_weapon := argument.trim_prefix("--harness-preview=")
			if preview_weapon in WEAPONS:
				select_weapon(WEAPONS.find(preview_weapon))
				local_robot.wants_fire = not "--harness-preview-idle" in OS.get_cmdline_user_args()
				for frame in 30: await get_tree().physics_frame
	for frame in 8: await get_tree().process_frame
	if DisplayServer.get_name() != "headless":
		await RenderingServer.frame_post_draw
		get_viewport().get_texture().get_image().save_png("res://reports/weapon-effects-harness.png")
	print("HARNESS_SMOKE_PASS primary=", JSON.stringify(counts), " secondary=rifle,lightning,flamethrower headshot=true shield=true movement=true wheel=true framing=true")
	var tree := get_tree()
	phase = "Finished"
	for voice in audio.voices: voice.stop()
	await tree.create_timer(0.15).timeout
	# Fixed-FPS headless simulation outruns the audio thread's release queue.
	if DisplayServer.get_name() == "headless": OS.delay_msec(150)
	queue_free()
	tree.quit.call_deferred()
