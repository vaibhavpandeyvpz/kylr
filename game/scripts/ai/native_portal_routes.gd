class_name NativePortalRoutes
extends RefCounted
## Exact portal costs over cached native AStar walking paths.
var walking:=AStar3D.new()
var transitions: Dictionary
var anchors: Array[int]=[]
var walks: Dictionary={}
var anchor_walks: Dictionary={}
var components: Dictionary={}
var roots: Dictionary={}

func _init(source: AStar3D,actions: Dictionary):
	transitions={}
	for id in source.get_point_ids():
		roots[id]=id
		walking.add_point(id,source.get_point_position(id),source.get_point_weight_scale(id))
		walking.set_point_disabled(id,source.is_point_disabled(id))
	for id in source.get_point_ids():
		for target in source.get_point_connections(id):
			if actions.get(Vector2i(id,target),"")=="portal":
				transitions[Vector2i(id,target)]="portal";continue
			walking.connect_points(id,target,false)
			if not source.is_point_disabled(id) and not source.is_point_disabled(target):
				var a:=component_root(id);var b:=component_root(target)
				if a!=b:roots[maxi(a,b)]=mini(a,b)
	for edge in transitions:
		for id in [edge.x,edge.y]:
			if walking.has_point(id) and id not in anchors:anchors.append(id)
	for id in walking.get_point_ids():components[id]=component_root(id)
	roots.clear()

func component_root(id: int) -> int:
	var root:=id
	while int(roots[root])!=root:root=roots[root]
	while int(roots[id])!=id:
		var next: int=roots[id];roots[id]=root;id=next
	return root

func prepare() -> void:
	for from_id in anchors:
		for to_id in anchors:walk(from_id,to_id)

func walk(from_id: int,to_id: int) -> Dictionary:
	var key:=Vector2i(from_id,to_id)
	var cache: Dictionary=anchor_walks if from_id in anchors and to_id in anchors else walks
	if not cache.has(key):
		var path:=walking.get_id_path(from_id,to_id) if components[from_id]==components[to_id] else PackedInt64Array()
		var cost:=0.0 if not path.is_empty() else INF
		for index in range(1,path.size()):
			cost+=walking.get_point_position(path[index-1]).distance_to(walking.get_point_position(path[index]))*walking.get_point_weight_scale(path[index])
		if cache.size()>=2048:cache.erase(cache.keys()[0])
		cache[key]={"ids":path,"cost":cost}
	return cache[key]

func path(from_id: int,to_id: int) -> PackedInt64Array:
	if from_id==to_id:return walking.get_id_path(from_id,to_id)
	if walking.is_point_disabled(from_id) or walking.is_point_disabled(to_id):return PackedInt64Array()
	var nodes: Array[int]=anchors.duplicate()
	for id in [from_id,to_id]:
		if id not in nodes:nodes.append(id)
	var distances: Dictionary={from_id:0.0}
	var visited: Dictionary={}
	var previous: Dictionary={}
	var segments: Dictionary={}
	while true:
		var current: int=-1;var best:=INF
		for id in distances:
			if not visited.has(id) and float(distances[id])<best:current=id;best=distances[id]
		if current<0:return PackedInt64Array()
		if current==to_id:break
		visited[current]=true
		for target in nodes:
			if visited.has(target) or walking.is_point_disabled(target):continue
			var segment: Dictionary=walk(current,target)
			if transitions.get(Vector2i(current,target),"")=="portal":
				var portal_cost: float=3.0*walking.get_point_weight_scale(target)
				if portal_cost<float(segment.cost):segment={"ids":PackedInt64Array([current,target]),"cost":portal_cost}
			var candidate: float=best+float(segment.cost)
			if candidate<float(distances.get(target,INF)):
				distances[target]=candidate;previous[target]=current;segments[target]=segment.ids
	var pieces: Array[PackedInt64Array]=[]
	var cursor:=to_id
	while cursor!=from_id:
		pieces.push_front(segments[cursor]);cursor=previous[cursor]
	var result:=PackedInt64Array([from_id])
	for piece in pieces:
		for index in range(1,piece.size()):result.append(piece[index])
	return result
