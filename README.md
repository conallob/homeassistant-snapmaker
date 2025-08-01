# homeassistant-snapmaker
A home-assistant.io integration for interacting with a Snapmaker 3D printer

## Overview

This custom integration allows you to monitor and control your Snapmaker 3D
printer from Home Assistant. It communicates with the Snapmaker device over your
local network and provides sensors for various printer states and metrics.

## Features

- Auto-discovery of Snapmaker devices on your network
- Monitor printer status (IDLE, RUNNING, etc.)
- Track nozzle and heated bed temperatures
- View current print job information (file name, progress, elapsed time,
  remaining time)
- Integration with Home Assistant's device registry

## Installation

### Manual Installation

1. Copy the `custom_components/snapmaker` directory to your Home Assistant's
   `custom_components` directory
2. Restart Home Assistant
3. Go to Configuration -> Integrations
4. Click the "+ Add Integration" button
5. Search for "Snapmaker" and follow the configuration steps

### HACS Installation

1. Open HACS in your Home Assistant instance
2. Go to "Integrations"
3. Click the three dots in the top right corner and select "Custom repositories"
4. Add this repository URL with category "Integration"
5. Click "Install" on the Snapmaker integration card
6. Restart Home Assistant
7. Configure the integration as described above

## Configuration

The integration can be configured through the Home Assistant UI. You'll need to
provide the IP address of your Snapmaker device.

## Troubleshooting

- Make sure your Snapmaker device is powered on and connected to the same
  network as your Home Assistant instance
- Check that port 20054 (UDP) is open for device discovery
- Verify that port 8080 (TCP) is accessible for API communication

## Credits

This integration is based on the work
of [NiteCrwlr](https://github.com/NiteCrwlr/playground/blob/main/SNStatus/SNStatusV2.py)
for the Snapmaker communication protocol.

## License

This project is licensed under the MIT License - see the LICENSE file for
details.
