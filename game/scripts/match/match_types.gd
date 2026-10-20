class_name MatchTypes
extends RefCounted

const ALL := ["DM","TDM","CTF","ELIMINATION","GUNGAME"]
const LIVES := 5

static func individual(type: String) -> bool:
	return type in ["DM","ELIMINATION","GUNGAME"]

static func elimination_winners(entries: Array) -> Array:
	var most_lives := -1
	var candidates: Array = []
	for entry in entries:
		var lives := maxi(0,LIVES-int(entry.deaths))
		if lives>most_lives:
			most_lives=lives
			candidates=[entry]
		elif lives==most_lives: candidates.append(entry)
	return Arsenal.winners(candidates,"kills","reached") if most_lives>0 else []
