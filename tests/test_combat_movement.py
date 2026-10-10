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

def make_unit(unit_id, team, x, attack_range):
    unit = ce.CombatUnit()
    unit.id = unit_id
    unit.name = f"Unit-{unit_id}"
    unit.star = 1
    unit.team = team
    unit.role = ce.UnitRole.FIGHTER

    position = ce.CombatPosition()
    position.x = x
    position.y = 1
    unit.position = position

    unit.hp = 100.0
    unit.max_hp = 100.0
    unit.attack_damage = 25.0
    unit.attack_speed = 1.0
    unit.attack_range = attack_range
    unit.armor = 0.0
    unit.alive = True

    return unit


# ============================================================
# Execução do combate
# ============================================================

def run_battle(attack_range):
    combat = ce.CombatInput()
    combat.context = ce.CombatContext.PVP
    combat.seed = 42

    config = ce.CombatConfig()
    config.board_rows = 4
    config.board_cols = 7
    config.max_duration = 10.0
    config.max_events = 10_000
    config.deterministic = True
    config.seed = 42
    config.record_events = True
    config.record_positions = True

    combat.config = config

    team_a = ce.CombatTeam()
    team_a.team = ce.UnitTeam.PLAYER_A
    team_a.player_id = 0
    team_a.player_hp = 100.0
    team_a.units = [
        make_unit(0, ce.UnitTeam.PLAYER_A, 1, attack_range)
    ]

    team_b = ce.CombatTeam()
    team_b.team = ce.UnitTeam.PLAYER_B
    team_b.player_id = 1
    team_b.player_hp = 100.0
    team_b.units = [
        make_unit(1, ce.UnitTeam.PLAYER_B, 3, attack_range)
    ]

    combat.player_a = team_a
    combat.player_b = team_b

    result = ce.simulate(combat)

    assert result.success, (
        f"Alcance {attack_range}: "
        f"{result.error_code}: {result.error_message}"
    )

    assert result.completed, (
        f"Alcance {attack_range}: combate não concluído."
    )

    return result


# ============================================================
# TESTE 1: Unidades com alcance 2 não precisam se aproximar
# ============================================================

def test_units_with_range_two_do_not_need_to_move():
    result = run_battle(attack_range=2.0)

    print(
        "\n--- Teste de alcance 2 ---",
        "\nVencedor:", result.winner,
        "\nDuração:", result.duration,
        "\nEventos:", result.events_processed,
        "\nMovimentações:", len(result.position_events),
        "\nAtaques:", len(result.attack_events),
    )

    assert len(result.position_events) == 0, (
        "As unidades com alcance 2 deveriam conseguir atacar "
        "das posições iniciais, sem se movimentar."
    )


# ============================================================
# TESTE 2: Unidades com alcance 1 precisam se aproximar
# ============================================================

def test_units_with_range_one_need_to_move():
    result = run_battle(attack_range=1.0)

    print(
        "\n--- Teste de alcance 1 ---",
        "\nVencedor:", result.winner,
        "\nDuração:", result.duration,
        "\nEventos:", result.events_processed,
        "\nMovimentações:", len(result.position_events),
        "\nAtaques:", len(result.attack_events),
    )

    assert len(result.position_events) > 0, (
        "Esperava-se ao menos uma movimentação com alcance 1."
    )


# ============================================================
# TESTE 3: Ambos os combates devem ser reproduzíveis
# ============================================================

def test_movement_combat_is_deterministic():
    first = run_battle(attack_range=1.0)
    second = run_battle(attack_range=1.0)

    assert first.winner == second.winner
    assert first.duration == pytest.approx(second.duration)
    assert first.events_processed == second.events_processed
    assert len(first.position_events) == len(second.position_events)
    assert len(first.attack_events) == len(second.attack_events)