"""Select platform for cFos Powerbrain — phase mode selection."""
from typing import Any

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import callback
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .__init__ import get_entity_deviceinfo
from .__init__ import PowerbrainUpdateCoordinator
from .const import DOMAIN
from .powerbrain import Evse
from .powerbrain import Powerbrain

PHASE_OPTIONS = ["1 phase", "3 phases"]
PHASE_TO_INT = {"1 phase": 1, "3 phases": 3}
# used_phases bitfield: 1 = L1 only, 7 = L1+L2+L3; 0 = auto-detect
PHASE_BITS_TO_OPTION = {
    0: "3 phases",  # auto / 3-phase default
    1: "1 phase",
    7: "3 phases",
}


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Create the select entities for powerbrain integration."""
    brain: Powerbrain = hass.data[DOMAIN][entry.entry_id]

    entities = []
    for device in brain.devices.values():
        if device.attributes["is_evse"]:
            entities.append(
                EvsePhaseSelectEntity(
                    hass.data[DOMAIN][entry.entry_id + "_coordinator"],
                    device,
                    "Phase Mode",
                )
            )
    async_add_entities(entities)


class EvsePhaseSelectEntity(CoordinatorEntity, SelectEntity):
    """Select entity for EVSE phase mode (1-phase / 3-phase)."""

    def __init__(
        self,
        coordinator: PowerbrainUpdateCoordinator,
        device: Evse,
        name: str,
    ) -> None:
        """Initialize phase select entity."""
        super().__init__(coordinator)
        self.device = device
        self._attr_has_entity_name = True
        self._attr_unique_id = (
            f"{coordinator.brain.attributes['vsn']['serialno']}"
            f"_{self.device.dev_id}_{name}"
        )
        self._attr_name = name
        self._attr_options = PHASE_OPTIONS
        self._attr_icon = "mdi:sine-wave"

    @callback
    def _handle_coordinator_update(self) -> None:
        bits = self.device.attributes.get("phases", 0)
        self._attr_current_option = PHASE_BITS_TO_OPTION.get(bits, "3 phases")
        self.async_write_ha_state()

    async def async_select_option(self, option: str) -> None:
        """Change phase mode."""
        phases = PHASE_TO_INT.get(option, 3)
        await self.hass.async_add_executor_job(self.device.set_phase_mode, phases)
        await self.coordinator.async_request_refresh()

    @property
    def device_info(self) -> DeviceInfo:
        """Information of the parent device."""
        return get_entity_deviceinfo(self.device)
