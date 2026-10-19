class_name ScoreboardDisplay
extends Node
var game
var title: Label
var score: Label
var clock_label: Label
var refresh := 0.0
var viewport: SubViewport
var marquee_viewport: SubViewport
var marquee: Label
var notice_text := ""
var notice_time := 0.0

func install(jumbotron: Node3D, match_controller):
	game = match_controller
	jumbotron.add_child(self)
	viewport = SubViewport.new()
	viewport.size = Vector2i(1024,576)
	viewport.render_target_update_mode = SubViewport.UPDATE_ONCE
	viewport.disable_3d = true
	add_child(viewport)
	var background := ColorRect.new()
	background.color = Color("0b1119")
	background.size = Vector2(1024,576)
	viewport.add_child(background)
	title = readout(viewport,Vector2(40,38),Vector2(944,90),48,Color("6fe5ea"))
	score = readout(viewport,Vector2(40,166),Vector2(944,174),110,Color("f3f6f7"))
	clock_label = readout(viewport,Vector2(40,396),Vector2(944,90),56,Color("b9c9d1"))
	var material := StandardMaterial3D.new()
	material.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
	material.albedo_texture = viewport.get_texture()
	marquee_viewport = SubViewport.new()
	marquee_viewport.size = Vector2i(1024,128)
	marquee_viewport.disable_3d = true
	marquee_viewport.render_target_update_mode = SubViewport.UPDATE_ONCE
	add_child(marquee_viewport)
	var band := ColorRect.new()
	band.color = Color("0b1119")
	band.size = Vector2(1024,128)
	marquee_viewport.add_child(band)
	marquee = readout(marquee_viewport,Vector2(24,30),Vector2(976,72),36,Color("6fe5ea"))
	var marquee_material := StandardMaterial3D.new()
	marquee_material.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
	marquee_material.albedo_texture = marquee_viewport.get_texture()
	game.message.connect(show_notice)
	for mesh in jumbotron.find_children("*","MeshInstance3D",true,false):
		for surface in mesh.mesh.get_surface_count():
			var source = mesh.get_active_material(surface)
			if source != null and Assets.material_role(source.resource_name) == "M_Screen":
				mesh.set_surface_override_material(surface,material)
			elif source != null and Assets.material_role(source.resource_name) == "M_Marquee":
				mesh.set_surface_override_material(surface,marquee_material)

func show_notice(text: String) -> void:
	# Personal pickup confirmations belong to the HUD, arena/objective notices to this band.
	if not text.begins_with("ARENA / ") and game.phase != "Finished": return
	notice_text = text
	notice_time = 10.0
	refresh = 0.0

func readout(parent: Node,at: Vector2,dimensions: Vector2,font_size: int,color: Color) -> Label:
	var label := Label.new()
	label.position = at
	label.size = dimensions
	label.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	label.add_theme_font_size_override("font_size",font_size)
	label.add_theme_color_override("font_color",color)
	parent.add_child(label)
	return label

func _process(dt):
	notice_time = maxf(0.0,notice_time-dt)
	refresh -= dt
	if refresh > 0 or game == null: return
	var camera: Camera3D = game.camera
	var distance := camera.global_position.distance_to(get_parent().global_position) if camera != null else 0.0
	refresh = 0.25 if distance < 60.0 else 1.0
	title.text = "KYLR   /   " + game.match_type
	score.text = game.score_text()
	clock_label.text = game.clock_text() if game.phase == "Active" else game.phase.to_upper()
	if game.phase == "Finished" and not game.result.is_empty(): clock_label.text = game.result.title
	marquee.text = notice_text if notice_time > 0.0 else game.map.config.title.to_upper() + "   /   " + game.phase.to_upper()
	viewport.render_target_update_mode = SubViewport.UPDATE_ONCE
	marquee_viewport.render_target_update_mode = SubViewport.UPDATE_ONCE
