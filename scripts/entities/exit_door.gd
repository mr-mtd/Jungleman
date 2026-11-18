extends Node2D
## The temple at the end of the level. Walk into the doorway to finish.

@onready var door: Area2D = $Door


func _ready() -> void:
	door.body_entered.connect(func(body):
		if body.has_method("win"):
			body.win())
