extends GutTest

func test_export_metadata_compression_roundtrips_without_a_size_header():
	var payload:=var_to_bytes({"version":1,"meshes":{"sample":[PackedInt32Array([0,1,2])]}})
	var packed:=payload.compress(FileAccess.COMPRESSION_GZIP)
	assert_eq(packed.decompress_dynamic(268435456,FileAccess.COMPRESSION_GZIP),payload)

func sample_mesh() -> ArrayMesh:
	var mesh := ArrayMesh.new()
	for surface in 2:
		var arrays: Array=[]
		arrays.resize(Mesh.ARRAY_MAX)
		arrays[Mesh.ARRAY_VERTEX]=PackedVector3Array([Vector3(0,0,surface),Vector3(1,0,surface),Vector3(0,1,surface),Vector3(1,1,surface)])
		arrays[Mesh.ARRAY_NORMAL]=PackedVector3Array([Vector3.BACK,Vector3.BACK,Vector3.BACK,Vector3.BACK])
		arrays[Mesh.ARRAY_INDEX]=PackedInt32Array([0,1,2,1,3,2])
		mesh.add_surface_from_arrays(Mesh.PRIMITIVE_TRIANGLES,arrays,[],{0.5 if surface==0 else 1.0:PackedInt32Array([0,1,2])})
		mesh.surface_set_material(surface,StandardMaterial3D.new())
	return mesh

func test_baking_retains_source_lods_and_baked_vertex_positions():
	var source := sample_mesh()
	var baked := ArrayMesh.new()
	for surface in 2:
		var arrays := source.surface_get_arrays(surface)
		var vertices: PackedVector3Array=arrays[Mesh.ARRAY_VERTEX]
		for index in vertices.size(): vertices[index]+=Vector3(10,5,3)
		arrays[Mesh.ARRAY_VERTEX]=vertices
		baked.add_surface_from_arrays(Mesh.PRIMITIVE_TRIANGLES,arrays)
	var retained := MeshLods.retain(baked,source)
	for surface in 2:
		assert_eq(retained.surface_get_arrays(surface)[Mesh.ARRAY_VERTEX],baked.surface_get_arrays(surface)[Mesh.ARRAY_VERTEX])
		assert_eq(MeshLods.surface(retained,surface),MeshLods.surface(source,surface))
		assert_same(retained.surface_get_material(surface),source.surface_get_material(surface))

func test_shadow_batch_retains_each_surface_lod_threshold_and_index_offset():
	var source := sample_mesh()
	var batch := ShadowBatch.combine(source,false,BaseMaterial3D.CULL_BACK)
	var lods := MeshLods.surface(batch,0)
	assert_eq(lods[0.5],PackedInt32Array([0,1,2,4,5,6,5,7,6]),"Each surface follows its own native threshold")
	assert_eq(lods[1.0],PackedInt32Array([0,1,2,4,5,6]))
	var points: PackedVector3Array=batch.surface_get_arrays(0)[Mesh.ARRAY_VERTEX]
	for indices: PackedInt32Array in lods.values():
		for index in indices: assert_between(index,0,points.size()-1)

func test_packaged_lods_bind_only_to_matching_asset_mesh_layout():
	var root:=Node3D.new()
	autofree(root)
	var instance:=MeshInstance3D.new()
	instance.name="Geometry"
	instance.mesh=sample_mesh()
	root.add_child(instance)
	var previous:=MeshLods.packaged
	var loaded:=MeshLods.package_loaded
	MeshLods.package_loaded=true
	MeshLods.packaged={"res://sample.glb|Geometry":{"vertices":PackedInt32Array([4,4]),"indices":PackedInt32Array([6,6]),"lods":[{0.5:PackedInt32Array([0,1,2])},{}]}}
	MeshLods.bind(root,"res://other.glb")
	assert_false(instance.mesh.has_meta("imported_lods"))
	MeshLods.bind(root,"res://sample.glb")
	assert_eq(instance.mesh.get_meta("imported_lods")[0][0.5],PackedInt32Array([0,1,2]))
	instance.mesh.remove_meta("imported_lods")
	MeshLods.packaged["res://sample.glb|Geometry"].vertices[0]=999
	MeshLods.bind(root,"res://sample.glb")
	assert_false(instance.mesh.has_meta("imported_lods"),"Stale exported metadata cannot change mesh indices")
	MeshLods.packaged=previous
	MeshLods.package_loaded=loaded
