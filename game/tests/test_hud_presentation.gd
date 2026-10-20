extends GutTest

func test_killfeed_order_is_stable_when_simulation_and_caption_clocks_drift():
	var game:=ArenaMatch.new()
	autofree(game)
	var calls:=ArenaCallouts.new()
	game.add_child(calls)
	game.callouts=calls
	game.elapsed=20.0
	calls.clock=game.elapsed
	game.feed_events=[{"kind":"leave","actor":"Earlier","team":0,"time":20.0}]
	assert_true(calls.publish("Next!","Pilot",0,false))
	var events:=HudKillFeed.active_events(game,true)
	assert_eq(events[0].kind,"callout")
	game.elapsed+=0.03
	calls._process(0.04)
	assert_eq(HudKillFeed.active_events(game,true)[0].kind,"callout","Clock drift cannot reorder accepted events")
	var event:Dictionary=events[0].merged({"direction":" / right"},true)
	var text:=HudKillFeed.format_event(event,"DM",[])
	assert_false(text.contains("/ right"),"Legacy network metadata never appears in dialogue")
	assert_false(calls.caption_text().contains(" / "))
	assert_true(calls.publish("Flag captured.","Announcer",1,true))
	assert_eq(calls.captions.size(),2,"An announcement does not erase unexpired dialogue")

func test_kill_feed_is_a_sentence_with_bold_team_colored_people_and_weapon():
	var colors: Array[Color] = [Color("e84a43"), Color("4ab77a")]
	var event := {"kind":"kill", "killer":"ABC", "killer_team":0,
		"victim":"XYZ", "victim_team":1, "weapon":"Minigun"}
	var team_text := HudKillFeed.format_event(event, "TDM", colors)
	assert_true(team_text.contains("[b][color=#e84a43]ABC[/color][/b]"))
	assert_true(team_text.contains("[b][color=#4ab77a]XYZ[/color][/b]"))
	assert_true(team_text.ends_with(" with [b]Minigun[/b]."))
	var solo_text := HudKillFeed.format_event(event, "DM", colors)
	assert_false(solo_text.contains("e84a43"), "DM has no team-color claims")
	assert_true(HudKillFeed.format_event({"kind":"death", "victim":"XYZ", "victim_team":1,
		"cause":"Fall off map"}, "CTF", colors).contains("fell from the arena."))

func test_weapon_silhouette_fit_preserves_source_ratio():
	var bounds := Rect2(0, 0, 160, 42)
	var wide := WeaponReadout.fit_icon(Vector2(200, 50), bounds)
	assert_almost_eq(wide.size.x, 160.0, 0.001)
	assert_almost_eq(wide.size.y, 40.0, 0.001)
	assert_almost_eq(wide.position.y, 1.0, 0.001)
	var tall := WeaponReadout.fit_icon(Vector2(40, 80), bounds)
	assert_almost_eq(tall.size.x, 21.0, 0.001)
	assert_almost_eq(tall.size.y, 42.0, 0.001)

func test_robot_callouts_share_the_feed_with_safe_bold_team_names_and_expire():
	var game := ArenaMatch.new()
	autofree(game)
	var calls := ArenaCallouts.new()
	game.add_child(calls)
	game.callouts=calls
	game.elapsed=20.0
	calls.clock=game.elapsed
	game.feed_events=[{"kind":"leave","actor":"Other","team":1,"time":19.5}]
	assert_true(calls.publish("Cover [b]me[/b]", "ABC", 0, false))
	assert_false(calls.publish("Spam", "ABC", 0, false))
	assert_true(calls.caption_text().contains("Cover"),"Settings retains the complete accessible transcript")
	var events := HudKillFeed.active_events(game,true)
	assert_eq(events.size(),2)
	assert_eq(events[0].kind,"callout","Newest speech shares the chronological feed")
	var colors: Array[Color] = [Color("e84a43"),Color("4ab77a")]
	var text := HudKillFeed.format_event(events[0],"CTF",colors)
	assert_true(text.begins_with("[b][color=#e84a43]ABC[/color][/b] said: "))
	assert_true(text.contains("［b］me［/b］"),"Speech cannot inject markup")
	assert_false(HudKillFeed.format_event(events[0],"DM",colors).contains("e84a43"))
	assert_eq(HudKillFeed.active_events(game,false).size(),1,"Subtitles off hides speech only")
	assert_true(calls.publish("Flag captured.","Announcer",1,true))
	assert_true(calls.caption_text().contains("Flag captured."))
	var announcer := HudKillFeed.active_events(game,true)[0]
	assert_eq(HudKillFeed.format_event(announcer,"CTF",colors),"[b]Announcement:[/b] Flag captured.")
	assert_eq(HudKillFeed.sentence("ARENA / Cover banks reconfigured"),"Cover banks reconfigured.")
	calls._process(5.0)
	assert_eq(HudKillFeed.active_events(game,true).size(),1,"Expired speech leaves the feed")
