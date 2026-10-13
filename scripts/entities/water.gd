class_name Water
extends Area2D
## Deep water. Falling in is fatal, so hop across on the crocodiles.

const TilesTexture := preload("res://assets/tiles/jungle_tiles.png")
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
	var shift := fmod(_time * 8.0, 16.0)
	var x := -16.0
	while x < size.x:
		var dx := x + shift
		var left := maxf(dx, 0.0)
		var right := minf(dx + 16.0, size.x)
		if right > left:
			var src_x := left - dx
			draw_texture_rect_region(TilesTexture, Rect2(left, 0, right - left, 16), Rect2(160 + src_x, 0, right - left, 16), Color(1, 1, 1, 0.9))
			var y := 16.0
			while y < size.y:
				draw_texture_rect_region(TilesTexture, Rect2(left, y, right - left, 16), Rect2(176 + src_x, 0, right - left, 16), Color(1, 1, 1, 0.9))
				y += 16.0
		x += 16.0
