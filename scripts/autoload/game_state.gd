extends Node
## Global run state: score, lives, ammo and the active checkpoint.

signal changed
signal message(text: String, seconds: float)

const START_LIVES := 3
const START_STONES := 10
const MAX_HEALTH := 100

var lives := START_LIVES
var score := 0
var treasure := 0
var stones := START_STONES
var health := MAX_HEALTH
var checkpoint := Vector2.ZERO
var has_checkpoint := false


func reset() -> void:
	lives = START_LIVES
	score = 0
	treasure = 0
	stones = START_STONES
	health = MAX_HEALTH
	has_checkpoint = false
	changed.emit()


func add_score(points: int) -> void:
	score += points
	changed.emit()


func add_treasure() -> void:
	treasure += 1
	add_score(100)


func add_stones(amount: int) -> void:
	stones = min(stones + amount, 99)
	changed.emit()


func use_stone() -> bool:
	if stones <= 0:
		return false
	stones -= 1
	changed.emit()
	return true


func set_health(value: int) -> void:
	health = clampi(value, 0, MAX_HEALTH)
	changed.emit()


func add_life() -> void:
	lives += 1
	changed.emit()
	show_message("1UP!", 1.5)


func lose_life() -> void:
	lives -= 1
	changed.emit()


func set_checkpoint(pos: Vector2) -> void:
	checkpoint = pos
	has_checkpoint = true


func show_message(text: String, seconds := 2.0) -> void:
	message.emit(text, seconds)
