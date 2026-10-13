class_name TarPit
extends Area2D
## Sticky tar. You sink slowly and move at a crawl; mash Jump to climb out
## before you go under.

const TilesTexture := preload("res://assets/tiles/jungle_tiles.png")
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
	var x := 0.0
	while x < size.x:
		draw_texture_rect_region(TilesTexture, Rect2(x, SURFACE_DROP, 16, 16), Rect2(128, 0, 16, 16))
		var y := 16.0 + SURFACE_DROP
		while y < size.y:
			draw_texture_rect_region(TilesTexture, Rect2(x, y, 16, minf(16.0, size.y - y)), Rect2(144, 0, 16, minf(16.0, size.y - y)))
			y += 16.0
		x += 16.0
	# slow bubbles
	for i in int(size.x / 24.0):
		var t := fmod(_time * 0.6 + i * 0.37, 1.0)
		var bx := fmod(i * 23.0 + 7.0, size.x - 4.0) + 2.0
		draw_circle(Vector2(bx, SURFACE_DROP + 1.0), 1.0 + t * 2.0, Color(0.25, 0.2, 0.3, 1.0 - t))
