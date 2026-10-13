class_name TarPit
extends Area2D
## Sticky tar. You sink slowly and move at a crawl; mash Jump to climb out
## before you go under.

const SURFACE_DROP := 3.0

var size := Vector2(64, 32)
var _time := 0.0


func _ready() -> void:
	z_index = 5
	collision_layer = 0
	collision_mask = 2
	var col := CollisionShape2D.new()
	var rect := RectangleShape2D.new()
	rect.size = Vector2(size.x, size.y - SURFACE_DROP)
	col.shape = rect
	col.position = Vector2(size.x / 2.0, SURFACE_DROP + rect.size.y / 2.0)
	add_child(col)
	body_entered.connect(func(b): if b.has_method("enter_tar"): b.enter_tar(self))
	body_exited.connect(func(b): if b.has_method("exit_tar"): b.exit_tar(self))


func surface_y() -> float:
	return global_position.y + SURFACE_DROP


func _process(delta: float) -> void:
	_time += delta
	queue_redraw()


func _draw() -> void:
	var top := SURFACE_DROP
	var w := size.x
	var h := size.y
	# glossy body: deep purple-black gradient with a soft rim where it meets the soil
	draw_polygon(
		PackedVector2Array([Vector2(0, top), Vector2(w, top), Vector2(w, h), Vector2(0, h)]),
		PackedColorArray([Color("3a2c4a"), Color("3a2c4a"), Color("07050c"), Color("07050c")]))
	# gently rippling surface line
	var surface := PackedVector2Array()
	for i in int(w / 2.0) + 1:
		var x := i * 2.0
		surface.append(Vector2(x, top + sin(x * 0.25 + _time * 1.4) * 0.5))
	draw_polyline(surface, Color(0.62, 0.52, 0.78, 0.8), 0.9, true)
	draw_polyline(surface, Color(0.85, 0.78, 1.0, 0.25), 2.4, true)
	# sheen streaks
	for i in int(w / 22.0):
		var sx := fmod(i * 19.0 + _time * 4.0, w - 10.0) + 2.0
		draw_line(Vector2(sx, top + 3.0), Vector2(sx + 7.0, top + 3.0), Color(1, 1, 1, 0.08), 1.2, true)
	# slow bubbles that swell and pop
	for i in int(w / 18.0) + 1:
		var t := fmod(_time * 0.5 + i * 0.37, 1.0)
		var bx := fmod(i * 23.0 + 7.0, w - 6.0) + 3.0
		var r := 0.6 + t * 2.4
		draw_circle(Vector2(bx, top + 0.5), r, Color(0.18, 0.13, 0.25, 1.0 - t * 0.7))
		draw_arc(Vector2(bx, top + 0.5), r, PI * 1.1, PI * 1.6, 8, Color(0.9, 0.8, 1.0, 0.5 * (1.0 - t)), 0.5, true)
