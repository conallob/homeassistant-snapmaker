# Snapmaker Integration Tests

This directory contains unit tests for the Snapmaker Home Assistant integration.

## Running Tests

### Install Test Dependencies

```bash
pip install -r requirements_test.txt
```

### Run All Tests

```bash
pytest
```

### Run Specific Test File

```bash
pytest tests/test_snapmaker.py
```

### Run with Coverage

```bash
pytest --cov=custom_components.snapmaker --cov-report=html
```

## Test Structure

- `test_snapmaker.py` - Tests for the SnapmakerDevice class (UDP discovery, token management, status retrieval)
- `test_config_flow.py` - Tests for the configuration flow (user setup, DHCP discovery, device selection)
- `test_init.py` - Tests for integration setup and coordinator
- `test_sensor.py` - Tests for all sensor entities
- `conftest.py` - Shared fixtures and mocks

## Coverage

The tests cover:

- Device discovery via UDP broadcast
- Token-based authentication
- Status data retrieval and parsing
- Single and dual extruder configurations
- Config flow steps (user, DHCP, discovery, confirmation)
- DataUpdateCoordinator setup and updates
- All sensor entities and their properties
- Error handling and edge cases
