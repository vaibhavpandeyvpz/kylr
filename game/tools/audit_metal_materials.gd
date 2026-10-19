extends SceneTree
var report := {}
var assets := 0
var shaders := {}
var unshaded_metals: Array[String] = []

func _initialize() -> void: run.call_deferred()

func run() -> void:
	for category: String in ["weapons","characters","architecture","environments","gameplay","maps"]:
		var base := "res://assets/models/"+category
		for asset in DirAccess.get_directories_at(base):
			for file in DirAccess.get_files_at(base.path_join(asset)):
				if not file.ends_with(".glb") or file.ends_with("_col.glb"): continue
				audit(base.path_join(asset).path_join(file))
	FileAccess.open("res://reports/metal-material-audit.json",FileAccess.WRITE).store_string(JSON.stringify({"asset_count":assets,"metals":report,"shaders":shaders,"unshaded_metals":unshaded_metals},"  "))
	print("METAL_AUDIT assets=",assets," material_variants=",report.size()," shader_finishes=",shaders.size()," unshaded_metals=",unshaded_metals.size())
	quit(0 if unshaded_metals.is_empty() else 1)

func audit(path: String) -> void:
	var model := Assets.scene(path)
	assets += 1
	for mesh: MeshInstance3D in model.find_children("*","MeshInstance3D",true,false):
		for surface in mesh.mesh.get_surface_count():
			var active := mesh.get_active_material(surface)
			if active is ShaderMaterial:
				shaders[active.resource_name] = active.shader.resource_path
				continue
			var source := mesh.mesh.surface_get_material(surface) as StandardMaterial3D
			if source == null or source.metallic<=0: continue
			var finish := active as StandardMaterial3D
			if finish == null: continue
			if finish.shading_mode==BaseMaterial3D.SHADING_MODE_UNSHADED: unshaded_metals.append(path+":"+source.resource_name)
			var key := "%s metal=%.2f rough=%.2f textured=%s"%[source.resource_name,source.metallic,source.roughness,source.roughness_texture!=null]
			if not report.has(key): report[key]={"assets":[],"finish_roughness":finish.roughness,"finish_metallic":finish.metallic,"clearcoat":finish.clearcoat_enabled}
			if path not in report[key].assets: report[key].assets.append(path)
	model.free()
