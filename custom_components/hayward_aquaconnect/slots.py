from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping


@dataclass(frozen=True)
class EquipmentSlot:
    key_index: int
    slug: str
    name: str
    used_default: bool
    press_key_id: str
    enable_switch: bool = False


DEFAULT_EQUIPMENT_SLOTS: tuple[EquipmentSlot, ...] = (
    EquipmentSlot(0, "system_off", "System Off", False, "04"),
    EquipmentSlot(6, "heat_pump", "Heater Manual", True, "13", True),
    EquipmentSlot(12, "aux3", "AUX3", False, "0C"),
    EquipmentSlot(1, "pool", "Pool", True, "07"),
    EquipmentSlot(7, "valve3", "Valve3", False, "11"),
    EquipmentSlot(13, "deck_light", "Pool Deck Light", True, "0D", True),
    EquipmentSlot(2, "spa", "Spa", False, "07"),
    EquipmentSlot(8, "valve4", "Valve4", False, "12"),
    EquipmentSlot(14, "cooling", "Pool Chiller", True, "0E", True),
    EquipmentSlot(3, "spillover", "Spillover", False, "07"),
    EquipmentSlot(9, "waterfall", "Waterfall Pump", True, "0A", True),
    EquipmentSlot(15, "aux6", "AUX6", False, "0F"),
    EquipmentSlot(4, "filter_pump", "Filter Pump", True, "08", True),
    EquipmentSlot(10, "fount_lt", "Fire Goblets", True, "0B", True),
    EquipmentSlot(5, "pool_light", "Pool Light", True, "09", True),
)

# Backwards-compatible alias for callers that still import the defaults directly.
EQUIPMENT_SLOTS = DEFAULT_EQUIPMENT_SLOTS


def _resolve_slot(default: EquipmentSlot, override: Mapping[str, Any] | None) -> EquipmentSlot:
    if not override:
        return default
    return EquipmentSlot(
        default.key_index,
        default.slug,
        str(override.get("name", default.name)),
        bool(override.get("used_default", default.used_default)),
        str(override.get("press_key_id", default.press_key_id)).upper(),
        bool(override.get("enable_switch", default.enable_switch)),
    )


def resolve_equipment_slots(overrides: Mapping[str, Mapping[str, Any]] | None = None) -> tuple[EquipmentSlot, ...]:
    overrides = overrides or {}
    return tuple(_resolve_slot(slot, overrides.get(slot.slug)) for slot in DEFAULT_EQUIPMENT_SLOTS)


SLOTS_BY_SLUG = {slot.slug: slot for slot in EQUIPMENT_SLOTS}
USED_SLOTS = tuple(slot for slot in EQUIPMENT_SLOTS if slot.used_default)
SWITCH_SLOTS = tuple(slot for slot in EQUIPMENT_SLOTS if slot.enable_switch)
