class_name ShadowBatch
extends RefCounted
## Combine opaque material sections only for shadow rendering. Visible geometry,
## native skinning, collision, transparent surfaces and source materials stay intact.
static var meshes: Dictionary={}

static func install(root: Node3D) -> void:
	for source: MeshInstance3D in root.find_children("*","MeshInstance3D",true,false):install_one(source)

static func install_one(source: MeshInstance3D) -> void:
	if source.has_meta("batched_shadow") or not source.visible or source.cast_shadow!=GeometryInstance3D.SHADOW_CASTING_SETTING_ON:return
	var mesh:=source.mesh as ArrayMesh
	if mesh==null or mesh.get_surface_count()<2 or mesh.get_blend_shape_count()>0:return
	var cull: int=-1
	for surface in mesh.get_surface_count():
		var material:=source.get_active_material(surface) as StandardMaterial3D
		if material==null or material.transparency!=BaseMaterial3D.TRANSPARENCY_DISABLED or material.grow:return
		if mesh.surface_get_primitive_type(surface)!=Mesh.PRIMITIVE_TRIANGLES:return
		if (mesh.surface_get_format(surface)&Mesh.ARRAY_FORMAT_NORMAL)==0:return
		if cull>=0 and cull!=material.cull_mode:return
		cull=material.cull_mode
	var key: Array=[mesh.get_instance_id(),source.skin!=null,cull]
	if not meshes.has(key):meshes[key]=combine(mesh,source.skin!=null,cull)
	var proxy:=MeshInstance3D.new()
	proxy.name="ShadowBatch_"+source.name
	proxy.mesh=meshes[key];proxy.skin=source.skin;proxy.skeleton=source.skeleton
	proxy.transform=source.transform;proxy.layers=source.layers
	proxy.custom_aabb=source.custom_aabb;proxy.extra_cull_margin=source.extra_cull_margin
	proxy.cast_shadow=GeometryInstance3D.SHADOW_CASTING_SETTING_SHADOWS_ONLY
	source.get_parent().add_child(proxy)
	for property in ["visibility_range_begin","visibility_range_begin_margin","visibility_range_end","visibility_range_end_margin","visibility_range_fade_mode"]:
		proxy.set(property,source.get(property))
	source.visibility_changed.connect(func():proxy.visible=source.visible)
	source.cast_shadow=GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	source.set_meta("batched_shadow",weakref(proxy))

static func combine(mesh: ArrayMesh,skinned: bool,cull: int) -> ArrayMesh:
	var vertices:=PackedVector3Array();var normals:=PackedVector3Array()
	var indices:=PackedInt32Array();var bones:=PackedInt32Array();var weights:=PackedFloat32Array()
	var flags:=0
	for surface in mesh.get_surface_count():
		var arrays:=mesh.surface_get_arrays(surface)
		var offset:=vertices.size()
		var points: PackedVector3Array=arrays[Mesh.ARRAY_VERTEX]
		vertices.append_array(points);normals.append_array(arrays[Mesh.ARRAY_NORMAL])
		if arrays[Mesh.ARRAY_INDEX]!=null and arrays[Mesh.ARRAY_INDEX].size()>0:
			for index in arrays[Mesh.ARRAY_INDEX]:indices.append(index+offset)
		else:
			for index in points.size():indices.append(index+offset)
		if skinned:
			bones.append_array(arrays[Mesh.ARRAY_BONES]);weights.append_array(arrays[Mesh.ARRAY_WEIGHTS])
			flags=mesh.surface_get_format(surface)&Mesh.ARRAY_FLAG_USE_8_BONE_WEIGHTS
	var combined: Array=[];combined.resize(Mesh.ARRAY_MAX)
	combined[Mesh.ARRAY_VERTEX]=vertices;combined[Mesh.ARRAY_NORMAL]=normals;combined[Mesh.ARRAY_INDEX]=indices
	if skinned:combined[Mesh.ARRAY_BONES]=bones;combined[Mesh.ARRAY_WEIGHTS]=weights
	var result:=ArrayMesh.new()
	result.add_surface_from_arrays(Mesh.PRIMITIVE_TRIANGLES,combined,[],{},flags)
	var material:=StandardMaterial3D.new();material.cull_mode=cull
	result.surface_set_material(0,material)
	return result
