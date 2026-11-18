extends Enemy
## Bat fluttering in a figure-eight; it dips toward you when you pass under.

@export var range_x := 48.0
@export var range_y := 14.0

var _home := Vector2.ZERO
var _t := 0.0
var _dip := 0.0


func _ready() -> void:
	super()
	_home = position
	_t = position.x
	sprite.play("fly")


func _physics_process(delta: float) -> void:
	super(delta)
	if dying:
		return
	_t += delta
	var p := player()
	var target_dip := 0.0
	if p and absf(p.global_position.x - global_position.x) < 70.0:
		target_dip = clampf(p.global_position.y - _home.y - 10.0, 0.0, 34.0)
	_dip = move_toward(_dip, target_dip, 30.0 * delta)
	var x := sin(_t * 1.2) * range_x
	position = _home + Vector2(x, sin(_t * 2.4) * range_y + _dip)
	sprite.flip_h = cos(_t * 1.2) < 0
