from custom_components.hayward_aquaconnect.parser import decode_equipment, parse_payload
from custom_components.hayward_aquaconnect.slots import resolve_equipment_slots


def test_parse_live_style_status():
    payload = """<html><body>
  Pool Chlorinator  xxx
        75%         xxx
EDTDDCDD3333xxx

</body></html>"""
    status = parse_payload(payload)
    assert status.chlorinator_percent == 75
    assert status.raw_leds == "EDTDDCDD3333"
    assert status.equipment["pool"]["state"] == "on"
    assert status.equipment["filter_pump"]["state"] == "on"
    assert status.equipment["pool_light"]["state"] == "off"
    assert status.equipment["deck_light"]["name"] == "Pool Deck Light"
    assert status.equipment["fount_lt"]["name"] == "Fire Goblets"


def test_parse_temperatures_and_salt():
    assert parse_payload("<body>Pool Temp  85&#176F   xxx&nbspxxxEDTDDCDD3333xxx</body>").pool_temperature == 85
    assert parse_payload("<body>Air Temp   76&#176F   xxx&nbspxxxEDTDDCDD3333xxx</body>").air_temperature == 76
    assert parse_payload("<body>Salt Level     xxx      2700 PPM      xxxEDTDDCDD3333xxx</body>").salt_level == 2700


def test_classifies_routine_clock_and_alert_display_pages():
    clock = parse_payload("<body>Friday xxx10:57AxxxEDTDDCDD3333xxx</body>")
    assert clock.display_page_kind == "clock"
    assert clock.display_alert is None

    routine = parse_payload("<body>Heat Pump xxxManual OffxxxEDTDDCDD3333xxx</body>")
    assert routine.display_page_kind == "routine"
    assert routine.display_alert is None

    air_temp = parse_payload("<body>Air Temp 79&#176F xxx&nbspxxxEDTDDCDD3333xxx</body>")
    assert air_temp.display_page_kind == "routine"
    assert air_temp.display_alert is None

    alert = parse_payload("<body>No Flow xxxCheck SystemxxxEDTDDCDD3333xxx</body>")
    assert alert.display_page_kind == "alert"
    assert alert.display_alert == "No Flow / Check System"


def test_merge_clears_display_alert_after_routine_page():
    from custom_components.hayward_aquaconnect.parser import merge_status

    previous = parse_payload("<body>No Flow xxxCheck SystemxxxEDTDDCDD3333xxx</body>").as_dict()
    routine = parse_payload("<body>Salt Level xxx2700 PPMxxxEDTDDCDD3333xxx</body>")
    merged = merge_status(previous, routine)
    assert merged["display_page_kind"] == "routine"
    assert merged["display_alert"] is None


def test_decode_all_configured_slots():
    equipment = decode_equipment("EDTDDCDD3333")
    assert set(equipment) >= {"heat_pump", "pool", "deck_light", "waterfall", "filter_pump", "fount_lt", "pool_light"}
    assert equipment["heat_pump"]["press_key_id"] == "13"
    assert equipment["waterfall"]["press_key_id"] == "0A"


def test_slot_overrides_change_metadata_and_preserve_defaults():
    slots = resolve_equipment_slots(
        {
            "pool_light": {"name": "Spa Light", "press_key_id": "0E", "enable_switch": False},
            "filter_pump": {"press_key_id": "99"},
        }
    )
    equipment = decode_equipment("EDTDDCDD3333", slots=slots)
    assert equipment["pool_light"]["name"] == "Spa Light"
    assert equipment["pool_light"]["press_key_id"] == "0E"
    assert equipment["filter_pump"]["press_key_id"] == "99"
    assert equipment["pool_light"]["state"] == "off"
