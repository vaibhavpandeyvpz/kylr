class_name ArenaUI
extends CanvasLayer
const TEXT = MenuSkin.TEXT
const MUTED = MenuSkin.MUTED
const ACTION = MenuSkin.ACTION
var app
var root: Control
var page: Control
var hud: Control
var screen := ""
var status: Label
var results_status: Label
var match_frame: MatchHudFrame
var kill_feed: HudKillFeed
var kill_accolade: KillAccolade
var resources: ResourceReadout
var weapon: WeaponReadout
var reticle: WeaponCrosshair
var damage_indicator: DamageIndicator
var highlighted_target: ArenaRobot
var board: Label
var notification_time := 0.0
var pending: Dictionary = {}
var pending_bindings: Dictionary = {}
var waiting_binding := ""
var binding_button: Button
var settings_return: Callable
var settings_help: Label
var settings_help_title: Label
var settings_body: BoxContainer
var settings_help_box: VBoxContainer
var settings_caption: Label
var display_before: Dictionary = {}
var display_window_before: Dictionary = {}
var return_after_apply := false
var display_remaining := 0.0
var display_prompt: ConfirmationDialog
var display_prompt_text: Label
var sprint_effects: SprintEffects
var tutorial: TutorialReadout
var tutorial_hints := preload("res://scripts/ui/tutorial.gd").new()
var menu_scroll: ScrollContainer
var menu_stack: VBoxContainer
const SETTING_HELP = {
 "sensitivity":"Changes mouse-look speed. Does not add aim assistance.",
 "invert":"Reverses vertical mouse look.", "fov":"Sets camera field of view in degrees. A wider view makes distant objects appear smaller.",
 "display_mode":"Windowed is resizable. Borderless and exclusive fullscreen use the monitor's native resolution. Display changes need confirmation within 15 seconds.",
 "resolution":"3D rendering resolution. Menus, HUD and touch controls stay sharp at native display resolution. Fullscreen fits the image without stretching its aspect ratio.",
 "quality":"High enables fixture illumination and shadows. Raster rendering uses the selected ambient occlusion and MSAA settings. Low and Medium retain emissive-only fixtures. Detail changes select Custom.",
 "fixture_lighting":"Makes sconces, battens, pole heads and jumbotron spotlights illuminate nearby surfaces using their authored facing. Light shadows controls their shadows.",
 "shadows":"Draws supported light shadows. Turning this off reduces rendering cost.",
 "ambient_occlusion":"Adds raster shading around surface contacts. Available with Forward+.",
 "bloom":"Adds a subtle glow around bright surfaces. This preserves gameplay indicators when off.",
 "antialiasing":"Smooths jagged raster edges. Higher sample counts cost more GPU time.",
 "sprint_blur":"Blurs only the screen edges during actual sprint movement. Zero turns it off; the center aim area and HUD stay clear.",
 "speed_lines":"Adds faint lines at the screen edges while sprinting. Reduced motion suppresses both sprint effects.",
 "callouts":"Full allows ordinary reactions once per robot per 8 seconds; Reduced uses 16 seconds. Kill quips and repair/energy dialogue play per event. Off suppresses robot dialogue. Objective announcements and the low-energy warning tone remain available.",
 "subtitles":"Shows speaker-labeled captions for accepted objective, power, arena and optional robot callout events, including while online Settings is open. Volume does not affect captions.",
 "reduced_audio_range":"Brings quieter effects forward for comfortable listening without changing hearing range or gameplay.",
 "hud_scale":"Scales the combat readouts while keeping their screen anchors.",
 "contrast":"Adds stronger HUD backing and outlines for readability.",
 "reduced_motion":"Reduces decorative animation and suppresses impact camera shake, sprint blur and speed lines. Essential match information stays visible."}


func _ready():
	process_mode = Node.PROCESS_MODE_ALWAYS
	root = Control.new()
	root.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	root.mouse_filter = Control.MOUSE_FILTER_IGNORE
	add_child(root)
	root.theme = make_theme()
	root.resized.connect(responsive_layout)

func make_theme() -> Theme:
	return MenuSkin.make_theme()

func retire_control(control: Control):
	if not is_instance_valid(control): return
	# Navigation can run inside a signal emitted by a child of this control.
	# Hide immediately, but keep the sender alive until signal dispatch finishes.
	control.hide()
	control.process_mode = Node.PROCESS_MODE_DISABLED
	control.queue_free()

func close_page():
	results_status=null
	retire_control(page)
	page = null
	menu_scroll = null
	menu_stack = null
	waiting_binding = ""
	binding_button = null

func clear_page(id: String):
	if OS.has_feature("mobile"): Input.emulate_mouse_from_touch=true
	screen = id
	var stage = app.get("preview")
	if id == "main" and not is_instance_valid(stage) and app.has_method("make_preview"):
		app.make_preview()
		stage = app.get("preview")
	if is_instance_valid(stage): stage.visible = id not in ["setup","online_lobby","customise","online_search","online_loading","online_waiting"]
	var surface = app.get("preview_surface")
	if is_instance_valid(surface): surface.visible = is_instance_valid(stage) and stage.visible
	close_page()
	page = Control.new()
	root.add_child(page)
	page.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	var shade := ColorRect.new()
	shade.color = MenuSkin.CANVAS if id in ["setup","online_lobby","customise","online_search","online_waiting"] else Color(MenuSkin.CANVAS,0.0 if id == "main" else 0.84)
	shade.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	page.add_child(shade)
	Input.mouse_mode = Input.MOUSE_MODE_VISIBLE

func label(parent: Node,text: String,size := 18,color := TEXT) -> Label:
	var node := Label.new()
	node.text = text
	if parent.has_meta("menu_rect"): node.autowrap_mode=TextServer.AUTOWRAP_WORD_SMART
	node.add_theme_font_size_override("font_size",size)
	if size>=24: node.add_theme_font_override("font",load("res://assets/ui/fonts/Rajdhani-SemiBold.ttf"))
	node.add_theme_color_override("font_color",color)
	parent.add_child(node)
	return node

func button(parent: Node,text: String,action: Callable,primary := false) -> Button:
	var node := Button.new()
	node.text = text
	node.custom_minimum_size.y = 52
	node.alignment = HORIZONTAL_ALIGNMENT_LEFT
	parent.add_child(node)
	MenuSkin.apply_button(node,primary)
	node.pressed.connect(action)
	return node

func column(x: float,y: float,width: float,height := 600.0) -> VBoxContainer:
	var node := VBoxContainer.new()
	page.add_child(node)
	node.position = Vector2(x,y)
	node.size = Vector2(width,height)
	node.add_theme_constant_override("separation",12)
	node.set_meta("menu_rect",Rect2(x,y,width,height))
	call_deferred("responsive_layout")
	return node

func main_menu():
	clear_page("main")
	var col := column(64,60,430)
	label(col,"K Y L R",20,ACTION)
	label(col,"BUILT TO\nOUTLAST.",68)
	label(col,"Fight for power. Control the arena.",20,MUTED)
	label(col,"",16)
	var instant := button(col,"INSTANT ACTION",setup,true)
	var online := button(col,"ONLINE MULTIPLAYER",app.open_online)
	button(col,"SETTINGS",func(): settings(main_menu))
	button(col,"EXIT",app.request_quit)
	(online if app.prefs.values.mode == "Online Multiplayer" else instant).grab_focus()
	var footer := label(col,"SKYFALL  /  LUNAR COMBAT FACILITY\n10 weapons  /  DM · TDM · CTF  /  Tensor platform",16,MUTED)
	footer.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART

func choice(parent: Node,title: String,options: Array,selected: int,changed: Callable) -> OptionButton:
	label(parent,title,16,MUTED)
	var control := OptionButton.new()
	control.accessibility_name = title
	for option in options: control.add_item(str(option))
	control.selected = selected
	control.custom_minimum_size.y = 44
	parent.add_child(control)
	control.item_selected.connect(changed)
	return control

func save_setup_choice(key: String, value):
	app.prefs.values[key] = value
	app.prefs.save()

func setup():
	clear_page("setup")
	app.prefs.values.mode = "Instant Action"
	var view := OnlineLayout.frame(self,"Instant Action","Choose an arena and configure your match","INSTANT ACTION")
	var col := OnlineLayout.column(view.body,1.0)
	var name_field: LineEdit
	if not Preferences.valid_name(str(app.prefs.values.name)):
		label(col,"Your robot's call sign",16,MUTED)
		name_field = LineEdit.new()
		name_field.accessibility_name = "Your robot's call sign"
		name_field.text = app.prefs.values.name
		name_field.placeholder_text = "1–20 letters, digits, dots or underscores"
		name_field.max_length = 20
		col.add_child(name_field)
		name_field.text_changed.connect(func(value):
			if Preferences.valid_name(value): save_setup_choice("name",value))
	else:
		label(col,"CALL SIGN / " + app.prefs.values.name,18,ACTION)
	choice(col,"Match type",["DM / Every robot for itself","TDM / Team eliminations","CTF / Capture the flag","Elimination / Five lives","Gun Game / New weapon per kill"],app.prefs.values.type,func(i): save_setup_choice("type",i))
	choice(col,"Bot difficulty",["Noob","Hobbyist","Skilled","Impossible"],app.prefs.values.difficulty,func(i): save_setup_choice("difficulty",i))
	choice(col,"Total robots",Preferences.OFFLINE_COUNTS,Preferences.OFFLINE_COUNTS.find(int(app.prefs.values.count)),func(i): save_setup_choice("count",Preferences.OFFLINE_COUNTS[i]))
	var row := HBoxContainer.new()
	col.add_child(row)
	for entry in [["Goal",1,999,"goal"],["Minutes",5,60,"minutes"]]:
		var group := VBoxContainer.new()
		group.size_flags_horizontal = Control.SIZE_EXPAND_FILL
		row.add_child(group)
		label(group,entry[0],16,MUTED)
		var spin := SpinBox.new()
		spin.accessibility_name = entry[0]
		spin.min_value = entry[1]
		spin.max_value = entry[2]
		spin.value = app.prefs.values[entry[3]]
		group.add_child(spin)
		spin.value_changed.connect(func(value): save_setup_choice(entry[3],int(value)))
	status = label(col,"",15,Color("ffc36a"))
	OnlineLayout.action(self,view.footer,"START MATCH",func():
		if name_field != null:
			if not Preferences.valid_name(name_field.text): status.text="Enter a valid call sign."; return
			save_setup_choice("name",name_field.text)
		app.start_match(),true)
	var back := OnlineLayout.action(self,view.footer,"BACK",main_menu)
	view.footer.move_child(back,0)
	var gap := OnlineLayout.spacer(view.footer)
	view.footer.move_child(gap,1)
	var brief := OnlineLayout.column(view.body,1.0)
	var maps := MapCatalog.all()
	var map_titles: Array=[]
	var selected:=0
	var found := false
	for i in maps.size():
		map_titles.append(maps[i].title)
		if maps[i].id==app.prefs.values.map:
			selected=i
			found=true
	if not found:
		app.prefs.setup_notices.append("Saved arena is unavailable. Using " + maps[selected].title + ".")
		app.prefs.values.map = maps[selected].id
	status.text = "\n".join(app.prefs.setup_notices)
	status.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	app.prefs.setup_notices.clear()
	app.prefs.save()
	choice(brief,"Arena",map_titles,selected,func(i): save_setup_choice("map",maps[i].id); setup())
	var subtitle := label(brief,maps[selected].subtitle,24)
	subtitle.autowrap_mode=TextServer.AUTOWRAP_WORD_SMART
	var description := label(brief,maps[selected].description,16,MUTED)
	description.autowrap_mode=TextServer.AUTOWRAP_WORD_SMART
	var preview := MapPreview.new()
	preview.map_id=maps[selected].id
	preview.reduced_motion=bool(app.prefs.values.reduced_motion)
	brief.add_child(preview)
	OnlineLayout.layout(self)

func settings(back: Callable):
	settings_return = back
	pending = app.prefs.values.duplicate(true)
	pending_bindings = app.prefs.bindings.duplicate(true)
	settings_tab("Controls")

func responsive_layout():
	if screen=="results": return
	if not is_instance_valid(page): return
	if page.has_meta("online_body"):
		OnlineLayout.layout(self)
		return
	if screen == "settings":
		if is_instance_valid(settings_body):
			settings_body.vertical = root.size.x < 1050
			settings_help_box.custom_minimum_size.x = 0 if settings_body.vertical else 300
			settings_help_box.custom_minimum_size.y = 80 if settings_body.vertical else 0
		return
	var columns: Array[Node] = []
	for node in page.find_children("*","VBoxContainer",true,false):
		if node.has_meta("menu_rect"): columns.append(node)
	var narrow := root.size.x < 1200 or root.size.y < 700
	for box in page.find_children("*","BoxContainer",true,false):
		if box.has_meta("responsive_vertical"): box.vertical = narrow
	if narrow:
		if not is_instance_valid(menu_scroll):
			menu_scroll = ScrollContainer.new()
			page.add_child(menu_scroll)
			menu_scroll.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
			menu_scroll.offset_left = 24
			menu_scroll.offset_right = -24
			menu_scroll.offset_top = 24
			menu_scroll.offset_bottom = -24
			menu_stack = VBoxContainer.new()
			menu_stack.size_flags_horizontal = Control.SIZE_EXPAND_FILL
			menu_stack.add_theme_constant_override("separation",28)
			menu_scroll.add_child(menu_stack)
		for col in columns:
			if col.get_parent() != menu_stack: col.reparent(menu_stack)
			col.custom_minimum_size.x = 0
			col.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	else:
		for col in columns:
			if col.get_parent() != page: col.reparent(page)
			var rect: Rect2 = col.get_meta("menu_rect")
			col.position = rect.position + Vector2((root.size.x-1280)*0.5,0)
			col.size = rect.size
		if is_instance_valid(menu_scroll):
			menu_scroll.queue_free()
			menu_scroll = null
			menu_stack = null

func setting_help(control: Control, key: String, title: String):
	var explanation: String = SETTING_HELP.get(key,"Adjusts the " + title.to_lower() + " channel. Audio volume does not change captions or gameplay.")
	if key == "tutorial_hints": explanation = "Shows five first-life hints with your current controls. They pause during spawn, repair, death and results, then turn off automatically. Enable this to repeat them next match."
	if key == "name": explanation = "Your robot's callsign in Instant Action. Use 1–20 letters, digits, dots or underscores. Online Multiplayer uses your account display name."
	if key == "separate_rendering_thread": explanation = "Runs rendering on a separate thread. Experimental; it may improve performance or cause instability. Off uses Safe mode. Requires a game restart and is independent of visual quality."
	if key in pending_bindings: explanation = "Choose a keyboard key or mouse button for " + title.to_lower() + ". Escape cancels capture. A conflict offers Swap or Cancel, keeping both actions usable."
	control.tooltip_text = explanation
	control.accessibility_name = title
	control.accessibility_description = explanation
	var reveal := func():
		settings_help_title.text = title
		settings_help.text = explanation
	control.focus_entered.connect(reveal)
	control.mouse_entered.connect(reveal)

func settings_dirty():
	status.text = "Unsaved changes — Apply to save." if pending != app.prefs.values or pending_bindings != app.prefs.bindings else "No unsaved changes."
	if Preferences.render_thread_restart_required(bool(pending.separate_rendering_thread)):
		status.text += " Restart the game to change the rendering thread."

func settings_tab(tab: String):
	clear_page("settings")
	var margin := MarginContainer.new()
	page.add_child(margin)
	margin.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	for edge in ["left","right","top","bottom"]: margin.add_theme_constant_override("margin_" + edge,24)
	var col := VBoxContainer.new()
	col.add_theme_constant_override("separation",12)
	margin.add_child(col)
	label(col,"SETTINGS",32)
	if app.match_node and app.match_node.online: label(col,"MATCH STILL RUNNING / Your robot remains vulnerable",16,Color("ffc36a"))
	settings_caption=null
	if app.match_node is ArenaMatch:
		settings_caption=label(col,"",17)
		settings_caption.autowrap_mode=TextServer.AUTOWRAP_WORD_SMART
	var tabs := HBoxContainer.new()
	col.add_child(tabs)
	for name in ["Controls","Audio","Graphics","HUD"]:
		var title: String = "HUD & Accessibility" if name == "HUD" else name
		var active: bool = name == tab
		var b := button(tabs,title,func(): settings_tab(name))
		MenuSkin.apply_button(b,false,active)
		b.size_flags_horizontal = Control.SIZE_EXPAND_FILL
		b.alignment = HORIZONTAL_ALIGNMENT_CENTER
		b.add_theme_font_size_override("font_size",16)
		for state in ["normal","hover","pressed","focus"]:
			var style := b.get_theme_stylebox(state).duplicate() as StyleBoxFlat
			style.content_margin_left=8
			style.content_margin_right=8
			b.add_theme_stylebox_override(state,style)
		b.tooltip_text = "Active tab" if active else "Open " + title
	settings_body = BoxContainer.new()
	settings_body.add_theme_constant_override("separation",24)
	settings_body.size_flags_vertical = Control.SIZE_EXPAND_FILL
	col.add_child(settings_body)
	var scroll := ScrollContainer.new()
	scroll.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	scroll.size_flags_vertical = Control.SIZE_EXPAND_FILL
	settings_body.add_child(scroll)
	var rows := VBoxContainer.new()
	rows.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	rows.add_theme_constant_override("separation",9)
	scroll.add_child(rows)
	settings_help_box = VBoxContainer.new()
	settings_body.add_child(settings_help_box)
	settings_help_title = label(settings_help_box,"YOUR CONTROL SYSTEM",21,ACTION)
	settings_help = label(settings_help_box,"Focus or hover a setting to see its effect. Changes remain pending until Apply.",17,MUTED)
	settings_help.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	settings_help.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	match tab:
		"Controls":
			label(rows,"PLAYER",20,ACTION)
			label(rows,"Callsign",17)
			var callsign := LineEdit.new()
			callsign.name="InstantActionCallsign"
			callsign.text=str(pending.name)
			callsign.placeholder_text="1–20 letters, digits, dots or underscores"
			callsign.max_length=20
			callsign.size_flags_horizontal=Control.SIZE_EXPAND_FILL
			rows.add_child(callsign)
			setting_help(callsign,"name","Callsign")
			callsign.text_changed.connect(func(value): pending.name=value; settings_dirty())
			label(rows,"MOUSE & AIM",20,ACTION)
			slider(rows,"Look sensitivity","sensitivity",0.0005,0.006,0.0001)
			toggle(rows,"Invert vertical look","invert")
			var view := choice(rows,"Preferred camera view",["FPV","TPV"],int(pending.third_person),func(i): pending.third_person=i==1; settings_dirty())
			setting_help(view,"view","Preferred camera view")
			label(rows,"BINDINGS / Escape always opens the menu",18,ACTION)
			for key in pending_bindings:
				var b := button(rows,binding_title(key)+"   /   "+Preferences.binding_text(int(pending_bindings[key])),func(): pass)
				b.pressed.connect(func(): waiting_binding=key; binding_button=b; b.text="Press a key or mouse button / Escape cancels")
				setting_help(b,key,binding_title(key))
				b.tooltip_text = "Choose a keyboard key or mouse button. Escape cancels. Conflicts offer a binding swap."
		"Audio":
			for key in ["master","music","effects","interface","announcer","voices"]: slider(rows,key.capitalize(),key,0,1,0.05)
			setting_choice(rows,"Callout frequency","callouts",["Full","Reduced","Off"])
			toggle(rows,"Captions","subtitles")
			toggle(rows,"Reduced dynamic range","reduced_audio_range")
		"Graphics":
			label(rows,"DISPLAY",20,ACTION)
			if not OS.has_feature("mobile"): setting_choice(rows,"Display mode","display_mode",["Windowed","Borderless fullscreen","Exclusive fullscreen"])
			var sizes := Preferences.resolutions()
			var titles: Array[String] = ["Native (%d × %d)" % [Preferences.native_size().x,Preferences.native_size().y]]
			for size in sizes: titles.append("%d × %d" % [size.x,size.y])
			var selected := 0 if pending.native_resolution else sizes.find(pending.resolution)+1
			var resolution := choice(rows,"3D display resolution",titles,selected,func(i):
				pending.native_resolution=i==0
				if i>0: pending.resolution=sizes[i-1]
				settings_dirty())
			resolution.set_meta("setting_key","resolution")
			setting_help(resolution,"resolution","Resolution")
			label(rows,"QUALITY",20,ACTION)
			setting_choice(rows,"Visual quality","quality",["Low","Medium","High","Custom"])
			toggle(rows,"Fixture illumination","fixture_lighting")
			toggle(rows,"Light shadows","shadows")
			var ao := toggle(rows,"Raster ambient occlusion","ambient_occlusion")
			ao.disabled = RenderingServer.get_current_rendering_method() != "forward_plus"
			toggle(rows,"Bloom","bloom")
			setting_choice(rows,"Raster antialiasing","antialiasing",["Off","2× MSAA","4× MSAA","8× MSAA"])
			label(rows,"RENDERING",20,ACTION)
			var renderer_status:=label(rows,"Active renderer: "+Preferences.active_renderer_label(app),16,MUTED)
			renderer_status.set_meta("renderer_status",true)
			toggle(rows,"Separate rendering thread (restart required)","separate_rendering_thread")
			label(rows,"MOTION & CAMERA",20,ACTION)
			slider(rows,"Field of view","fov",60,100,1)
			slider(rows,"Sprint edge blur","sprint_blur",0,1,0.05)
			toggle(rows,"Sprint speed lines","speed_lines")
		"HUD":
			slider(rows,"HUD scale","hud_scale",0.8,1.4,0.05)
			toggle(rows,"High contrast","contrast")
			toggle(rows,"Captions","subtitles")
			toggle(rows,"Reduce decorative motion","reduced_motion")
			toggle(rows,"First-life tutorial hints","tutorial_hints")
	status = label(col,"",16,MUTED)
	status.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	settings_dirty()
	var footer := HBoxContainer.new()
	col.add_child(footer)
	button(footer,"BACK",func():
		if pending != app.prefs.values or pending_bindings != app.prefs.bindings:
			var confirm := ConfirmationDialog.new()
			confirm.dialog_text = "Unsaved changes. Apply to save, Discard to leave, or Stay."
			confirm.get_ok_button().text = "APPLY"
			confirm.get_cancel_button().text = "STAY"
			confirm.add_button("DISCARD",true,"discard")
			page.add_child(confirm)
			confirm.confirmed.connect(func(): return_after_apply=true; apply_settings())
			confirm.custom_action.connect(func(_action): settings_return.call())
			confirm.popup_centered()
		else: settings_return.call())
	button(footer,"DEFAULTS",func():
		var groups := {"Controls":["sensitivity","invert","third_person"],"Audio":["master","music","effects","interface","announcer","voices","reduced_audio_range","callouts","subtitles"],"Graphics":["fov","display_mode","native_resolution","resolution","quality","separate_rendering_thread","fixture_lighting","shadows","ambient_occlusion","bloom","antialiasing","sprint_blur","speed_lines"],"HUD":["hud_scale","contrast","subtitles","reduced_motion","tutorial_hints"]}
		for key in groups[tab]: pending[key]=Preferences.DEFAULTS[key]
		if tab == "Graphics": pending.resolution=Preferences.default_resolution(); pending.native_resolution=not OS.has_feature("mobile")
		if tab == "Controls": pending_bindings=Preferences.DEFAULT_BINDINGS.duplicate()
		settings_tab(tab))
	OnlineLayout.spacer(footer)
	OnlineLayout.action(self,footer,"Apply",apply_settings,true)
	responsive_layout()

func setting_choice(parent: Node, title: String, key: String, options: Array) -> OptionButton:
	var node := choice(parent,title,options,int(pending[key]),func(i):
		pending[key]=i
		if key == "quality" and i < Preferences.QUALITY_PRESETS.size():
			for detail in Preferences.QUALITY_PRESETS[i]: pending[detail]=Preferences.QUALITY_PRESETS[i][detail]
			settings_tab("Graphics")
		elif key == "display_mode": settings_tab("Graphics")
		else:
			if key == "antialiasing": pending.quality=Preferences.CUSTOM_QUALITY
			settings_dirty())
	setting_help(node,key,title)
	node.set_meta("setting_key",key)
	return node

func apply_settings():
	if not display_before.is_empty(): return
	if pending.name!=app.prefs.values.name and not Preferences.valid_name(str(pending.name)):
		status.text="Callsign must use 1–20 letters, digits, dots or underscores."
		return
	if (pending.display_mode != app.prefs.values.display_mode or pending.resolution != app.prefs.values.resolution or pending.native_resolution != app.prefs.values.native_resolution) and DisplayServer.get_name() != "headless":
		begin_display_preview()
	else: commit_settings()

func begin_display_preview():
	display_before = app.prefs.values.duplicate(true)
	if DisplayServer.get_name() != "headless":
		display_window_before = {"mode":DisplayServer.window_get_mode(),"size":DisplayServer.window_get_size(),"position":DisplayServer.window_get_position()}
	display_remaining = 15.0
	app.prefs.apply_display(pending)
	display_prompt = ConfirmationDialog.new()
	display_prompt.title = "Keep this display configuration?"
	display_prompt.get_ok_button().text = "KEEP & APPLY"
	display_prompt.get_cancel_button().text = "REVERT"
	display_prompt.dialog_text = "Reverting in 15 seconds unless you confirm."
	root.add_child(display_prompt)
	display_prompt.confirmed.connect(func(): display_before.clear(); display_remaining=0; commit_settings(); display_prompt.queue_free())
	display_prompt.canceled.connect(revert_display)
	display_prompt.popup_centered()

func restore_display_window():
	if not display_window_before.is_empty() and DisplayServer.get_name() != "headless" and not OS.has_feature("mobile"):
		DisplayServer.window_set_mode(display_window_before.mode)
		if int(display_window_before.mode) == DisplayServer.WINDOW_MODE_WINDOWED:
			DisplayServer.window_set_size(display_window_before.size)
			DisplayServer.window_set_position(display_window_before.position)
	display_window_before.clear()

func revert_display():
	if display_before.is_empty(): return
	app.prefs.apply_display(display_before)
	restore_display_window()
	pending.display_mode=display_before.display_mode
	pending.resolution=display_before.resolution
	pending.native_resolution=display_before.native_resolution
	display_before.clear()
	display_remaining=0.0
	return_after_apply=false
	if is_instance_valid(page):
		for option: OptionButton in page.find_children("*","OptionButton",true,false):
			match option.get_meta("setting_key",""):
				"display_mode": option.select(int(pending.display_mode))
				"resolution": option.select(0 if pending.native_resolution else maxi(0,Preferences.resolutions().find(pending.resolution)+1))
	if is_instance_valid(display_prompt): display_prompt.queue_free()
	if is_instance_valid(status): status.text="Display reverted. Other edits remain pending."

func commit_settings():
	var old_values: Dictionary = app.prefs.values.duplicate(true)
	var old_bindings: Dictionary = app.prefs.bindings.duplicate(true)
	app.prefs.values=pending.duplicate(true)
	app.prefs.values.quality_benchmarked=true
	pending.quality_benchmarked=true
	app.prefs.bindings=pending_bindings.duplicate(true)
	if app.prefs.save() != OK:
		app.prefs.values=old_values
		app.prefs.bindings=old_bindings
		app.prefs.apply_display(old_values)
		restore_display_window()
		return_after_apply=false
		status.text="Could not save. Your edits remain pending; try Apply again."
		return
	app.prefs.apply()
	if app.has_method("apply_rendering_with_loading"): await app.apply_rendering_with_loading()
	else: app.prefs.apply_rendering(app)
	for readout in page.find_children("*","Label",true,false):
		if readout.get_meta("renderer_status",false):readout.text="Active renderer: "+Preferences.active_renderer_label(app)
	display_window_before.clear()
	status.text="Saved"
	if Preferences.render_thread_restart_required(bool(pending.separate_rendering_thread)):
		status.text += " — restart the game to change the rendering thread."
	if app.match_node:
		if not app.match_node.online and is_instance_valid(app.match_node.local_robot) and Preferences.valid_name(str(pending.name)):
			app.match_node.local_robot.display_name=str(pending.name)
		app.match_node.fov=pending.fov
		app.match_node.third_person=pending.third_person
	if return_after_apply:
		return_after_apply=false
		settings_return.call()

func binding_title(key: String) -> String:
	return "Primary fire" if key == "fire" else "Secondary fire" if key == "secondary" else "Walk (hold)" if key == "walk" else "Sprint (hold)" if key == "sprint" else "Charged jump (hold)" if key == "charged_jump" else "Crouch (hold)" if key == "crouch" else "Camera FPV / TPV" if key == "view" else key.capitalize()

func slider(parent,title: String,key: String,low: float,high: float,step: float):
	var text := label(parent,title + "  /  " + str(pending[key]),17)
	var control := HSlider.new()
	control.min_value=low
	control.max_value=high
	control.step=step
	control.value=pending[key]
	parent.add_child(control)
	control.value_changed.connect(func(value): pending[key]=value; text.text=title+"  /  "+str(snappedf(value,step)); settings_dirty())
	setting_help(control,key,title)

func toggle(parent,title: String,key: String) -> CheckButton:
	var node := SettingsToggle.new()
	node.text=title
	node.button_pressed=pending[key]
	parent.add_child(node)
	node.toggled.connect(func(value):
		pending[key]=value
		if key in ["shadows","ambient_occlusion","bloom","fixture_lighting"]: pending.quality=Preferences.CUSTOM_QUALITY
		settings_dirty())
	setting_help(node,key,title)
	return node

func _input(event):
	if waiting_binding == "": return
	var value := 0
	if event is InputEventKey and event.pressed and not event.echo:
		if event.keycode == KEY_ESCAPE:
			binding_button.text=binding_title(waiting_binding)+" / "+Preferences.binding_text(int(pending_bindings[waiting_binding]))
			waiting_binding=""
			get_viewport().set_input_as_handled()
			return
		value = event.physical_keycode if event.physical_keycode != 0 else event.keycode
	elif event is InputEventMouseButton and event.pressed:
		if event.button_index in [MOUSE_BUTTON_WHEEL_UP,MOUSE_BUTTON_WHEEL_DOWN,MOUSE_BUTTON_WHEEL_LEFT,MOUSE_BUTTON_WHEEL_RIGHT]: return
		value = -event.button_index
	if value == 0: return
	var action := waiting_binding
	var target := binding_button
	waiting_binding=""
	for key in pending_bindings:
		if key != action and int(pending_bindings[key]) == value:
			var conflict := ConfirmationDialog.new()
			conflict.dialog_text="%s is assigned to %s. Swap with %s?" % [Preferences.binding_text(value),binding_title(key),binding_title(action)]
			conflict.get_ok_button().text="SWAP"
			conflict.get_cancel_button().text="CANCEL"
			page.add_child(conflict)
			conflict.confirmed.connect(func(): pending_bindings[key]=pending_bindings[action]; pending_bindings[action]=value; settings_tab("Controls"))
			conflict.canceled.connect(func(): target.text=binding_title(action)+" / "+Preferences.binding_text(int(pending_bindings[action])))
			conflict.popup_centered()
			get_viewport().set_input_as_handled()
			return
	pending_bindings[action]=value
	target.text=binding_title(action)+" / "+Preferences.binding_text(value)
	settings_dirty()
	get_viewport().set_input_as_handled()

func hud_place(node: Control, anchor: Vector2, offset: Vector2, dimensions: Vector2):
	node.anchor_left=anchor.x
	node.anchor_right=anchor.x
	node.anchor_top=anchor.y
	node.anchor_bottom=anchor.y
	node.offset_left=offset.x
	node.offset_top=offset.y
	node.offset_right=offset.x+dimensions.x
	node.offset_bottom=offset.y+dimensions.y
	node.mouse_filter=Control.MOUSE_FILTER_IGNORE

func hud_readout(anchor: Vector2, offset: Vector2, dimensions: Vector2, font_size: int, centered := false, backed := true) -> Label:
	var node := label(hud,"",font_size)
	hud_place(node,anchor,offset,dimensions)
	node.vertical_alignment=VERTICAL_ALIGNMENT_CENTER
	node.horizontal_alignment=HORIZONTAL_ALIGNMENT_CENTER if centered else HORIZONTAL_ALIGNMENT_LEFT
	node.add_theme_color_override("font_shadow_color",Color(0,0,0,0.85))
	node.add_theme_constant_override("shadow_offset_y",1)
	if backed:
		var panel := MenuSkin.surface()
		panel.bg_color=Color(MenuSkin.CANVAS,0.94)
		panel.set_border_width_all(1)
		panel.content_margin_left=16
		panel.content_margin_right=16
		panel.content_margin_top=8
		panel.content_margin_bottom=8
		panel.corner_radius_bottom_right=8
		node.add_theme_stylebox_override("normal",panel)
	return node

func start_hud():
	if is_instance_valid(sprint_effects): sprint_effects.queue_free()
	sprint_effects = SprintEffects.new()
	root.add_child(sprint_effects)
	sprint_effects.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)

	close_page()
	screen="match"
	retire_control(hud)
	hud=Control.new()
	root.add_child(hud)
	hud.size=root.size
	hud.mouse_filter=Control.MOUSE_FILTER_IGNORE
	damage_indicator=DamageIndicator.new()
	hud.add_child(damage_indicator)
	damage_indicator.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	if app.match_node is ArenaMatch:
		damage_indicator.camera=app.match_node.camera
		app.match_node.damage_taken.connect(damage_indicator.mark)
		app.match_node.fall_impact.connect(damage_indicator.mark_fall_impact)
	match_frame=MatchHudFrame.new()
	hud.add_child(match_frame)
	match_frame.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	match_frame.arena_match=app.match_node as ArenaMatch
	kill_feed=HudKillFeed.new()
	hud.add_child(kill_feed)
	hud_place(kill_feed,Vector2(1,0),Vector2(-360,106),Vector2(336,204))
	kill_feed.arena_match=app.match_node as ArenaMatch
	if OS.has_feature("mobile"):
		hud_place(kill_feed,Vector2(1,0),Vector2(-304,106),Vector2(280,112))
	kill_accolade=KillAccolade.new()
	hud.add_child(kill_accolade)
	kill_accolade.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	if app.match_node is ArenaMatch: app.match_node.local_elimination.connect(kill_accolade.announce)
	resources=ResourceReadout.new()
	hud.add_child(resources)
	hud_place(resources,Vector2(1,1),Vector2(-324,-172),Vector2(300,148))
	weapon=WeaponReadout.new()
	hud.add_child(weapon)
	hud_place(weapon,Vector2(0,1),Vector2(24,-172),Vector2(436,148))
	reticle=WeaponCrosshair.new()
	hud.add_child(reticle)
	hud_place(reticle,Vector2(0.5,0.5),Vector2(-32,-32),Vector2(64,64))
	board=hud_readout(Vector2(0.5,0.5),Vector2(-300,-200),Vector2(600,400),20)
	board.hide()
	tutorial_hints = preload("res://scripts/ui/tutorial.gd").new()
	tutorial = TutorialReadout.new()
	hud.add_child(tutorial)
	hud_place(tutorial,Vector2(0,0.5),Vector2(24,-72),Vector2(300,144))
	tutorial.accessibility_live = 1 # Platform live-region mode: Polite.
	Input.mouse_mode=Input.MOUSE_MODE_VISIBLE if OS.has_feature("mobile") else Input.MOUSE_MODE_CAPTURED
	if OS.has_feature("mobile"):
		Input.emulate_mouse_from_touch=false
		app.mobile_controls=preload("res://scripts/ui/mobile_controls.gd").new()
		app.mobile_controls.app=app
		hud.add_child(app.mobile_controls)
		app.mobile_controls.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)

func show_notice(text: String):
	if match_frame:
		match_frame.notice_text=text
		notification_time=2.4

func _process(dt):
	if screen == "settings" and is_instance_valid(page):
		for node in page.find_children("*","OptionButton",true,false):
			if node.get_meta("setting_key","") == "quality": node.selected=int(pending.quality)
	if display_remaining > 0:
		display_remaining=maxf(0.0,display_remaining-dt)
		if is_instance_valid(display_prompt): display_prompt.dialog_text="Keep this display configuration? Reverting in %d seconds." % ceili(display_remaining)
		if display_remaining <= 0: revert_display()
	if is_instance_valid(settings_caption) and app and app.match_node and app.match_node.callouts:
		settings_caption.text=app.match_node.callouts.caption_text()
		settings_caption.visible=app.prefs.values.subtitles and not settings_caption.text.is_empty()
	if is_instance_valid(sprint_effects): sprint_effects.visible=screen=="match"
	if not app or not app.match_node or not hud: return
	var game = app.match_node
	var r = game.local_robot
	if r == null: return
	if is_instance_valid(sprint_effects): sprint_effects.update_sprint(r,app.prefs.values,game.phase=="Active" and screen=="match",dt)
	damage_indicator.viewer=r
	damage_indicator.reduced_motion=app.prefs.values.reduced_motion
	if not r.alive and not damage_indicator.hits.is_empty(): damage_indicator.clear()
	damage_indicator.visible=game.phase=="Active" and (r.alive or damage_indicator.impact_age<0.38) and screen=="match"
	var opening: bool = game.phase == "Countdown"
	var hud_scale: float=app.prefs.values.hud_scale
	hud.scale=Vector2.ONE*hud_scale
	hud.size=root.size/hud_scale
	notification_time=maxf(0,notification_time-dt)
	kill_feed.show_callouts=app.prefs.values.subtitles
	kill_accolade.reduced_motion=app.prefs.values.reduced_motion
	kill_accolade.high_contrast=app.prefs.values.contrast
	match_frame.viewer=r
	match_frame.notice_remaining=notification_time
	match_frame.reduced_motion=app.prefs.values.reduced_motion
	match_frame.high_contrast=app.prefs.values.contrast
	tutorial.high_contrast=app.prefs.values.contrast
	resources.visible=not opening
	weapon.visible=not opening
	resources.values=Vector3(r.sh,r.ah,r.ep)
	resources.accessibility_name="Shield %d. Armor %d. Energy %d." % [r.sh,r.ah,r.ep]
	resources.shield_seconds=r.shield_time
	resources.reduced_motion=app.prefs.values.reduced_motion
	resources.high_contrast=app.prefs.values.contrast
	resources.offset_top=-172 if r.sh>0 else -125
	resources.offset_bottom=-24
	weapon.robot=r
	weapon.accessibility_name="%s. %s." % [Arsenal.WEAPONS[r.equipped].title,"Unlimited ammunition" if r.equipped == "pistol" else "%d loaded, %d ammo packs" % [r.loaded,r.packs]]
	weapon.reduced_motion=app.prefs.values.reduced_motion
	# Percentages are measured in HUD coordinates, preserving HUD-scale settings.
	resources.anchor_left=0.75
	resources.anchor_right=1.0
	resources.offset_left=8
	resources.offset_right=-24
	weapon.anchor_left=0.0
	weapon.anchor_right=0.4
	weapon.offset_left=24
	weapon.offset_right=-8
	weapon.screen_width=hud.size.x
	reticle.configure(r.equipped, r.wants_secondary)
	reticle.lock_progress = r.rocket_lock_progress if r.equipped == "rocket_launcher" and r.wants_secondary else -1.0
	reticle.confirmed_hit=game.hit_marker>0
	var target: ArenaRobot = game.combat.damageable_target(r)
	reticle.target_valid=target != null
	if highlighted_target != target:
		if is_instance_valid(highlighted_target): highlighted_target.target_nameplate.visible=false
		highlighted_target=target
	if is_instance_valid(highlighted_target):
		highlighted_target.target_nameplate.visible=screen=="match" and highlighted_target.alive and highlighted_target.is_visible_in_tree() \
			and game.camera != null and OpponentMarker.in_camera_range(game.camera.global_position, highlighted_target.global_position)
	match_frame.phase_text=""
	match_frame.repair_detail=""
	if game.phase=="Countdown":
		var step := "GET READY"
		match_frame.phase_text="%s   ·   CONTROL IN %02d" % [step,ceili(maxf(0.0,ArenaMatch.OPENING_SECONDS-game.countdown))]
	elif r.eliminated(): match_frame.phase_text="ELIMINATED / SPECTATING"
	elif not r.alive: match_frame.phase_text="SYSTEM OFFLINE / REBOOTING"
	elif r.spawn_remaining>0: match_frame.phase_text="DEPLOYING / LIFT ACTIVE"
	elif r.protection>0: match_frame.phase_text="INVULNERABLE / WALK ONLY  %.1fs" % r.protection
	elif r.repair!=null:
		var state: Dictionary = game.map.repair_feedback(r.repair)
		match_frame.phase_text=state.label.to_upper()+" / %.1fs" % state.seconds
		match_frame.repair_detail="STATION BARRIER ACTIVE / COMBAT DISABLED" if state.barrier else "BARRIER ACTIVATING / VULNERABLE / COMBAT DISABLED"
	elif game.phase=="Active": match_frame.phase_text=game.map.repair_hint(r)
	match_frame.accessibility_name=match_frame.phase_text
	if is_instance_valid(tutorial):
		tutorial.text = tutorial_hints.text(game,app.prefs,dt)
		tutorial.visible = not tutorial.text.is_empty() and not OS.has_feature("mobile")
	board.visible=not opening and Input.is_action_pressed("scoreboard") and screen=="match"
	if board.visible:
		var sorted: Array=game.robots.duplicate()
		sorted.sort_custom(func(a,b): return a.kills>b.kills)
		board.text="ROBOT                K / A / D / C\n"
		if game.match_type=="ELIMINATION": board.text="ROBOT                K / A / D / LIVES\n"
		for robot in sorted: board.text+="%-20s %d / %d / %d / %d\n" % [robot.display_name,robot.kills,robot.assists,robot.deaths,robot.lives_remaining() if game.match_type=="ELIMINATION" else robot.captures]
	reticle.visible=game.phase=="Active" and r.alive

func pause_menu():
	clear_page("pause")
	if not app.match_node.online: get_tree().paused=true
	var col:=column(440,175,400)
	label(col,"PAUSED" if not app.match_node.online else "MATCH STILL RUNNING",30)
	button(col,"RESUME",resume,true)
	button(col,"SETTINGS",func(): settings(pause_menu))
	button(col,"RETURN TO MAIN MENU",app.leave_match)

func resume():
	get_tree().paused=false
	close_page()
	screen="match"
	if OS.has_feature("mobile"): Input.emulate_mouse_from_touch=false
	Input.mouse_mode=Input.MOUSE_MODE_VISIBLE if OS.has_feature("mobile") else Input.MOUSE_MODE_CAPTURED

func results():
	clear_page("results")
	if hud: hud.hide()
	var view := preload("res://scripts/ui/results_view.gd").new()
	view.name="MatchResults"
	view.result=app.match_node.result
	view.map_title=app.match_node.map.config.title
	view.online=bool(app.match_node.get("online"))
	view.team_colors=app.match_node.team_colors
	if app.match_node.local_robot: view.local_id=app.match_node.local_robot.robot_id
	view.return_requested.connect(app.leave_match)
	view.exit_requested.connect(app.request_quit)
	page.add_child(view)
	results_status=view.status
