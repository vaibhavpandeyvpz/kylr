class_name ContentRegistry
extends RefCounted
static var cache: Dictionary = {}
static func read(path: String) -> Dictionary:
	if not cache.has(path):
		var parsed = JSON.parse_string(FileAccess.get_file_as_string(path))
		assert(parsed is Dictionary,"Invalid catalog: " + path)
		cache[path] = parsed
	return cache[path]
static func characters() -> Array:
	return read("res://data/characters/catalog.json").characters
static func character(id: String) -> Dictionary:
	for entry in characters():
		if entry.id == id: return entry
	return characters()[0]
static func weapons() -> Dictionary:
	return read("res://data/weapons/catalog.json").weapons
