extends RefCounted
## Diagnostic constraints only. The shipping BT, perception, aiming, movement,
## projectile dodging, physics, damage effects and audio still run normally.
const WEAPONS = ["pistol", "rifle", "minigun", "lightning_gun", "emp_gun", "rocket_launcher", "flamethrower", "flak_cannon", "bio_rifle", "grenade_launcher"]
var game: ArenaMatch
var center := Vector3.ZERO
var clock := 0.0
var camera_started_usec := 0
var orbit_seconds := 12.0
var measured_angle := 0.0
var stats: Array[Dictionary] = []
var lights: Array[Light3D] = []
var measuring := false
var failed := false
var diagnostic_deck := false
var preset_lighting := false

class LockedEquipment extends BotEquipment:
	func tick(_dt: float) -> void:
		suspend_fire = false
	func plan(_urgent: bool) -> bool:
		return false

class BoundedBrain extends ArenaBrain:
	var arena_center := Vector3.ZERO
	var exercise_clock := 0.0
	var combat_jump_requests := 0
	func _init(owner):
		super(owner)
		equipment = LockedEquipment.new(self)
	func commit_goal(destination: Vector3, kind: String) -> bool:
		var bounded := Vector3(clampf(destination.x,arena_center.x-4,arena_center.x+4),arena_center.y,clampf(destination.z,arena_center.z-4,arena_center.z+4))
		return super(bounded,kind)
	func tick(dt: float):
		var jump_before: float=robot.jump_buffer
		super(dt)
		if jump_before<=0 and robot.jump_buffer>0 and target!=null and transition_index<0: combat_jump_requests+=1
		exercise_clock+=dt
		# A short trigger exercise guarantees every assigned gun contributes
		# effects in a brief sample even when a bot's tactical fire policy waits.
		# Aim, movement, BT decisions and normal weapon cadence remain active.
		if fmod(exercise_clock+robot.robot_id*0.13,3.0)<0.75:
			robot.wants_fire=true
			robot.wants_secondary=false
		# Turn inward before reaching the diagnostic perimeter. Preserve native
		# combat weaving and projectile dodges throughout the interior.
		var delta: Vector3 = robot.position-arena_center
		if maxf(absf(delta.x),absf(delta.z))>4.0:
			var local: Vector3 = Basis(Vector3.UP,-robot.yaw)*(-delta*Vector3(1,0,1)).normalized()
			robot.move_input = Vector2(local.x,local.z)

func install(match_node: ArenaMatch, seconds: float, use_preset_lighting := false) -> bool:
	game = match_node
	preset_lighting = use_preset_lighting
	orbit_seconds = maxf(1,seconds-0.2)
	if game.robots.size()!=10 or game.match_type!="DM":
		return reject("Arena stress requires DM and exactly ten robots")
	install_open_deck()
	# Physical perimeter is invisible, outside the usable square; no teleports,
	# no modified map asset and no collision bypass for the ten combatants.
	for axis in 2:
		for sign_value in [-1,1]:
			var wall := StaticBody3D.new()
			wall.collision_layer=1
			wall.collision_mask=2
			var collider := CollisionShape3D.new()
			var box := BoxShape3D.new()
			box.size=Vector3(0.2,8,10.4) if axis==0 else Vector3(10.4,8,0.2)
			collider.shape=box
			wall.add_child(collider)
			game.add_child(wall)
			wall.position=center+Vector3(sign_value*5.1 if axis==0 else 0,4,sign_value*5.1 if axis==1 else 0)
	for index in 10:
		var robot: ArenaRobot = game.robots[index]
		if robot.brain:
			robot.brain.behavior.free()
			robot.brain=null
		robot.human=false
		robot.alive=true
		robot.show()
		robot.spawn_remaining=0
		robot.protection=0
		robot.position=center+Vector3((index%5-2)*1.7,0.05,-2.5 if index<5 else 2.5)
		robot.last_safe=robot.position
		robot.velocity=Vector3.ZERO
		robot.knockback_velocity=Vector3.ZERO
		robot.body.show()
		robot.set_weapon_pose_visible(true)
		robot.reset_inventory()
		robot.pickup_weapon=WEAPONS[index] if index>0 else ""
		robot.equip(WEAPONS[index])
		robot.queued_weapon=""
		robot.ah=1000000
		robot.loaded=10000
		robot.packs=10000
		robot.brain=BoundedBrain.new(robot)
		robot.brain.arena_center=center
		robot.yaw=0 if index>=5 else PI
		robot.bot_aim=Basis(Vector3.UP,robot.yaw)*Vector3.FORWARD
		stats.append({"weapon":WEAPONS[index],"distance_m":0.0,"moving_seconds":0.0,"airborne_seconds":0.0,"stream_seconds":0.0,"direction_changes":0,"last_direction":Vector3.ZERO,"previous":robot.position,"shots_start":0,"shots":0,"hits":0,"bt_updates":0,"bounds_violations":0})
		robot.brain.behavior.updated.connect(record_bt.bind(index))
	game.map.abort_all_repairs("arena_stress")
	game.third_person=true
	game.camera_snap=false
	game.camera_rig.host.set_process(false)
	game.first_person.set_process(false)
	game.first_person.hide()
	game.camera.fov=100
	var listener := AudioListener3D.new()
	game.camera.add_child(listener)
	listener.make_current()
	# Explicit diagnostic GI override, independent of shipping Ultra's GI rule.
	if not preset_lighting:
		for world: WorldEnvironment in game.find_children("*","WorldEnvironment",true,false):
			world.environment.ambient_light_source=Environment.AMBIENT_SOURCE_COLOR
			world.environment.ambient_light_energy=0.26
			world.environment.sdfgi_enabled=true
	install_lighting_rig()
	update_camera(0)
	print("ARENA_STRESS_READY map=",game.map_id," center=",center," bots=10 weapons=10 area=10x10 lighting_requested=",("preset" if preset_lighting else "SDFGI+ambient+fixtures"))
	return true

func install_open_deck() -> void:
	# Both maps share this diagnostic deck. Skyfall uses central higher ground;
	# Faceoff clears the cistern roof by three metres.
	diagnostic_deck=true
	center=Vector3(0,26.02,0)
	if game.map_id=="faceoff":
		var metadata: Dictionary=JSON.parse_string(FileAccess.get_file_as_string("res://assets/models/architecture/cistern/cistern_rig.json"))
		var markers: Array=game.map.markers.filter(func(item): return item.asset=="cistern")
		assert(markers.size()==1,"Faceoff stress requires one cistern")
		center=game.map.world_point(markers[0].position_godot)
		center.y+=float(metadata.bounds_m.hi[2])+3.0+0.02
	# Skyfall retains its authored rooftop+5 m placement. Faceoff alone has
	# the requested diagnostic exception: 20 m instead of in-game 10 m.
	var jumbo: Node3D=game.map.jumbotron.motion.asset
	if game.map_id=="faceoff": jumbo.global_position=game.map.world_point([0,20,0])
	var floor_body := StaticBody3D.new()
	floor_body.name="DiagnosticCombatDeck"
	var shape := BoxShape3D.new()
	shape.size=Vector3(12,0.2,12)
	var collision := CollisionShape3D.new()
	collision.shape=shape
	floor_body.add_child(collision)
	var mesh := MeshInstance3D.new()
	var box := BoxMesh.new()
	box.size=shape.size
	mesh.mesh=box
	mesh.material_override=Assets.regolith_material()
	floor_body.add_child(mesh)
	game.add_child(floor_body)
	floor_body.position=center-Vector3.UP*0.12
	# A separate diagnostic navigation island uses the same route finder and
	# walking rules; native map nodes and transitions are retained intact.
	var traversal: TraversalGraph=game.map.traversal
	for nav in [traversal.graph,traversal.basic_graph]:
		var ids := {}
		for x in range(-4,5):
			for z in range(-4,5):
				var id: int=nav.get_available_point_id()
				nav.add_point(id,center+Vector3(x,0,z))
				ids[Vector2i(x,z)]=id
		for key: Vector2i in ids:
			for offset in [Vector2i(1,0),Vector2i(0,1),Vector2i(1,1),Vector2i(1,-1)]:
				if ids.has(key+offset): nav.connect_points(ids[key],ids[key+offset])
		nav.refresh_portal_metric()

func rig_bar(position: Vector3,size: Vector3) -> void:
	var bar := MeshInstance3D.new()
	var box := BoxMesh.new()
	box.size=size
	bar.mesh=box
	var material := StandardMaterial3D.new()
	material.albedo_color=Color("303942")
	material.metallic=0.8
	material.roughness=0.4
	bar.material_override=material
	game.add_child(bar)
	bar.position=center+position

func native_lamp(asset: String,offset: Vector3,yaw: float) -> void:
	var lamp: Node3D=Assets.model("environments",asset)
	game.add_child(lamp)
	lamp.position=center+offset
	lamp.rotation.y=yaw
	ArchitectureLights.install(lamp,"environments",asset)
	CollisionRig.install(lamp,"environments",asset)
	for light: Light3D in lamp.find_children("*","Light3D",true,false):
		FixtureLighting.configure(light,game.fixture_lighting_enabled if preset_lighting else true,game.fixture_shadows_enabled if preset_lighting else true)
		lights.append(light)

func install_lighting_rig() -> void:
	# Twelve metre overall deck: ten metre combat square, one metre service
	# strip for real pole heads and supported wall/ceiling luminaire mounts.
	for z in [-4.0,4.0]:
		for x in [-5.7,5.7]: rig_bar(Vector3(x,3,z),Vector3(0.18,6,0.18))
		rig_bar(Vector3(0,6,z),Vector3(11.6,0.18,0.22))
		native_lamp("batten_light",Vector3(0,5.89,z),0)
	for offset in [Vector3(-5.6,0,-5.6),Vector3(5.6,0,5.6)]:
		native_lamp("pole_light",offset,atan2(-offset.x,-offset.z))
	for x in [-5.7,5.7]:
		native_lamp("sconce_light",Vector3(x,2.3,-4),PI/2 if x<0 else -PI/2)

func begin_sample() -> void:
	measuring=true
	clock=0
	camera_started_usec=Time.get_ticks_usec()
	measured_angle=0
	for index in 10:
		stats[index].shots_start=game.robots[index].network_shots
		stats[index].bt_updates=0
		stats[index].distance_m=0.0
		stats[index].moving_seconds=0.0
		stats[index].airborne_seconds=0.0
		stats[index].stream_seconds=0.0
		stats[index].direction_changes=0
		stats[index].hits=0
		stats[index].bounds_violations=0
		stats[index]["projectile_dodge_seconds"]=0.0
		game.robots[index].brain.combat_jump_requests=0
		stats[index].previous=game.robots[index].position

func record_bt(_status: int,index: int) -> void:
	if measuring: stats[index].bt_updates+=1

func update_camera(angle: float) -> void:
	var azimuth := -PI/4+angle
	game.camera.global_position=center+Vector3(sin(azimuth)*5,5,cos(azimuth)*5)
	game.camera.look_at(center+Vector3.UP)

func tick(dt: float) -> void:
	if camera_started_usec==0: camera_started_usec=Time.get_ticks_usec()
	# Render coverage follows elapsed time even when physics catch-up is capped.
	# Native bot decisions, movement and weapon cadence still use physics dt.
	clock=(Time.get_ticks_usec()-camera_started_usec)/1000000.0
	update_camera(TAU*clock/orbit_seconds)
	if measuring: measured_angle=TAU*clock/orbit_seconds
	for index in 10:
		var robot: ArenaRobot=game.robots[index]
		if not robot.alive or robot.equipped!=WEAPONS[index]:
			reject("Dead robot or assigned weapon changed")
			return
		var row: Dictionary=stats[index]
		if measuring:
			var delta: Vector3=robot.position-row.previous
			row.distance_m+=delta.length()
			if delta.length()>0.002: row.moving_seconds+=dt
			if not robot.is_on_floor(): row.airborne_seconds+=dt
			if robot.streaming: row.stream_seconds+=dt
			if robot.brain.projectile_dodge.remaining>0: row.projectile_dodge_seconds+=dt
			if delta.length()>0.01:
				if row.last_direction!=Vector3.ZERO and delta.normalized().dot(row.last_direction)<0.5: row.direction_changes+=1
				row.last_direction=delta.normalized()
			if robot.ah<999999: row.hits+=1
			if maxf(absf(robot.position.x-center.x),absf(robot.position.z-center.z))>5.05: row.bounds_violations+=1
		row.previous=robot.position
		row.shots=robot.network_shots-row.shots_start
		robot.ah=1000000
		robot.ep=ArenaTuning.MAX_EP
		robot.loaded=10000
		robot.packs=10000
		robot.queued_weapon=""

func report() -> Dictionary:
	var valid := not failed and measured_angle>=TAU
	var bots: Array = []
	for row in stats:
		valid=valid and (row.shots>0 or row.stream_seconds>0) and row.distance_m>1 and row.bt_updates>0 and row.bounds_violations==0
		var clean: Dictionary=row.duplicate()
		clean["combat_jump_requests"]=game.robots[bots.size()].brain.combat_jump_requests
		for key in ["previous","last_direction","shots_start"]: clean.erase(key)
		bots.append(clean)
	return {"valid":valid,"center":[center.x,center.y,center.z],"area_m":[10,10],"diagnostic_deck":diagnostic_deck,"overall_deck_m":[12,12],"native_lamp_counts":{"pole_light":2,"sconce_light":2,"batten_light":2},"jumbotron_position":str(game.map.jumbotron.motion.asset.global_position),"jumbotron_height_m":game.map.jumbotron.motion.asset.global_position.y,"camera_radius_m":5,"camera_height_m":5,"camera_sweep_degrees":rad_to_deg(measured_angle),"full_map_loaded":true,"preset_lighting":preset_lighting,"gi_override":"authored settings preserved" if preset_lighting else "SDFGI and ambient enabled; RT bounces retained when RT enabled","fixture_lights":lights.size(),"equipment_locked":true,"trigger_exercise":"0.75 s primary trigger every 3 s, staggered per actor; native AI between exercises","resources_replenished_each_tick":true,"bots":bots}

func reject(reason: String) -> bool:
	failed=true
	push_error("ARENA_STRESS_INVALID: "+reason)
	game.get_tree().quit(1)
	return false
