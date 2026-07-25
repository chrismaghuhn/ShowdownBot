class_name SpectatorRoomGatewayPort
extends RefCounted

## Seam between RoomEntryPanel and the real SpectatorRoomGateway, mirroring net/SocketPeerPort's
## pattern: a plain, script-defined RefCounted base class that both the production gateway
## (Task 28) and a gdUnit test fake can extend, so RoomEntryPanel.configure() never has to name
## the concrete gateway type (which a fake cannot satisfy without dragging in its
## WebSocketTransport/RoomStateMachine dependencies).

func join(_intent: RoomJoinIntent) -> void:
	push_error("SpectatorRoomGatewayPort.join is abstract")


func leave() -> void:
	push_error("SpectatorRoomGatewayPort.leave is abstract")
