import sys
from pathlib import Path

import pytest


# ============================================================
# Configuração do módulo C++
# ============================================================

ROOT = Path(__file__).resolve().parent.parent
BUILD_DIR = ROOT / "cpp" / "build" / "bin" / "Release"

if not BUILD_DIR.exists():
    pytest.fail(
        f"Diretório do motor C++ não encontrado: {BUILD_DIR}",
        pytrace=False,
    )

sys.path.insert(0, str(BUILD_DIR))

try:
    import combat_engine as ce
except ImportError as exc:
    pytest.fail(
        f"Não foi possível importar combat_engine: {exc}",
        pytrace=False,
    )


# ============================================================
# Criação de unidades
# ============================================================

def make_unit(unit_id, team, x, attack_damage, armor=0.0):
    unit = ce.CombatUnit()
    unit.id = unit_id
    unit.name = f"Unit-{unit_id}"
    unit.star = 1
    unit.team = team

    position = ce.CombatPosition()
    position.x = x
    position.y = 1
    unit.position = position

    unit.hp = 1000.0
    unit.max_hp = 1000.0
    unit.attack_damage = float(attack_damage)
    unit.attack_speed = 1.0
    unit.attack_range = 1.0
    unit.armor = float(armor)

    # Desabilita efeitos aleatórios de crítico.
    unit.critical_strike_chance = 0.0
    unit.critical_strike_damage = 1.5
    unit.damage_amplification = 0.0
    unit.damage_reduction = 0.0

    unit.alive = True
    unit.can_move = True
    unit.can_attack = True

    return unit


# ============================================================
# Execução de um combate controlado
# ============================================================

def run_battle(attack_damage_a=20.0, armor_b=0.0):
    combat = ce.CombatInput()
    combat.context = ce.CombatContext.PVP
    combat.seed = 42

    config = ce.CombatConfig()
    config.board_rows = 4
    config.board_cols = 7
    config.max_duration = 2.0
    config.max_events = 10_000
    config.deterministic = True
    config.seed = 42

    combat.config = config

    team_a = ce.CombatTeam()
    team_a.team = ce.UnitTeam.PLAYER_A
    team_a.player_id = 0
    team_a.player_hp = 100.0
    team_a.units = [
        make_unit(
            0,
            ce.UnitTeam.PLAYER_A,
            2,
            attack_damage=attack_damage_a,
        )
    ]

    team_b = ce.CombatTeam()
    team_b.team = ce.UnitTeam.PLAYER_B
    team_b.player_id = 1
    team_b.player_hp = 100.0
    team_b.units = [
        make_unit(
            1,
            ce.UnitTeam.PLAYER_B,
            3,
            attack_damage=20.0,
            armor=armor_b,
        )
    ]

    combat.player_a = team_a
    combat.player_b = team_b

    result = ce.simulate(combat)

    assert result.success, (
        f"Falha na simulação: "
        f"{result.error_code}: {result.error_message}"
    )

    assert result.completed, "O combate não foi concluído."

    # Recupera os resultados individuais das unidades.
    units = list(result.units)

    unit_a = next(
        (unit for unit in units if unit.unit_id == 0),
        None,
    )
    unit_b = next(
        (unit for unit in units if unit.unit_id == 1),
        None,
    )

    assert unit_a is not None, "Resultado da unidade A ausente."
    assert unit_b is not None, "Resultado da unidade B ausente."

    return {
        "damage_a": float(unit_a.damage_dealt),
        "damage_b": float(unit_b.damage_dealt),
        "hp_a": float(unit_a.final_hp),
        "hp_b": float(unit_b.final_hp),
        "result": result,
    }


# ============================================================
# TESTE 1: Armadura reduz o dano recebido
# ============================================================

def test_armor_reduces_incoming_damage():
    base = run_battle(
        attack_damage_a=20.0,
        armor_b=0.0,
    )

    armored = run_battle(
        attack_damage_a=20.0,
        armor_b=100.0,
    )

    print("\n--- Teste de armadura ---")
    print("Dano recebido sem armadura:", base["damage_a"])
    print("Dano recebido com armadura:", armored["damage_a"])

    assert armored["damage_a"] < base["damage_a"], (
        "A armadura deveria reduzir o dano causado pela unidade A."
    )


# ============================================================
# TESTE 2: Aumentar o ataque aumenta o dano causado
# ============================================================

def test_higher_attack_damage_increases_damage_dealt():
    base = run_battle(
        attack_damage_a=20.0,
        armor_b=0.0,
    )

    stronger = run_battle(
        attack_damage_a=40.0,
        armor_b=0.0,
    )

    print("\n--- Teste de poder de ataque ---")
    print("Dano com ataque 20:", base["damage_a"])
    print("Dano com ataque 40:", stronger["damage_a"])

    assert stronger["damage_a"] > base["damage_a"], (
        "Aumentar o ataque de 20 para 40 deveria aumentar "
        "o dano total causado pela unidade A."
    )