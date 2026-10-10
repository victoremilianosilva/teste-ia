
"""Integração ponta a ponta da lobby real."""

import numpy as np
import pytest

from lobby.TFTLobby import TFTLobby, CombatResult


def test_real_lobby_executes_round_and_resolves_combat():
    lobby = TFTLobby(seed=123)

    try:
        # 1. Inicializa os oito jogadores.
        observations = lobby.reset()

        assert observations.shape[0] == 8
        assert np.isfinite(observations).all()
        assert len(lobby.players) == 8

        # 2. Coloca a unidade inicial de cada jogador no tabuleiro.
        actions = []

        for player in lobby.players:
            bench = player.env.bench_manager.bench

            bench_slot = next(
                (
                    index
                    for index, unit in enumerate(bench)
                    if unit is not None
                ),
                None,
            )

            assert bench_slot is not None, (
                f"Jogador {player.player_id} sem unidade no banco."
            )

            actions.append({
                "type": 3,  # MOVE_BENCH
                "bench_slot": bench_slot,
                "board_target": player.player_id,
            })

        observations, rewards, done, info = lobby.step(actions)

        assert observations.shape[0] == 8
        assert rewards.shape == (8,)
        assert np.isfinite(rewards).all()
        assert done is False

        for player in lobby.players:
            assert any(
                unit is not None
                for unit in player.env.board_manager.board
            ), f"Jogador {player.player_id} ficou sem unidades no tabuleiro."

        # 3. Todos encerram a preparação.
        # O PASS marca round_end=True no ambiente individual.
        pass_actions = [{"type": 6} for _ in range(8)]

        observations, rewards, done, info = lobby.step(pass_actions)

        assert observations.shape[0] == 8
        assert rewards.shape == (8,)
        assert np.isfinite(rewards).all()

        # 4. A rodada precisa ter sido resolvida.
        # O resultado da rodada contém os combates realizados.
        round_info = info["round_info"]

        assert len(round_info["combat"]) == 4

        # A flag round_resolved fica nos dados dos jogadores.
        player_infos = info["players"]

        assert len(player_infos) == 8
        assert all(
            player_info.get("round_resolved") is True
            for player_info in player_infos
        )

        # 5. Validar os resultados dos combates.
        combat_results = round_info["combat"]

        for result in combat_results:
            assert isinstance(result, CombatResult)

            if result.draw:
                assert result.damage == 0
                continue

            assert result.winner_id is not None
            assert result.loser_id is not None
            assert result.winner_id != result.loser_id
            assert result.damage >= 0

        # 6. Validar recompensas e informações dos jogadores.
        assert np.isfinite(rewards).all()

        assert all(
            "combat_reward" in player_info
            for player_info in player_infos
        )


    finally:
        close = getattr(lobby, "close", None)

        if callable(close):
            close()
