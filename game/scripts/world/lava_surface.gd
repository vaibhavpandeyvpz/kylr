class_name LavaSurface
extends Node3D
## Source-authored pit surfaces and sparse deterministic bubble bursts.
const MIN_BUBBLE_RADIUS := 0.025
const MAX_BUBBLE_RADIUS := 0.075
var game
var pits: Array[Dictionary] = []
var bubble_mesh: SphereMesh
var droplet_mesh: SphereMesh
var bubble_material: StandardMaterial3D

func install(match_node, definitions: Array) -> void:
	game=match_node
	name="LavaSurface"
	bubble_mesh=SphereMesh.new()
	bubble_mesh.radius=1.0;bubble_mesh.height=2.0
	bubble_mesh.radial_segments=12;bubble_mesh.rings=6
	droplet_mesh=SphereMesh.new()
	droplet_mesh.radius=1.0;droplet_mesh.height=2.0
	droplet_mesh.radial_segments=6;droplet_mesh.rings=3
	bubble_material=StandardMaterial3D.new()
	bubble_material.albedo_color=Color(.3,.025,.002)
	bubble_material.roughness=.38
	bubble_material.emission_enabled=true
	bubble_material.emission=Color(1.0,.16,.008)
	bubble_material.emission_energy_multiplier=2.5
	for definition in definitions:
		var polygon:=PackedVector2Array()
		for point in definition.rim:polygon.append(Vector2(float(point[0]),float(point[1])))
		var indices:=Geometry2D.triangulate_polygon(polygon)
		assert(not indices.is_empty(),"Lava footprint must triangulate: "+str(definition.name))
		var vertices:=PackedVector3Array();var normals:=PackedVector3Array()
		for point in polygon:
			vertices.append(Vector3(point.x,float(definition.surface_m),point.y));normals.append(Vector3.UP)
		var arrays:=[];arrays.resize(Mesh.ARRAY_MAX)
		arrays[Mesh.ARRAY_VERTEX]=vertices;arrays[Mesh.ARRAY_NORMAL]=normals;arrays[Mesh.ARRAY_INDEX]=indices
		var mesh:=ArrayMesh.new();mesh.add_surface_from_arrays(Mesh.PRIMITIVE_TRIANGLES,arrays)
		var material:=ShaderMaterial.new()
		material.shader=preload("res://shaders/original/lava.gdshader")
		material.set_shader_parameter("molten_basalt",preload("res://assets/textures/lava/molten_basalt.png"))
		var index:=pits.size()
		var direction:=Vector2(cos(index*2.4),sin(index*2.4))
		material.set_shader_parameter("flow_direction",direction)
		var surface:=MeshInstance3D.new();surface.name=str(definition.name).replace(" ","")
		surface.mesh=mesh;surface.material_override=material
		surface.cast_shadow=GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
		add_child(surface)
		var bubble:=MeshInstance3D.new();bubble.mesh=bubble_mesh;bubble.material_override=bubble_material
		bubble.cast_shadow=GeometryInstance3D.SHADOW_CASTING_SETTING_OFF;bubble.hide();add_child(bubble)
		var droplets:=MultiMeshInstance3D.new();droplets.multimesh=MultiMesh.new()
		droplets.multimesh.transform_format=MultiMesh.TRANSFORM_3D;droplets.multimesh.mesh=droplet_mesh
		droplets.multimesh.instance_count=4;droplets.material_override=bubble_material
		droplets.cast_shadow=GeometryInstance3D.SHADOW_CASTING_SETTING_OFF;droplets.hide();add_child(droplets)
		var bounds:=Rect2(polygon[0],Vector2.ZERO)
		for point in polygon:bounds=bounds.expand(point)
		pits.append({"polygon":polygon,"height":float(definition.surface_m),"material":material,
			"bubble":bubble,"droplets":droplets,"bounds":bounds,"cycle":-1,"point":Vector2.ZERO,"radius":MIN_BUBBLE_RADIUS})

func contains_contact(point: Vector3) -> bool:
	return contact_height(point) != INF

func contact_height(point: Vector3) -> float:
	var local:=to_local(point)
	var horizontal:=Vector2(local.x,local.z)
	for pit in pits:
		if local.y>float(pit.height)+.03:continue
		if not pit.bounds.has_point(horizontal):continue
		if Geometry2D.is_point_in_polygon(horizontal,pit.polygon):return to_global(Vector3(local.x,float(pit.height),local.z)).y
	return INF

func random_value(seed_value: float) -> float:
	return fposmod(sin(seed_value*12.9898)*43758.5453,1.0)

func bubble_point(pit: Dictionary,seed_value: float) -> Vector2:
	# Inset from walls, including the concave footprints, so bubbles stay in lava.
	var inset:=Geometry2D.offset_polygon(pit.polygon,-.45)
	var polygon: PackedVector2Array=pit.polygon if inset.is_empty() else inset[0]
	for attempt in 48:
		var candidate: Vector2=pit.bounds.position+pit.bounds.size*Vector2(random_value(seed_value+attempt*2),random_value(seed_value+attempt*2+1))
		if Geometry2D.is_point_in_polygon(candidate,polygon):return candidate
	return polygon[0]

func _process(_dt: float) -> void:
	var quality:=clampi(int(get_viewport().get_meta("effect_quality",2)),0,2)
	var clock:=0.0 if game.reduced_motion else float(game.elapsed)
	for index in pits.size():
		var pit: Dictionary=pits[index]
		pit.material.set_shader_parameter("clock_seconds",clock)
		pit.material.set_shader_parameter("detail",quality)
		var period:=7.0+random_value(index+17)*6.0
		var shifted:=clock+random_value(index+4)*period
		var cycle:=int(floor(shifted/period))
		var phase:=fposmod(shifted,period)
		if cycle!=int(pit.cycle):
			pit.cycle=cycle;pit.point=bubble_point(pit,index*213.0+cycle*43.0+7.0)
			pit.radius=lerpf(MIN_BUBBLE_RADIUS,MAX_BUBBLE_RADIUS,random_value(index*719.0+cycle*89.0+31.0))
			pit.material.set_shader_parameter("bubble_radius",pit.radius)
		var enabled: bool=not game.reduced_motion and (quality>0 or index%2==0)
		var growing: bool=enabled and phase<1.0
		pit.bubble.visible=growing
		pit.droplets.visible=enabled and quality>0 and phase>=1.0 and phase<1.65
		pit.material.set_shader_parameter("bubble_center",pit.point)
		pit.material.set_shader_parameter("bubble_phase",phase if enabled else -1.0)
		if growing:
			var rise:=sin(phase*PI*.5)
			pit.bubble.position=Vector3(pit.point.x,pit.height-pit.radius*(.15+(1.0-rise)*1.2),pit.point.y)
			pit.bubble.scale=Vector3.ONE*pit.radius*rise
		if pit.droplets.visible:
			var age: float=(phase-1.0)/.65
			for drop in 4:
				var angle:=TAU*drop/4+index
				var position:=Vector3(pit.point.x+cos(angle)*age*pit.radius*.6,pit.height+pit.radius*(2.0*age*(1.0-age)-.15),pit.point.y+sin(angle)*age*pit.radius*.6)
				pit.droplets.multimesh.set_instance_transform(drop,Transform3D(Basis.IDENTITY.scaled(Vector3.ONE*pit.radius*.12*(1.0-age)),position))
