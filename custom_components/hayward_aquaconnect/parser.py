from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from .slots import EQUIPMENT_SLOTS, EquipmentSlot

_STATUS_BY_NIBBLE = {
    "3": "nokey",
    "4": "off",
    "5": "on",
    "6": "blink",
}

_WEEKDAYS = {"monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"}
_ROUTINE_DISPLAY_TITLES = {
    "air temp",
    "pool temp",
    "salt level",
    "pool chlorinator",
    "heat pump",
    "heater set point",
    "pool heat",
    "spa heat",
    "super chlorinate",
}


@dataclass
class AquaConnectStatus:
    display_line_1: str | None = None
    display_line_2: str | None = None
    display_message: str | None = None
    display_page_kind: str | None = None
    display_alert: str | None = None
    raw_leds: str | None = None
    pool_temperature: int | None = None
    air_temperature: int | None = None
    salt_level: int | None = None
    chlorinator_percent: int | None = None
    super_chlorinate_running: bool | None = None
    super_chlorinate_time_remaining: int | None = None
    heater_setpoint: int | None = None
    equipment: dict[str, dict[str, Any]] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return {
            "display_line_1": self.display_line_1,
            "display_line_2": self.display_line_2,
            "display_message": self.display_message,
            "display_page_kind": self.display_page_kind,
            "display_alert": self.display_alert,
            "raw_leds": self.raw_leds,
            "pool_temperature": self.pool_temperature,
            "air_temperature": self.air_temperature,
            "salt_level": self.salt_level,
            "chlorinator_percent": self.chlorinator_percent,
            "super_chlorinate_running": self.super_chlorinate_running,
            "super_chlorinate_time_remaining": self.super_chlorinate_time_remaining,
            "heater_setpoint": self.heater_setpoint,
            "equipment": self.equipment,
        }


def _clean_line(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = re.sub(r"\s+", " ", value.replace("&nbsp", " ")).strip()
    return cleaned or None


def _body_text(html: str) -> str:
    match = re.search(r"<body>(.*?)</body", html, re.I | re.S)
    if not match:
        return html.strip()
    return match.group(1).replace("\r", "").replace("\n", "").strip()


def _is_time_line(value: str | None) -> bool:
    if not value:
        return False
    return bool(re.fullmatch(r"\d{1,2}:\d{2}\s*[AP]", value.strip(), re.I))


def _display_page_kind(line_1: str | None, line_2: str | None) -> str:
    if line_1 and line_1.lower() in _WEEKDAYS and _is_time_line(line_2):
        return "clock"
    if line_1 and any(line_1.lower().startswith(title) for title in _ROUTINE_DISPLAY_TITLES):
        return "routine"
    if not line_1 and not line_2:
        return "unknown"
    return "alert"


def _status_from_nibble(raw_leds: str, char_offset: int, hex_offset: int) -> str:
    if len(raw_leds) <= char_offset:
        return "unknown"
    nibble = f"{ord(raw_leds[char_offset]):02X}"[hex_offset]
    return _STATUS_BY_NIBBLE.get(nibble, "unknown")


def decode_equipment(raw_leds: str | None, slots: tuple[EquipmentSlot, ...] = EQUIPMENT_SLOTS) -> dict[str, dict[str, Any]]:
    if not raw_leds:
        return {}

    decoded_slots: list[str] = []
    for index, _char in enumerate(raw_leds):
        decoded_slots.append(_status_from_nibble(raw_leds, index, 0))
        # Per WebsFuncs.js, final low nibble is a control nibble, not an LED slot.
        if index != len(raw_leds) - 1:
            decoded_slots.append(_status_from_nibble(raw_leds, index, 1))

    equipment: dict[str, dict[str, Any]] = {}
    for slot in slots:
        state = decoded_slots[slot.key_index] if slot.key_index < len(decoded_slots) else "unknown"
        equipment[slot.slug] = {
            "name": slot.name,
            "state": state,
            "used": slot.used_default,
            "key_index": slot.key_index,
            "press_key_id": slot.press_key_id,
        }
    return equipment


def parse_payload(payload: str, slots: tuple[EquipmentSlot, ...] = EQUIPMENT_SLOTS) -> AquaConnectStatus:
    body = _body_text(payload)
    parts = [_clean_line(part) for part in body.split("xxx")]
    status = AquaConnectStatus()

    if parts:
        status.display_line_1 = parts[0]
    if len(parts) > 1:
        status.display_line_2 = parts[1]
    if len(parts) > 2:
        status.raw_leds = parts[2]

    status.display_message = " / ".join(part for part in (status.display_line_1, status.display_line_2) if part) or None
    status.display_page_kind = _display_page_kind(status.display_line_1, status.display_line_2)
    if status.display_page_kind == "alert":
        status.display_alert = status.display_message

    text = " ".join(part for part in parts[:2] if part)
    if match := re.search(r"Air Temp\s+(\d+)", text, re.I):
        status.air_temperature = int(match.group(1))
    if match := re.search(r"Pool Temp\s+(\d+)", text, re.I):
        status.pool_temperature = int(match.group(1))

    if match := re.search(r"Salt Level\s+\w+\s+(\d+)\s*PPM", text, re.I):
        status.salt_level = int(match.group(1))
    elif status.display_line_1 == "Salt Level" and status.display_line_2:
        if match := re.search(r"(\d+)\s*PPM", status.display_line_2, re.I):
            status.salt_level = int(match.group(1))

    if match := re.search(r"Pool Chlorinator\s+\w+\s+(\d+)%", text, re.I):
        status.chlorinator_percent = int(match.group(1))
    elif status.display_line_1 == "Pool Chlorinator" and status.display_line_2:
        if match := re.search(r"(\d+)%", status.display_line_2):
            status.chlorinator_percent = int(match.group(1))

    if status.display_line_1 and status.display_line_1.lower().startswith("super chlorinate"):
        status.super_chlorinate_running = True
        if match := re.search(r"(\d{1,2}):(\d{2})\s*remaining", status.display_line_2 or "", re.I):
            status.super_chlorinate_time_remaining = int(match.group(1)) * 60 + int(match.group(2))

    if match := re.search(r"(\d+)\s*(?:°|&#176;?|&deg;?)?\s*F\s+Set\s+Point", text, re.I):
        status.heater_setpoint = int(match.group(1))

    status.equipment = decode_equipment(status.raw_leds, slots)
    return status


def merge_status(previous: dict[str, Any], current: AquaConnectStatus) -> dict[str, Any]:
    """Merge current rotating LCD page into retained coordinator state."""
    merged = dict(previous or {})
    data = current.as_dict()
    for key, value in data.items():
        if key == "equipment":
            if value:
                merged[key] = value
        elif key == "display_alert":
            merged[key] = value
        elif value is not None:
            merged[key] = value
    return merged
