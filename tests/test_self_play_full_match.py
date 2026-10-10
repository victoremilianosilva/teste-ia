"""Validação de uma partida completa de self-play com 8 jogadores."""

import numpy as np

from lobby.TFTLobby import TFTLobby, CombatResult


def test_eight_player_self_play_reaches_final_ranking():
    lobby = TFTLobby(seed=123)

    max_rounds = 200
    rounds_resolved = 0
    total_combats = 0

    try:
        # 1. Inicializa a partida e os oito jogadores.
        observations = lobby.reset()

        assert len(lobby.players) == 8
        assert observations.shape[0] == 8
        assert np.isfinite(observations).all()

        # 2. Coloca a unidade inicial de cada jogador no tabuleiro.
        move_actions = []

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
                f"Jogador {player.player_id} começou sem unidade no banco."
            )

            move_actions.append({
                "type": 3,  # MOVE_BENCH
                "bench_slot": bench_slot,
                "board_target": player.player_id,
            })

        observations, rewards, done, info = lobby.step(move_actions)

        assert observations.shape[0] == 8
        assert np.isfinite(observations).all()
        assert np.isfinite(rewards).all()

        for player in lobby.players:
            assert any(
                unit is not None
                for unit in player.env.board_manager.board
            ), f"Jogador {player.player_id} ficou sem unidade no tabuleiro."

        # 3. Encerra a preparação inicial.
        pass_actions = [{"type": 6} for _ in range(8)]  # PASS

        observations, rewards, done, info = lobby.step(pass_actions)

        # 4. Continua até o lobby terminar ou atingir o limite de segurança.
        while not done and rounds_resolved < max_rounds:
            observations, rewards, done, info = lobby.step(pass_actions)

            assert observations.shape[0] == 8
            assert np.isfinite(observations).all()
            assert np.isfinite(rewards).all()


            round_info = info.get("round_info", {})
            player_infos = info.get("players", [])

            round_was_resolved = (
                bool(player_infos)
                and all(
                    player_info.get("round_resolved") is True
                    for player_info in player_infos
                )
            )

            if round_was_resolved:
                rounds_resolved += 1

                combat_results = round_info.get("combat", [])
                total_combats += len(combat_results)


                # Cada combate precisa ter um resultado consistente.
                for result in combat_results:
                    assert isinstance(result, CombatResult)
                    assert result.damage >= 0

                    if not result.draw:
                        assert result.winner_id is not None
                        assert result.loser_id is not None
                        assert result.winner_id != result.loser_id

                print(
                    f"Rodada {rounds_resolved}: "
                    f"{sum(player.alive for player in lobby.players)} "
                    f"jogadores vivos | "
                    f"{len(combat_results)} combates"
                )

        # 5. Confirma que a partida terminou de verdade.
        assert done, (
            f"A partida não terminou após {max_rounds} rodadas. "
            f"Rodada atual: {lobby.round}; "
            f"jogadores vivos: "
            f"{sum(player.alive for player in lobby.players)}."
        )

        assert lobby.finished is True
        assert lobby.winner_id is not None
        assert lobby.final_ranking, "O ranking final está vazio."
        assert rounds_resolved > 0
        assert total_combats > 0

        print("\\nPartida concluída!")
        print(f"Rodadas resolvidas: {rounds_resolved}")
        print(f"Combates registrados: {total_combats}")
        print(f"Vencedor: jogador {lobby.winner_id}")
        print(f"Ranking final: {lobby.final_ranking}")

    finally:
        close = getattr(lobby, "close", None)

        if callable(close):
            close()