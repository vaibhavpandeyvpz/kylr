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
var portrait_viewport: SubViewport
var portrait_robot: Node3D
var portrait_animator: AnimationPlayer
var portrait_victory := ""
var canceled_deadline := 0
var lobby_notice := ""
var armor_channel := "primary"
var portrait_turntable: Node3D
var waiting_for_players := false
var connection_steps: Array[Label] = []
var roster_status: Label
var roster_names: Label
var roster_stamp := ""

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
	var view := OnlineLayout.frame(ui,"Create account" if register else "Sign in","Your identity across every match")
	var info := OnlineLayout.column(view.body,0.8)
	ui.label(info,"BUILT TO OUTLAST.",40)
	ui.label(info,"One account. Your robot. Every arena.",22,ui.ACTION)
	var explanation := ui.label(info,"Save your head, armor finishes and victory animation. Join dedicated servers for Deathmatch, Team Deathmatch and Capture the Flag.",18,ui.MUTED)
	explanation.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	var col := OnlineLayout.column(view.body,1.0)
	ui.label(col,"ACCOUNT DETAILS",16,ui.MUTED)
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
	var submit: Button = OnlineLayout.action(ui,view.footer,"Create account" if register else "Sign in",func():
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
	OnlineLayout.action(ui,view.footer,"Back",func(): operation += 1; ui.main_menu()).move_to_front()
	OnlineLayout.action(ui,view.footer,"Sign in instead" if register else "Create account",func(): if not busy: login(not register)).move_to_front()
	var gap := OnlineLayout.spacer(view.footer)
	view.footer.move_child(gap,view.footer.get_child_count()-2)
	view.footer.move_child(submit,view.footer.get_child_count()-1)
	OnlineLayout.layout(ui)
	username.grab_focus()

func lobby():
	ui.clear_page("online_lobby")
	request_id = ""
	selected_type = ["DM","TDM","CTF"][int(app.prefs.values.online_type)]
	var view := OnlineLayout.frame(ui,"Deploy",api.player.display_name+" / Ready to play")
	var choices := OnlineLayout.column(view.body,0.85)
	ui.label(choices,"SELECT MATCH TYPE",16,ui.MUTED)
	if lobby_notice != "": ui.label(choices,lobby_notice,16,ui.ACTION)
	for type in ["DM","TDM","CTF"]:
		var title: String = {"DM":"Deathmatch","TDM":"Team Deathmatch","CTF":"Capture the Flag"}[type]
		var detail: String = {"DM":"Every robot for itself.","TDM":"Two teams. One shared kill score.","CTF":"Steal the enemy flag and defend your base."}[type]
		var card := ui.button(choices,"",func(): app.prefs.values.online_type = ["DM","TDM","CTF"].find(type); app.prefs.save(); lobby())
		card.custom_minimum_size.y = 104
		MenuSkin.apply_button(card,false,type == selected_type)
		var inside := VBoxContainer.new()
		inside.mouse_filter = Control.MOUSE_FILTER_IGNORE
		card.add_child(inside)
		inside.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
		inside.offset_left = 24; inside.offset_right = -24; inside.offset_top = 16; inside.offset_bottom = -12
		ui.label(inside,type+"  /  "+title,26)
		ui.label(inside,detail,16,ui.MUTED)
	ui.label(choices,"2–10 PLAYERS   /   HUMAN-ONLY MATCHES",14,ui.ACTION)
	ui.label(choices,"30 minutes · score target scales with the roster",16,ui.MUTED)
	portrait(OnlineLayout.column(view.body,1.15),api.player.loadout)
	OnlineLayout.action(ui,view.footer,"Back",func(): operation += 1; ui.main_menu())
	OnlineLayout.action(ui,view.footer,"Sign out",func(): operation += 1; await api.logout(); login())
	OnlineLayout.spacer(view.footer)
	OnlineLayout.action(ui,view.footer,"Settings",func(): ui.settings(lobby))
	OnlineLayout.action(ui,view.footer,"Customise",func(): draft = api.player.loadout.duplicate(); category = "Heads"; customise())
	OnlineLayout.action(ui,view.footer,"Play",search,true)
	OnlineLayout.layout(ui)

func connection_screen(waiting: bool, text: String):
	ui.clear_page("online_waiting" if waiting else "online_search")
	connection_steps.clear()
	roster_stamp = ""
	var view := OnlineLayout.frame(ui,"Match staging",selected_type+" / "+api.player.display_name)
	var col := OnlineLayout.column(view.body,0.9)
	var panel := PanelContainer.new()
	panel.add_theme_stylebox_override("panel",MenuSkin.surface())
	col.add_child(panel)
	var content := VBoxContainer.new()
	content.add_theme_constant_override("separation",24)
	panel.add_child(content)
	ui.label(content,"CONNECTED" if waiting else "LIVE CONNECTION",14,MenuSkin.SUCCESS if waiting else ui.ACTION)
	status = ui.label(content,text,36,ui.ACTION)
	status.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	var help := ui.label(content,"Your place is reserved. The match starts when at least two players are connected." if waiting else "Finding a dedicated server and reserving your place. First startup can take a few minutes.",18,ui.MUTED)
	help.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	for title in ["Find a server","Connect securely","Gather players"]:
		var row := HBoxContainer.new()
		content.add_child(row)
		var name_label := ui.label(row,title,17)
		name_label.size_flags_horizontal = Control.SIZE_EXPAND_FILL
		connection_steps.append(ui.label(row,"Pending",14,ui.MUTED))
	if waiting:
		roster_status = ui.label(col,"",28)
		roster_names = ui.label(col,"",18,ui.MUTED)
		roster_names.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
		update_waiting_roster()
	else:
		roster_status = null
		roster_names = null
	set_connection_status(text,2 if waiting else 0)
	portrait(OnlineLayout.column(view.body,1.1),api.player.loadout)
	ui.label(view.footer,"You can leave at any time.",14,ui.MUTED)
	OnlineLayout.spacer(view.footer)
	OnlineLayout.action(ui,view.footer,"Leave server" if waiting else "Cancel search",cancel)
	OnlineLayout.layout(ui)

func set_connection_status(text: String, step := -1):
	if not is_instance_valid(status): return
	status.text = text
	if step < 0: step = 1 if is_instance_valid(transport) or text == "Ready" else 0
	for index in connection_steps.size():
		var label := connection_steps[index]
		if not is_instance_valid(label): continue
		label.text = "Complete" if index < step else "In progress" if index == step else "Pending"
		label.add_theme_color_override("font_color",MenuSkin.SUCCESS if index < step else ui.ACTION if index == step else ui.MUTED)

func update_waiting_roster():
	if not is_instance_valid(roster_status) or not is_instance_valid(app.match_node): return
	var names: Array[String] = []
	for robot in app.match_node.robots:
		if is_instance_valid(robot): names.append(robot.display_name)
	var stamp := "\n".join(names)
	if stamp == roster_stamp and not roster_status.text.is_empty(): return
	roster_stamp = stamp
	roster_status.text = "%02d / 02 players to start" % names.size()
	roster_names.text = stamp if not names.is_empty() else api.player.display_name

func searching(text: String):
	connection_screen(false,text)

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
		set_connection_status(result.state)
		if result.state == "Ready": connect_game(result.assignment); return
		if result.state == "Canceled": lobby(); return
		await get_tree().create_timer(1.0).timeout
	if current == operation: await cancel_request(); problem("Matchmaking timed out. Retry for a fresh ticket.")

func connect_game(assignment: Dictionary):
	app.retire_preview()
	transport = OnlineTransport.new()
	transport.name = "OnlineTransport"
	get_tree().root.add_child(transport)
	transport.progress.connect(func(text): set_connection_status(text,1))
	transport.admitted.connect(enter_match)
	transport.loading.connect(func():
		results_countdown = null
		waiting_for_players = false
		app.loading_screen.begin("Preparing match…")
		if app.match_node:
			app.match_node = null
			ui.retire_control(ui.hud)
			ui.hud = null
			ui.clear_page("online_loading")
			ui.label(ui.column(64,80,450),"Loading next map…",28))
	transport.failed.connect(problem)
	transport.connect_match(assignment)

func enter_match(game: ArenaMatch):
	app.retire_preview()
	app.match_node = game
	game.third_person = app.prefs.values.third_person
	game.fov = app.prefs.values.fov
	game.reduced_motion = app.prefs.values.reduced_motion
	app.prefs.apply_rendering(app)
	game.message.connect(ui.show_notice)
	game.completed.connect(func(): ui.results(); show_next_map())
	if game.phase == "Waiting":
		waiting_for_players = true
		game.hide()
		app.loading_screen.finish()
		connection_screen(true,"Waiting for players")
	else:
		reveal_match(game)

func reveal_match(game: ArenaMatch):
	waiting_for_players = false
	var current := operation
	app.loading_screen.begin("Preparing match…")
	game.show()
	game.camera.current = true
	await app.loading_screen.paint()
	await app.prepare_rendering()
	if current != operation or not is_instance_valid(game) or app.match_node != game: return
	app.loading_screen.finish()
	ui.start_hud()
	if game.phase == "Finished": ui.results(); show_next_map()

func show_next_map():
	if not transport or not ui.page: return
	if app.match_node.result.get("canceled",false): canceled_deadline = Time.get_ticks_msec()+3000
	results_countdown = ui.results_status

func _process(_dt):
	if waiting_for_players: update_waiting_roster()
	if waiting_for_players and is_instance_valid(app.match_node) and app.match_node.phase != "Waiting": reveal_match(app.match_node)
	if is_instance_valid(portrait_viewport):
		var active := ui.screen in ["online_lobby","customise","online_search","online_waiting"]
		portrait_viewport.render_target_update_mode = SubViewport.UPDATE_ALWAYS if active else SubViewport.UPDATE_DISABLED
		portrait_viewport.process_mode = Node.PROCESS_MODE_INHERIT if active else Node.PROCESS_MODE_DISABLED
		if active and not app.prefs.values.reduced_motion: portrait_turntable.rotation.y += _dt*0.10
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
	waiting_for_players = false
	app.loading_screen.finish()
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
	if not is_instance_valid(app.preview): app.make_preview()

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
	var view := OnlineLayout.frame(ui,"Could not join",selected_type+" / Connection interrupted")
	var col := OnlineLayout.column(view.body)
	var message := ui.label(col,text,24,MenuSkin.DANGER)
	message.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	var help := ui.label(col,"Try again or return to the lobby. Your account and saved loadout are unchanged.",18,ui.MUTED)
	help.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	OnlineLayout.action(ui,view.footer,"Return to lobby",func():
		if api.player.is_empty(): login()
		else: lobby())
	OnlineLayout.spacer(view.footer)
	OnlineLayout.action(ui,view.footer,"Retry",search,true)
	OnlineLayout.layout(ui)

func customise():
	ui.clear_page("customise")
	var view := OnlineLayout.frame(ui,"Customise",api.player.display_name+" / Tensor platform")
	portrait(OnlineLayout.column(view.body,1.0),draft)
	var choices := OnlineLayout.column(view.body,1.15)
	var tabs := HBoxContainer.new()
	tabs.add_theme_constant_override("separation",8)
	choices.add_child(tabs)
	for value in ["Heads","Emotes","Armor Colors"]:
		var tab := ui.button(tabs,value,func(): category = value; customise())
		tab.size_flags_horizontal = Control.SIZE_EXPAND_FILL
		tab.alignment = HORIZONTAL_ALIGNMENT_CENTER
		tab.add_theme_font_size_override("font_size",16)
		MenuSkin.apply_button(tab,false,category == value)
	var key := "head" if category == "Heads" else "emote"
	var items: Array = ContentRegistry.character("tensor").heads if key == "head" else ContentRegistry.character("tensor").emotes
	if category == "Armor Colors":
		var channels := HBoxContainer.new()
		choices.add_child(channels)
		for channel in ["primary","secondary"]:
			var choose := ui.button(channels,channel.capitalize()+" / "+String(draft[channel]).capitalize(),func(): armor_channel = channel; customise())
			choose.size_flags_horizontal = Control.SIZE_EXPAND_FILL
			choose.add_theme_font_size_override("font_size",14)
			MenuSkin.apply_button(choose,false,armor_channel == channel)
		key = armor_channel
		items = OnlineTransport.PALETTE.keys()
	ui.label(choices,"Choose your "+("armor finish" if category == "Armor Colors" else "head" if key == "head" else "victory animation"),18,ui.MUTED)
	var grid := GridContainer.new()
	grid.name = "ChoicesGrid"
	grid.columns = 3
	grid.set_meta("colors",category == "Armor Colors")
	grid.add_theme_constant_override("h_separation",12)
	grid.add_theme_constant_override("v_separation",12)
	grid.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	choices.add_child(grid)
	grid.resized.connect(func(): OnlineLayout.layout(ui))
	for id in items:
		choice_tile(grid,String(id),key)
	status = ui.label(choices,"Changes not saved" if draft != api.player.loadout else "Loadout saved to your account",16,ui.ACTION)
	OnlineLayout.action(ui,view.footer,"Back",back_customise)
	OnlineLayout.action(ui,view.footer,"Revert",func(): draft = api.player.loadout.duplicate(); customise())
	OnlineLayout.spacer(view.footer)
	var save := OnlineLayout.action(ui,view.footer,"Save loadout",save_customise,true)
	save.disabled = draft == api.player.loadout
	OnlineLayout.layout(ui)

func save_customise():
	if busy or draft == api.player.loadout: return
	busy = true
	var current := operation
	status.text = "Saving…"
	for control in ui.page.find_children("*","Button",true,false): control.disabled = true
	var response := await api.save_loadout(draft.duplicate(true))
	busy = false
	if current != operation or ui.screen != "customise": return
	if response.has("error"):
		status.text = response.error.message
		for control in ui.page.find_children("*","Button",true,false): control.disabled = false
	else: draft = api.player.loadout.duplicate(); customise()

func choice_tile(grid: GridContainer, id: String, key: String):
	var selected: bool = draft[key] == id
	var title := id.trim_prefix("victory_").replace("_"," ").capitalize()
	var button := ui.button(grid,"",func():
		draft[key] = id
		customise()
		if key == "emote": portrait_emote(id))
	button.accessibility_name = title
	button.tooltip_text = title+(" / selected" if selected else "")
	button.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	button.custom_minimum_size = Vector2(120,176)
	MenuSkin.apply_button(button,false,selected)
	var content := VBoxContainer.new()
	content.mouse_filter = Control.MOUSE_FILTER_IGNORE
	button.add_child(content)
	content.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	content.offset_left = 8; content.offset_right = -8; content.offset_top = 8; content.offset_bottom = -8
	var image := TextureRect.new()
	image.mouse_filter = Control.MOUSE_FILTER_IGNORE
	image.expand_mode = TextureRect.EXPAND_IGNORE_SIZE
	image.stretch_mode = TextureRect.STRETCH_KEEP_ASPECT_CENTERED
	image.size_flags_vertical = Control.SIZE_EXPAND_FILL
	content.add_child(image)
	var path: String
	if key == "head": path = "heads/"+id+"/"+draft.primary
	elif key == "emote": path = "emotes/"+id+"/"+draft.primary
	else: path = "armor/"+(id if key == "primary" else String(draft.primary))+"/"+(id if key == "secondary" else String(draft.secondary))
	image.texture = load("res://assets/ui/customisation/"+path+".webp")
	var caption := ui.label(content,title,14)
	caption.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	caption.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	var marker := ui.label(content,"SELECTED" if selected else "SAVED" if api.player.loadout[key] == id else "",11,ui.ACTION if selected else ui.MUTED)
	marker.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	for control in content.get_children(): control.mouse_filter = Control.MOUSE_FILTER_IGNORE

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

func portrait(parent: Node, loadout: Dictionary):
	if parent is Control: parent.size_flags_vertical = Control.SIZE_SHRINK_BEGIN
	if not is_instance_valid(portrait_viewport):
		portrait_viewport = MenuStudio.create(get_tree(),Vector2i(560,640),true)
		portrait_turntable = Node3D.new()
		portrait_viewport.add_child(portrait_turntable)
		portrait_robot = Assets.model("characters","tensor")
		portrait_turntable.add_child(portrait_robot)
		var floor := MeshInstance3D.new()
		var cylinder := CylinderMesh.new()
		cylinder.top_radius = 0.95; cylinder.bottom_radius = 1.0; cylinder.height = 0.12
		floor.mesh = cylinder
		floor.position.y = -0.06
		var regolith := Assets.regolith_material()
		regolith.uv1_world_triplanar = false
		floor.material_override = regolith
		portrait_turntable.add_child(floor)
		var skeleton := Assets.find(portrait_robot,"Skeleton3D")
		portrait_animator = AnimationPlayer.new()
		skeleton.get_parent().add_child(portrait_animator)
		var library := AnimationLibrary.new()
		var idle := Assets.animation("common/idle")
		if idle:
			idle = idle.duplicate()
			idle.loop_mode = Animation.LOOP_NONE
			library.add_animation("common_idle",idle)
		portrait_animator.add_animation_library("",library)
		portrait_animator.animation_finished.connect(func(clip):
			if clip == "common_idle": portrait_emote(portrait_victory)
			else: portrait_animator.play("common_idle",0.2))
		portrait_animator.play("common_idle")
		var camera := Camera3D.new()
		portrait_viewport.add_child(camera)
		camera.position = Vector3(-1.8,1.25,3.8)
		camera.look_at(Vector3(0,0.86,0))
		camera.fov = 34
		camera.current = true
	Assets.paint(portrait_robot,Color(OnlineTransport.PALETTE[loadout.primary]),Color(OnlineTransport.PALETTE[loadout.secondary]),loadout.head)
	portrait_victory = app.preview_victory(loadout.get("emote",""))
	portrait_viewport.process_mode = Node.PROCESS_MODE_INHERIT
	portrait_viewport.render_target_update_mode = SubViewport.UPDATE_ALWAYS
	var stage := TextureRect.new()
	stage.name = "OnlineStage"
	stage.texture = portrait_viewport.get_texture()
	stage.expand_mode = TextureRect.EXPAND_IGNORE_SIZE
	stage.stretch_mode = TextureRect.STRETCH_KEEP_ASPECT_CENTERED
	stage.custom_minimum_size.y = 420
	stage.size_flags_vertical = Control.SIZE_EXPAND_FILL
	stage.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	parent.add_child(stage)
	stage.tooltip_text = "Drag to rotate the platform"
	stage.gui_input.connect(func(event):
		if event is InputEventMouseMotion and Input.is_mouse_button_pressed(MOUSE_BUTTON_LEFT):
			portrait_turntable.rotation.y -= event.relative.x*0.01)

func shutdown_views():
	var stage := portrait_viewport
	portrait_viewport = null
	portrait_robot = null
	portrait_turntable = null
	portrait_animator = null
	if not is_instance_valid(stage): return
	stage.render_target_update_mode = SubViewport.UPDATE_DISABLED
	stage.process_mode = Node.PROCESS_MODE_DISABLED
	for mesh in stage.find_children("*","MeshInstance3D",true,false): mesh.mesh = null
	await get_tree().process_frame
	if DisplayServer.get_name() != "headless": await RenderingServer.frame_post_draw
	stage.queue_free()
	await get_tree().process_frame

func _exit_tree():
	if is_instance_valid(portrait_viewport): portrait_viewport.queue_free()

func portrait_emote(id: String):
	id = app.preview_victory(id)
	portrait_victory = id
	var library := portrait_animator.get_animation_library("")
	if not library.has_animation(id):
		var clip := Assets.animation("common/"+id)
		if clip == null: return
		clip = clip.duplicate()
		clip.loop_mode = Animation.LOOP_NONE
		library.add_animation(id,clip)
	portrait_animator.play(id,0.2)
