# Contributing to ThesslaGreen Modbus Integration

🎉 Thank you for your interest in contributing to the ThesslaGreen Modbus Integration! 

## 📋 Table of Contents

- [Code of Conduct](#code-of-conduct)
- [Getting Started](#getting-started)
- [Development Setup](#development-setup)
- [Making Changes](#making-changes)
- [Testing](#testing)
- [Code Quality](#code-quality)
- [Submitting Changes](#submitting-changes)
- [Release Process](#release-process)

## Code of Conduct

This project adheres to a simple code of conduct:
- Be respectful and inclusive
- Focus on constructive feedback
- Help others learn and grow
- Keep discussions on-topic

## Getting Started

### Prerequisites

- Python 3.12+
- Home Assistant 2025.7.1+ (managed outside `requirements.txt`)
- Git
- A ThesslaGreen AirPack device (for testing)

### Areas for Contribution

We welcome contributions in these areas:

🔧 **Bug Fixes**
- Modbus communication issues
- Entity state problems
- Configuration errors

✨ **Features**
- New sensor types
- Additional device models
- Enhanced automation capabilities

📚 **Documentation**
- Installation guides
- Configuration examples
- Troubleshooting help

🧪 **Testing**
- Unit tests
- Integration tests
- Performance testing

🌍 **Translations**
- Additional languages
- Improved existing translations

## Development Setup

### 1. Fork and Clone

```bash
# Fork the repository on GitHub first, then:
git clone https://github.com/thesslagreen/thessla-green-modbus-ha.git
cd thessla_green_modbus
```

### 2. Set up Development Environment

```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies (Home Assistant core excluded)
pip install -r requirements.txt -r requirements-dev.txt

# Install pre-commit hooks (run again after pulling new changes)
pre-commit install
```

> **Note:** The `homeassistant` package is not included in `requirements.txt`; ensure your environment provides a compatible Home Assistant version as declared in `custom_components/thessla_green_modbus/manifest.json`.

### 3. Verify Setup

```bash
# Run unit tests
python -m pytest tests/ -v

# Verify module syntax
python tools/py_compile_all.py

# Check code quality
pre-commit run --all-files
```

### Updating register maps

Register addresses are defined in
`custom_components/thessla_green_modbus/registers/thessla_green_registers_full.json`
and this file serves as the sole source of truth.  The integration reads the
JSON directly; if you require a static Python mapping for other tools, run:

```bash
python tools/generate_registers.py
```

The test suite ensures the JSON definitions remain valid.

## Making Changes

### Branch Strategy

- `main` - stable releases
- `develop` - development branch
- `feature/your-feature-name` - feature branches
- `bugfix/issue-description` - bug fix branches

### Creating a Feature Branch

```bash
git checkout develop
git pull origin develop
git checkout -b feature/your-feature-name
```

### Code Style Guidelines

We follow these conventions:

**Python Code:**
- Use [Black](https://black.readthedocs.io/) for formatting (100 char line length)
- Use [isort](https://pycqa.github.io/isort/) for import sorting
- Follow [PEP 8](https://pep8.org/) style guidelines
- Use type hints where possible

**Home Assistant Specific:**
- Follow [HA development guidelines](https://developers.home-assistant.io/)
- Use `async`/`await` for I/O operations
- Implement proper error handling
- Include device info for entities

**Modbus Communication:**
- Handle connection errors gracefully
- Implement retry logic
- Use efficient batch reading
- Validate register values

### File Structure

```
custom_components/thessla_green_modbus/
├── __init__.py              # Integration setup
├── manifest.json            # Integration metadata
├── config_flow.py           # Configuration UI
├── const.py                 # Constants and register definitions
├── coordinator.py           # Data coordinator (optimized)
├── device_scanner.py        # Device capability scanner
├── climate.py               # Climate entity (enhanced)
├── sensor.py                # Sensor entities
├── binary_sensor.py         # Binary sensor entities (enhanced)
├── select.py                # Select entities
├── number.py                # Number entities
├── switch.py                # Switch entities
├── fan.py                   # Fan entity
├── services.yaml            # Service definitions
└── translations/            # Translation files
    ├── en.json
    └── pl.json
```

### Regenerating register definitions

The canonical register specification lives in
`custom_components/thessla_green_modbus/registers/thessla_green_registers_full.json`.
After editing this file, run the validation tests and, if needed, regenerate the
helper Python module:

```bash
python tools/generate_registers.py  # optional helper
```

Commit the updated JSON file. The `generate-registers` pre-commit hook runs the
generator when necessary.

## Testing

### Running Tests

```bash
# Run all tests
python -m pytest tests/ -v

# Run specific test file
python -m pytest tests/test_coordinator.py -v

# Run with coverage
python -m pytest tests/ --cov=custom_components.thessla_green_modbus

# Validate register file
python -m pytest tests/test_register_loader.py -v

# Validate translation files
python -m json.tool custom_components/thessla_green_modbus/translations/*.json

# Run optimization validation
python run_optimization_tests.py
```

### Writing Tests

For new features, please include:

1. **Unit Tests** - Test individual functions/classes
2. **Integration Tests** - Test component interactions
3. **Mock Tests** - Test with simulated Modbus responses

Example test structure:
```python
async def test_your_feature():
    """Test your new feature."""
    # Arrange
    coordinator = create_mock_coordinator()
    
    # Act
    result = await coordinator.your_method()
    
    # Assert
    assert result == expected_value
```

### Testing with Real Hardware

If you have a ThesslaGreen device:

1. Create a test configuration
2. Test with different device states
3. Verify all registers are read correctly
4. Test error conditions (disconnection, etc.)

## Code Quality

### Pre-commit Checks

Run `pre-commit install` once to activate these checks. Before committing, the following checks run automatically:

- **Black** - Code formatting
- **isort** - Import sorting
- **flake8** - Linting
- **mypy** - Type checking
- **bandit** - Security scanning
- **yamllint** - YAML validation
- **check-merge-conflict** - Prevents committing unresolved merge conflicts
- **check-json** - Validates translation files
- **hassfest** - Validates integration metadata against Home Assistant rules
- **vulture** - Detects unused code in `custom_components/thessla_green_modbus`

### Manual Quality Checks

```bash
# Format code
black custom_components/

# Sort imports
isort custom_components/

# Lint code
flake8 custom_components/ --max-line-length=100

# Type checking
mypy custom_components/thessla_green_modbus/

# Security scan
bandit -r custom_components/

# Validate integration metadata
hassfest --config=.

# Dead code detection
vulture custom_components/thessla_green_modbus --min-confidence=80
```

## Submitting Changes

### Pull Request Process

1. **Update your branch:**
   ```bash
   git checkout develop
   git pull origin develop
   git checkout your-feature-branch
   git rebase develop
   ```

2. **Run all checks:**
   ```bash
   python tools/py_compile_all.py
   pre-commit run --all-files
   python -m pytest tests/
   ```

3. **Commit your changes:**
   ```bash
   git add .
   git commit -m "feat: add new sensor for XYZ"
   ```

4. **Push and create PR:**
   ```bash
   git push origin your-feature-branch
   # Create PR on GitHub
   ```

### Commit Message Format

We use [Conventional Commits](https://www.conventionalcommits.org/):

- `feat:` - New features
- `fix:` - Bug fixes
- `docs:` - Documentation changes
- `test:` - Adding tests
- `refactor:` - Code refactoring
- `perf:` - Performance improvements
- `chore:` - Maintenance tasks

Examples:
```
feat: add bypass temperature control
fix: resolve modbus timeout issues
docs: update installation instructions
test: add coordinator unit tests
```

### Pull Request Guidelines

**Title:** Clear, descriptive summary of changes

**Description should include:**
- What changed and why
- Any breaking changes
- Testing performed
- Related issues (if any)

**PR Checklist:**
- [ ] Code follows style guidelines
- [ ] Tests added/updated
- [ ] Documentation updated
- [ ] No breaking changes (or clearly documented)
- [ ] All checks pass

## Release Process

### Versioning

We use [Semantic Versioning](https://semver.org/):
- `MAJOR.MINOR.PATCH`
- Major: Breaking changes
- Minor: New features (backward compatible)
- Patch: Bug fixes

### Release Checklist

For maintainers:

1. Update version in `manifest.json`
2. Update `CHANGELOG.md`
3. Run full test suite
4. Create release tag
5. Publish to GitHub releases
6. Update HACS repository

## Getting Help

### Documentation

- [Installation Guide](README.md#installation)
- [Configuration Guide](DEPLOYMENT.md)
- [Troubleshooting](README.md#troubleshooting)

### Support Channels

- **GitHub Issues** - Bug reports and feature requests
- **Discussions** - General questions and ideas
- **Wiki** - Detailed documentation

### Modbus Resources

- [ThesslaGreen Modbus Documentation](docs/)
- [pymodbus Documentation](https://pymodbus.readthedocs.io/)
- [Home Assistant Developer Docs](https://developers.home-assistant.io/)

## Recognition

Contributors will be recognized in:
- `README.md` contributors section
- Release notes
- GitHub contributors page

Thank you for contributing to make ThesslaGreen integration better! 🚀
