extends Node2D
## Paints the level's terrain with smooth, high-resolution textures.
## Collision comes from the (hidden) TileMapLayer; this node is visual only.

const TILE := 16
const TEX_SCALE := 4.0  # texture pixels per world pixel (see tools/generate_art.py)

const Soil := preload("res://assets/tiles/soil.png")
const Grass := preload("res://assets/tiles/grass.png")
const Stone := preload("res://assets/tiles/stone.png")
const StoneMoss := preload("res://assets/tiles/stone_moss.png")
const Ledge := preload("res://assets/tiles/ledge.png")

var level: Node


func _draw() -> void:
	if level == null:
		return
	var soil_period := Soil.get_width() / TEX_SCALE
	var grass_period := Grass.get_width() / TEX_SCALE
	var grass_h := Grass.get_height() / TEX_SCALE
	for r in level.height:
		for c in level.width:
			var ch: String = level.cell(c, r)
			var pos := Vector2(c * TILE, r * TILE)
			match ch:
				"#":
					var src := Vector2(fposmod(pos.x, soil_period), fposmod(pos.y, soil_period)) * TEX_SCALE
					draw_texture_rect_region(Soil, Rect2(pos, Vector2(TILE, TILE)), Rect2(src, Vector2(TILE, TILE) * TEX_SCALE))
					_edge_shading(c, r, pos)
				"=":
					var tex := Stone if level.is_solid(c, r - 1) else StoneMoss
					draw_texture_rect(tex, Rect2(pos, Vector2(TILE, TILE)), false)
	# grass and ledges go on top so blades can overhang neighbouring tiles
	for r in level.height:
		for c in level.width:
			var ch: String = level.cell(c, r)
			var pos := Vector2(c * TILE, r * TILE)
			if ch == "#" and not level.is_solid(c, r - 1) and not (level.cell(c, r - 1) in ["T", "~"]):
				var w := TILE + (2.0 if not level.is_solid(c + 1, r) else 0.0)
				var x0 := pos.x - (2.0 if not level.is_solid(c - 1, r) else 0.0)
				draw_texture_rect_region(Grass, Rect2(Vector2(x0, pos.y - 4.0), Vector2(w, grass_h)),
					Rect2(Vector2(fposmod(x0, grass_period) * TEX_SCALE, 0), Vector2(w * TEX_SCALE, Grass.get_height())))
			elif ch == "-":
				draw_texture_rect(Ledge, Rect2(pos + Vector2(0, -0.5), Vector2(TILE, Ledge.get_height() / TEX_SCALE)), false)


## Soft shadows: soil darkens with depth and along exposed side walls.
func _edge_shading(c: int, r: int, pos: Vector2) -> void:
	var depth := 0
	while depth < 4 and level.is_solid(c, r - depth - 1):
		depth += 1
	var shade_top := clampf(depth * 0.12, 0.0, 0.45)
	var shade_bottom := clampf((depth + 1) * 0.12, 0.0, 0.45)
	var black := Color(0.08, 0.04, 0.02)
	draw_polygon(
		PackedVector2Array([pos, pos + Vector2(TILE, 0), pos + Vector2(TILE, TILE), pos + Vector2(0, TILE)]),
		PackedColorArray([Color(black, shade_top), Color(black, shade_top), Color(black, shade_bottom), Color(black, shade_bottom)]))
	for side in [-1, 1]:
		if not level.is_solid(c + side, r) and not (level.cell(c + side, r) in ["T", "~"]):
			var x_edge: float = pos.x if side < 0 else pos.x + TILE
			var x_in: float = x_edge - side * 5.0
			draw_polygon(
				PackedVector2Array([Vector2(x_edge, pos.y), Vector2(x_in, pos.y), Vector2(x_in, pos.y + TILE), Vector2(x_edge, pos.y + TILE)]),
				PackedColorArray([Color(black, 0.45), Color(black, 0.0), Color(black, 0.0), Color(black, 0.45)]))
