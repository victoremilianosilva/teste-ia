
from types import SimpleNamespace

import pytest

from ai.RewardManager import RewardManager
from lobby.TFTLobby import TFTLobby


def make_player(player_id):
    reward_manager = RewardManager(
        economy_manager=object(),
        composition_manager=object(),
        positioning_manager=object(),
    )

    env = SimpleNamespace(
        reward_manager=reward_manager,
    )

    return SimpleNamespace(
        player_id=player_id,
        env=env,
    )


def make_result(
    winner_id=0,
    loser_id=1,
    winner_units=2,
    loser_units=0,
    damage=3,
    draw=False,
):
    return SimpleNamespace(
        winner_id=winner_id,
        loser_id=loser_id,
        winner_units=winner_units,
        loser_units=loser_units,
        damage=damage,
        draw=draw,
    )


def make_lobby(players):
    lobby = object.__new__(TFTLobby)
    lobby.players = players
    return lobby


def test_combat_reward_reaches_both_players():
    players = [
        make_player(0),
        make_player(1),
    ]
    lobby = make_lobby(players)

    rewards = lobby._calculate_combat_rewards([
        make_result()
    ])

    assert set(rewards) == {0, 1}
    assert rewards[0] > 0
    assert rewards[1] < 0


def test_combat_reward_is_recorded_by_reward_manager():
    players = [
        make_player(0),
        make_player(1),
    ]
    lobby = make_lobby(players)

    rewards = lobby._calculate_combat_rewards([
        make_result()
    ])

    assert players[0].env.reward_manager.last_combat_reward == pytest.approx(
        rewards[0]
    )
    assert players[1].env.reward_manager.last_combat_reward == pytest.approx(
        rewards[1]
    )


def test_draw_does_not_generate_combat_reward():
    players = [
        make_player(0),
        make_player(1),
    ]
    lobby = make_lobby(players)

    rewards = lobby._calculate_combat_rewards([
        make_result(
            winner_id=None,
            loser_id=None,
            winner_units=1,
            loser_units=1,
            damage=0,
            draw=True,
        )
    ])

    assert rewards == {}

    for player in players:
        assert (
            player.env.reward_manager.last_combat_reward
            == 0.0
        )


def test_multiple_combat_results_are_not_overwritten():
    players = [
        make_player(0),
        make_player(1),
        make_player(2),
        make_player(3),
    ]
    lobby = make_lobby(players)

    rewards = lobby._calculate_combat_rewards([
        make_result(
            winner_id=0,
            loser_id=1,
            winner_units=2,
            loser_units=0,
        ),
        make_result(
            winner_id=2,
            loser_id=3,
            winner_units=1,
            loser_units=0,
        ),
    ])

    assert set(rewards) == {0, 1, 2, 3}
    assert rewards[0] > 0
    assert rewards[1] < 0
    assert rewards[2] > 0
    assert rewards[3] < 0
