
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from config.GameConfig import GameConfig
from lobby.TFTLobby import (
    TFTLobby,
    CombatResult,
    combat_engine,
)


def make_player(player_id, units):
    """
    Cria um jogador de teste com um tabuleiro de 28 posições.
    A lista units contém as unidades que estarão no tabuleiro.
    """
    board = [None] * 28

    for position, unit in enumerate(units):
        board[position] = unit

    board_manager = SimpleNamespace(
        board=board,
        get_occupied_positions=lambda: [
            i for i, unit in enumerate(board)
            if unit is not None
        ],
        get_unit=lambda position: board[position],
    )

    env = SimpleNamespace(
        hp=100,
        board_manager=board_manager,
        last_combat_result=None,
        last_combat_won=False,
        _rebuild_player_state=Mock(),
        apply_combat_result=Mock(),
        apply_damage=Mock(),
    )

    return SimpleNamespace(
        player_id=player_id,
        env=env,
        wins=0,
        losses=0,
        last_combat_result=None,
        last_damage_taken=0,
    )


def make_lobby():
    """Cria uma lobby mínima para testar somente a resolução do combate."""
    lobby = TFTLobby.__new__(TFTLobby)
    lobby.stage = 1
    return lobby


def make_unit(name):
    """Cria uma unidade simples para ocupar uma posição do tabuleiro."""
    return {
        "id": name,
        "champion_id": name,
        "name": name,
        "star": 1,
        "hp": 100,
    }


def forbid_cpp_combat(monkeypatch, lobby):
    """
    Falha imediatamente se a correção tentar chamar o motor C++
    em um cenário de equipe vazia.
    """
    monkeypatch.setattr(
        lobby,
        "_build_cpp_combat_input",
        Mock(side_effect=AssertionError(
            "Não deveria montar entrada para o motor C++."
        )),
    )

    monkeypatch.setattr(
        combat_engine,
        "simulate",
        Mock(side_effect=AssertionError(
            "Não deveria executar o motor C++."
        )),
    )


def test_equipe_a_vazia_equipe_b_vence_sem_cpp(monkeypatch):
    lobby = make_lobby()

    player_a = make_player(1, [])
    player_b = make_player(
        2,
        [make_unit("unit_b1"), make_unit("unit_b2")],
    )

    forbid_cpp_combat(monkeypatch, lobby)

    result = lobby.resolve_combat(player_a, player_b)

    expected_damage = (
        GameConfig.get_stage_damage(lobby.stage) + 2
    )

    assert isinstance(result, CombatResult)
    assert result.draw is False
    assert result.winner_id == player_b.player_id
    assert result.loser_id == player_a.player_id
    assert result.winner_units == 2
    assert result.loser_units == 0
    assert result.damage == expected_damage

    assert player_b.wins == 1
    assert player_a.losses == 1

    player_b.env.apply_combat_result.assert_called_once_with(
        result,
        won=True,
    )
    player_a.env.apply_combat_result.assert_called_once_with(
        result,
        won=False,
    )
    player_a.env.apply_damage.assert_called_once_with(
        expected_damage
    )
    player_b.env.apply_damage.assert_not_called()

    assert player_a.last_combat_result is result
    assert player_b.last_combat_result is result


def test_equipe_b_vazia_equipe_a_vence_sem_cpp(monkeypatch):
    lobby = make_lobby()

    player_a = make_player(
        1,
        [make_unit("unit_a1"), make_unit("unit_a2"),
         make_unit("unit_a3")],
    )
    player_b = make_player(2, [])

    forbid_cpp_combat(monkeypatch, lobby)

    result = lobby.resolve_combat(player_a, player_b)

    expected_damage = (
        GameConfig.get_stage_damage(lobby.stage) + 3
    )

    assert result.draw is False
    assert result.winner_id == player_a.player_id
    assert result.loser_id == player_b.player_id
    assert result.winner_units == 3
    assert result.loser_units == 0
    assert result.damage == expected_damage

    assert player_a.wins == 1
    assert player_b.losses == 1

    player_a.env.apply_combat_result.assert_called_once_with(
        result,
        won=True,
    )
    player_b.env.apply_combat_result.assert_called_once_with(
        result,
        won=False,
    )
    player_b.env.apply_damage.assert_called_once_with(
        expected_damage
    )
    player_a.env.apply_damage.assert_not_called()

    assert player_a.last_combat_result is result
    assert player_b.last_combat_result is result


def test_ambas_equipes_vazias_resultam_em_empate_sem_cpp(monkeypatch):
    lobby = make_lobby()

    player_a = make_player(1, [])
    player_b = make_player(2, [])

    forbid_cpp_combat(monkeypatch, lobby)

    result = lobby.resolve_combat(player_a, player_b)

    assert isinstance(result, CombatResult)
    assert result.draw is True
    assert result.winner_id is None
    assert result.loser_id is None
    assert result.winner_units == 0
    assert result.loser_units == 0
    assert result.damage == 0

    assert player_a.wins == 0
    assert player_a.losses == 0
    assert player_b.wins == 0
    assert player_b.losses == 0

    player_a.env.apply_combat_result.assert_not_called()
    player_b.env.apply_combat_result.assert_not_called()
    player_a.env.apply_damage.assert_not_called()
    player_b.env.apply_damage.assert_not_called()

    assert player_a.last_damage_taken == 0
    assert player_b.last_damage_taken == 0

    assert player_a.last_combat_result is result
    assert player_b.last_combat_result is result

    assert player_a.env.last_combat_result is result
    assert player_b.env.last_combat_result is result

    assert player_a.env.last_combat_won is False
    assert player_b.env.last_combat_won is False

    player_a.env._rebuild_player_state.assert_called_once()
    player_b.env._rebuild_player_state.assert_called_once()
