
import sys
from pathlib import Path

import pytest

# Localiza a raiz do projeto e importa o CombatProfileManager.
ROOT = Path(__file__).resolve().parent.parent

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

try:
    from combat.CombatProfileManager import (
        CombatProfileManager,
        UnitRole,
    )
except ImportError as exc:
    pytest.fail(
        f"Não foi possível importar CombatProfileManager: {exc}",
        pytrace=False,
    )


@pytest.fixture
def manager():
    """Cria um gerenciador isolado para cada teste."""
    return CombatProfileManager()


def test_process_unit_none_returns_none(manager):
    """Unidade inexistente deve ser tratada sem erro."""
    assert manager.process_unit(None) is None


def test_process_unit_adds_role_and_combat_profile(manager):
    """O processamento deve adicionar os campos esperados."""
    unit = {
        "apiName": "TestTank",
        "max_hp": 1200,
        "armor": 50,
        "magic_resist": 45,
        "attack_range": 1,
        "attack_damage": 40,
        "attack_speed": 0.6,
    }

    result = manager.process_unit(unit)

    assert result is unit
    assert "role" in result
    assert "combat_profile" in result
    assert result["role"] == result["combat_profile"]["role"]


def test_profile_contains_required_fields(manager):
    """O perfil deve conter os dados básicos de combate e posicionamento."""
    unit = {
        "apiName": "TestUnit",
        "max_hp": 500,
        "attack_damage": 60,
        "attack_speed": 0.7,
        "attack_range": 2,
        "armor": 20,
        "magic_resist": 15,
        "max_mana": 100,
    }

    profile = manager.get_profile(unit)

    required_fields = {
        "role",
        "role_name",
        "frontline",
        "backline",
        "is_tank",
        "is_carry",
        "is_support",
        "is_fighter",
        "is_assassin",
        "attack_range",
        "attack_speed",
        "attack_damage",
        "armor",
        "magic_resist",
        "max_hp",
        "max_mana",
    }

    assert required_fields.issubset(profile.keys())


def test_high_defensive_stats_infer_tank(manager):
    """Stats defensivos elevados devem favorecer o papel de tank."""
    unit = {
        "apiName": "TestTank",
        "max_hp": 1500,
        "armor": 60,
        "magic_resist": 60,
        "attack_range": 1,
    }

    assert manager.get_role(unit) == UnitRole.TANK


def test_high_attack_damage_and_speed_infer_carry(manager):
    """Dano e velocidade de ataque elevados devem favorecer carry."""
    unit = {
        "apiName": "TestCarry",
        "max_hp": 400,
        "attack_damage": 100,
        "attack_speed": 1.0,
        "attack_range": 4,
    }

    assert manager.get_role(unit) == UnitRole.CARRY


def test_assassin_role_uses_ability_description(manager):
    """A descrição da habilidade deve contribuir para inferir assassinos."""
    unit = {
        "apiName": "TestAssassin",
        "max_hp": 400,
        "attack_damage": 30,
        "attack_speed": 0.5,
        "attack_range": 1,
        "ability": {
            "description": "Dash toward the backline and target the furthest enemy"
        },
    }

    assert manager.get_role(unit) == UnitRole.ASSASSIN


def test_tank_is_frontline(manager):
    """Tank deve ser classificado como unidade de linha de frente."""
    unit = {
        "apiName": "FrontTank",
        "max_hp": 1500,
        "armor": 60,
        "magic_resist": 60,
        "attack_range": 1,
    }

    assert manager.is_frontline(unit) is True
    assert manager.is_backline(unit) is False


def test_carry_is_backline(manager):
    """Carry deve ser classificado como unidade de retaguarda."""
    unit = {
        "apiName": "BackCarry",
        "max_hp": 400,
        "attack_damage": 100,
        "attack_speed": 1.0,
        "attack_range": 4,
    }

    assert manager.is_backline(unit) is True
    assert manager.is_frontline(unit) is False


def test_none_defaults_to_fighter(manager):
    """A API de papel deve usar fighter quando a unidade é None."""
    assert manager.get_role(None) == UnitRole.FIGHTER
    assert manager.is_fighter(None) is True


def test_build_combat_input_contains_basic_stats(manager):
    """A conversão para entrada de combate deve preservar os atributos."""
    unit = {
        "apiName": "CombatUnit",
        "star": 2,
        "hp": 700,
        "max_hp": 900,
        "mana": 20,
        "max_mana": 100,
        "attack_damage": 80,
        "attack_speed": 0.9,
        "armor": 35,
        "magic_resist": 25,
        "attack_range": 3,
    }

    combat_input = manager.build_combat_input(unit)

    assert combat_input["id"] == "CombatUnit"
    assert combat_input["star"] == 2
    assert combat_input["hp"] == 700
    assert combat_input["max_hp"] == 900
    assert combat_input["mana"] == 20
    assert combat_input["max_mana"] == 100
    assert combat_input["attack_damage"] == 80
    assert combat_input["attack_speed"] == pytest.approx(0.9)
    assert combat_input["armor"] == 35
    assert combat_input["magic_resist"] == 25
    assert combat_input["attack_range"] == 3
    assert isinstance(combat_input["role"], int)


def test_clear_cache_removes_cached_profiles(manager):
    """Limpar o cache deve remover os perfis armazenados."""
    unit = {
        "apiName": "CachedUnit",
        "max_hp": 500,
        "attack_damage": 50,
    }

    manager.get_profile(unit)

    assert "CachedUnit" in manager._profile_cache

    manager.clear_cache()

    assert manager._profile_cache == {}


def test_reset_clears_cache(manager):
    """Reset deve limpar o cache do gerenciador."""
    unit = {
        "apiName": "ResetUnit",
        "max_hp": 500,
    }

    manager.get_profile(unit)
    manager.reset()

    assert manager._profile_cache == {}


def test_invalid_numeric_value_uses_default(manager):
    """Valores numéricos inválidos devem usar o valor padrão."""
    unit = {
        "apiName": "InvalidStats",
        "attack_range": "invalid",
        "attack_speed": None,
        "attack_damage": 50,
    }

    profile = manager.get_profile(unit)

    assert profile["attack_range"] == 0.0
    assert profile["attack_speed"] == 0.0
    assert profile["attack_damage"] == 50.0
