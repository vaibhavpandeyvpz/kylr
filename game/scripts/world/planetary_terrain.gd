class_name PlanetaryTerrain
extends RefCounted
## Shared static landform material. Terrain geometry and collision are authored.
const SHADER = preload("res://shaders/original/planetary_terrain.gdshader")
const LAYERS := ["dust","basalt","bedrock","rubble","compacted","scorch"]
static var materials: Dictionary = {}

static func material(map_id: String,local_surface := false) -> ShaderMaterial:
	var key:=map_id+str(local_surface)
	if materials.has(key): return materials[key]
	var result := ShaderMaterial.new()
	result.shader=SHADER
	var folder: String=MapCatalog.find(map_id).get("terrain_material","planetary")
	result.set_shader_parameter("volcanic_surface",folder=="volcanic_soil")
	result.set_shader_parameter("local_surface",local_surface)
	for layer: String in LAYERS:
		result.set_shader_parameter(layer+"_albedo",load("res://assets/textures/"+folder+"/"+layer+"_albedo_height.png"))
		result.set_shader_parameter(layer+"_normal",load("res://assets/textures/"+folder+"/"+layer+"_normal_roughness.png"))
	for index in 2:
		result.set_shader_parameter("weights"+str(index),load("res://assets/textures/planetary/"+map_id+"_weights"+str(index)+".png"))
	materials[key]=result
	return result
