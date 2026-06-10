from unittest.mock import AsyncMock, MagicMock
import pytest


@pytest.fixture
def mock_appliance():
    appliance = MagicMock()
    appliance.appliance_id = "test_appliance_id"
    appliance.name = "Test AC"
    appliance.online = True
    appliance.hub = MagicMock()
    appliance.hub.online = True
    appliance._states = {}
    appliance.capabilities = {}
    appliance.execute_command = AsyncMock()
    appliance.register_callback = MagicMock()
    appliance.remove_callback = MagicMock()
    return appliance
