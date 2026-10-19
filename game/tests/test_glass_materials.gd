extends GutTest

func test_native_glass_uses_shared_original_shader_without_replacing_symbols():
	for id in ["energy_core", "shield_core", "energy_core_pickup"]:
		var first := Assets.model("gameplay", id)
		var second := Assets.model("gameplay", id)
		var glass_count := 0
		var symbol_count := 0
		for mesh in first.find_children("*", "MeshInstance3D", true, false):
			for surface in mesh.mesh.get_surface_count():
				var material: Material = mesh.get_active_material(surface)
				if Assets.material_role(material.resource_name) == "M_CoreOuter":
					glass_count += 1
					assert_true(material is ShaderMaterial)
					assert_eq(material.shader, Assets.GLASS_SHADER)
					assert_almost_eq(float(material.get_shader_parameter("opacity")), 0.25, 0.0001)
					var twin := second.find_child(mesh.name, true, false) as MeshInstance3D
					assert_same(material, twin.get_active_material(surface))
				elif Assets.material_role(material.resource_name) == "M_CoreInner":
					symbol_count += 1
					assert_true(material is StandardMaterial3D)
		assert_gt(glass_count, 0)
		assert_gt(symbol_count, 0)
		first.free()
		second.free()
