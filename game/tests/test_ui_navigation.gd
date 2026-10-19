extends GutTest

class PreferencesProbe extends RefCounted:
	var values := Preferences.DEFAULTS.duplicate(true)
	var bindings := Preferences.DEFAULT_BINDINGS.duplicate()
	var setup_notices: Array[String] = []
	var saves := 0
	func save() -> Error:
		saves += 1
		return OK

class AppProbe extends Node:
	var prefs := PreferencesProbe.new()
	var match_node = null
	var ui: ArenaUI
	func open_online(): ui.clear_page("online")
	func request_quit(): pass
	func leave_match(): ui.main_menu()
	func start_match(): ui.start_hud()

var app: AppProbe
var ui: ArenaUI

func before_each():
	app = AppProbe.new()
	add_child_autofree(app)
	ui = ArenaUI.new()
	ui.app = app
	app.ui = ui
	app.add_child(ui)
	ui.set_process(false)
	ui.main_menu()

func after_each():
	get_tree().paused = false
	Input.mouse_mode = Input.MOUSE_MODE_VISIBLE

func press(text: String):
	var sender: Button
	for node in ui.page.find_children("*", "Button", true, false):
		if node.text == text:
			sender = node
			break
	assert_not_null(sender, text)
	if not sender: return
	var old_page := ui.page
	sender.pressed.emit()
	assert_true(is_instance_valid(sender), "Signal sender survives dispatch")
	assert_true(old_page.is_queued_for_deletion(), "Old page is retired after the signal")
	assert_false(old_page.visible, "Old page cannot cover the new screen")
	await wait_process_frames(2)
	assert_false(is_instance_valid(old_page), "Retired pages are freed")

func test_instant_action_and_settings_navigation_from_real_button_signals():
	await press("INSTANT ACTION")
	assert_eq(ui.screen, "setup")
	await press("BACK")
	await press("SETTINGS")
	await press("Audio")
	await press("Graphics")
	await press("Controls")
	await press("DEFAULTS")
	await press("BACK")
	assert_eq(ui.screen, "main")

func test_map_selection_can_rebuild_its_own_page():
	ui.setup()
	var old_page := ui.page
	var choices := ui.page.find_children("*", "OptionButton", true, false)
	var map_choice: OptionButton = choices.back()
	map_choice.item_selected.emit(0)
	assert_true(is_instance_valid(map_choice))
	assert_true(old_page.is_queued_for_deletion())
	assert_eq(ui.screen, "setup")
	await wait_process_frames(2)
	assert_false(is_instance_valid(old_page))

func test_start_hud_and_resume_keep_signal_senders_alive():
	ui.button(ui.page, "TEST START", ui.start_hud)
	await press("TEST START")
	assert_eq(ui.screen, "match")
	assert_null(ui.page)
	app.match_node = {"online": false}
	ui.pause_menu()
	assert_true(get_tree().paused)
	await press("RESUME")
	assert_false(get_tree().paused)
	assert_null(ui.page)

func test_setup_reuses_name_and_saves_choices_before_start():
	app.prefs.values.name = "Pilot_1"
	ui.setup()
	for editor in ui.page.find_children("*","LineEdit",true,false):
		assert_false(editor.placeholder_text.contains("letters"),"Saved name does not prompt again")
	var choices := ui.page.find_children("*","OptionButton",true,false)
	assert_eq(choices[2].item_count,5)
	for i in 5: assert_eq(choices[2].get_item_text(i),str(Preferences.OFFLINE_COUNTS[i]))
	var before := app.prefs.saves
	choices[0].item_selected.emit(2)
	choices[1].item_selected.emit(3)
	choices[2].item_selected.emit(1)
	var spins := ui.page.find_children("*","SpinBox",true,false)
	spins[0].value = 99
	spins[1].value = 20
	assert_eq(app.prefs.saves,before + 5)
	ui.main_menu()
	ui.setup()
	assert_eq(app.prefs.values.type,2)
	assert_eq(app.prefs.values.count,4)
	assert_eq(app.prefs.values.goal,99)
	assert_eq(app.prefs.values.minutes,20)

func test_removed_map_is_reset_with_explanation():
	app.prefs.values.map = "removed_map"
	ui.setup()
	assert_eq(app.prefs.values.map,MapCatalog.all()[0].id)
	assert_true(ui.status.text.contains("Saved arena is unavailable"))
	assert_gt(app.prefs.saves,0)

func test_valid_name_survives_map_rebuild_without_starting_match():
	ui.setup()
	var field: LineEdit = ui.page.find_children("*","LineEdit",true,false)[0]
	field.text = "Pilot.2"
	field.text_changed.emit(field.text)
	var choices := ui.page.find_children("*","OptionButton",true,false)
	choices.back().item_selected.emit(0)
	assert_eq(app.prefs.values.name,"Pilot.2")
	assert_eq(ui.screen,"setup")

func test_results_show_team_objective_times_and_assists():
	app.match_node = {"online":false,"local_robot":null,"team_colors":[],"map":{"config":{"title":"Skyfall"}},"result":{
		"title":"Team B wins","mvp":"Pilot","canceled":false,"match_type":"CTF",
		"teams":[{"name":"Team A","score":3,"time":90.0},{"name":"Team B","score":3,"time":80.0}],
		"entries":[{"name":"Pilot","team":0,"kills":8,"assists":3,"deaths":2,"captures":2,"reached":17.0}]}}
	ui.results()
	var texts: Array[String] = []
	for node in ui.page.find_children("*","Label",true,false): texts.append(node.text)
	assert_has(texts,"ASSISTS")
	assert_has(texts,"KILL TIME")
	assert_has(texts,"TEAM A")
	assert_has(texts,"TEAM B")
	assert_has(texts,"Captures  /  reached 90.00 s")
	assert_has(texts,"Captures  /  reached 80.00 s")
	assert_has(texts,"17.00 s")
