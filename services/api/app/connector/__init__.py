"""Desktop connector: pairing, hub, action-script execution."""

from app.connector.executor import build_steps, execute_connector_tool
from app.connector.hub import ConnectorHub, hub

__all__ = ["ConnectorHub", "build_steps", "execute_connector_tool", "hub"]
