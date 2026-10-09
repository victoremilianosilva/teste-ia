
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from config.GameConfig import GameConfig
from lobby.TFTLobby import TFTLobby, CombatResult, combat_engine


def make_player(player_id):
    env = SimpleNamespace(
        hp=100,
        economy_manager=SimpleNamespace(
            add_gold=Mock(),
        ),
        apply_combat_result=Mock(),
        apply_damage=Mock(),
        _rebuild_player_state=Mock(),
        last_combat_result=None,
        last_combat_won=False,
    )

    return SimpleNamespace(
        player_id=player_id,
        env=env,
        wins=0,
        losses=0,
        last_combat_result=None,
        last_damage_taken=0,
    )


def make_lobby(monkeypatch, winner, survivors_a=2, survivors_b=0):
    lobby = TFTLobby.__new__(TFTLobby)
    lobby.stage = 1

    player_a = make_player(1)
    player_b = make_player(2)

    cpp_result = SimpleNamespace(
        success=True,
        completed=True,
        winner=winner,
        player_a_survivors=survivors_a,
        player_b_survivors=survivors_b,
    )

    monkeypatch.setattr(
        lobby,
        "_build_cpp_combat_input",
        lambda a, b: object(),
    )
    monkeypatch.setattr(
        combat_engine,
        "simulate",
        lambda _: cpp_result,
    )

    return lobby, player_a, player_b


# TESTE 1 — dano por estágio e sobreviventes
@pytest.mark.parametrize("stage", [1, 2, 3, 4, 5])
@pytest.mark.parametrize("survivors", [0, 1, 3, 7])
def test_damage_is_stage_base_plus_survivors(stage, survivors):
    lobby = TFTLobby.__new__(TFTLobby)
    lobby.stage = stage

    expected = max(
        0,
        GameConfig.get_stage_damage(stage) + survivors,
    )

    assert lobby._calculate_damage(survivors) == expected


# TESTE 2 — vitória aplica dano e recompensa corretamente
def test_player_a_win_applies_damage_and_win_gold(monkeypatch):
    lobby, player_a, player_b = make_lobby(
        monkeypatch,
        combat_engine.CombatWinner.PLAYER_A,
        survivors_a=3,
        survivors_b=0,
    )

    result = lobby.resolve_combat(player_a, player_b)

    expected_damage = (
        GameConfig.get_stage_damage(lobby.stage) + 3
    )

    assert isinstance(result, CombatResult)
    assert result.winner_id == player_a.player_id
    assert result.loser_id == player_b.player_id
    assert result.damage == expected_damage
    assert result.draw is False

    assert player_a.wins == 1
    assert player_b.losses == 1

    player_a.env.apply_combat_result.assert_called_once_with(
        result,
        won=True,
    )
    player_b.env.apply_damage.assert_called_once_with(expected_damage)


# TESTE 3 — vitória da equipe B inverte vencedor e perdedor
def test_player_b_win_applies_damage_to_player_a(monkeypatch):
    lobby, player_a, player_b = make_lobby(
        monkeypatch,
        combat_engine.CombatWinner.PLAYER_B,
        survivors_a=0,
        survivors_b=2,
    )

    result = lobby.resolve_combat(player_a, player_b)

    expected_damage = (
        GameConfig.get_stage_damage(lobby.stage) + 2
    )

    assert result.winner_id == player_b.player_id
    assert result.loser_id == player_a.player_id
    assert result.damage == expected_damage

    assert player_b.wins == 1
    assert player_a.losses == 1

    player_b.env.apply_combat_result.assert_called_once_with(
        result,
        won=True,
    )
    player_a.env.apply_damage.assert_called_once_with(expected_damage)


# TESTE 4 — empate não causa dano nem concede ouro de vitória
def test_draw_does_not_damage_or_reward_players(monkeypatch):
    lobby, player_a, player_b = make_lobby(
        monkeypatch,
        combat_engine.CombatWinner.DRAW,
        survivors_a=1,
        survivors_b=1,
    )

    result = lobby.resolve_combat(player_a, player_b)

    assert result.draw is True
    assert result.winner_id is None
    assert result.loser_id is None
    assert result.damage == 0

    assert player_a.wins == 0
    assert player_a.losses == 0
    assert player_b.wins == 0
    assert player_b.losses == 0

    player_a.env.apply_damage.assert_not_called()
    player_b.env.apply_damage.assert_not_called()
    player_a.env.apply_combat_result.assert_not_called()
    player_b.env.apply_combat_result.assert_not_called()