extends GutTest

func build_fixture() -> Dictionary:
	var root := Node3D.new()
	add_child_autofree(root)
	var mesh := ArrayMesh.new()
	var box := BoxMesh.new()
	mesh.add_surface_from_arrays(Mesh.PRIMITIVE_TRIANGLES,box.get_mesh_arrays())
	mesh.surface_set_material(0,StandardMaterial3D.new())
	var fixtures: Array=[]
	var sources: Array[MeshInstance3D]=[]
	for index in 2:
		var fixture := Node3D.new()
		root.add_child(fixture)
		fixture.position=Vector3(index*3,0,0)
		var source := MeshInstance3D.new()
		source.mesh=mesh
		source.position=Vector3(0,2,0)
		source.set_meta("fixed_render_mesh",true)
		fixture.add_child(source)
		var body := StaticBody3D.new()
		fixture.add_child(body)
		var light := OmniLight3D.new()
		fixture.add_child(light)
		fixtures.append({"id":str(index),"kind":"prop","node":fixture})
		sources.append(source)
	return {"arena":{"model":root,"markers":[],"fixtures":fixtures,"carriers":null},"sources":sources,"root":root,"mesh":mesh}

func test_fixed_batch_preserves_world_geometry_and_native_gameplay_nodes():
	var fixture := build_fixture()
	var result := FixedMeshBatch.install(fixture.arena)
	assert_eq(result.sources,2)
	assert_eq(result.batches,1)
	var batch := fixture.root.find_child("FixedFixtureBatch",true,false) as MultiMeshInstance3D
	assert_not_null(batch)
	if batch==null: return
	assert_same(batch.multimesh.mesh,fixture.mesh)
	for index in 2:
		assert_false(fixture.sources[index].visible)
	assert_eq(fixture.root.find_children("*","StaticBody3D",true,false).size(),2)
	for light in fixture.root.find_children("*","OmniLight3D",true,false): assert_true(light.is_visible_in_tree())

func test_native_multimesh_transforms_match_each_source():
	if DisplayServer.get_name()=="headless":
		pending("Dummy rendering server does not retain MultiMesh transform buffers")
		return
	var fixture := build_fixture()
	var transforms: Array[Transform3D]=[]
	for source in fixture.sources: transforms.append(source.global_transform)
	FixedMeshBatch.install(fixture.arena)
	var batch := fixture.root.find_child("FixedFixtureBatch",true,false) as MultiMeshInstance3D
	assert_not_null(batch)
	if batch==null: return
	for index in 2: assert_eq(batch.global_transform*batch.multimesh.get_instance_transform(index),transforms[index])

func test_distinct_material_overrides_are_not_combined():
	var fixture := build_fixture()
	for source in fixture.sources: source.material_override=StandardMaterial3D.new()
	var result := FixedMeshBatch.install(fixture.arena)
	assert_eq(result.batches,0)
	for source in fixture.sources: assert_true(source.visible)

func test_carrier_batch_remains_under_its_native_deck_bone():
	var fixture:=build_fixture()
	var skeleton:=Skeleton3D.new()
	fixture.root.add_child(skeleton)
	skeleton.add_bone("Deck_Main")
	fixture.arena.carriers={"rigid_groups":{"Main":"group"},"skeleton":skeleton}
	fixture.arena.markers=[{"name":"0","deck":"Main"},{"name":"1","deck":"Main"}]
	var result:=FixedMeshBatch.install(fixture.arena)
	assert_eq(result.batches,1)
	var batch: Node=fixture.root.find_child("FixedFixtureBatch",true,false)
	assert_true(batch.get_parent() is BoneAttachment3D)
	assert_eq(batch.get_parent().bone_name,"Deck_Main")
	assert_same(batch.get_parent().get_parent(),skeleton)

func test_transparent_surfaces_retain_individual_sortable_instances():
	var fixture := build_fixture()
	var glass := StandardMaterial3D.new()
	glass.transparency=BaseMaterial3D.TRANSPARENCY_ALPHA
	fixture.mesh.add_surface_from_arrays(Mesh.PRIMITIVE_TRIANGLES,fixture.mesh.surface_get_arrays(0))
	fixture.mesh.surface_set_material(1,glass)
	var result := FixedMeshBatch.install(fixture.arena)
	assert_eq(result.batches,1)
	var transparent: Array = fixture.root.find_children("FixedFixtureTransparent","MeshInstance3D",true,false)
	assert_eq(transparent.size(),2)
	for instance in transparent:
		assert_eq(instance.mesh.get_surface_count(),1)
		assert_same(instance.mesh.surface_get_material(0),glass)
		assert_true(instance.visible)
