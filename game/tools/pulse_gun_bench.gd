extends "res://tools/weapon_effects_harness.gd"
## Manual fixture bench; native aiming, projectile, collision and impact path.
var fixture: Node3D
var pulse: PulseGunController
var shots := 0
var last_action := "Ready"
var orbit_yaw := 0.8
var orbit_pitch := 0.28
var orbit_distance := 11.5
var orbit_focus := Vector3(0,0.7,-5)
var dragging := false

class CenterTarget extends StationaryTarget:
	var center_local := Vector3(0,1.3,0)
	# The native controller asks for eye(); this fixture targets body center.
	func eye() -> Vector3:
		return to_global(center_local)

func _ready() -> void:
	match_type = "TDM"
	phase = "Active"
	third_person = true
	rng.randomize()
	team_colors = [Color("38b6e8"),Color("e76b42")]
	combat = ArenaCombat.new(self)
	effects = ArenaEffects.new()
	effects.game = self
	add_child(effects)
	audio = ArenaAudio.new()
	audio.game = self
	add_child(audio)
	map = TestFloor.new()
	map.game = self
	add_child(map)
	map.config = {"fall_boundary":-10.0,"pulse_gun":MapCatalog.find("faceoff").pulse_gun.duplicate(true)}
	map.config.pulse_gun["projectile_speed"] = 1.0
	map.config.pulse_gun["projectile_lifetime"] = 12.0
	build_floor()
	camera = Camera3D.new()
	camera.fov = 60
	add_child(camera)
	camera.make_current()
	var listener := AudioListener3D.new()
	camera.add_child(listener)
	listener.make_current()
	fixture = Assets.model("gameplay","pulse_gun")
	add_child(fixture)
	fixture.rotation.y = PI
	CollisionRig.install(fixture,"gameplay","pulse_gun")
	ArchitectureLights.install(fixture,"gameplay","pulse_gun")
	pulse = PulseGunController.new()
	pulse.install(fixture,self,0)
	pulse.set_physics_process(false)
	random_target()
	build_bench_overlay()
	update_camera()
	Input.mouse_mode = Input.MOUSE_MODE_VISIBLE
	automated = "--pulse-bench-smoke" in OS.get_cmdline_user_args()
	if automated: bench_smoke.call_deferred()

func random_target() -> void:
	for child in get_children():
		if child is BallisticProjectile: child.queue_free()
	robots.clear()
	if is_instance_valid(target): target.free()
	var character := ContentRegistry.character("tensor")
	target = CenterTarget.new()
	target.arena_match = self
	target.robot_id = 1
	target.display_name = "Pulse target"
	target.team = 1
	target.human = true
	target.head = character.heads[rng.randi_range(0,character.heads.size()-1)]
	target.upper_body = character.upper_bodies[rng.randi_range(0,character.upper_bodies.size()-1)]
	target.tint = Color.from_hsv(rng.randf(),0.6,0.8)
	add_child(target)
	robots.append(target)
	target.set_physics_process(false)
	target.position = Vector3(0,0.01,-10)
	target.yaw = PI
	target.body.rotation.y = target.yaw+target.character.forward_yaw
	target.weapon_pose_visible = false
	target.gun.hide()
	for collider in target.gun.find_children("*","CollisionObject3D",true,false):
		collider.collision_layer = 0
		collider.collision_mask = 0
	target.pose("idle")
	target.set_weapon_pose_visible(false)
	target.update_aim_pose(0)
	var spine := target.skeleton.find_bone("Spine")
	if spine>=0:
		target.center_local = target.to_local(target.skeleton.global_transform*target.skeleton.get_bone_global_pose(spine).origin)
	# Fit muzzle-to-center distance, including height and the moving barrel.
	for iteration in 5:
		aim_only()
		var origin := Assets.socket_world_transform(pulse.muzzle).origin
		var center := target.eye()
		var vertical := center.y-origin.y
		target.position += Vector3(origin.x-center.x,0,origin.z-sqrt(maxf(0,100.0-vertical*vertical))-center.z)
	aim_only()
	pulse.cooldown = 0
	hits = 0
	shots = 0
	last_action = "Ready"

func aim_only() -> void:
	var previous := pulse.cooldown
	pulse.cooldown = INF
	pulse._physics_process(0)
	pulse.cooldown = previous

func fire_once() -> bool:
	if pulse.cooldown>0:
		last_action = "Cooling down"
		return false
	target.ah = 100
	pulse._physics_process(0)
	if pulse.cooldown<=0:
		last_action = "Aim blocked"
		return false
	shots += 1
	last_action = "Pulse fired"
	return true

func _physics_process(dt: float) -> void:
	elapsed += dt
	if not is_instance_valid(pulse) or not is_instance_valid(target): return
	pulse.cooldown = maxf(0,pulse.cooldown-dt)
	target.ah = 100
	target.ep = 100
	target.protection = 0
	target.sh = 0
	target.hit_flash = maxf(0,target.hit_flash-dt)
	target.slow_remaining = maxf(0,target.slow_remaining-dt)
	target.update_aim_pose(dt)

func _process(_dt: float) -> void:
	if not is_instance_valid(target) or status==null: return
	var distance := Assets.socket_world_transform(pulse.muzzle).origin.distance_to(target.eye())
	status.text = "PULSE GUN BENCH  /  %.2f m\n%s head  /  %s upper body\nShots: %d  /  Hits: %d  /  Cooldown: %.2f s\n%s" % [distance,target.head,target.upper_body,shots,hits,pulse.cooldown,last_action]

func _unhandled_input(event: InputEvent) -> void:
	if event is InputEventMouseButton:
		if event.button_index==MOUSE_BUTTON_LEFT and event.pressed: fire_once()
		elif event.button_index==MOUSE_BUTTON_RIGHT: dragging = event.pressed
		elif event.pressed and event.button_index in [MOUSE_BUTTON_WHEEL_UP,MOUSE_BUTTON_WHEEL_DOWN]:
			orbit_distance = clampf(orbit_distance*(0.9 if event.button_index==MOUSE_BUTTON_WHEEL_UP else 1.1),0.7,30)
			update_camera()
	elif event is InputEventMouseMotion and dragging:
		orbit_yaw -= event.relative.x*0.006
		orbit_pitch = clampf(orbit_pitch+event.relative.y*0.006,-0.05,1.35)
		update_camera()
	elif event is InputEventKey and event.pressed and not event.echo:
		match event.keycode:
			KEY_R: random_target()
			KEY_1:
				orbit_focus = Vector3(0,0.7,-5)
				orbit_distance = 11.5
				orbit_yaw = 0.8
				orbit_pitch = 0.28
			KEY_2:
				orbit_focus = fixture.global_position+Vector3.UP*0.45
				orbit_distance = 1.8
			KEY_3:
				orbit_focus = target.eye()
				orbit_distance = 2.7
			KEY_ESCAPE, KEY_F10: get_tree().quit()
		update_camera()

func update_camera() -> void:
	var offset := Vector3(sin(orbit_yaw)*cos(orbit_pitch),sin(orbit_pitch),cos(orbit_yaw)*cos(orbit_pitch))*orbit_distance
	camera.position = orbit_focus+offset
	camera.look_at(orbit_focus)

func build_bench_overlay() -> void:
	build_overlay()
	var canvas := status.get_parent().get_parent()
	var controls: Label = canvas.get_child(1)
	controls.text = "LMB: one pulse  /  R: random target\nRMB drag: orbit  /  Wheel: zoom\n1: overview  /  2: gun  /  3: target  /  Esc: exit"
	controls.offset_top = -82

func bench_smoke() -> void:
	for frame in 75: await get_tree().physics_frame
	assert(shots==0 and hits==0,"The fixture must never fire automatically")
	assert(absf(Assets.socket_world_transform(pulse.muzzle).origin.distance_to(target.eye())-10.0)<0.01)
	await save_bench_preview("overview")
	var click := InputEventMouseButton.new()
	click.button_index = MOUSE_BUTTON_LEFT
	click.pressed = true
	_unhandled_input(click)
	assert(shots==1,"A left mouse press fires one pulse")
	for child in get_children():
		if child is BallisticProjectile:
			assert(is_equal_approx(child.velocity.length(),1.0),"Bench pulses travel at 1 m/s")
	assert(not fire_once(),"The native one-second cooldown remains active")
	for frame in 12: await get_tree().physics_frame
	for child in get_children():
		if child is BallisticProjectile and is_instance_valid(child.visual):
			orbit_focus = child.global_position
			orbit_distance = 0.7
			update_camera()
	await save_bench_preview("flight")
	for frame in 24: await get_tree().physics_frame
	for child in get_children():
		if child is BallisticProjectile and is_instance_valid(child.visual):
			assert(is_equal_approx(child.visual.length_m,0.25))
			orbit_focus = child.global_position
			update_camera()
	await save_bench_preview("full-tracer")
	orbit_focus = target.eye()
	orbit_distance = 2.7
	update_camera()
	for frame in 660:
		await get_tree().physics_frame
		if hits==1: break
	for frame in 3: await get_tree().physics_frame
	await save_bench_preview("hit")
	for frame in 6: await get_tree().physics_frame
	await save_bench_preview("absorption")
	assert(shots==1 and hits==1,"A manual pulse must hit the target center once")
	for frame in 75: await get_tree().physics_frame
	assert(shots==1 and hits==1,"Holding time must not repeat a shot")
	var previous := target
	random_target()
	assert(not is_instance_valid(previous) and target.head in ContentRegistry.character("tensor").heads)
	for frame in 4: await get_tree().physics_frame
	assert(fire_once())
	for frame in 660: await get_tree().physics_frame
	assert(hits==1)
	print("PULSE_BENCH_SMOKE_PASS distance=",Assets.socket_world_transform(pulse.muzzle).origin.distance_to(target.eye())," shots=",shots," hits=",hits)
	get_tree().quit()

func save_bench_preview(label: String) -> void:
	if DisplayServer.get_name()=="headless": return
	await RenderingServer.frame_post_draw
	DirAccess.make_dir_recursive_absolute("res://reports/pulse-bench")
	assert(get_viewport().get_texture().get_image().save_png("res://reports/pulse-bench/"+label+".png")==OK)
