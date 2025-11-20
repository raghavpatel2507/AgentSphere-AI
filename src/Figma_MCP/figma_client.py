import json
import requests


class FigmaMCPClient:
    BASE_URL = "https://mcp.figma.com/mcp"

    def call_tool(self, tool_name: str, params: dict):
        """
        Calls a Figma MCP remote tool.
        """
        payload = {
            "tool": tool_name,
            "params": params
        }

        try:
            response = requests.post(self.BASE_URL, json=payload)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            return {"error": str(e)}
