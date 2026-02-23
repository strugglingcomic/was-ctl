"""was-ctl — CLI for Willow Application Server management."""

import json
import subprocess
import sys

import click
import httpx

from was_ctl import __version__
from was_ctl.api import WASClient

HELP_TEXT = """\
CLI for managing Willow Application Server (WAS).

WAS is the server component of the Willow voice assistant ecosystem.  It stores
device configuration, routes voice commands to endpoints (Home Assistant, REST,
MQTT, etc.), and manages OTA updates for ESP32-S3-BOX-3 devices.

\b
Connection:
  Connects to WAS at http://localhost:8502 by default.
  Override with --host or the WAS_CTL_HOST environment variable.

\b
Quick start:
  was-ctl status                          # server info + connected devices
  was-ctl config show                     # view current device configuration
  was-ctl config set speaker_volume=100   # change a setting (applied immediately)
  was-ctl clients                         # list connected Willow devices
  was-ctl client restart                  # restart a device
"""


@click.group(help=HELP_TEXT)
@click.version_option(__version__, prog_name="was-ctl")
@click.option(
    "--host",
    envvar="WAS_CTL_HOST",
    default="http://localhost:8502",
    show_default=True,
    help="WAS server URL.",
)
@click.pass_context
def cli(ctx: click.Context, host: str) -> None:
    ctx.ensure_object(dict)
    ctx.obj["client"] = WASClient(host)


# ---------------------------------------------------------------------------
# config
# ---------------------------------------------------------------------------


@cli.group(help="View and modify device configuration stored in WAS.")
def config() -> None:
    pass


@config.command(
    "show",
    help="Display the effective device configuration.\n\n"
    "Merges WAS defaults with any overrides you've set, showing the full\n"
    "config the device actually uses.  Use --key to retrieve a single value\n"
    "or --overrides-only to see just the explicitly changed values.",
)
@click.option("--key", "-k", default=None, help="Show only this config key.")
@click.option(
    "--overrides-only",
    is_flag=True,
    default=False,
    help="Show only explicitly set overrides (skip defaults).",
)
@click.pass_context
def config_show(ctx: click.Context, key: str | None, overrides_only: bool) -> None:
    client: WASClient = ctx.obj["client"]
    try:
        overrides = client.get_config()
        if overrides_only:
            data = overrides
        else:
            defaults = client.get_config(default=True)
            data = {**defaults, **overrides}
    except httpx.ConnectError:
        _die("Cannot connect to WAS. Is it running?")

    if key:
        if key not in data:
            _die(f"Key {key!r} not found in config.")
        click.echo(f"{key}: {json.dumps(data[key])}")
    else:
        click.echo(json.dumps(data, indent=2))


@config.command(
    "set",
    help="Set one or more config values and push to the device.\n\n"
    "Values are auto-coerced: true/false become booleans, numeric strings\n"
    "become integers, everything else stays a string.\n\n"
    '\b\nExamples:\n  was-ctl config set speaker_volume=100\n  was-ctl config set was_mode=true command_endpoint=REST\n  was-ctl config set --no-apply display_timeout=30',
)
@click.argument("pairs", nargs=-1, required=True)
@click.option(
    "--no-apply",
    is_flag=True,
    default=False,
    help="Save to WAS database only; don't push to device.",
)
@click.pass_context
def config_set(ctx: click.Context, pairs: tuple[str, ...], no_apply: bool) -> None:
    client: WASClient = ctx.obj["client"]
    data: dict = {}
    for pair in pairs:
        if "=" not in pair:
            _die(f"Invalid format: {pair!r}. Expected KEY=VALUE.")
        k, v = pair.split("=", 1)
        data[k] = _coerce(v)

    try:
        if no_apply:
            # DB-only: just send the new values
            client.set_config(data, apply=False)
        else:
            # Merge new values into existing overrides so the device gets
            # the full config (WAS broadcasts exactly what we POST, and the
            # device overwrites its SPIFFS cache with that payload).
            existing = client.get_config()
            merged = {**existing, **data}
            client.set_config(merged, apply=True)
    except httpx.ConnectError:
        _die("Cannot connect to WAS. Is it running?")

    action = "Saved" if no_apply else "Applied"
    for k, v in data.items():
        click.echo(f"  {k} = {json.dumps(v)}")
    click.echo(f"{action} {len(data)} setting(s).")


@config.command(
    "diff",
    help="Show differences between current config and defaults.\n\n"
    "Fetches the default config from the Willow servers and compares\n"
    "it against the current WAS config.  Only changed keys are shown.",
)
@click.pass_context
def config_diff(ctx: click.Context) -> None:
    client: WASClient = ctx.obj["client"]
    try:
        current = client.get_config()
        default = client.get_config(default=True)
    except httpx.ConnectError:
        _die("Cannot connect to WAS. Is it running?")

    diffs = []
    all_keys = sorted(set(current) | set(default))
    for k in all_keys:
        cur = current.get(k)
        dflt = default.get(k)
        if cur != dflt:
            diffs.append((k, dflt, cur))

    if not diffs:
        click.echo("No differences — config matches defaults.")
        return

    click.echo(f"{'Key':<30} {'Default':<25} {'Current':<25}")
    click.echo("-" * 80)
    for k, dflt, cur in diffs:
        click.echo(f"{k:<30} {_fmt(dflt):<25} {_fmt(cur):<25}")


# ---------------------------------------------------------------------------
# clients / client
# ---------------------------------------------------------------------------


@cli.command("clients", help="List connected Willow devices.")
@click.pass_context
def clients(ctx: click.Context) -> None:
    client: WASClient = ctx.obj["client"]
    try:
        devices = client.get_clients()
    except httpx.ConnectError:
        _die("Cannot connect to WAS. Is it running?")

    if not devices:
        click.echo("No devices connected.")
        return

    for d in devices:
        label = f" ({d['label']})" if d.get("label") else ""
        click.echo(
            f"  {d['hostname']}{label}  "
            f"{d.get('platform', '?')}  "
            f"{d.get('ip', '?')}  "
            f"v{d.get('version', '?')}"
        )
    click.echo(f"\n{len(devices)} device(s) connected.")


@cli.group(
    "client",
    help="Send commands to a connected Willow device.\n\n"
    "If only one device is connected, --hostname is optional.",
)
def client_group() -> None:
    pass


@client_group.command(
    "restart",
    help="Restart a Willow device.\n\nThe device will reboot and reconnect to WAS.",
)
@click.option("--hostname", "-h", default=None, help="Target device hostname.")
@click.pass_context
def client_restart(ctx: click.Context, hostname: str | None) -> None:
    client: WASClient = ctx.obj["client"]
    hostname = _resolve_hostname(client, hostname)
    client.client_action("restart", {"hostname": hostname})
    click.echo(f"Restart sent to {hostname}.")


@client_group.command(
    "identify",
    help="Play an identification sound on a device.\n\n"
    "Useful for figuring out which physical device has a given hostname.",
)
@click.option("--hostname", "-h", default=None, help="Target device hostname.")
@click.pass_context
def client_identify(ctx: click.Context, hostname: str | None) -> None:
    client: WASClient = ctx.obj["client"]
    hostname = _resolve_hostname(client, hostname)
    client.client_action("identify", {"hostname": hostname})
    click.echo(f"Identify sent to {hostname}.")


# ---------------------------------------------------------------------------
# status / logs
# ---------------------------------------------------------------------------


@cli.command("status", help="Show WAS server info and connected device summary.")
@click.pass_context
def status(ctx: click.Context) -> None:
    client: WASClient = ctx.obj["client"]
    try:
        devices = client.get_clients()
    except httpx.ConnectError:
        _die("Cannot connect to WAS. Is it running?")

    try:
        info = client.get_info()
        was_ver = info.get("was", {}).get("version", "unknown")
        click.echo(f"WAS version: {was_ver}")
    except httpx.HTTPStatusError:
        pass  # /api/info not available in all WAS versions

    click.echo(f"URL:         {client.base_url}")
    click.echo(f"Devices:     {len(devices)} connected")
    for d in devices:
        label = f" ({d['label']})" if d.get("label") else ""
        click.echo(f"  - {d['hostname']}{label} @ {d.get('ip', '?')}")


@cli.command(
    "logs",
    help="Tail WAS Docker container logs.\n\n"
    "Convenience wrapper around 'docker logs -f willow-application-server'.\n"
    "Press Ctrl+C to stop.",
)
@click.option("--lines", "-n", default=50, help="Number of initial lines to show.")
def logs(lines: int) -> None:
    try:
        subprocess.run(
            ["docker", "logs", "-f", "--tail", str(lines), "willow-application-server"],
            check=True,
        )
    except FileNotFoundError:
        _die("docker not found on PATH.")
    except KeyboardInterrupt:
        pass


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------


def _coerce(value: str) -> bool | int | str:
    """Coerce a CLI string value to the appropriate Python/JSON type."""
    if value.lower() == "true":
        return True
    if value.lower() == "false":
        return False
    try:
        return int(value)
    except ValueError:
        return value


def _fmt(value: object) -> str:
    if value is None:
        return "(missing)"
    return json.dumps(value) if not isinstance(value, str) else value


def _resolve_hostname(client: WASClient, hostname: str | None) -> str:
    """If hostname is None, auto-select the only connected device."""
    if hostname:
        return hostname
    try:
        devices = client.get_clients()
    except httpx.ConnectError:
        _die("Cannot connect to WAS. Is it running?")
    if len(devices) == 0:
        _die("No devices connected.")
    if len(devices) == 1:
        return devices[0]["hostname"]
    names = ", ".join(d["hostname"] for d in devices)
    _die(f"Multiple devices connected ({names}). Use --hostname to pick one.")


def _die(msg: str) -> None:
    click.echo(f"Error: {msg}", err=True)
    sys.exit(1)
