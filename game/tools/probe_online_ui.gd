extends SceneTree
var app
func _initialize(): run.call_deferred()
func capture(name: String):
	print("CAPTURE_STAGE ",name)
	for frame in 20: await process_frame
	await RenderingServer.frame_post_draw
	root.get_texture().get_image().save_png("res://reports/online/ui_"+name+".png")
func run():
	app = load("res://scripts/core/app.gd").new()
	root.add_child(app)
	DisplayServer.window_set_mode(DisplayServer.WINDOW_MODE_WINDOWED)
	DisplayServer.window_set_size(Vector2i(1280,720))
	app.online_ui.login(true)
	await capture("register")
	var username := "UIProbe"+str(Time.get_ticks_msec())
	var session: Dictionary = await app.api.sign_in(username,"LocalProbePassword1",username)
	if session.has("error"): push_error(session.error.message); quit(1); return
	app.online_ui.lobby()
	await capture("lobby")
	app.online_ui.draft = app.api.player.loadout.duplicate()
	app.online_ui.customise()
	await capture("heads")
	for control in app.ui.page.find_children("*","Button",true,false):
		if control.text == "Raptor": control.pressed.emit(); break
	assert(app.online_ui.draft.head == "raptor")
	for control in app.ui.page.find_children("*","Button",true,false):
		if control.text == "REVERT": control.pressed.emit(); break
	assert(app.online_ui.draft.head == app.api.player.loadout.head)
	app.online_ui.category = "Emotes"
	app.online_ui.customise()
	app.online_ui.portrait_emote("victory_gangnam_style")
	await capture("emotes")
	app.online_ui.category = "Armor Colors"
	app.online_ui.draft.primary = "red"
	app.online_ui.draft.secondary = "cyan"
	app.online_ui.customise()
	await capture("colors")
	for control in app.ui.page.find_children("*","Button",true,false):
		if control.text == "SAVE": control.pressed.emit(); break
	while app.online_ui.busy: await process_frame
	assert(app.api.player.loadout.primary == "red" and app.api.player.loadout.secondary == "cyan")
	DisplayServer.window_set_size(Vector2i(800,600))
	app.online_ui.lobby()
	await capture("narrow_lobby")
	app.online_ui.category = "Heads"
	app.online_ui.customise()
	await capture("narrow_heads")
	await app.api.logout()
	print("ONLINE_UI registration/loadout/logout passed")
	app.request_quit()
