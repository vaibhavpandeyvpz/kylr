extends SceneTree

func _initialize() -> void: run.call_deferred()

func run() -> void:
	root.size = Vector2i(1280,720)
	var lighting := ArenaMap.new()
	lighting.add_world()
	for child in lighting.get_children():
		lighting.remove_child(child)
		root.add_child(child)
		if child is WorldEnvironment:
			child.environment.sky.sky_material.set_shader_parameter("reduced_motion",true)
	lighting.free()
	var entries := [
		["weapons","pistol","M_Joint","WEAPON / STEEL"],
		["characters","tensor","M_Titanium","ROBOT / TITANIUM"],
		["characters","tensor","M_Alu","ROBOT / ALUMINIUM"],
		["characters","tensor","M_Wire","ROBOT / COPPER"],
		["environments","pillar","M_Bronze","PILLAR / BRONZE"],
		["architecture","bunker","M_Glass","ARCHITECTURE / GLASS"],
		["gameplay","energy_core","M_CoreOuter","ENERGY CORE / GLASS"],
		["gameplay","shield_core","M_CoreOuter","SHIELD CORE / GLASS"]]
	entries.append_array([
		["weapons","pistol","M_Primary","WEAPON / PAINTED SHELL"],
		["weapons","pistol","M_Frame","WEAPON / TITANIUM FRAME"],
		["characters","tensor","M_Primary","ROBOT / PAINTED ARMOUR"],
		["characters","tensor","M_Frame","ROBOT / MATTE CHASSIS"],
		["architecture","bunker","M_Primary","ARCHITECTURE / WHITE MATTE"],
		["architecture","bunker","M_Secondary","ARCHITECTURE / GREY MATTE"],
		["architecture","bunker","M_Frame","ARCHITECTURE / FRAME MATTE"],
		["architecture","bunker","M_Joint","ARCHITECTURE / JOINT MATTE"]])
	for index in entries.size():
		var entry: Array = entries[index]
		var model := Assets.model(entry[0],entry[1])
		var material: Material
		for mesh: MeshInstance3D in model.find_children("*","MeshInstance3D",true,false):
			for surface in mesh.mesh.get_surface_count():
				var candidate := mesh.get_active_material(surface)
				if candidate != null and Assets.material_role(candidate.resource_name)==entry[2]: material=candidate
		assert(material!=null,"Missing authored material: "+entry[3])
		var ball := MeshInstance3D.new()
		var sphere := SphereMesh.new()
		sphere.radius=.48
		sphere.height=.96
		ball.mesh=sphere
		ball.material_override=material
		ball.position=Vector3((index%4-1.5)*1.65,1.65-floori(index/4.0)*1.65,0)
		root.add_child(ball)
		var label := Label3D.new()
		label.text=entry[3]
		label.position=ball.position+Vector3(0,-.66,0)
		label.pixel_size=.002
		label.font_size=22
		root.add_child(label)
		print("REFLECTION_MATERIAL ",entry[3]," type=",material.get_class())
		model.free()
	var camera := Camera3D.new()
	camera.position=Vector3(0,-.825,6)
	camera.projection=Camera3D.PROJECTION_ORTHOGONAL
	camera.size=7.5
	camera.current=true
	root.add_child(camera)
	await create_timer(3).timeout
	await RenderingServer.frame_post_draw
	root.get_texture().get_image().save_png("res://reports/reflection-materials.png")
	print("REFLECTION_MATERIALS_COMPLETE")
	quit()
