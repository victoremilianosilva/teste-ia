
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
BUILD_DIR = ROOT / "cpp" / "build" / "bin" / "Release"
sys.path.insert(0, str(BUILD_DIR))

import combat_engine as ce


def make_unit(unit_id, team, x, attack_damage, armor=0.0):
    unit = ce.CombatUnit()
    unit.id = unit_id
    unit.name = f"Unit-{unit_id}"
    unit.star = 1
    unit.team = team

    pos = ce.CombatPosition()
    pos.x = x
    pos.y = 1
    unit.position = pos

    unit.hp = 1000.0
    unit.max_hp = 1000.0
    unit.attack_damage = float(attack_damage)
    unit.attack_speed = 1.0
    unit.attack_range = 1.0
    unit.armor = float(armor)

    # Remove variáveis aleatórias para isolar o teste.
    unit.critical_strike_chance = 0.0
    unit.critical_strike_damage = 1.5
    unit.damage_amplification = 0.0
    unit.damage_reduction = 0.0

    unit.alive = True
    unit.can_move = True
    unit.can_attack = True

    return unit


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
            0, ce.UnitTeam.PLAYER_A, 2,
            attack_damage=attack_damage_a,
        )
    ]

    team_b = ce.CombatTeam()
    team_b.team = ce.UnitTeam.PLAYER_B
    team_b.player_id = 1
    team_b.player_hp = 100.0
    team_b.units = [
        make_unit(
            1, ce.UnitTeam.PLAYER_B, 3,
            attack_damage=20.0,
            armor=armor_b,
        )
    ]

    combat.player_a = team_a
    combat.player_b = team_b

    result = ce.simulate(combat)

    assert result.success, (
        f"Erro no motor: {result.error_code} "
        f"{result.error_message}"
    )
    assert result.completed, "O combate não foi concluído."

    # Busca o dano total causado por cada unidade.
    units = list(result.units)
    unit_a = next(u for u in units if u.unit_id == 0)
    unit_b = next(u for u in units if u.unit_id == 1)

    return {
        "damage_a": float(unit_a.damage_dealt),
        "damage_b": float(unit_b.damage_dealt),
        "hp_a": float(unit_a.final_hp),
        "hp_b": float(unit_b.final_hp),
    }


# Cenário base: ataque 20 contra armadura 0.
base = run_battle(attack_damage_a=20, armor_b=0)

# Cenário defensivo: a unidade B recebe 100 de armadura.
armored = run_battle(attack_damage_a=20, armor_b=100)

# Cenário ofensivo: a unidade A passa a atacar com 40.
stronger = run_battle(attack_damage_a=40, armor_b=0)

print("Base:", base)
print("Com armadura:", armored)
print("Com ataque aumentado:", stronger)

# A armadura de B deve reduzir o dano causado por A.
assert armored["damage_a"] < base["damage_a"], (
    "A armadura não reduziu o dano recebido."
)

# Aumentar o ataque de A deve aumentar seu dano causado.
assert stronger["damage_a"] > base["damage_a"], (
    "Aumentar o ataque não aumentou o dano causado."
)

print("\n✅ Testes de ataque e armadura passaram.")