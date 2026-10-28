extends ArenaMatch
## Staged encounters with gameplay-driven shots, impacts and deaths.
const Preparation = preload("res://scripts/core/resource_preparation.gd")
@export_enum("faceoff","skyfall","ramparts") var cinematic_map := "faceoff"
@export_enum("vista","combat","portal","aftermath","launch","hero","all") var cinematic_shot := "all"
const PLAN_PATH := "res://tools/cinematics/plans.json"
var plans: Dictionary
var active_plan: Dictionary
var stage_frame := Transform3D.IDENTITY
var capture_view: Viewport
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
	plans=JSON.parse_string(FileAccess.get_file_as_string(PLAN_PATH))
	assert(plans.has(map_id))
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
	settings.values.merge(Preferences.QUALITY_PRESETS[2],true)
	settings.values.quality = 2
	settings.apply_rendering(self)
	capture_view=get_viewport()
	assert(is_equal_approx(capture_view.scaling_3d_scale,1.0))
	var portrait: bool=String(options.get("shot",cinematic_shot))=="hero"
	var proof: bool=options.get("preview","0")=="1"
	var size := (Vector2i(640,960) if proof else Vector2i(1280,1920)) if portrait else (Vector2i(1280,720) if proof else Vector2i(1920,1080))
	capture_view=get_viewport()
	var window_size:=Vector2i(640,960) if portrait else size
	get_tree().root.size = window_size
	get_tree().root.content_scale_size = window_size
	if portrait:
		var offscreen:=SubViewport.new()
		offscreen.name="PortraitCapture"
		offscreen.size=size
		offscreen.world_3d=get_world_3d()
		offscreen.msaa_3d=get_viewport().msaa_3d
		offscreen.scaling_3d_scale=1.0
		offscreen.render_target_update_mode=SubViewport.UPDATE_ALWAYS
		add_child(offscreen)
		observer.reparent(offscreen,false)
		observer.make_current()
		capture_view=offscreen
		get_viewport().disable_3d=true
		var layer:=CanvasLayer.new()
		add_child(layer)
		var proof_image:=TextureRect.new()
		proof_image.texture=offscreen.get_texture()
		proof_image.expand_mode=TextureRect.EXPAND_IGNORE_SIZE
		proof_image.stretch_mode=TextureRect.STRETCH_SCALE
		layer.add_child(proof_image)
		proof_image.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	DisplayServer.window_set_vsync_mode(DisplayServer.VSYNC_DISABLED)
	Engine.max_fps = 60
	set_vista()
	run.call_deferred()

func _process(_dt: float) -> void:
	suppress_hit_overlay()

func suppress_hit_overlay() -> void:
	# Presentation-only override. Retain hit_flash for native reaction poses.
	for robot in selected_actors:
		robot.surface_material.set_shader_parameter("hit_strength",0.0)
		for mesh in robot.surface_meshes: mesh.material_overlay=null
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
		var aim: Vector3=stage_frame*MapCatalog.vector(active_plan.aims[index]) if current_shot=="hero" else target.position+Vector3.UP*1.05
		var direction := (aim-robot.eye()).normalized()
		robot.bot_aim=direction
		robot.yaw=atan2(-direction.x,-direction.z)
		robot.pitch=asin(clampf(direction.y,-1,1))
		# Inputs go through the same trigger, animation events and collision paths
		# as play. No projectiles or impact/death effects are placed by this tool.
		robot.wants_fire=take_clock>=.6 and (current_shot=="hero" or target.alive)
		if current_shot=="aftermath" and index>0: robot.wants_fire=false
		robot.wants_secondary=false
		robot.move_input=Vector2.ZERO
		robot.wants_crouch=index in active_plan.get("crouched",[]) or (index==1 and current_shot=="combat")

func set_vista() -> void:
	var plan: Dictionary=plans[map_id].vista
	observer.fov=plan.fov
	observer.attributes.exposure_multiplier=plan.exposure
	observer.position=MapCatalog.vector(plan.camera)
	observer.look_at(MapCatalog.vector(plan.focus))

func clear_ground(robot: ArenaRobot, desired: Vector3) -> Vector3:
	var terrain := map_id=="faceoff" and current_shot!="portal"
	var offsets: Array[Vector3]=[Vector3.ZERO,Vector3(1,0,0),Vector3(-1,0,0),Vector3(0,0,1),Vector3(0,0,-1),Vector3(1,0,1),Vector3(-1,0,-1)]
	if current_shot=="hero":
		for radius in [1.5,2.0,2.5,3.0]:
			for angle in 12:offsets.append(Vector3(cos(TAU*angle/12.0),0,sin(TAU*angle/12.0))*radius)
	for offset in offsets:
		var candidate: Vector3 = desired+offset
		if selected_actors.any(func(other):return Vector2(other.position.x-candidate.x,other.position.z-candidate.z).length()<1.3):continue
		var ray := PhysicsRayQueryParameters3D.create(candidate+Vector3.UP*(4.0 if terrain else 1.2),candidate-Vector3.UP*2,1)
		var hit := get_world_3d().direct_space_state.intersect_ray(ray)
		if hit.is_empty() or hit.normal.y<(.8 if terrain else .9) or absf(hit.position.y-desired.y)>(4.0 if terrain else .65): continue
		candidate=hit.position+Vector3.UP*(.1 if terrain else .03)
		var query := PhysicsShapeQueryParameters3D.new()
		query.shape=robot.body_capsule
		query.transform=Transform3D(Basis.IDENTITY,candidate+Vector3.UP*.86)
		query.collision_mask=1
		if get_world_3d().direct_space_state.intersect_shape(query,1).is_empty(): return candidate
	return Vector3.INF

func plan_encounter(shot: String) -> void:
	current_shot=shot
	active_plan=plans[map_id][shot]
	rng.seed=1347
	selected_actors.clear()
	for robot: ArenaRobot in robots:
		robot.wants_fire=false
		combat.stop_contact(robot)
		robot.hide()
		robot.collision_layer=0
		for body in robot.find_children("*","StaticBody3D",true,false):
			if body.get_meta("robot",null)==robot:body.collision_layer=0
		robot.set_physics_process(false)
		robot.set_process(false)
	stage_frame=Transform3D.IDENTITY
	if active_plan.has("carrier"):
		for section in map.carriers.sections:
			if section.name==active_plan.carrier:stage_frame=MapCarriers.transform_at(elapsed,section)
	observer.attributes.exposure_multiplier=active_plan.exposure
	observer.fov=active_plan.fov
	observer.position=stage_frame*MapCatalog.vector(active_plan.camera)
	camera_focus=stage_frame*MapCatalog.vector(active_plan.focus)
	observer.look_at(camera_focus)
	encounter_center=stage_frame*MapCatalog.vector(active_plan.center)
	if shot=="vista":return
	var loadout: Array=active_plan.weapons
	var available: Array[ArenaRobot]=[]
	for robot: ArenaRobot in robots:
		if robot.alive and robot.spawn_remaining<=0 and robot.protection<=0:available.append(robot)
	for index in mini(loadout.size(),available.size()):
		var robot:=available[index]
		var desired: Vector3=MapCatalog.vector(active_plan.points[index]) if active_plan.has("points") else MapCatalog.vector(active_plan.center)+MapCatalog.vector(active_plan.offsets[index])
		var point:=clear_ground(robot,stage_frame*desired)
		if point==Vector3.INF:
			push_error("No clear authored actor placement: "+map_id+"/"+shot+"/"+str(index))
			get_tree().quit(1)
			return
		robot.position=point
		robot.last_safe=point
		robot.velocity=Vector3.ZERO
		robot.knockback_velocity=Vector3.ZERO
		robot.reset_inventory()
		if loadout[index]!="pistol":robot.take_weapon(loadout[index])
		robot.select_weapon(loadout[index])
		robot.brain=null
		robot.ah=100
		robot.ep=100
		robot.protection=0
		robot.wants_fire=false
		robot.wants_secondary=false
		robot.move_input=Vector2.ZERO
		robot.collision_layer=2
		for body in robot.find_children("*","StaticBody3D",true,false):
			if body.get_meta("robot",null)==robot:body.collision_layer=4
		if active_plan.has("colors"):
			robot.tint=Color(active_plan.colors[index][0])
			robot.armor_secondary=Color(active_plan.colors[index][1])
			Assets.paint(robot.body,robot.tint,robot.armor_secondary,robot.head,false,robot.upper_body)
		restore_weapon_palette(robot)
		robot.set_physics_process(true)
		robot.set_process(true)
		robot.show()
		selected_actors.append(robot)
	assert(selected_actors.size()==loadout.size(),"Encounter needs every authored actor")
	if shot=="aftermath":selected_actors[1].ah=30
	for index in selected_actors.size():
		var robot:=selected_actors[index]
		var aim: Vector3=stage_frame*MapCatalog.vector(active_plan.aims[index]) if shot=="hero" else selected_actors[(index+1)%selected_actors.size()].position+Vector3.UP*1.05
		var direction: Vector3=(aim-robot.eye()).normalized()
		robot.bot_aim=direction
		robot.yaw=atan2(-direction.x,-direction.z)
		robot.pitch=asin(clampf(direction.y,-1,1))
	take_clock=0
	if shot=="hero":
		for attempt in 100:
			if selected_actors.all(func(actor):return actor_in_frame(actor,1.2,.065)):break
			observer.position+=(observer.position-camera_focus).normalized()*.3
		assert(selected_actors.all(func(actor):return actor_in_frame(actor,1.2,.065)),"Hero framing must contain every robot")

func actor_in_frame(robot: ArenaRobot,radius: float,margin: float) -> bool:
	var size:=capture_view.get_visible_rect().size
	var safe:=Rect2(size*margin,size*(1.0-2.0*margin))
	for x in [-radius,radius]:
		for z in [-radius,radius]:
			for y in [0.0,2.2]:
				var point: Vector3=robot.position+Vector3(x,y,z)
				if observer.is_position_behind(point) or not safe.has_point(observer.unproject_position(point)):return false
	return true

func restore_weapon_palette(robot: ArenaRobot) -> void:
	# Preserve runtime metal/glass finishes while restoring the asset's own paint.
	for mesh: MeshInstance3D in robot.gun.find_children("*","MeshInstance3D",true,false):
		for index in mesh.mesh.get_surface_count():
			var authored:=mesh.mesh.surface_get_material(index) as StandardMaterial3D
			var active:=mesh.get_active_material(index) as StandardMaterial3D
			if authored==null or active==null or Assets.material_role(authored.resource_name) not in ["M_Primary","M_Secondary"]:continue
			var restored:=active.duplicate() as StandardMaterial3D
			restored.albedo_color=authored.albedo_color
			mesh.set_surface_override_material(index,restored)

func weapon_palette_is_authored(robot: ArenaRobot) -> bool:
	for mesh: MeshInstance3D in robot.gun.find_children("*","MeshInstance3D",true,false):
		for index in mesh.mesh.get_surface_count():
			var authored:=mesh.mesh.surface_get_material(index) as StandardMaterial3D
			var active:=mesh.get_active_material(index) as StandardMaterial3D
			if authored!=null and active!=null and Assets.material_role(authored.resource_name) in ["M_Primary","M_Secondary"] and not authored.albedo_color.is_equal_approx(active.albedo_color):return false
	return true

func run() -> void:
	var ready: Dictionary=await Preparation.wait_for_rendering(get_tree(),capture_view)
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
		await Preparation.wait_for_rendering(get_tree(),capture_view)
		taking=true
		var capture_at := float(options.get("capture-at",active_plan.capture_at))
		if shot=="vista": capture_at=.2
		while take_clock<capture_at: await get_tree().physics_frame
		taking=false
		# Hold the authoritative instant for readback, including animation/VFX.
		get_tree().paused=true
		suppress_hit_overlay()
		for robot in selected_actors:
			restore_weapon_palette(robot)
			for mesh in robot.surface_meshes: assert(mesh.material_overlay==null)
		assert(is_equal_approx(capture_view.scaling_3d_scale,1.0))
		await RenderingServer.frame_post_draw
		var captured := capture_view.get_texture().get_image()
		var actors: Array=[]
		for robot in selected_actors:
			assert(weapon_palette_is_authored(robot),"Weapon paint must match its authored palette")
			actors.append({"weapon_palette_authored":weapon_palette_is_authored(robot),"id":robot.robot_id,"weapon":robot.equipped,"shots":robot.network_shots,"streaming":robot.streaming,"alive":robot.alive,"ah":robot.ah,"position":robot.position,"head":robot.head,"upper_body":robot.upper_body,"primary":robot.tint.to_html(),"secondary":robot.armor_secondary.to_html()})
		var directory := ProjectSettings.globalize_path(String(options.get("out","res://reports/cinematics/staged")))
		DirAccess.make_dir_recursive_absolute(directory)
		var filename: String=directory+"/"+map_id+"-"+String(shot)+".png"
		assert(captured.save_png(filename)==OK)
		var state := {"map":map_id,"shot":shot,"gameplay_driven_shots":true,"time_scale":speed,"capture_time":take_clock,"match_elapsed":elapsed,"actors":actors,"corpses":corpses.size(),"drops":drops.size(),"camera_position":observer.position,"camera_focus":camera_focus,"plan":active_plan,"gpu":RenderingServer.get_rendering_device().get_device_name(),"quality":"High","hit_overlay":false,"upscaling":false,"internal_scale":capture_view.scaling_3d_scale,"rendering_ready":ready,"path":filename,"size":[captured.get_width(),captured.get_height()]}
		captures.append(state)
		print("CINEMATIC_CAPTURE ",JSON.stringify(state))
		get_tree().paused=false
	var report := ProjectSettings.globalize_path(String(options.get("out","res://reports/cinematics/staged"))+"/"+map_id+"-"+selected+"-metadata.json")
	FileAccess.open(report,FileAccess.WRITE).store_string(JSON.stringify(captures,"  "))
	Engine.time_scale=1
	get_tree().quit()
