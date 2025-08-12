#!/usr/bin/env python3
"""
Script to clean up old references in Home Assistant for the ThesslaGreen Modbus
integration. Removes outdated entities and references that may cause errors.

Usage:
    python3 cleanup_old_entities.py

Run this script before restarting Home Assistant after updating the integration.
"""

import logging
import json
import shutil
from datetime import datetime
from pathlib import Path

_LOGGER = logging.getLogger(__name__)

# Configuration
HA_CONFIG_PATHS = [
    Path.home() / ".homeassistant",  # Standard Linux path
    Path.home() / "homeassistant",  # Docker/Container
    Path("/config"),  # Home Assistant OS
    Path("./config"),  # Relative path
]

OLD_ENTITY_PATTERNS = [
    "number.rekuperator_predkosc",
    "thessla_green_modbus.rekuperator_predkosc",
    "thessla.*rekuperator_predkosc",
]


def find_ha_config_dir() -> Path | None:
    """Find the Home Assistant configuration directory."""
    for path in HA_CONFIG_PATHS:
        if path.exists() and (path / "configuration.yaml").exists():
            return path
    return None


def backup_file(file_path: Path) -> Path:
    """Create a backup of the file."""
    backup_suffix = datetime.now().strftime("_backup_%Y%m%d_%H%M%S")
    backup_path = file_path.with_suffix(file_path.suffix + backup_suffix)
    shutil.copy2(file_path, backup_path)
    _LOGGER.info("Backup created: %s", backup_path)
    return backup_path


def cleanup_entity_registry(config_dir: Path) -> bool:
    """Clean outdated entities from the entity registry."""
    registry_path = config_dir / ".storage" / "core.entity_registry"

    if not registry_path.exists():
        _LOGGER.error("Entity registry not found: %s", registry_path)
        return False

    _LOGGER.info("Processing entity registry: %s", registry_path)

    # Backup
    backup_path = backup_file(registry_path)

    try:
        with open(registry_path, "r", encoding="utf-8") as f:
            registry = json.load(f)

        # Find old entities
        old_entities = []
        entities = registry.get("data", {}).get("entities", [])

        for entity in entities:
            entity_id = entity.get("entity_id", "")
            platform = entity.get("platform", "")

            # Check if this is an old thessla_green_modbus entity
            if platform == "thessla_green_modbus" and (
                "rekuperator_predkosc" in entity_id
                or "rekuperator_predkosc" in entity.get("unique_id", "")
            ):
                old_entities.append(entity)

            # Check other problematic patterns
            for pattern in OLD_ENTITY_PATTERNS:
                if pattern.replace("thessla.*", "thessla") in entity_id:
                    if entity not in old_entities:
                        old_entities.append(entity)

        if old_entities:
            _LOGGER.info("Found %s old entities to remove:", len(old_entities))
            for entity in old_entities:
                _LOGGER.info(
                    "   - %s (platform: %s)",
                    entity["entity_id"],
                    entity.get("platform", "unknown"),
                )

            # Remove old entities
            registry["data"]["entities"] = [e for e in entities if e not in old_entities]

            # Save
            with open(registry_path, "w", encoding="utf-8") as f:
                json.dump(registry, f, indent=2, ensure_ascii=False)

            _LOGGER.info("Entity registry updated")
            return True
        else:
            _LOGGER.info("No old entities found")
            # Remove unnecessary backup
            backup_path.unlink()
            return True

    except OSError as exc:
        _LOGGER.error("Error processing entity registry file: %s", exc)
        if backup_path.exists():
            shutil.copy2(backup_path, registry_path)
            _LOGGER.info("Restored backup from: %s", backup_path)
        return False
    except json.JSONDecodeError as exc:
        _LOGGER.error("Error decoding entity registry JSON: %s", exc)
        if backup_path.exists():
            shutil.copy2(backup_path, registry_path)
            _LOGGER.info("Restored backup from: %s", backup_path)
        return False


def cleanup_automations(config_dir: Path) -> bool:
    """Remove outdated entity references from automations."""
    automations_path = config_dir / "automations.yaml"

    if not automations_path.exists():
        _LOGGER.info("automations.yaml does not exist - skipping")
        return True

    _LOGGER.info("Checking automations: %s", automations_path)

    try:
        with open(automations_path, "r", encoding="utf-8") as f:
            content = f.read()

        # Check for references to old entities
        problematic_refs = []
        for pattern in OLD_ENTITY_PATTERNS:
            if pattern.replace("thessla.*", "thessla") in content:
                problematic_refs.append(pattern)

        if problematic_refs:
            _LOGGER.warning("Found %s references to old entities:", len(problematic_refs))
            for ref in problematic_refs:
                _LOGGER.warning("   - %s", ref)
            _LOGGER.warning("Review and update automations manually")
            _LOGGER.warning("   File: %s", automations_path)
            return False
        else:
            _LOGGER.info("Automations are clean")
            return True

    except (OSError, UnicodeDecodeError) as exc:
        _LOGGER.error("Error checking automations: %s", exc)
        return False


def cleanup_configuration_yaml(config_dir: Path) -> bool:
    """Check configuration.yaml for old references."""
    config_path = config_dir / "configuration.yaml"

    if not config_path.exists():
        _LOGGER.error("configuration.yaml not found")
        return False

    _LOGGER.info("Checking configuration: %s", config_path)

    try:
        with open(config_path, "r", encoding="utf-8") as f:
            content = f.read()

        # Look for problematic references
        issues = []

        for pattern in OLD_ENTITY_PATTERNS:
            if pattern.replace("thessla.*", "thessla") in content:
                issues.append(f"Reference to {pattern}")

        # Check for old integration configuration
        if "thessla_green_modbus:" in content:
            issues.append("Old YAML configuration for integration (use UI)")

        if issues:
            _LOGGER.warning("Found %s issues in configuration:", len(issues))
            for issue in issues:
                _LOGGER.warning("   - %s", issue)
            _LOGGER.warning("Review and update configuration.yaml manually")
            return False
        else:
            _LOGGER.info("Configuration is clean")
            return True

    except (OSError, UnicodeDecodeError) as exc:
        _LOGGER.error("Error checking configuration: %s", exc)
        return False


def cleanup_custom_component_cache(config_dir: Path) -> bool:
    """Clear custom component cache."""
    cache_paths = [
        config_dir / "deps",
        config_dir / ".storage" / "lovelace",
        config_dir / "__pycache__",
        config_dir / "custom_components" / "thessla_green_modbus" / "__pycache__",
    ]

    cleaned = False
    for cache_path in cache_paths:
        if cache_path.exists():
            try:
                if cache_path.is_dir():
                    shutil.rmtree(cache_path)
                else:
                    cache_path.unlink()
                _LOGGER.info("Removed cache: %s", cache_path)
                cleaned = True
            except OSError as exc:
                _LOGGER.warning("Unable to remove cache %s: %s", cache_path, exc)

    if not cleaned:
        _LOGGER.info("No cache found to clean")

    return True


def main():
    """Main entry point of the script."""
    _LOGGER.info("ThesslaGreen Modbus - Cleanup Tool")
    _LOGGER.info("=" * 50)

    # Locate HA configuration directory
    config_dir = find_ha_config_dir()
    if not config_dir:
        _LOGGER.error("Cannot find Home Assistant configuration directory")
        _LOGGER.error("Ensure you are in the correct directory or Home Assistant is installed")
        raise SystemExit(1)

    _LOGGER.info("Found HA configuration: %s", config_dir)
    _LOGGER.info("")

    # Perform cleanup
    results = {
        "entity_registry": cleanup_entity_registry(config_dir),
        "automations": cleanup_automations(config_dir),
        "configuration": cleanup_configuration_yaml(config_dir),
        "cache": cleanup_custom_component_cache(config_dir),
    }

    _LOGGER.info("\n" + "=" * 50)
    _LOGGER.info("SUMMARY:")

    success_count = sum(results.values())
    total_count = len(results)

    for task, success in results.items():
        status = "OK" if success else "ATTENTION"
        _LOGGER.info("   %s: %s", task.ljust(20), status)

    _LOGGER.info("\nResult: %s/%s tasks completed successfully", success_count, total_count)

    if success_count == total_count:
        _LOGGER.info("\nCleanup completed successfully!")
        _LOGGER.info("You can now safely restart Home Assistant")
    else:
        _LOGGER.warning("\nSome tasks require attention")
        _LOGGER.warning("Check and fix the reported issues before restarting HA")

    # Show next steps
    _LOGGER.info("\nNEXT STEPS:")
    _LOGGER.info("1. Review the warnings above (if any)")
    _LOGGER.info("2. Restart Home Assistant")
    _LOGGER.info("3. Verify the integration works properly")
    _LOGGER.info("4. Remove unnecessary backups from .storage/ (optional)")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        _LOGGER.warning("\n\nInterrupted by user")
        raise SystemExit(1)
    except (OSError, json.JSONDecodeError, UnicodeDecodeError) as exc:
        _LOGGER.error("\nUnexpected error: %s", exc)
        raise SystemExit(1)
