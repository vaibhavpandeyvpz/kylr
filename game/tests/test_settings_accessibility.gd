extends GutTest
class PreferencesProbe extends RefCounted:
	var values := Preferences.DEFAULTS.duplicate(true)
	var bindings := Preferences.DEFAULT_BINDINGS.duplicate()
	var saves := 0
	var save_error := OK
	var applied := 0
	var display_calls: Array[Dictionary] = []
	func save() -> Error:
		saves += 1
		return save_error
	func apply(): applied += 1
	func apply_rendering(_node): pass
	func apply_display(options: Dictionary): display_calls.append(options.duplicate(true))
class AppProbe extends Node:
	var prefs := PreferencesProbe.new()
	var match_node = null
	func request_quit(): pass
	func open_online(): pass
class SprintRobot extends ArenaRobot:
	func _ready(): set_physics_process(false); set_process(false)
	func can_act() -> bool: return alive and protection<=0 and repair==null
var app: AppProbe
var ui: ArenaUI
func before_each():
	app=AppProbe.new()
	add_child_autofree(app)
	ui=ArenaUI.new()
	ui.app=app
	app.add_child(ui)
	ui.set_process(false)
	ui.settings(func(): ui.main_menu())
func after_each():
	get_tree().paused=false
	Input.mouse_mode=Input.MOUSE_MODE_VISIBLE

func test_instant_action_callsign_is_editable_validated_and_applied():
	var callsign:=ui.page.find_child("InstantActionCallsign",true,false) as LineEdit
	assert_not_null(callsign)
	callsign.text="New.Pilot"
	callsign.text_changed.emit(callsign.text)
	assert_ne(app.prefs.values.name,"New.Pilot","Typing remains pending until Apply")
	ui.apply_settings()
	assert_eq(app.prefs.values.name,"New.Pilot")
	assert_eq(app.prefs.saves,1)
	ui.pending.name="Invalid call sign!"
	ui.apply_settings()
	assert_eq(app.prefs.saves,1)
	assert_eq(app.prefs.values.name,"New.Pilot")
	assert_true(ui.status.text.contains("Callsign"))

func test_high_preset_selects_full_fixture_lighting_and_custom_keeps_individual_choice():
	ui.settings_tab("Graphics")
	var quality: OptionButton
	for option in ui.page.find_children("*","OptionButton",true,false):
		if option.get_meta("setting_key","")=="quality": quality=option
	assert_eq(quality.item_count,4)
	assert_eq(quality.get_item_text(2),"High")
	quality.item_selected.emit(2)
	assert_true(ui.pending.fixture_lighting)
	assert_true(ui.pending.shadows)
	assert_eq(ui.pending.antialiasing,2)
	for toggle in ui.page.find_children("*","CheckButton",true,false):
		if toggle.text=="Fixture illumination":toggle.toggled.emit(false)
	assert_eq(ui.pending.quality,Preferences.CUSTOM_QUALITY)
	assert_false(ui.pending.fixture_lighting)

func test_high_preset_enables_fixture_illumination_and_shadows():
	ui.settings_tab("Graphics")
	for option in ui.page.find_children("*","OptionButton",true,false):
		if option.get_meta("setting_key","")=="quality":
			option.item_selected.emit(2)
			break
	assert_true(ui.pending.fixture_lighting)
	assert_true(ui.pending.shadows)
	assert_eq(ui.pending.antialiasing,2)
	for preset in [0,1]:
		assert_false(Preferences.QUALITY_PRESETS[preset].fixture_lighting)

func test_saved_custom_preserves_individual_lighting():
	var path := "user://settings_custom_fixture_test.cfg"
	var prefs := Preferences.new(path)
	prefs.values.quality=Preferences.CUSTOM_QUALITY
	prefs.values.fixture_lighting=false
	prefs.values.shadows=false
	assert_eq(prefs.save(),OK)
	var restored := Preferences.new(path)
	assert_eq(restored.values.quality,Preferences.CUSTOM_QUALITY)
	assert_false(restored.values.fixture_lighting)
	assert_false(restored.values.shadows)
	DirAccess.remove_absolute(path)

func test_graphics_quality_offers_three_presets_and_custom():
	ui.settings_tab("Graphics")
	for node in ui.page.find_children("*","OptionButton",true,false):
		if node.get_meta("setting_key","")=="quality":
			var titles: Array[String]=[]
			for index in node.item_count: titles.append(node.get_item_text(index))
			assert_eq(titles,["Low","Medium","High","Custom"])
	assert_eq(app.prefs.saves,0)

func test_render_thread_choice_is_pending_and_independent_of_quality():
	ui.settings_tab("Graphics")
	var control:CheckButton
	for node in ui.page.find_children("*","CheckButton",true,false):
		if node.text.begins_with("Separate rendering thread"):control=node
	assert_not_null(control)
	assert_false(control.button_pressed)
	assert_true(control.tooltip_text.contains("Experimental"))
	assert_true(control.tooltip_text.contains("restart"))
	control.toggled.emit(true)
	assert_true(ui.pending.separate_rendering_thread)
	assert_false(app.prefs.values.separate_rendering_thread)
	assert_eq(app.prefs.saves,0)
	var quality:OptionButton
	for node in ui.page.find_children("*","OptionButton",true,false):
		if node.get_meta("setting_key","")=="quality":quality=node
	quality.item_selected.emit(2)
	assert_true(ui.pending.separate_rendering_thread,"High preserves an explicit independent thread choice")
	for node in ui.page.find_children("*","Button",true,false):
		if node.text=="DEFAULTS":node.pressed.emit();break
	assert_false(ui.pending.separate_rendering_thread)
func test_fire_bindings_survive_reload_and_apply():
	var prefs := Preferences.new("user://settings_input_test.cfg")
	prefs.bindings.fire=KEY_F
	prefs.bindings.secondary=-MOUSE_BUTTON_MIDDLE
	assert_eq(prefs.save(),OK)
	var restored := Preferences.new("user://settings_input_test.cfg")
	for i in 2: restored.apply()
	var primary: InputEventKey=InputMap.action_get_events("fire")[0]
	var secondary: InputEventMouseButton=InputMap.action_get_events("secondary")[0]
	assert_eq(primary.physical_keycode,KEY_F)
	assert_eq(secondary.button_index,MOUSE_BUTTON_MIDDLE)
	DirAccess.remove_absolute("user://settings_input_test.cfg")
func test_mouse_capture_and_conflict_swap_preserve_both_actions():
	var b: Button
	for node in ui.page.find_children("*","Button",true,false):
		if node.text.begins_with("Primary fire"): b=node
	b.pressed.emit()
	var mouse := InputEventMouseButton.new()
	mouse.button_index=MOUSE_BUTTON_MIDDLE
	mouse.pressed=true
	ui._input(mouse)
	assert_eq(ui.pending_bindings.fire,-MOUSE_BUTTON_MIDDLE)
	b.pressed.emit()
	var key := InputEventKey.new()
	key.keycode=KEY_R
	key.physical_keycode=KEY_R
	key.pressed=true
	ui._input(key)
	var dialogs := ui.page.find_children("*","ConfirmationDialog",true,false)
	assert_eq(dialogs.size(),1)
	dialogs[0].confirmed.emit()
	assert_eq(ui.pending_bindings.fire,KEY_R)
	assert_eq(ui.pending_bindings.reload,-MOUSE_BUTTON_MIDDLE)
func test_display_preview_timeout_reverts_without_saving_other_edits():
	ui.settings_tab("Graphics")
	var display_nodes: Dictionary={}
	for option in ui.page.find_children("*","OptionButton",true,false):
		var key: String=option.get_meta("setting_key","")
		if key in ["resolution","display_mode"]: display_nodes[key]=option
	display_nodes.resolution.select(1)
	display_nodes.display_mode.select(1)
	ui.pending.native_resolution=false
	ui.pending.display_mode=1
	ui.pending.resolution=Vector2i(800,600)
	ui.pending.fov=85.0
	ui.begin_display_preview()
	assert_eq(app.prefs.saves,0)
	assert_eq(ui.display_remaining,15.0)
	get_tree().paused=true
	ui._process(16.0)
	assert_eq(app.prefs.display_calls.size(),2)
	assert_eq(app.prefs.display_calls.back().resolution,Preferences.DEFAULTS.resolution)
	assert_eq(ui.pending.resolution,Preferences.DEFAULTS.resolution)
	assert_eq(ui.pending.fov,85.0)
	assert_eq(app.prefs.saves,0)
	assert_true(ui.display_before.is_empty())
	assert_eq(display_nodes.resolution.selected,0,"Revert restores the visible Native choice")
	assert_eq(display_nodes.display_mode.selected,Preferences.DEFAULTS.display_mode)
func test_display_confirmation_saves_and_applies_pending_preferences():
	ui.pending.display_mode=1
	ui.pending.callouts=2
	ui.begin_display_preview()
	ui.display_prompt.confirmed.emit()
	assert_eq(app.prefs.saves,1)
	assert_eq(app.prefs.applied,1)
	assert_eq(app.prefs.values.display_mode,1)
	assert_eq(app.prefs.values.callouts,2)
func test_failed_save_keeps_edits_pending_and_saved_values_unchanged():
	app.prefs.save_error=ERR_CANT_CREATE
	ui.pending.fov=90.0
	ui.commit_settings()
	assert_eq(app.prefs.values.fov,Preferences.DEFAULTS.fov)
	assert_eq(ui.pending.fov,90.0)
	assert_eq(app.prefs.applied,0)
	assert_true(ui.status.text.contains("remain pending"))
func test_help_follows_focus_and_pending_edits_survive_tabs():
	var slider: HSlider=ui.page.find_children("*","HSlider",true,false)[0]
	slider.focus_entered.emit()
	assert_eq(ui.settings_help_title.text,"Look sensitivity")
	assert_true(ui.settings_help.text.contains("mouse-look"))
	slider.value=0.003
	ui.settings_tab("Graphics")
	assert_almost_eq(ui.pending.sensitivity,0.003,0.00001)
	var active: Button
	for node in ui.page.find_children("*","Button",true,false):
		if node.text == "Graphics": active=node
	assert_not_null(active)
	assert_true(ui.status.text.contains("Unsaved"))
func test_quality_changes_rendering_without_changing_geometry():
	var world := Node3D.new()
	add_child_autofree(world)
	var env := WorldEnvironment.new()
	env.environment=Environment.new()
	env.environment.glow_enabled=true
	env.environment.ssao_enabled=true
	world.add_child(env)
	var light := DirectionalLight3D.new()
	light.shadow_enabled=true
	world.add_child(light)
	var geometry := StaticBody3D.new()
	world.add_child(geometry)
	var prefs := Preferences.new("user://settings_quality_test.cfg")
	for detail in Preferences.QUALITY_PRESETS[0]: prefs.values[detail]=Preferences.QUALITY_PRESETS[0][detail]
	prefs.apply_rendering(world)
	assert_false(light.shadow_enabled)
	assert_false(env.environment.glow_enabled)
	assert_false(env.environment.ssao_enabled)
	for detail in Preferences.QUALITY_PRESETS[2]: prefs.values[detail]=Preferences.QUALITY_PRESETS[2][detail]
	prefs.apply_rendering(world)
	assert_true(light.shadow_enabled)
	assert_true(env.environment.ssao_enabled)
	assert_eq(world.get_child_count(),3)
	assert_eq(geometry.collision_layer,1)
func test_callout_frequency_caps_repetition_but_preserves_critical_captions():
	var calls := ArenaCallouts.new()
	add_child_autofree(calls)
	calls.set_process(false)
	assert_true(calls.publish("Armor hit.","Pilot",0,false))
	assert_false(calls.publish("Got it.","Pilot",0,false))
	calls.clock=8.1
	assert_true(calls.publish("Got it.","Pilot",0,false))
	calls.frequency=1
	calls.clock=17.0
	assert_false(calls.publish("Cover me.","Pilot",0,false))
	calls.frequency=2
	assert_false(calls.publish("Pickup acquired.","Other",1,false))
	assert_true(calls.publish("Flag captured.","Announcer",1,true))
	assert_true(calls.caption_text().contains("Announcer: Flag captured."))
	calls._process(5.0)
	assert_eq(calls.caption_text(),"")
func test_sprint_effects_use_real_motion_and_reduced_motion_overrides_toggles():
	var robot := SprintRobot.new()
	add_child_autofree(robot)
	robot.protection=0
	robot.wants_sprint=true
	robot.velocity=Vector3(12,0,0)
	var fx := SprintEffects.new()
	add_child_autofree(fx)
	var options := Preferences.DEFAULTS.duplicate(true)
	fx.update_sprint(robot,options,true,1.0)
	assert_eq(fx.strength,1.0)
	assert_true(fx.blur.visible)
	options.reduced_motion=true
	fx.update_sprint(robot,options,true,0.1)
	assert_eq(fx.strength,0.0)
	assert_false(fx.blur.visible)
	options.reduced_motion=false
	robot.velocity=Vector3.ZERO
	fx.update_sprint(robot,options,true,1.0)
	assert_eq(fx.strength,0.0)

func test_live_online_settings_captions_work_when_audio_is_muted():
	var game := ArenaMatch.new()
	autofree(game)
	game.online=true
	game.callouts=ArenaCallouts.new()
	game.add_child(game.callouts)
	app.match_node=game
	app.prefs.values.master=0.0
	ui.settings_tab("Audio")
	game.callouts.publish("Flag dropped.","Announcer",0,true)
	ui._process(0.0)
	assert_true(ui.settings_caption.visible)
	assert_true(ui.settings_caption.text.contains("Flag dropped."))
	app.prefs.values.subtitles=false
	ui._process(0.0)
	assert_false(ui.settings_caption.visible)
	app.match_node=null

func test_narrow_settings_keeps_actions_visible_and_collapses_help():
	ui.root.anchor_right=0
	ui.root.anchor_bottom=0
	ui.root.size=Vector2(800,600)
	ui.responsive_layout()
	await wait_process_frames(2)
	assert_true(ui.settings_body.vertical)
	for node in ui.page.find_children("*","Button",true,false):
		if node.text in ["BACK","DEFAULTS","APPLY"]:
			assert_lte(node.get_global_rect().end.y,600.0)
			assert_lte(node.get_global_rect().end.x,800.0)
