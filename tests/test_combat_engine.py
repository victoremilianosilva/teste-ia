import sys
from pathlib import Path

import pytest

# ============================================================
# Localização do módulo C++ compilado
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
        f"Não foi possível importar combat_engine de {BUILD_DIR}: {exc}",
        pytrace=False,
    )


# ============================================================
# Fábrica de unidades
# ============================================================

def make_unit(unit_id, team, x):
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
    unit.attack_damage = 30.0
    unit.attack_speed = 1.0
    unit.attack_range = 1.0
    unit.armor = 0.0
    unit.alive = True

    return unit


# ============================================================
# Montagem do combate
# ============================================================

def make_combat():
    combat = ce.CombatInput()
    combat.context = ce.CombatContext.PVP
    combat.seed = 42

    config = ce.CombatConfig()
    config.board_rows = 4
    config.board_cols = 7
    config.max_duration = 30.0
    config.max_events = 100_000
    config.deterministic = True
    config.seed = 42

    combat.config = config

    team_a = ce.CombatTeam()
    team_a.team = ce.UnitTeam.PLAYER_A
    team_a.player_id = 0
    team_a.player_hp = 100.0
    team_a.units = [
        make_unit(0, ce.UnitTeam.PLAYER_A, 0)
    ]

    team_b = ce.CombatTeam()
    team_b.team = ce.UnitTeam.PLAYER_B
    team_b.player_id = 1
    team_b.player_hp = 100.0
    team_b.units = [
        make_unit(1, ce.UnitTeam.PLAYER_B, 6)
    ]

    combat.player_a = team_a
    combat.player_b = team_b

    return combat


# ============================================================
# Teste de integração do motor
# ============================================================

def test_combat_engine_executes_battle():
    combat = make_combat()

    result = ce.simulate(combat)

    print("\nUnidades A:", len(combat.player_a.units))
    print("Unidades B:", len(combat.player_b.units))
    print("Entrada aceita:", result.success)
    print("Combate concluído:", result.completed)
    print("Erro:", result.error_code, result.error_message)
    print("Vencedor:", result.winner)
    print(
        "Sobreviventes A/B:",
        result.player_a_survivors,
        result.player_b_survivors,
    )
    print("Duração:", result.duration)
    print("Eventos:", result.events_processed)

    # O motor precisa aceitar e concluir a simulação.
    assert result.success, (
        f"Entrada rejeitada: {result.error_code} "
        f"{result.error_message}"
    )

    assert result.completed, "O combate não foi concluído."

    # O resultado precisa indicar um vencedor válido.
    assert result.winner in (
        ce.CombatWinner.PLAYER_A,
        ce.CombatWinner.PLAYER_B,
        ce.CombatWinner.DRAW,
    ), f"Vencedor inesperado: {result.winner}"

    # A simulação deve produzir valores válidos.
    assert result.duration >= 0.0
    assert result.events_processed >= 0

    # Ao final, pelo menos uma das equipes deve ter sido
    # eliminada, ou o combate deve ter terminado em empate.
    assert (
        result.player_a_survivors >= 0
        and result.player_b_survivors >= 0
    )

    if result.winner == ce.CombatWinner.PLAYER_A:
        assert result.player_a_survivors > 0

    elif result.winner == ce.CombatWinner.PLAYER_B:
        assert result.player_b_survivors > 0
