class_name OnlineTransport
extends Node
signal admitted(game)
signal failed(reason: String)
signal round_changed(game)
signal progress(text: String)
signal loading
const PALETTE := {"graphite":"333f48","silver":"aab5bd","white":"edf2f4","yellow":"ecb846","orange":"d97b32","red":"b74740","magenta":"be438e","violet":"855ab5","blue":"3878b4","cyan":"46bac8","teal":"398c82","green":"689649"}
var server := false
var server_id := ""
var generation := ""
var api_url := ""
var control_token := ""
var game: ArenaMatch
var peers: Dictionary = {}
var pending_peers: Dictionary = {}
var remote_history: Dictionary = {}
var projectiles: Dictionary = {}
var remote_drops: Dictionary = {}
var remote_corpses: Dictionary = {}
var local_id := -1
var next_id := 1
var sequence := 0
var snapshot_number := 0
var last_snapshot := -1
var last_ack := 0
var unacked: Array[Dictionary] = []
var assignment: Dictionary = {}
var command_source: Callable
var discrete := {"jump":false,"release":false,"reload":false,"slot":""}
var snapshot_clock := 0.0
var reliable_snapshot_clock := 0.0
var heartbeat_clock := 0.0
var heartbeat_deadline := 0
var heartbeat_pending := false
var heartbeat_failures := 0
var diagnostic_deadline := 0
var next_map := -1.0
var next_map_deadline := 0
var building := false
var round_ready := false
var closed := false
var results_seen := false
var connection_deadline := 0
var silence_deadline := 0
var last_phase := ""
var last_roster: Array = []
var snapshot_parts: Dictionary = {}
var pending_snapshot: Dictionary = {}
var pending_presentation: Array = []
var predicted_fire_clock := 0.0
var resync_deadline := 0

func _ready():
	if DisplayServer.get_name() == "headless": Engine.max_fps = 60
	process_physics_priority = 20
	var pump := preload("res://scripts/network/input_pump.gd").new()
	pump.transport = self
	add_child(pump)
	multiplayer.peer_disconnected.connect(disconnected)

func private_request(route: String, data: Dictionary) -> Dictionary:
	var request := HTTPRequest.new()
	request.timeout = 5
	add_child(request)
	var error := request.request(api_url+"/internal/servers/"+server_id+"/"+route,["Content-Type: application/json","X-Control-Token: "+control_token],HTTPClient.METHOD_POST,JSON.stringify(data))
	if error != OK: request.queue_free(); return {}
	var response = await request.request_completed
	request.queue_free()
	if response[0] != HTTPRequest.RESULT_SUCCESS or response[1] != 200: return {}
	var body = JSON.parse_string(response[3].get_string_from_utf8())
	return body if body is Dictionary else {}

func start_server():
	server = true
	# The account-bound server owns all traffic; peers never relay to one another.
	multiplayer.server_relay = false
	server_id = OS.get_environment("KYLR_SERVER_ID")
	generation = OS.get_environment("KYLR_MATCH_ID")
	api_url = OS.get_environment("KYLR_API_URL")
	control_token = OS.get_environment("KYLR_CONTROL_TOKEN")
	if server_id == "" or generation == "" or control_token.length() < 32: get_tree().quit(2); return
	var enet := ENetMultiplayerPeer.new()
	if enet.create_server(int(OS.get_environment("KYLR_PORT")),32) != OK: get_tree().quit(3); return
	multiplayer.multiplayer_peer = enet
	multiplayer.peer_connected.connect(func(peer): pending_peers[peer] = Time.get_ticks_msec()+5000)
	await build_round(OS.get_environment("KYLR_MATCH_TYPE"))
	await heartbeat()
	print("ONLINE_SERVER round_ready type=",game.match_type)

func build_round(type: String, previous_map := ""):
	building = true
	round_ready = false
	if game: remove_child(game); game.queue_free()
	var eligible: Array = MapCatalog.all().filter(func(item): return type in item.match_types)
	var maps: Array = eligible.filter(func(item): return item.id != previous_map)
	if maps.is_empty(): maps = eligible
	var map_random := RandomNumberGenerator.new()
	map_random.randomize()
	var selection_seed := map_random.seed
	var selected_map: String = maps[map_random.randi_range(0,maps.size()-1)].id
	print("ONLINE_MAP selection_seed=",selection_seed," map=",selected_map," previous=",previous_map," type=",type)
	game = ArenaMatch.new()
	game.name = "Match"
	game.online = true
	game.async_scene_loading = true
	game.replicating = true
	game.authority = server
	game.map_id = selected_map
	game.match_type = type
	game.time_limit = 1800
	game.on_ready = func(): round_ready = true
	add_child(game)
	while not round_ready: await get_tree().physics_frame
	for peer in peers: add_player(peer,peers[peer].player)
	game.goal = 2*peers.size()
	if peers.size() >= 2:
		game.loading_hold = true
		await game.begin_countdown_async()
		game.loading_hold = false
	elif previous_map != "": game.finish(true,"Fewer than two players remain for the next match.")
	building = false
	next_map = -1
	next_map_deadline = 0
	last_phase = ""
	results_seen = false

func heartbeat():
	if heartbeat_pending or game == null: return
	heartbeat_pending = true
	var accounts: Array = []
	for peer in peers: accounts.append(peers[peer].player.id)
	var phase := "Finished" if building else "Canceled" if game.result.get("canceled",false) else game.phase
	var response := await private_request("heartbeat",{"match_id":generation,"phase":phase,"accounts":accounts})
	heartbeat_pending = false
	if response.is_empty():
		heartbeat_failures += 1
		if heartbeat_failures >= 3: close(); get_tree().quit(4)
		return
	heartbeat_failures = 0
	for account in response.get("revoked_accounts",[]):
		for peer in peers.keys():
			if peers[peer].player.id == account:
				print("ONLINE_ADMISSION revoked robot=",peers[peer].id)
				disconnected(peer)
				multiplayer.multiplayer_peer.disconnect_peer(peer,true)
	if response.get("retire",false): close(); get_tree().quit()

func connect_match(value: Dictionary):
	assignment = value
	generation = value.match_id
	connection_deadline = Time.get_ticks_msec()+12000
	var enet := ENetMultiplayerPeer.new()
	if enet.create_client(value.host,int(value.port)) != OK: failed.emit("Could not open the game connection."); return
	multiplayer.connected_to_server.connect(func(): connection_deadline = Time.get_ticks_msec()+90000; progress.emit("Joining"); join.rpc_id(1,generation,value.ticket))
	multiplayer.connection_failed.connect(func(): fail_connection("Connection failed. Retry for a fresh ticket."))
	multiplayer.server_disconnected.connect(func(): fail_connection("The game server disconnected."))
	multiplayer.multiplayer_peer = enet
	progress.emit("Connecting")

@rpc("any_peer","call_remote","reliable",0)
func join(match_id: String, ticket: String):
	if not server: return
	var peer := multiplayer.get_remote_sender_id()
	if closed or building or not round_ready or not pending_peers.has(peer) or peers.has(peer) or match_id != generation or ticket.length() > 128:
		reject_peer(peer,"Admission was not accepted. Retry for a fresh ticket."); return
	pending_peers.erase(peer)
	var accepted := await private_request("admit",{"match_id":match_id,"ticket":ticket})
	if not multiplayer.get_peers().has(peer):
		if accepted.has("reservation_id"): private_request("release",{"reservation_id":accepted.reservation_id})
		return
	if accepted.is_empty() or peers.size() >= 10 or game.phase == "Finished" or (game.match_type=="ELIMINATION" and game.phase=="Active") or generation != match_id:
		if accepted.has("reservation_id"): private_request("release",{"reservation_id":accepted.reservation_id})
		reject_peer(peer,"Join ticket expired or was already used. Retry for a fresh ticket."); return
	for item in peers.values():
		if item.player.id == accepted.player.id:
			private_request("release",{"reservation_id":accepted.reservation_id})
			reject_peer(peer,"This account already has a player in the match."); return
	peers[peer] = {"player":accepted.player,"reservation":accepted.reservation_id,"id":next_id,"received":0,"ack":0,"queue":[],"last_input":Time.get_ticks_msec(),"rate_start":Time.get_ticks_msec(),"rate_count":0}
	next_id += 1
	add_player(peer,accepted.player)
	game.goal = 2*peers.size()
	if game.phase == "Waiting" and peers.size() >= 2:
		game.loading_hold = true
		await game.begin_countdown_async()
		game.loading_hold = false
		if closed or not peers.has(peer): return
	initial.rpc_id(peer,peers[peer].id,pack_snapshot(peer))
	heartbeat_clock = 5

func add_player(peer: int, player: Dictionary):
	var a := 0
	var b := 0
	for robot in game.robots:
		if robot.team == 0: a += 1
		else: b += 1
	var team := randi_range(0,1) if a == b else 0 if a < b else 1
	var robot: ArenaRobot = game.add_robot(peers[peer].id,player.display_name,team,true,player.loadout.head)
	robot.tint = Color(PALETTE[player.loadout.primary]) if MatchTypes.individual(game.match_type) else game.team_colors[team]
	robot.armor_secondary = Color(PALETTE[player.loadout.secondary]) if MatchTypes.individual(game.match_type) else Assets.robot_accent(robot.body,robot.tint,robot.character.model)
	robot.account_emote = player.loadout.emote
	Assets.paint(robot.body,robot.tint,robot.armor_secondary,robot.head)
	robot.hide()
	robot.collision_layer = 0
	if game.phase == "Active" or game.spawn_reveal_started: game.spawn_robot(robot)
	peers[peer].queue.clear()
	peers[peer].ack = 0
	peers[peer].received = 0

@rpc("authority","call_remote","reliable",0)
func rejected(reason: String): fail_connection(reason)

func reject_peer(peer: int, reason: String):
	rejected.rpc_id(peer,reason)
	await get_tree().create_timer(0.2).timeout
	if not closed and multiplayer.get_peers().has(peer): multiplayer.multiplayer_peer.disconnect_peer(peer,true)

func fail_connection(reason: String):
	if closed: return
	close()
	failed.emit(reason)

@rpc("any_peer","call_remote","unreliable_ordered",1)
func inputs(payload: PackedByteArray):
	if not server: return
	var peer := multiplayer.get_remote_sender_id()
	if not peers.has(peer) or building: return
	var record: Dictionary = peers[peer]
	var now := Time.get_ticks_msec()
	# Allow a bounded delivery burst after loading or scheduler jitter. Packet
	# arrivals never grant additional simulation steps (simulate_inputs coalesces).
	var tokens: float = minf(360,float(record.get("tokens",360))+(now-int(record.get("token_time",now)))*0.12)
	record.token_time = now
	record.tokens = tokens-1
	if tokens < 1:
		print("ONLINE_INPUT throttled robot=",record.id)
		return
	if payload.size() > 1000: return
	var commands = bytes_to_var(payload.decompress_dynamic(16384,FileAccess.COMPRESSION_DEFLATE))
	if not commands is Array: return
	if commands.size() > 6: return
	for command in commands:
		if not command is Dictionary: continue
		if command.get("seq",0) <= record.received: continue
		if not OnlineInput.valid(command,generation,record.received): continue
		if record.queue.size() >= 120: continue
		record.received = command.seq
		record.queue.append(command)
		record.last_input = now

func simulate_inputs(dt: float):
	if closed or building or not round_ready or game == null: return
	if server:
		for peer in peers:
			var record: Dictionary = peers[peer]
			var robot: ArenaRobot = game.robot_by_id(record.id)
			var released := false
			# Network bursts must not create a permanent simulation backlog.
			# Apply queued actions in order, then simulate the latest held intent
			# once in the robot's server physics tick. Extra packets grant no travel.
			while not record.queue.is_empty():
				var command: Dictionary = record.queue.pop_front()
				OnlineInput.apply(robot,command)
				released = released or command.release
				record.ack = command.seq
			robot.jump_release = released
			if Time.get_ticks_msec()-record.last_input > 150: OnlineInput.stop(robot)
	else:
		var robot: ArenaRobot = game.local_robot
		if robot == null: return
		if unacked.size() >= 120:
			# Bound prediction work while reliable resynchronization catches up.
			# Keep resending pending intent; the normal silence deadline handles
			# a genuinely lost server instead of terminating during a packet burst.
			inputs.rpc_id(1,var_to_bytes(unacked.slice(unacked.size()-6)).compress(FileAccess.COMPRESSION_DEFLATE))
			return
		sequence += 1
		var command := {"generation":generation,"seq":sequence,"move":robot.move_input.limit_length(),"yaw":wrapf(robot.yaw,-PI,PI),"pitch":clampf(robot.pitch,-PI/4,PI/4),"walk":robot.wants_walk,"sprint":robot.wants_sprint,"crouch":robot.wants_crouch,"fire":robot.wants_fire,"secondary":robot.wants_secondary,"held":robot.jump_held,"jump":discrete.jump,"release":discrete.release,"reload":discrete.reload,"slot":discrete.slot}
		if command_source.is_valid(): command = command_source.call(command)
		discrete = {"jump":false,"release":false,"reload":false,"slot":""}
		unacked.append(command)
		inputs.rpc_id(1,var_to_bytes(unacked.slice(maxi(0,unacked.size()-6))).compress(FileAccess.COMPRESSION_DEFLATE))
		OnlineInput.apply(robot,command,true)
		predicted_fire_clock = maxf(0,predicted_fire_clock-dt)
		var orb: bool = Arsenal.orb_secondary(robot.equipped) and command.secondary
		var discrete_fire: bool = robot.equipped not in ["lightning_gun","flamethrower"] or orb
		if discrete_fire and (command.fire or orb) and robot.can_act() and robot.reload_time <= 0 and predicted_fire_clock <= 0 and (robot.equipped == "pistol" or robot.loaded > 0):
			var profile: Dictionary = Arsenal.WEAPONS[robot.equipped]
			predicted_fire_clock = profile.secondary_interval if orb else profile.interval
			robot.predicted_shot_time = Time.get_ticks_msec()
			robot.weapon_vfx.begin_shot()
			robot.weapon_vfx.shot()
			game.audio.cue(Arsenal.shot_cue(robot.equipped,orb),robot.muzzle(),true,robot)
			robot.apply_recoil(profile.recoil)
		if robot.alive and robot.spawn_remaining <= 0 and robot.repair == null and game.phase == "Active": robot.simulate_movement(dt,true)

func _physics_process(dt):
	if closed: return
	if not server:
		var now := Time.get_ticks_msec()
		flush_client_state()
		if game: game.hit_marker = maxf(0,game.hit_marker-dt)
		if round_ready and not building and now > resync_deadline:
			resync_deadline = now+1000
			resynchronize.rpc_id(1,generation)
		if not round_ready and connection_deadline > 0 and now > connection_deadline: fail_connection("Joining timed out. Retry for a fresh ticket.")
		elif round_ready and silence_deadline > 0 and now > silence_deadline: fail_connection("The game server stopped responding.")
		return
	# Loading yields between authored fixtures; keep the admission lease alive
	# while reporting a non-admitting phase until the new world is complete.
	if building:
		if Time.get_ticks_msec() >= heartbeat_deadline:
			heartbeat_deadline = Time.get_ticks_msec()+5000
			heartbeat()
		return
	if not round_ready: return
	for peer in peers.keys():
		var link := (multiplayer.multiplayer_peer as ENetMultiplayerPeer).get_peer(peer)
		if link == null or link.get_state() != ENetPacketPeer.STATE_CONNECTED:
			print("ONLINE_CONNECTION lost robot=",peers[peer].id," state=",link.get_state() if link else -1)
			disconnected(peer)
	if Time.get_ticks_msec() >= diagnostic_deadline:
		diagnostic_deadline = Time.get_ticks_msec()+5000
		var connections: Array = []
		for peer in peers:
			var link := (multiplayer.multiplayer_peer as ENetMultiplayerPeer).get_peer(peer)
			connections.append({"robot":peers[peer].id,"ack":peers[peer].ack,"state":link.get_state() if link else -1,"input_age_ms":Time.get_ticks_msec()-peers[peer].last_input})
		print("ONLINE_HEALTH ",JSON.stringify({"elapsed":game.elapsed,"phase":game.phase,"connections":connections}))
	for peer in pending_peers.keys():
		if Time.get_ticks_msec() > pending_peers[peer]: pending_peers.erase(peer); multiplayer.multiplayer_peer.disconnect_peer(peer,true)
	# API leases use wall time, including when simulation is under load.
	if heartbeat_clock >= 5 or Time.get_ticks_msec() >= heartbeat_deadline:
		heartbeat_clock = 0
		heartbeat_deadline = Time.get_ticks_msec()+5000
		heartbeat()
	var roster: Array = peers.keys()
	roster.sort()
	if game.phase != last_phase or roster != last_roster:
		last_phase = game.phase
		last_roster = roster
		heartbeat_clock = 5
		snapshot_number += 1
		for peer in peers:
			if peer_connected(peer): transition.rpc_id(peer,pack_snapshot(peer))
	if game.phase == "Finished" and not game.result.get("canceled",false):
		if next_map_deadline == 0: next_map_deadline = Time.get_ticks_msec()+15000
		next_map = maxf(0,(next_map_deadline-Time.get_ticks_msec())/1000.0)
		if next_map <= 0: advance_round(); return
	snapshot_clock += dt
	reliable_snapshot_clock += dt
	if reliable_snapshot_clock >= 2.0:
		reliable_snapshot_clock = 0.0
		snapshot_number += 1
		for peer in peers:
			if peer_connected(peer): transition.rpc_id(peer,pack_snapshot(peer))
	if snapshot_clock >= 0.05:
		snapshot_clock = 0
		if not game.presentation_events.is_empty():
			var batch := game.presentation_events.duplicate(true)
			game.presentation_events.clear()
			for peer in peers:
				var recipient: int = peers[peer].id
				var selected: Array = batch.filter(func(event): return int(event.get("recipient",-1)) in [-1,recipient])
				if peer_connected(peer) and not selected.is_empty(): presentation.rpc_id(peer,generation,selected)
		snapshot_number += 1
		for peer in peers:
			if not peer_connected(peer): continue
			var packed := var_to_bytes(make_snapshot(peer)).compress(FileAccess.COMPRESSION_DEFLATE)
			var count := ceili(packed.size()/1000.0)
			for index in count: update_chunk.rpc_id(peer,generation,snapshot_number,index,count,packed.slice(index*1000,mini(packed.size(),(index+1)*1000)))

func advance_round():
	building = true
	var previous := game.map_id
	var type := game.match_type
	for peer in peers:
		if peer_connected(peer): preparing_round.rpc_id(peer,generation)
	(multiplayer.multiplayer_peer as ENetMultiplayerPeer).get_host().flush()
	await get_tree().process_frame
	generation = Crypto.new().generate_random_bytes(16).hex_encode()
	await build_round(type,previous)
	await heartbeat()
	for peer in peers:
		if peer_connected(peer): initial.rpc_id(peer,peers[peer].id,pack_snapshot(peer))

@rpc("authority","call_remote","reliable",0)
func preparing_round(previous_generation: String):
	if server or closed or previous_generation != generation: return
	building = true
	round_ready = false
	silence_deadline = 0
	connection_deadline = Time.get_ticks_msec()+90000
	unacked.clear()
	pending_snapshot.clear()
	pending_presentation.clear()
	loading.emit()

func peer_connected(peer: int) -> bool:
	var link := (multiplayer.multiplayer_peer as ENetMultiplayerPeer).get_peer(peer)
	return link != null and link.get_state() == ENetPacketPeer.STATE_CONNECTED

func pack_snapshot(peer: int) -> PackedByteArray:
	return var_to_bytes(make_snapshot(peer)).compress(FileAccess.COMPRESSION_DEFLATE)

func make_snapshot(peer: int) -> Dictionary:
	var actors: Array = []
	for robot in game.robots: actors.append(robot.network_state())
	var fixtures: Array = []
	for fixture in game.map.fixtures:
		var state := {"id":fixture.id,"transform":fixture.node.global_transform}
		for key in ["ready","cooldown","elapsed","open","active","inside","repair_active","usable"]:
			if fixture.has(key) and (fixture[key] is bool or fixture[key] is float or fixture[key] is int): state[key] = fixture[key]
		if fixture.has("occupant"): state.occupant = fixture.occupant.robot_id if is_instance_valid(fixture.occupant) else -1
		var animator := Assets.find(fixture.node,"AnimationPlayer") as AnimationPlayer
		if animator and animator.current_animation != "": state.animation = animator.current_animation; state.time = animator.current_animation_position
		if fixture.has("motion"): state.motion = fixture.motion.snapshot()
		fixtures.append(state)
	var flag_states: Array = []
	for flag in game.flags:
		var player := Assets.find(flag.node,"AnimationPlayer") as AnimationPlayer
		flag_states.append({"state":flag.state,"carrier":flag.carrier,"point":flag.point,"transform":flag.node.global_transform,"animation":player.current_animation,"frame":player.current_animation_position if player.current_animation != "" else 0.0})
	var missiles: Array = []
	for child in game.get_children():
		if child is ArenaProjectile: missiles.append({"id":child.get_instance_id(),"weapon":child.weapon,"p":child.position,"direction":child.direction,"distance":child.distance,"shooter":child.shooter.robot_id})
	var captions: Array = []
	for line in game.callouts.captions:
		var caption: Dictionary = line.duplicate()
		caption["remaining"] = line.expires-game.callouts.clock
		caption.erase("expires")
		captions.append(caption)
	var stadium := Assets.find(game.map.stadium,"AnimationPlayer") as AnimationPlayer
	var drops: Array = []
	for drop in game.drops: drops.append({"id":drop.node.get_instance_id(),"p":drop.node.global_position,"ep":drop.ep,"claim":drop.claim})
	var corpses: Array = []
	for corpse in game.corpses:
		var animator := corpse.node.find_child("RuntimeAnimator",true,false) as AnimationPlayer
		corpses.append({"id":corpse.node.get_instance_id(),"robot":corpse.robot,"transform":corpse.node.global_transform,"time":corpse.time,"fall":corpse.falling_out,"animation":animator.current_animation if animator else "","frame":animator.current_animation_position if animator and animator.current_animation != "" else 0.0})
	return {"protocol":2,"generation":generation,"number":snapshot_number,"map":game.map_id,"type":game.match_type,"phase":game.phase,"elapsed":game.elapsed,"countdown":game.countdown,"goal":game.goal,"teams":game.team_scores,"reached":game.team_reached,"colors":game.team_colors,"actors":actors,"ack":peers[peer].ack,"fixtures":fixtures,"flags":flag_states,"missiles":missiles,"arena_warned":game.map.event_warned,"arena_done":game.map.event_done,"feed":game.feed_events,"result":game.result,"next_map":next_map,"captions":captions,"stadium_clip":stadium.current_animation,"stadium_time":stadium.current_animation_position if stadium.current_animation != "" else 0.0,"jumbo":game.map.jumbotron.motion.snapshot(),"drops":drops,"corpses":corpses}

@rpc("authority","call_remote","reliable",0)
func initial(id: int, payload: PackedByteArray):
	if payload.size() > 64000: return
	var state: Variant = bytes_to_var(payload.decompress_dynamic(256000,FileAccess.COMPRESSION_DEFLATE))
	if not state is Dictionary: return
	if server or closed or state.get("protocol",0) != 2: return
	connection_deadline = Time.get_ticks_msec()+90000
	loading.emit()
	building = true
	round_ready = false
	local_id = id
	generation = state.generation
	sequence = 0
	predicted_fire_clock = 0
	last_snapshot = -1
	unacked.clear()
	remote_history.clear()
	snapshot_parts.clear()
	pending_snapshot.clear()
	pending_presentation.clear()
	projectiles.clear()
	remote_drops.clear()
	remote_corpses.clear()
	if game: remove_child(game); game.queue_free()
	game = ArenaMatch.new()
	game.name = "Match"
	game.online = true
	game.authority = false
	game.async_scene_loading = true
	game.replicating = true
	game.map_id = state.map
	game.match_type = state.type
	game.time_limit = 1800
	game.on_ready = func(): round_ready = true
	add_child(game)
	while not round_ready and not closed: await get_tree().physics_frame
	if closed: return
	building = false
	results_seen = false
	apply_snapshot(state,true)
	admitted.emit(game)
	round_changed.emit(game)

@rpc("authority","call_remote","unreliable",2)
func update_chunk(match_id: String, number: int, index: int, total: int, payload: PackedByteArray):
	if server or closed or building or not round_ready or match_id != generation or number <= last_snapshot or total < 1 or total > 64 or index < 0 or index >= total or payload.size() > 1000: return
	for old in snapshot_parts.keys():
		if old < number-4: snapshot_parts.erase(old)
	if not snapshot_parts.has(number): snapshot_parts[number] = {}
	snapshot_parts[number][index] = payload
	if snapshot_parts[number].size() != total: return
	var packed := PackedByteArray()
	for part in total: packed.append_array(snapshot_parts[number][part])
	snapshot_parts.erase(number)
	var state = bytes_to_var(packed.decompress_dynamic(256000,FileAccess.COMPRESSION_DEFLATE))
	if state is Dictionary and state.get("generation","") == generation: queue_snapshot(state)

@rpc("authority","call_remote","reliable",0)
func transition(payload: PackedByteArray):
	if payload.size() > 64000: return
	var state: Variant = bytes_to_var(payload.decompress_dynamic(256000,FileAccess.COMPRESSION_DEFLATE))
	if not state is Dictionary: return
	if server or closed or building or not round_ready or state.get("generation","") != generation or state.get("number",0) <= last_snapshot: return
	queue_snapshot(state)

@rpc("any_peer","call_remote","reliable",0)
func resynchronize(match_id: String):
	if not server or closed or building or match_id != generation: return
	var peer := multiplayer.get_remote_sender_id()
	if not peers.has(peer) or not peer_connected(peer): return
	var now := Time.get_ticks_msec()
	if now < peers[peer].get("resync_after",0): return
	peers[peer].resync_after = now+1000
	snapshot_number += 1
	transition.rpc_id(peer,pack_snapshot(peer))

func queue_snapshot(state: Dictionary):
	if state.number <= last_snapshot or state.number <= int(pending_snapshot.get("number",-1)): return
	pending_snapshot = state

func flush_client_state():
	if building or not round_ready or game == null: return
	if not pending_snapshot.is_empty():
		var newest := pending_snapshot
		pending_snapshot = {}
		apply_snapshot(newest)
	var events := pending_presentation
	pending_presentation = []
	for event in events: apply_presentation(event)

func apply_snapshot(state: Dictionary, first := false):
	last_snapshot = state.number
	resync_deadline = Time.get_ticks_msec()+500
	last_ack = state.ack
	silence_deadline = Time.get_ticks_msec()+8000
	game.phase = state.phase
	game.elapsed = state.elapsed
	game.countdown = state.countdown
	game.goal = state.goal
	game.team_scores = state.teams
	game.team_reached = state.reached
	game.team_colors.assign(state.colors)
	if first:
		for index in game.flags.size():
			game.tint_flag_cloth(game.flags[index].node,game.team_colors[index])
			game.flags[index].base_effect.configure(game.team_colors[index],game.reduced_motion)
	next_map = state.next_map
	game.result = state.result
	game.feed_events.assign(state.feed)
	if first: game.callouts.captions.clear()
	for line in state.captions:
		if first and line.critical:
			var caption: Dictionary = line.duplicate()
			caption["expires"] = game.callouts.clock+line.remaining
			caption.erase("remaining")
			game.callouts.captions.append(caption)
	var stadium := Assets.find(game.map.stadium,"AnimationPlayer") as AnimationPlayer
	if state.stadium_clip != "" and (stadium.current_animation != state.stadium_clip or absf(stadium.current_animation_position-float(state.stadium_time)) > 0.025):
		stadium.play(state.stadium_clip)
		stadium.seek(state.stadium_time,true)
		stadium.pause()
	game.map.jumbotron.motion.restore(state.jumbo)
	game.map.jumbotron.started = game.phase != "Waiting"
	if not game.loadout_started and (state.phase in ["Countdown","Active","Finished"]):
		game.loadout_started = true
		game.map.start_loadout()
	if state.phase in ["Countdown","Active","Finished"]:
		var assembly_time := ArenaMatch.MAP_ASSEMBLY_SECONDS
		if first or not game.map_assembly_finished:
			game.map.assembly.play("runtime/assemble")
			game.map.assembly.seek(assembly_time,true)
			game.map.assembly.pause()
		game.map_assembly_finished = assembly_time == ArenaMatch.MAP_ASSEMBLY_SECONDS
	game.map.event_warned = state.arena_warned
	game.map.event_done = state.arena_done
	var present: Array = []
	for actor in state.actors:
		present.append(actor.id)
		var robot: ArenaRobot = game.robot_by_id(actor.id)
		if robot == null:
			robot = game.add_robot(actor.id,actor.name,actor.team,true,actor.head)
			robot.tint = Color(actor.tint)
			robot.armor_secondary = Color(actor.secondary)
			robot.account_emote = actor.emote
			Assets.paint(robot.body,robot.tint,robot.armor_secondary,robot.head)
			if actor.id == local_id:
				game.local_robot = robot
				robot.listener.make_current()
				game.first_person = FirstPersonRig.new()
				game.first_person.robot = robot
				game.first_person.camera = game.camera
				game.add_child(game.first_person)
		if actor.id == local_id:
			var aim := Vector2(robot.yaw,robot.pitch)
			var move := robot.move_input
			robot.restore_network(actor,true)
			unacked = unacked.filter(func(command): return command.seq > state.ack)
			# Replaying seconds of physical movement on every snapshot can stall
			# receipt of the next snapshot. Bound extrapolation to 250 ms while
			# retaining the complete acknowledgement/resend history.
			for command in unacked.slice(maxi(0,unacked.size()-15)):
				OnlineInput.apply(robot,command,true)
				if robot.alive and robot.spawn_remaining <= 0 and robot.repair == null and game.phase == "Active": robot.simulate_movement(1.0/60.0,true,true)
			if not first and robot.spawn_remaining <= 0 and not robot.spawn_look_locked(): robot.yaw = aim.x; robot.pitch = aim.y
			robot.move_input = move
		else:
			var previous := robot.position
			var previous_yaw := robot.yaw
			var previous_pitch := robot.pitch
			robot.restore_network(actor)
			if first or previous.distance_to(robot.position) > 8.0: previous = robot.position; previous_yaw = robot.yaw; previous_pitch = robot.pitch
			remote_history[actor.id] = {"from":previous,"to":robot.position,"yaw_from":previous_yaw,"yaw_to":robot.yaw,"pitch_from":previous_pitch,"pitch_to":robot.pitch,"clock":0.0}
			robot.position = previous
			robot.yaw = previous_yaw
			robot.pitch = previous_pitch
	for robot in game.robots.duplicate():
		if robot.robot_id not in present: game.remove_robot(robot.robot_id); remote_history.erase(robot.robot_id)
	for value in state.fixtures:
		var found: Variant = game.map.fixture_by_id(value.id)
		if not found is Dictionary: continue
		var fixture: Dictionary = found
		if not fixture.node.global_transform.is_equal_approx(value.transform): fixture.node.global_transform = value.transform
		for key in value:
			if key in ["ready","cooldown","elapsed","open","active","inside","repair_active","usable"]: fixture[key] = value[key]
		if value.has("occupant"): fixture.occupant = game.robot_by_id(value.occupant)
		if fixture.has("payload") and is_instance_valid(fixture.payload): fixture.payload.visible = fixture.get("ready",false)
		if fixture.has("payload"): game.map.set_pickup_collision(fixture,fixture.get("ready",false))
		if value.has("motion"): fixture.motion.restore(value.motion)
		if fixture.kind == "repair_station": game.map.update_repair_status(fixture); game.map.update_repair_audio(fixture)
		if fixture.kind == "portal": game.map.update_portal_status(fixture)
		if value.has("animation"):
			var animator := Assets.find(fixture.node,"AnimationPlayer") as AnimationPlayer
			if animator and (animator.current_animation != value.animation or absf(animator.current_animation_position-float(value.time)) > 0.025):
				animator.play(value.animation)
				animator.seek(value.time,true)
				animator.pause()
	for index in state.flags.size():
		var flag: Dictionary = game.flags[index]
		var value: Dictionary = state.flags[index]
		flag.state = value.state
		flag.carrier = value.carrier
		flag.point = value.point
		flag.node.global_transform = value.transform
		flag.node.visible = game.match_type == "CTF" and game.phase in ["Active","Finished"]
		var player := Assets.find(flag.node,"AnimationPlayer") as AnimationPlayer
		var clip: String = value.get("animation","")
		if clip != "" and (player.current_animation != clip or absf(player.current_animation_position-float(value.frame)) > 0.2):
			player.play(clip)
			player.seek(value.frame,true)
	var missile_ids: Array = []
	for value in state.missiles:
		missile_ids.append(value.id)
		if not projectiles.has(value.id):
			var missile := ArenaProjectile.new()
			missile.game = game
			missile.weapon = value.weapon
			game.add_child(missile)
			missile.set_physics_process(false)
			projectiles[value.id] = missile
		var missile: ArenaProjectile = projectiles[value.id]
		missile.position = value.p
		missile.direction = value.direction
		missile.shooter = game.robot_by_id(value.get("shooter", -1))
		missile.distance = value.distance
		missile.orient_to_flight(value.direction)
		if not missile.presentation_configured: missile.configure_presentation()
		missile.update_presentation()
		if missile.weapon == "emp_gun": missile.update_emp_visual()
	for id in projectiles.keys():
		if id not in missile_ids: projectiles[id].retire(); projectiles.erase(id)
	var drop_ids: Array = []
	for value in state.drops:
		drop_ids.append(value.id)
		if not remote_drops.has(value.id):
			var orb := CoreOrb.new("energy",true)
			game.effects.add_child(orb)
			remote_drops[value.id] = orb
		remote_drops[value.id].global_position = value.p
	for id in remote_drops.keys():
		if id not in drop_ids: remote_drops[id].queue_free(); remote_drops.erase(id)
	var corpse_ids: Array = []
	for value in state.corpses:
		corpse_ids.append(value.id)
		if not remote_corpses.has(value.id):
			var robot: ArenaRobot = game.robot_by_id(value.robot)
			if robot == null: continue
			if value.animation.begins_with("common_"): robot.pose("common/"+value.animation.trim_prefix("common_"))
			var corpse := robot.body.duplicate() as Node3D
			Assets.paint(corpse,robot.tint,robot.armor_secondary,robot.head,true)
			game.add_child(corpse)
			corpse.show()
			for collider in corpse.find_children("*","CollisionObject3D",true,false): collider.collision_layer = 0
			remote_corpses[value.id] = corpse
		var corpse: Node3D = remote_corpses[value.id]
		corpse.global_transform = value.transform
		var animator := corpse.find_child("RuntimeAnimator",true,false) as AnimationPlayer
		if animator and value.animation != "": animator.play(value.animation); animator.seek(value.frame,true); animator.pause()
		if value.robot == local_id:
			game.local_death_corpse = corpse
			game.death_view_remaining = value.time
			game.local_fall_death = value.fall
	for id in remote_corpses.keys():
		if id not in corpse_ids: remote_corpses[id].queue_free(); remote_corpses.erase(id)
	if game.phase == "Finished" and not results_seen:
		results_seen = true
		game.completed.emit()

@rpc("authority","call_remote","reliable",3)
func presentation(match_id: String, events: Array):
	if server or closed or building or not round_ready or game == null or match_id != generation: return
	pending_presentation.append_array(events)
	if pending_presentation.size() > 512: pending_presentation = pending_presentation.slice(-512)

func apply_presentation(event: Dictionary):
	match event.kind:
		"elimination": game.receive_elimination(event)
		"shot":
			var robot: ArenaRobot = game.robot_by_id(event.robot)
			if robot == null or event.number <= robot.network_presented_shot: return
			robot.network_presented_shot = event.number
			if robot.equipped != event.weapon: return
			if event.robot == local_id and Time.get_ticks_msec()-robot.predicted_shot_time <= 200: return
			var barrel := robot.barrel
			var secondary := robot.wants_secondary
			robot.barrel = event.barrel
			robot.wants_secondary = event.secondary
			robot.weapon_vfx.begin_shot()
			robot.weapon_vfx.shot()
			game.audio.cue(Arsenal.shot_cue(event.weapon,event.secondary),robot.muzzle(),event.robot == local_id,robot)
			if event.weapon in ["pistol","rifle","minigun"]: game.effects.beam(robot.weapon_vfx.origin(),event.trace,Color("ffd295"),0.009)
			robot.barrel = barrel
			robot.wants_secondary = secondary
		"damage":
			var victim: ArenaRobot = game.robot_by_id(event.victim)
			if victim != null:
				var incoming := victim.shield_mesh.to_local(event.source)-Vector3(0,0.95,0)
				victim.shield_mesh.material_override.set_shader_parameter("hit_direction",incoming.normalized())
				victim.hit_flash = 0.2
			if event.attacker == local_id: game.hit_marker = 0.24
			if event.victim == local_id: game.damage_taken.emit(event.source,event.amount)
		"audio":
			var local: bool = event.near and (event.emitter == local_id or event.emitter == -1)
			if event.get("individual",false) and event.cue == "pickup_item":
				game.audio.energy_core_pickup(event.point,local,game.robot_by_id(event.emitter))
			else:
				game.audio.cue(event.cue,event.point,local,game.robot_by_id(event.emitter))
		"impact": game.effects.impact(event.point,event.normal,event.energy,null,event.robot)
		"explosion": game.effects.explosion(event.point,event.normal,event.size,event.incoming)
		"grenade_explosion": game.effects.grenade_explosion(event.point,event.normal)
		"pulse_contact": game.effects.pulse_contact(event.point,event.normal)
		"bio_contact": game.effects.bio_contact(event.point,event.normal)
		"flak_contact": game.effects.flak_contact(event.point,event.normal)
		"emp": game.effects.emp_contact(event.point,event.normal)
		"electric": game.effects.electric_contact(event.point,event.normal)
		"fire_orb": game.effects.fire_contact(event.point,event.normal)
		"caption": game.callouts.publish(event.text,event.speaker,event.team,event.critical,event.point,-1,int(event.get("robot_id",-1)),event.get("winner_ids",[]))

func _process(dt):
	if server or not round_ready or building or closed: return
	for id in remote_history:
		var robot: ArenaRobot = game.robot_by_id(id)
		if robot == null: continue
		var history: Dictionary = remote_history[id]
		history.clock += dt
		robot.position = history.from.lerp(history.to,clampf(history.clock/0.1,0,1))
		var blend := clampf(history.clock/0.1,0,1)
		robot.yaw = lerp_angle(history.yaw_from,history.yaw_to,blend)
		robot.pitch = lerpf(history.pitch_from,history.pitch_to,blend)
		robot.body.rotation.y = robot.yaw+robot.character.forward_yaw

func disconnected(peer: int):
	if not server: return
	pending_peers.erase(peer)
	if not peers.has(peer): return
	print("ONLINE_ROSTER disconnected peer=",peer," elapsed=",game.elapsed if game else -1," remaining=",peers.size()-1)
	var record: Dictionary = peers[peer]
	peers.erase(peer)
	game.remove_robot(record.id)
	private_request("release",{"reservation_id":record.reservation})
	if game.phase == "Countdown" and not game.roster_valid(): game.finish(true,"The roster no longer has both teams." if not MatchTypes.individual(game.match_type) else "Fewer than two players remain.")
	heartbeat_clock = 5

func close():
	if closed: return
	if not server and multiplayer.multiplayer_peer and multiplayer.multiplayer_peer.get_connection_status() == MultiplayerPeer.CONNECTION_CONNECTED:
		depart.rpc_id(1,generation)
		(multiplayer.multiplayer_peer as ENetMultiplayerPeer).get_host().flush()
	closed = true
	if multiplayer.multiplayer_peer: multiplayer.multiplayer_peer.close()
	if game: game.map.abort_all_repairs("disconnect")

@rpc("any_peer","call_remote","reliable",0)
func depart(match_id: String):
	if not server or closed or match_id != generation: return
	var peer := multiplayer.get_remote_sender_id()
	if not peers.has(peer): return
	disconnected(peer)
	multiplayer.multiplayer_peer.disconnect_peer(peer,true)
