# Snapmaker Integration Tests

This directory contains comprehensive tests for the Snapmaker Home Assistant integration.

## Test Structure

The test suite is organized into the following files:

### `conftest.py`
Contains shared fixtures used across all test files:
- `mock_snapmaker_device`: Mocks the SnapmakerDevice class with realistic test data
- `mock_discovery`: Mocks the device discovery method
- `mock_socket`: Mocks UDP socket communication for discovery tests
- `mock_requests`: Mocks HTTP requests for API communication
- `config_entry_data`: Provides sample config entry data
- `auto_enable_custom_integrations`: Auto-enables the custom integration for testing

### `test_snapmaker.py` (18 tests)
Tests for the core `SnapmakerDevice` class:
- Device discovery via UDP broadcast
- Token acquisition and validation
- Status updates via HTTP API
- Error handling and offline state management
- Dual vs single extruder configuration detection

### `test_config_flow.py` (13 tests)
Tests for the Home Assistant config flow:
- Manual device configuration
- DHCP-based discovery
- Device discovery and selection
- Error handling (connection failures, invalid data)
- Duplicate device prevention

### `test_init.py` (7 tests)
Tests for integration initialization:
- Component setup
- Config entry setup and unloading
- DataUpdateCoordinator creation and configuration
- Update intervals and failure handling

### `test_sensor.py` (20 tests)
Tests for sensor entities:
- Sensor platform setup for single and dual extruder configurations
- Individual sensor functionality (temperature, status, progress, etc.)
- Sensor availability based on coordinator and device status
- Device information and entity naming
- Handling of missing data

## Running Tests

### Prerequisites

Install test dependencies:
```bash
pip install -r requirements_test.txt
```

### Run All Tests

```bash
pytest
```

### Run with Verbose Output

```bash
pytest -v
```

### Run Specific Test File

```bash
pytest tests/test_snapmaker.py
pytest tests/test_config_flow.py
pytest tests/test_init.py
pytest tests/test_sensor.py
```

### Run Specific Test

```bash
pytest tests/test_snapmaker.py::TestSnapmakerDevice::test_discover_success
```

### Run with Coverage

```bash
pytest --cov=custom_components.snapmaker --cov-report=html
```

This generates an HTML coverage report in `htmlcov/index.html`.

### Run with Coverage (Terminal Output)

```bash
pytest --cov=custom_components.snapmaker --cov-report=term
```

## Test Configuration

### `pytest.ini`
Configures pytest settings:
- Test discovery patterns
- Async test mode (auto)
- Test paths

## Continuous Integration

Tests run automatically via GitHub Actions on:
- Push to main/master/develop branches
- Pull requests to main/master/develop branches

The CI workflow:
1. Runs tests on Python 3.11 and 3.12
2. Checks code formatting with `black`
3. Checks import sorting with `isort`
4. Validates manifest.json and hacs.json
5. Uploads coverage reports to Codecov

## Writing New Tests

When adding new functionality:

1. **Add unit tests** for the core logic in `test_snapmaker.py`
2. **Add config flow tests** if modifying setup/configuration in `test_config_flow.py`
3. **Add integration tests** if modifying initialization in `test_init.py`
4. **Add sensor tests** if adding new sensors or modifying existing ones in `test_sensor.py`

### Test Naming Conventions

- Test files: `test_*.py`
- Test classes: `Test*`
- Test methods: `test_*`

### Common Patterns

**Using fixtures:**
```python
def test_something(self, hass, mock_snapmaker_device):
    # hass and mock_snapmaker_device are automatically provided
    device = mock_snapmaker_device.return_value
    assert device.host == "192.168.1.100"
```

**Testing async functions:**
```python
async def test_async_function(self, hass):
    result = await some_async_function(hass)
    assert result is True
```

**Mocking config entries:**
```python
from pytest_homeassistant_custom_component.common import MockConfigEntry

config_entry = MockConfigEntry(
    domain=DOMAIN,
    data={CONF_HOST: "192.168.1.100"},
    unique_id="192.168.1.100",
)
config_entry.add_to_hass(hass)
```

## Troubleshooting

### Tests fail with "Integration not found"
Make sure `auto_enable_custom_integrations` fixture is active in `conftest.py`.

### Tests fail with socket errors
Check that socket mocking is properly configured in the fixture.

### Import errors
Ensure `pytest-homeassistant-custom-component` is installed:
```bash
pip install pytest-homeassistant-custom-component
```

## Test Coverage Goals

- **Overall coverage**: >90%
- **Core device logic**: 100%
- **Config flow paths**: All user flows covered
- **Error handling**: All exception paths tested
