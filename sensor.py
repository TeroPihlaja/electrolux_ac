"""Platform for sensor integration."""

from homeassistant.components.sensor import SensorDeviceClass

from homeassistant.const import (
    UnitOfTemperature
)
from homeassistant.helpers.entity import Entity

from .const import DOMAIN
import logging
import asyncio

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass, config_entry, async_add_entities):
  """Add sensors for passed config_entry in HA."""
  hub = hass.data[DOMAIN][config_entry.entry_id]

  new_devices = []
  for appliance in hub.appliances:
    status_ready = asyncio.Event()
    asyncio.create_task(appliance.wait_for_state(status_ready))
    await status_ready.wait()
    new_devices.append(TemperatureSensor(appliance))
  if new_devices:
    async_add_entities(new_devices)

# TODO: Add more sensors
# startTime
# stopTime
# sleepMode
# uiLockMode
# filterState
# VmNo_MCU
# dataModelVersion
# VmNo_NIU
# compressorState
# totalRuntime
# compressorCoolingRuntime
# compressorHeatingRuntime
# filterRuntime
# networkInterface.linkQualityIndicator
# networkInterface.rssi
# fourWayValveState
# evapDefrostState

class SensorBase(Entity):
  """Base representation of a Hello World Sensor."""

  should_poll = False

  def __init__(self, appliance):
    """Initialize the sensor."""
    self._appliance = appliance

  @property
  def device_info(self):
    """Return information to link this entity with the correct device."""
    return {"identifiers": {(DOMAIN, self._appliance.appliance_id)}}

  @property
  def available(self) -> bool:
    """Return True if appliance and hub is available."""
    return self._appliance.online and self._appliance.hub.online

  async def async_added_to_hass(self):
    """Run when this Entity has been added to HA."""
    self._appliance.register_callback(self.async_write_ha_state)

  async def async_will_remove_from_hass(self):
    """Entity being removed from hass."""
    self._appliance.remove_callback(self.async_write_ha_state)


class TemperatureSensor(SensorBase):
  """Representation of a Sensor."""

  device_class = SensorDeviceClass.TEMPERATURE

  def __init__(self, appliance):
    """Initialize the sensor."""
    super().__init__(appliance)

    self._attr_unique_id = f"{self._appliance.appliance_id}_temperature"

    # The name of the entity
    self._attr_name = f"{self._appliance.name} Temperature"

    _LOGGER.warn(f"Creating temperature sensor with presentation: {self._appliance._states.get('temperatureRepresentation')}")
    if self._appliance._states.get('temperatureRepresentation') == 'celsius':
      self._attr_unit_of_measurement = UnitOfTemperature.CELSIUS
    else:
      self._attr_unit_of_measurement = UnitOfTemperature.FAHRENHEIT

  @property
  def state(self):
    """Return the state of the sensor."""
    if self._attr_unit_of_measurement == UnitOfTemperature.CELSIUS:
      temperature = self._appliance._states.get('ambientTemperatureC')
    else: 
      temperature = self._appliance._states.get('ambientTemperatureF')

    _LOGGER.debug(f"Returning temperature: {temperature}")

    return temperature
