"""Asyncio bridge between udi_interface thread callbacks and kidde-homesafe."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from threading import Event, Lock, Thread
from typing import Any, Dict

from kidde_homesafe import KiddeClient, KiddeClientAuthError, KiddeCommand


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
        def _runner() -> None:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            self._loop = loop
            self._ready.set()
            try:
                loop.run_forever()
            finally:
                pending = asyncio.all_tasks(loop)
                for task in pending:
                    task.cancel()
                if pending:
                    loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))
                loop.close()

        self._thread = Thread(target=_runner, name="kidde-async-loop", daemon=True)
        self._thread.start()
        self._ready.wait(timeout=3)

    def _submit(self, coro, timeout: float = 20.0):
        if self._loop is None or not self._ready.is_set():
            raise RuntimeError("Async loop is not ready")
        future = asyncio.run_coroutine_threadsafe(coro, self._loop)
        return future.result(timeout=timeout)

    def _load_cookies(self) -> dict[str, str]:
        if not self._cookie_file.exists():
            return {}
        try:
            raw = json.loads(self._cookie_file.read_text(encoding="utf-8"))
        except Exception:
            return {}
        if not isinstance(raw, dict):
            return {}
        return {str(key): str(value) for key, value in raw.items()}

    def _save_cookies(self, cookies: dict[str, str]) -> None:
        self._cookie_file.parent.mkdir(parents=True, exist_ok=True)
        self._cookie_file.write_text(json.dumps(cookies, indent=2), encoding="utf-8")

    async def _ensure_client(self, email: str, password: str) -> KiddeClient:
        if self._client is not None:
            return self._client

        cookies = self._load_cookies()
        if cookies:
            client = KiddeClient(cookies)
            try:
                await client.get_data(get_devices=False, get_events=False)
                self._client = client
                return client
            except KiddeClientAuthError:
                pass

        client = await KiddeClient.from_login(email, password)
        self._save_cookies(client.cookies)
        self._client = client
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

    async def _refresh_async(self, email: str, password: str, temp_unit: str = "F") -> Dict[str, Any]:
        # temp_unit is parsed at config-level and reserved for future data mapping.
        _ = temp_unit
        client = await self._ensure_client(email=email, password=password)
        dataset = await client.get_data(get_devices=True, get_events=True)
        devices = dataset.devices or {}
        events = dataset.events or {}
        return {
            "num_alarms": self._count_active_alarms(devices),
            "device_count": len(devices),
            "event_count": len(events),
            "devices": devices,
        }

    async def _device_command_async(self, email: str, password: str, location_id: int, device_id: int, command: KiddeCommand):
        client = await self._ensure_client(email=email, password=password)
        await client.device_command(location_id=location_id, device_id=device_id, command=command)

    def refresh(self, email: str, password: str, temp_unit: str = "F", timeout: float = 20.0) -> Dict[str, Any] | None:
        if not email or not password:
            return None
        with self._lock:
            try:
                return self._submit(self._refresh_async(email=email, password=password, temp_unit=temp_unit), timeout=timeout)
            except KiddeClientAuthError:
                # Force a clean login path on next attempt.
                self._client = None
                try:
                    return self._submit(self._refresh_async(email=email, password=password, temp_unit=temp_unit), timeout=timeout)
                except Exception:
                    return None
            except Exception:
                return None

    def device_command(self, email: str, password: str, location_id: int, device_id: int, command: KiddeCommand, timeout: float = 20.0) -> bool:
        if not email or not password:
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
                return True
            except Exception:
                return False

    def clear_cached_client(self) -> None:
        with self._lock:
            self._client = None

    def shutdown(self) -> None:
        self._shutdown.set()
        if self._loop is not None:
            self._loop.call_soon_threadsafe(self._loop.stop)
        if self._thread is not None:
            self._thread.join(timeout=3)
