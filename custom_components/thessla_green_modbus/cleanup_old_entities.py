#!/usr/bin/env python3
"""
Skrypt do czyszczenia starych referencji w Home Assistant - ThesslaGreen Modbus
Usuwa stare entytie i referencje, które mogą powodować błędy.

Uruchom PRZED restartowaniem Home Assistant po aktualizacji integracji.
"""

import json
import os
import shutil
import sys
from pathlib import Path
from datetime import datetime

# Konfiguracja
HA_CONFIG_PATHS = [
    Path.home() / ".homeassistant",  # Standardowa ścieżka Linux
    Path.home() / "homeassistant",   # Docker/Container
    Path("/config"),                 # Home Assistant OS
    Path("./config"),                # Względna ścieżka
]

OLD_ENTITY_PATTERNS = [
    "number.rekuperator_predkosc",
    "thessla_green_modbus.rekuperator_predkosc",
    "thessla.*rekuperator_predkosc",
]

BACKUP_SUFFIX = f"_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"


def find_ha_config_dir() -> Path | None:
    """Znajdź katalog konfiguracyjny Home Assistant."""
    for path in HA_CONFIG_PATHS:
        if path.exists() and (path / "configuration.yaml").exists():
            return path
    return None


def backup_file(file_path: Path) -> Path:
    """Utwórz backup pliku."""
    backup_path = file_path.with_suffix(file_path.suffix + BACKUP_SUFFIX)
    shutil.copy2(file_path, backup_path)
    print(f"✅ Backup utworzony: {backup_path}")
    return backup_path


def cleanup_entity_registry(config_dir: Path) -> bool:
    """Wyczyść entity registry z starych entytii."""
    registry_path = config_dir / ".storage" / "core.entity_registry"
    
    if not registry_path.exists():
        print(f"❌ Entity registry nie znaleziony: {registry_path}")
        return False

    print(f"📁 Przetwarzam entity registry: {registry_path}")
    
    # Backup
    backup_path = backup_file(registry_path)
    
    try:
        with open(registry_path, 'r', encoding='utf-8') as f:
            registry = json.load(f)
        
        # Znajdź stare entytie
        old_entities = []
        entities = registry.get("data", {}).get("entities", [])
        
        for entity in entities:
            entity_id = entity.get("entity_id", "")
            platform = entity.get("platform", "")
            
            # Sprawdź czy to stara entytia thessla_green_modbus
            if (platform == "thessla_green_modbus" and 
                ("rekuperator_predkosc" in entity_id or 
                 "rekuperator_predkosc" in entity.get("unique_id", ""))):
                old_entities.append(entity)
            
            # Sprawdź inne problematyczne wzorce
            for pattern in OLD_ENTITY_PATTERNS:
                if pattern.replace("thessla.*", "thessla") in entity_id:
                    if entity not in old_entities:
                        old_entities.append(entity)

        if old_entities:
            print(f"🗑️  Znaleziono {len(old_entities)} starych entytii do usunięcia:")
            for entity in old_entities:
                print(f"   - {entity['entity_id']} (platform: {entity.get('platform', 'unknown')})")
            
            # Usuń stare entytie
            registry["data"]["entities"] = [
                e for e in entities if e not in old_entities
            ]
            
            # Zapisz
            with open(registry_path, 'w', encoding='utf-8') as f:
                json.dump(registry, f, indent=2, ensure_ascii=False)
            
            print("✅ Entity registry zaktualizowany")
            return True
        else:
            print("✅ Nie znaleziono starych entytii do usunięcia")
            # Usuń niepotrzebny backup
            backup_path.unlink()
            return True
            
    except Exception as exc:
        print(f"❌ Błąd przetwarzania entity registry: {exc}")
        # Przywróć backup
        if backup_path.exists():
            shutil.copy2(backup_path, registry_path)
            print(f"🔄 Przywrócono backup z: {backup_path}")
        return False


def cleanup_automations(config_dir: Path) -> bool:
    """Wyczyść automatyzacje z referencjami do starych entytii."""
    automations_path = config_dir / "automations.yaml"
    
    if not automations_path.exists():
        print("ℹ️  Plik automations.yaml nie istnieje - pomijam")
        return True

    print(f"📁 Sprawdzam automatyzacje: {automations_path}")
    
    try:
        with open(automations_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Sprawdź czy są referencje do starych entytii
        problematic_refs = []
        for pattern in OLD_ENTITY_PATTERNS:
            if pattern.replace("thessla.*", "thessla") in content:
                problematic_refs.append(pattern)
        
        if problematic_refs:
            print(f"⚠️  Znaleziono {len(problematic_refs)} referencji do starych entytii:")
            for ref in problematic_refs:
                print(f"   - {ref}")
            print("❗ Sprawdź i zaktualizuj automatyzacje ręcznie")
            print(f"   Plik: {automations_path}")
            return False
        else:
            print("✅ Automatyzacje są czyste")
            return True
            
    except Exception as exc:
        print(f"❌ Błąd sprawdzania automatyzacji: {exc}")
        return False


def cleanup_configuration_yaml(config_dir: Path) -> bool:
    """Sprawdź configuration.yaml pod kątem starych referencji."""
    config_path = config_dir / "configuration.yaml"
    
    if not config_path.exists():
        print("❌ configuration.yaml nie znaleziony")
        return False

    print(f"📁 Sprawdzam konfigurację: {config_path}")
    
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Sprawdź problematyczne referencje
        issues = []
        
        for pattern in OLD_ENTITY_PATTERNS:
            if pattern.replace("thessla.*", "thessla") in content:
                issues.append(f"Referencja do {pattern}")
        
        # Sprawdź stare konfiguracje integracji
        if "thessla_green_modbus:" in content:
            issues.append("Stara konfiguracja YAML integracji (użyj UI)")
        
        if issues:
            print(f"⚠️  Znaleziono {len(issues)} problemów w konfiguracji:")
            for issue in issues:
                print(f"   - {issue}")
            print("❗ Sprawdź i zaktualizuj configuration.yaml ręcznie")
            return False
        else:
            print("✅ Konfiguracja jest czysta")
            return True
            
    except Exception as exc:
        print(f"❌ Błąd sprawdzania konfiguracji: {exc}")
        return False


def cleanup_custom_component_cache(config_dir: Path) -> bool:
    """Wyczyść cache komponentu niestandardowego."""
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