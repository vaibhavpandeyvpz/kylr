extends GutTest

func test_directly_authored_aprons_import_shared_pbr_without_runtime_replacement():
	for name in ["bunker", "shelter"]:
		# Load the native scene directly: arena material replacement must not
		# conceal an incomplete source export.
		var scene: PackedScene = load("res://assets/models/architecture/%s/%s.glb" % [name, name])
		assert_not_null(scene)
		if scene == null: continue
		var prop := scene.instantiate()
		add_child_autofree(prop)
		var regolith_surfaces := 0
		for mesh in prop.find_children("*", "MeshInstance3D", true, false):
			for surface in mesh.mesh.get_surface_count():
				var material := mesh.get_active_material(surface) as StandardMaterial3D
				if material == null or Assets.material_role(material.resource_name) != "M_Regolith": continue
				regolith_surfaces += 1
				assert_eq(material.albedo_texture, Assets.REGOLITH_ALBEDO, name + " shares canonical albedo")
				assert_true(material.normal_enabled)
				assert_eq(material.normal_texture, Assets.REGOLITH_NORMAL, name + " shares canonical normals")
				assert_eq(material.roughness_texture, Assets.REGOLITH_ORM, name + " shares canonical roughness")
				assert_true(material.ao_enabled)
				assert_eq(material.ao_texture, Assets.REGOLITH_ORM, name + " shares canonical occlusion")
				assert_almost_eq(material.metallic, 0.0, 0.00001)
		assert_gt(regolith_surfaces, 0, name + " exports a regolith apron")
