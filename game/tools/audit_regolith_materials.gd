extends SceneTree
const ResourcePreparation=preload("res://scripts/core/resource_preparation.gd")

var failures: Array[String] = []
var counts := {}

func _initialize() -> void:
	run.call_deferred()

func run() -> void:
	DirAccess.make_dir_recursive_absolute("res://reports")
	for map_id in ["skyfall", "faceoff"]:
		var game := ArenaMatch.new()
		game.map_id = map_id
		game.count = 2
		root.add_child(game)
		for frame in range(12): await physics_frame
		var count := 0
		for mesh: MeshInstance3D in game.find_children("*", "MeshInstance3D", true, false):
			if mesh.mesh == null: continue
			for surface in mesh.mesh.get_surface_count():
				var material := mesh.get_active_material(surface) as StandardMaterial3D
				if material == null or Assets.material_role(material.resource_name) not in ["M_Regolith", "M_RegolithLight", "M_RegolithDark"]: continue
				count += 1
				var correct := material.albedo_texture != null and material.albedo_texture.resource_path.ends_with("regolith_albedo.png")
				correct = correct and material.normal_texture != null and material.normal_texture.resource_path.ends_with("regolith_normal.png")
				correct = correct and material.ao_enabled and material.ao_texture != null and material.ao_texture.resource_path.ends_with("regolith_orm.png")
				correct = correct and material.roughness_texture == material.ao_texture and material.roughness_texture_channel == BaseMaterial3D.TEXTURE_CHANNEL_GREEN
				correct = correct and material.ao_texture_channel == BaseMaterial3D.TEXTURE_CHANNEL_RED and material.metallic == 0.0
				correct = correct and material.uv1_world_triplanar and material.albedo_color == Color.WHITE
				correct = correct and not material.vertex_color_use_as_albedo
				if not correct: failures.append(map_id + ":" + str(mesh.get_path()) + ":" + material.resource_name)
		if "--capture" in OS.get_cmdline_user_args():
			root.size = Vector2i(1280, 720)
			game.map.assembly.seek(5.0, true)
			game.map.assembly.pause()
			var camera := Camera3D.new()
			game.add_child(camera)
			camera.current = true
			var preferences := Preferences.new("res://reports/regolith-audit-preferences.cfg")
			preferences.values.quality=2
			for key in Preferences.QUALITY_PRESETS[2]: preferences.values[key]=Preferences.QUALITY_PRESETS[2][key]
			preferences.apply_rendering(game)
			for region in ["crater", "outside"]:
				var target := Vector3(25,0,25) if region=="crater" else Vector3(180,0,0)
				camera.global_position=target+Vector3(6,7,8)
				camera.look_at(target)
				var readiness := await ResourcePreparation.wait_for_rendering(self,root)
				if not readiness.ready: failures.append(map_id+":"+region+": rendering not ready")
				for frame in range(30): await RenderingServer.frame_post_draw
				root.get_texture().get_image().save_png("res://reports/regolith-%s-%s.png"%[map_id,region])
				print("REGOLITH_CAPTURE ",map_id," ",region," ready=",readiness.ready)
		counts[map_id] = count
		if count == 0: failures.append(map_id + ": no regolith surfaces")
		game.queue_free()
		await process_frame
	FileAccess.open("res://reports/regolith-audit.json", FileAccess.WRITE).store_string(JSON.stringify({"surfaces": counts, "failures": failures}, "\t"))
	print("REGOLITH_AUDIT ", JSON.stringify({"surfaces": counts, "failures": failures}))
	quit(0 if failures.is_empty() else 1)
