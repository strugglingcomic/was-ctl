"""HTTP client for the Willow Application Server (WAS) REST API."""

import httpx


class WASClient:
    """Thin wrapper around the WAS REST API at /api/*."""

    def __init__(self, base_url: str = "http://localhost:8502"):
        self.base_url = base_url.rstrip("/")
        self._http = httpx.Client(base_url=self.base_url, timeout=10)

    # -- config ---------------------------------------------------------------

    def get_config(self, default: bool = False) -> dict:
        params: dict = {"type": "config"}
        if default:
            params["default"] = "true"
        return self._http.get("/api/config", params=params).raise_for_status().json()

    def set_config(self, data: dict, apply: bool = True) -> str:
        params = {"type": "config", "apply": str(apply).lower()}
        resp = self._http.post("/api/config", params=params, json=data)
        resp.raise_for_status()
        return resp.text

    # -- clients --------------------------------------------------------------

    def get_clients(self) -> list[dict]:
        return self._http.get("/api/client").raise_for_status().json()

    def client_action(self, action: str, data: dict) -> str:
        resp = self._http.post("/api/client", params={"action": action}, json=data)
        resp.raise_for_status()
        return resp.text

    # -- server info ----------------------------------------------------------

    def get_info(self) -> dict:
        return self._http.get("/api/info").raise_for_status().json()

    def get_status(self, status_type: str) -> dict | list:
        return (
            self._http.get("/api/status", params={"type": status_type})
            .raise_for_status()
            .json()
        )
