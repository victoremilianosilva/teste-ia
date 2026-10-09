
# tests/test_lobby_learning.py

from types import SimpleNamespace

import numpy as np
import pytest

from vector_lobby_env import LobbyVectorEnv
from lobby.TFTLobby import TFTLobby


# ============================================================
# 🧪 LOBBY FALSA PARA TESTAR O ADAPTADOR SEM COMBATE REAL
# ============================================================

class FakeLobby:
    PLAYERS_PER_LOBBY = 8

    def __init__(self):
        self.players = [
            SimpleNamespace(alive=True)
            for _ in range(self.PLAYERS_PER_LOBBY)
        ]

    def reset(self):
        # 8 jogadores, 4 features de observação por jogador.
        return np.zeros((8, 4), dtype=np.float32)

    def step(self, actions):
        assert len(actions) == 8

        observations = np.ones((8, 4), dtype=np.float32)
        rewards = np.zeros(8, dtype=np.float32)

        # Simula uma partida que acabou.
        finished = True
        info = {"finished": True}

        return observations, rewards, finished, info

    def close(self):
        pass


# ============================================================
# 1️⃣ FORMATO DAS OBSERVAÇÕES, RECOMPENSAS E DONES
# ============================================================

def test_lobby_vector_env_returns_expected_shapes():
    env = LobbyVectorEnv([FakeLobby])

    try:
        observations = env.reset()

        assert observations.shape == (1, 8, 4)
        assert observations.dtype == np.float32

        actions = [[None] * 8]

        obs, rewards, dones, infos = env.step(actions)

        assert obs.shape == (1, 8, 4)
        assert rewards.shape == (1, 8)
        assert dones.shape == (1, 8)

        assert obs.dtype == np.float32
        assert rewards.dtype == np.float32
        assert dones.dtype == np.bool_

        # A lobby terminou: os oito episódios devem encerrar.
        assert dones[0].all()
        assert infos[0]["lobby_done"] is True

    finally:
        env.close()


# ============================================================
# 2️⃣ A RECOMPENSA DE COLOCAÇÃO SÓ É ENTREGUE UMA VEZ
# ============================================================

def test_eliminated_player_receives_placement_reward_once():
    lobby = object.__new__(TFTLobby)

    lobby.players = [
        SimpleNamespace(
            player_id=0,
            placement=6,
            placement_reward_given=False,
        )
    ]

    rewards = np.zeros(8, dtype=np.float32)

    first_result = lobby._apply_placement_rewards(rewards)

    expected = lobby._calculate_placement_reward(6)

    assert rewards[0] == pytest.approx(expected)
    assert first_result[0] == pytest.approx(expected)
    assert lobby.players[0].placement_reward_given is True

    # Chamar novamente não pode duplicar a recompensa.
    second_result = lobby._apply_placement_rewards(rewards)

    assert rewards[0] == pytest.approx(expected)
    assert second_result == {}


# ============================================================
# 3️⃣ VENCEDOR, ÚLTIMO COLOCADO E FIM DOS OITO EPISÓDIOS
# ============================================================

def test_final_placement_rewards_and_episode_termination():
    lobby = object.__new__(TFTLobby)

    lobby.players = [
        SimpleNamespace(
            player_id=player_id,
            placement=player_id + 1,
            placement_reward_given=False,
        )
        for player_id in range(8)
    ]

    rewards = np.zeros(8, dtype=np.float32)

    placement_rewards = lobby._apply_placement_rewards(rewards)

    # Primeiro colocado: +1.
    assert rewards[0] == pytest.approx(1.0)
    assert placement_rewards[0] == pytest.approx(1.0)

    # Último colocado: -1.
    assert rewards[7] == pytest.approx(-1.0)
    assert placement_rewards[7] == pytest.approx(-1.0)

    # Todos os oito jogadores recebem uma recompensa final.
    assert len(placement_rewards) == 8
    assert all(
        player.placement_reward_given
        for player in lobby.players
    )

    # Validar também o encerramento de todos os episódios.
    vector_env = LobbyVectorEnv([FakeLobby])

    try:
        vector_env.reset()

        _, _, dones, infos = vector_env.step([[None] * 8])

        assert dones.shape == (1, 8)
        assert np.all(dones[0])
        assert infos[0]["lobby_done"] is True

    finally:
        vector_env.close()