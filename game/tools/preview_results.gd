extends SceneTree
## Layout/action coverage without running an entire match.
class FixtureRobot extends RefCounted:
	var robot_id := 0
class FixtureGame extends Node:
	var result: Dictionary
	var map := {"config":{"title":"Faceoff"}}
	var team_colors := [Color("b74740"),Color("3878b4")]
	var local_robot=null
	var online := false
class FixtureApp extends Node:
	var match_node
	var preview_robot=null
	var returned := false
	var exited := false
	func leave_match(): returned=true
	func request_quit(): exited=true

func _initialize() -> void: run.call_deferred()

func run() -> void:
	var app := FixtureApp.new()
	root.add_child(app)
	var game := FixtureGame.new()
	app.add_child(game)
	app.match_node=game
	var entries := []
	for index in 10:
		entries.append({"id":index,"name":"ABCDEFGHIJKLMNOPQRST" if index==0 else ["Kestrel","Relay","Vector","Sable","Flux","Torque","Cipher","Helix","Rook"][index-1],"team":index%2,"kills":25-index*2,"assists":index,"deaths":index+1,"captures":index%3,"reached":333.7+index})
	entries.reverse()
	game.result={"title":"ABCDEFGHIJKLMNOPQRST wins","mvp":"ABCDEFGHIJKLMNOPQRST","canceled":false,"match_type":"DM","entries":entries,"teams":[{"name":"Team A","score":25,"time":333.7},{"name":"Team B","score":20,"time":300.0}]}
	game.local_robot=FixtureRobot.new()
	var ui := ArenaUI.new()
	ui.app=app
	app.add_child(ui)
	DirAccess.make_dir_recursive_absolute("res://reports/results")
	for mode in ["DM","TDM","CTF","CANCELED"]:
		game.online=mode=="CANCELED"
		game.result.canceled=mode=="CANCELED"
		game.result.match_type="CTF" if mode=="CANCELED" else mode
		if mode!="DM": game.result.title="Canceled" if mode=="CANCELED" else "Team A wins"
		game.result.reason="The roster is no longer valid."
		for dimensions in [Vector2i(1920,1080),Vector2i(1280,720),Vector2i(800,600),Vector2i(3840,2160)]:
			root.size=dimensions
			ui.results()
			if game.online: ui.results_status.text="The roster is no longer valid. Returning to lobby…"
			app.returned=false;app.exited=false
			for frame in 5: await process_frame
			var view=ui.page.get_node("MatchResults")
			if "ABCDEFGHIJKLMNOPQRST" not in view.table_rows[1].get_child(0).text:push_error("Results standings are not sorted by frozen score");quit(6);return
			var return_button := ui.page.find_child("ReturnToMenu",true,false) as Button
			var exit_button := ui.page.find_child("ExitGame",true,false) as Button
			for button in [return_button,exit_button]:
				if button==null or not Rect2(Vector2.ZERO,Vector2(dimensions)).encloses(button.get_global_rect()):
					push_error("Results action outside viewport: "+mode+str(dimensions));quit(2);return
			return_button.pressed.emit()
			exit_button.pressed.emit()
			if not app.returned or not app.exited: push_error("Results action was not connected");quit(3);return
			if return_button.text!=("RETURN TO LOBBY" if game.online else "RETURN TO MAIN MENU"):push_error("Wrong results destination");quit(4);return
			app.returned=false
			var cancel := InputEventAction.new()
			cancel.action="ui_cancel";cancel.pressed=true
			ui.page.get_node("MatchResults")._unhandled_key_input(cancel)
			if not app.returned:push_error("Results keyboard return failed");quit(5);return
			if DisplayServer.get_name()!="headless":
				for frame in 3: await RenderingServer.frame_post_draw
				root.get_texture().get_image().save_png("res://reports/results/%s-%dx%d.png"%[mode,dimensions.x,dimensions.y])
			print("RESULTS_LAYOUT_PASS ",mode," ",dimensions)
	app.free()
	await process_frame
	quit()
