extends SceneTree

# Render the game's effect classes directly; only camera framing and snapshot
# clocks differ from gameplay. Release each row to bound GPU descriptor usage.
const TILE := Vector2i(420, 320)
const WEAPONS := ["pistol", "rifle", "minigun", "lightning_gun", "emp_gun", "rocket_launcher", "flamethrower"]
const COLUMNS := ["PRIMARY FIRE", "PRIMARY HIT", "SECONDARY FIRE", "SECONDARY HIT", "MUZZLE"]
const OUTPUT := "res://reports/weapon-contact-sheet"

func _initialize() -> void:
	build.call_deferred()

func text_label(viewport: SubViewport, text: String, y: float, size := 18) -> void:
	var label := Label.new()
	label.text = text
	label.position = Vector2(12, y)
	label.add_theme_font_size_override("font_size", size)
	viewport.add_child(label)

func tile(weapon: String, column: int) -> Dictionary:
	var viewport := SubViewport.new()
	viewport.size = TILE
	viewport.own_world_3d = true
	viewport.render_target_update_mode = SubViewport.UPDATE_ALWAYS
	root.add_child(viewport)
	var stage := Node3D.new()
	viewport.add_child(stage)
	var environment := WorldEnvironment.new()
	environment.environment = Environment.new()
	environment.environment.background_mode = Environment.BG_COLOR
	environment.environment.background_color = Color("202934")
	environment.environment.ambient_light_source = Environment.AMBIENT_SOURCE_COLOR
	environment.environment.ambient_light_color = Color.WHITE
	environment.environment.ambient_light_energy = 0.65
	environment.environment.glow_enabled = true
	stage.add_child(environment)
	var light := DirectionalLight3D.new()
	light.rotation_degrees = Vector3(-35, -20, 0)
	light.light_energy = 1.0
	stage.add_child(light)
	var camera := Camera3D.new()
	stage.add_child(camera)
	camera.position = Vector3(0, 0.15, 5)
	camera.look_at(Vector3.ZERO)
	camera.projection = Camera3D.PROJECTION_ORTHOGONAL
	camera.size = 2.6
	camera.current = true
	var effects := ArenaEffects.new()
	stage.add_child(effects)
	effects.rng.seed = 3120
	text_label(viewport, weapon.replace("_", " ").to_upper(), 8)
	text_label(viewport, COLUMNS[column], 33, 15)
	return {"viewport": viewport, "stage": stage, "camera": camera, "effects": effects}

func backdrop(stage: Node3D, stripes := false) -> MeshInstance3D:
	var wall := MeshInstance3D.new()
	var box := BoxMesh.new()
	box.size = Vector3(6, 6, 0.04)
	wall.mesh = box
	wall.position.z = -0.5 if not stripes else -1.8
	wall.material_override = Assets.material(Color("4c5967"))
	stage.add_child(wall)
	if stripes:
		for index in range(-10, 11):
			var stripe := MeshInstance3D.new()
			var mesh := BoxMesh.new()
			mesh.size = Vector3(0.055, 6, 0.03)
			stripe.mesh = mesh
			stripe.position = Vector3(index * 0.24, 0, -1.76)
			stripe.material_override = Assets.material(Color("aab6c4"))
			stage.add_child(stripe)
	return wall

func populate(entry: Dictionary, weapon: String, column: int) -> void:
	var stage: Node3D = entry.stage
	var effects: ArenaEffects = entry.effects
	var camera: Camera3D = entry.camera
	var viewport: SubViewport = entry.viewport
	var note := ""
	if column in [2, 3] and weapon not in ["rifle", "lightning_gun", "flamethrower"]:
		text_label(viewport, "NO SECONDARY FIRE", 150, 24)
		return
	if column == 4:
		var gun := Assets.model("weapons", weapon)
		stage.add_child(gun)
		gun.position.x = 0.55
		gun.rotation.y = -PI / 2
		camera.size = 1.9
		var socket := Assets.socket(gun, "Muzzle1" if weapon in ["minigun", "rocket_launcher"] else "Muzzle")
		if weapon == "emp_gun":
			effects.sprite(socket.global_position, Color(1, 1, 1, 0.1), 0.24, 0.18, 2)
			for id in ["VentLeft", "VentRight"]: effects.vent(Assets.socket(gun, id))
			note = "Faint white pulse + vent puffs"
		elif weapon == "flamethrower":
			var pilot := FlamePilot.new()
			Assets.socket(gun, "PilotFlame").add_child(pilot)
			pilot.update_target(socket)
			pilot.plume.set_process(false)
			var stream := effects.stream("flame")
			stream.update_endpoints(socket.global_position, socket.global_position + Vector3.LEFT * 0.65)
			stream.set_process(false)
			note = "Pilot flame + active nozzle"
		else:
			effects.muzzle(socket, weapon)
			note = {"pistol": "Short flash 02", "rifle": "Flash 02 / scoped TPV shares flash", "minigun": "Wide flash 02 / rotating barrel", "rocket_launcher": "Big flash 02 + backblast", "lightning_gun": "Orb flash + primary prong arcs"}.get(weapon, "")
			if weapon == "rocket_launcher": effects.vent(Assets.socket(gun, "Backblast"))
			if weapon == "lightning_gun":
				for id in ["ArcTip1", "ArcTip2", "ArcTip3"]:
					effects.arc(Assets.socket(gun, id).global_position, socket.global_position + Vector3.LEFT * 0.22, 0.004)
	elif column in [0, 2]:
		if weapon in ["pistol", "rifle", "minigun"]:
			effects.beam(Vector3(1.1, 0, 0), Vector3(-1.1, 0, 0), Color.WHITE, 0.009)
			note = "Scoped hitscan / shared tracer" if column == 2 else "Hitscan / fast travelling tracer"
		elif weapon == "lightning_gun" and column == 0:
			var stream := effects.stream("lightning")
			stream.update_endpoints(Vector3(1, 0, 0), Vector3(-1, 0, 0))
			stream.set_process(false)
			note = "Continuous lightning beam"
		elif weapon == "flamethrower" and column == 0:
			var stream := effects.stream("flame")
			stream.update_endpoints(Vector3(1, 0, 0), Vector3(-1, 0, 0))
			stream.set_process(false)
			note = "Beam VFX 01 / flame-colored stream"
		else:
			var projectile := ArenaProjectile.new()
			projectile.weapon = weapon
			projectile.direction = Vector3.LEFT
			stage.add_child(projectile)
			projectile.set_physics_process(false)
			camera.size = 0.55 if weapon == "emp_gun" else 0.4 if Arsenal.orb_secondary(weapon) else 1.4
			note = "Fire Ball 02 / 10 cm swirl" if weapon == "flamethrower" else "Half-size grey charge" if weapon == "emp_gun" else "10 cm electricity orb" if weapon == "lightning_gun" else "Rocket projectile + Fire VFX 09 thrust"
	else:
		if weapon in ["pistol", "rifle", "minigun"]:
			var wall := backdrop(stage)
			effects.impact(Vector3(0, 0, -0.475), Vector3.BACK, false, wall)
			camera.size = 1.4
			note = "Surface core + sparks + smoke + decal"
		elif weapon == "lightning_gun":
			backdrop(stage)
			effects.electric_contact(Vector3(0, 0, -0.45), Vector3.BACK)
			camera.size = 1.2
			note = "Orb contact / shared curved sparks" if column == 3 else "Beam contact / curved sparks + core"
		elif weapon == "emp_gun":
			backdrop(stage, true)
			effects.emp_contact(Vector3.ZERO, Vector3.UP)
			camera.size = 3.4
			note = "Impact 04 / grey refraction + blur"
		elif weapon == "rocket_launcher":
			backdrop(stage)
			effects.explosion(Vector3.ZERO, Vector3.UP, 1.3, Vector3.DOWN)
			camera.size = 6.0
			note = "Explosion 01 / fire + smoke + rings"
		elif weapon == "flamethrower" and column == 3:
			backdrop(stage)
			effects.fire_contact(Vector3(0, 0, -0.45), Vector3.BACK)
			camera.size = 0.5
			note = "Hit 01 / compact golden contact"
		else:
			backdrop(stage)
			var stream := effects.stream("flame")
			stream.update_endpoints(Vector3(0.9, 0, 0.8), Vector3(0, 0, -0.45))
			stream.set_process(false)
			camera.size = 2.0
			note = "Clipped stream contact / no extra burst"
	text_label(viewport, note, 293, 14)
	# Freeze short-lived CPU geometry at a readable point in its real timeline.
	for node in effects.get_children():
		if node is CombatTransient:
			node._process(0.003 if node.tracer else 0.025)
			node.set_process(false)
		elif node is PackBurst:
			node.set_process(false)
			if column == 4:
				node.effect.set("speed_scale", 0.15)
			else:
				node.effect.get_node("AnimationPlayer").seek(0.24, true)
				node.effect.get_node("AnimationPlayer").pause()
				if node.emp:
					node.remaining = 0.96
					node._process(0)
					node.set_process(false)

func build() -> void:
	DirAccess.make_dir_recursive_absolute(OUTPUT)
	var sheet := Image.create(TILE.x * 5, TILE.y * WEAPONS.size(), false, Image.FORMAT_RGBA8)
	for row in WEAPONS.size():
		var entries: Array[Dictionary] = []
		for column in 5: entries.append(tile(WEAPONS[row], column))
		await create_timer(0.12).timeout
		for column in 5: populate(entries[column], WEAPONS[row], column)
		await create_timer(0.045).timeout
		await RenderingServer.frame_post_draw
		var strip := Image.create(TILE.x * 5, TILE.y, false, Image.FORMAT_RGBA8)
		for column in 5:
			# GPU flashes last only ~85 ms in-game. Slow their playback for
			# this still capture and give emitters time to initialize.
			if column == 4:
				await create_timer(0.15).timeout
				await RenderingServer.frame_post_draw
			var pixels: Image = entries[column].viewport.get_texture().get_image()
			pixels.convert(Image.FORMAT_RGBA8)
			strip.blit_rect(pixels, Rect2i(Vector2i.ZERO, TILE), Vector2i(column * TILE.x, 0))
		strip.save_png(OUTPUT + "/" + WEAPONS[row] + ".png")
		sheet.blit_rect(strip, Rect2i(Vector2i.ZERO, strip.get_size()), Vector2i(0, row * TILE.y))
		for entry in entries: entry.viewport.queue_free()
		await process_frame
		await RenderingServer.frame_post_draw
	sheet.save_png(OUTPUT + "/all-weapons.png")
	print("WEAPON_CONTACT_SHEET_COMPLETE / 7 weapons x 5 effect categories")
	quit()
