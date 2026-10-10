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

def make_unit(unit_id, team, x, y, hp=100.0):
    unit = ce.CombatUnit()
    unit.id = unit_id
    unit.name = f"Unit-{unit_id}"
    unit.star = 1
    unit.team = team

    pos = ce.CombatPosition()
    pos.x = x
    pos.y = y
    unit.position = pos

    unit.hp = float(hp)
    unit.max_hp = max(1000.0, float(hp))
    unit.attack_damage = 0.0
    unit.attack_speed = 1.0
    unit.attack_range = 0.0
    unit.armor = 0.0
    unit.critical_strike_chance = 0.0
    unit.critical_strike_damage = 1.5
    unit.damage_amplification = 0.0
    unit.damage_reduction = 0.0
    unit.alive = True
    unit.can_move = True
    unit.can_attack = True

    return unit


# ============================================================
# Execução do combate
# ============================================================

def run_battle(units_a, units_b):
    combat = ce.CombatInput()
    combat.context = ce.CombatContext.PVP
    combat.seed = 42

    config = ce.CombatConfig()
    config.board_rows = 4
    config.board_cols = 7
    config.max_duration = 0.01
    config.max_events = 10_000
    config.deterministic = True
    config.seed = 42

    combat.config = config

    team_a = ce.CombatTeam()
    team_a.team = ce.UnitTeam.PLAYER_A
    team_a.player_id = 0
    team_a.player_hp = 100.0
    team_a.units = units_a

    team_b = ce.CombatTeam()
    team_b.team = ce.UnitTeam.PLAYER_B
    team_b.player_id = 1
    team_b.player_hp = 100.0
    team_b.units = units_b

    combat.player_a = team_a
    combat.player_b = team_b

    result = ce.simulate(combat)

    assert result.success, (
        f"Falha na simulação: "
        f"{result.error_code}: {result.error_message}"
    )

    assert result.completed, "O combate não foi concluído."

    assert result.timeout, (
        "Esperava-se que o combate terminasse por timeout."
    )

    return result


# ============================================================
# TESTE 1: Desempate pelo número de sobreviventes
# ============================================================

def test_timeout_tiebreak_by_survivors():
    result = run_battle(
        units_a=[
            make_unit(0, ce.UnitTeam.PLAYER_A, 0, 0, hp=10),
            make_unit(1, ce.UnitTeam.PLAYER_A, 0, 1, hp=10),
        ],
        units_b=[
            make_unit(2, ce.UnitTeam.PLAYER_B, 6, 3, hp=1000),
        ],
    )

    print(
        "\nTeste de sobreviventes:",
        result.winner,
        "| A:", result.player_a_survivors,
        "| B:", result.player_b_survivors,
        "| Timeout:", result.timeout,
    )

    assert result.player_a_survivors == 2
    assert result.player_b_survivors == 1

    assert result.winner == ce.CombatWinner.PLAYER_A, (
        "A deveria vencer por ter mais unidades sobreviventes."
    )


# ============================================================
# TESTE 2: Desempate pela vida restante
# ============================================================

def test_timeout_tiebreak_by_remaining_hp():
    result = run_battle(
        units_a=[
            make_unit(10, ce.UnitTeam.PLAYER_A, 0, 0, hp=500),
        ],
        units_b=[
            make_unit(11, ce.UnitTeam.PLAYER_B, 6, 3, hp=100),
        ],
    )

    print(
        "\nTeste de vida restante:",
        result.winner,
        "| Sobreviventes A:", result.player_a_survivors,
        "| Sobreviventes B:", result.player_b_survivors,
        "| Timeout:", result.timeout,
    )

    assert result.player_a_survivors == 1
    assert result.player_b_survivors == 1

    assert result.winner == ce.CombatWinner.PLAYER_A, (
        "A deveria vencer pelo critério de vida restante."
    )
