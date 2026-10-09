
import sys
from pathlib import Path

# Localiza o módulo C++ compilado no Windows.
ROOT = Path(__file__).resolve().parent
BUILD_DIR = ROOT / "cpp" / "build" / "bin" / "Release"
sys.path.insert(0, str(BUILD_DIR))

import combat_engine as ce


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
    config.record_events = True
    config.record_positions = True
    combat.config = config

    # As unidades começam a duas casas de distância.
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

    return ce.simulate(combat)


# ------------------------------------------------------------
# TESTE A: alcance 2 — já conseguem atacar a partir da posição inicial.
# TESTE B: alcance 1 — precisam se aproximar primeiro.
# ------------------------------------------------------------

long_range = run_battle(attack_range=2.0)
short_range = run_battle(attack_range=1.0)

for name, result in [
    ("Alcance 2", long_range),
    ("Alcance 1", short_range),
]:
    print(f"\n--- {name} ---")
    print("Sucesso:", result.success)
    print("Concluído:", result.completed)
    print("Erro:", result.error_code, result.error_message)
    print("Vencedor:", result.winner)
    print("Duração:", result.duration)
    print("Eventos processados:", result.events_processed)
    print("Movimentações:", len(result.position_events))
    print("Ataques:", len(result.attack_events))

    assert result.success, f"{name}: entrada rejeitada"
    assert result.completed, f"{name}: combate não concluído"

assert len(long_range.position_events) == 0, (
    "Com alcance 2, as unidades deveriam atacar sem se mover."
)

assert len(short_range.position_events) > 0, (
    "Com alcance 1, esperávamos ao menos uma movimentação."
)

print("\n✅ Teste de movimentação e alcance passou.")