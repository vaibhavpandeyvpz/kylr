class_name ImpactSparks
extends Node3D
## Shared cosmetic tracers. Jolt sweeps stop each nose at the first surface.
const MAX_PARTICLES := 32
const DIAMETER := 0.01
const MIN_LENGTH := 0.02
const MAX_LENGTH := 0.05
const SPEED := 2.0
const FLIGHT_TIME := 0.5
const SHRINK_TIME := MAX_LENGTH/SPEED
const COUNTS := {&"ballistic":24,&"welding":16,&"flak":20,&"emp":28}
const MATERIAL = preload("res://shaders/combat/particle_spark.gdshader")
static var collision_shape: SphereShape3D
var remaining := 0.0
var elapsed := 0.0
var acceleration := Vector3.DOWN*8.0
var profile: StringName = &"ballistic"
var tracers: Array[Dictionary] = []
var renderer := MultiMeshInstance3D.new()
var query := PhysicsShapeQueryParameters3D.new()

func _init():
	if collision_shape == null:
		collision_shape = SphereShape3D.new()
		collision_shape.radius = DIAMETER*0.5
	query.shape = collision_shape
	query.margin = 0.0
	query.collision_mask = 5 # Solid world and the authored robot hit hulls.
	renderer.multimesh = MultiMesh.new()
	renderer.multimesh.transform_format = MultiMesh.TRANSFORM_3D
	renderer.multimesh.mesh = ProjectileResources.primitive(&"CylinderMesh",{
		"top_radius":DIAMETER*0.5,"bottom_radius":DIAMETER*0.5,
		"height":1.0,"radial_segments":12,"rings":0,
	})
	renderer.multimesh.instance_count = MAX_PARTICLES
	renderer.multimesh.visible_instance_count = 0
	renderer.material_override = ProjectileResources.shader(MATERIAL)
	renderer.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	renderer.custom_aabb = AABB(Vector3.ONE*-1.1,Vector3.ONE*2.2)
	add_child(renderer)
	hide()
	set_physics_process(false)

func fire(point: Vector3, normal: Vector3, _energy: bool, gravity: float, preset: StringName = &"ballistic"):
	profile = preset if COUNTS.has(preset) else &"ballistic"
	global_transform = Transform3D(Basis.IDENTITY,point)
	var orientation := Basis(Quaternion(Vector3.UP,normal.normalized() if normal.length_squared()>0.01 else Vector3.UP))
	var phase := randf()*TAU
	tracers.clear()
	var count: int = COUNTS[profile]
	for index in count:
		# Even spherical petals, rotated per burst, without a forward cone bias.
		var y := 1.0-2.0*(float(index)+0.5)/float(count)
		var radial := sqrt(maxf(0.0,1.0-y*y))
		var angle := phase+float(index)*2.39996323
		var direction := orientation*Vector3(cos(angle)*radial,y,sin(angle)*radial)
		tracers.append({"head":Vector3.ZERO,"direction":direction,"velocity":direction*SPEED,
			"stop_age":-1.0,"length":0.0,"max_length":randf_range(MIN_LENGTH,MAX_LENGTH),
			"path":[Vector3.ZERO],"path_length":0.0})
	acceleration = Vector3.DOWN*maxf(gravity,0.0)
	var bounds := SPEED*FLIGHT_TIME+acceleration.length()*FLIGHT_TIME*FLIGHT_TIME*0.5+MAX_LENGTH+DIAMETER
	renderer.custom_aabb = AABB(Vector3.ONE*-bounds,Vector3.ONE*bounds*2.0)
	elapsed = 0.0
	remaining = FLIGHT_TIME+SHRINK_TIME
	renderer.multimesh.visible_instance_count = 0
	show()
	set_physics_process(true)

func _physics_process(dt: float):
	# Keep swept segments and the short trail faithful to a curved trajectory.
	if dt>1.0/60.0+0.000001:
		var left := dt
		while left>0.0000001:
			var step := minf(left,1.0/60.0)
			_physics_process(step)
			left-=step
		return
	var previous := elapsed
	elapsed += dt
	var space := get_world_3d().direct_space_state
	var visible_count := 0
	for tracer in tracers:
		if tracer.stop_age < 0.0:
			var step := minf(dt,maxf(0.0,FLIGHT_TIME-previous))
			var motion: Vector3 = tracer.velocity*step+acceleration*step*step*0.5
			if step>0.0:
				query.transform = Transform3D(Basis.IDENTITY,global_position+tracer.head)
				query.motion = Vector3.ZERO
				var fraction := 0.0
				if previous>0.0 or space.intersect_shape(query,1).is_empty():
					query.motion = motion
					fraction = space.cast_motion(query)[0]
				tracer.head += motion*fraction
				tracer.velocity += acceleration*step*fraction
				var path: Array = tracer.path
				tracer.path_length += path[-1].distance_to(tracer.head)
				path.append(tracer.head)
				while path.size()>2 and tracer.path_length-path[0].distance_to(path[1])>=tracer.max_length:
					tracer.path_length -= path[0].distance_to(path[1])
					path.pop_front()
				if fraction<1.0: tracer.stop_age = previous+step*fraction
			if elapsed>=FLIGHT_TIME and tracer.stop_age<0.0: tracer.stop_age = FLIGHT_TIME
		var trail_length := minf(tracer.max_length,tracer.path_length)
		if tracer.stop_age>=0.0: trail_length = maxf(0.0,trail_length-(elapsed-tracer.stop_age)*SPEED)
		var tail := tail_position(tracer.path,trail_length)
		var chord: Vector3 = tracer.head-tail
		var length := chord.length()
		tracer.length = length
		if length<=0.000001: continue
		renderer.multimesh.set_instance_transform(visible_count,cylinder_transform(tracer.head,tail))
		visible_count += 1
	renderer.multimesh.visible_instance_count = visible_count
	remaining = maxf(0.0,FLIGHT_TIME+SHRINK_TIME-elapsed) if visible_count>0 or elapsed<=0.0 else 0.0
	if remaining<=0.0:
		hide()
		set_physics_process(false)

func tail_position(path: Array, distance: float) -> Vector3:
	for index in range(path.size()-1,0,-1):
		var segment: float = path[index].distance_to(path[index-1])
		if segment>0.0000001 and distance<=segment:
			return path[index].lerp(path[index-1],distance/segment)
		distance-=segment
	return path[0]

func cylinder_transform(head: Vector3, tail: Vector3) -> Transform3D:
	var chord := head-tail
	var length := chord.length()
	var basis := Basis(Quaternion(Vector3.UP,chord/length))*Basis.from_scale(Vector3(1,length,1))
	return Transform3D(basis,(head+tail)*0.5)
