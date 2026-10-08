"""Dependency-free client for Orchid Studio's local control API."""
import http.client
import json

from .sequencer import integer


def request(payload, port=8765):
    integer(port, 1024, 65535, "API port")
    if not isinstance(payload, dict):
        raise ValueError("request must be a JSON object")
    body = json.dumps(payload, allow_nan=False).encode()
    connection = http.client.HTTPConnection("127.0.0.1", port, timeout=10)
    try:
        connection.request("POST", "/command", body, {"Content-Type": "application/json"})
        response = connection.getresponse()
        result = json.loads(response.read())
        if not isinstance(result, dict):
            raise RuntimeError("API returned a non-object response")
        return result
    except (OSError, http.client.HTTPException) as exc:
        raise RuntimeError(f"Cannot reach Orchid Studio API on port {port}: {exc}") from exc
    finally:
        connection.close()
