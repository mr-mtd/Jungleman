class_name Player
extends CharacterBody2D
## The jungle explorer. Runs, jumps, crouches, cracks a whip, slings stones,
## swings on vines, rides ziplines and struggles out of tar pits.

const RUN_SPEED := 115.0
const CROUCH_SPEED := 0.0
const GROUND_ACCEL := 900.0
const GROUND_FRICTION := 1200.0
const AIR_ACCEL := 520.0
const GRAVITY := 900.0
const JUMP_VELOCITY := -310.0
const JUMP_CUT := 0.45
const MAX_FALL := 420.0
const COYOTE_TIME := 0.1
const JUMP_BUFFER := 0.12

const TAR_SINK_SPEED := 12.0
const TAR_MOVE_SPEED := 25.0
const TAR_JUMP := -240.0

const VINE_CLIMB_SPEED := 40.0
const VINE_RELEASE_BOOST := Vector2(0, -150)
const ZIP_ACCEL := 320.0
const ZIP_MAX_SPEED := 240.0

const HAND_OFFSET := 14.0  # distance from body origin to the hands when hanging
const GRAB_POINT := Vector2(0, -16)  # where the hands reach while jumping
const STAND_HEIGHT := 26.0
const CROUCH_HEIGHT := 16.0

const WHIP_TIME := 0.32
const WHIP_ACTIVE_FROM := 0.1
const WHIP_LENGTH := 34.0
const THROW_TIME := 0.25
const INVULN_TIME := 1.4

enum State { NORMAL, SWING, ZIP, DEAD, WIN }

const StoneScene := preload("res://scenes/entities/stone.tscn")

var state := State.NORMAL
var facing := 1
var kill_y := 10000.0
var crouching := false
var coyote := 0.0
var jump_buffer := 0.0
var invuln := 0.0
var hurt_time := 0.0
var attack_time := 0.0
var throw_time := 0.0
var whip_hits: Array = []

var vine: Vine = null
var vine_grab := 0.0
var regrab_block: Node = null
var regrab_timer := 0.0

var zipline: Zipline = null
var zip_t := 0.0
var zip_speed := 0.0

var tar: TarPit = null
var tar_jump_cooldown := 0.0

@onready var sprite: AnimatedSprite2D = $Sprite
@onready var shape: CollisionShape2D = $Shape
@onready var whip_hitbox: Area2D = $WhipHitbox
@onready var whip_line: Line2D = $WhipLine


func _ready() -> void:
	add_to_group("player")
	GameState.set_health(GameState.MAX_HEALTH)
	invuln = 1.0


func _physics_process(delta: float) -> void:
	invuln = max(invuln - delta, 0.0)
	hurt_time = max(hurt_time - delta, 0.0)
	regrab_timer = max(regrab_timer - delta, 0.0)
	tar_jump_cooldown = max(tar_jump_cooldown - delta, 0.0)
	match state:
		State.NORMAL:
			_normal(delta)
		State.SWING:
			_swing(delta)
		State.ZIP:
			_zip(delta)
		State.DEAD:
			velocity.y = min(velocity.y + GRAVITY * delta, MAX_FALL)
			position += velocity * delta
		State.WIN:
			velocity.x = 0
			velocity.y = min(velocity.y + GRAVITY * delta, MAX_FALL)
			move_and_slide()
	_update_attacks(delta)
	_update_animation()
	sprite.visible = invuln <= 0.0 or state == State.DEAD or int(invuln * 20) % 2 == 0
	queue_redraw()
	if state != State.DEAD and global_position.y > kill_y:
		die()


# --- Running, jumping, tar -------------------------------------------------

func _normal(delta: float) -> void:
	var dir := Input.get_axis("move_left", "move_right")
	var on_floor := is_on_floor()
	var sinking := _in_tar()

	coyote = COYOTE_TIME if on_floor else max(coyote - delta, 0.0)
	jump_buffer = JUMP_BUFFER if Input.is_action_just_pressed("jump") else max(jump_buffer - delta, 0.0)

	_set_crouch(on_floor and not sinking and Input.is_action_pressed("move_down") and hurt_time <= 0.0)

	# horizontal movement
	var target := dir * RUN_SPEED
	if crouching or (attack_time > 0.0 and on_floor):
		target = 0.0
	if sinking:
		target = dir * TAR_MOVE_SPEED
	if hurt_time > 0.0:
		target = velocity.x
	var accel := GROUND_ACCEL if on_floor else AIR_ACCEL
	if on_floor and is_zero_approx(target):
		accel = GROUND_FRICTION
	velocity.x = move_toward(velocity.x, target, accel * delta)
	if dir != 0 and attack_time <= 0.0 and hurt_time <= 0.0:
		facing = 1 if dir > 0 else -1

	# vertical movement
	if sinking:
		velocity.y = min(velocity.y + GRAVITY * delta, TAR_SINK_SPEED)
		if jump_buffer > 0.0 and tar_jump_cooldown <= 0.0:
			velocity.y = TAR_JUMP
			jump_buffer = 0.0
			tar_jump_cooldown = 0.3
		if global_position.y - STAND_HEIGHT / 2.0 > tar.surface_y() - 4.0:
			die(false)
			return
	else:
		velocity.y = min(velocity.y + GRAVITY * delta, MAX_FALL)
		if jump_buffer > 0.0 and coyote > 0.0 and not crouching:
			velocity.y = JUMP_VELOCITY
			jump_buffer = 0.0
			coyote = 0.0
		if Input.is_action_just_released("jump") and velocity.y < 0.0:
			velocity.y *= JUMP_CUT

	move_and_slide()

	if not is_on_floor() and hurt_time <= 0.0:
		_try_grab()


func _in_tar() -> bool:
	return tar != null and global_position.y + STAND_HEIGHT / 2.0 > tar.surface_y() + 2.0


func _set_crouch(value: bool) -> void:
	if value == crouching:
		return
	crouching = value
	var rect := shape.shape as RectangleShape2D
	var h := CROUCH_HEIGHT if crouching else STAND_HEIGHT
	rect.size.y = h
	shape.position.y = (STAND_HEIGHT - h) / 2.0


func enter_tar(pit: TarPit) -> void:
	tar = pit


func exit_tar(pit: TarPit) -> void:
	if tar == pit:
		tar = null


# --- Vines and ziplines ----------------------------------------------------

func _try_grab() -> void:
	var hand := global_position + GRAB_POINT
	if regrab_timer <= 0.0:
		regrab_block = null
	for v in get_tree().get_nodes_in_group("vines"):
		if v == regrab_block:
			continue
		var d: float = v.grab_distance(hand)
		if d >= 0.0:
			_attach_vine(v, d)
			return
	if regrab_timer > 0.0:
		return
	for z in get_tree().get_nodes_in_group("ziplines"):
		var t: float = z.grab_t(hand)
		if t >= 0.0:
			state = State.ZIP
			zipline = z
			zip_t = t
			zip_speed = max(velocity.dot(z.direction()), 40.0)
			_set_crouch(false)
			return


func _attach_vine(v: Vine, dist: float) -> void:
	state = State.SWING
	vine = v
	vine_grab = clamp(dist, 12.0, v.length)
	v.attach(vine_grab, velocity)
	velocity = Vector2.ZERO
	_set_crouch(false)
	attack_time = 0.0


func _swing(delta: float) -> void:
	var dir := Input.get_axis("move_left", "move_right")
	vine.pump(dir, delta)
	if dir != 0:
		facing = 1 if dir > 0 else -1
	var climb := Input.get_axis("move_up", "move_down")
	vine_grab = clamp(vine_grab + climb * VINE_CLIMB_SPEED * delta, 12.0, vine.length)
	vine.set_grab(vine_grab)
	var axis := vine.down_vector()
	global_position = vine.point_at(vine_grab) + axis * HAND_OFFSET
	sprite.rotation = vine.angle
	if Input.is_action_just_pressed("jump"):
		_release_vine(vine.velocity_at(vine_grab) * 1.1 + VINE_RELEASE_BOOST)


func _release_vine(vel: Vector2) -> void:
	vine.detach()
	regrab_block = vine
	regrab_timer = 0.45
	vine = null
	sprite.rotation = 0.0
	velocity = vel
	state = State.NORMAL
	if absf(vel.x) > 1.0:
		facing = 1 if vel.x > 0 else -1


func _zip(delta: float) -> void:
	zip_speed = min(zip_speed + ZIP_ACCEL * delta, ZIP_MAX_SPEED)
	zip_t += zip_speed * delta / zipline.length()
	facing = 1 if zipline.direction().x >= 0 else -1
	if zip_t >= 1.0 or Input.is_action_just_pressed("jump"):
		var vel := zipline.direction() * zip_speed
		if zip_t < 1.0:
			vel += Vector2(0, -120)
		zip_t = min(zip_t, 1.0)
		global_position = zipline.point_at(zip_t) + Vector2(0, HAND_OFFSET)
		velocity = vel
		regrab_timer = 0.3
		state = State.NORMAL
		zipline = null
		return
	global_position = zipline.point_at(zip_t) + Vector2(0, HAND_OFFSET)


# --- Whip and sling --------------------------------------------------------

func _update_attacks(delta: float) -> void:
	var can_act := state == State.NORMAL and not _in_tar() and hurt_time <= 0.0
	if can_act and attack_time <= 0.0 and throw_time <= 0.0:
		if Input.is_action_just_pressed("attack"):
			attack_time = WHIP_TIME
			whip_hits.clear()
		elif Input.is_action_just_pressed("throw") and GameState.use_stone():
			throw_time = THROW_TIME
			var stone := StoneScene.instantiate()
			stone.global_position = global_position + Vector2(10 * facing, -8 + (6 if crouching else 0))
			stone.velocity = Vector2(260 * facing, -70)
			get_parent().add_child(stone)

	throw_time = max(throw_time - delta, 0.0)
	if attack_time > 0.0:
		attack_time -= delta
		var elapsed := WHIP_TIME - attack_time
		var active := elapsed >= WHIP_ACTIVE_FROM and attack_time > 0.0
		var reach := 0.0
		if active:
			reach = clamp((elapsed - WHIP_ACTIVE_FROM) / 0.08, 0.0, 1.0)
		var hand := Vector2(8 * facing, -5 + (6 if crouching else 0))
		whip_hitbox.position = Vector2(facing * (8 + WHIP_LENGTH / 2.0), hand.y)
		whip_line.visible = active
		if active:
			var pts := PackedVector2Array()
			for i in 6:
				var t := i / 5.0 * reach
				pts.append(hand + Vector2(facing * WHIP_LENGTH * t, sin(t * PI) * -3.0 + t * 2.0))
			whip_line.points = pts
			for area in whip_hitbox.get_overlapping_areas():
				if area.has_method("hit") and not whip_hits.has(area):
					whip_hits.append(area)
					area.hit(1)
	else:
		whip_line.visible = false


# --- Damage, death, victory ------------------------------------------------

func hurt(amount: int, from: Vector2) -> void:
	if invuln > 0.0 or state == State.DEAD or state == State.WIN:
		return
	if state == State.SWING:
		_release_vine(Vector2.ZERO)
	elif state == State.ZIP:
		state = State.NORMAL
		zipline = null
	GameState.set_health(GameState.health - amount)
	if GameState.health <= 0:
		die()
		return
	invuln = INVULN_TIME
	hurt_time = 0.35
	attack_time = 0.0
	_set_crouch(false)
	var away := 1.0 if global_position.x >= from.x else -1.0
	velocity = Vector2(away * 130.0, -180.0)


func heal(amount: int) -> void:
	GameState.set_health(GameState.health + amount)


func die(hop := true) -> void:
	if state == State.DEAD or state == State.WIN:
		return
	if vine:
		vine.detach()
		vine = null
	sprite.rotation = 0.0
	state = State.DEAD
	GameState.set_health(0)
	velocity = Vector2(0, -160) if hop and global_position.y < kill_y else Vector2.ZERO
	collision_layer = 0
	collision_mask = 0
	await get_tree().create_timer(1.6).timeout
	GameState.lose_life()
	if GameState.lives <= 0:
		GameState.show_message("GAME OVER\nPress Jump to try again", 999.0)
		get_tree().call_group("hud", "show_game_over")
	else:
		respawn()


func respawn() -> void:
	global_position = GameState.checkpoint
	velocity = Vector2.ZERO
	collision_layer = 2
	collision_mask = 1
	tar = null
	state = State.NORMAL
	facing = 1
	GameState.set_health(GameState.MAX_HEALTH)
	invuln = INVULN_TIME
	get_node("Camera").reset_smoothing()


func win() -> void:
	if state == State.DEAD or state == State.WIN:
		return
	state = State.WIN
	GameState.add_score(1000)
	get_tree().call_group("hud", "show_level_complete")


# --- Animation ---------------------------------------------------------------

func _draw() -> void:
	# soft contact shadow under the feet
	if state == State.NORMAL and is_on_floor() and not _in_tar():
		for i in 3:
			var r := 7.0 - i * 1.8
			draw_set_transform(Vector2(0, STAND_HEIGHT / 2.0), 0.0, Vector2(1.0, 0.3))
			draw_circle(Vector2.ZERO, r, Color(0, 0, 0, 0.12))
		draw_set_transform(Vector2.ZERO)


func _update_animation() -> void:
	sprite.flip_h = facing < 0
	var anim := "idle"
	match state:
		State.DEAD:
			anim = "die"
		State.WIN:
			anim = "idle"
		State.ZIP:
			anim = "zip"
		State.SWING:
			anim = "climb" if Input.get_axis("move_up", "move_down") != 0 and vine_grab > 12.0 and vine_grab < vine.length else "swing"
		State.NORMAL:
			if hurt_time > 0.0:
				anim = "hurt"
			elif attack_time > 0.0:
				anim = "whip"
			elif throw_time > 0.0:
				anim = "throw"
			elif _in_tar():
				anim = "struggle"
			elif not is_on_floor():
				anim = "jump" if velocity.y < 0.0 else "fall"
			elif crouching:
				anim = "crouch"
			elif absf(velocity.x) > 10.0:
				anim = "run"
	if sprite.animation != anim:
		sprite.play(anim)
	if anim == "whip":
		# keep the whip pose in sync with the hitbox timing
		var frame := clampi(int((WHIP_TIME - attack_time) / WHIP_TIME * 3.0 * 1.6), 0, 2)
		sprite.frame = frame
		sprite.pause()
