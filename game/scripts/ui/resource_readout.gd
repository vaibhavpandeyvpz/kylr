class_name ResourceReadout
extends Control

var values := Vector3(0, 100, 100)
var shield_seconds := 0.0
var reduced_motion := false
var high_contrast := false
var displayed := Vector3(0, 100, 100)
var trailing := Vector3(0, 100, 100)
var previous := Vector3(0, 100, 100)
var flashes := [0.0, 0.0, 0.0]
var time := 0.0
var icons: Array[Texture2D] = [
	preload("res://assets/ui/icons/material_symbols/shield.svg"),
	preload("res://assets/ui/icons/material_symbols/health_and_safety.svg"),
	preload("res://assets/ui/icons/material_symbols/bolt.svg")]

func _ready() -> void:
	mouse_filter = Control.MOUSE_FILTER_IGNORE

func _process(dt: float) -> void:
	if not reduced_motion: time += dt
	for row in 3:
		if values[row] < previous[row] - 0.02: flashes[row] = 1.0
		previous[row] = values[row]
		displayed[row] = lerpf(displayed[row], values[row], 1.0 - exp(-12.0 * dt))
		trailing[row] = lerpf(trailing[row], values[row], 1.0 - exp(-2.6 * dt))
		flashes[row] = maxf(0.0, flashes[row] - dt * 2.3)
	queue_redraw()

func _draw() -> void:
	if size.x<80 or size.y<40: return
	var names := ["SHIELD", "ARMOR", "ENERGY"]
	var maxima := [100.0, 100.0, ArenaTuning.MAX_EP]
	var colors := [Color("a084f4"), HudSkin.CYAN, HudSkin.AMBER]
	var visible_rows := [1, 2] if values.x <= 0.0 else [0, 1, 2]
	for display_row in visible_rows.size():
		var row: int = visible_rows[display_row]
		var y := 10.0 + display_row * 47.0
		var color: Color = colors[row]
		if row == 1 and values[row] <= 25.0: color = HudSkin.DANGER
		if row == 2 and values[row] <= ArenaTuning.HALF_EP: color = HudSkin.DANGER
		var compact := size.x<240
		HudSkin.icon(self, icons[row], Vector2(5 if compact else 14,y+5),20.0 if compact else 24.0,color)
		var title: String = ["SH","AH","EP"][row] if compact else names[row]
		if row == 0: title += "  %02ds" % ceili(shield_seconds)
		HudSkin.label(self,title,Vector2(32 if compact else 45,y+19),12 if compact else 16,color,size.x-84 if compact else -1,true)
		var value_text := "%03d" % ceili(values[row])
		HudSkin.label(self, value_text, Vector2(size.x-(48 if compact else 63),y+20),18 if compact else 21,HudSkin.WHITE,44 if compact else 56, true)
		var x := 32.0 if compact else 45.0
		var width := size.x - x - 16.0
		draw_rect(Rect2(x, y + 28, width, 7), Color(0.02, 0.09, 0.12, 0.80 if not high_contrast else 0.96))
		var tail_width := width * clampf(trailing[row] / maxima[row], 0.0, 1.0)
		if tail_width > 0.0:
			draw_rect(Rect2(x, y + 28, tail_width, 7), Color(color.r, color.g, color.b, 0.32))
		var fill_width := width * clampf(displayed[row] / maxima[row], 0.0, 1.0)
		if fill_width > 0.0:
			draw_rect(Rect2(x, y + 28, fill_width, 7), color)
			draw_rect(Rect2(x + maxf(0.0, fill_width - 2.0), y + 25, 2, 11), color)
		if row == 2:
			draw_line(Vector2(x + width * 0.5, y + 25), Vector2(x + width * 0.5, y + 36), HudSkin.WHITE, 1.5)
		if flashes[row] > 0.0:
			draw_rect(Rect2(x, y + 25, width, 11), Color(color.r, color.g, color.b, flashes[row] * 0.12))
		if not reduced_motion:
			var scan := fposmod(time * 37.0 + row * 41.0, width)
			draw_line(Vector2(x + scan, y + 28), Vector2(x + scan, y + 33), Color(1, 1, 1, 0.18), 1)
