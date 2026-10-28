class_name LavaDeathBubbles
extends MultiMeshInstance3D
## One bounded, GPU-animated bubble batch per sinking robot.

var game: ArenaMatch
var settings: Dictionary
var bubbles: Array[Dictionary] = []
var bubble_material: ShaderMaterial

static func attach(world: ArenaMatch, corpse: Node3D, recipe: Dictionary) -> void:
	if corpse.has_node("LavaDeathBubbles") or world.map.lava == null: return
	if world.replicating and world.authority and DisplayServer.get_name() == "headless": return
	var effect := LavaDeathBubbles.new()
	effect.name = "LavaDeathBubbles"
	corpse.add_child(effect)
	effect.top_level = true
	effect.global_position = corpse.get_meta("lava_origin")
	effect.configure(world, recipe)

func configure(world: ArenaMatch, recipe: Dictionary) -> void:
	game = world
	settings = recipe
	var random := RandomNumberGenerator.new()
	random.seed = int(recipe.seed)
	var count := random.randi_range(20,25)
	var lava := game.map.lava
	var local := lava.to_local(global_position)
	var center := Vector2(local.x,local.z)
	var polygon := PackedVector2Array()
	for pit in lava.pits:
		if Geometry2D.is_point_in_polygon(center,pit.polygon):
			polygon = pit.polygon
			break
	if polygon.is_empty(): return
	var fallback := center
	var triangles := Geometry2D.triangulate_polygon(polygon)
	for index in range(0,triangles.size(),3):
		var triangle := PackedVector2Array([polygon[triangles[index]],polygon[triangles[index+1]],polygon[triangles[index+2]]])
		if Geometry2D.is_point_in_polygon(center,triangle):
			var centroid := (triangle[0]+triangle[1]+triangle[2])/3.0
			fallback = center.move_toward(centroid,0.25)
			break
	var mesh := SphereMesh.new()
	mesh.radius = 1.0; mesh.height = 2.0
	mesh.radial_segments = 12; mesh.rings = 6
	multimesh = MultiMesh.new()
	multimesh.transform_format = MultiMesh.TRANSFORM_3D
	multimesh.use_custom_data = true
	multimesh.mesh = mesh
	multimesh.instance_count = count * 4
	for index in count:
		var radius := random.randf_range(LavaSurface.MIN_BUBBLE_RADIUS,LavaSurface.MAX_BUBBLE_RADIUS)
		var point := fallback
		var found := false
		for attempt in 64:
			var angle := random.randf() * TAU
			var distance := sqrt(random.randf()) * 1.6
			var candidate := center + Vector2(cos(angle),sin(angle)) * distance
			if Geometry2D.is_point_in_polygon(candidate,polygon) and edge_distance(candidate,polygon) > radius:
				point = candidate; found = true
				break
		if not found: radius = minf(radius,edge_distance(point,polygon)*0.8)
		var lifespan := random.randf_range(0.65,1.15)
		var start := random.randf_range(0.0,maxf(0.0,float(recipe.duration)-lifespan*1.2))
		var seed_value := random.randf() * TAU
		var position := lava.to_global(Vector3(point.x,local.y-radius*0.15,point.y)) - global_position
		bubbles.append({"point":point,"radius":radius,"start":start,"lifespan":lifespan})
		for part in 4:
			multimesh.set_instance_transform(index*4+part,Transform3D(Basis.IDENTITY.scaled(Vector3.ONE*radius),position))
			multimesh.set_instance_custom_data(index*4+part,Color(start,lifespan,seed_value,float(part)))
	bubble_material = ShaderMaterial.new()
	bubble_material.shader = preload("res://shaders/original/lava_death_bubbles.gdshader")
	# The ambient lava bubbles own the shared orange finish.
	var finish := lava.bubble_material
	bubble_material.set_shader_parameter("bubble_albedo",finish.albedo_color)
	bubble_material.set_shader_parameter("bubble_emission",finish.emission)
	bubble_material.set_shader_parameter("bubble_energy",finish.emission_energy_multiplier)
	bubble_material.set_shader_parameter("bubble_roughness",finish.roughness)
	material_override = bubble_material
	cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	custom_aabb = AABB(Vector3(-2.0,-1.0,-2.0),Vector3(4.0,2.5,4.0))
	_process(0.0)

static func edge_distance(point: Vector2, polygon: PackedVector2Array) -> float:
	var distance := INF
	for edge in polygon.size():
		distance = minf(distance,point.distance_to(Geometry2D.get_closest_point_to_segment(point,polygon[edge],polygon[(edge+1)%polygon.size()])))
	return distance

func _process(_dt: float) -> void:
	if bubble_material == null: return
	var age := maxf(0.0,float(game.elapsed)-float(settings.start))
	visible = not game.reduced_motion and age <= float(settings.duration)
	if visible: bubble_material.set_shader_parameter("clock_seconds",age)
