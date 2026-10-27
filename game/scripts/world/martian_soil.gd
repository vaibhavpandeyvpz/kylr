class_name MartianSoil
extends RefCounted
## Cached six-layer mineral materials shared by Ramparts terrain and regolith.
const LAYERS=["dust","dunes","bedrock","rubble","strata","sediment"]
static var shared: Dictionary={}
static func material(stone := false,local_surface := false) -> ShaderMaterial:
	var key:=Vector2i(int(stone),int(local_surface))
	if shared.has(key):return shared[key]
	var result:=ShaderMaterial.new();result.resource_name="M_MartianRegolith" if local_surface else ("M_MartianTerrainStone" if stone else "M_MartianTerrain")
	result.shader=preload("res://shaders/original/martian_terrain.gdshader")
	for index in 2:result.set_shader_parameter("weights%d"%index,load("res://assets/textures/martian_soil/ramparts_weights%d.png"%index))
	for layer in LAYERS:
		result.set_shader_parameter(layer+"_albedo",load("res://assets/textures/martian_soil/%s_albedo_height.png"%layer))
		result.set_shader_parameter(layer+"_normal",load("res://assets/textures/martian_soil/%s_normal_roughness.png"%layer))
	result.set_shader_parameter("stone_surface",stone)
	result.set_shader_parameter("local_surface",local_surface);shared[key]=result
	return result
