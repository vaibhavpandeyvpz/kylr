extends GutTest

func fixture() -> MeshInstance3D:
	var root:=Node3D.new();add_child_autofree(root)
	var skeleton:=Skeleton3D.new();skeleton.name="Skeleton3D";root.add_child(skeleton);skeleton.add_bone("Root")
	var instance:=MeshInstance3D.new();root.add_child(instance)
	var mesh:=ArrayMesh.new()
	for offset in [0.0,2.0]:
		var arrays: Array=[];arrays.resize(Mesh.ARRAY_MAX)
		arrays[Mesh.ARRAY_VERTEX]=PackedVector3Array([Vector3(offset,0,0),Vector3(offset+1,0,0),Vector3(offset,0,1)])
		arrays[Mesh.ARRAY_NORMAL]=PackedVector3Array([Vector3.UP,Vector3.UP,Vector3.UP])
		arrays[Mesh.ARRAY_BONES]=PackedInt32Array([0,0,0,0,0,0,0,0,0,0,0,0])
		arrays[Mesh.ARRAY_WEIGHTS]=PackedFloat32Array([1,0,0,0,1,0,0,0,1,0,0,0])
		arrays[Mesh.ARRAY_INDEX]=PackedInt32Array([0,1,2])
		mesh.add_surface_from_arrays(Mesh.PRIMITIVE_TRIANGLES,arrays)
		mesh.surface_set_material(mesh.get_surface_count()-1,StandardMaterial3D.new())
	instance.mesh=mesh;instance.skin=Skin.new();instance.skin.add_named_bind("Root",Transform3D.IDENTITY)
	instance.skeleton=NodePath("../Skeleton3D");instance.position=Vector3(3,2,1)
	return instance

func test_opaque_batch_preserves_every_triangle_normal_and_skin_weight():
	var source:=fixture();var original: ArrayMesh=source.mesh
	ShadowBatch.install_one(source)
	assert_eq(source.cast_shadow,GeometryInstance3D.SHADOW_CASTING_SETTING_OFF)
	var proxy: MeshInstance3D=source.get_meta("batched_shadow").get_ref()
	assert_eq(proxy.cast_shadow,GeometryInstance3D.SHADOW_CASTING_SETTING_SHADOWS_ONLY)
	assert_same(proxy.skin,source.skin);assert_eq(proxy.skeleton,source.skeleton)
	assert_eq(proxy.transform,source.transform);assert_same(source.mesh,original)
	assert_eq(proxy.mesh.get_surface_count(),1)
	var combined: Array=proxy.mesh.surface_get_arrays(0)
	for surface in original.get_surface_count():
		var arrays:=original.surface_get_arrays(surface)
		for vertex in 3:
			assert_eq(combined[Mesh.ARRAY_VERTEX][surface*3+vertex],arrays[Mesh.ARRAY_VERTEX][vertex])
			assert_eq(combined[Mesh.ARRAY_NORMAL][surface*3+vertex],arrays[Mesh.ARRAY_NORMAL][vertex])
			for influence in 4:
				assert_eq(combined[Mesh.ARRAY_BONES][(surface*3+vertex)*4+influence],arrays[Mesh.ARRAY_BONES][vertex*4+influence])
				assert_eq(combined[Mesh.ARRAY_WEIGHTS][(surface*3+vertex)*4+influence],arrays[Mesh.ARRAY_WEIGHTS][vertex*4+influence])
	assert_eq(combined[Mesh.ARRAY_INDEX],PackedInt32Array([0,1,2,3,4,5]))
	ShadowBatch.install_one(source)
	assert_eq(source.get_parent().find_children("ShadowBatch_*","MeshInstance3D",false,false).size(),1)
	source.hide();assert_false(proxy.visible,"Hidden native variants cannot leave a ghost shadow")
	source.show();assert_true(proxy.visible)

func test_transparent_custom_and_noncasting_meshes_keep_their_native_path():
	for kind in ["transparent","shader","noncasting","grown"]:
		var source:=fixture()
		var material:=StandardMaterial3D.new()
		if kind=="transparent":material.transparency=BaseMaterial3D.TRANSPARENCY_ALPHA
		if kind=="grown":material.grow=true
		if kind=="shader":source.material_override=ShaderMaterial.new()
		else:source.set_surface_override_material(0,material)
		if kind=="noncasting":source.cast_shadow=GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
		var before:=source.cast_shadow
		ShadowBatch.install_one(source)
		assert_false(source.has_meta("batched_shadow"),kind)
		assert_eq(source.cast_shadow,before)
