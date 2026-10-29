@tool
extends EditorExportPlugin

func _get_name() -> String:
	return "KYLRMeshLods"

func _export_begin(features: PackedStringArray, _debug: bool, _path: String, _flags: int) -> void:
	if "android" not in features: return
	var meshes: Dictionary={}
	var pending: Array[String]=["res://assets/models"]
	var cache: Dictionary={}
	while not pending.is_empty():
		var folder: String=pending.pop_back()
		for child in DirAccess.get_directories_at(folder): pending.append(folder.path_join(child))
		for file in DirAccess.get_files_at(folder):
			if not file.ends_with(".glb") or file.ends_with("_col.glb"): continue
			var path:=folder.path_join(file)
			var scene:=load(path) as PackedScene
			if scene==null: continue
			var root:=scene.instantiate()
			for instance: MeshInstance3D in root.find_children("*","MeshInstance3D",true,false):
				var mesh:=instance.mesh as ArrayMesh
				if mesh==null: continue
				if not cache.has(mesh):
					var entry: Dictionary={"vertices":PackedInt32Array(),"indices":PackedInt32Array(),"lods":[]}
					for surface in mesh.get_surface_count():
						entry.vertices.append(mesh.surface_get_array_len(surface))
						entry.indices.append(mesh.surface_get_array_index_len(surface))
						entry.lods.append(read_lods(mesh,surface))
					var opaque:=mesh.get_surface_count()>1 and mesh.get_blend_shape_count()==0
					var sections: Array[Dictionary]=[]
					var offset:=0
					for surface in mesh.get_surface_count():
						var material:=mesh.surface_get_material(surface) as StandardMaterial3D
						opaque=opaque and material!=null and material.transparency==BaseMaterial3D.TRANSPARENCY_DISABLED and not material.grow
						if not opaque: break
						var arrays:=mesh.surface_get_arrays(surface)
						var base: PackedInt32Array=arrays[Mesh.ARRAY_INDEX] if arrays[Mesh.ARRAY_INDEX]!=null else PackedInt32Array()
						if base.is_empty():
							for index in entry.vertices[surface]: base.append(index)
						var distances: Array=entry.lods[surface].keys()
						distances.sort()
						sections.append({"offset":offset,"base":base,"lods":entry.lods[surface],"distances":distances})
						offset+=entry.vertices[surface]
					if opaque: entry["shadow_lods"]=MeshLods.combine_shadow_lods(sections)
					cache[mesh]=entry
				meshes[path+"|"+String(root.get_path_to(instance))]=cache[mesh]
			root.free()
	var payload:=var_to_bytes({"version":1,"meshes":meshes})
	add_file("res://data/render_mesh_lods.bin",payload.compress(FileAccess.COMPRESSION_GZIP),false)
	print("EXPORT_MESH_LODS entries=",meshes.size()," bytes=",payload.size())

static func read_lods(mesh: ArrayMesh, surface: int) -> Dictionary:
	var data:=RenderingServer.mesh_get_surface(mesh.get_rid(),surface)
	var stride:=RenderingServer.mesh_surface_get_format_index_stride(data.format,data.vertex_count)
	var result: Dictionary={}
	for lod in data.get("lods",[]):
		var bytes: PackedByteArray=lod.index_data
		var indices:=PackedInt32Array()
		indices.resize(bytes.size()/stride)
		for offset in indices.size(): indices[offset]=bytes.decode_u16(offset*2) if stride==2 else bytes.decode_u32(offset*4)
		result[float(lod.edge_length)]=indices
	return result
