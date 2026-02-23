# was-ctl

CLI tool for managing Willow Application Server (WAS).

## Usage

```bash
cd ~/workspace/HOME-AI_projects/was-ctl
uv run was-ctl --help            # see all commands
uv run was-ctl status            # server info + devices
uv run was-ctl config show       # current config
uv run was-ctl config set K=V    # set + apply config
uv run was-ctl clients           # list devices
uv run was-ctl client restart    # restart device
```

## Structure

- `src/was_ctl/cli.py` — Click CLI commands
- `src/was_ctl/api.py` — WASClient HTTP wrapper

## WAS API

Talks to WAS at `http://localhost:8502` (override with `--host` or `WAS_CTL_HOST`).

Key endpoints used:
- `GET /api/config?type=config` — get device config
- `POST /api/config?type=config&apply=true` — set + push config
- `GET /api/client` — list connected devices
- `POST /api/client?action=restart|identify` — device commands

## Config Persistence

WAS stores config overrides in SQLite (`storage/was.db`). Device also caches config in SPIFFS flash (`/spiffs/user/config/willow.json`), enabling boot without WAS.

- `config show` merges WAS defaults + overrides to show full effective config
- `config show --overrides-only` shows only explicitly set values
- `config set` always sends full merged overrides to prevent partial-overwrite (WAS broadcasts exactly what you POST, and the device replaces its entire SPIFFS cache with that payload)
- `config diff` compares current overrides against upstream defaults
- NVS (WiFi + WAS URL) is separate from config — only changeable via WAS NVS API or reflashing
