#!/usr/bin/env python3
"""
Script to clean up old references in Home Assistant for the ThesslaGreen Modbus
integration. Removes outdated entities and references that may cause errors.

Run before restarting Home Assistant after updating the integration.
"""

import json
import os
import shutil
import sys
from pathlib import Path
from datetime import datetime

# Configuration
HA_CONFIG_PATHS = [
    Path.home() / ".homeassistant",  # Standard Linux path
    Path.home() / "homeassistant",   # Docker/Container
    Path("/config"),                 # Home Assistant OS
    Path("./config"),                # Relative path
]

OLD_ENTITY_PATTERNS = [
    "number.rekuperator_predkosc",
    "thessla_green_modbus.rekuperator_predkosc",
    "thessla.*rekuperator_predkosc",
]

BACKUP_SUFFIX = f"_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"


def find_ha_config_dir() -> Path | None:
    """Find the Home Assistant configuration directory."""
    for path in HA_CONFIG_PATHS:
        if path.exists() and (path / "configuration.yaml").exists():
            return path
    return None


def backup_file(file_path: Path) -> Path:
    """Create a backup of the file."""
    backup_path = file_path.with_suffix(file_path.suffix + BACKUP_SUFFIX)
    shutil.copy2(file_path, backup_path)
    print(f"✅ Backup utworzony: {backup_path}")
    return backup_path


def cleanup_entity_registry(config_dir: Path) -> bool:
    """Clean outdated entities from the entity registry."""
    registry_path = config_dir / ".storage" / "core.entity_registry"
    
    if not registry_path.exists():
        print(f"❌ Entity registry not found: {registry_path}")
        return False

    print(f"📁 Processing entity registry: {registry_path}")
    
    # Backup
    backup_path = backup_file(registry_path)
    
    try:
        with open(registry_path, 'r', encoding='utf-8') as f:
            registry = json.load(f)
        
        # Find old entities
        old_entities = []
        entities = registry.get("data", {}).get("entities", [])
        
        for entity in entities:
            entity_id = entity.get("entity_id", "")
            platform = entity.get("platform", "")
            
            # Check if this is an old thessla_green_modbus entity
            if (platform == "thessla_green_modbus" and 
                ("rekuperator_predkosc" in entity_id or 
                 "rekuperator_predkosc" in entity.get("unique_id", ""))):
                old_entities.append(entity)
            
            # Check other problematic patterns
            for pattern in OLD_ENTITY_PATTERNS:
                if pattern.replace("thessla.*", "thessla") in entity_id:
                    if entity not in old_entities:
                        old_entities.append(entity)

        if old_entities:
            print(f"🗑️  Found {len(old_entities)} old entities to remove:")
            for entity in old_entities:
                print(f"   - {entity['entity_id']} (platform: {entity.get('platform', 'unknown')})")
            
            # Remove old entities
            registry["data"]["entities"] = [
                e for e in entities if e not in old_entities
            ]
            
            # Save
            with open(registry_path, 'w', encoding='utf-8') as f:
                json.dump(registry, f, indent=2, ensure_ascii=False)
            
            print("✅ Entity registry updated")
            return True
        else:
            print("✅ No old entities found")
            # Remove unnecessary backup
            backup_path.unlink()
            return True
            
    except Exception as exc:
        print(f"❌ Error processing entity registry: {exc}")
        # Restore backup
        if backup_path.exists():
            shutil.copy2(backup_path, registry_path)
            print(f"🔄 Restored backup from: {backup_path}")
        return False


def cleanup_automations(config_dir: Path) -> bool:
    """Remove outdated entity references from automations."""
    automations_path = config_dir / "automations.yaml"
    
    if not automations_path.exists():
        print("ℹ️  automations.yaml does not exist - skipping")
        return True

    print(f"📁 Checking automations: {automations_path}")
    
    try:
        with open(automations_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Check for references to old entities
        problematic_refs = []
        for pattern in OLD_ENTITY_PATTERNS:
            if pattern.replace("thessla.*", "thessla") in content:
                problematic_refs.append(pattern)
        
        if problematic_refs:
            print(f"⚠️  Found {len(problematic_refs)} references to old entities:")
            for ref in problematic_refs:
                print(f"   - {ref}")
            print("❗ Review and update automations manually")
            print(f"   File: {automations_path}")
            return False
        else:
            print("✅ Automations are clean")
            return True
            
    except Exception as exc:
        print(f"❌ Error checking automations: {exc}")
        return False


def cleanup_configuration_yaml(config_dir: Path) -> bool:
    """Check configuration.yaml for old references."""
    config_path = config_dir / "configuration.yaml"
    
    if not config_path.exists():
        print("❌ configuration.yaml not found")
        return False

    print(f"📁 Checking configuration: {config_path}")
    
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Look for problematic references
        issues = []
        
        for pattern in OLD_ENTITY_PATTERNS:
            if pattern.replace("thessla.*", "thessla") in content:
                issues.append(f"Referencja do {pattern}")
        
        # Check for old integration configuration
        if "thessla_green_modbus:" in content:
            issues.append("Old YAML configuration for integration (use UI)")
        
        if issues:
            print(f"⚠️  Found {len(issues)} issues in configuration:")
            for issue in issues:
                print(f"   - {issue}")
            print("❗ Review and update configuration.yaml manually")
            return False
        else:
            print("✅ Configuration is clean")
            return True
            
    except Exception as exc:
        print(f"❌ Error checking configuration: {exc}")
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
                print(f"🧹 Usunięto cache: {cache_path}")
                cleaned = True
            except Exception as exc:
                print(f"⚠️  Nie można usunąć cache {cache_path}: {exc}")
    
    if not cleaned:
        print("ℹ️  Nie znaleziono cache do wyczyszczenia")
    
    return True


def main():
    """Główna funkcja skryptu."""
    print("🔧 ThesslaGreen Modbus - Cleanup Tool")
    print("=" * 50)
    
    # Znajdź katalog konfiguracyjny HA
    config_dir = find_ha_config_dir()
    if not config_dir:
        print("❌ Nie można znaleźć katalogu konfiguracyjnego Home Assistant")
        print("Sprawdź czy znajdujesz się w odpowiednim katalogu lub HA jest zainstalowany")
        sys.exit(1)
    
    print(f"📁 Znaleziono konfigurację HA: {config_dir}")
    print()
    
    # Wykonaj czyszczenie
    results = {
        "entity_registry": cleanup_entity_registry(config_dir),
        "automations": cleanup_automations(config_dir),
        "configuration": cleanup_configuration_yaml(config_dir),
        "cache": cleanup_custom_component_cache(config_dir),
    }
    
    print("\n" + "=" * 50)
    print("📊 PODSUMOWANIE:")
    
    success_count = sum(results.values())
    total_count = len(results)
    
    for task, success in results.items():
        status = "✅ OK" if success else "❌ UWAGA"
        print(f"   {task.ljust(20)}: {status}")
    
    print(f"\nWynik: {success_count}/{total_count} zadań zakończonych pomyślnie")
    
    if success_count == total_count:
        print("\n🎉 Czyszczenie zakończone pomyślnie!")
        print("💡 Możesz teraz bezpiecznie zrestartować Home Assistant")
    else:
        print("\n⚠️  Niektóre zadania wymagają uwagi")
        print("📝 Sprawdź i popraw wskazane problemy przed restartem HA")
    
    # Pokaż instrukcje następnych kroków
    print("\n🔄 NASTĘPNE KROKI:")
    print("1. Sprawdź powyższe ostrzeżenia (jeśli są)")
    print("2. Zrestartuj Home Assistant")
    print("3. Sprawdź czy integracja działa poprawnie")
    print("4. Usuń niepotrzebne backupy z .storage/ (opcjonalnie)")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n⏹️  Przerwano przez użytkownika")
        sys.exit(1)
    except Exception as exc:
        print(f"\n❌ Nieoczekiwany błąd: {exc}")
        sys.exit(1)