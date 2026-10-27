extends GutTest

class DirectGraph extends TraversalGraph:
	var last_bias := -1
	var blocked_destination:=Vector3.INF
	func route(a: Vector3,b: Vector3,_charged := true,_grounded := true,bias := 0) -> Array:
		last_bias=bias
		if b==blocked_destination:return []
		return [{"from":a,"point":b,"action":"walk"}]

func fixtures() -> Dictionary:
	var arena:=ArenaMap.new();autofree(arena)
	arena.config={"crossing_balance":{"junction":1.0,"floaters":1.0},"zone_bounds":[{"min":[-36,8,-36],"max":[-10,15,-10]},{"min":[10,8,10],"max":[36,15,36]}]}
	var carriers:=MapCarriers.new();carriers.arena=arena;arena.carriers=carriers
	var traffic:=CrossingTraffic.new(carriers,arena);carriers.traffic=traffic
	arena.traversal=DirectGraph.new(arena)
	return {"arena":arena,"traffic":traffic}

func test_corridor_quota_counts_entries_and_pending_commitments():
	var setup:=fixtures();var traffic: CrossingTraffic=setup.traffic
	traffic.usage={"junction":12,"floaters":25}
	assert_eq(traffic.choose_kind(),"junction","Long floater trips must not reserve every fighter indefinitely")
	traffic.usage={"junction":0,"floaters":0}
	traffic.actors[1]={"assignment":{"kind":"junction"},"touches":{}}
	assert_eq(traffic.choose_kind(),"floaters","Pending commitments reserve their corridor once")

func test_flag_carrier_uses_direct_safe_route_without_balancing_detour():
	var setup:=fixtures();var traffic: CrossingTraffic=setup.traffic
	var robot:=ArenaRobot.new();autofree(robot)
	robot.position=Vector3(-22,10,-22);robot.carrying=0
	var state:=traffic.state_for(robot)
	state.assignment={"kind":"floaters","destination":1,"goal":Vector3(22,10,22),"via":"A_Floater_2","passed":false}
	var route:=traffic.route(robot,Vector3(22,10,22),"extract")
	assert_false(route.is_empty())
	assert_true(state.assignment.is_empty(),"Objective delivery releases the optional flanking commitment")
	assert_eq((setup.arena.traversal as DirectGraph).last_bias,0)

func test_corridor_search_filters_other_corridor_and_keeps_cache_contexts_separate():
	var graph:=TraversalGraph.TraversalAStar.new()
	for id in 4:graph.add_point(id,[Vector3.ZERO,Vector3(2,0,0),Vector3(1,0,2),Vector3(4,0,0)][id])
	for pair in [Vector2i(0,1),Vector2i(1,3),Vector2i(0,2),Vector2i(2,3)]:graph.connect_points(pair.x,pair.y)
	graph.corridor_nodes={1:1,2:2}
	assert_eq(Array(graph.cached_path(0,3)),[0,1,3])
	graph.corridor_bias=2;graph.neighbor_filter_enabled=true
	assert_eq(Array(graph.cached_path(0,3)),[0,2,3])
	graph.set_point_position(2,Vector3(1,0,3))
	var cached:=graph.cached_path(0,3)
	assert_eq(graph.get_point_position(cached[1]),Vector3(1,0,3),"Cached IDs resolve current carrier coordinates")
	graph.corridor_bias=0;graph.neighbor_filter_enabled=false
	assert_eq(Array(graph.cached_path(0,3)),[0,1,3])

func test_deck_waypoint_tracks_motion_and_avoids_disabled_or_raised_nodes():
	var setup:=fixtures();var arena: ArenaMap=setup.arena
	var carriers: MapCarriers=arena.carriers
	carriers.sections=[{"name":"A_Floater_2","position":[0,0,10]}]
	carriers.deck_navigation={"A_Floater_2":[3,2,1]}
	carriers.navigation_points={1:{"rest":Vector3(0,10,0)},2:{"rest":Vector3(1,10,0)},3:{"rest":Vector3(0,12,0)}}
	arena.nav=arena.traversal.graph
	for id in carriers.navigation_points:arena.nav.add_point(id,carriers.navigation_points[id].rest)
	assert_eq(setup.traffic.waypoint("A_Floater_2"),Vector3(0,10,0))
	arena.nav.set_point_position(1,Vector3(4,10.5,0))
	assert_eq(setup.traffic.waypoint("A_Floater_2"),Vector3(4,10.5,0),"Cached rank resolves the live moving deck")
	arena.nav.set_point_disabled(1,true)
	assert_eq(setup.traffic.waypoint("A_Floater_2"),Vector3(1,10,0),"A disabled centre falls back to walkable deck ground")

func test_floater_plan_advances_a_deck_while_the_final_destination_is_disconnected():
	var setup:=fixtures();var arena: ArenaMap=setup.arena
	var carriers: MapCarriers=arena.carriers
	var first:=Vector3(-7,10,-22);var second:=Vector3(10,10,-26)
	var goal:=Vector3(22,10,22)
	arena.config.floater_paths=[["A_Mainland","A_Floater_1","A_Floater_2","B_Mainland"]]
	carriers.deck_sections=[{"name":"A_Floater_1","position":[first.x,-first.z,10]},{"name":"A_Floater_2","position":[second.x,-second.z,10]}]
	carriers.deck_navigation={"A_Mainland":[0],"A_Floater_1":[1],"A_Floater_2":[2]}
	carriers.navigation_points={0:{"rest":Vector3(-22,10,-22),"deck":"A_Mainland"},1:{"rest":first,"deck":"A_Floater_1"},2:{"rest":second,"deck":"A_Floater_2"}}
	arena.nav=arena.traversal.graph
	for id in carriers.navigation_points:arena.nav.add_point(id,carriers.navigation_points[id].rest)
	(arena.traversal as DirectGraph).blocked_destination=goal
	var robot:=ArenaRobot.new();autofree(robot);robot.position=Vector3(-22,10,-22)
	var state: Dictionary=setup.traffic.state_for(robot)
	var assignment: Dictionary={"kind":"floaters","via":"","waiting_since":-1.0}
	state.assignment=assignment;state.deck="A_Floater_1"
	var path: Array=setup.traffic.floater_route(robot,goal,assignment,true,true)
	assert_eq(path.back().point,first,"Board the next deck without requiring a complete route to the flag")
	assert_eq(path.back().action,"wait_carrier")
	robot.position=first
	path=setup.traffic.floater_route(robot,goal,assignment,true,true)
	assert_eq(path.back().point,second,"Progress to the next docking stage instead of waiting for the whole chain")
