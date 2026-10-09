import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
BUILD_DIR = ROOT / "cpp" / "build" / "bin" / "Release"
sys.path.insert(0, str(BUILD_DIR))

import combat_engine as ce


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
    unit.max_hp = 1000.0
    unit.attack_damage = 0.0  # Não causa dano neste teste.
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
        f"{result.error_code}: {result.error_message}"
    )
    assert result.completed, "O combate não foi concluído."
    assert result.timeout, (
        "O combate deveria ter atingido o limite de tempo."
    )

    return result


# TESTE 1:
# A tem dois sobreviventes com pouca vida.
# B tem apenas um sobrevivente com muita vida.
# A deve ganhar porque tem mais sobreviventes.
result_survivors = run_battle(
    units_a=[
        make_unit(0, ce.UnitTeam.PLAYER_A, 0, 0, hp=10),
        make_unit(1, ce.UnitTeam.PLAYER_A, 0, 1, hp=10),
    ],
    units_b=[
        make_unit(2, ce.UnitTeam.PLAYER_B, 6, 3, hp=1000),
    ],
)

print(
    "Teste de sobreviventes:",
    result_survivors.winner,
    "| A:", result_survivors.player_a_survivors,
    "| B:", result_survivors.player_b_survivors,
)

assert result_survivors.winner == ce.CombatWinner.PLAYER_A
assert result_survivors.player_a_survivors == 2
assert result_survivors.player_b_survivors == 1


# TESTE 2:
# Mesmo número de sobreviventes.
# A termina com mais vida total e deve ganhar.
result_hp = run_battle(
    units_a=[
        make_unit(10, ce.UnitTeam.PLAYER_A, 0, 0, hp=500),
    ],
    units_b=[
        make_unit(11, ce.UnitTeam.PLAYER_B, 6, 3, hp=100),
    ],
)

print(
    "Teste de vida restante:",
    result_hp.winner,
    "| A:", result_hp.units[0].final_hp,
    "| B:", result_hp.units[1].final_hp,
)

assert result_hp.player_a_survivors == result_hp.player_b_survivors
assert result_hp.winner == ce.CombatWinner.PLAYER_A

print("\\n✅ Testes de timeout e desempate passaram.")