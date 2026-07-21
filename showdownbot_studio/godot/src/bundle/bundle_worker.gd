class_name BundleWorker
extends RefCounted

class WorkerHooks:
	extends RefCounted

	var on_before_validate: Callable = Callable()
	var on_before_terminal_enqueue: Callable = Callable()
	var on_after_validate: Callable = Callable()
	var omit_terminal_envelope: bool = false


const ENVELOPE_PROGRESS := "progress"
const ENVELOPE_OK := "ok"
const ENVELOPE_REFUSE := "refuse"
const ENVELOPE_CANCELLED := "cancelled"


func run(
	request_id: int,
	path: String,
	hooks: WorkerHooks,
	is_cancelled: Callable,
	enqueue: Callable
) -> void:
	if hooks != null and hooks.on_before_validate.is_valid():
		hooks.on_before_validate.call()

	if is_cancelled.call():
		_enqueue_terminal(enqueue, request_id, ENVELOPE_CANCELLED, null)
		return

	enqueue.call({"request_id": request_id, "kind": ENVELOPE_PROGRESS, "payload": "validating"})

	if is_cancelled.call():
		_enqueue_terminal(enqueue, request_id, ENVELOPE_CANCELLED, null)
		return

	var result: ValidationResult = BundleValidator.validate_dir(path)

	if hooks != null and hooks.on_after_validate.is_valid():
		hooks.on_after_validate.call(result)

	if is_cancelled.call():
		_enqueue_terminal(enqueue, request_id, ENVELOPE_CANCELLED, null)
		return

	if hooks != null and hooks.on_before_terminal_enqueue.is_valid():
		hooks.on_before_terminal_enqueue.call()

	if hooks != null and hooks.omit_terminal_envelope:
		return

	if is_cancelled.call():
		_enqueue_terminal(enqueue, request_id, ENVELOPE_CANCELLED, null)
		return

	if result.ok:
		_enqueue_terminal(enqueue, request_id, ENVELOPE_OK, result)
	else:
		_enqueue_terminal(enqueue, request_id, ENVELOPE_REFUSE, result)


static func _enqueue_terminal(enqueue: Callable, request_id: int, kind: String, payload: Variant) -> void:
	enqueue.call({"request_id": request_id, "kind": kind, "payload": payload})
