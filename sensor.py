"""Platform for sensor integration."""

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity, SensorStateClass

from homeassistant.const import (
    UnitOfTemperature,
    UnitOfTime,
    SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
)

from .const import DOMAIN
import logging

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass, config_entry, async_add_entities):
  """Add sensors for passed config_entry in HA."""
  hub = hass.data[DOMAIN][config_entry.entry_id]

  new_devices = []
  for appliance in hub.appliances:
    try:
      await appliance.wait_for_state()
    except Exception:
      _LOGGER.warning("Skipping appliance %s — state not ready", appliance.appliance_id)
      continue
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

class SensorBase(SensorEntity):
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


class GenericSensor(SensorBase):
  """Sensor that reads a single key from appliance state, with dot-notation nested access."""

  def __init__(self, appliance, state_key, name_suffix, unique_id_suffix,
               device_class, native_unit, state_class):
    super().__init__(appliance)
    self._state_key = state_key
    self._attr_unique_id = f"{appliance.appliance_id}_{unique_id_suffix}"
    self._attr_name = f"{appliance.name} {name_suffix}"
    self._attr_device_class = device_class
    self._attr_native_unit_of_measurement = native_unit
    self._attr_state_class = state_class

  @property
  def native_value(self):
    value = self._appliance._states
    for part in self._state_key.split('.'):
      if not isinstance(value, dict):
        return None
      value = value.get(part)
      if value is None:
        return None
    return value


class TemperatureSensor(SensorBase):
  """Representation of a Sensor."""

  device_class = SensorDeviceClass.TEMPERATURE
  state_class = SensorStateClass.MEASUREMENT

  def __init__(self, appliance):
    """Initialize the sensor."""
    super().__init__(appliance)

    self._attr_unique_id = f"{self._appliance.appliance_id}_temperature"
    self._attr_name = f"{self._appliance.name} Temperature"

    _LOGGER.warning("Creating temperature sensor with presentation: %s",
                    self._appliance._states.get('temperatureRepresentation'))
    if self._appliance._states.get('temperatureRepresentation') == 'celsius':
      self._attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS
    else:
      self._attr_native_unit_of_measurement = UnitOfTemperature.FAHRENHEIT

  @property
  def native_value(self):
    """Return the state of the sensor."""
    if self._attr_native_unit_of_measurement == UnitOfTemperature.CELSIUS:
      temperature = self._appliance._states.get('ambientTemperatureC')
    else:
      temperature = self._appliance._states.get('ambientTemperatureF')
    _LOGGER.debug("Returning temperature: %s", temperature)
    return temperature
