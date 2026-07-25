class_name UntrustedTextSanitizer
extends RefCounted

## docs/security/UNTRUSTED_SERVER_CONTENT.md: "control characters are escaped before display...
## message length is capped." Applied here, at render time, to every server-delivered string
## (room titles, player names, log lines) before it reaches a Label/RichTextLabel.

const MAX_LENGTH := 300


static func sanitize(raw: String) -> String:
	var stripped := ""
	for i in range(raw.length()):
		var code := raw.unicode_at(i)
		if code >= 0x20 and code != 0x7F:
			stripped += raw[i]
	if stripped.length() > MAX_LENGTH:
		stripped = stripped.substr(0, MAX_LENGTH)
	return stripped
