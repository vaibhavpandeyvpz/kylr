class_name SettingsToggle
extends CheckButton
## Native switch input and accessibility, with an explicit readable state.

func _init():
	custom_minimum_size.y = 56
	mouse_default_cursor_shape = Control.CURSOR_POINTING_HAND
	add_theme_constant_override("h_separation",64)
	alignment = HORIZONTAL_ALIGNMENT_LEFT

func _draw():
	var font := get_theme_font("font")
	var font_size := 14
	var value := "On" if button_pressed else "Off"
	var tint := MenuSkin.MUTED.darkened(0.25) if disabled else MenuSkin.ACTION if button_pressed else MenuSkin.MUTED
	var right := size.x-get_theme_stylebox("normal").content_margin_right-get_theme_icon("checked").get_width()-12
	var baseline := (size.y-font.get_height(font_size))*0.5+font.get_ascent(font_size)
	draw_string(font,Vector2(right-font.get_string_size(value,HORIZONTAL_ALIGNMENT_LEFT,-1,font_size).x,baseline),value,HORIZONTAL_ALIGNMENT_LEFT,-1,font_size,tint)
