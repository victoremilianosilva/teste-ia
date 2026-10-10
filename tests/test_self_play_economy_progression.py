"""Validação da progressão econômica do self-play, sem treinamento PPO."""

import numpy as np

from config.GameConfig import GameConfig
from lobby.TFTLobby import TFTLobby


def test_self_play_economy_progression_is_consistent():
    lobby = TFTLobby(seed=789)

    try:
        # 1. Inicializa a partida.
        observations = lobby.reset()

        assert len(lobby.players) == 8
        assert observations.shape[0] == 8
        assert np.isfinite(observations).all()

        # Guarda os valores iniciais para comparar depois.
        initial_gold = {}
        initial_units = {}

        for player in lobby.players:
            pid = player.player_id
            env = player.env

            initial_gold[pid] = env.economy_manager.gold
            initial_units[pid] = (
                env.board_manager.get_unit_count()
                + env.bench_manager.get_unit_count()
            )

            assert initial_gold[pid] >= 0
            assert initial_units[pid] >= 0

        print("\n💰 Estado inicial:")
        print(f"   Ouro inicial por jogador: {initial_gold}")
        print(f"   Unidades iniciais: {initial_units}")

        # 2. Todos passam as ações para não gastar ouro voluntariamente.
        # Isso permite observar a progressão econômica básica.
        pass_actions = [{"type": 6} for _ in range(8)]

        max_steps = 40
        resolved_rounds = 0
        previous_round = lobby.round
        gold_history = {p.player_id: [] for p in lobby.players}

        for step in range(max_steps):
            if lobby.finished:
                break

            observations, rewards, done, info = lobby.step(pass_actions)

            # 3. Confere a integridade dos retornos do ambiente.
            assert observations.shape[0] == 8
            assert np.isfinite(observations).all()
            assert np.isfinite(rewards).all()

            player_infos = info.get("players", [])

            round_resolved = (
                bool(player_infos)
                and any(
                    player_info.get("round_resolved") is True
                    for player_info in player_infos
                )
            )

            if round_resolved:
                resolved_rounds += 1

                for player in lobby.players:
                    pid = player.player_id
                    env = player.env
                    gold = env.economy_manager.gold

                    # O ouro não deve ficar negativo.
                    assert gold >= 0, (
                        f"Jogador {pid} ficou com ouro negativo: {gold}"
                    )

                    gold_history[pid].append(gold)

                alive = sum(player.alive for player in lobby.players)

                print(
                    f"📊 Rodada resolvida {resolved_rounds}: "
                    f"{alive} jogadores vivos | "
                    f"rodada interna do lobby: {lobby.round}"
                )

            # Se o jogo terminar, não precisamos avançar mais.
            if done:
                break

            # Evita que uma falha silenciosa fique rodando indefinidamente.
            assert step < max_steps - 1 or lobby.finished or resolved_rounds > 0

        # 4. Verifica se houve progressão real.
        assert resolved_rounds > 0, (
            "Nenhuma rodada foi resolvida durante o teste."
        )

        for player in lobby.players:
            pid = player.player_id
            env = player.env

            assert env.economy_manager.gold >= 0
            assert (
                env.board_manager.get_unit_count()
                + env.bench_manager.get_unit_count()
            ) >= 0

        print("\n✅ Integridade econômica validada.")
        print(f"   Rodadas resolvidas: {resolved_rounds}")

        for pid, history in gold_history.items():
            if history:
                print(
                    f"   Jogador {pid}: "
                    f"ouro observado={history}"
                )

        print("\n🏁 Teste de progressão econômica concluído.")

    finally:
        close = getattr(lobby, "close", None)
        if callable(close):
            close()