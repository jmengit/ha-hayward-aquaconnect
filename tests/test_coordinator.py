from __future__ import annotations

import asyncio
import sys
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from types import ModuleType, SimpleNamespace
from typing import Any, cast

import pytest


if "homeassistant" not in sys.modules:
    ha = ModuleType("homeassistant")
    config_entries = ModuleType("homeassistant.config_entries")
    core = ModuleType("homeassistant.core")
    helpers = ModuleType("homeassistant.helpers")
    aiohttp_client = ModuleType("homeassistant.helpers.aiohttp_client")
    update_coordinator = ModuleType("homeassistant.helpers.update_coordinator")

    class ConfigEntry:  # pragma: no cover - import stub
        pass

    class HomeAssistant:  # pragma: no cover - import stub
        pass

    class UpdateFailed(Exception):
        pass

    class DataUpdateCoordinator:
        def __init__(self, hass, logger, name=None, update_interval=None):
            self.hass = hass
            self.logger = logger
            self.name = name
            self.update_interval = update_interval
            self.data = None

        def __class_getitem__(cls, item):
            return cls

        async def async_request_refresh(self):
            self.data = await self._async_update_data()  # type: ignore[attr-defined]
            return self.data

    def async_get_clientsession(hass):
        return getattr(hass, "session", None)

    setattr(config_entries, "ConfigEntry", ConfigEntry)
    setattr(core, "HomeAssistant", HomeAssistant)
    setattr(aiohttp_client, "async_get_clientsession", async_get_clientsession)
    setattr(update_coordinator, "DataUpdateCoordinator", DataUpdateCoordinator)
    setattr(update_coordinator, "UpdateFailed", UpdateFailed)

    setattr(ha, "config_entries", config_entries)
    setattr(ha, "core", core)
    setattr(ha, "helpers", helpers)

    sys.modules["homeassistant"] = ha
    sys.modules["homeassistant.config_entries"] = config_entries
    sys.modules["homeassistant.core"] = core
    sys.modules["homeassistant.helpers"] = helpers
    sys.modules["homeassistant.helpers.aiohttp_client"] = aiohttp_client
    sys.modules["homeassistant.helpers.update_coordinator"] = update_coordinator


from custom_components.hayward_aquaconnect import coordinator as coordinator_mod
from custom_components.hayward_aquaconnect.client import AquaConnectError
from custom_components.hayward_aquaconnect.parser import AquaConnectStatus


@dataclass
class FakeEntry:
    data: dict
    options: dict


class FakeClient:
    def __init__(self, outcomes):
        self.outcomes = list(outcomes)
        self.calls = 0

    async def async_read_status(self, *args, **kwargs):
        self.calls += 1
        outcome = self.outcomes.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome


class FakeDatetime:
    times: list[datetime] = []

    @classmethod
    def now(cls, tz=None):
        if not cls.times:
            raise AssertionError("FakeDatetime.now called without queued times")
        return cls.times.pop(0)


@pytest.fixture(autouse=True)
def reset_fake_datetime(monkeypatch):
    monkeypatch.setattr(coordinator_mod, "datetime", FakeDatetime)
    FakeDatetime.times = []


def test_failure_progression_and_staleness():
    async def run():
        entry = FakeEntry(data={"host": "192.168.86.182"}, options={"scan_interval": 5})
        coord = coordinator_mod.AquaConnectCoordinator(SimpleNamespace(session=None), entry)
        good = AquaConnectStatus(display_line_1="Air Temp 74&#176F", raw_leds="EDTDDCDD3333")
        cast(Any, coord).client = FakeClient(
            [
                good,
                AquaConnectError("read 1 failed"),
                AquaConnectError("read 2 failed"),
                AquaConnectError("read 3 failed"),
                AquaConnectError("read 4 failed"),
            ]
        )

        base = datetime(2026, 6, 12, 12, 0, tzinfo=UTC)
        FakeDatetime.times = [
            base,
            base + timedelta(seconds=1),
            base + timedelta(seconds=2),
            base + timedelta(seconds=12),
            base + timedelta(seconds=32),
        ]

        first = await cast(Any, coord).async_request_refresh()
        assert first["display_line_1"] == "Air Temp 74&#176F"
        assert coord.consecutive_failures == 0
        assert coord.last_successful_read == base
        assert coord._read_status_state() == "healthy"

        second = await cast(Any, coord).async_request_refresh()
        assert second["display_line_1"] == "Air Temp 74&#176F"
        assert coord.consecutive_failures == 1
        assert coord.cooldown_until is None
        assert coord._read_status_state() == "degraded"

        third = await cast(Any, coord).async_request_refresh()
        assert third["display_line_1"] == "Air Temp 74&#176F"
        assert coord.consecutive_failures == 2
        assert coord.cooldown_until == base + timedelta(seconds=12)
        assert coord._read_status_state() == "cooldown"

        fourth = await cast(Any, coord).async_request_refresh()
        assert fourth["display_line_1"] == "Air Temp 74&#176F"
        assert coord.consecutive_failures == 3
        assert coord.cooldown_until == base + timedelta(seconds=32)
        assert coord._read_status_state() == "cooldown"

        with pytest.raises(coordinator_mod.UpdateFailed):
            await cast(Any, coord).async_request_refresh()
        assert coord.consecutive_failures == 4
        assert coord._read_status_state() == "stale"

    asyncio.run(run())


def test_cooldown_skips_device_reads():
    async def run():
        entry = FakeEntry(data={"host": "192.168.86.182"}, options={"scan_interval": 5})
        coord = coordinator_mod.AquaConnectCoordinator(SimpleNamespace(session=None), entry)
        coord.data = {"display_line_1": "cached"}
        fake_client = FakeClient([AquaConnectError("should not be used")])
        cast(Any, coord).client = fake_client
        coord.consecutive_failures = 2
        coord.cooldown_until = datetime(2026, 6, 12, 12, 0, tzinfo=UTC) + timedelta(seconds=10)

        FakeDatetime.times = [datetime(2026, 6, 12, 12, 0, 5, tzinfo=UTC)]
        data = await cast(Any, coord).async_request_refresh()
        assert data["display_line_1"] == "cached"
        assert fake_client.calls == 0

    asyncio.run(run())


def test_generic_display_alert_requires_persistent_non_standard_text():
    async def run():
        entry = FakeEntry(data={"host": "192.168.86.182"}, options={"scan_interval": 5})
        coord = coordinator_mod.AquaConnectCoordinator(SimpleNamespace(session=None), entry)
        alert = AquaConnectStatus(
            display_line_1="Service Required",
            display_line_2="Inspect Cell",
            display_message="Service Required / Inspect Cell",
            display_page_kind="alert",
            display_alert="Service Required / Inspect Cell",
            raw_leds="EDTDDCDD3333",
        )
        cast(Any, coord).client = FakeClient([alert, alert, alert])

        base = datetime(2026, 6, 12, 12, 0, tzinfo=UTC)
        FakeDatetime.times = [base, base + timedelta(minutes=2), base + timedelta(minutes=3, seconds=1)]

        first = await cast(Any, coord).async_request_refresh()
        assert first["display_alert"] is None
        assert first["display_alert_candidate"] == "Service Required / Inspect Cell"
        assert first["display_alert_observations"] == 1

        second = await cast(Any, coord).async_request_refresh()
        assert second["display_alert"] is None
        assert second["display_alert_observations"] == 2

        third = await cast(Any, coord).async_request_refresh()
        assert third["display_alert"] == "Service Required / Inspect Cell"
        assert third["display_alert_observations"] == 3

    asyncio.run(run())


def test_check_system_display_alert_confirms_immediately_and_survives_rotation():
    async def run():
        entry = FakeEntry(data={"host": "192.168.86.182"}, options={"scan_interval": 5})
        coord = coordinator_mod.AquaConnectCoordinator(SimpleNamespace(session=None), entry)
        alert = AquaConnectStatus(
            display_line_1="No Flow",
            display_line_2="Check System",
            display_message="No Flow / Check System",
            display_page_kind="alert",
            display_alert="No Flow / Check System",
            raw_leds="EDTDDCDD3333",
        )
        routine = AquaConnectStatus(
            display_line_1="Salt Level",
            display_line_2="2800 PPM",
            display_message="Salt Level / 2800 PPM",
            display_page_kind="routine",
            salt_level=2800,
            raw_leds="EDTDDCDD3333",
        )
        cast(Any, coord).client = FakeClient([alert, routine])

        base = datetime(2026, 6, 12, 12, 0, tzinfo=UTC)
        FakeDatetime.times = [base, base + timedelta(minutes=1)]

        first = await cast(Any, coord).async_request_refresh()
        assert first["display_alert"] == "No Flow / Check System"
        assert first["display_alert_candidate"] == "No Flow / Check System"
        assert first["display_alert_observations"] == 1

        second = await cast(Any, coord).async_request_refresh()
        assert second["display_page_kind"] == "routine"
        assert second["display_alert"] == "No Flow / Check System"
        assert second["display_alert_candidate"] == "No Flow / Check System"

    asyncio.run(run())


def test_display_alert_confirms_when_same_alert_recurs_between_routine_pages():
    async def run():
        entry = FakeEntry(data={"host": "192.168.86.182"}, options={"scan_interval": 5})
        coord = coordinator_mod.AquaConnectCoordinator(SimpleNamespace(session=None), entry)
        alert = AquaConnectStatus(
            display_line_1="Service Required",
            display_line_2="Inspect Cell",
            display_message="Service Required / Inspect Cell",
            display_page_kind="alert",
            display_alert="Service Required / Inspect Cell",
            raw_leds="EDTDDCDD3333",
        )
        routine = AquaConnectStatus(
            display_line_1="Pool Temp 85&#176F",
            display_message="Pool Temp 85&#176F",
            display_page_kind="routine",
            pool_temperature=85,
            raw_leds="EDTDDCDD3333",
        )
        cast(Any, coord).client = FakeClient([alert, routine, alert, routine, alert])

        base = datetime(2026, 6, 12, 12, 0, tzinfo=UTC)
        FakeDatetime.times = [
            base,
            base + timedelta(minutes=1),
            base + timedelta(minutes=2),
            base + timedelta(minutes=3),
            base + timedelta(minutes=4),
        ]

        first = await cast(Any, coord).async_request_refresh()
        assert first["display_alert"] is None
        assert first["display_alert_candidate"] == "Service Required / Inspect Cell"
        assert first["display_alert_observations"] == 1

        second = await cast(Any, coord).async_request_refresh()
        assert second["display_page_kind"] == "routine"
        assert second["display_alert"] is None
        assert second["display_alert_candidate"] == "Service Required / Inspect Cell"
        assert second["display_alert_observations"] == 1

        third = await cast(Any, coord).async_request_refresh()
        assert third["display_alert"] is None
        assert third["display_alert_observations"] == 2

        fourth = await cast(Any, coord).async_request_refresh()
        assert fourth["display_page_kind"] == "routine"
        assert fourth["display_alert"] is None
        assert fourth["display_alert_candidate"] == "Service Required / Inspect Cell"
        assert fourth["display_alert_observations"] == 2

        fifth = await cast(Any, coord).async_request_refresh()
        assert fifth["display_alert"] == "Service Required / Inspect Cell"
        assert fifth["display_alert_observations"] == 3

    asyncio.run(run())


def test_display_alert_does_not_trigger_during_short_menu_navigation():
    async def run():
        entry = FakeEntry(data={"host": "192.168.86.182"}, options={"scan_interval": 5})
        coord = coordinator_mod.AquaConnectCoordinator(SimpleNamespace(session=None), entry)
        menu_pages = [
            AquaConnectStatus(
                display_line_1="Settings Menu",
                display_line_2="Filter Time",
                display_message="Settings Menu / Filter Time",
                display_page_kind="alert",
                display_alert="Settings Menu / Filter Time",
                raw_leds="EDTDDCDD3333",
            ),
            AquaConnectStatus(
                display_line_1="Settings Menu",
                display_line_2="Heater Config",
                display_message="Settings Menu / Heater Config",
                display_page_kind="alert",
                display_alert="Settings Menu / Heater Config",
                raw_leds="EDTDDCDD3333",
            ),
            AquaConnectStatus(
                display_line_1="Friday",
                display_line_2="10:57A",
                display_message="Friday / 10:57A",
                display_page_kind="clock",
                raw_leds="EDTDDCDD3333",
            ),
        ]
        cast(Any, coord).client = FakeClient(menu_pages)

        base = datetime(2026, 6, 12, 12, 0, tzinfo=UTC)
        FakeDatetime.times = [base, base + timedelta(minutes=1), base + timedelta(minutes=2)]

        first = await cast(Any, coord).async_request_refresh()
        assert first["display_alert"] is None
        assert first["display_alert_candidate"] == "Settings Menu / Filter Time"

        second = await cast(Any, coord).async_request_refresh()
        assert second["display_alert"] is None
        assert second["display_alert_candidate"] == "Settings Menu / Heater Config"

        third = await cast(Any, coord).async_request_refresh()
        assert third["display_alert"] is None
        assert third["display_alert_candidate"] == "Settings Menu / Heater Config"
        assert third["display_page_kind"] == "clock"

    asyncio.run(run())


def test_measurement_values_are_retained_until_twenty_four_hour_stale_threshold():
    async def run():
        entry = FakeEntry(data={"host": "192.168.86.182"}, options={"scan_interval": 5})
        coord = coordinator_mod.AquaConnectCoordinator(SimpleNamespace(session=None), entry)
        pool_temp = AquaConnectStatus(
            display_line_1="Pool Temp 85&#176F",
            display_message="Pool Temp 85&#176F",
            display_page_kind="routine",
            pool_temperature=85,
            raw_leds="EDTDDCDD3333",
        )
        pump_off_page = AquaConnectStatus(
            display_line_1="Heat Pump",
            display_line_2="Manual Off",
            display_message="Heat Pump / Manual Off",
            display_page_kind="routine",
            raw_leds="EDTDDCDD3333",
        )
        cast(Any, coord).client = FakeClient([pool_temp, pump_off_page, pump_off_page])

        base = datetime(2026, 6, 12, 12, 0, tzinfo=UTC)
        FakeDatetime.times = [base, base + timedelta(hours=23, minutes=59), base + timedelta(hours=24, seconds=1)]

        first = await cast(Any, coord).async_request_refresh()
        assert first["pool_temperature"] == 85

        retained = await cast(Any, coord).async_request_refresh()
        assert retained["pool_temperature"] == 85

        expired = await cast(Any, coord).async_request_refresh()
        assert expired["pool_temperature"] is None

    asyncio.run(run())
