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

### Token-Based Authentication

The integration implements secure token-based authentication following Snapmaker's
API requirements. This ensures only authorized connections can access device data.

**Token Generation Flow**:

1. Config flow initiates token request via POST to `/api/v1/connect`
2. Device responds with a temporary token
3. User must approve the connection on the Snapmaker touchscreen
4. Integration polls the token validation endpoint (10s intervals, max 5 minutes)
5. Once approved, token is validated and persisted to config entry

**Token Persistence**:

- Tokens are stored in Home Assistant's config entry data
- Tokens survive restarts and are automatically restored on setup
- A callback mechanism updates the config entry if a token refresh occurs
- Thread-safe updates using `call_soon_threadsafe()` from executor threads

**Token Expiration & Reauth**:

- When API returns 401 Unauthorized, the `token_invalid` flag is set
- DataUpdateCoordinator detects this and triggers a reauth flow (only once)
- User is prompted to generate a new token via the touchscreen
- New token is validated before persisting to config entry
- Integration automatically reloads with the new token

**Thread Pool Considerations**:

The `generate_token()` method blocks an executor thread during token generation:
- Default: 18 attempts × 10 second intervals = up to 3 minutes blocking time
- This is necessary because users must manually approve on the touchscreen
- Home Assistant's default executor pool has limited threads (typically 5-15)
- During token generation, one thread is unavailable for other operations
- This only occurs during initial setup or reauth, not during normal operation
- Consider the impact if multiple devices need reauth simultaneously
- The timeout can be customized via the `max_attempts` parameter if needed

Recommendations for production use:
- Ensure users understand they must approve on the touchscreen promptly
- Monitor thread pool utilization if managing many Snapmaker devices
- Token generation only happens during setup/reauth, not routine updates
- For large deployments, stagger device setup to avoid simultaneous token requests

### Breaking Changes & Migration

**Version 2.x - Token Authentication Required**

Prior versions of this integration did not implement token authentication,
which meant the API status endpoint was accessed without proper authorization.
As of version 2.x, token authentication is mandatory.

**Migration Path for Existing Users**:

If you're upgrading from a pre-2.x version:

1. **Automatic Reauth Prompt**: On first update attempt after upgrade, the
   integration will detect missing or invalid token and trigger a reauth flow
2. **User Action Required**: You'll see a "Reauthenticate" notification in Home
   Assistant → Configuration → Integrations
3. **Complete Reauth**: Click the notification, follow the authorize step, and
   approve the connection on your Snapmaker touchscreen
4. **Normal Operation Resumes**: Once token is generated and validated, the
   integration will work as before

**What Changed**:

- Config entries now include a `token` field in addition to `host`
- All API status requests include `?token=<token>` parameter
- 401 responses trigger automatic reauth flow instead of failing silently
- New `authorize` step in config flow guides users through token generation

**Backward Compatibility**:

- Existing config entries without tokens will continue to load
- First update will fail and trigger reauth automatically
- No manual intervention needed beyond approving on touchscreen

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
