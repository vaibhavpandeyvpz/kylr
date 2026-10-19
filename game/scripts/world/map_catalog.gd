class_name MapCatalog
extends RefCounted
static func all() -> Array:
	var catalog: Dictionary = JSON.parse_string(FileAccess.get_file_as_string("res://data/maps/catalog.json"))
	return catalog.maps
static func find(id: String) -> Dictionary:
	for map in all():
		if map.id == id: return map
	return all()[0]
static func vector(value: Array) -> Vector3:
	return Vector3(value[0],value[1],value[2])
