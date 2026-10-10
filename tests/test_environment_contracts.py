
import numpy as np
import pytest

from ai.ActionMaskManager import ActionType
from lobby.TFTLobby import TFTLobby


@pytest.fixture
def lobby():
    instance = TFTLobby(seed=123)
    instance.reset()

    yield instance

    close = getattr(instance, "close", None)
    if callable(close):
        close()


def test_observations_have_consistent_shape_and_dtype(lobby):
    observations = lobby.get_observations()

    assert observations.shape[0] == 8
    assert observations.dtype == np.float32
    assert np.isfinite(observations).all()

    # Todos os jogadores devem ter observações compatíveis.
    expected_shape = observations[0].shape
    for observation in observations:
        assert observation.shape == expected_shape


def test_player_step_returns_valid_transition(lobby):
    env = lobby.players[0].env

    observation, reward, done, info = env.step({
        "type": int(ActionType.PASS),
    })

    assert observation.dtype == np.float32
    assert np.isfinite(observation).all()
    assert np.isscalar(reward)
    assert np.isfinite(reward)
    assert isinstance(done, bool)
    assert isinstance(info, dict)
    assert info["action_success"] is True


def test_reset_restores_player_state(lobby):
    env = lobby.players[0].env

    env.hp = 1
    env.done = True
    env.round = 5
    env.economy_manager.add_gold(20)

    observation = env.reset()

    assert env.hp > 1
    assert env.done is False
    assert env.round == 1
    assert env.economy_manager.gold == 0
    assert observation.dtype == np.float32
    assert np.isfinite(observation).all()


def test_lobby_reset_restores_eight_players(lobby):
    # Marca um jogador como eliminado antes do reset.
    player = lobby.players[0]
    player.alive = False
    player.eliminated = True
    player.placement = 8

    observations = lobby.reset()

    assert len(lobby.players) == 8
    assert observations.shape[0] == 8
    assert player.alive is True
    assert player.eliminated is False
    assert player.placement is None
    assert np.isfinite(observations).all()
