extends SceneTree

func _initialize(): call_deferred("capture")

func capture():
	var canvas := Control.new()
	root.add_child(canvas)
	var background := ColorRect.new()
	background.color = Color("17202b")
	background.size = Vector2(1280, 720)
	canvas.add_child(background)
	var weapons := ["pistol", "rifle", "minigun", "flamethrower", "emp_gun", "lightning_gun", "rocket_launcher", "flak_cannon", "bio_rifle", "grenade_launcher", "rifle", "rocket_launcher", "lightning_gun", "flamethrower"]
	for i in weapons.size():
		var center := Vector2(160 + (i % 4) * 320, 75 + (i / 4) * 170)
		for state in 2:
			var reticle := WeaponCrosshair.new()
			canvas.add_child(reticle)
			reticle.size = Vector2(64, 64)
			reticle.position = center + Vector2(-90 if state == 0 else 26, -32)
			reticle.configure(weapons[i], i >= 10)
			if i == 11: reticle.lock_progress = float(state)
			reticle.contraction = float(state)
			reticle.set_process(false)
			reticle.queue_redraw()
			var state_label := Label.new()
			canvas.add_child(state_label)
			state_label.text = "NORMAL" if state == 0 else "ON TARGET"
			state_label.add_theme_font_size_override("font_size", 13)
			state_label.position = reticle.position + Vector2(-8, 95)
		var label := Label.new()
		canvas.add_child(label)
		label.text = weapons[i].replace("_", " ").to_upper() + (" / SECONDARY" if i >= 10 else "")
		label.position = center + Vector2(-135, -65)
	await process_frame
	await RenderingServer.frame_post_draw
	# Every catalogued mode must draw visible strokes in both eligibility states.
	var picture := root.get_texture().get_image()
	for node in canvas.get_children():
		if not node is WeaponCrosshair: continue
		var bright := 0
		for x in range(int(node.position.x), int(node.position.x + 64)):
			for y in range(int(node.position.y), int(node.position.y + 64)):
				if picture.get_pixel(x,y).r > 0.8: bright += 1
		if bright < 8:
			push_error("Missing reticle pixels: " + str(node.profile))
			quit(1)
			return
	print("CROSSHAIRS_RENDERED 14 variants, 28 states")
	root.get_texture().get_image().save_png("res://reports/crosshairs.png")
	canvas.queue_free()
	await process_frame
	quit()
