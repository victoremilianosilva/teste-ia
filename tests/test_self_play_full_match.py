"""Valida uma partida completa de self-play sem PPO."""

import numpy as np

from config.GameConfig import GameConfig
from lobby.TFTLobby import TFTLobby, CombatResult


PASS = 6
BUY = 0
BUY_XP = 2
MOVE_BENCH = 3


def choose_action(lobby, player):
    """Política básica para exercitar o fluxo real do jogo."""
    pid = player.player_id

    if not player.alive or lobby.round_finished[pid]:
        return {"type": PASS}

    env = player.env
    economy = env.economy_manager
    bench_manager = env.bench_manager
    board = env.board_manager.board

    board_count = sum(unit is not None for unit in board)

    bench_slot = next(
        (
            i for i, unit in enumerate(bench_manager.bench)
            if unit is not None
        ),
        None,
    )

    # 1. Coloca unidades em campo até atingir o nível atual.
    if bench_slot is not None and board_count < economy.level:
        target = next(
            (i for i, unit in enumerate(board) if unit is None),
            None,
        )

        if target is not None:
            return {
                "type": MOVE_BENCH,
                "bench_slot": bench_slot,
                "board_target": target,
            }

    # 2. Se o tabuleiro atingiu o limite, tenta comprar XP.
    if board_count >= economy.level:
        if economy.can_buy_xp():
            return {"type": BUY_XP}

        return {"type": PASS}

    # 3. Compra uma unidade que caiba no banco e que possa pagar.
    if bench_manager.has_free_slot():
        shop = env.shop_manager.get_shop()

        affordable = [
            (int(unit.get("cost", 1)), slot)
            for slot, unit in enumerate(shop)
            if unit is not None
            and economy.can_spend(int(unit.get("cost", 1)))
        ]

        if affordable:
            # Prioriza a unidade mais cara que o jogador pode pagar.
            _, slot = max(affordable)

            return {
                "type": BUY,
                "shop_slot": slot,
            }

    # 4. Sem ação útil, encerra a preparação do jogador.
    return {"type": PASS}


def test_eight_player_self_play_finishes_with_one_winner():
    lobby = TFTLobby(seed=123)

    # Proteção do teste contra travamento.
    # Não é uma regra de duração da partida.
    max_steps = 5000

    steps = 0
    resolved_rounds = 0
    total_combats = 0
    successful_buys = 0
    successful_moves = 0

    try:
        observations = lobby.reset()

        assert len(lobby.players) == 8
        assert observations.shape[0] == 8
        assert np.isfinite(observations).all()

        # Todos começam com uma unidade própria.
        for player in lobby.players:
            assert (
                player.env.bench_manager.get_unit_count()
                + player.env.board_manager.get_unit_count()
            ) >= 1

        while not lobby.finished and steps < max_steps:
            actions = [
                choose_action(lobby, player)
                for player in lobby.players
            ]

            observations, rewards, done, info = lobby.step(actions)
            steps += 1

            assert observations.shape[0] == 8
            assert np.isfinite(observations).all()
            assert np.isfinite(rewards).all()

            player_infos = info.get("players", [])

            for player_info in player_infos:
                if not player_info.get("action_success"):
                    continue

                action_type = player_info.get("action_type")

                if action_type == BUY:
                    successful_buys += 1
                elif action_type == MOVE_BENCH:
                    successful_moves += 1

            round_resolved = any(
                item.get("round_resolved") is True
                for item in player_infos
            )

            if round_resolved:
                resolved_rounds += 1

                combat_results = info.get(
                    "round_info", {}
                ).get("combat", [])

                total_combats += len(combat_results)

                for result in combat_results:
                    assert isinstance(result, CombatResult)
                    assert result.damage >= 0

                    if not result.draw:
                        assert result.winner_id is not None
                        assert result.loser_id is not None
                        assert result.winner_id != result.loser_id

                alive_count = sum(
                    player.alive for player in lobby.players
                )

                print(
                    f"Round {lobby.round}: "
                    f"{alive_count} jogadores vivos; "
                    f"{len(combat_results)} combates."
                )

            if done:
                assert lobby.finished

        # Se o watchdog disparar, o teste falha; a partida não é
        # encerrada artificialmente por esse contador.
        assert lobby.finished, (
            f"A partida não terminou em {max_steps} passos. "
            f"Round atual: {lobby.round}; "
            f"jogadores vivos: "
            f"{sum(player.alive for player in lobby.players)}."
        )

        alive_players = [
            player for player in lobby.players if player.alive
        ]

        assert len(alive_players) == 1
        assert lobby.winner_id == alive_players[0].player_id
        assert lobby.final_ranking
        assert len(lobby.final_ranking) == 8
        assert set(lobby.final_ranking) == set(range(8))

        placements = [
            player.placement for player in lobby.players
        ]

        assert sorted(placements) == list(range(1, 9))
        assert alive_players[0].placement == 1

        assert resolved_rounds > 0
        assert total_combats > 0
        assert successful_buys > 0
        assert successful_moves > 0

        assert sum(
            player.eliminated for player in lobby.players
        ) == 7

        print("\nPartida concluída!")
        print(f"Passos: {steps}")
        print(f"Rounds resolvidos: {resolved_rounds}")
        print(f"Combates: {total_combats}")
        print(f"Compras bem-sucedidas: {successful_buys}")
        print(f"Movimentos para o tabuleiro: {successful_moves}")
        print(f"Vencedor: jogador {lobby.winner_id}")
        print(f"Ranking: {lobby.final_ranking}")

    finally:
        close = getattr(lobby, "close", None)
        if callable(close):
            close()