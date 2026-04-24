# Node classes for Kidde PG3x node server

import udi_interface
import time
from config_parser import KiddeConfig, build_config
from kidde_async_adapter import KiddeAsyncAdapter

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

        self.poly.subscribe(self.poly.START, self.start, self.address)
        self.poly.subscribe(self.poly.STOP, self.stop)
        self.poly.subscribe(self.poly.POLL, self.poll)
        self.poly.subscribe(self.poly.CUSTOMPARAMS, self.handle_params)
        self.poly.subscribe(self.poly.CUSTOMDATA, self.handle_custom_data)
        self.poly.subscribe(self.poly.LOGLEVEL, self.handle_log_level)
        self.poly.subscribe(self.poly.DISCOVER, self.discover)

        self.poly.updateProfile()
        self.poly.ready()
        self.poly.addNode(self, conn_status="ST", rename=True)

    def start(self):
        self._set("TIME", int(time.time()), 151)
        # Defer Kidde login to longPoll

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
            self.poly.Notices["required"] = "Missing required parameters: " + ", ".join(missing)
        # No device login here; defer to longPoll

    def handle_custom_data(self, custom_data):
        self.data_store.load(custom_data or {})
        # Restore any cached state if needed

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
            self._refresh_status()

    def _refresh_status(self):
        # Run async Kidde refresh in background
        result = self.adapter.refresh()
        if result:
            self.online = 1
            self.num_alarms = result.get("num_alarms", 0)
            self.last_update = int(time.time())
        else:
            self.online = 0
        self._set("GV1", self.online)
        self._set("GV0", self.num_alarms)
        self._set("TIME", self.last_update, 151)

    def discover(self, *_):
        pass

    def _set(self, driver, value, uom=None, force=False):
        if uom is None:
            self.setDriver(driver, value, True, force)
        else:
            self.setDriver(driver, value, True, force, uom=uom)
