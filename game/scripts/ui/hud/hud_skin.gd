class_name HudSkin
extends RefCounted

const INK := MenuSkin.CANVAS
const SURFACE := Color(MenuSkin.PLATE,0.79)
const EDGE := Color(MenuSkin.ACTION,0.34)
const WHITE := MenuSkin.TEXT
const SOFT := MenuSkin.MUTED
const CYAN := MenuSkin.ACTION
const AMBER := MenuSkin.CAUTION
const DANGER := MenuSkin.DANGER
const GREEN := MenuSkin.SUCCESS
const DISPLAY_FONT := preload("res://assets/ui/fonts/Rajdhani-SemiBold.ttf")
const BOLD_FONT := preload("res://assets/ui/fonts/Rajdhani-Bold.ttf")
const BODY_FONT := preload("res://assets/ui/fonts/Inter.ttf")

static func plate(canvas: CanvasItem, rect: Rect2, accent: Color = CYAN, opacity := 1.0) -> void:
	var left := rect.position.x
	var top := rect.position.y
	var right := rect.end.x
	var bottom := rect.end.y
	var cut := minf(11.0, rect.size.y * 0.2)
	canvas.draw_rect(rect, Color(SURFACE.r, SURFACE.g, SURFACE.b, 0.70 * opacity))
	canvas.draw_line(Vector2(left, top + cut), Vector2(left + cut, top), Color(EDGE.r, EDGE.g, EDGE.b, EDGE.a * opacity), 1.0, true)
	canvas.draw_line(Vector2(left + cut, top), Vector2(left + minf(64.0, rect.size.x * 0.35), top), Color(accent.r, accent.g, accent.b, 0.86 * opacity), 2.0, true)
	canvas.draw_line(Vector2(right - cut, top), Vector2(right, top + cut), Color(EDGE.r, EDGE.g, EDGE.b, EDGE.a * opacity), 1.0, true)
	canvas.draw_line(Vector2(right, bottom - cut), Vector2(right - cut, bottom), Color(EDGE.r, EDGE.g, EDGE.b, EDGE.a * opacity), 1.0, true)
	canvas.draw_line(Vector2(left + cut, bottom), Vector2(left, bottom - cut), Color(EDGE.r, EDGE.g, EDGE.b, EDGE.a * opacity), 1.0, true)

static func icon(canvas: CanvasItem, texture: Texture2D, position: Vector2, side: float, tint: Color) -> void:
	if texture == null: return
	canvas.draw_texture_rect(texture, Rect2(position, Vector2(side, side)), false, tint)

static func fade_backdrop(canvas: CanvasItem, rect: Rect2, opacity: float) -> void:
	for step in 8:
		var slice := rect.size.x / 8.0
		var alpha := opacity * (1.0 - float(step) / 8.0 * 0.62)
		canvas.draw_rect(Rect2(rect.position.x + slice * step, rect.position.y, slice + 0.5, rect.size.y), Color(INK,alpha))

static func label(canvas: CanvasItem, value: String, position: Vector2, size: int, color: Color = WHITE, width := -1.0, display := false, alignment := HORIZONTAL_ALIGNMENT_LEFT, bold := false) -> void:
	var outline := Color(0, 0, 0, 0.78)
	var font: Font = BOLD_FONT if bold else DISPLAY_FONT if display else BODY_FONT
	canvas.draw_string_outline(font, position, value, alignment, width, size, 2 if size <= 21 else 1, outline)
	canvas.draw_string(font, position, value,
		alignment, width, size, color)

## Transient HUD text uses an open, softly fading scrim, not a modal plate.
static func message_style(node: Label, high_contrast := false) -> void:
	if node.has_meta("message_contrast") and node.get_meta("message_contrast") == high_contrast: return
	node.set_meta("message_contrast", high_contrast)
	var gradient := Gradient.new()
	gradient.offsets = PackedFloat32Array([0.0, 0.08, 0.82, 1.0])
	var alpha := 0.74 if high_contrast else 0.24
	gradient.colors = PackedColorArray([Color(INK,0), Color(INK,alpha), Color(INK,alpha), Color(INK,0)])
	var texture := GradientTexture2D.new()
	texture.gradient = gradient
	texture.width = 256
	texture.height = 2
	var backing := StyleBoxTexture.new()
	backing.texture = texture
	backing.content_margin_left = 12
	backing.content_margin_right = 12
	backing.content_margin_top = 8
	backing.content_margin_bottom = 8
	node.add_theme_stylebox_override("normal", backing)
	node.add_theme_font_override("font", BODY_FONT)
	node.add_theme_color_override("font_color", WHITE)
	node.add_theme_color_override("font_outline_color", Color(0,0,0,0.9))
	node.add_theme_constant_override("outline_size", 2)

static func message_accent(text: String) -> Color:
	if "ARENA /" in text or "POWER /" in text: return AMBER
	if text.ends_with("acquired"): return GREEN
	return CYAN
