class_name CoreOrb
extends Node3D

var kind := "energy"
var dropped := false
var visual: Node3D
static var energy_materials: Dictionary = {}

func _init(core_kind := "energy", is_drop := false) -> void:
	assert(core_kind in ["energy", "shield"])
	assert(not is_drop or core_kind == "energy")
	kind = core_kind
	dropped = is_drop

func _ready() -> void:
	var asset := "energy_core_pickup" if dropped else kind + "_core"
	visual = Assets.model("gameplay", asset)
	if kind == "energy": apply_energy_materials(visual)
	add_child(visual)
	# Preserve the native glass, hardware, symbol and counter-rotating rig.
	Assets.play(visual, "spin", true)

static func prepare_energy_materials() -> void:
	if not energy_materials.is_empty(): return
	# Use the square pickup's actual finished materials for both energy models.
	# The map prepares these materials before a short-lived death drop needs them.
	var reference := Assets.model("gameplay", "energy_core")
	for mesh in reference.find_children("*", "MeshInstance3D", true, false):
		for surface in mesh.mesh.get_surface_count():
			var material: Material = mesh.get_active_material(surface)
			var role := Assets.material_role(material.resource_name)
			if role in ["M_CoreOuter", "M_CoreInner"]: energy_materials[role] = material
	reference.free()

static func apply_energy_materials(node: Node) -> void:
	prepare_energy_materials()
	if node is MeshInstance3D:
		for surface in node.mesh.get_surface_count():
			var role := Assets.material_role(node.get_active_material(surface).resource_name)
			if energy_materials.has(role): node.set_surface_override_material(surface, energy_materials[role])
	for child in node.get_children(): apply_energy_materials(child)
