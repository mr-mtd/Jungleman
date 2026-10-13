class_name Water
extends Area2D
## Deep water. Falling in is fatal, so hop across on the crocodiles.

const KILL_DEPTH := 6.0

var size := Vector2(64, 32)
var _time := 0.0


func _ready() -> void:
	z_index = 5
	collision_layer = 0
	collision_mask = 2
	var col := CollisionShape2D.new()
	var rect := RectangleShape2D.new()
	rect.size = Vector2(size.x, size.y - KILL_DEPTH)
	col.shape = rect
	col.position = Vector2(size.x / 2.0, KILL_DEPTH + rect.size.y / 2.0)
	add_child(col)
	body_entered.connect(func(b): if b.has_method("die"): b.die(false))


func _process(delta: float) -> void:
	_time += delta
	queue_redraw()


func _draw() -> void:
	var w := size.x
	var h := size.y
	var top := PackedVector2Array()
	for i in int(w / 2.0) + 1:
		var x := i * 2.0
		top.append(Vector2(x, sin(x * 0.18 + _time * 2.0) * 0.9 + sin(x * 0.07 - _time * 1.3) * 0.6))
	var body := PackedVector2Array(top)
	body.append(Vector2(w, h))
	body.append(Vector2(0, h))
	var colors := PackedColorArray()
	for p in body:
		colors.append(Color("3aa6c8").lerp(Color("0c3552"), clampf(p.y / h, 0.0, 1.0)) * Color(1, 1, 1, 0.88))
	draw_polygon(body, colors)
	# foam line and soft highlight
	draw_polyline(top, Color(0.85, 0.97, 1.0, 0.9), 0.8, true)
	draw_polyline(top, Color(0.85, 0.97, 1.0, 0.25), 2.6, true)
	# drifting caustic glints
	for i in int(w / 14.0):
		var gx := fmod(i * 17.0 + _time * (6.0 + i % 3), w - 8.0) + 2.0
		var gy := 4.0 + fmod(i * 7.0, maxf(h - 8.0, 1.0))
		var a := 0.12 + 0.1 * sin(_time * 2.0 + i)
		draw_line(Vector2(gx, gy), Vector2(gx + 4.0 + (i % 3), gy), Color(1, 1, 1, a), 0.8, true)
