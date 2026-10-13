extends Node2D
## Atmosphere that follows the camera: drifting leaves, fireflies and a soft
## vignette. Purely cosmetic.

const LeafTexture := preload("res://assets/fx/leaf.png")
const GlowTexture := preload("res://assets/fx/glow.png")

const VIEW := Vector2(480, 270)


func _ready() -> void:
	z_index = 20
	add_child(_leaves())
	add_child(_fireflies())
	add_child(_vignette())


func _leaves() -> CPUParticles2D:
	var p := CPUParticles2D.new()
	p.texture = LeafTexture
	p.amount = 14
	p.lifetime = 9.0
	p.preprocess = 9.0
	p.local_coords = false
	p.emission_shape = CPUParticles2D.EMISSION_SHAPE_RECTANGLE
	p.emission_rect_extents = Vector2(VIEW.x * 0.7, 8)
	p.position = Vector2(0, -VIEW.y * 0.55)
	p.direction = Vector2(-0.3, 1)
	p.spread = 25.0
	p.gravity = Vector2(0, 8)
	p.initial_velocity_min = 8.0
	p.initial_velocity_max = 16.0
	p.angular_velocity_min = -90.0
	p.angular_velocity_max = 90.0
	p.angle_min = 0.0
	p.angle_max = 360.0
	p.scale_amount_min = 0.18
	p.scale_amount_max = 0.3
	p.color = Color(1, 1, 1, 0.85)
	return p


func _fireflies() -> CPUParticles2D:
	var p := CPUParticles2D.new()
	p.texture = GlowTexture
	p.amount = 18
	p.lifetime = 5.0
	p.preprocess = 5.0
	p.local_coords = false
	p.emission_shape = CPUParticles2D.EMISSION_SHAPE_RECTANGLE
	p.emission_rect_extents = VIEW * 0.5
	p.gravity = Vector2(0, -2)
	p.direction = Vector2(0, -1)
	p.spread = 180.0
	p.initial_velocity_min = 2.0
	p.initial_velocity_max = 8.0
	p.scale_amount_min = 0.12
	p.scale_amount_max = 0.3
	var ramp := Gradient.new()
	ramp.set_color(0, Color(1, 0.95, 0.6, 0.0))
	ramp.set_color(1, Color(1, 0.95, 0.6, 0.0))
	ramp.add_point(0.3, Color(1, 0.95, 0.6, 0.8))
	ramp.add_point(0.7, Color(1, 0.95, 0.6, 0.6))
	p.color_ramp = ramp
	var mat := CanvasItemMaterial.new()
	mat.blend_mode = CanvasItemMaterial.BLEND_MODE_ADD
	p.material = mat
	return p


func _vignette() -> CanvasLayer:
	var layer := CanvasLayer.new()
	layer.layer = 1
	var grad := Gradient.new()
	grad.set_color(0, Color(0, 0, 0, 0))
	grad.set_color(1, Color(0.02, 0.05, 0.03, 0.55))
	grad.add_point(0.6, Color(0, 0, 0, 0))
	var tex := GradientTexture2D.new()
	tex.gradient = grad
	tex.fill = GradientTexture2D.FILL_RADIAL
	tex.fill_from = Vector2(0.5, 0.5)
	tex.fill_to = Vector2(1.05, 1.05)
	tex.width = 256
	tex.height = 144
	var rect := TextureRect.new()
	rect.texture = tex
	rect.set_anchors_preset(Control.PRESET_FULL_RECT)
	rect.expand_mode = TextureRect.EXPAND_IGNORE_SIZE
	rect.stretch_mode = TextureRect.STRETCH_SCALE
	rect.mouse_filter = Control.MOUSE_FILTER_IGNORE
	layer.add_child(rect)
	return layer
