class_name ProjectileResources
extends RefCounted
## Immutable render resources. Motion and shader overrides belong to instances.
static var meshes: Dictionary = {}
static var materials: Dictionary = {}
static var gradients: Dictionary = {}

static func gradient(offsets: PackedFloat32Array, colors: PackedColorArray) -> GradientTexture1D:
	var key := [offsets, colors]
	if gradients.has(key): return gradients[key]
	var ramp := GradientTexture1D.new()
	var stops := Gradient.new()
	stops.offsets = offsets
	stops.colors = colors
	ramp.gradient = stops
	gradients[[offsets.duplicate(), colors.duplicate()]] = ramp
	return ramp

static func particles(properties: Dictionary) -> ParticleProcessMaterial:
	var key := [&"particles", properties]
	if materials.has(key): return materials[key]
	var material := ParticleProcessMaterial.new()
	for property in properties: material.set(property, properties[property])
	materials[[&"particles", properties.duplicate()]] = material
	return material

static func primitive(kind: StringName, properties: Dictionary) -> PrimitiveMesh:
	var key := [kind, properties]
	if meshes.has(key): return meshes[key]
	assert(kind in [&"SphereMesh", &"CylinderMesh", &"BoxMesh", &"QuadMesh"])
	var mesh := ClassDB.instantiate(kind) as PrimitiveMesh
	for property in properties: mesh.set(property, properties[property])
	meshes[[kind, properties.duplicate()]] = mesh
	return mesh

static func shader(shader_resource: Shader, parameters: Dictionary = {}) -> ShaderMaterial:
	var key := [shader_resource, parameters]
	if materials.has(key): return materials[key]
	var material := ShaderMaterial.new()
	material.shader = shader_resource
	for parameter in parameters: material.set_shader_parameter(parameter, parameters[parameter])
	materials[[shader_resource, parameters.duplicate()]] = material
	return material

static func standard(properties: Dictionary) -> StandardMaterial3D:
	var key := [&"standard", properties]
	if materials.has(key): return materials[key]
	var material := StandardMaterial3D.new()
	for property in properties: material.set(property, properties[property])
	materials[[&"standard", properties.duplicate()]] = material
	return material
