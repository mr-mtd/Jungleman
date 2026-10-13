extends Node2D
## Builds a level from an ASCII map: ground tiles, hazards, enemies and pickups.
##
## Map legend (one character = one 16x16 tile):
##   #  jungle ground (grass is added automatically on top)
##   =  temple stone block
##   -  wooden ledge you can jump up through
##   T  tar pit (the run of T's sets its width and depth)
##   ~  water (deadly; ride the crocodiles across)
##   C  crocodile (sits on the water surface below it)
##   B  crumbling bridge plank
##   V  swinging vine anchor
##   Z  zipline start   z  zipline end (pairs are matched left to right)
##   R  rolling log spawner (logs roll to the left)
##   S  snake   K  scorpion   W  bat
##   G  gold treasure   o  sling stones   H  canteen (health)   L  extra life
##   I  checkpoint idol   E  temple exit   P  player start

const TILE := 16

const PlayerScene := preload("res://scenes/player.tscn")
const VineScene := preload("res://scenes/entities/vine.tscn")
const ZiplineScene := preload("res://scenes/entities/zipline.tscn")
const TarPitScene := preload("res://scenes/entities/tar_pit.tscn")
const WaterScene := preload("res://scenes/entities/water.tscn")
const CrocScene := preload("res://scenes/entities/crocodile.tscn")
const PlankScene := preload("res://scenes/entities/crumble_plank.tscn")
const LogSpawnerScene := preload("res://scenes/entities/log_spawner.tscn")
const SnakeScene := preload("res://scenes/entities/snake.tscn")
const ScorpionScene := preload("res://scenes/entities/scorpion.tscn")
const BatScene := preload("res://scenes/entities/bat.tscn")
const PickupScene := preload("res://scenes/entities/pickup.tscn")
const CheckpointScene := preload("res://scenes/entities/checkpoint.tscn")
const ExitScene := preload("res://scenes/entities/exit_door.tscn")
const HudScene := preload("res://scenes/ui/hud.tscn")
const AmbienceScript := preload("res://scripts/fx/ambience.gd")

enum Collision { SOLID, LEDGE }

@export var map_script: Script = preload("res://levels/level_1_map.gd")
@export var level_title := "LEVEL 1 - THE MAYAN JUNGLE"

var rows: Array = []
var width := 0
var height := 0
var player: Player

@onready var ground: TileMapLayer = $Ground
@onready var ground_art: Node2D = $GroundArt
@onready var entities: Node2D = $Entities


func _ready() -> void:
	rows = map_script.ROWS
	height = rows.size()
	for r in rows:
		width = max(width, (r as String).length())
	ground.tile_set = _make_tileset()
	_build_tiles()
	_build_hazards()
	_spawn_entities()
	add_child(HudScene.instantiate())
	GameState.show_message(level_title, 3.0)
	queue_redraw()


## Darkens bottomless pits so they read as holes rather than background.
func _draw() -> void:
	for c in width:
		if is_solid(c, height - 1) or cell(c, height - 1) == "~":
			continue
		var top := _ground_row_near(c)
		var y0 := top * TILE
		var y1 := height * TILE
		var dark := Color(0.04, 0.05, 0.03)
		draw_polygon(
			PackedVector2Array([Vector2(c * TILE, y0), Vector2((c + 1) * TILE, y0), Vector2((c + 1) * TILE, y1), Vector2(c * TILE, y1)]),
			PackedColorArray([Color(dark, 0.0), Color(dark, 0.0), Color(dark, 1.0), Color(dark, 1.0)]))


func _ground_row_near(c: int) -> int:
	for offset in width:
		for side in [-1, 1]:
			var nc: int = c + side * offset
			if nc >= 0 and nc < width and is_solid(nc, height - 1):
				for r in height:
					if is_solid(nc, r) and cell(nc, r) != "=":
						return r
	return height - 4


func cell(c: int, r: int) -> String:
	if r < 0 or r >= height or c < 0:
		return " "
	var row: String = rows[r]
	return row[c] if c < row.length() else " "


func is_solid(c: int, r: int) -> bool:
	return cell(c, r) in ["#", "="]


func tile_center(c: int, r: int) -> Vector2:
	return Vector2(c * TILE + TILE / 2.0, r * TILE + TILE / 2.0)


## Collision-only tileset; the visible terrain is painted by GroundArt.
func _make_tileset() -> TileSet:
	var ts := TileSet.new()
	ts.tile_size = Vector2i(TILE, TILE)
	ts.add_physics_layer()
	ts.set_physics_layer_collision_layer(0, 1)
	ts.set_physics_layer_collision_mask(0, 0)
	var img := Image.create(TILE * 2, TILE, false, Image.FORMAT_RGBA8)
	img.fill(Color.WHITE)
	var src := TileSetAtlasSource.new()
	src.texture = ImageTexture.create_from_image(img)
	src.texture_region_size = Vector2i(TILE, TILE)
	ts.add_source(src, 0)
	var full := PackedVector2Array([Vector2(-8, -8), Vector2(8, -8), Vector2(8, 8), Vector2(-8, 8)])
	var top := PackedVector2Array([Vector2(-8, -8), Vector2(8, -8), Vector2(8, -3), Vector2(-8, -3)])
	for i in [Collision.SOLID, Collision.LEDGE]:
		src.create_tile(Vector2i(i, 0))
		var td := src.get_tile_data(Vector2i(i, 0), 0)
		td.add_collision_polygon(0)
		td.set_collision_polygon_points(0, 0, top if i == Collision.LEDGE else full)
		td.set_collision_polygon_one_way(0, 0, i == Collision.LEDGE)
	return ts


func _build_tiles() -> void:
	for r in height:
		for c in width:
			var ch := cell(c, r)
			if ch == "#" or ch == "=":
				ground.set_cell(Vector2i(c, r), 0, Vector2i(Collision.SOLID, 0))
			elif ch == "-":
				ground.set_cell(Vector2i(c, r), 0, Vector2i(Collision.LEDGE, 0))
	ground.visible = false
	ground_art.level = self
	ground_art.queue_redraw()


## Groups horizontal runs of tar/water into single hazard areas.
func _build_hazards() -> void:
	for r in height:
		var c := 0
		while c < width:
			var ch := cell(c, r)
			if (ch == "T" or ch == "~") and cell(c, r - 1) != ch:
				var start := c
				while cell(c, r) == ch:
					c += 1
				var depth := 0
				while cell(start, r + depth) == ch:
					depth += 1
				var hazard: Node2D = (TarPitScene if ch == "T" else WaterScene).instantiate()
				hazard.position = Vector2(start * TILE, r * TILE)
				hazard.size = Vector2((c - start) * TILE, depth * TILE)
				entities.add_child(hazard)
			else:
				c += 1


func _spawn_entities() -> void:
	var zip_starts: Array[Vector2] = []
	var zip_ends: Array[Vector2] = []
	var spawn := Vector2(48, 100)
	for r in height:
		for c in width:
			var ch := cell(c, r)
			var p := tile_center(c, r)
			var bottom := Vector2(p.x, (r + 1) * TILE)  # standing on the tile below
			var node: Node2D = null
			match ch:
				"P":
					spawn = bottom + Vector2(0, -13)
				"V":
					node = VineScene.instantiate()
					node.position = p
					node.phase = c * 0.7
				"Z":
					zip_starts.append(p)
				"z":
					zip_ends.append(p)
				"C":
					node = CrocScene.instantiate()
					node.position = bottom
				"B":
					node = PlankScene.instantiate()
					node.position = Vector2(p.x, r * TILE)
				"R":
					node = LogSpawnerScene.instantiate()
					node.position = p
				"S":
					node = SnakeScene.instantiate()
					node.position = bottom + Vector2(0, -8)
				"K":
					node = ScorpionScene.instantiate()
					node.position = bottom + Vector2(0, -7)
				"W":
					node = BatScene.instantiate()
					node.position = p
				"G", "o", "H", "L":
					node = PickupScene.instantiate()
					node.kind = "GoHL".find(ch)
					node.position = p
				"I":
					node = CheckpointScene.instantiate()
					node.position = bottom + Vector2(0, -8)
				"E":
					node = ExitScene.instantiate()
					node.position = bottom
			if node:
				entities.add_child(node)
	for i in min(zip_starts.size(), zip_ends.size()):
		var zip := ZiplineScene.instantiate()
		zip.position = zip_starts[i]
		zip.end_offset = zip_ends[i] - zip_starts[i]
		entities.add_child(zip)

	if not GameState.has_checkpoint:
		GameState.set_checkpoint(spawn)
	player = PlayerScene.instantiate()
	player.position = GameState.checkpoint
	player.kill_y = height * TILE + 32
	add_child(player)
	var cam: Camera2D = player.get_node("Camera")
	cam.limit_left = 0
	cam.limit_top = 0
	cam.limit_right = width * TILE
	cam.limit_bottom = height * TILE
	cam.reset_smoothing()
	cam.add_child(_make_ambience())


func _make_ambience() -> Node2D:
	var fx := Node2D.new()
	fx.set_script(AmbienceScript)
	return fx
