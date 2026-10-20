class_name MatchHudFrame
extends Control

var arena_match: ArenaMatch
var viewer: ArenaRobot
var phase_text := ""
var repair_detail := ""
var notice_text := ""
var notice_remaining := 0.0
var reduced_motion := false
var high_contrast := false
var score_flash := 0.0
var last_score := ""
const SKULL := preload("res://assets/ui/icons/material_symbols/skull.svg")
const FLAG := preload("res://assets/ui/icons/material_symbols/flag.svg")

func _ready() -> void:
	mouse_filter = Control.MOUSE_FILTER_IGNORE

func _process(dt: float) -> void:
	if arena_match == null: return
	var key := arena_match.score_text()
	if not last_score.is_empty() and key != last_score: score_flash = 1.0
	last_score = key
	score_flash = maxf(0.0, score_flash - dt * 2.0)
	queue_redraw()

func _draw() -> void:
	if arena_match == null or viewer == null: return
	if arena_match.phase == "Countdown":
		_draw_phase(size.x * 0.5, 26)
		return
	_draw_score()
	_draw_leaders()
	if arena_match.match_type == "CTF": _draw_flags()
	if not phase_text.is_empty(): _draw_phase(size.x * 0.5, 142 if arena_match.match_type == "CTF" else 113)
	if notice_remaining > 0.0 and not notice_text.is_empty(): _draw_notice()

func _draw_score() -> void:
	var x := size.x * 0.5 - 235.0
	var rect := Rect2(x, 18, 470, 106 if arena_match.match_type == "CTF" else 76)
	draw_rect(rect, Color(0, 0, 0, 0.10))
	if score_flash > 0.0 and not reduced_motion:
		draw_rect(rect, Color(HudSkin.CYAN.r, HudSkin.CYAN.g, HudSkin.CYAN.b, score_flash * 0.11))
	HudSkin.label(self, arena_match.match_type, Vector2(x + 16, 39), 14, HudSkin.CYAN, 135, true, HORIZONTAL_ALIGNMENT_CENTER)
	_draw_timer_mark(Vector2(x + 212, 32))
	HudSkin.label(self, arena_match.clock_text(), Vector2(x + 205, 39), 17, HudSkin.WHITE, 79, true, HORIZONTAL_ALIGNMENT_CENTER)
	HudSkin.label(self, "GOAL %d" % arena_match.goal, Vector2(x + 319, 39), 13, HudSkin.SOFT, 135, true, HORIZONTAL_ALIGNMENT_CENTER)
	if MatchTypes.individual(arena_match.match_type):
		HudSkin.label(self, "YOUR KILLS", Vector2(x + 16, 55), 13, HudSkin.CYAN, 135, true, HORIZONTAL_ALIGNMENT_CENTER)
		HudSkin.label(self, "LIVES" if arena_match.match_type=="ELIMINATION" else "TARGET", Vector2(x + 319, 55), 13, HudSkin.SOFT, 135, true, HORIZONTAL_ALIGNMENT_CENTER)
		HudSkin.label(self, "%02d" % viewer.kills, Vector2(x + 16, 84), 31, HudSkin.WHITE, 135, true, HORIZONTAL_ALIGNMENT_CENTER)
		HudSkin.label(self, "%02d" % (viewer.lives_remaining() if arena_match.match_type=="ELIMINATION" else arena_match.goal), Vector2(x + 319, 84), 31, HudSkin.WHITE, 135, true, HORIZONTAL_ALIGNMENT_CENTER)
		HudSkin.label(self, "ELIMINATIONS", Vector2(x + 165, 80), 12, HudSkin.SOFT, 140, true, HORIZONTAL_ALIGNMENT_CENTER)
	else:
		var left_color: Color = arena_match.team_colors[0]
		var right_color: Color = arena_match.team_colors[1]
		HudSkin.label(self, "TEAM A" + ("  /  YOU" if viewer.team == 0 else ""), Vector2(x + 16, 55), 13, left_color, 135, true, HORIZONTAL_ALIGNMENT_CENTER)
		HudSkin.label(self, "TEAM B" + ("  /  YOU" if viewer.team == 1 else ""), Vector2(x + 319, 55), 13, right_color, 135, true, HORIZONTAL_ALIGNMENT_CENTER)
		HudSkin.label(self, "%02d" % arena_match.team_scores[0], Vector2(x + 16, 84), 31, HudSkin.WHITE, 135, true, HORIZONTAL_ALIGNMENT_CENTER)
		HudSkin.label(self, "%02d" % arena_match.team_scores[1], Vector2(x + 319, 84), 31, HudSkin.WHITE, 135, true, HORIZONTAL_ALIGNMENT_CENTER)
		draw_line(Vector2(x + 16, 92), Vector2(x + 151, 92), left_color, 3, true)
		draw_line(Vector2(x + 319, 92), Vector2(x + 454, 92), right_color, 3, true)
		HudSkin.label(self, "CAPTURES" if arena_match.match_type == "CTF" else "ELIMINATIONS", Vector2(x + 165, 80), 12, HudSkin.SOFT, 140, true, HORIZONTAL_ALIGNMENT_CENTER)

func _draw_timer_mark(center: Vector2) -> void:
	draw_arc(center, 6.0, 0.0, TAU, 28, HudSkin.SOFT, 1.1, true)
	draw_line(center + Vector2(0, -8.5), center + Vector2(0, -6.5), HudSkin.SOFT, 1.1, true)
	draw_line(center, center + Vector2(2.2, -3.3), HudSkin.SOFT, 1.1, true)

func _draw_leaders() -> void:
	var x := 23.0
	var y := 106.0
	HudSkin.fade_backdrop(self, Rect2(x - 5, y - 4, 250, 174), 0.55)
	HudSkin.icon(self, SKULL, Vector2(x, y), 18, HudSkin.CYAN)
	HudSkin.label(self, "TOP KILLERS", Vector2(x + 25, y + 15), 14, HudSkin.CYAN, -1, true)
	var ranked: Array = arena_match.robots.duplicate()
	ranked.sort_custom(func(a, b): return a.kills > b.kills)
	for index in mini(5, ranked.size()):
		var robot = ranked[index]
		var row_y := y + 36.0 + index * 28.0
		var local: bool = robot == viewer
		var color := arena_match.team_colors[robot.team] if not MatchTypes.individual(arena_match.match_type) else HudSkin.CYAN if local else HudSkin.SOFT
		if local: draw_rect(Rect2(x, row_y - 15, 238, 25), Color(color.r, color.g, color.b, 0.18))
		draw_line(Vector2(x, row_y - 13), Vector2(x, row_y + 9), color, 2, true)
		HudSkin.label(self, "%02d" % (index + 1), Vector2(x + 10, row_y + 3), 15, color, -1, true)
		HudSkin.label(self, robot.display_name.left(17), Vector2(x + 42, row_y + 2), 13, HudSkin.WHITE if local else HudSkin.SOFT, 160)
		HudSkin.label(self, "%d" % robot.kills, Vector2(x + 214, row_y + 3), 16, HudSkin.WHITE, -1, true)

func _draw_flags() -> void:
	var x := size.x * 0.5 - 235.0
	for team in 2:
		var flag: Dictionary = arena_match.flags[team]
		var tint: Color = arena_match.team_colors[team]
		var state: String = String(flag.state).to_upper()
		if flag.state == "carried":
			var carrier = arena_match.robot_by_id(flag.carrier)
			state = "CARRIED / " + carrier.display_name.left(11) if carrier else "CARRIED"
		var text_width := HudSkin.DISPLAY_FONT.get_string_size(state, HORIZONTAL_ALIGNMENT_LEFT, -1, 12).x
		var center := x + (83.5 if team == 0 else 386.5)
		var left := center - (18.0 + text_width) * 0.5
		HudSkin.icon(self, FLAG, Vector2(left, 99), 14, tint)
		HudSkin.label(self, state, Vector2(left + 18, 111), 12, tint, text_width + 4, true)

func _draw_phase(center_x: float, y: float) -> void:
	var width := minf(440.0, size.x * 0.44)
	var left := center_x - width * 0.5
	draw_line(Vector2(left, y + 19), Vector2(left + 30, y + 19), HudSkin.CYAN, 1.5)
	draw_line(Vector2(left + width - 30, y + 19), Vector2(left + width, y + 19), HudSkin.CYAN, 1.5)
	var text_width := HudSkin.DISPLAY_FONT.get_string_size(phase_text, HORIZONTAL_ALIGNMENT_LEFT, -1, 16).x
	HudSkin.label(self, phase_text, Vector2(center_x - text_width * 0.5, y + 24), 16, HudSkin.WHITE, width, true)
	if not repair_detail.is_empty():
		HudSkin.fade_backdrop(self, Rect2(left, y + 31, width, 26), 0.74 if high_contrast else 0.24)
		HudSkin.label(self, repair_detail, Vector2(left, y + 49), 13, HudSkin.CYAN, width, true, HORIZONTAL_ALIGNMENT_CENTER)

func _draw_notice() -> void:
	var opacity := clampf(notice_remaining / 0.4, 0.0, 1.0)
	var width := minf(440.0, size.x * 0.4 - 32.0)
	if width <= 32: return
	var left := 24.0
	var top := size.y - 218.0
	var accent := HudSkin.message_accent(notice_text)
	HudSkin.fade_backdrop(self, Rect2(left, top, width, 32), (0.74 if high_contrast else 0.24) * opacity)
	draw_line(Vector2(left, top + 6), Vector2(left, top + 26), Color(accent, opacity), 2)
	HudSkin.label(self, notice_text, Vector2(left + 12, top + 22), 16,
		Color(HudSkin.WHITE, opacity), width - 24)
