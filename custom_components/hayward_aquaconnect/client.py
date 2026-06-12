from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any

import aiohttp

from .parser import AquaConnectStatus, parse_payload
from .slots import SLOTS_BY_SLUG


class AquaConnectError(Exception):
    """Base AquaConnect error."""


class AquaConnectCommandError(AquaConnectError):
    """Raised when a command cannot be verified."""


@dataclass
class CommandResult:
    slot: str
    desired_state: str
    success: bool
    attempts: int
    final_state: str | None
    message: str


class AquaConnectClient:
    def __init__(self, session: aiohttp.ClientSession, host: str) -> None:
        self.session = session
        self.host = host.removeprefix("http://").removeprefix("https://").rstrip("/")
        self.base_url = f"http://{self.host}"
        self._lock = asyncio.Lock()

    async def async_read_status(self) -> AquaConnectStatus:
        payload = await self._post("Update Local Server&", content_type="text/plain;charset=UTF-8")
        return parse_payload(payload)

    async def async_press_key(self, key_id: str) -> str:
        return await self._post(f"KeyId={key_id}&", content_type="application/x-www-form-urlencoded")

    async def _post(self, body: str, content_type: str) -> str:
        url = f"{self.base_url}/WNewSt.htm"
        try:
            async with self.session.post(url, data=body, headers={"Content-Type": content_type}) as response:
                response.raise_for_status()
                return await response.text(encoding="latin-1")
        except (aiohttp.ClientError, asyncio.TimeoutError) as err:
            raise AquaConnectError(f"AquaConnect request failed: {err}") from err

    async def async_set_slot_state(
        self,
        slug: str,
        desired_on: bool,
        *,
        retries: int = 1,
        verify_timeout: float = 10.0,
        button_delay: float = 0.75,
    ) -> CommandResult:
        desired = "on" if desired_on else "off"
        slot = SLOTS_BY_SLUG[slug]
        async with self._lock:
            initial = await self.async_read_status()
            current = initial.equipment.get(slug, {}).get("state")
            if current == desired:
                return CommandResult(slug, desired, True, 0, current, "Already in desired state")

            attempts = 0
            last_state = current
            errors: list[str] = []
            for attempt in range(retries + 1):
                attempts = attempt + 1
                try:
                    await self.async_press_key(slot.press_key_id)
                    await asyncio.sleep(button_delay)
                    deadline = asyncio.get_running_loop().time() + verify_timeout
                    while asyncio.get_running_loop().time() < deadline:
                        status = await self.async_read_status()
                        last_state = status.equipment.get(slug, {}).get("state")
                        if last_state == desired:
                            return CommandResult(slug, desired, True, attempts, last_state, "Verified desired state")
                        await asyncio.sleep(0.75)
                    errors.append(f"attempt {attempts}: timed out waiting for {desired}, last_state={last_state}")
                except AquaConnectError as err:
                    errors.append(f"attempt {attempts}: {err}")

            message = "; ".join(errors) or f"Could not verify {slug} changed to {desired}"
            raise AquaConnectCommandError(message)
