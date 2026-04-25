# Node classes for Kidde PG3x node server

import re
import time
import udi_interface
from datetime import datetime, timezone
from config_parser import KiddeConfig, build_config
from kidde_async_adapter import KiddeAsyncAdapter

_ISO_TS_RE = re.compile(r"(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2})")

def _parse_last_seen(s) -> int:
    """Parse an ISO-8601 timestamp string to a Unix integer, returning 0 on failure."""
    if not s:
        return 0
    m = _ISO_TS_RE.match(str(s))
    if not m:
        return 0
    try:
        return int(datetime.fromisoformat(m.group(1)).replace(tzinfo=timezone.utc).timestamp())
    except Exception:
        return 0

LOGGER = udi_interface.LOGGER
Custom = udi_interface.Custom

class KiddeController(udi_interface.Node):
    id = "setup"
    drivers = [
        {"driver": "ST", "value": 0, "uom": 25},
        {"driver": "GV0", "value": 0, "uom": 56},  # Number of alarms
        {"driver": "GV1", "value": 0, "uom": 25},  # Online status
        {"driver": "TIME", "value": int(time.time()), "uom": 151},
    ]

    def __init__(self, polyglot, primary, address, name):
        super().__init__(polyglot, primary, address, name)
        self.poly = polyglot
        self.config = KiddeConfig()
        self.parameters = Custom(self.poly, "customparams")
        self.data_store = Custom(self.poly, "customdata")
        self.heartbeat_state = 0
        self.adapter = KiddeAsyncAdapter()
        self.num_alarms = 0
        self.online = 0
        self.last_update = int(time.time())
        self._alarm_nodes: dict[int, "KiddeAlarmNode"] = {}
        self._started = False
        self._has_valid_params = False
        self._config_done = False
        self._controller_node_added = False
        self._pending_initial_discovery = False
        self._initial_discovery_in_progress = False

        self.poly.subscribe(self.poly.START, self.start, self.address)
        self.poly.subscribe(self.poly.STOP, self.stop)
        self.poly.subscribe(self.poly.POLL, self.poll)
        self.poly.subscribe(self.poly.CUSTOMPARAMS, self.handle_params)
        self.poly.subscribe(self.poly.CUSTOMDATA, self.handle_custom_data)
        self.poly.subscribe(self.poly.CONFIGDONE, self.handle_config_done)
        self.poly.subscribe(self.poly.ADDNODEDONE, self.handle_addnode_done)
        self.poly.subscribe(self.poly.LOGLEVEL, self.handle_log_level)
        self.poly.subscribe(self.poly.DISCOVER, self.discover)

        self.poly.updateProfile()
        self.poly.ready()
        self.poly.addNode(self, conn_status="ST", rename=True)

    def start(self):
        self._started = True
        self._set("TIME", int(time.time()), 151)
        self._pending_initial_discovery = True
        LOGGER.info("Controller start: waiting for CONFIGDONE and ADDNODEDONE before initial Kidde discovery")
        self._maybe_run_initial_discovery("START")

    def stop(self):
        self._set("ST", 0)
        self._set("GV1", 0)
        self.adapter.shutdown()

    def handle_log_level(self, level):
        if isinstance(level, dict) and "level" in level:
            LOGGER.info("New log level: %s", level["level"])

    def handle_params(self, custom_params):
        self.parameters.load(custom_params)
        self.poly.Notices.clear()
        try:
            self.config = build_config(custom_params)
        except Exception as err:
            self.poly.Notices["config"] = f"Invalid configuration format: {err}"
            LOGGER.error("Failed to parse custom params: %s", err)
            return
        missing = []
        if not self.config.email:
            missing.append("EMAIL")
        if not self.config.password:
            missing.append("PASSWORD")
        if missing:
            self._has_valid_params = False
            self.poly.Notices["required"] = "Missing required parameters: " + ", ".join(missing)
            self.online = 0
            self._set("ST", 0)
            self._set("GV1", 0)
            return

        self._has_valid_params = True
        self.adapter.clear_cached_client()
        if self._started:
            self._pending_initial_discovery = True
            LOGGER.info("Configuration updated: scheduling Kidde discovery when startup is fully ready")
            self._maybe_run_initial_discovery("CUSTOMPARAMS")

    def handle_custom_data(self, custom_data):
        self.data_store.load(custom_data or {})
        # Restore any cached state if needed

    def handle_config_done(self):
        self._config_done = True
        LOGGER.info("CONFIGDONE received")
        self._maybe_run_initial_discovery("CONFIGDONE")

    def handle_addnode_done(self, node):
        node_address = getattr(node, "address", None)
        if node_address is None and isinstance(node, dict):
            node_address = node.get("address")
        if node_address == self.address:
            self._controller_node_added = True
            LOGGER.info("ADDNODEDONE received for controller node")
            self._maybe_run_initial_discovery("ADDNODEDONE")

    def _maybe_run_initial_discovery(self, reason: str) -> None:
        if not self._pending_initial_discovery or self._initial_discovery_in_progress:
            return

        # In practice the controller node is often effectively ready by the time
        # START/longPoll runs, even if ADDNODEDONE is not observed for it.
        if not self._controller_node_added and getattr(self, "added", False):
            self._controller_node_added = True
            LOGGER.debug("Controller node marked ready from node.added state after %s", reason)

        waiting_for: list[str] = []
        if not self._started:
            waiting_for.append("START")
        if not self._config_done:
            waiting_for.append("CONFIGDONE")
        if not self._controller_node_added:
            waiting_for.append("ADDNODEDONE(controller)")
        if not self._has_valid_params:
            waiting_for.append("valid EMAIL/PASSWORD params")

        if waiting_for:
            LOGGER.debug(
                "Initial Kidde discovery not ready after %s; waiting for %s",
                reason,
                ", ".join(waiting_for),
            )
            return

        LOGGER.info("Running initial Kidde discovery after %s", reason)
        self._initial_discovery_in_progress = True
        try:
            self._refresh_status()
            if self.online:
                LOGGER.info("Initial Kidde discovery complete: %d detector node(s)", len(self._alarm_nodes))
                self._pending_initial_discovery = False
            else:
                LOGGER.warning("Initial Kidde discovery failed; will retry on subsequent longPoll")
        finally:
            self._initial_discovery_in_progress = False

    def poll(self, poll_type):
        self._set("TIME", int(time.time()), 151)
        if poll_type == "shortPoll":
            self.heartbeat_state = 1 - self.heartbeat_state
            if self.heartbeat_state:
                self.reportCmd("DON", 2)
            else:
                self.reportCmd("DOF", 2)
            return
        if poll_type == "longPoll":
            if self._pending_initial_discovery:
                self._maybe_run_initial_discovery("longPoll")
                return
            self._refresh_status()

    def _refresh_status(self):
        if not self.config.email or not self.config.password:
            self.online = 0
            self._set("ST", 0)
            self._set("GV1", 0)
            return

        result = self.adapter.refresh(
            email=self.config.email,
            password=self.config.password,
            timeout=20.0,
        )
        if result:
            self.online = 1
            self.num_alarms = result.get("num_alarms", 0)
            self.last_update = int(time.time())
            self._set("ST", 1)
            self.poly.Notices.delete("refresh")
            self._reconcile_nodes(result.get("devices", {}))
        else:
            self.online = 0
            self._set("ST", 0)
            self.poly.Notices["refresh"] = "Kidde refresh failed. Check credentials/connectivity."
        self._set("GV1", self.online)
        self._set("GV0", self.num_alarms)
        self._set("TIME", self.last_update, 151)

    def _reconcile_nodes(self, devices: dict) -> None:
        """Create child nodes for newly-discovered devices and update existing ones."""
        used_addresses = {self.address}
        used_addresses.update(node.address for node in self._alarm_nodes.values())

        for device_id, device in devices.items():
            device_id = int(device_id)
            if device_id not in self._alarm_nodes:
                label = (
                    device.get("label")
                    or device.get("announcement")
                    or f"Device {device_id}"
                )
                valid_name = self.poly.getValidName(str(label))
                if not valid_name:
                    valid_name = f"Device {device_id}"

                # Use device id as the source for address generation.
                # getValidAddress enforces PG3 format/length constraints.
                address_seed = f"d{device_id}"
                valid_address = self.poly.getValidAddress(address_seed)
                if valid_address in used_addresses:
                    # Preserve determinism while avoiding collisions after sanitization/truncation.
                    for idx in range(1, 100):
                        candidate = self.poly.getValidAddress(f"{address_seed}{idx}")
                        if candidate not in used_addresses:
                            valid_address = candidate
                            break

                location_id = int(device.get("location_id", 0))
                alarm_node = KiddeAlarmNode(
                    self.poly, self.address, valid_address, valid_name,
                    location_id=location_id, device_id=device_id,
                )
                alarm_node.controller = self
                self.poly.addNode(alarm_node)
                self._alarm_nodes[device_id] = alarm_node
                used_addresses.add(valid_address)
            self._alarm_nodes[device_id].update_from_device(device)

    def discover(self, *_):
        self._refresh_status()

    def force_update(self, command=None):
        self._refresh_status()

    def _set(self, driver, value, uom=None, force=False):
        if uom is None:
            self.setDriver(driver, value, True, force)
        else:
            self.setDriver(driver, value, True, force, uom=uom)

    commands = {
        "UPDATE": force_update,
    }


# Battery state string → integer mapping for GV4
_BATTERY_MAP = {
    "good":     1,
    "ok":       1,
    "low":      2,
    "critical": 3,
}

_IAQ_MAP = {
    "very bad": 1,
    "bad":      2,
    "moderate": 3,
    "good":     4,
}

_MODEL_TYPE_MAP = {
    "wifiiaqdetector":   1,
    "wifidetector":      2,
    "cowifidetector":    3,
    "waterleakdetector": 4,
    "esswfac":           5,
}


def _value_or_self(value):
    """Return scalar value, unwrapping Kidde {value, Unit, status} objects when present."""
    if isinstance(value, dict):
        return value.get("value")
    return value


def _to_int(value, default: int = 0) -> int:
    value = _value_or_self(value)
    try:
        if value is None or value == "":
            return default
        return int(float(value))
    except Exception:
        return default


def _to_bool(value) -> int:
    value = _value_or_self(value)
    if isinstance(value, bool):
        return 1 if value else 0
    if isinstance(value, (int, float)):
        return 1 if value != 0 else 0
    if isinstance(value, str):
        return 1 if value.strip().lower() in {"1", "true", "yes", "on"} else 0
    return 0


class KiddeAlarmNode(udi_interface.Node):
    """Child node representing a single Kidde smoke/CO detector."""

    id = "kiddealarm"
    drivers = [
        {"driver": "ST",     "value": 0, "uom": 2},    # Device online (boolean)
        {"driver": "GV0",   "value": 0, "uom": 2},    # Smoke alarm (boolean)
        {"driver": "GV1",   "value": 0, "uom": 2},    # CO alarm (boolean)
        {"driver": "GV2",   "value": 0, "uom": 2},    # Smoke hushed
        {"driver": "GV3",   "value": 0, "uom": 2},    # Lost
        {"driver": "SMOKED","value": 0, "uom": 56},   # Smoke level (raw)
        {"driver": "CO",    "value": 0, "uom": 54},   # CO level (PPM)
        {"driver": "GV4",   "value": 0, "uom": 25},   # Battery state (battery enum)
        {"driver": "GV5",   "value": 0, "uom": 2},    # Low battery alarm
        {"driver": "GV6",   "value": 0, "uom": 2},    # Water alarm
        {"driver": "GV7",   "value": 0, "uom": 2},    # Freeze alarm
        {"driver": "GV8",   "value": 0, "uom": 2},    # Contact lost
        {"driver": "GV9",   "value": 0, "uom": 56},   # MB model (DETECT indicator)
        {"driver": "GV10",  "value": 0, "uom": 56},   # Life remaining (days/weeks)
        {"driver": "GV11",  "value": 0, "uom": 56},   # Battery level (%)
        {"driver": "GV12",  "value": 0, "uom": 25},   # IAQ status
        {"driver": "GV13",  "value": 0, "uom": 25},   # Model type
        {"driver": "TIME",  "value": 0, "uom": 151},  # Last seen (unix time)
    ]

    def __init__(self, polyglot, primary, address, name, location_id, device_id):
        super().__init__(polyglot, primary, address, name)
        self.location_id = location_id
        self.device_id = device_id
        self.controller: "KiddeController | None" = None
        self._alarm_active: bool = False  # tracks last reported alarm state

    def update_from_device(self, device: dict) -> None:
        """Update drivers from a device dict returned by KiddeDataset.devices."""
        lost        = _to_bool(device.get("lost", False))
        online      = 0 if lost else 1
        smoke       = _to_bool(device.get("smoke_alarm", False))
        co          = _to_bool(device.get("co_alarm", False))
        smoke_hush  = _to_bool(device.get("smoke_hushed", False))
        low_batt    = _to_bool(device.get("low_battery_alarm", False))
        water_alarm = _to_bool(device.get("water_alarm", False))
        low_temp    = _to_bool(device.get("low_temp_alarm", False))
        contact_lost = _to_bool(device.get("contact_lost", False))

        smoke_level = _to_int(device.get("smoke_level", 0), 0)
        co_level    = _to_int(device.get("co_level", None), 0)
        if co_level == 0:
            # DETECT series may report CO value under co_ppm.
            co_level = _to_int(device.get("co_ppm", 0), 0)

        mb_model = _to_int(device.get("mb_model", 0), 0)
        life_remaining = _to_int(device.get("life", 0), 0)
        battery_level = _to_int(device.get("battery_level", 0), 0)
        iaq_raw = str(_value_or_self(device.get("overall_iaq_status", "")) or "").strip().lower()
        iaq_status = _IAQ_MAP.get(iaq_raw, 0)
        model_raw = str(device.get("model", "") or "").strip().lower()
        model_type = _MODEL_TYPE_MAP.get(model_raw, 0)

        battery_raw = str(device.get("battery_state", "") or "").lower()
        battery_int = _BATTERY_MAP.get(battery_raw, 0)
        last_seen   = _parse_last_seen(device.get("last_seen"))

        self.setDriver("ST",     online)
        self.setDriver("GV0",   smoke)
        self.setDriver("GV1",   co)
        self.setDriver("GV2",   smoke_hush)
        self.setDriver("GV3",   lost)
        self.setDriver("SMOKED",smoke_level)
        self.setDriver("CO",    co_level)
        self.setDriver("GV4",   battery_int)
        self.setDriver("GV5",   low_batt)
        self.setDriver("GV6",   water_alarm)
        self.setDriver("GV7",   low_temp)
        self.setDriver("GV8",   contact_lost)
        self.setDriver("GV9",   mb_model)
        self.setDriver("GV10",  life_remaining)
        self.setDriver("GV11",  battery_level)
        self.setDriver("GV12",  iaq_status)
        self.setDriver("GV13",  model_type)
        self.setDriver("TIME",  last_seen)

        # Report DON on alarm onset, DOF on alarm clearance
        alarm_now = bool(smoke or co)
        if alarm_now and not self._alarm_active:
            self.reportCmd("DON", 2)
        elif not alarm_now and self._alarm_active:
            self.reportCmd("DOF", 2)
        self._alarm_active = alarm_now

    def hush(self, command=None) -> None:
        """Send HUSH command to this device via the controller's adapter."""
        if self.controller is None:
            LOGGER.error("KiddeAlarmNode.hush: no controller reference")
            return
        cfg = self.controller.config
        if not cfg.email or not cfg.password:
            LOGGER.warning("KiddeAlarmNode.hush: missing credentials")
            return
        from kidde_homesafe import KiddeCommand
        ok = self.controller.adapter.device_command(
            cfg.email, cfg.password,
            self.location_id, self.device_id,
            KiddeCommand.HUSH,
        )
        LOGGER.info("HUSH %s/%s -> %s", self.location_id, self.device_id, ok)
        if ok:
            self.controller._refresh_status()

    commands = {
        "HUSH": hush,
    }
