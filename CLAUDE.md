# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with
code in this repository.

## Project Overview

This is a Home Assistant custom integration for monitoring and controlling
Snapmaker 3D printers over the local network. The integration communicates with
Snapmaker devices using:

- UDP broadcast on port 20054 for device discovery
- HTTP REST API on port 8080 for detailed status and control

## Architecture

### Core Components

**SnapmakerDevice** (`custom_components/snapmaker/snapmaker.py`):

- Handles low-level communication with Snapmaker devices
- Implements discovery protocol via UDP broadcast
- Manages token-based authentication for API access
- Provides device status updates including temperatures, print progress, and job
  information

**DataUpdateCoordinator** (`custom_components/snapmaker/__init__.py`):

- Polls the SnapmakerDevice every 30 seconds
- Coordinates data updates across all sensor entities
- Runs the blocking `snapmaker.update()` call in an executor job

**Config Flow** (`custom_components/snapmaker/config_flow.py`):

- Supports multiple setup methods: manual IP entry, DHCP discovery, and
  automatic device discovery
- Uses unique_id based on device IP to prevent duplicate configuration
- Validates connectivity before completing setup

**Sensors** (`custom_components/snapmaker/sensor.py`):

- 9 sensor entities per device:
    - Status (IDLE, RUNNING, OFFLINE)
    - Nozzle temperature (current and target)
    - Bed temperature (current and target)
    - File name
    - Progress percentage
    - Elapsed and remaining time
- All sensors inherit from `SnapmakerSensorBase` which extends
  `CoordinatorEntity`

### Communication Flow

1. **Discovery**: UDP broadcast message "discover" → device responds with
   `IP@<ip>|Model:<model>|Status:<status>`
2. **Authentication**: POST to `/api/v1/connect` → receive token → validate
   token
3. **Status Updates**: GET `/api/v1/status?token=<token>` → parse JSON response

### Data Structure

The SnapmakerDevice maintains a `_data` dict with keys:

- `ip`, `model`, `status`
- `nozzle_temperature`, `nozzle_target_temperature`
- `heated_bed_temperature`, `heated_bed_target_temperature`
- `file_name`, `progress`, `elapsed_time`, `remaining_time`

## Development Commands

This is a Home Assistant custom component - no separate build or test commands
are needed. Development workflow:

1. **Install in Home Assistant**: Copy `custom_components/snapmaker/` to your
   Home Assistant `config/custom_components/` directory
2. **Restart Home Assistant**: Required after any code changes
3. **Configure Integration**: Configuration → Integrations → Add Integration →
   Snapmaker
4. **View Logs**: Check Home Assistant logs for errors (logger name:
   `custom_components.snapmaker`)

## Testing

Test the integration by:

1. Ensuring your Snapmaker device is on the same network
2. Verifying UDP port 20054 and TCP port 8080 are accessible
3. Checking sensor values update every 30 seconds in Home Assistant

## Key Design Patterns

- **Async/Sync Bridge**: Home Assistant is async, but the Snapmaker
  communication uses synchronous `requests` and `socket`. All blocking calls are
  wrapped with `hass.async_add_executor_job()`.
- **Coordinator Pattern**: Single DataUpdateCoordinator polls the device; all
  sensors listen to coordinator updates rather than polling independently.
- **Unique ID Strategy**: Device IP address is used as the unique identifier for
  both the config entry and as the base for sensor unique IDs.
- **Error Handling**: Connection failures set device status to "OFFLINE" and
  populate sensors with default values (0 for temperatures, "N/A" for strings).

## Important Constraints

- Minimum Home Assistant version: 2023.8.0 (specified in hacs.json)
- Token must be refreshed if device reboots or connection is lost
- Discovery uses a retry mechanism (MAX_RETRIES=5, SOCKET_TIMEOUT=1.0s) to
  handle network latency
- The integration only supports the sensor platform; no control entities (
  switches, buttons) are implemented yet
