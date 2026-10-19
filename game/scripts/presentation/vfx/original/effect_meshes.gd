class_name EffectMeshes
extends RefCounted

const KIT = preload("res://assets/models/effects/combat_effects/combat_effects.glb")
static var meshes: Dictionary = {}

static func mesh(id: String) -> Mesh:
	if meshes.is_empty():
		var source := KIT.instantiate()
		for node in source.find_children("*","MeshInstance3D",true,false):
			meshes[String(node.name).trim_prefix("SK_")] = node.mesh
		source.free()
	assert(meshes.has(id),"Unknown authored effect mesh: " + id)
	return meshes[id]
