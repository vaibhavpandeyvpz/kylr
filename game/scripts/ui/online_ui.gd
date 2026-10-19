class_name OnlineUI
extends Node
var app
var ui: ArenaUI
var api: OnlineClient
var operation := 0
var request_id := ""
var selected_type := "DM"
var transport: OnlineTransport
var status: Label
var draft: Dictionary = {}
var category := "Heads"
var busy := false
var results_countdown: Label
var thumbnails: Dictionary = {}
var portrait_viewport: SubViewport
var portrait_robot: Node3D
var portrait_animator: AnimationPlayer
var portrait_victory := ""
var canceled_deadline := 0
var lobby_notice := ""

func _ready(): set_process(true)

func open():
	operation += 1
	var current := operation
	ui.clear_page("online_loading")
	var col := ui.column(64,80,450)
	ui.label(col,"ONLINE MULTIPLAYER",32)
	ui.label(col,"Restoring account…",20)
	await api.restore()
	if current != operation: return
	if api.player.is_empty(): login()
	else: lobby()

func field(parent: Node, caption: String, secret := false) -> LineEdit:
	ui.label(parent,caption,16,ui.MUTED)
	var edit := LineEdit.new()
	edit.accessibility_name = caption
	edit.secret = secret
	edit.custom_minimum_size.y = 44
	parent.add_child(edit)
	return edit

func login(register := false):
	ui.clear_page("online_account")
	var col := ui.column(64,45,440,660)
	ui.label(col,"CREATE ACCOUNT" if register else "SIGN IN",36)
	ui.label(col,"KYLR account / server may take a moment to wake",16,ui.MUTED)
	var username := field(col,"Username / 3–24 letters, digits, . or _")
	username.max_length = 24
	var display: LineEdit
	if register: display = field(col,"Display name / 1–20 letters, digits, . or _"); display.max_length = 20
	var password := field(col,"Password / at least 12 characters",true)
	password.max_length = 256
	var confirmation: LineEdit
	if register:
		confirmation = field(col,"Confirm password",true)
		confirmation.max_length = 256
	status = ui.label(col,"",17,ui.ACTION)
	var submit: Button = ui.button(col,"REGISTER" if register else "SIGN IN",func():
		if busy: return
		if register and password.text != confirmation.text:
			status.text = "The passwords must match."
			return
		busy = true
		var current := operation
		status.text = "Creating account…" if register else "Signing in…"
		var response := await api.sign_in(username.text,password.text,display.text if register else "",register)
		if is_instance_valid(password): password.clear()
		if is_instance_valid(confirmation): confirmation.clear()
		busy = false
		if current != operation: return
		if response.has("error"): status.text = response.error.message
		else: lobby(),true)
	password.text_submitted.connect(func(_text): submit.pressed.emit())
	ui.button(col,"ALREADY HAVE AN ACCOUNT / SIGN IN" if register else "CREATE ACCOUNT",func(): if not busy: login(not register))
	ui.button(col,"BACK",func(): operation += 1; ui.main_menu())
	username.grab_focus()

func lobby():
	ui.clear_page("online_lobby")
	request_id = ""
	selected_type = ["DM","TDM","CTF"][int(app.prefs.values.online_type)]
	app.preview_loadout(api.player.loadout)
	portrait(ui.column(500,55,400,530),api.player.loadout)
	var col := ui.column(64,55,410,620)
	ui.label(col,"ONLINE / "+api.player.display_name,30)
	ui.label(col,"Choose a match",20,ui.MUTED)
	if lobby_notice != "": ui.label(col,lobby_notice,17,ui.ACTION)
	for type in ["DM","TDM","CTF"]:
		var detail: String = {"DM":"Every robot for itself","TDM":"Two teams / shared kill score","CTF":"Two teams / capture the enemy flag"}[type]
		ui.button(col,type+"\n"+detail,func(): app.prefs.values.online_type = ["DM","TDM","CTF"].find(type); app.prefs.save(); lobby(),selected_type == type)
	ui.label(col,"2–10 players / no bots\n30 minutes / target adjusts with the roster",16,ui.MUTED)
	ui.button(col,"CUSTOMISE",func(): draft = api.player.loadout.duplicate(); category = "Heads"; customise())
	ui.button(col,"SETTINGS",func(): ui.settings(lobby))
	ui.button(col,"SIGN OUT",func():
		operation += 1
		await api.logout()
		login())
	ui.button(col,"BACK",func(): operation += 1; ui.main_menu())
	var action := ui.column(940,565,280,130)
	ui.button(action,"PLAY",search,true)
	if not api.remembered: ui.label(action,"Session stays in memory on this device.",14,ui.MUTED)

func searching(text: String):
	ui.clear_page("online_search")
	var col := ui.column(64,100,430,430)
	ui.label(col,selected_type+" / ONLINE",32)
	status = ui.label(col,text,24,ui.ACTION)
	ui.label(col,"Finding a game server. First startup can take a few minutes.\nYou can cancel before or during admission.",18,ui.MUTED)
	ui.button(col,"CANCEL",cancel)

func search():
	lobby_notice = ""
	operation += 1
	var current := operation
	searching("Searching")
	var response := await api.request("/v1/matches",HTTPClient.METHOD_POST,{"type":selected_type})
	if response.has("request_id") and current != operation:
		await api.request("/v1/matches/"+response.request_id,HTTPClient.METHOD_DELETE)
		return
	if current != operation: return
	if response.has("error"): problem(response.error.message); return
	request_id = response.request_id
	var startup_seconds := clampi(int(ceil(float(response.get("timeout_seconds",180)))),1,600)
	var deadline := Time.get_ticks_msec()+startup_seconds*1000+15000
	while current == operation and Time.get_ticks_msec() < deadline:
		var result := await api.request("/v1/matches/"+request_id)
		if current != operation: return
		if result.has("error"): problem(result.error.message); return
		status.text = result.state
		if result.state == "Ready": connect_game(result.assignment); return
		if result.state == "Canceled": lobby(); return
		await get_tree().create_timer(1.0).timeout
	if current == operation: await cancel_request(); problem("Matchmaking timed out. Retry for a fresh ticket.")

func connect_game(assignment: Dictionary):
	transport = OnlineTransport.new()
	transport.name = "OnlineTransport"
	get_tree().root.add_child(transport)
	transport.progress.connect(func(text): if is_instance_valid(status): status.text = text)
	transport.admitted.connect(enter_match)
	transport.loading.connect(func():
		results_countdown = null
		if app.match_node:
			app.match_node = null
			ui.retire_control(ui.hud)
			ui.hud = null
			ui.clear_page("online_loading")
			ui.label(ui.column(64,80,450),"Loading next map…",28))
	transport.failed.connect(problem)
	transport.connect_match(assignment)

func enter_match(game: ArenaMatch):
	if app.preview: app.preview.free(); app.preview = null
	app.match_node = game
	game.third_person = app.prefs.values.third_person
	game.fov = app.prefs.values.fov
	game.reduced_motion = app.prefs.values.reduced_motion
	app.prefs.apply_rendering(app)
	game.message.connect(ui.show_notice)
	game.completed.connect(func(): ui.results(); show_next_map())
	ui.start_hud()
	if game.phase == "Finished": ui.results(); show_next_map()

func show_next_map():
	if not transport or not ui.page: return
	if app.match_node.result.get("canceled",false): canceled_deadline = Time.get_ticks_msec()+3000
	results_countdown = ui.results_status

func _process(_dt):
	if portrait_viewport:
		portrait_viewport.render_target_update_mode = SubViewport.UPDATE_ALWAYS if ui.screen in ["online_lobby","customise"] else SubViewport.UPDATE_DISABLED
		if ui.screen in ["online_lobby","customise"] and not app.prefs.values.reduced_motion: portrait_robot.rotation.y += _dt*0.15
	if is_instance_valid(results_countdown) and is_instance_valid(transport) and is_instance_valid(app.match_node):
		results_countdown.text = app.match_node.result.get("reason","Match canceled")+" / Returning to lobby…" if app.match_node.result.get("canceled",false) else "Next map in %d seconds" % maxi(0,ceili(transport.next_map))
	if canceled_deadline > 0 and Time.get_ticks_msec() >= canceled_deadline:
		canceled_deadline = 0
		lobby_notice = app.match_node.result.get("reason","Match canceled.") if is_instance_valid(app.match_node) else "Match canceled."
		cancel()

func cancel_request():
	var id := request_id
	request_id = ""
	if id != "": await api.request("/v1/matches/"+id,HTTPClient.METHOD_DELETE)

func dispose_transport():
	canceled_deadline = 0
	results_countdown = null
	if is_instance_valid(transport):
		transport.close()
		get_tree().root.remove_child(transport)
		transport.queue_free()
	transport = null
	app.match_node = null
	ui.retire_control(ui.hud)
	ui.hud = null
	if not app.preview: app.make_preview()

func cancel():
	operation += 1
	dispose_transport()
	await cancel_request()
	lobby()

func problem(text: String):
	operation += 1
	dispose_transport()
	cancel_request()
	ui.clear_page("online_failed")
	var col := ui.column(64,100,450,480)
	ui.label(col,"COULD NOT JOIN",32)
	ui.label(col,text,20,ui.ACTION)
	ui.button(col,"RETRY",search,true)
	ui.button(col,"RETURN TO LOBBY",func():
		if api.player.is_empty(): login()
		else: lobby())

func customise():
	ui.clear_page("customise")
	app.preview_loadout(draft)
	portrait(ui.column(300,45,480,560),draft)
	var categories := ui.column(32,40,240,560)
	ui.label(categories,"CUSTOMISE",30)
	ui.label(categories,api.player.display_name,18,ui.MUTED)
	for value in ["Heads","Emotes","Armor Colors"]:
		ui.button(categories,value,func(): category = value; customise(),category == value)
	ui.label(categories,"Preview changes immediately.\nSave updates your account.",16,ui.MUTED)
	ui.button(categories,"REVERT",func(): draft = api.player.loadout.duplicate(); customise())
	ui.button(categories,"BACK",back_customise)
	var choices := ui.column(850,40,390,620)
	ui.label(choices,category.to_upper(),26)
	if category == "Armor Colors":
		for key in ["primary","secondary"]:
			ui.label(choices,key.capitalize()+" / "+draft[key],20)
			var colors := GridContainer.new()
			colors.columns = 4
			choices.add_child(colors)
			for color_id in OnlineTransport.PALETTE:
				var swatch := ui.button(colors,"●" if draft[key] == color_id else "",func(): draft[key] = color_id; customise())
				swatch.custom_minimum_size = Vector2(78,44)
				swatch.tooltip_text = color_id.capitalize()
				var style := StyleBoxFlat.new()
				style.bg_color = Color(OnlineTransport.PALETTE[color_id])
				style.border_color = Color.WHITE
				style.set_border_width_all(3 if draft[key] == color_id else 1)
				swatch.add_theme_stylebox_override("normal",style)
	else:
		var grid := GridContainer.new()
		grid.columns = 2
		choices.add_child(grid)
		var character := ContentRegistry.character("tensor")
		var key := "head" if category == "Heads" else "emote"
		for id in character.heads if key == "head" else character.emotes:
			var tile := VBoxContainer.new()
			grid.add_child(tile)
			var image := TextureRect.new()
			image.custom_minimum_size = Vector2(170,94)
			image.expand_mode = TextureRect.EXPAND_IGNORE_SIZE
			image.stretch_mode = TextureRect.STRETCH_KEEP_ASPECT_CENTERED
			tile.add_child(image)
			image.texture = silhouette(tile,id,key == "head")
			var title: String = id.trim_prefix("victory_").replace("_"," ").capitalize()
			var choice := ui.button(tile,title+(" / preview" if draft[key] == id else "")+(" / saved" if api.player.loadout[key] == id else ""),func():
				draft[key] = id
				customise()
				if key == "emote": portrait_emote(id))
			choice.add_theme_font_size_override("font_size",14)
			choice.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	status = ui.label(choices,"Unsaved changes" if draft != api.player.loadout else "Saved loadout",17,ui.ACTION)
	ui.button(choices,"SAVE",func():
		if busy: return
		busy = true
		status.text = "Saving…"
		for control in ui.page.find_children("*","Button",true,false): control.disabled = true
		var response := await api.save_loadout(draft.duplicate(true))
		busy = false
		if ui.screen != "customise": return
		if response.has("error"):
			status.text = response.error.message
			for control in ui.page.find_children("*","Button",true,false): control.disabled = false
		else: draft = api.player.loadout.duplicate(); customise(),true)

func back_customise():
	if busy: return
	if draft == api.player.loadout: lobby(); return
	var confirm := ConfirmationDialog.new()
	confirm.title = "Discard unsaved changes?"
	confirm.dialog_text = "Your saved account loadout will be restored."
	confirm.ok_button_text = "Discard"
	ui.page.add_child(confirm)
	confirm.confirmed.connect(lobby)
	confirm.popup_centered(Vector2i(420,170))

func silhouette(parent: Node, id: String, head_only: bool) -> Texture:
	var cache_id: String = id if head_only else id+"/"+draft.head
	if thumbnails.has(cache_id): return thumbnails[cache_id]
	var viewport := SubViewport.new()
	viewport.size = Vector2i(192,128)
	viewport.transparent_bg = true
	viewport.own_world_3d = true
	viewport.render_target_update_mode = SubViewport.UPDATE_ONCE
	add_child(viewport)
	var model := Assets.model("characters","tensor")
	viewport.add_child(model)
	Assets.paint(model,Color.WHITE,Color.WHITE,id if head_only else draft.head)
	var bounds := AABB()
	var initialized := false
	for mesh in model.find_children("*","MeshInstance3D",true,false):
		if head_only and not String(mesh.name).begins_with("SK_TensorHead"): mesh.hide()
		if mesh.visible:
			var extent: AABB = mesh.global_transform*mesh.get_aabb()
			bounds = bounds.merge(extent) if initialized else extent
			initialized = true
		var material := StandardMaterial3D.new()
		material.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
		material.albedo_color = Color("b9c9d1")
		mesh.material_override = material
	if not head_only:
		var skeleton := Assets.find(model,"Skeleton3D")
		var animator := AnimationPlayer.new()
		skeleton.get_parent().add_child(animator)
		var library := AnimationLibrary.new()
		var clip := Assets.animation("common/"+id)
		if clip:
			library.add_animation("pose",clip)
			animator.add_animation_library("",library)
			animator.play("pose")
			animator.seek(minf(clip.length*0.3,1.5),true)
			animator.pause()
	var camera := Camera3D.new()
	viewport.add_child(camera)
	var center := bounds.get_center() if head_only else Vector3(0,0.85,0)
	camera.position = center+Vector3(0,0,3)
	camera.look_at(center)
	camera.projection = Camera3D.PROJECTION_ORTHOGONAL
	camera.size = maxf(bounds.size.y,bounds.size.x/1.5)*1.3 if head_only else 2.3
	thumbnails[cache_id] = viewport.get_texture()
	return thumbnails[cache_id]

func portrait(parent: Node, loadout: Dictionary):
	if portrait_viewport == null:
		portrait_viewport = SubViewport.new()
		portrait_viewport.size = Vector2i(480,560)
		portrait_viewport.own_world_3d = true
		portrait_viewport.transparent_bg = true
		add_child(portrait_viewport)
		portrait_robot = Assets.model("characters","tensor")
		portrait_viewport.add_child(portrait_robot)
		var skeleton := Assets.find(portrait_robot,"Skeleton3D")
		portrait_animator = AnimationPlayer.new()
		skeleton.get_parent().add_child(portrait_animator)
		var library := AnimationLibrary.new()
		var idle := Assets.animation("common/idle")
		if idle:
			idle.loop_mode = Animation.LOOP_NONE
			library.add_animation("common_idle",idle)
		portrait_animator.add_animation_library("",library)
		portrait_animator.animation_finished.connect(func(clip):
			if clip == "common_idle": portrait_emote(portrait_victory)
			else: portrait_animator.play("common_idle",0.2))
		portrait_animator.play("common_idle")
		var camera := Camera3D.new()
		portrait_viewport.add_child(camera)
		camera.position = Vector3(0,1.1,3.4)
		camera.look_at(Vector3(0,0.88,0))
		camera.fov = 34
		ArenaLighting.install(portrait_viewport,true)
		app.prefs.apply_rendering(portrait_viewport)
	Assets.paint(portrait_robot,Color(OnlineTransport.PALETTE[loadout.primary]),Color(OnlineTransport.PALETTE[loadout.secondary]),loadout.head)
	portrait_victory = app.preview_victory(loadout.get("emote",""))
	var texture := TextureRect.new()
	texture.texture = portrait_viewport.get_texture()
	texture.expand_mode = TextureRect.EXPAND_IGNORE_SIZE
	texture.stretch_mode = TextureRect.STRETCH_KEEP_ASPECT_CENTERED
	texture.custom_minimum_size.y = 460
	texture.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	parent.add_child(texture)

func shutdown_views():
	# Detach geometry before freeing materials used by cached thumbnail views.
	# Let the renderer consume that change before retiring the viewports.
	var retiring: Array[Material] = []
	for child in get_children():
		if child is SubViewport:
			child.render_target_update_mode = SubViewport.UPDATE_DISABLED
			for mesh in child.find_children("*","MeshInstance3D",true,false):
				if mesh.material_override: retiring.append(mesh.material_override)
				mesh.mesh = null
	await get_tree().process_frame
	if DisplayServer.get_name() != "headless": await RenderingServer.frame_post_draw
	for child in get_children():
		if child is SubViewport:
			child.queue_free()
	portrait_viewport = null
	thumbnails.clear()
	await get_tree().process_frame

func portrait_emote(id: String):
	id = app.preview_victory(id)
	portrait_victory = id
	var library := portrait_animator.get_animation_library("")
	if not library.has_animation(id):
		var clip := Assets.animation("common/"+id)
		if clip == null: return
		clip.loop_mode = Animation.LOOP_NONE
		library.add_animation(id,clip)
	portrait_animator.play(id,0.2)
