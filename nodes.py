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


def _alarm_nodedef_id(supports_smoke: bool, supports_co: bool, supports_iaq: bool) -> str:
    bitmask = (4 if supports_smoke else 0) | (2 if supports_co else 0) | (1 if supports_iaq else 0)
    # Bump schema version when driver semantics/UOMs change so existing nodes are rebuilt.
    return f"kiddealarm_v5_{bitmask}"


def _alarm_nodedef_name(supports_smoke: bool, supports_co: bool, supports_iaq: bool) -> str:
    features = []
    if supports_smoke:
        features.append("Smoke")
    if supports_co:
        features.append("CO")
    if supports_iaq:
        features.append("Air Quality")
    if not features:
        features.append("Base")
    return "Kidde Alarm (" + "+".join(features) + ")"


def _profile_editors() -> list[dict]:
    return [
        {
            "id": "bool",
            "ranges": [
                {
                    "uom": "2",
                    "min": 0,
                    "max": 1,
                    "step": 1,
                    "names": {"0": "No", "1": "Yes"},
                }
            ],
        },
        {
            "id": "connect",
            "ranges": [
                {
                    "uom": "25",
                    "subset": "0,1,2",
                    "names": {
                        "0": "Disconnected",
                        "1": "Connected",
                        "2": "Failed",
                    },
                }
            ],
        },
        {
            "id": "count",
            "ranges": [
                {
                    "uom": "56",
                    "min": 0,
                    "max": 255,
                    "step": 1,
                }
            ],
        },
        {
            "id": "ppm",
            "ranges": [
                {
                    "uom": "54",
                    "min": 0,
                    "max": 9999,
                    "step": 1,
                }
            ],
        },
        {
            "id": "unixtime",
            "ranges": [
                {
                    "uom": "151",
                    "min": 0,
                    "max": 2147483647,
                    "step": 1,
                }
            ],
        },
        {
            "id": "battery",
            "ranges": [
                {
                    "uom": "25",
                    "subset": "0,1,2,3",
                    "names": {
                        "0": "Unknown",
                        "1": "Good",
                        "2": "Low",
                        "3": "Critical",
                    },
                }
            ],
        },
        {
            "id": "iaq",
            "ranges": [
                {
                    "uom": "25",
                    "subset": "0,1,2,3,4",
                    "names": {
                        "0": "Unknown",
                        "1": "Very Bad",
                        "2": "Bad",
                        "3": "Moderate",
                        "4": "Good",
                    },
                }
            ],
        },
        {
            "id": "modeltype",
            "ranges": [
                {
                    "uom": "25",
                    "subset": "0,1,2,3,4,5",
                    "names": {
                        "0": "Unknown",
                        "1": "Smoke+IAQ (wifiiaqdetector)",
                        "2": "Smoke (wifidetector)",
                        "3": "CO (cowifidetector)",
                        "4": "Water Leak (waterleakdetector)",
                        "5": "DETECT (EssWFAC)",
                    },
                }
            ],
        },
        {
            "id": "minuteofday",
            "ranges": [
                {
                    "uom": "44",
                    "min": 0,
                    "max": 1439,
                    "step": 1,
                }
            ],
        },
    ]


def _alarm_properties(supports_smoke: bool, supports_co: bool, supports_iaq: bool) -> list[dict]:
    if supports_smoke and supports_co:
        st_name = "Alarm (Smoke / CO)"
    elif supports_smoke:
        st_name = "Smoke Alarm"
    elif supports_co:
        st_name = "CO Alarm"
    else:
        st_name = "Alarm"
    props = [
        {"id": "ST",   "editor": "bool",        "name": st_name},
        {"id": "GV3",  "editor": "minuteofday", "name": "Chirps Off Time after Midnight"},
        {"id": "GV4",  "editor": "battery",     "name": "Battery State"},
        {"id": "GV5",  "editor": "bool",        "name": "Low Battery Alarm"},
        {"id": "GV6",  "editor": "minuteofday", "name": "Chirps On Time (after Midnight)"},
        {"id": "GV7",  "editor": "bool",        "name": "Online"},
        {"id": "GV9",  "editor": "modeltype",   "name": "Model"},
        {"id": "GV10", "editor": "count",       "name": "Life Remaining"},
        {"id": "TIME", "editor": "unixtime",    "name": "Last Seen"},
    ]
    if supports_smoke:
        props.extend(
            [
                {"id": "GV0", "editor": "bool", "name": "Smoke Alarm"},
                {"id": "GV2", "editor": "bool", "name": "Smoke Hushed"},
                {"id": "SMOKED", "editor": "count", "name": "Smoke Level"},
            ]
        )
    if supports_co:
        props.extend(
            [
                {"id": "GV1", "editor": "bool", "name": "CO Alarm"},
                {"id": "CO", "editor": "ppm", "name": "CO Level"},
            ]
        )
    if supports_iaq:
        props.append({"id": "GV12", "editor": "iaq", "name": "Overall IAQ Status"})
    props.sort(key=lambda item: item["id"])
    return props


def _alarm_nodedefs() -> list[dict]:
    nodedefs = []
    for smoke in (False, True):
        for co in (False, True):
            for iaq in (False, True):
                nodedefs.append(
                    {
                        "id": _alarm_nodedef_id(smoke, co, iaq),
                        "name": _alarm_nodedef_name(smoke, co, iaq),
                        "icon": "GenericCtl",
                        "properties": _alarm_properties(smoke, co, iaq),
                        "cmds": {
                            "sends": [
                                {"id": "DON", "name": "Alarm Active"},
                                {"id": "DOF", "name": "Alarm Cleared"},
                            ],
                            "accepts": [{"id": "HUSH", "name": "Hush Alarm"}],
                        },
                        "links": {"ctl": [], "rsp": []},
                    }
                )
    return nodedefs


def _dynamic_profile_payload() -> dict:
    return {
        "delete": {
            "editors": ["*"],
            "nodedefs": ["*"],
            "linkdefs": ["*"],
        },
        "editors": _profile_editors(),
        "nodedefs": [
            {
                "id": "setup",
                "name": "Kidde Monitors",
                "icon": "GenericCtl",
                "properties": [
                    {"id": "ST", "editor": "connect", "name": "Node Server Status"},
                    {"id": "GV0", "editor": "count", "name": "Number of Alarms"},
                    {"id": "GV1", "editor": "bool", "name": "Online Status"},
                    {"id": "TIME", "editor": "unixtime", "name": "Last Update Time"},
                ],
                "cmds": {
                    "sends": [
                        {"id": "DON", "name": "Heartbeat On"},
                        {"id": "DOF", "name": "Heartbeat Off"},
                    ],
                    "accepts": [{"id": "UPDATE", "name": "Force Data Update"}],
                },
                "links": {"ctl": [], "rsp": []},
            },
            *_alarm_nodedefs(),
        ],
        "linkdefs": [],
    }

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
        self._pending_node_device_updates: dict[str, dict] = {}

        self.poly.subscribe(self.poly.START, self.start, self.address)
        self.poly.subscribe(self.poly.STOP, self.stop)
        self.poly.subscribe(self.poly.POLL, self.poll)
        self.poly.subscribe(self.poly.CUSTOMPARAMS, self.handle_params)
        self.poly.subscribe(self.poly.CUSTOMDATA, self.handle_custom_data)
        self.poly.subscribe(self.poly.CONFIGDONE, self.handle_config_done)
        self.poly.subscribe(self.poly.ADDNODEDONE, self.handle_addnode_done)
        self.poly.subscribe(self.poly.LOGLEVEL, self.handle_log_level)
        self.poly.subscribe(self.poly.DISCOVER, self.discover)

        self._update_dynamic_profile()
        self.poly.ready()
        self.poly.addNode(self, conn_status="ST", rename=True)

    def _update_dynamic_profile(self) -> None:
        updater = getattr(self.poly, "updateJsonProfile", None)
        if not callable(updater):
            LOGGER.error("updateJsonProfile is not available; dynamic profiles are required")
            self.poly.Notices["profile"] = "Dynamic profiles require udi_interface/PG3x support."
            return
        try:
            updater(_dynamic_profile_payload(), {"waitResponse": True})
            LOGGER.info("Dynamic profile updated with 8 Kidde alarm nodedef variants")
            self.poly.Notices.delete("profile")
        except Exception:
            LOGGER.exception("Dynamic profile update failed")
            self.poly.Notices["profile"] = "Dynamic profile update failed. Check PG3x/IoX compatibility."

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
            return

        if node_address in self._pending_node_device_updates:
            pending_device = self._pending_node_device_updates.pop(node_address)
            for alarm_node in self._alarm_nodes.values():
                if alarm_node.address == node_address:
                    LOGGER.debug("Applying deferred device update after ADDNODEDONE for %s", node_address)
                    alarm_node.update_from_device(pending_device)
                    break

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
        expected_device_ids: set[int] = set()

        for device_id, device in devices.items():
            device_id = int(device_id)
            supports_smoke, supports_co, supports_iaq = _device_capabilities(device)
            expected_device_ids.add(device_id)

            expected_nodedef = _alarm_nodedef_id(supports_smoke, supports_co, supports_iaq)
            label = (
                device.get("label")
                or device.get("announcement")
                or f"Device {device_id}"
            )
            valid_name = self.poly.getValidName(str(label))
            if not valid_name:
                valid_name = f"Device {device_id}"
            LOGGER.debug(
                "Discovered Kidde device_id=%s model=%s caps=%s -> smoke=%s co=%s iaq=%s nodedef=%s",
                device_id,
                device.get("model"),
                device.get("capabilities"),
                supports_smoke,
                supports_co,
                supports_iaq,
                expected_nodedef,
            )
            existing = self._alarm_nodes.get(device_id)

            if existing is not None and existing.id != expected_nodedef:
                LOGGER.info(
                    "Replacing node for device_id=%s due to capability change (%s -> %s)",
                    device_id,
                    existing.id,
                    expected_nodedef,
                )
                self.poly.delNode(existing.address)
                used_addresses.discard(existing.address)
                del self._alarm_nodes[device_id]
                existing = None

            if existing is None:
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
                    supports_smoke=supports_smoke,
                    supports_co=supports_co,
                    supports_iaq=supports_iaq,
                )
                alarm_node.controller = self
                self.poly.addNode(alarm_node)
                self._alarm_nodes[device_id] = alarm_node
                used_addresses.add(valid_address)
            elif existing.name != valid_name:
                LOGGER.info(
                    "Renaming node for device_id=%s address=%s from '%s' to '%s'",
                    device_id,
                    existing.address,
                    existing.name,
                    valid_name,
                )
                renamed = False
                try:
                    rename_fn = getattr(existing, "rename", None)
                    if callable(rename_fn):
                        rename_fn(valid_name)
                        renamed = True
                except Exception:
                    LOGGER.debug("Node.rename failed for address=%s", existing.address, exc_info=True)
                if not renamed:
                    try:
                        poly_rename = getattr(self.poly, "renameNode", None)
                        if callable(poly_rename):
                            poly_rename(existing.address, valid_name)
                            renamed = True
                    except Exception:
                        LOGGER.debug("poly.renameNode failed for address=%s", existing.address, exc_info=True)
                if renamed:
                    existing.name = valid_name
                else:
                    LOGGER.warning(
                        "Unable to rename node for device_id=%s; keeping existing name '%s'",
                        device_id,
                        existing.name,
                    )
            target_node = self._alarm_nodes[device_id]
            if getattr(target_node, "added", False):
                target_node.update_from_device(device)
            else:
                LOGGER.debug(
                    "Deferring update for device_id=%s address=%s until ADDNODEDONE",
                    device_id,
                    target_node.address,
                )
                self._pending_node_device_updates[target_node.address] = device

        for known_device_id in list(self._alarm_nodes.keys()):
            if known_device_id in expected_device_ids:
                continue
            stale = self._alarm_nodes[known_device_id]
            LOGGER.info("Removing stale Kidde node device_id=%s address=%s", known_device_id, stale.address)
            self.poly.delNode(stale.address)
            self._pending_node_device_updates.pop(stale.address, None)
            del self._alarm_nodes[known_device_id]

    def discover(self, *_):
        self._update_dynamic_profile()
        self._refresh_status()

    def force_update(self, command=None):
        self._update_dynamic_profile()
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


def _device_capabilities(device: dict) -> tuple[bool, bool, bool]:
    caps = set()
    raw_caps = device.get("capabilities", [])
    if isinstance(raw_caps, list):
        caps = {str(item).strip().lower() for item in raw_caps if str(item).strip()}

    model_raw = str(device.get("model", "") or "").strip().lower()

    if caps:
        supports_smoke = "smoke" in caps
        supports_co = "co" in caps
        supports_iaq = bool({"iaq", "air_quality", "airquality"}.intersection(caps))
    else:
        supports_smoke = any(key in device for key in ("smoke_alarm", "smoke_hushed", "smoke_level"))
        supports_co = any(key in device for key in ("co_alarm", "co_level", "co_ppm"))
        supports_iaq = "overall_iaq_status" in device

    # Model-based fallback when capabilities are incomplete.
    if model_raw == "wifiiaqdetector":
        supports_iaq = True

    return supports_smoke, supports_co, supports_iaq


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


def _to_minute_of_day(value, default: int = 0) -> int:
    value = _value_or_self(value)
    if value is None or value == "":
        return default

    if isinstance(value, str):
        text = value.strip()
        if ":" in text:
            try:
                hh, mm = text.split(":", 1)
                minutes = int(hh) * 60 + int(mm)
                return max(0, min(1439, minutes))
            except Exception:
                return default

    return max(0, min(1439, _to_int(value, default)))


def _minute_of_day_payload(raw_value) -> int | None:
    """Return minutes after midnight, or None when the source is missing/invalid."""
    value = _value_or_self(raw_value)
    if value is None or value == "" or isinstance(value, bool):
        return None

    return _to_minute_of_day(value, 0)


class KiddeAlarmNode(udi_interface.Node):
    """Child node representing a single Kidde smoke/CO detector."""

    def __init__(
        self,
        polyglot,
        primary,
        address,
        name,
        location_id,
        device_id,
        supports_smoke: bool,
        supports_co: bool,
        supports_iaq: bool,
    ):
        self.supports_smoke = bool(supports_smoke)
        self.supports_co = bool(supports_co)
        self.supports_iaq = bool(supports_iaq)
        self.id = _alarm_nodedef_id(self.supports_smoke, self.supports_co, self.supports_iaq)
        self.drivers = self._build_drivers()
        super().__init__(polyglot, primary, address, name)
        self.location_id = location_id
        self.device_id = device_id
        self.controller: "KiddeController | None" = None
        self._alarm_active: bool = False  # tracks last reported alarm state
        self._driver_ids = {driver["driver"] for driver in self.drivers}

    def _build_drivers(self) -> list[dict]:
        drivers = [
            {"driver": "ST",   "value": 0, "uom": 2},    # Alarm active
            {"driver": "GV3",  "value": 0, "uom": 44},   # Chirps Off Time after Midnight
            {"driver": "GV4",  "value": 0, "uom": 25},   # Battery State
            {"driver": "GV5",  "value": 0, "uom": 2},    # Low Battery Alarm
            {"driver": "GV6",  "value": 0, "uom": 44},   # Chirps On Time after Midnight
            {"driver": "GV7",  "value": 0, "uom": 2},    # Online
            {"driver": "GV9",  "value": 0, "uom": 25},   # Model
            {"driver": "GV10", "value": 0, "uom": 56},   # Life Remaining
            {"driver": "TIME", "value": 0, "uom": 151},  # Last Seen
        ]
        if self.supports_smoke:
            drivers.extend(
                [
                    {"driver": "GV0", "value": 0, "uom": 2},
                    {"driver": "GV2", "value": 0, "uom": 2},
                    {"driver": "SMOKED", "value": 0, "uom": 56},
                ]
            )
        if self.supports_co:
            drivers.extend(
                [
                    {"driver": "GV1", "value": 0, "uom": 2},
                    {"driver": "CO", "value": 0, "uom": 54},
                ]
            )
        if self.supports_iaq:
            drivers.append({"driver": "GV12", "value": 0, "uom": 25})
        return drivers

    def _set_if_supported(self, driver: str, value, uom: int | None = None) -> None:
        if driver in self._driver_ids:
            if uom is None:
                self.setDriver(driver, value)
            else:
                self.setDriver(driver, value, uom=uom)

    def update_from_device(self, device: dict) -> None:
        """Update drivers from a device dict returned by KiddeDataset.devices."""
        online      = 0 if _to_bool(device.get("lost", False)) else 1
        smoke       = _to_bool(device.get("smoke_alarm", False)) if self.supports_smoke else 0
        co          = _to_bool(device.get("co_alarm", False)) if self.supports_co else 0
        smoke_hush  = _to_bool(device.get("smoke_hushed", False)) if self.supports_smoke else 0
        low_batt    = _to_bool(device.get("low_battery_alarm", False))

        smoke_level = _to_int(device.get("smoke_level", 0), 0) if self.supports_smoke else 0
        co_level    = _to_int(device.get("co_level", None), 0) if self.supports_co else 0
        if self.supports_co and co_level == 0:
            # DETECT series may report CO value under co_ppm.
            co_level = _to_int(device.get("co_ppm", 0), 0)
        life_remaining = _to_int(device.get("life", 0), 0)
        chips_off_raw = next(
            (
                device.get(key)
                for key in (
                    "no_chips_off",
                    "no_chips_off_time",
                    "noChipsOff",
                    "no_chipsOff",
                    "no_chirp_off",
                    "no_chirp_off_time",
                    "noChirpOff",
                    "no_chirpOff",
                )
                if key in device and device.get(key) not in (None, "")
            ),
            None,
        )
        chips_on_raw = next(
            (
                device.get(key)
                for key in (
                    "no_chips_on",
                    "no_chips_on_time",
                    "noChipsOn",
                    "no_chipsOn",
                    "no_chirp_on",
                    "no_chirp_on_time",
                    "noChirpOn",
                    "no_chirpOn",
                )
                if key in device and device.get(key) not in (None, "")
            ),
            None,
        )
        chips_off = _minute_of_day_payload(chips_off_raw)
        chips_on = _minute_of_day_payload(chips_on_raw)
        iaq_raw = str(_value_or_self(device.get("overall_iaq_status", "")) or "").strip().lower()
        iaq_status = _IAQ_MAP.get(iaq_raw, 0) if self.supports_iaq else 0
        model_raw = str(device.get("model", "") or "").strip().lower()
        model_type = _MODEL_TYPE_MAP.get(model_raw, 0)

        battery_raw = str(device.get("battery_state", "") or "").lower()
        battery_int = _BATTERY_MAP.get(battery_raw, 0)
        last_seen   = _parse_last_seen(device.get("last_seen"))

        # Report DON on alarm onset, DOF on alarm clearance
        alarm_now = bool(smoke or co)
        if alarm_now and not self._alarm_active:
            self.reportCmd("DON", 2)
        elif not alarm_now and self._alarm_active:
            self.reportCmd("DOF", 2)
        self._alarm_active = alarm_now

        self._set_if_supported("ST",    1 if alarm_now else 0)
        self._set_if_supported("GV0",   smoke)
        self._set_if_supported("GV1",   co)
        self._set_if_supported("GV2",   smoke_hush)
        
        if chips_off is not None:
            LOGGER.debug(
                "device_id=%s chirps_off raw=%r mapped=%r driver=GV3 uom=44",
                self.device_id,
                chips_off_raw,
                chips_off,
            )
            self._set_if_supported("GV3", chips_off, uom=44)
        else:
            # Enforce UOM migration even when the API omits chips-off data.
            current = self.getDriver("GV3")
            current_minutes = _to_minute_of_day(current, 0)
            LOGGER.debug(
                "device_id=%s chirps_off raw=%r mapped=%r driver=GV3 uom=44 (fallback)",
                self.device_id,
                chips_off_raw,
                current_minutes,
            )
            self._set_if_supported("GV3", current_minutes, uom=44)
        self._set_if_supported("SMOKED", smoke_level)
        self._set_if_supported("CO",    co_level)
        self._set_if_supported("GV4",   battery_int)
        self._set_if_supported("GV5",   low_batt)
        if chips_on is not None:
            LOGGER.debug(
                "device_id=%s chirps_on raw=%r mapped=%r driver=GV6 uom=44",
                self.device_id,
                chips_on_raw,
                chips_on,
            )
            self._set_if_supported("GV6", chips_on, uom=44)
        else:
            # Enforce UOM migration even when the API omits chips-on data.
            current = self.getDriver("GV6")
            current_minutes = _to_minute_of_day(current, 0)
            LOGGER.debug(
                "device_id=%s chirps_on raw=%r mapped=%r driver=GV6 uom=44 (fallback)",
                self.device_id,
                chips_on_raw,
                current_minutes,
            )
            self._set_if_supported("GV6", current_minutes, uom=44)
        self._set_if_supported("GV7",   online)
        self._set_if_supported("GV9",   model_type)
        self._set_if_supported("GV10",  life_remaining)
        self._set_if_supported("GV12",  iaq_status)
        self._set_if_supported("TIME",  last_seen)

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
