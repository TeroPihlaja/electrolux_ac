import pytest
from homeassistant.components.sensor import SensorDeviceClass, SensorStateClass
from custom_components.electrolux_ac.sensor import GenericSensor


def test_simple_key(mock_appliance):
    mock_appliance._states = {"filterState": "clean"}
    sensor = GenericSensor(
        mock_appliance, "filterState", "Filter State", "filter_state",
        None, None, None,
    )
    assert sensor.native_value == "clean"


def test_nested_key(mock_appliance):
    mock_appliance._states = {"networkInterface": {"rssi": -40}}
    sensor = GenericSensor(
        mock_appliance, "networkInterface.rssi", "WiFi Signal", "rssi",
        SensorDeviceClass.SIGNAL_STRENGTH, "dBm", None,
    )
    assert sensor.native_value == -40


def test_missing_top_level_key_returns_none(mock_appliance):
    mock_appliance._states = {}
    sensor = GenericSensor(
        mock_appliance, "filterState", "Filter State", "filter_state",
        None, None, None,
    )
    assert sensor.native_value is None


def test_missing_nested_key_returns_none(mock_appliance):
    mock_appliance._states = {"networkInterface": {}}
    sensor = GenericSensor(
        mock_appliance, "networkInterface.rssi", "WiFi Signal", "rssi",
        SensorDeviceClass.SIGNAL_STRENGTH, "dBm", None,
    )
    assert sensor.native_value is None


def test_attributes_set_correctly(mock_appliance):
    sensor = GenericSensor(
        mock_appliance, "filterRuntime", "Filter Runtime", "filter_runtime",
        SensorDeviceClass.DURATION, "s", SensorStateClass.TOTAL_INCREASING,
    )
    assert sensor.device_class == SensorDeviceClass.DURATION
    assert sensor.native_unit_of_measurement == "s"
    assert sensor.state_class == SensorStateClass.TOTAL_INCREASING
    assert sensor.unique_id == "test_appliance_id_filter_runtime"
    assert sensor.name == "Test AC Filter Runtime"
