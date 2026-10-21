class_name PlanetaryTerrain
extends RefCounted
## Shared static landform material. Terrain geometry and collision are authored.
const SHADER = preload("res://shaders/original/planetary_terrain.gdshader")
const LAYERS := ["dust","basalt","bedrock","rubble","compacted","scorch"]
static var materials: Dictionary = {}

static func material(map_id: String) -> ShaderMaterial:
	if materials.has(map_id): return materials[map_id]
	var result := ShaderMaterial.new()
	result.shader=SHADER
	for layer: String in LAYERS:
		result.set_shader_parameter(layer+"_albedo",load("res://assets/textures/planetary/"+layer+"_albedo_height.png"))
		result.set_shader_parameter(layer+"_normal",load("res://assets/textures/planetary/"+layer+"_normal_roughness.png"))
	for index in 2:
		result.set_shader_parameter("weights"+str(index),load("res://assets/textures/planetary/"+map_id+"_weights"+str(index)+".png"))
	materials[map_id]=result
	return result
