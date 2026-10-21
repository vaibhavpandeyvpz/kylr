extends ArenaMatch
## Staged encounters with gameplay-driven shots, impacts and deaths.
const Preparation = preload("res://scripts/core/resource_preparation.gd")
@export_enum("faceoff","skyfall") var cinematic_map := "faceoff"
@export_enum("vista","combat","portal","aftermath","launch","all") var cinematic_shot := "all"
var options: Dictionary = {}
var settings: Preferences
var observer: Camera3D
var selected_actors: Array[ArenaRobot] = []
var encounter_center := Vector3.ZERO
var captures: Array[Dictionary] = []
var current_shot := ""
var taking := false
var camera_focus := Vector3.ZERO
var take_clock := 0.0

func _ready() -> void:
	for arg in OS.get_cmdline_user_args():
		if arg.begins_with("--") and "=" in arg:
			options[arg.get_slice("=",0).trim_prefix("--")] = arg.get_slice("=",1)
	map_id = String(options.get("map",cinematic_map))
	assert(map_id in ["faceoff","skyfall"])
	count = 10
	difficulty = 3
	goal = 999
	time_limit = 1800
	third_person = true
	fixture_lighting_enabled = true
	fixture_shadows_enabled = true
	loading_hold = true
	set_meta("profile_roster_seed",1347)
	await super._ready()
	for robot: ArenaRobot in robots:
		robot.human = false
		robot.brain = null
		robot.body.show()
		robot.gun.show()
	local_robot = null
	first_person.hide()
	first_person.set_process(false)
	camera_rig.host.set_process(false)
	camera.current = false
	observer = Camera3D.new()
	observer.far = 500
	observer.fov = 52
	observer.attributes = CameraAttributesPractical.new()
	observer.attributes.exposure_multiplier = 1.6
	add_child(observer)
	observer.make_current()
	camera = observer
	AudioServer.set_bus_mute(0,true)
	process_priority=100
	settings = Preferences.new("res://reports/cinematic-unused.cfg")
	settings.values = Preferences.DEFAULTS.duplicate(true)
	settings.values.merge(Preferences.QUALITY_PRESETS[3],true)
	settings.values.quality = 3
	settings.values.rt_upscaling = false
	settings.apply_rendering(self)
	assert(is_equal_approx(get_viewport().scaling_3d_scale,1.0))
	var reason := Preferences.ray_tracing_unavailable_reason()
	if not reason.is_empty():
		push_error(reason)
		get_tree().quit(1)
		return
	var size := Vector2i(1280,720) if options.get("preview","0")=="1" else Vector2i(1920,1080)
	get_tree().root.size = size
	get_tree().root.content_scale_size = size
	DisplayServer.window_set_vsync_mode(DisplayServer.VSYNC_DISABLED)
	Engine.max_fps = 60
	set_vista()
	run.call_deferred()

func _process(_dt: float) -> void:
	suppress_hit_overlay()

func suppress_hit_overlay() -> void:
	# Presentation-only override. Retain hit_flash for native reaction poses.
	for robot in selected_actors:
		robot.armor_flash.set_shader_parameter("strength",0.0)
		for mesh in robot.armor_meshes: mesh.material_overlay=null
	for corpse in corpses:
		for mesh in corpse.node.find_children("*","MeshInstance3D",true,false): mesh.material_overlay=null

func _physics_process(dt: float) -> void:
	super._physics_process(dt)
	if not taking: return
	take_clock += dt
	for index in selected_actors.size():
		var robot := selected_actors[index]
		if not robot.alive: continue
		var target := selected_actors[(index+1)%selected_actors.size()]
		var direction := (target.position+Vector3.UP*1.05-robot.eye()).normalized()
		robot.bot_aim=direction
		robot.yaw=atan2(-direction.x,-direction.z)
		robot.pitch=asin(clampf(direction.y,-1,1))
		# Inputs go through the same trigger, animation events and collision paths
		# as play. No projectiles or impact/death effects are placed by this tool.
		robot.wants_fire=take_clock>=.6 and target.alive
		if current_shot=="aftermath" and index>0: robot.wants_fire=false
		robot.wants_secondary=false
		robot.move_input=Vector2.ZERO
		robot.wants_crouch=index==1 and current_shot=="combat"

func set_vista() -> void:
	observer.fov=55
	observer.position=Vector3(58,34,58) if map_id=="faceoff" else Vector3(69,56,72)
	observer.look_at(Vector3(0,1,0) if map_id=="faceoff" else Vector3(0,25,0))

func clear_ground(robot: ArenaRobot, desired: Vector3) -> Vector3:
	var terrain := map_id=="faceoff" and current_shot!="portal"
	for offset in [Vector3.ZERO,Vector3(1,0,0),Vector3(-1,0,0),Vector3(0,0,1),Vector3(0,0,-1),Vector3(1,0,1),Vector3(-1,0,-1)]:
		var candidate: Vector3 = desired+offset
		var ray := PhysicsRayQueryParameters3D.create(candidate+Vector3.UP*(4.0 if terrain else 1.2),candidate-Vector3.UP*2,1)
		var hit := get_world_3d().direct_space_state.intersect_ray(ray)
		if hit.is_empty() or hit.normal.y<(.8 if terrain else .9) or absf(hit.position.y-desired.y)>(4.0 if terrain else .4): continue
		candidate=hit.position+Vector3.UP*(.1 if terrain else .03)
		var query := PhysicsShapeQueryParameters3D.new()
		query.shape=robot.body_capsule
		query.transform=Transform3D(Basis.IDENTITY,candidate+Vector3.UP*.86)
		query.collision_mask=1
		if get_world_3d().direct_space_state.intersect_shape(query,1).is_empty(): return candidate
	return Vector3.INF

func plan_encounter(shot: String) -> void:
	current_shot=shot
	rng.seed=1347
	selected_actors.clear()
	for robot: ArenaRobot in robots:
		robot.wants_fire=false
		combat.stop_contact(robot)
		robot.hide()
		robot.set_physics_process(false)
		robot.set_process(false)
	observer.attributes.exposure_multiplier=1.6
	observer.fov=52
	if shot=="vista":
		set_vista()
		return
	var loadout: Array = []
	match shot:
		"combat":
			encounter_center=Vector3(20,0,-12) if map_id=="faceoff" else Vector3(-1,22,-22.5)
			loadout=["rifle","flak_cannon","grenade_launcher"] if map_id=="faceoff" else ["rocket_launcher","emp_gun","rifle"]
		"portal":
			encounter_center=Vector3(1,.078,-2) if map_id=="faceoff" else Vector3(30,22,22.5)
			loadout=["lightning_gun","emp_gun"]
		"aftermath":
			encounter_center=Vector3(17,0,0) if map_id=="faceoff" else Vector3(25.5,30.1,27)
			loadout=["minigun","pistol","grenade_launcher"]
			observer.attributes.exposure_multiplier=1.15 if map_id=="faceoff" else 1.6
		"launch":
			encounter_center=Vector3(-15.5,0,11) if map_id=="faceoff" else Vector3(21,22,16.5)
			loadout=["flamethrower","bio_rifle","pistol"]
	var available: Array[ArenaRobot]=[]
	for robot: ArenaRobot in robots:
		if robot.alive and robot.spawn_remaining<=0 and robot.protection<=0: available.append(robot)
	var offsets := [Vector3(0,0,-2.4),Vector3(0,0,2.4),Vector3(3,0,0)]
	if shot=="combat" and map_id=="skyfall": offsets=[Vector3(-3,0,0),Vector3(3,0,0),Vector3(0,0,.4)]
	if shot=="portal": offsets=[Vector3(1,0,1.6),Vector3(-2,0,-1.2)]
	if shot=="portal" and map_id=="faceoff": offsets=[Vector3(-4.5,0,-1),Vector3(-4.5,0,2.8)]
	if shot=="launch": offsets=[Vector3(3,0,-1.5),Vector3(-3,0,-1.2),Vector3(0,0,2.4)]
	for index in mini(loadout.size(),available.size()):
		var robot := available[index]
		var point := clear_ground(robot,encounter_center+offsets[index])
		if point==Vector3.INF: continue
		# Set the encounter state; weapon simulation owns the resulting shots,
		# projectile trajectories, impacts, damage and deaths.
		robot.position=point
		robot.last_safe=point
		robot.velocity=Vector3.ZERO
		robot.knockback_velocity=Vector3.ZERO
		robot.reset_inventory()
		if loadout[index]!="pistol": robot.take_weapon(loadout[index])
		robot.select_weapon(loadout[index])
		robot.brain=null
		robot.ah=100
		robot.ep=100
		robot.protection=0
		robot.wants_fire=false
		robot.wants_secondary=false
		robot.move_input=Vector2.ZERO
		robot.set_physics_process(true)
		robot.set_process(true)
		robot.show()
		selected_actors.append(robot)
	assert(selected_actors.size()>=2,"Encounter needs two clear actor placements")
	if shot=="aftermath": selected_actors[1].ah=30
	if map_id=="faceoff" and shot!="portal":
		encounter_center.y=0
		for robot in selected_actors:encounter_center.y+=robot.position.y/selected_actors.size()
	camera_focus=encounter_center+Vector3.UP*.95
	if shot=="portal" and map_id=="faceoff": camera_focus=Vector3(-1.5,1.0,-1.8)
	if map_id=="faceoff":
		match shot:
			"combat": observer.position=encounter_center+Vector3(-7,2.4,5)
			"portal": observer.position=Vector3(4.6,1.5,1.2)
			"aftermath": observer.position=encounter_center+Vector3(7,2.4,4.5)
			"launch": observer.position=encounter_center+Vector3(-6,2.3,5.5)
	else:
		match shot:
			"combat": observer.position=encounter_center+Vector3(2,2.5,8)
			"portal": observer.position=Vector3(37.5,24.1,29)
			"aftermath": observer.position=encounter_center+Vector3(-6,2.5,6)
			"launch": observer.position=encounter_center+Vector3(0,2.4,-8)
	observer.look_at(camera_focus)
	for index in selected_actors.size():
		var robot := selected_actors[index]
		var direction := (selected_actors[(index+1)%selected_actors.size()].position+Vector3.UP*1.05-robot.eye()).normalized()
		robot.bot_aim=direction
		robot.yaw=atan2(-direction.x,-direction.z)
		robot.pitch=asin(clampf(direction.y,-1,1))
	take_clock=0

func run() -> void:
	var ready: Dictionary=await Preparation.wait_for_rendering(get_tree(),get_viewport(),true)
	assert(ready.get("ready",false))
	loading_hold=false
	while phase!="Active": await get_tree().physics_frame
	var shots := ["vista","combat","portal","aftermath","launch"]
	var selected := String(options.get("shot",cinematic_shot))
	if selected!="all": shots=[selected]
	var speed := clampf(float(options.get("speed",.1)),.01,1.0)
	Engine.time_scale=speed
	for shot in shots:
		plan_encounter(shot)
		# Settle the fixed view before firing; time remains slowed throughout.
		await Preparation.wait_for_rendering(get_tree(),get_viewport(),true)
		taking=true
		var capture_at := float(options.get("capture-at",2.0 if shot=="aftermath" else .95))
		if shot=="vista": capture_at=.2
		while take_clock<capture_at: await get_tree().physics_frame
		taking=false
		# Hold the authoritative instant for readback, including animation/VFX.
		get_tree().paused=true
		suppress_hit_overlay()
		for robot in selected_actors:
			for mesh in robot.armor_meshes: assert(mesh.material_overlay==null)
		assert(is_equal_approx(get_viewport().scaling_3d_scale,1.0))
		await RenderingServer.frame_post_draw
		var captured := get_viewport().get_texture().get_image()
		var actors: Array=[]
		for robot in selected_actors:
			actors.append({"id":robot.robot_id,"weapon":robot.equipped,"shots":robot.network_shots,"alive":robot.alive,"ah":robot.ah,"position":robot.position})
		var directory := ProjectSettings.globalize_path(String(options.get("out","res://reports/cinematics/staged")))
		DirAccess.make_dir_recursive_absolute(directory)
		var filename: String=directory+"/"+map_id+"-"+String(shot)+".png"
		assert(captured.save_png(filename)==OK)
		var state := {"map":map_id,"shot":shot,"gameplay_driven_shots":true,"time_scale":speed,"capture_time":take_clock,"match_elapsed":elapsed,"actors":actors,"corpses":corpses.size(),"drops":drops.size(),"camera_position":observer.position,"gpu":RenderingServer.get_rendering_device().get_device_name(),"quality":"Ultra","hit_overlay":false,"upscaling":false,"internal_scale":get_viewport().scaling_3d_scale,"rt_ready":ready,"path":filename,"size":[captured.get_width(),captured.get_height()]}
		captures.append(state)
		print("CINEMATIC_CAPTURE ",JSON.stringify(state))
		get_tree().paused=false
	var report := ProjectSettings.globalize_path("res://reports/cinematics/"+map_id+"-staged.json")
	FileAccess.open(report,FileAccess.WRITE).store_string(JSON.stringify(captures,"  "))
	Engine.time_scale=1
	get_tree().quit()
