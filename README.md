# Lumos Smart Lighting (WiSilica) for Home Assistant

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://github.com/hacs/integration)
![Version](https://img.shields.io/badge/version-1.0.0-blue)
![License](https://img.shields.io/badge/license-MIT-green)

A Home Assistant custom integration for [Lumos Smart Lighting](https://www.wisilica.com/lumos/) devices by WiSilica. Control your Lumos lights and dimmers directly from Home Assistant.

---

## Features

- **Light control** — ON/OFF, brightness, RGB colour, colour temperature (1800K–6500K)
- **DALI dimmer support** — Individual channel control for multi-channel DALI drivers (e.g. Radiar DP5)
- **Tunable white lights** — Warm/cool colour temperature slider
- **Optimistic state updates** — UI responds instantly without waiting for cloud confirmation
- **Mobile app sync** — Changes made in the Lumos mobile app sync back to Home Assistant within 30 seconds
- **Multi-account support** — Add multiple Lumos accounts as separate integration entries

---

## Supported Devices

| Device Type | Name | Capabilities |
|-------------|------|-------------|
| 1021 | RGB CCT Light | ON/OFF, Brightness, RGB, Colour Temp |
| 1022 | WCA2CS Tunable White | ON/OFF, Brightness, Colour Temp |
| 1023 | CCT Tunable White | ON/OFF, Brightness, Colour Temp |
| 1024 | Radiar DP5 – DALI Dimmer | ON/OFF, Brightness (per channel) |
| 1042 | Tunable White Light | ON/OFF, Brightness, Colour Temp |
| 1, 2, 3 | Standard Lights | ON/OFF, Brightness, Colour Temp |
| 6, 7 | RGB Lights | ON/OFF, Brightness, RGB, Colour Temp |

New device types are automatically logged with a warning so they can be added easily.

---

## Requirements

- Home Assistant 2023.1 or newer
- A Lumos cloud account (sign up via the Lumos mobile app)
- Your Lumos gateway/bridge must be online and connected to the internet

---

## Installation

### Via HACS (Recommended)

1. Open HACS in Home Assistant
2. Go to **Integrations**
3. Click the **+** button and search for **Lumos Smart Lighting**
4. Click **Download**
5. Restart Home Assistant

### Manual Installation

1. Download the latest release from the [Releases page](https://github.com/raku306363s/ha-lumos/releases)
2. Copy the `custom_components/lumos` folder into your Home Assistant `config/custom_components/` directory
3. Restart Home Assistant

---

## Configuration

1. Go to **Settings → Devices & Services → Add Integration**
2. Search for **Lumos Smart Lighting**
3. Enter your credentials:
   - **Cloud API Base URL**: `https://lumos.wisilica.com`
   - **Username**: Your Lumos account username
   - **Password**: Your Lumos account password
4. Click **Submit**

Home Assistant will automatically discover all your Lumos devices and create entities for them.

---

## Options

After setup, you can adjust the polling interval:

1. Go to **Settings → Devices & Services → Lumos**
2. Click the **gear icon** → **Configure**
3. Set the **Polling interval** (default: 30 seconds, range: 10–3600 seconds)

---

## Device Discovery

The integration polls the Lumos cloud every 30 seconds. New devices added to your Lumos account will appear in Home Assistant automatically on the next poll — no restart required.

If a device type is not recognised, a warning is logged:
```
WARNING Unknown deviceType=XXXX — add to device_capabilities.py
```
Please open an issue with the device type number and device name so it can be added.

---

## Colour Temperature

The integration supports colour temperatures from **1800K** (warm candlelight) to **6500K** (cool daylight). The slider in Home Assistant maps directly to the warm/cool control in the Lumos app.

---

## Troubleshooting

**Devices not appearing**
- Make sure your Lumos gateway is online
- Check that your account credentials are correct
- Look for WARNING messages in the Home Assistant logs for unknown device types

**Commands not reaching the physical device**
- The Lumos cloud accepts and logs the command (status 20001) but the mesh network is responsible for delivery
- Check that your Lumos gateway/bridge is powered on and connected
- Try controlling the device from the Lumos mobile app to confirm mesh connectivity

**State not updating after mobile app changes**
- State syncs every 30 seconds by default
- You can reduce the polling interval in the integration options

---

## Adding a New Device Type

If you have a device that is not in the supported list, open `custom_components/lumos/device_capabilities.py` and add an entry:

```python
XXXX: LumosCapability(**_TW, label="My New Device"),
```

Available presets: `_ONOFF`, `_DIMMABLE`, `_TW`, `_RGB`

---

## Contributing

Pull requests are welcome. For major changes please open an issue first to discuss what you would like to change.

---

## License

MIT License — see [LICENSE](LICENSE) for details.

---

## Credits

Developed by [Rakesh C](https://github.com/raku306363s)  
Based on the WiSilica Lumos cloud API  
Built for the Home Assistant community
