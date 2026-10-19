import json
from typing import Optional, Dict, Any

class Protocol:
    """Handles serialization and validation of Remote Desktop network packets."""

    @staticmethod
    def create_host_init(room_id: str, pin: str, width: int, height: int, device_name: str = "Host-PC") -> str:
        return json.dumps({
            "type": "init_host",
            "room_id": str(room_id).strip(),
            "pin": str(pin).strip(),
            "device_name": device_name,
            "width": int(width),
            "height": int(height)
        })

    @staticmethod
    def parse_input_event(raw_data: str) -> Optional[Dict[str, Any]]:
        try:
            data = json.loads(raw_data)
        except Exception:
            return None

        if not isinstance(data, dict) or "type" not in data:
            return None

        event_type = data["type"]

        if event_type == "mouse_move":
            try:
                x = float(data.get("x", 0.0))
                y = float(data.get("y", 0.0))
                # Clamp coordinates to [0.0, 1.0]
                x_clamped = max(0.0, min(1.0, x))
                y_clamped = max(0.0, min(1.0, y))
                return {
                    "type": "mouse_move",
                    "x": x_clamped,
                    "y": y_clamped
                }
            except (ValueError, TypeError):
                return None

        elif event_type in ("mouse_down", "mouse_up"):
            button = int(data.get("button", 0))
            return {
                "type": event_type,
                "button": button
            }

        elif event_type == "mouse_wheel":
            delta_y = int(data.get("delta_y", 0))
            return {
                "type": "mouse_wheel",
                "delta_y": delta_y
            }

        elif event_type in ("key_down", "key_up"):
            vk = int(data.get("vk", 0))
            code = str(data.get("code", ""))
            return {
                "type": event_type,
                "vk": vk,
                "code": code
            }

        elif event_type == "text_input":
            text = str(data.get("text", ""))
            return {
                "type": "text_input",
                "text": text
            }

        elif event_type == "ping":
            return {"type": "ping", "timestamp": data.get("timestamp", 0)}

        return None
