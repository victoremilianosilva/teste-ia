"""Testes de comportamento econômico em self-play, sem PPO."""

import numpy as np

from config.GameConfig import GameConfig
from lobby.TFTLobby import TFTLobby


def test_eight_players_buy_units_and_one_player_rerolls():
    lobby = TFTLobby(seed=456)

    try:
        # 1. Inicializa os oito jogadores.
        observations = lobby.reset()

        assert observations.shape[0] == 8

        expected_bench_counts = {}
        expected_gold = {}
        purchase_slots = {}

        # 2. Prepara compras válidas para todos os jogadores.
        buy_actions = []

        for player in lobby.players:
            env = player.env
            economy = env.economy_manager
            bench = env.bench_manager

            shop = env.shop_manager.get_shop()

            slot = next(
                (
                    i for i, unit in enumerate(shop)
                    if unit is not None
                ),
                None,
            )

            assert slot is not None, (
                f"Jogador {player.player_id}: loja sem unidades."
            )

            champion = shop[slot]
            cost = int(champion.get("cost", 1))

            # Fornece apenas o ouro necessário para testar a compra.
            economy.add_gold(cost)

            expected_gold[player.player_id] = economy.gold - cost
            expected_bench_counts[player.player_id] = (
                bench.get_unit_count() + 1
            )
            purchase_slots[player.player_id] = slot

            buy_actions.append({
                "type": 0,  # BUY
                "shop_slot": slot,
            })

        # 3. Executa as oito compras no mesmo passo do lobby.
        observations, rewards, done, info = lobby.step(buy_actions)

        assert observations.shape[0] == 8
        assert np.isfinite(observations).all()
        assert np.isfinite(rewards).all()

        for player in lobby.players:
            pid = player.player_id
            env = player.env
            slot = purchase_slots[pid]

            assert env.economy_manager.gold == expected_gold[pid], (
                f"Jogador {pid}: saldo incorreto após a compra."
            )

            assert (
                env.bench_manager.get_unit_count()
                == expected_bench_counts[pid]
            ), f"Jogador {pid}: unidade não foi adicionada ao banco."

            assert env.shop_manager.get_unit(slot) is None, (
                f"Jogador {pid}: slot comprado não foi esvaziado."
            )

        print("✅ Oito jogadores compraram uma unidade corretamente.")

        # 4. Testa reroll para o jogador 0.
        player = lobby.players[0]
        env = player.env
        economy = env.economy_manager
        shop_manager = env.shop_manager

        reroll_cost = int(GameConfig.REROLL_COST)
        economy.add_gold(reroll_cost)

        gold_before = economy.gold
        bench_before = env.bench_manager.get_unit_count()

        # Os demais encerram a ação atual; o jogador 0 rerrola.
        actions = [{"type": 6} for _ in range(8)]  # PASS
        actions[0] = {"type": 1}  # REROLL

        observations, rewards, done, info = lobby.step(actions)

        assert np.isfinite(observations).all()
        assert np.isfinite(rewards).all()

        assert economy.gold == gold_before - reroll_cost, (
            "O custo do reroll não foi descontado corretamente."
        )

        assert env.bench_manager.get_unit_count() == bench_before, (
            "O reroll alterou indevidamente o banco."
        )

        assert len(shop_manager.get_shop()) == GameConfig.SHOP_SIZE
        assert all(
            unit is None or isinstance(unit, dict)
            for unit in shop_manager.get_shop()
        ), "A loja contém entradas inválidas após o reroll."

        print("✅ Reroll cobrou o custo e preservou o banco.")
        print(f"💰 Custo do reroll: {reroll_cost}")
        print("✅ Teste econômico de self-play concluído.")

    finally:
        close = getattr(lobby, "close", None)

        if callable(close):
            close()