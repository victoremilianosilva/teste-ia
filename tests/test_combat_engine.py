
import sys
from pathlib import Path

root = Path(__file__).resolve().parent
sys.path.insert(
    0,
    str(root / "cpp" / "build" / "bin" / "Release"),
)

import combat_engine as ce

combat = ce.CombatInput()
combat.config.board_rows = 4
combat.config.board_cols = 7
combat.config.max_duration = 30.0
combat.config.max_events = 100_000
combat.config.deterministic = True
combat.config.seed = 42

def make_unit(unit_id, team, x):
    unit = ce.CombatUnit()
    unit.id = unit_id
    unit.name = f"Unit-{unit_id}"
    unit.star = 1
    unit.team = team
    unit.role = ce.UnitRole.FIGHTER

    pos = ce.CombatPosition()
    pos.x = x
    pos.y = 1
    unit.position = pos

    unit.hp = 100.0
    unit.max_hp = 100.0
    unit.attack_damage = 30.0
    unit.attack_speed = 1.0
    unit.attack_range = 1.0
    unit.armor = 0.0
    unit.alive = True

    return unit

a = ce.CombatTeam()
a.team = ce.UnitTeam.PLAYER_A
a.player_id = 0
a.player_hp = 100.0
a.units = [make_unit(0, ce.UnitTeam.PLAYER_A, 0)]

b = ce.CombatTeam()
b.team = ce.UnitTeam.PLAYER_B
b.player_id = 1
b.player_hp = 100.0
b.units = [make_unit(1, ce.UnitTeam.PLAYER_B, 6)]

print("Unidades A:", len(a.units))
print("Unidades B:", len(b.units))

combat.player_a = a
combat.player_b = b

result = ce.simulate(combat)

print("Entrada aceita:", result.success)
print("Combate concluído:", result.completed)
print("Erro:", result.error_code, result.error_message)
print("Vencedor:", result.winner)
print("Sobreviventes A/B:",
      result.player_a_survivors,
      result.player_b_survivors)
print("Duração:", result.duration)
print("Eventos:", result.events_processed)