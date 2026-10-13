extends Enemy
## Coiled snake that lunges when you get close.

@export var strike_range := Vector2(52, 28)

var _strike := 0.0
var _cooldown := 0.0

@onready var strike_shape: CollisionShape2D = $StrikeShape


func _physics_process(delta: float) -> void:
	super(delta)
	if dying:
		return
	_cooldown = max(_cooldown - delta, 0.0)
	var p := player()
	if p:
		var d := p.global_position - global_position
		if _strike <= 0.0:
			sprite.flip_h = d.x < 0
			strike_shape.position.x = absf(strike_shape.position.x) * (-1.0 if sprite.flip_h else 1.0)
		if _strike <= 0.0 and _cooldown <= 0.0 and absf(d.x) < strike_range.x and absf(d.y) < strike_range.y:
			_strike = 0.6
			_cooldown = 1.4
			sprite.play("strike")
			strike_shape.set_deferred("disabled", false)
	if _strike > 0.0:
		_strike -= delta
		if _strike <= 0.0:
			sprite.play("idle")
			strike_shape.set_deferred("disabled", true)
