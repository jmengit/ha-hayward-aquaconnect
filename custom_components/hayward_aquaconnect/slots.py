from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class EquipmentSlot:
    key_index: int
    slug: str
    name: str
    used_default: bool
    press_key_id: str
    enable_switch: bool = False


EQUIPMENT_SLOTS: tuple[EquipmentSlot, ...] = (
    EquipmentSlot(0, "system_off", "System Off", False, "04"),
    EquipmentSlot(6, "heat_pump", "Heat Pump", True, "13"),
    EquipmentSlot(12, "aux3", "AUX3", False, "0C"),
    EquipmentSlot(1, "pool", "Pool", True, "07"),
    EquipmentSlot(7, "valve3", "Valve3", False, "11"),
    EquipmentSlot(13, "deck_light", "Pool Deck Light", True, "0D", True),
    EquipmentSlot(2, "spa", "Spa", False, "07"),
    EquipmentSlot(8, "valve4", "Valve4", False, "12"),
    EquipmentSlot(14, "cooling", "Cooling", True, "0E"),
    EquipmentSlot(3, "spillover", "Spillover", False, "07"),
    EquipmentSlot(9, "waterfall", "Waterfall Pump", True, "0A", True),
    EquipmentSlot(15, "aux6", "AUX6", False, "0F"),
    EquipmentSlot(4, "filter_pump", "Filter Pump", True, "08", True),
    EquipmentSlot(10, "fount_lt", "Fire Goblets", True, "0B", True),
    EquipmentSlot(5, "pool_light", "Pool Light", True, "09", True),
)

SLOTS_BY_SLUG = {slot.slug: slot for slot in EQUIPMENT_SLOTS}
USED_SLOTS = tuple(slot for slot in EQUIPMENT_SLOTS if slot.used_default)
SWITCH_SLOTS = tuple(slot for slot in EQUIPMENT_SLOTS if slot.enable_switch)
