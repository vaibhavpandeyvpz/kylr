class_name MeshLods
extends RefCounted
## Preserve imported index-only LODs when render geometry is baked or batched.
static var imported: Dictionary={}
static var packaged: Dictionary={}
static var package_loaded := false
static var missing := 0

static func bind(root: Node3D, asset_path: String) -> void:
	if not package_loaded:
		package_loaded=true
		if FileAccess.file_exists("res://data/render_mesh_lods.bin"):
			var bytes:=FileAccess.get_file_as_bytes("res://data/render_mesh_lods.bin").decompress_dynamic(268435456,FileAccess.COMPRESSION_GZIP)
			var data: Dictionary=bytes_to_var(bytes)
			if data.get("version",0)==1: packaged=data.meshes
	if packaged.is_empty(): return
	for instance: MeshInstance3D in root.find_children("*","MeshInstance3D",true,false):
		var mesh:=instance.mesh as ArrayMesh
		if mesh==null: continue
		var key:=asset_path+"|"+String(root.get_path_to(instance))
		if not packaged.has(key): continue
		var entry: Dictionary=packaged[key]
		var valid: bool=entry.lods.size()==mesh.get_surface_count()
		for index in mesh.get_surface_count():
			if not valid: break
			valid=mesh.surface_get_array_len(index)==entry.vertices[index] and mesh.surface_get_array_index_len(index)==entry.indices[index]
		if valid:
			mesh.set_meta("imported_lods",entry.lods)
			if entry.has("shadow_lods"): mesh.set_meta("shadow_lods",entry.shadow_lods)

static func surface(mesh: ArrayMesh, index: int) -> Dictionary:
	var key: Array=[mesh,index]
	if imported.has(key): return imported[key]
	if mesh.has_meta("imported_lods"):
		return mesh.get_meta("imported_lods")[index]
	if OS.has_feature("android"):
		missing+=1
		return {}
	var data := RenderingServer.mesh_get_surface(mesh.get_rid(),index)
	var stride := RenderingServer.mesh_surface_get_format_index_stride(data.format,data.vertex_count)
	var result: Dictionary = {}
	for lod in data.get("lods",[]):
		var bytes: PackedByteArray = lod.index_data
		var indices := PackedInt32Array()
		indices.resize(bytes.size()/stride)
		for offset in indices.size(): indices[offset]=bytes.decode_u16(offset*2) if stride==2 else bytes.decode_u32(offset*4)
		result[float(lod.edge_length)]=indices
	imported[key]=result
	return result

static func retain(baked: ArrayMesh, source: ArrayMesh) -> ArrayMesh:
	var result := ArrayMesh.new()
	var lods: Array=[]
	for index in baked.get_surface_count():
		assert(baked.surface_get_array_len(index)==source.surface_get_array_len(index),"Baked LOD vertex order must match the source")
		lods.append(surface(source,index))
		result.add_surface_from_arrays(baked.surface_get_primitive_type(index),baked.surface_get_arrays(index),[],lods.back())
		result.surface_set_material(index,source.surface_get_material(index))
	result.set_meta("imported_lods",lods)
	if source.has_meta("shadow_lods"): result.set_meta("shadow_lods",source.get_meta("shadow_lods"))
	return result

static func combine_shadow_lods(sections: Array[Dictionary]) -> Dictionary:
	var thresholds: Array=[]
	for section in sections:
		for distance in section.distances:
			if distance not in thresholds: thresholds.append(distance)
	thresholds.sort()
	var result: Dictionary={}
	for threshold in thresholds:
		var indices:=PackedInt32Array()
		for section in sections:
			var selected: PackedInt32Array=section.base
			for distance in section.distances:
				if distance>threshold: break
				selected=section.lods[distance]
			if int(section.offset)==0: indices.append_array(selected)
			else:
				for index in selected: indices.append(index+int(section.offset))
		result[threshold]=indices
	return result
