class_name TutorialReadout
extends Control

const INFO := preload("res://assets/ui/icons/material_symbols/info.svg")
var text := "":
	set(value):
		if text == value: return
		text = value
		accessibility_name = value
		update_text()
var high_contrast := false:
	set(value):
		high_contrast = value
		queue_redraw()
var body := Label.new()
var heading := ""

func _ready() -> void:
	mouse_filter = Control.MOUSE_FILTER_IGNORE
	body.mouse_filter = Control.MOUSE_FILTER_IGNORE
	body.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	body.add_theme_font_override("font", HudSkin.BODY_FONT)
	body.add_theme_font_size_override("font_size", 16)
	body.add_theme_color_override("font_color", HudSkin.WHITE)
	body.add_theme_color_override("font_outline_color", Color(0,0,0,0.85))
	body.add_theme_constant_override("outline_size", 2)
	add_child(body)
	resized.connect(update_text)
	update_text()

func update_text() -> void:
	var lines := text.split("\n",true,1)
	heading = lines[0]
	body.text = lines[1] if lines.size()>1 else ""
	body.position = Vector2(16,44)
	body.size = Vector2(maxf(0,size.x-32),0)
	queue_redraw()

func _draw() -> void:
	if text.is_empty(): return
	var height := maxf(96,body.get_minimum_size().y+60)
	draw_rect(Rect2(0,0,size.x,height),Color(0.02,0.04,0.06,0.74 if high_contrast else 0.38))
	draw_line(Vector2(0,12),Vector2(0,height-12),HudSkin.CYAN,2)
	HudSkin.icon(self,INFO,Vector2(16,12),20,HudSkin.CYAN)
	HudSkin.label(self,heading,Vector2(44,28),15,HudSkin.CYAN,size.x-60,true)
