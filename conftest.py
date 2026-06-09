import sys
import types
from pathlib import Path

# Set up custom_components namespace BEFORE importing pytest plugin
if "custom_components" not in sys.modules:
    cc = types.ModuleType("custom_components")
    cc.__path__ = [str(Path(__file__).parent.parent)]
    sys.modules["custom_components"] = cc

# Also pre-create the electrolux_ac module stub so it doesn't get auto-imported
if "custom_components.electrolux_ac" not in sys.modules:
    electrolux_ac = types.ModuleType("electrolux_ac")
    electrolux_ac.__path__ = [str(Path(__file__).parent)]
    sys.modules["custom_components.electrolux_ac"] = electrolux_ac

pytest_plugins = "pytest_homeassistant_custom_component"
