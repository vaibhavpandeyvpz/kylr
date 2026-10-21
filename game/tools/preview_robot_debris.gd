extends SceneTree
## Render the real breakup factory against a floor and wall, without match AI.
var stage: ArenaMatch
var directory := "res://reports/robot-debris"

class PreviewMatch extends ArenaMatch:
	func _ready() -> void: pass

class PreviewMap extends ArenaMap:
	func _ready() -> void: config = {"fall_boundary":-50.0}
	func _process(_dt: float) -> void: pass

func _initialize() -> void: run.call_deferred()

func capture(label: String) -> void:
	await RenderingServer.frame_post_draw
	var path := directory.path_join(label + ".png")
	assert(root.get_texture().get_image().save_png(path) == OK)
	print("ROBOT_DEBRIS_CAPTURE ", path)

func run() -> void:
	root.size = Vector2i(1280, 800)
	Engine.max_fps = 60
	AudioServer.set_bus_mute(0, true)
	DirAccess.make_dir_recursive_absolute(directory)
	stage = PreviewMatch.new()
	stage.online = true
	stage.phase = "Active"
	stage.team_colors = [Color("3878b4"), Color("b74740")]
	root.add_child(stage)
	Input.mouse_mode = Input.MOUSE_MODE_VISIBLE
	stage.set_process(false)
	stage.set_physics_process(false)
	stage.set_process_unhandled_input(false)
	stage.map = PreviewMap.new()
	stage.add_child(stage.map)
	stage.combat = ArenaCombat.new(stage)
	stage.audio = ArenaAudio.new()
	stage.audio.game = stage
	stage.add_child(stage.audio)
	stage.effects = ArenaEffects.new()
	stage.add_child(stage.effects)
	var target := ArenaRobot.new()
	target.arena_match = stage
	target.human = true
	stage.add_child(target)
	stage.robots.append(target)
	target.set_process(false)
	target.set_physics_process(false)
	var environment := WorldEnvironment.new()
	environment.environment = Environment.new()
	environment.environment.background_mode = Environment.BG_COLOR
	environment.environment.background_color = Color("1e2630")
	environment.environment.ambient_light_source = Environment.AMBIENT_SOURCE_COLOR
	environment.environment.ambient_light_color = Color.WHITE
	environment.environment.ambient_light_energy = 0.65
	stage.add_child(environment)
	var light := DirectionalLight3D.new()
	light.rotation_degrees = Vector3(-55,-30,0)
	light.shadow_enabled = true
	stage.add_child(light)
	var floor_body := StaticBody3D.new()
	stage.add_child(floor_body)
	floor_body.position.y = -0.15
	var floor_mesh := MeshInstance3D.new()
	var floor_box := BoxMesh.new()
	floor_box.size = Vector3(30,0.3,30)
	floor_mesh.mesh = floor_box
	floor_mesh.material_override = Assets.material(Color("343d45"))
	floor_body.add_child(floor_mesh)
	var floor_shape := CollisionShape3D.new()
	floor_shape.shape = floor_box.create_convex_shape()
	floor_body.add_child(floor_shape)
	var camera := Camera3D.new()
	stage.add_child(camera)
	camera.position = Vector3(-5, 3.6, 7)
	camera.look_at(Vector3(0.5, 0.9, 0))
	camera.fov = 50
	camera.make_current()
	var wall := StaticBody3D.new()
	stage.add_child(wall)
	wall.position = Vector3(3, 1.5, 0)
	var box := BoxMesh.new()
	box.size = Vector3(0.3, 3, 10)
	var mesh := MeshInstance3D.new()
	mesh.mesh = box
	mesh.material_override = Assets.material(Color("475361"))
	wall.add_child(mesh)
	var shape := CollisionShape3D.new()
	shape.shape = box.create_convex_shape()
	wall.add_child(shape)
	for frame in 30: await process_frame
	for weapon: String in RobotDebris.WEAPONS:
		var robot: ArenaRobot = target
		robot.alive = true
		robot.ah = 100
		robot.ep = 0 # No pickup scatter in this presentation-only fixture.
		robot.protection = 0
		robot.spawn_remaining = 0
		robot.sh = 0
		robot.show()
		robot.position = Vector3.ZERO
		robot.body.rotation.y = 0
		robot.velocity = Vector3.ZERO
		robot.pose("idle")
		robot.animator.advance(0)
		robot.gun.hide()
		Assets.paint(robot.body, robot.tint, robot.armor_secondary, robot.head, false, robot.upper_body)
		await capture(weapon + "-intact")
		stage.eliminate(robot, null, weapon, {"point":Vector3(-1, 1, 0), "direction":Vector3.RIGHT, "radial":weapon != "emp_gun"})
		for sample in [{"frames":8, "label":"launch"}, {"frames":22, "label":"flight"}, {"frames":75, "label":"bounce"}, {"frames":105, "label":"settled"}]:
			for frame in sample.frames: await physics_frame
			await capture(weapon + "-" + sample.label)
		stage.tick_drops(4.01)
		await process_frame
	stage.queue_free()
	await process_frame
	quit()
