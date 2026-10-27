class_name LakeSurface
extends Node3D
## Finite crater lake. The water level remains the gameplay fall boundary.
var material: ShaderMaterial
var game
func install(match_node, recipe: Dictionary) -> void:
	game = match_node
	name = "LakeSurface"
	install_water(recipe)
	install_environment(recipe)

func install_water(recipe: Dictionary) -> void:
	material = ShaderMaterial.new()
	material.shader = preload("res://shaders/original/lake.gdshader")
	for parameter in ["deep_color","shallow_color","foam_color"]:
		var color:=Color(recipe.water[parameter]).srgb_to_linear()
		material.set_shader_parameter(parameter,Vector3(color.r,color.g,color.b))
	material.set_shader_parameter("absorption",MapCatalog.vector(recipe.water.absorption))
	var radius: float=recipe.water.radius_m
	material.set_shader_parameter("lake_radius",radius)
	var segments:=192;var rings:=64
	var vertices:=PackedVector3Array([Vector3.ZERO]);var normals:=PackedVector3Array([Vector3.UP]);var indices:=PackedInt32Array()
	for ring in range(1,rings+1):
		var r:=radius*ring/rings
		var start:=vertices.size()
		for i in segments:
			var angle:=TAU*i/segments
			vertices.append(Vector3(cos(angle)*r,0,sin(angle)*r));normals.append(Vector3.UP)
		for i in segments:
			var j: int=(i+1)%segments
			if ring==1:indices.append_array([0,start+i,start+j])
			else:
				var previous:=start-segments
				indices.append_array([previous+i,start+i,start+j,previous+i,start+j,previous+j])
	var arrays:=[];arrays.resize(Mesh.ARRAY_MAX)
	arrays[Mesh.ARRAY_VERTEX]=vertices;arrays[Mesh.ARRAY_NORMAL]=normals;arrays[Mesh.ARRAY_INDEX]=indices
	var mesh:=ArrayMesh.new();mesh.add_surface_from_arrays(Mesh.PRIMITIVE_TRIANGLES,arrays)
	var water:=MeshInstance3D.new();water.name="CraterLake";water.mesh=mesh;water.material_override=material
	water.cast_shadow=GeometryInstance3D.SHADOW_CASTING_SETTING_OFF;water.extra_cull_margin=1.0;add_child(water)

func install_environment(recipe: Dictionary) -> void:
	var world := WorldEnvironment.new()
	var environment := Environment.new()
	environment.background_mode = Environment.BG_SKY
	var sky := Sky.new()
	var atmosphere := ProceduralSkyMaterial.new()
	atmosphere.sky_top_color = Color(recipe.sky_top)
	atmosphere.sky_horizon_color = Color(recipe.sky_horizon)
	atmosphere.ground_horizon_color = Color(recipe.ground_horizon)
	atmosphere.ground_bottom_color = Color(recipe.ground_bottom)
	atmosphere.sun_angle_max = 6.0
	sky.sky_material = atmosphere
	environment.sky = sky
	environment.ambient_light_source = Environment.AMBIENT_SOURCE_COLOR
	environment.ambient_light_color = Color(recipe.ambient_color)
	environment.ambient_light_energy = float(recipe.ambient_energy)
	environment.ambient_light_sky_contribution = 0.0
	environment.reflected_light_source = Environment.REFLECTION_SOURCE_SKY
	environment.tonemap_mode = Environment.TONE_MAPPER_FILMIC
	environment.glow_enabled = true
	environment.glow_intensity = 0.12
	environment.ssao_enabled = true
	environment.ssao_radius = 0.75
	environment.ssao_intensity = 1.1
	environment.fog_enabled = true
	environment.fog_light_color = Color(recipe.fog_color)
	environment.fog_density = float(recipe.fog_density)
	world.environment = environment
	add_child(world)
	var sun := DirectionalLight3D.new()
	sun.name = "LGT_RampartsSun"
	sun.rotation_degrees = MapCatalog.vector(recipe.key_rotation_degrees)
	sun.light_color = Color(recipe.key_color)
	sun.light_energy = float(recipe.key_energy)
	sun.shadow_enabled = true
	sun.directional_shadow_max_distance = 140
	add_child(sun)

func _process(_dt: float) -> void:
	if material==null:return
	material.set_shader_parameter("clock_seconds",0.0 if game.reduced_motion else game.elapsed)
	material.set_shader_parameter("detail",clampi(int(get_viewport().get_meta("effect_quality",2)),0,2))
