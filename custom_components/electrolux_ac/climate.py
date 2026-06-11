"""Platform for sensor integration."""
from __future__ import annotations

from homeassistant.components.climate import (
  FAN_AUTO,
  FAN_HIGH,
  FAN_LOW,
  FAN_MEDIUM,
  PRESET_NONE,
  PRESET_SLEEP,
  SWING_OFF,
  SWING_VERTICAL,
  ClimateEntity,
  ClimateEntityFeature,
  HVACMode,
)

from homeassistant.const import ATTR_TEMPERATURE, PRECISION_WHOLE, UnitOfTemperature

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.device_registry import DeviceInfo

from .const import (
  DOMAIN,
  TARGET_TEMPERATURE_STEP
)

import logging

SWING_MODES = [SWING_OFF, SWING_VERTICAL]

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(
  hass: HomeAssistant,
  config_entry: ConfigEntry,
  async_add_entities: AddEntitiesCallback,
) -> None:
  hub = hass.data[DOMAIN][config_entry.entry_id]

  new_devices = []
  for appliance in hub.appliances:
    try:
      await appliance.wait_for_state()
    except Exception:
      _LOGGER.warning("Skipping appliance %s — state not ready", appliance.appliance_id)
      continue
    if appliance.appliance_info.get("deviceType") == "PORTABLE_AIR_CONDITIONER":
      new_devices.append(ElectroluxClimate(appliance))
  if new_devices:
    async_add_entities(new_devices)

class ElectroluxClimate(ClimateEntity):
  _attr_should_poll = False

  _attr_precision = PRECISION_WHOLE
  _attr_supported_features = (
    ClimateEntityFeature.TARGET_TEMPERATURE
    | ClimateEntityFeature.FAN_MODE
    | ClimateEntityFeature.SWING_MODE
    | ClimateEntityFeature.PRESET_MODE
    | ClimateEntityFeature.TURN_ON
    | ClimateEntityFeature.TURN_OFF
  )
  _attr_preset_modes = [PRESET_NONE, PRESET_SLEEP]
  _attr_target_temperature_step = TARGET_TEMPERATURE_STEP
  _attr_hvac_modes = [HVACMode.OFF, HVACMode.COOL, HVACMode.DRY, HVACMode.FAN_ONLY]
  _attr_fan_modes = [FAN_AUTO, FAN_LOW, FAN_MEDIUM, FAN_HIGH]
  _attr_swing_modes = SWING_MODES
  _attr_name = None
  _enable_turn_on_off_backwards_compatibility = False

  def __init__(self, appliance) -> None:
    """Initialize the sensor."""
    self._appliance = appliance

    self._attr_unique_id = f"{self._appliance.appliance_id}"

    self._attr_name = self._appliance.name

    if self._appliance._states.get('temperatureRepresentation') == 'fahrenheit':
      self._attr_unit_of_measurement = UnitOfTemperature.FAHRENHEIT
    else:
      self._attr_unit_of_measurement = UnitOfTemperature.CELSIUS

  async def async_added_to_hass(self) -> None:
    """Run when this Entity has been added to HA."""
    self._appliance.register_callback(self.async_write_ha_state)

  async def async_will_remove_from_hass(self) -> None:
    """Entity being removed from hass."""
    self._appliance.remove_callback(self.async_write_ha_state)

  @property
  def device_info(self) -> DeviceInfo:
    """Information about this entity/device."""
    model = self._appliance.appliance_info.get('model')
    brand = self._appliance.appliance_info.get('brand')
    return DeviceInfo(
      identifiers={
        (DOMAIN, self._appliance.appliance_id)
      },
      name=self.name,
      model=model.capitalize() if model else None,
      manufacturer=brand.capitalize() if brand else None,
    )

  @property
  def available(self) -> bool:
    """Return True if appliance and hub is available."""
    return self._appliance.online and self._appliance.hub.online

  @property
  def current_temperature(self):
    if self._attr_unit_of_measurement == UnitOfTemperature.CELSIUS:
      temperature = self._appliance._states.get('ambientTemperatureC')
    else: 
      temperature = self._appliance._states.get('ambientTemperatureF')
    return temperature

  @property
  def fan_mode(self) -> str | None:
    if self._appliance._states.get('fanSpeedSetting') == 'auto':
      return FAN_AUTO
    elif self._appliance._states.get('fanSpeedSetting') == 'low':
      return FAN_LOW
    elif self._appliance._states.get('fanSpeedSetting') == 'middle':
      return FAN_MEDIUM
    elif self._appliance._states.get('fanSpeedSetting') == 'high':
      return FAN_HIGH
    else:
      return None

  @property
  def fan_modes(self) -> list[str] | None:
    return self._attr_fan_modes

  @property
  def hvac_mode(self) -> HVACMode | None:
    if self._appliance._states.get('applianceState') == 'off':
      return HVACMode.OFF
    if self._appliance._states.get('mode') == 'cool':
      return HVACMode.COOL
    elif self._appliance._states.get('mode') == 'dry':
      return HVACMode.DRY
    elif self._appliance._states.get('mode') == 'fanOnly':
      return HVACMode.FAN_ONLY
    else:
      return HVACMode.OFF

  @property
  def hvac_modes(self) -> list[HVACMode]:
    return self._attr_hvac_modes

  @property
  def min_temp(self) -> float:
    return self._appliance.capabilities.get("targetTemperatureC", {}).get("min", 16)

  @property
  def max_temp(self) -> float:
    return self._appliance.capabilities.get("targetTemperatureC", {}).get("max", 32)

  @property
  def target_temperature(self) -> float | None:
    if self._attr_unit_of_measurement == UnitOfTemperature.FAHRENHEIT:
      return self._appliance._states.get('targetTemperatureF')
    else:
      return self._appliance._states.get('targetTemperatureC')

  @property
  def swing_mode(self) -> str | None:
    if self._appliance._states.get('verticalSwing') == 'off':
      return SWING_OFF
    elif self._appliance._states.get('verticalSwing') == 'on':
      return SWING_VERTICAL
    else:
      return None

  @property
  def swing_modes(self) -> list[str] | None:
    return self._attr_swing_modes

  @property
  def temperature_unit(self) -> str:
    if self._attr_unit_of_measurement == UnitOfTemperature.FAHRENHEIT:
      return UnitOfTemperature.FAHRENHEIT
    else:
      return UnitOfTemperature.CELSIUS

  @property
  def preset_mode(self) -> str:
    if self._appliance._states.get('sleepMode') == 'on':
      return PRESET_SLEEP
    return PRESET_NONE

  async def async_set_preset_mode(self, preset_mode: str) -> None:
    """Set sleep mode on or off."""
    value = "on" if preset_mode == PRESET_SLEEP else "off"
    await self._appliance.execute_command("sleepMode", value)
    self.async_write_ha_state()

  async def async_set_hvac_mode(self, hvac_mode):
    """Set new target hvac mode."""
    _LOGGER.debug(
        "Setting HVAC mode to %s for device %s",
        hvac_mode,
        self._attr_name,
    )
    if hvac_mode == HVACMode.OFF:
      await self.async_turn_off()
      return
    await self.async_turn_on()
    if hvac_mode == HVACMode.FAN_ONLY:
      await self._appliance.execute_command("mode", "fanOnly")
    else:
      await self._appliance.execute_command("mode", hvac_mode)
    self.async_write_ha_state()

  async def async_turn_on(self):
    _LOGGER.debug(
        "Turning on device %s",
        self._attr_name,
    )
    """Turn the entity on."""
    await self._appliance.execute_command("executeCommand", "ON")
    self.async_write_ha_state()

  async def async_turn_off(self):
    """Turn the entity off."""
    _LOGGER.debug(
        "Turning off device %s",
        self._attr_name,
    )
    await self._appliance.execute_command("executeCommand", "OFF")
    self.async_write_ha_state()

  async def async_set_swing_mode(self, swing_mode):
    """Set new target swing operation."""
    _LOGGER.debug(
        "Setting SWING mode to %s for device %s",
        swing_mode,
        self._attr_name,
    )
    if swing_mode == SWING_OFF:
      await self._appliance.execute_command("verticalSwing", "off")
    elif swing_mode == SWING_VERTICAL:
      await self._appliance.execute_command("verticalSwing", "on")
    self.async_write_ha_state()

  async def async_set_fan_mode(self, fan_mode):
    """Set new target fan mode."""
    _LOGGER.debug(
        "Setting fan mode to %s for device %s",
        fan_mode,
        self._attr_name,
    )
    if fan_mode == FAN_AUTO:
      await self._appliance.execute_command("fanSpeedSetting", "auto")
    elif fan_mode == FAN_LOW:
      await self._appliance.execute_command("fanSpeedSetting", "low")
    elif fan_mode == FAN_MEDIUM:
      await self._appliance.execute_command("fanSpeedSetting", "middle")
    elif fan_mode == FAN_HIGH:
      await self._appliance.execute_command("fanSpeedSetting", "high")
    self.async_write_ha_state()

  async def async_set_temperature(self, **kwargs):
    """Set new target temperature."""
    temperature = kwargs.get(ATTR_TEMPERATURE)
    if temperature is None:
      return
    temperature = int(temperature)
    _LOGGER.debug(
        "Setting target temperature to %s for device %s",
        temperature,
        self._attr_name,
    )
    if self._attr_unit_of_measurement == UnitOfTemperature.FAHRENHEIT:
      await self._appliance.execute_command("targetTemperatureF", temperature)
    else:
      await self._appliance.execute_command("targetTemperatureC", temperature)
    self.async_write_ha_state()
