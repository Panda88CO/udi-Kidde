"""Asyncio bridge between udi_interface thread callbacks and kidde-homesafe."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from threading import Event, Lock, Thread
from typing import Any, Dict

import udi_interface
from kidde_homesafe import KiddeClient, KiddeClientAuthError, KiddeCommand


LOGGER = udi_interface.LOGGER


def _redact_email(email: str) -> str:
    if not email or "@" not in email:
        return "<redacted>"
    local, domain = email.split("@", 1)
    if len(local) <= 2:
        masked_local = "*" * len(local)
    else:
        masked_local = local[0] + ("*" * (len(local) - 2)) + local[-1]
    return f"{masked_local}@{domain}"


class KiddeAsyncAdapter:
    def __init__(self, cookie_file: str = ".kidde_cookies.json") -> None:
        self._cookie_file = Path(cookie_file)
        self._loop: asyncio.AbstractEventLoop | None = None
        self._thread: Thread | None = None
        self._ready = Event()
        self._shutdown = Event()
        self._lock = Lock()
        self._client: KiddeClient | None = None
        self._start_loop()

    def _start_loop(self) -> None:
        LOGGER.debug("Starting Kidde async event loop thread")

        def _runner() -> None:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            self._loop = loop
            self._ready.set()
            LOGGER.debug("Kidde async event loop ready")
            try:
                loop.run_forever()
            finally:
                LOGGER.debug("Stopping Kidde async event loop")
                pending = asyncio.all_tasks(loop)
                for task in pending:
                    task.cancel()
                if pending:
                    loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))
                loop.close()
                LOGGER.debug("Kidde async event loop closed")

        self._thread = Thread(target=_runner, name="kidde-async-loop", daemon=True)
        self._thread.start()
        if not self._ready.wait(timeout=3):
            LOGGER.warning("Kidde async event loop did not become ready within timeout")

    def _submit(self, coro, timeout: float = 20.0):
        if self._loop is None or not self._ready.is_set():
            raise RuntimeError("Async loop is not ready")
        LOGGER.debug("Submitting coroutine to Kidde async loop (timeout=%ss)", timeout)
        future = asyncio.run_coroutine_threadsafe(coro, self._loop)
        return future.result(timeout=timeout)

    def _load_cookies(self) -> dict[str, str]:
        if not self._cookie_file.exists():
            LOGGER.debug("Kidde cookie file not found at %s", self._cookie_file)
            return {}
        try:
            raw = json.loads(self._cookie_file.read_text(encoding="utf-8"))
        except Exception:
            LOGGER.warning("Failed to read Kidde cookie file at %s", self._cookie_file, exc_info=True)
            return {}
        if not isinstance(raw, dict):
            LOGGER.warning("Ignoring Kidde cookie file: expected object, got %s", type(raw).__name__)
            return {}
        LOGGER.debug("Loaded Kidde cookies from %s", self._cookie_file)
        return {str(key): str(value) for key, value in raw.items()}

    def _save_cookies(self, cookies: dict[str, str]) -> None:
        self._cookie_file.parent.mkdir(parents=True, exist_ok=True)
        self._cookie_file.write_text(json.dumps(cookies, indent=2), encoding="utf-8")
        LOGGER.debug("Saved Kidde cookies to %s", self._cookie_file)

    async def _ensure_client(self, email: str, password: str) -> KiddeClient:
        if self._client is not None:
            LOGGER.debug("Reusing cached Kidde client")
            return self._client

        cookies = self._load_cookies()
        if cookies:
            LOGGER.debug("Attempting Kidde auth with cached cookies")
            client = KiddeClient(cookies)
            try:
                await client.get_data(get_devices=False, get_events=False)
                self._client = client
                LOGGER.debug("Kidde cookie authentication successful")
                return client
            except KiddeClientAuthError:
                LOGGER.debug("Kidde cached cookies are no longer valid")
                pass

        LOGGER.debug("Attempting Kidde login for %s", _redact_email(email))
        client = await KiddeClient.from_login(email, password)
        self._save_cookies(client.cookies)
        self._client = client
        LOGGER.debug("Kidde login successful for %s", _redact_email(email))
        return client

    @staticmethod
    def _count_active_alarms(devices: dict[int, dict[str, Any]] | None) -> int:
        if not devices:
            return 0
        count = 0
        for device in devices.values():
            if bool(device.get("smoke_alarm")) or bool(device.get("co_alarm")):
                count += 1
        return count

    async def _refresh_async(self, email: str, password: str) -> Dict[str, Any]:
        LOGGER.debug("Refreshing Kidde dataset for %s", _redact_email(email))
        client = await self._ensure_client(email=email, password=password)
        dataset = await client.get_data(get_devices=True, get_events=False)
        devices = dataset.devices or {}
        events = dataset.events or {}
        LOGGER.debug(
            "Kidde dataset refresh complete: devices=%d events=%d alarms=%d",
            len(devices),
            len(events),
            self._count_active_alarms(devices),
        )
        return {
            "num_alarms": self._count_active_alarms(devices),
            "device_count": len(devices),
            "event_count": len(events),
            "devices": devices,
        }

    async def _device_command_async(self, email: str, password: str, location_id: int, device_id: int, command: KiddeCommand):
        LOGGER.debug(
            "Sending Kidde command=%s location_id=%s device_id=%s for %s",
            command,
            location_id,
            device_id,
            _redact_email(email),
        )
        client = await self._ensure_client(email=email, password=password)
        await client.device_command(location_id=location_id, device_id=device_id, command=command)
        LOGGER.debug("Kidde command sent successfully")

    def refresh(self, email: str, password: str, timeout: float = 20.0) -> Dict[str, Any] | None:
        if not email or not password:
            LOGGER.debug("Skipping Kidde refresh due to missing credentials")
            return None
        with self._lock:
            try:
                result = self._submit(self._refresh_async(email=email, password=password), timeout=timeout)
                LOGGER.debug("Kidde refresh succeeded")
                return result
            except KiddeClientAuthError:
                LOGGER.debug("Kidde auth error during refresh; retrying after clearing cached client")
                # Force a clean login path on next attempt.
                self._client = None
                try:
                    result = self._submit(self._refresh_async(email=email, password=password), timeout=timeout)
                    LOGGER.debug("Kidde refresh succeeded after re-authentication")
                    return result
                except Exception:
                    LOGGER.warning("Kidde refresh failed after re-authentication attempt", exc_info=True)
                    return None
            except Exception:
                LOGGER.warning("Kidde refresh failed", exc_info=True)
                return None

    def device_command(self, email: str, password: str, location_id: int, device_id: int, command: KiddeCommand, timeout: float = 20.0) -> bool:
        if not email or not password:
            LOGGER.debug("Skipping Kidde command due to missing credentials")
            return False
        with self._lock:
            try:
                self._submit(
                    self._device_command_async(
                        email=email,
                        password=password,
                        location_id=location_id,
                        device_id=device_id,
                        command=command,
                    ),
                    timeout=timeout,
                )
                LOGGER.debug("Kidde device command succeeded")
                return True
            except Exception:
                LOGGER.warning("Kidde device command failed", exc_info=True)
                return False

    def clear_cached_client(self) -> None:
        with self._lock:
            self._client = None
        LOGGER.debug("Cleared cached Kidde client")

    def shutdown(self) -> None:
        LOGGER.debug("Shutting down Kidde async adapter")
        self._shutdown.set()
        if self._loop is not None:
            self._loop.call_soon_threadsafe(self._loop.stop)
        if self._thread is not None:
            self._thread.join(timeout=3)
        LOGGER.debug("Kidde async adapter shutdown complete")
