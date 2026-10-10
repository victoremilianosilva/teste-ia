
from pathlib import Path
import sys

import pytest

ROOT = Path(__file__).resolve().parent.parent
ENGINE_DIR = ROOT / "cpp" / "build" / "bin" / "Release"

sys.path.insert(0, str(ENGINE_DIR))

ce = pytest.importorskip("combat_engine")


def criar_unidade(nome, unit_id, team, x, y, hp, dano):
    unit = ce.CombatUnit()

    unit.id = unit_id
    unit.name = nome
    unit.api_name = nome
    unit.team = team

    unit.position.x = x
    unit.position.y = y

    unit.max_hp = hp
    unit.hp = hp
    unit.attack_damage = dano
    unit.attack_speed = 1.0
    unit.attack_range = 1.0

    unit.armor = 30.0
    unit.magic_resist = 30.0
    unit.max_mana = 100.0
    unit.mana = 0.0
    unit.star = 1

    unit.alive = True
    unit.can_attack = True
    unit.can_cast = True
    unit.can_move = True
    unit.role = ce.UnitRole.FIGHTER

    return unit


def criar_combate(seed=42):
    combat = ce.CombatInput()

    config = combat.config
    config.board_cols = 7
    config.board_rows = 4
    config.max_duration = 30.0
    config.max_events = 100000
    config.deterministic = True
    config.seed = seed

    config.record_events = True
    config.record_damage = True
    config.record_positions = True

    combat.context = ce.CombatContext.PVP
    combat.seed = seed

    team_a = combat.player_a
    team_a.player_id = 1
    team_a.team = ce.UnitTeam.PLAYER_A
    team_a.player_hp = 100.0
    team_a.units = [
        criar_unidade(
            "Lutador_A", 1, ce.UnitTeam.PLAYER_A,
            1, 1, 500.0, 50.0,
        )
    ]

    team_b = combat.player_b
    team_b.player_id = 2
    team_b.team = ce.UnitTeam.PLAYER_B
    team_b.player_hp = 100.0
    team_b.units = [
        criar_unidade(
            "Lutador_B", 2, ce.UnitTeam.PLAYER_B,
            5, 1, 500.0, 40.0,
        )
    ]

    return combat


def assinatura_resultado(result):
    """Extrai os resultados observáveis para comparação."""
    unidades = sorted(
        (
            unit.unit_id,
            str(unit.team),
            unit.survived,
            unit.initial_hp,
            unit.final_hp,
            unit.damage_dealt,
            unit.damage_taken,
            unit.kills,
            unit.attacks,
            unit.final_x,
            unit.final_y,
        )
        for unit in result.units
    )

    return (
        result.success,
        result.completed,
        str(result.winner),
        result.timeout,
        result.duration,
        result.events_processed,
        result.player_a_survivors,
        result.player_b_survivors,
        result.player_a_deaths,
        result.player_b_deaths,
        result.player_a_damage_dealt,
        result.player_b_damage_dealt,
        len(result.events),
        len(result.damage_events),
        len(result.position_events),
        unidades,
    )


def test_simulacao_deterministica_mesma_seed():
    resultado_a = ce.simulate(criar_combate(seed=42))
    resultado_b = ce.simulate(criar_combate(seed=42))

    assert resultado_a.success, (
        f"Primeira simulação falhou: "
        f"{resultado_a.error_code} - {resultado_a.error_message}"
    )
    assert resultado_b.success, (
        f"Segunda simulação falhou: "
        f"{resultado_b.error_code} - {resultado_b.error_message}"
    )

    assert resultado_a.completed
    assert resultado_b.completed

    assert assinatura_resultado(resultado_a) == assinatura_resultado(
        resultado_b
    ), "Duas simulações com a mesma seed produziram resultados diferentes."
