extends Enemy
## Scorpion patrolling back and forth along the ground.

@export var speed := 28.0
@export var patrol_range := 40.0

var _home := 0.0
var _dir := -1.0


func _ready() -> void:
	super()
	_home = position.x
	sprite.play("walk")


func _physics_process(delta: float) -> void:
	super(delta)
	if dying:
		return
	position.x += _dir * speed * delta
	if absf(position.x - _home) > patrol_range:
		position.x = _home + sign(position.x - _home) * patrol_range
		_dir = -_dir
	sprite.flip_h = _dir < 0
