"""cFos Powerbrain http API interface."""
import requests

API_GET_VALIDATE_AUTH = "/ui/en/sim.htm"
API_GET_PARAMS = "/cnf?cmd=get_params"
API_SET_PARAMS = "/cnf?cmd=set_params"
API_GET_DEV_INFO = "/cnf?cmd=get_dev_info"
API_GET_ENTER_RFID = "/cnf?cmd=enter_rfid&rfid="
API_GET_SET_VAR = "/cnf?cmd=set_cm_vars&name="
API_OVERRIDE_DEVICE = "/cnf?cmd=override_device&dev_id="
API_OVERRIDE_FLAG_AMPS = "&mamps="
API_OVERRIDE_FLAGS = "&flags="
API_DEV_ID = "&dev_id="
API_VAR_VAL = "&val="
API_SET_METER = "/cnf?cmd=set_ajax_meter"


class Powerbrain:
    """Powerbrain charging controller class."""

    def __init__(self, host, username, password):
        """Initialize the Powerbrain instance."""
        self.host = host
        self.username = username
        self.password = password
        self.name = ""
        self.devices = {}
        self.attributes = {}
        self.version = 0.0

    def validate_auth(self):
        """Make a request to check if given admin username and password are valid."""
        response = requests.get(
            self.host + API_GET_VALIDATE_AUTH,
            timeout=5,
            auth=(self.username, self.password),
        )
        response.raise_for_status()

    def get_devices(self):
        """Get powerbrain attributes and available devices."""

        dev_info = requests.get(self.host + API_GET_DEV_INFO, timeout=5).json()

        params = dev_info["params"]
        self.name = params["title"]
        self.attributes = params
        version_list = params["version"].split(".")
        self.version = float(version_list[0] + "." + version_list[1])

        for device_attr in dev_info["devices"]:
            if device_attr["device_enabled"]:
                if device_attr["is_evse"]:
                    self.devices[device_attr["dev_id"]] = Evse(device_attr, self)
                else:
                    self.devices[device_attr["dev_id"]] = Meter(device_attr, self)

    def update_device_status(self):
        """Update the device status."""
        dev_info = requests.get(self.host + API_GET_DEV_INFO, timeout=5).json()
        for k, device in self.devices.items():
            attr = next((x for x in dev_info["devices"] if x["dev_id"] == k), "")
            device.update_status(attr)

    def enter_rfid(self, rfid, dev=""):
        """Enter RFID or PIN code."""
        dev_id = ""
        if dev != "":
            dev_id = API_DEV_ID + dev
        requests.get(self.host + API_GET_ENTER_RFID + rfid + dev_id, timeout=5)

    def set_variable(self, name, value):
        """Set value of a charging manager variable."""
        requests.get(
            f"{self.host}{API_GET_SET_VAR}{name}{API_VAR_VAL}{value}",
            timeout=5,
            auth=(self.username, self.password),
        )

    def set_params(self, params: dict):
        """Set global Charging Manager parameters via POST.

        Supported keys include: min_pause_time, disable_policy, max_total_current,
        reserve_current, lb_enabled, feed_in_tariff, price_model, surplus_expr, etc.
        """
        response = requests.post(
            self.host + API_SET_PARAMS,
            json=params,
            timeout=5,
            auth=(self.username, self.password),
        )
        response.raise_for_status()

    def get_charging_rules(self, dev_id: str) -> list:
        """Get current charging rules for a device."""
        dev_info = requests.get(self.host + API_GET_DEV_INFO, timeout=5).json()
        device = next(
            (d for d in dev_info["devices"] if d["dev_id"] == dev_id), None
        )
        if device is None:
            raise ValueError(f"Device {dev_id} not found")
        return device.get("charging_rules", [])

    def set_charging_rules(self, dev_id: str, rules: list):
        """Set charging rules for a specific device.

        Each rule is a dict with keys:
            days    (int)   bitfield weekdays: bit0=Mon...bit6=Sun, 127=all days
            mode    (int)   0=absolute current, 1=relative, 2=solar current,
                            3=relative solar, 4=solar minus value, 5=solar surplus
            current (int)   current in mA
            enabled (bool)  True = rule active
            time    (int)   minutes after midnight (for time-based rules)
            dur     (int)   duration in minutes (for time-based rules)
            udur    (int)   undercut duration in seconds
            expr    (str)   expression string (for expression-based rules)
            input   (str)   input string (for input-based rules)
            price_level (int) price level (for cost-based rules)
            solar   (int)   solar current in mA (for solar-based rules)
        """
        payload = {
            "devices": [
                {
                    "dev_id": dev_id,
                    "charging_rules": rules,
                }
            ]
        }
        response = requests.post(
            self.host + API_SET_PARAMS,
            json=payload,
            timeout=5,
            auth=(self.username, self.password),
        )
        response.raise_for_status()


class Device:
    """Device connected via Powerbrain."""

    def __init__(self, attr, brain: Powerbrain):
        """Initialize the device instance."""
        self.name = attr["name"]
        self.dev_id = attr["dev_id"]
        self.attributes = attr
        self.brain = brain

    def update_status(self, attr):
        """Update attributes."""
        self.attributes = attr


class Evse(Device):
    """EVSE device."""

    def override_current_limit(self, value: float):
        """Override max charging current."""
        response = requests.get(
            f"{self.brain.host}{API_OVERRIDE_DEVICE}{self.dev_id}{API_OVERRIDE_FLAG_AMPS}{value}",
            timeout=5,
            auth=(self.brain.username, self.brain.password),
        )
        response.raise_for_status()

    def disable_charging(self, disable: bool):
        """Disable or enable charging."""
        response = requests.get(
            f"{self.brain.host}{API_OVERRIDE_DEVICE}{self.dev_id}{API_OVERRIDE_FLAGS}{'C' if disable else 'c'}",
            timeout=5,
            auth=(self.brain.username, self.brain.password),
        )
        response.raise_for_status()

    def disable_charging_rules(self, disable: bool):
        """Disable or enable evse charging rules."""
        response = requests.get(
            f"{self.brain.host}{API_OVERRIDE_DEVICE}{self.dev_id}{API_OVERRIDE_FLAGS}{'E' if disable else 'e'}",
            timeout=5,
            auth=(self.brain.username, self.brain.password),
        )
        response.raise_for_status()

    def disable_user_rules(self, disable: bool):
        """Disable or enable user charging rules."""
        response = requests.get(
            f"{self.brain.host}{API_OVERRIDE_DEVICE}{self.dev_id}{API_OVERRIDE_FLAGS}{'U' if disable else 'u'}",
            timeout=5,
            auth=(self.brain.username, self.brain.password),
        )
        response.raise_for_status()

    def get_charging_rules(self) -> list:
        """Get current charging rules for this EVSE."""
        return self.brain.get_charging_rules(self.dev_id)

    def set_charging_rules(self, rules: list):
        """Set charging rules for this EVSE. See Powerbrain.set_charging_rules for rule format."""
        self.brain.set_charging_rules(self.dev_id, rules)


class Meter(Device):
    """Energy meter device"""

    def set_value(self, data):
        """send values of httpinput meter"""
        response = requests.post(
            f"{self.brain.host}{API_SET_METER}{API_DEV_ID}{self.dev_id}",
            json=data,
            timeout=5,
            auth=(self.brain.username, self.brain.password),
        )
        response.raise_for_status()
