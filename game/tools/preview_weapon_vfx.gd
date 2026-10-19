extends SceneTree

var stage: Node3D
var effects: ArenaEffects
var guns: Array[Node3D] = []
var weapons := ["pistol", "rifle", "minigun", "rocket_launcher", "lightning_gun", "flamethrower", "emp_gun"]

func _initialize():
	call_deferred("build")

func build():
	stage = Node3D.new()
	root.add_child(stage)
	var environment := WorldEnvironment.new()
	environment.environment = Environment.new()
	environment.environment.background_mode = Environment.BG_COLOR
	environment.environment.background_color = Color("17202b")
	environment.environment.ambient_light_source = Environment.AMBIENT_SOURCE_COLOR
	environment.environment.ambient_light_color = Color("d5e4ff")
	environment.environment.ambient_light_energy = 0.7
	environment.environment.glow_enabled = true
	stage.add_child(environment)
	var light := DirectionalLight3D.new()
	stage.add_child(light)
	light.rotation_degrees = Vector3(-35, -25, 0)
	light.light_energy = 1.6
	var camera := Camera3D.new()
	stage.add_child(camera)
	camera.position = Vector3(0, 0, 7)
	camera.projection = Camera3D.PROJECTION_ORTHOGONAL
	camera.size = 5.0
	camera.current = true
	effects = ArenaEffects.new()
	stage.add_child(effects)
	for i in weapons.size():
		var gun := Assets.model("weapons", weapons[i])
		stage.add_child(gun)
		gun.position = Vector3((i % 3 - 1) * 2.7 + 0.25, 1.5 - (i / 3) * 1.5, 0)
		gun.rotation.y = -PI / 2
		guns.append(gun)
		var label := Label3D.new()
		stage.add_child(label)
		label.text = weapons[i].replace("_", " ").to_upper()
		label.font_size = 36
		label.pixel_size = 0.004
		label.position = gun.position + Vector3(-0.3, -0.36, 0)
	await create_timer(1.0).timeout
	for i in weapons.size():
		var gun := guns[i]
		var weapon: String = weapons[i]
		var socket := Assets.socket(gun, "Muzzle1" if weapon in ["minigun", "rocket_launcher"] else "Muzzle")
		if weapon == "flamethrower":
			effects.muzzle(Assets.socket(gun, "PilotFlame"), weapon, 0.045)
			effects.flame(socket.global_position, -socket.global_basis.z, 1.5)
		elif weapon == "lightning_gun":
			var beam := effects.stream("lightning")
			beam.update_endpoints(socket.global_position, socket.global_position + Vector3.LEFT * 1.0)
			for id in ["ArcTip1", "ArcTip2", "ArcTip3"]:
				effects.arc(Assets.socket(gun, id).global_position, socket.global_position + Vector3.LEFT * 0.15, 0.004)
		elif weapon == "emp_gun":
			var pulse := ArenaProjectile.new()
			pulse.weapon = weapon
			pulse.direction = -socket.global_basis.z.normalized()
			stage.add_child(pulse)
			pulse.set_physics_process(false)
			pulse.speed = 20.0
			pulse.distance = 1.0
			pulse.position = socket.global_position + pulse.direction * pulse.distance
			pulse.update_emp_visual()
		else: effects.muzzle(socket, weapon)
		if weapon in ["pistol", "rifle", "minigun"]:
			effects.shot_smoke(socket)
			effects.casing(Assets.socket(gun, "ShellEject"))
		if weapon == "emp_gun":
			effects.emp_contact(socket.global_position + Vector3.LEFT * 1.0, Vector3.RIGHT)
			effects.emp_pool[-1].set_process(false)
			effects.emp_pool[-1].effect.get_node("AnimationPlayer").seek(0.2, true)
			effects.emp_pool[-1].remaining = 0.96
			effects.emp_pool[-1]._process(0.0)
		else:
			effects.impact(socket.global_position + Vector3.LEFT * 1.0, Vector3.RIGHT, weapon == "lightning_gun")
	effects.explosion(Vector3(0, -1.3, 0), Vector3.UP, 0.65, Vector3(1, -1, 0).normalized())
	for child in effects.get_children():
		if child is CombatTransient and child.progress_parameter == "effect_progress": child._process(0.12)
		elif child is CombatTransient and child.align_velocity: child._process(0.04)
	var shell := Assets.sphere(stage, 0.4, Color("79c8ff"))
	shell.position = Vector3(2.7, -1.3, 0)
	var shield_material := ShaderMaterial.new()
	shield_material.shader = preload("res://shaders/shield.gdshader")
	shield_material.set_shader_parameter("hit_progress", 0.28)
	shield_material.set_shader_parameter("hit_direction", Vector3.BACK)
	shell.material_override = shield_material
	for entry in [["ROCKET IMPACT", 0.0], ["SHIELD RESPONSE", 2.7]]:
		var label := Label3D.new()
		stage.add_child(label)
		label.text = entry[0]
		label.font_size = 36
		label.pixel_size = 0.004
		label.position = Vector3(entry[1], -1.86, 0)
	await create_timer(0.025).timeout
	await RenderingServer.frame_post_draw
	DirAccess.make_dir_recursive_absolute("res://reports")
	root.get_texture().get_image().save_png("res://reports/weapon-vfx.png")
	stage.queue_free()
	await process_frame
	quit()
