class_name HudKillFeed
extends Control

var arena_match: ArenaMatch
var rows: Array[RichTextLabel] = []
var show_callouts := true
const SKULL := preload("res://assets/ui/icons/material_symbols/skull.svg")

func _ready() -> void:
	mouse_filter = Control.MOUSE_FILTER_IGNORE
	for index in 4:
		var row := RichTextLabel.new()
		row.bbcode_enabled = true
		row.scroll_active = false
		row.mouse_filter = Control.MOUSE_FILTER_IGNORE
		row.accessibility_live = 1
		row.add_theme_font_override("normal_font", HudSkin.BODY_FONT)
		row.add_theme_font_override("bold_font", HudSkin.BOLD_FONT)
		row.add_theme_font_size_override("normal_font_size", 14)
		row.add_theme_font_size_override("bold_font_size", 15)
		row.add_theme_color_override("font_shadow_color", Color(0, 0, 0, 0.92))
		row.add_theme_constant_override("shadow_offset_x", 1)
		row.add_theme_constant_override("shadow_offset_y", 1)
		row.add_theme_stylebox_override("normal", StyleBoxEmpty.new())
		row.position = Vector2(12, 34 + index * 42)
		row.size = Vector2(size.x - 18, 36)
		add_child(row)
		rows.append(row)

func _process(_dt: float) -> void:
	if arena_match == null: return
	var active := active_events(arena_match,show_callouts)
	for index in rows.size():
		var row := rows[index]
		row.size.x = size.x - 18
		row.visible = index < active.size()
		if not row.visible: continue
		var event := active[index]
		var formatted := format_event(event, arena_match.match_type, arena_match.team_colors)
		if row.text != formatted:
			row.text = formatted
			row.accessibility_name = row.get_parsed_text()
		row.modulate.a = clampf(float(event.remaining) / 0.7, 0.0, 1.0)
		row.position.x = 12.0
	visible = not active.is_empty()
	queue_redraw()

func _draw() -> void:
	if arena_match == null or not visible: return
	HudSkin.icon(self, SKULL, Vector2(0, 0), 18, HudSkin.CYAN)
	HudSkin.label(self, "KILL FEED", Vector2(25, 15), 14, HudSkin.CYAN, -1, true)
	for index in rows.size():
		if not rows[index].visible: continue
		var y := 30.0 + index * 42.0
		HudSkin.fade_backdrop(self, Rect2(0, y, size.x, 38), 0.51 * rows[index].modulate.a)
		draw_line(Vector2(0, y + 2), Vector2(0, y + 34), Color(HudSkin.CYAN.r, HudSkin.CYAN.g, HudSkin.CYAN.b, rows[index].modulate.a * 0.68), 2)

static func active_events(game: ArenaMatch, include_callouts: bool) -> Array[Dictionary]:
	var active: Array[Dictionary] = []
	for source in game.feed_events:
		var age := game.elapsed - float(source.time)
		if age >= 5.0: continue
		var event: Dictionary = source.duplicate()
		event["age"] = age
		event["remaining"] = 5.0-age
		active.append(event)
	if include_callouts and game.callouts:
		for line in game.callouts.captions:
			var remaining: float = float(line.expires)-game.callouts.clock
			if remaining<=0: continue
			active.append({"kind":"callout","actor":line.get("speaker","Announcer"),"team":line.get("team",-1) if line.get("robot_feed",false) else -1,
				"announcement":not line.get("robot_feed",false),"text":line.get("utterance",line.text),"direction":line.get("direction",""),"age":4.0-remaining,"remaining":remaining})
	active.sort_custom(func(a,b): return a.age<b.age)
	return active.slice(0,4)

static func sentence(value: String) -> String:
	for prefix in ["ARENA / ","POWER / "]:
		value=value.trim_prefix(prefix)
	if not value.is_empty() and not value.ends_with(".") and not value.ends_with("!") and not value.ends_with("?"):
		value += "."
	return value

static func safe(value: String) -> String:
	return value.replace("[", "［").replace("]", "］")

static func person(name: String, team: int, mode: String, colors: Array[Color]) -> String:
	var color := HudSkin.WHITE
	if not MatchTypes.individual(mode) and team >= 0 and team < colors.size(): color = colors[team]
	return "[b][color=#%s]%s[/color][/b]" % [color.to_html(false), safe(name)]

static func format_event(event: Dictionary, mode: String, colors: Array[Color]) -> String:
	match String(event.kind):
		"callout":
			if event.get("announcement",false): return "[b]Announcement:[/b] " + safe(sentence(event.text))
			return "%s said: %s%s" % [person(event.actor,int(event.team),mode,colors),safe(sentence(event.text)),safe(event.get("direction",""))]
		"kill":
			return "%s killed %s with [b]%s[/b]." % [
				person(event.killer, int(event.killer_team), mode, colors),
				person(event.victim, int(event.victim_team), mode, colors), safe(event.weapon)]
		"death":
			var victim := person(event.victim, int(event.victim_team), mode, colors)
			return "%s fell from the arena." % victim if String(event.cause).to_lower().contains("fall") else "%s died." % victim
		"flag":
			return "%s %s." % [person(event.actor, int(event.team), mode, colors), safe(event.action)]
		"leave":
			return "%s left the match." % person(event.actor, int(event.team), mode, colors)
	return ""
