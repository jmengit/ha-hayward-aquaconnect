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
