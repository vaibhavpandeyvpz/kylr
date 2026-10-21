class_name ArchitectureLift
extends Node
## Native CargoLift clip and occupancy trigger; doors retain their held pose.
var game
var fixture: Dictionary
var metadata: Dictionary
var motion: PropMotion
var surface: Node3D
var trigger: Area3D
var lower := 0.0
var upper := 0.0
var requested := 0.0
var hold := 0.0
var traveling := false
var platform_bounds := AABB()

func install(world,placement: Dictionary,info: Dictionary) -> void:
	game=world;fixture=placement;metadata=info;fixture.node.add_child(self)
	process_physics_priority=-20
	surface=Assets.socket(fixture.node,"LiftSurfaceMount")
	assert(surface!=null,"Cargo lift requires its native moving surface gizmo")
	trigger=CollisionRig.install_trigger(fixture.node,"maps",game.map.config.model,metadata.trigger.object,fixture.asset_suffix+"_col")
	lower=fixture.node.global_position.y+float(info.cargo_lift_m.lower)
	upper=fixture.node.global_position.y+float(info.cargo_lift_m.upper)
	requested=lower
	motion=PropMotion.new();motion.install(fixture.node,false,"CargoLift")
	# Safety must run before sampling the next physical platform pose.
	motion.set_physics_process(false)
	fixture["motion"]=motion;game.map.machinery.append(motion)
	motion.play("lift_down")
	var state: Dictionary=motion.channels.main
	state.time=state.player.get_animation("lift_down").length;motion.sample(state);state.done=true
	var first := true
	for attachment: BoneAttachment3D in fixture.node.find_children("*","BoneAttachment3D",true,false):
		if attachment.bone_name!="CargoLift": continue
		for shape: CollisionShape3D in attachment.find_children("*","CollisionShape3D",true,false):
			var bounds: AABB=surface.global_transform.affine_inverse()*shape.global_transform*shape.shape.get_debug_mesh().get_aabb()
			platform_bounds=bounds if first else platform_bounds.merge(bounds)
			first=false
	assert(not first,"Cargo lift requires its authored physical platform")

func next_displacement(dt: float) -> Vector3:
	var state: Dictionary=motion.channels.main
	var clip: Animation=state.player.get_animation(state.clip)
	for track in clip.get_track_count():
		if clip.track_get_type(track)!=Animation.TYPE_POSITION_3D or String(clip.track_get_path(track)).get_slice(":",1)!="CargoLift": continue
		return fixture.node.global_basis*(clip.position_track_interpolate(track,minf(state.time+dt,clip.length))-clip.position_track_interpolate(track,state.time))
	return Vector3.ZERO

func obstructed(descent: Vector3) -> bool:
	var bounds: AABB=surface.global_transform*platform_bounds
	var swept := bounds.merge(AABB(bounds.position+descent,bounds.size)).grow(0.04)
	for robot: ArenaRobot in game.robots:
		if not robot.alive: continue
		# Riders above the deck are carried normally; any robot underneath,
		# including a protected or airborne one, must never be crushed.
		if robot.global_position.y>=surface.global_position.y-0.05: continue
		var capsule: CapsuleShape3D=robot.body_capsule
		var center: Vector3=robot.body_shape.global_position
		var box := AABB(center-Vector3(capsule.radius,capsule.height*0.5,capsule.radius),Vector3(capsule.radius*2,capsule.height,capsule.radius*2))
		box=box.merge(AABB(box.position+robot.velocity*get_physics_process_delta_time(),box.size))
		if swept.intersects(box): return true
	return false

func reverse_up() -> void:
	var state: Dictionary=motion.channels.main
	var height: float=surface.global_position.y
	var clip: Animation=state.player.get_animation("lift_up")
	# Match the current pose on the reverse clip rather than replaying from
	# the bottom. Both clips use the same native CargoLift translation track.
	var phase := 0.0
	for track in clip.get_track_count():
		if clip.track_get_type(track)!=Animation.TYPE_POSITION_3D or String(clip.track_get_path(track)).get_slice(":",1)!="CargoLift": continue
		var lo := 0.0
		var hi := clip.length
		for iteration in 20:
			var mid := (lo+hi)*0.5
			var y: float=lower+(fixture.node.global_basis*(clip.position_track_interpolate(track,mid)-clip.position_track_interpolate(track,0.0))).y
			if y<height: lo=mid
			else: hi=mid
		phase=(lo+hi)*0.5
	requested=upper
	motion.play("lift_up",false,"",false,"main",phase)
	traveling=true

func request_floor(height: float) -> void:
	requested=lower if absf(height-lower)<absf(height-upper) else upper

func boarding_ready(height: float) -> bool:
	return not traveling and absf(surface.global_position.y-height)<0.15

func waiting_point(robot: ArenaRobot, height: float) -> Vector3:
	var bounds: AABB=surface.global_transform*platform_bounds
	# Wait on the room side of the native platform, clear of its swept footprint.
	var forward: Vector3=fixture.node.global_basis*Vector3.BACK
	forward.y=0
	forward=forward.normalized()
	var extent := absf(forward.x)*bounds.size.x*0.5+absf(forward.z)*bounds.size.z*0.5
	var point := bounds.get_center()+forward*(extent+robot.body_capsule.radius+0.65)
	point.y=height
	return point

func needs_clearance(robot: ArenaRobot, point: Vector3) -> bool:
	var floor_y := lower if absf(point.y-lower)<absf(point.y-upper) else upper
	if absf(point.y-floor_y)>0.6 or boarding_ready(floor_y): return false
	# A rider on the actual deck must remain aboard while it moves.
	if absf(robot.global_position.y-surface.global_position.y)<0.2: return false
	var bounds: AABB=(surface.global_transform*platform_bounds).grow(robot.body_capsule.radius+0.25)
	return point.x>bounds.position.x and point.x<bounds.end.x and point.z>bounds.position.z and point.z<bounds.end.z

func _physics_process(dt: float) -> void:
	if game.phase!="Active":return
	if not game.authority:
		motion.advance(dt)
		return
	if traveling:
		var descent := next_displacement(dt)
		if descent.y<0 and obstructed(descent): reverse_up()
		motion.advance(dt)
		if motion.channels.main.done:traveling=false;hold=2.0
		return
	hold=maxf(0,hold-dt)
	if hold>0:return
	var passengers=trigger.get_overlapping_bodies().filter(func(body):return body is ArenaRobot and body.can_act() and body.is_on_floor())
	if not passengers.is_empty():requested=upper if absf(surface.global_position.y-lower)<.1 else lower
	if absf(surface.global_position.y-requested)<.1:return
	motion.play("lift_up" if requested==upper else "lift_down")
	traveling=true
