from __future__ import annotations

import json
import subprocess
import threading
import urllib.request
from typing import Any

MCP_TIMEOUT = 30


class McpError(RuntimeError):
    pass


class McpStdioClient:
    """Minimal MCP client over stdio (JSON-RPC 2.0)."""

    def __init__(self, command: str, args: list[str], timeout: int = MCP_TIMEOUT) -> None:
        self._timeout = timeout
        self._proc = subprocess.Popen(
            [command, *(args or [])],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
        )
        self._id = 0
        self._lock = threading.Lock()
        self._initialized = False

    def _write(self, payload: dict[str, Any]) -> None:
        if not self._proc.stdin:
            raise McpError("MCP stdio process stdin is not available")
        self._proc.stdin.write(json.dumps(payload, ensure_ascii=False) + "\n")
        self._proc.stdin.flush()

    def _read_response(self, expected_id: int) -> Any:
        if not self._proc.stdout:
            raise McpError("MCP stdio process stdout is not available")
        while True:
            line = self._proc.stdout.readline()
            if not line:
                raise McpError("MCP stdio process closed while waiting for response")
            try:
                response = json.loads(line)
            except json.JSONDecodeError:
                continue
            if response.get("id") != expected_id:
                continue
            if response.get("error"):
                raise McpError(str(response["error"]))
            return response.get("result")

    def _request(self, method: str, params: dict[str, Any] | None = None) -> Any:
        with self._lock:
            self._id += 1
            self._write({"jsonrpc": "2.0", "id": self._id, "method": method, "params": params or {}})
            return self._read_response(self._id)

    def _notify(self, method: str, params: dict[str, Any] | None = None) -> None:
        with self._lock:
            self._write({"jsonrpc": "2.0", "method": method, "params": params or {}})

    def _ensure_initialized(self) -> None:
        if self._initialized:
            return
        self._request(
            "initialize",
            {
                "protocolVersion": "2025-06-18",
                "capabilities": {},
                "clientInfo": {"name": "shizukuclaw", "version": "1.0.0"},
            },
        )
        self._notify("notifications/initialized")
        self._initialized = True

    def list_tools(self) -> list[dict[str, Any]]:
        self._ensure_initialized()
        result = self._request("tools/list")
        return list((result or {}).get("tools") or [])

    def call_tool(self, name: str, arguments: dict[str, Any]) -> str:
        self._ensure_initialized()
        result = self._request("tools/call", {"name": name, "arguments": arguments or {}})
        content = (result or {}).get("content") or []
        parts = []
        for item in content:
            if item.get("type") == "text":
                parts.append(str(item.get("text") or ""))
            else:
                parts.append(str(item.get("text") or json.dumps(item, ensure_ascii=False)))
        return "\n".join(parts) or str(result)

    def close(self) -> None:
        try:
            if self._proc.poll() is None:
                self._proc.terminate()
                try:
                    self._proc.wait(timeout=2)
                except subprocess.TimeoutExpired:
                    self._proc.kill()
                    self._proc.wait(timeout=2)
        except Exception:
            pass
        for stream in (self._proc.stdin, self._proc.stdout, self._proc.stderr):
            if stream is not None:
                try:
                    stream.close()
                except Exception:
                    pass

    def __del__(self) -> None:
        try:
            self.close()
        except Exception:
            pass


def _parse_mcp_http_response(body: str) -> dict[str, Any]:
    text = body.strip()
    if not text:
        return {}
    if text.startswith("{"):
        return json.loads(text)
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("data:"):
            data = stripped[5:].strip()
            if data.startswith("{"):
                return json.loads(data)
    return {}


class McpHttpClient:
    """Minimal MCP client over streamable HTTP (JSON-RPC)."""

    def __init__(self, url: str, headers: dict[str, str] | None = None, timeout: int = MCP_TIMEOUT) -> None:
        self._url = url
        self._headers = {
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
            **dict(headers or {}),
        }
        self._timeout = timeout
        self._id = 0
        self._lock = threading.Lock()
        self._session_id: str | None = None
        self._initialized = False

    def _post(self, payload: dict[str, Any]) -> dict[str, Any]:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        headers = dict(self._headers)
        if self._session_id:
            headers["Mcp-Session-Id"] = self._session_id
        request = urllib.request.Request(self._url, data=data, headers=headers, method="POST")
        with urllib.request.urlopen(request, timeout=self._timeout) as response:
            session_id = response.headers.get("Mcp-Session-Id")
            if session_id:
                self._session_id = session_id
            body = response.read().decode("utf-8", errors="replace")
        return _parse_mcp_http_response(body)

    def _request(self, method: str, params: dict[str, Any] | None = None) -> Any:
        with self._lock:
            self._id += 1
            response = self._post(
                {"jsonrpc": "2.0", "id": self._id, "method": method, "params": params or {}}
            )
        if response.get("error"):
            raise McpError(str(response["error"]))
        return response.get("result")

    def _ensure_initialized(self) -> None:
        if self._initialized:
            return
        self._request(
            "initialize",
            {
                "protocolVersion": "2025-06-18",
                "capabilities": {},
                "clientInfo": {"name": "shizukuclaw", "version": "1.0.0"},
            },
        )
        self._initialized = True

    def list_tools(self) -> list[dict[str, Any]]:
        self._ensure_initialized()
        result = self._request("tools/list")
        return list((result or {}).get("tools") or [])

    def call_tool(self, name: str, arguments: dict[str, Any]) -> str:
        self._ensure_initialized()
        result = self._request("tools/call", {"name": name, "arguments": arguments or {}})
        content = (result or {}).get("content") or []
        parts = []
        for item in content:
            if item.get("type") == "text":
                parts.append(str(item.get("text") or ""))
            else:
                parts.append(str(item.get("text") or json.dumps(item, ensure_ascii=False)))
        return "\n".join(parts) or str(result)


def build_mcp_clients(servers: list[dict[str, Any]]) -> dict[str, Any]:
    clients: dict[str, Any] = {}
    for server in servers:
        if not server.get("enabled"):
            continue
        server_type = str(server.get("type") or "")
        server_id = str(server.get("id") or "")
        if server_type == "stdio" and server.get("command"):
            clients[server_id] = McpStdioClient(str(server["command"]), list(server.get("args") or []))
        elif server_type == "http" and server.get("url"):
            clients[server_id] = McpHttpClient(str(server["url"]), dict(server.get("headers") or {}))
    return clients