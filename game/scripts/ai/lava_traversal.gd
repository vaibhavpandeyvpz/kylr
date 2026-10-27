class_name LavaTraversal
extends RefCounted
## Incremental physics-checked routes across authored lava footprints.
var traversal: TraversalGraph
var points: Dictionary = {}
var columns: Dictionary = {}
var jobs: Array[Dictionary] = []
var cursor:=0
var pads_done:=false

func _init(value: TraversalGraph):
	traversal=value
	for id in traversal.graph.get_point_ids():
		var point:=traversal.graph.get_point_position(id)
		points[id]=point
		var key:=Vector2i(roundi(point.x),roundi(point.z))
		if not columns.has(key):columns[key]=[]
		columns[key].append(id)
	for pit in traversal.arena.lava.pits:
		for id in points:
			var point: Vector3=points[id]
			if absf(point.y)>3.5:continue
			if pit.bounds.grow(1.8).has_point(Vector2(point.x,point.z)):
				jobs.append({"pit":pit,"id":id})

static func crosses_polygon(a: Vector3,b: Vector3,polygon: PackedVector2Array) -> bool:
	var pieces:=Geometry2D.intersect_polyline_with_polygon(PackedVector2Array([Vector2(a.x,a.z),Vector2(b.x,b.z)]),polygon)
	for piece in pieces:
		var length:=0.0
		for index in range(1,piece.size()):length+=piece[index-1].distance_to(piece[index])
		if length>.45:return true
	return false

static func flight_time(game,height: float,speed: float) -> float:
	var effective: float=game.jump_release_height(height)
	return effective/speed+(speed+sqrt(speed*speed+2.0*game.gravity*effective))/game.gravity

func step() -> bool:
	if cursor<jobs.size():
		var job: Dictionary=jobs[cursor];cursor+=1
		bake_bank(job.id,job.pit)
		return false
	if not pads_done:
		pads_done=true
		bake_pads()
	return true

func bake_bank(id: int,pit: Dictionary) -> void:
	var a: Vector3=points[id];var horizontal:=Vector2(a.x,a.z)
	if Geometry2D.is_point_in_polygon(horizontal,pit.polygon):return
	var nearest:=INF
	for index in pit.polygon.size():
		nearest=minf(nearest,horizontal.distance_to(Geometry2D.get_closest_point_to_segment(horizontal,pit.polygon[index],pit.polygon[(index+1)%pit.polygon.size()])))
	if nearest>1.8:return
	var game=traversal.arena.game
	var effective: float=game.jump_release_height(ArenaTuning.CHARGED_JUMP_HEIGHT)
	var speed: float=sqrt(2.0*game.gravity*effective)
	var reach:=ArenaTuning.RUN_SPEED*flight_time(game,ArenaTuning.CHARGED_JUMP_HEIGHT,speed)*.9
	var cell:=Vector2i(roundi(a.x),roundi(a.z));var radius:=ceili(reach)
	var candidates: Array[Dictionary]=[]
	for x in range(-radius,radius+1):
		for z in range(-radius,radius+1):
			for target_id in columns.get(cell+Vector2i(x,z),[]):
				if target_id==id:continue
				var b: Vector3=points[target_id]
				var distance:=a.distance_to(b)
				if distance>reach or distance<1.0 or absf(a.y-b.y)>.4:continue
				if traversal.graph.are_points_connected(id,target_id):continue
				if Geometry2D.is_point_in_polygon(Vector2(b.x,b.z),pit.polygon):continue
				if not crosses_polygon(a,b,pit.polygon):continue
				candidates.append({"id":target_id,"point":b,"distance":distance})
	# Keep a long and a short crossing per angular sector, rather than testing
	# every pair of shoreline nodes or adding an unbounded set of duplicate arcs.
	candidates.sort_custom(func(a_value,b_value):return a_value.distance>b_value.distance)
	var sectors: Dictionary={}
	for candidate in candidates:
		var b: Vector3=candidate.point
		var sector:=posmod(roundi(atan2(b.z-a.z,b.x-a.x)*8.0/PI),16)
		var normal_key:=Vector2i(sector,0);var charged_key:=Vector2i(sector,1)
		if sectors.has(normal_key) and sectors.has(charged_key):continue
		if not sectors.has(normal_key) and traversal.arc_clear(a,b,ArenaTuning.NORMAL_JUMP_HEIGHT):
			traversal.link(a,b,"jump",false);sectors[normal_key]=true
		elif not sectors.has(charged_key) and traversal.arc_clear(a,b,ArenaTuning.CHARGED_JUMP_HEIGHT):
			traversal.link(a,b,"charged_jump",false);sectors[charged_key]=true

func pad_arc_clear(a: Vector3,b: Vector3) -> bool:
	var game=traversal.arena.game
	var speed:=ArenaTuning.JUMP_PAD_SPEED
	var height: float=game.jump_release_height(ArenaTuning.JUMP_PAD_HEIGHT)
	var powered: float=height/speed
	var discriminant: float=speed*speed+2.0*game.gravity*(a.y+height-b.y)
	if discriminant<0:return false
	var flight: float=powered+(speed+sqrt(discriminant))/game.gravity
	var horizontal:=Vector2(b.x-a.x,b.z-a.z).length()
	if horizontal>(flight-.25)*ArenaTuning.RUN_SPEED*.85:return false
	if not traversal.supported(b) or not traversal.standing_clear(b) or traversal.crosses_portal(a,b):return false
	var capsule:=CapsuleShape3D.new();capsule.radius=.32;capsule.height=1.8
	var query:=PhysicsShapeQueryParameters3D.new();query.shape=capsule;query.collision_mask=1;query.margin=.001
	var previous:=a
	for index in range(1,33):
		var time: float=flight*index/32.0
		var released:=maxf(0.0,time-powered)
		var rise: float=speed*time if time<=powered else height+speed*released-game.gravity*released*released*.5
		var progress:=minf(1.0,ArenaTuning.RUN_SPEED*maxf(0.0,time-.15)/maxf(horizontal,.001))
		var next:=a.lerp(b,progress);next.y=a.y+rise
		query.transform=Transform3D(Basis.IDENTITY,previous+Vector3.UP*.9)
		query.motion=next-previous
		var safe: PackedFloat32Array=traversal.arena.get_world_3d().direct_space_state.cast_motion(query)
		if safe.size()!=2 or safe[0]<.999 or not traversal.standing_clear(next):return false
		previous=next
	return true

func bake_pads() -> void:
	for fixture in traversal.arena.fixtures:
		if fixture.kind!="jump_pad":continue
		var a: Vector3=fixture.point
		var support: Dictionary=traversal.arena.game.combat.ray(a+Vector3.UP*.5,a-Vector3.UP*.5,[],1)
		if support.is_empty():continue
		a.y=float(support.position.y)+.02
		var targets: Array[Dictionary]=[]
		for id in points:
			var b: Vector3=points[id];var distance:=a.distance_to(b)
			if distance<2.0 or distance>13.0 or absf(a.y-b.y)>.4:continue
			var crosses:=false
			for pit in traversal.arena.lava.pits:
				if crosses_polygon(a,b,pit.polygon):crosses=true;break
			if crosses:targets.append({"point":b,"distance":distance})
		targets.sort_custom(func(a_value,b_value):return a_value.distance>b_value.distance)
		var sectors: Dictionary={}
		for target in targets:
			var b: Vector3=target.point
			var sector:=posmod(roundi(atan2(b.z-a.z,b.x-a.x)*8.0/PI),16)
			if sectors.has(sector):continue
			if pad_arc_clear(a,b):
				traversal.link(a,b,"launch",false,fixture.point);sectors[sector]=true
