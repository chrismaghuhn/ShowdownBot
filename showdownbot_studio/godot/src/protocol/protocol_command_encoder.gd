class_name ProtocolCommandEncoder
extends RefCounted

## The only place an outbound Showdown command string is assembled (spec section 4.1, 4.1.1).


static func encode_join_room(room_id: String) -> String:
	return "|/join %s" % room_id


static func encode_leave_room(room_id: String) -> String:
	return "|/leave %s" % room_id
