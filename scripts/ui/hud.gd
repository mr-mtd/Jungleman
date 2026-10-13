extends CanvasLayer
## Health meter, lives, sling stones, treasure, score and on-screen messages.

@onready var health_bar: ProgressBar = %Health
@onready var lives_label: Label = %Lives
@onready var stones_label: Label = %Stones
@onready var gold_label: Label = %Gold
@onready var score_label: Label = %Score
@onready var message_label: Label = %Message
@onready var pause_label: Label = %Paused

var _message_time := 0.0
var _waiting_restart := false
var _shown_health := 100.0
var _fill: StyleBoxFlat


func _ready() -> void:
	add_to_group("hud")
	process_mode = Node.PROCESS_MODE_ALWAYS
	_fill = health_bar.get_theme_stylebox("fill") as StyleBoxFlat
	GameState.changed.connect(_refresh)
	GameState.message.connect(_on_message)
	_shown_health = GameState.health
	_refresh()


func _refresh() -> void:
	health_bar.max_value = GameState.MAX_HEALTH
	lives_label.text = str(GameState.lives)
	stones_label.text = str(GameState.stones)
	gold_label.text = str(GameState.treasure)
	score_label.text = "%06d" % GameState.score


func _on_message(text: String, seconds: float) -> void:
	message_label.text = text
	message_label.modulate.a = 0.0
	message_label.scale = Vector2.ONE
	var tw := create_tween()
	tw.tween_property(message_label, "modulate:a", 1.0, 0.25)
	_message_time = seconds


func _process(delta: float) -> void:
	# health glides toward its new value and shifts from green to red
	_shown_health = move_toward(_shown_health, GameState.health, 120.0 * delta)
	health_bar.value = _shown_health
	var t := _shown_health / float(GameState.MAX_HEALTH)
	_fill.bg_color = Color("e2483c").lerp(Color("f2c23a"), clampf(t * 2.0, 0.0, 1.0)).lerp(Color("5cdc6a"), clampf(t * 2.0 - 1.0, 0.0, 1.0))
	if _message_time > 0.0:
		_message_time -= delta
		if _message_time < 0.4:
			message_label.modulate.a = max(_message_time / 0.4, 0.0)
	if _waiting_restart and Input.is_action_just_pressed("jump"):
		_waiting_restart = false
		get_tree().paused = false
		GameState.reset()
		get_tree().reload_current_scene()
	elif not _waiting_restart and Input.is_action_just_pressed("pause"):
		get_tree().paused = not get_tree().paused
		pause_label.visible = get_tree().paused


func show_game_over() -> void:
	_waiting_restart = true


func show_level_complete() -> void:
	GameState.show_message("LEVEL COMPLETE!\nTreasure %d   Score %d\nPress Jump to play again" % [GameState.treasure, GameState.score], 999.0)
	_waiting_restart = true
