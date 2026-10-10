
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
BUILD_DIR = ROOT / "cpp" / "build" / "bin" / "Release"

sys.path.insert(0, str(BUILD_DIR))

ce = pytest.importorskip("combat_engine")


def make_unit(
    unit_id,
    team,
    x,
    hp=100.0,
    damage=20.0,
    attack_range=1.0,
):
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

    unit.hp = float(hp)
    unit.max_hp = float(hp)
    unit.attack_damage = float(damage)
    unit.attack_speed = 1.0
    unit.attack_range = float(attack_range)
    unit.armor = 0.0
    unit.magic_resist = 0.0

    unit.critical_strike_chance = 0.0
    unit.critical_strike_damage = 1.5
    unit.damage_amplification = 0.0
    unit.damage_reduction = 0.0

    unit.alive = True
    unit.can_move = True
    unit.can_attack = True
    unit.can_cast = True

    return unit


def run_battle(units_a, units_b, max_duration=10.0):
    combat = ce.CombatInput()
    combat.context = ce.CombatContext.PVP
    combat.seed = 42

    config = ce.CombatConfig()
    config.board_rows = 4
    config.board_cols = 7
    config.max_duration = max_duration
    config.max_events = 10_000
    config.deterministic = True
    config.seed = 42
    config.record_events = True
    config.record_damage = True
    config.record_positions = True

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
        f"Falha no motor: {result.error_code} - "
        f"{result.error_message}"
    )
    assert result.completed, "O combate não foi concluído."

    return result


def test_combate_registra_eventos():
    """Um combate ativo deve produzir eventos observáveis."""
    result = run_battle(
        units_a=[
            make_unit(
                1, ce.UnitTeam.PLAYER_A,
                x=2, hp=500, damage=30,
            )
        ],
        units_b=[
            make_unit(
                2, ce.UnitTeam.PLAYER_B,
                x=3, hp=500, damage=30,
            )
        ],
    )

    assert result.events_processed > 0
    assert len(result.events) > 0


def test_dano_e_registrado_durante_o_combate():
    """Ataques que causam dano devem aparecer nos registros de dano."""
    result = run_battle(
        units_a=[
            make_unit(
                10, ce.UnitTeam.PLAYER_A,
                x=2, hp=1000, damage=50,
            )
        ],
        units_b=[
            make_unit(
                11, ce.UnitTeam.PLAYER_B,
                x=3, hp=1000, damage=10,
            )
        ],
    )

    assert len(result.damage_events) > 0

    total_damage = sum(
        float(unit.damage_dealt)
        for unit in result.units
    )

    assert total_damage > 0


def test_unidade_derrotada_nao_conta_como_sobrevivente():
    """Uma unidade eliminada não deve continuar viva no resultado."""
    result = run_battle(
        units_a=[
            make_unit(
                20, ce.UnitTeam.PLAYER_A,
                x=2, hp=1000, damage=500,
            )
        ],
        units_b=[
            make_unit(
                21, ce.UnitTeam.PLAYER_B,
                x=3, hp=100, damage=0,
            )
        ],
    )

    unit_b = next(
        unit for unit in result.units
        if unit.unit_id == 21
    )

    assert unit_b.survived is False
    assert unit_b.final_hp <= 0
    assert result.player_b_survivors == 0
    assert result.player_b_deaths == 1
    assert result.winner == ce.CombatWinner.PLAYER_A




def test_contagem_de_sobreviventes_corresponde_ao_resultado():
    """A contagem de sobreviventes deve refletir as unidades finais."""
    unit_a1 = make_unit(
        30, ce.UnitTeam.PLAYER_A,
        x=2, hp=1000, damage=500,
    )
    unit_a1.position.y = 1

    unit_a2 = make_unit(
        31, ce.UnitTeam.PLAYER_A,
        x=2, hp=1000, damage=500,
    )
    unit_a2.position.y = 2

    result = run_battle(
        units_a=[unit_a1, unit_a2],
        units_b=[
            make_unit(
                32, ce.UnitTeam.PLAYER_B,
                x=3, hp=100, damage=0,
            )
        ],
    )

    actual_a = sum(
        1 for unit in result.units
        if unit.team == ce.UnitTeam.PLAYER_A
        and unit.survived
    )

    actual_b = sum(
        1 for unit in result.units
        if unit.team == ce.UnitTeam.PLAYER_B
        and unit.survived
    )

    assert actual_a == result.player_a_survivors
    assert actual_b == result.player_b_survivors



def test_hp_final_nao_ultrapassa_hp_maximo():
    """O resultado não deve indicar HP final acima do máximo."""
    result = run_battle(
        units_a=[
            make_unit(
                40, ce.UnitTeam.PLAYER_A,
                x=2, hp=500, damage=25,
            )
        ],
        units_b=[
            make_unit(
                41, ce.UnitTeam.PLAYER_B,
                x=3, hp=500, damage=25,
            )
        ],
    )

    for unit in result.units:
        assert unit.final_hp <= unit.initial_hp
        assert unit.final_hp >= 0
