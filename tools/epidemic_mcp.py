"""Local client for Epidemic Sound's authenticated Streamable HTTP MCP API."""
import json
import os
from pathlib import Path
import urllib.error
import urllib.request

ENDPOINT = "https://www.epidemicsound.com/a/mcp-service/mcp"
ROOT = Path(__file__).resolve().parents[1]


def credential():
    names = ("EPIDEMICSOUND_API_KEY", "EPIDEMIC_SOUND_API_KEY")
    for name in names:
        if os.environ.get(name):
            return os.environ[name]
    path = ROOT / ".env"
    if path.is_file():
        for line in path.read_text(encoding="utf-8-sig").splitlines():
            name, separator, value = line.strip().removeprefix("export ").partition("=")
            if separator and name.strip() in names:
                value = value.strip()
                if value.startswith(("'", '"')) and value.endswith(value[0]):
                    value = value[1:-1]
                else:
                    value = value.split(" #", 1)[0].strip()
                if value:
                    return value
    raise ValueError("Set EPIDEMICSOUND_API_KEY in the environment or ignored .env")


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, request, file, code, message, headers, url):
        # Never forward account credentials to a redirect destination.
        return None


def response_message(response, request_id):
    if response.headers.get("Content-Type", "").startswith("text/event-stream"):
        lines = []
        for _ in range(10000):
            raw = response.readline(1024 * 1024)
            if not raw:
                break
            line = raw.decode("utf-8").rstrip("\r\n")
            if line.startswith("data:"):
                lines.append(line[5:].lstrip())
            elif not line and lines:
                payload = "\n".join(lines)
                lines = []
                if not payload.strip():
                    continue
                message = json.loads(payload)
                if message.get("id") == request_id:
                    return message
        raise ValueError("MCP stream ended without a matching response")
    data = response.read(16 * 1024 * 1024)
    message = json.loads(data)
    if message.get("id") != request_id:
        raise ValueError("MCP response ID did not match the request")
    return message


class EpidemicMCP:
    def __init__(self, key=None):
        self.key = key or credential()
        self.session = None
        self.protocol = None
        self.sequence = 0
        self.opener = urllib.request.build_opener(NoRedirect())

    def request(self, method, params=None, notification=False):
        self.sequence += 1
        message = {"jsonrpc": "2.0", "method": method}
        if params is not None:
            message["params"] = params
        if not notification:
            message["id"] = self.sequence
        headers = {"Authorization": "Bearer " + self.key,
                   "Content-Type": "application/json",
                   "Accept": "application/json, text/event-stream"}
        if self.session:
            headers["Mcp-Session-Id"] = self.session
        if self.protocol:
            headers["MCP-Protocol-Version"] = self.protocol
        request = urllib.request.Request(ENDPOINT, json.dumps(message).encode(), headers)
        try:
            with self.opener.open(request, timeout=60) as response:
                self.session = response.headers.get("Mcp-Session-Id", self.session)
                if notification:
                    return None
                result = response_message(response, self.sequence)
        except urllib.error.HTTPError as error:
            raise ValueError(f"Epidemic MCP HTTP {error.code}; check account access, key or rate limits") from None
        except urllib.error.URLError:
            raise ValueError("Cannot connect to the Epidemic MCP service") from None
        if "error" in result:
            # Do not echo server messages that might contain credentials or URLs.
            raise ValueError(f"Epidemic MCP RPC error {result['error'].get('code')}")
        return result["result"]

    def connect(self):
        result = self.request("initialize", {"protocolVersion": "2025-06-18", "capabilities": {},
                              "clientInfo": {"name": "kylr-asset-setup", "version": "0.1"}})
        self.protocol = result["protocolVersion"]
        self.request("notifications/initialized", notification=True)
        self.tools = {}
        cursor = None
        while True:
            result = self.request("tools/list", {"cursor": cursor} if cursor else {})
            self.tools.update({tool["name"]: tool for tool in result["tools"]})
            cursor = result.get("nextCursor")
            if not cursor:
                break
        return self

    def call(self, name, arguments):
        if name not in self.tools:
            raise ValueError(f"MCP tool unavailable: {name}")
        result = self.request("tools/call", {"name": name, "arguments": arguments})
        if result.get("isError"):
            raise ValueError(f"Epidemic tool {name} rejected the request")
        return result


if __name__ == "__main__":
    try:
        client = EpidemicMCP().connect()
        for name, tool in client.tools.items():
            if "SoundEffect" in name or "Recording" in name:
                print(name, json.dumps(tool.get("inputSchema", {})))
    except (ValueError, OSError) as error:
        raise SystemExit(str(error))
