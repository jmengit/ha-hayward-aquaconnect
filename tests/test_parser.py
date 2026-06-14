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


def test_parse_super_chlorinate_as_routine_with_remaining_time():
    status = parse_payload("<body>Super Chlorinate xxx18:21 remainingxxxEDTDDCDD3333xxx</body>")

    assert status.display_page_kind == "routine"
    assert status.display_alert is None
    assert status.super_chlorinate_running is True
    assert status.super_chlorinate_time_remaining == 1101


def test_parse_heater_setpoint():
    status = parse_payload("<body>Heat Pump xxx84&#176F Set PointxxxEDTDDCDD3333xxx</body>")

    assert status.display_page_kind == "routine"
    assert status.display_alert is None
    assert status.heater_setpoint == 84


def test_parse_pool_heat_menu_setpoint():
    status = parse_payload("<body>Pool Heat xxx86&#176F Set PointxxxEDTDDCDD3333xxx</body>")

    assert status.display_page_kind == "routine"
    assert status.display_alert is None
    assert status.heater_setpoint == 86


def test_parse_pool_heat_pump_menu_temperature_as_setpoint():
    status = parse_payload("<body>Pool Heat Pump xxx87&#176FxxxEDTDDCDD3333xxx</body>")

    assert status.display_page_kind == "routine"
    assert status.display_alert is None
    assert status.heater_setpoint == 87


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
    assert equipment["heat_pump"]["name"] == "Heater Manual"
    assert equipment["heat_pump"]["used"] is True
    assert equipment["waterfall"]["press_key_id"] == "0A"
    assert equipment["cooling"]["name"] == "Pool Chiller"


def test_heater_manual_and_pool_chiller_controls_are_enabled_by_default():
    slots = {slot.slug: slot for slot in resolve_equipment_slots()}

    assert slots["heat_pump"].name == "Heater Manual"
    assert slots["heat_pump"].enable_switch is True
    assert slots["heat_pump"].press_key_id == "13"
    assert slots["cooling"].name == "Pool Chiller"
    assert slots["cooling"].enable_switch is True
    assert slots["cooling"].press_key_id == "0E"


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
