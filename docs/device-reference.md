# ESP32-S3-BOX-3 Device Reference

## Physical Buttons

The ESP32-S3-BOX-3 has three physical interaction points:

### Mute Button (top, small round button)
- **Short press:** Toggles microphone on/off
- **Effect:** Software-only; does not affect config or device state
- **When muted:** Wake word detection is disabled, red LED indicator on

### Boot/Reset Button (recessed pinhole on the back or side)
- **Short press:** Reboots the device (equivalent to power cycle)
- **Long press (~5s):** Enters USB bootloader mode for firmware flashing
- **Effect on config:** None — NVS flash (WiFi + WAS URL) is preserved across reboots
- **Effect on WAS:** Device disconnects and reconnects; fetches fresh config from WAS

### Touch Screen
- **Touch:** Interacts with the on-screen UI (volume, settings display, etc.)
- **No hardware reset or factory reset is accessible through touch**

## What Survives a Reboot / Power Cycle

| Storage | Location | Survives reboot? | Contents |
|---|---|---|---|
| NVS flash | Device | Yes | WiFi SSID/PSK, WAS WebSocket URL |
| Device RAM | Device | No | Runtime config (fetched from WAS on boot) |
| WAS database | Laptop (Docker) | Yes* | All config overrides |

*WAS database survives as long as the Docker volume (`storage/was.db`) is intact.

## Boot Sequence

1. Device powers on, reads WiFi credentials from NVS flash
2. Connects to WiFi network
3. Reads WAS URL from NVS flash, opens WebSocket connection
4. Sends `{"hello": {...}}` with hostname, MAC, hardware type
5. Sends `{"cmd": "get_config"}` to request full configuration
6. WAS responds with merged config (defaults + overrides)
7. Device applies config to RAM and is ready for wake word detection

If WAS is unreachable at step 3, the device retries and eventually shows
a connection error. It cannot function without WAS in `was_mode=true`.

## Factory Reset

There is **no button combination** that triggers a factory reset. Clearing
NVS (WiFi + WAS URL) requires reflashing the NVS partition via the
Willow Web Flasher. This is a deliberate safety measure — you cannot
accidentally wipe device identity from a button press.

## USB Connection

USB-C provides **power only** during normal operation. The device communicates
with WAS exclusively over WiFi (WebSocket). USB is used for:
- Power delivery (5V from laptop, wall adapter, or battery pack)
- Serial console access (for firmware debugging via `idf.py monitor`)
- Firmware flashing (when in bootloader mode)

Switching from laptop USB to a wall adapter does not affect device operation
as long as WiFi and WAS remain accessible.
