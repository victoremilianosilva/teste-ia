
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


from collections import Counter


def test_dois_resets_consecutivos_preservam_estoque_global():
    lobby = TFTLobby(seed=123)

    try:
        for reset_number in (1, 2):
            lobby.reset()

            # A lobby deve continuar com os 8 jogadores.
            assert len(lobby.players) == 8
            assert all(player.alive for player in lobby.players)

            # Conta todas as cópias retiradas do pool:
            # unidades no banco, tabuleiro e lojas.
           
            active_copies = Counter()

            for player in lobby.players:
                env = player.env

                # Unidades no banco e no tabuleiro usam ID interno.
                for unit in env.bench_manager.bench:
                    if unit is not None:
                        active_copies[unit["id"]] += 1

                for unit in env.board_manager.board:
                    if unit is not None:
                        active_copies[unit["id"]] += 1

                # A loja contém campeões do catálogo, identificados
                # por apiName. Convertemos para o ID do UnitManager.
                for champion in env.shop_manager.get_shop():
                    if champion is not None:
                        champion_id = env.unit_manager.get_unit_id(
                            champion
                        )

                        assert champion_id is not None, (
                            "Campeão da loja não encontrado no catálogo: "
                            f"{champion.get('apiName')}"
                        )

                        active_copies[champion_id] += 1

            # Estoque disponível + cópias em circulação
            # deve corresponder ao estoque inicial.
            for champion_id, initial in (
                lobby.unit_pool.initial_counts.items()
            ):
                available = lobby.unit_pool.available[champion_id]

            if available + active_copies[champion_id] != initial:
                print(f"\nCampeão ID: {champion_id}")
                print(f"Estoque inicial: {initial}")
                print(f"Disponível: {available}")
                print(f"Contado em circulação: {active_copies[champion_id]}")

                for player in lobby.players:
                    env = player.env

                    for unit in env.bench_manager.bench:
                        if unit is not None and unit["id"] == champion_id:
                            print("BANCO:", player.player_id, unit)

                    for unit in env.board_manager.board:
                        if unit is not None and unit["id"] == champion_id:
                            print("TABULEIRO:", player.player_id, unit)

                    for champion in env.shop_manager.get_shop():
                        if (
                            champion is not None
                            and env.unit_manager.get_unit_id(champion) == champion_id
                        ):
                            print("LOJA:", player.player_id, champion)

                assert available + active_copies[champion_id] == initial

                assert 0 <= available <= initial, (
                    f"Reset {reset_number}: estoque inválido "
                    f"para campeão {champion_id}: {available}"
                )

                assert available + active_copies[champion_id] == initial, (
                    f"Reset {reset_number}: divergência para "
                    f"campeão {champion_id}. "
                    f"Disponível={available}, "
                    f"em circulação={active_copies[champion_id]}, "
                    f"inicial={initial}"
                )

            for player in lobby.players:
                assert any(
                    unit is not None
                    for unit in player.env.bench_manager.bench
                ), (
                    f"Jogador {player.player_id} sem unidade "
                    f"após reset {reset_number}"
                )


    finally:
        close = getattr(lobby, "close", None)
        if callable(close):
            close()


from collections import Counter
from config.GameConfig import GameConfig


def test_eliminacao_devolve_unidades_uma_unica_vez():
    lobby = TFTLobby(seed=456)

    try:
        lobby.reset()

        player = lobby.players[0]
        env = player.env

        # 📦 Move a unidade inicial do banco para o tabuleiro.
        bench_slot = next(
            i for i, unit in enumerate(env.bench_manager.bench)
            if unit is not None
        )
        unit = env.bench_manager.bench[bench_slot]
        env.bench_manager.bench[bench_slot] = None
        env.board_manager.board[0] = unit

        # Confirma que a loja tem ofertas para o cenário.
        assert any(
            offer is not None
            for offer in env.shop_manager.get_shop()
        )

        # 📊 Calcula quantas cópias cada campeão deve devolver.
        expected_returns = Counter()

        for unit in env.board_manager.board:
            if unit is not None:
                expected_returns[unit["id"]] += (
                    GameConfig.get_star_copies(
                        int(unit.get("star", 1))
                    )
                )

        for unit in env.bench_manager.bench:
            if unit is not None:
                expected_returns[unit["id"]] += (
                    GameConfig.get_star_copies(
                        int(unit.get("star", 1))
                    )
                )

        # As ofertas da loja são campeões do catálogo.
        for champion in env.shop_manager.get_shop():
            if champion is not None:
                champion_id = env.unit_manager.get_unit_id(champion)
                assert champion_id is not None
                expected_returns[champion_id] += 1

        before = dict(lobby.unit_pool.available)

        # ☠️ Elimina o jogador.
        env.hp = 0
        lobby.eliminate_players()

        assert player.alive is False
        assert player.eliminated is True

        # 🧹 Banco, tabuleiro e loja devem estar vazios.
        assert all(
            unit is None for unit in env.board_manager.board
        )
        assert all(
            unit is None for unit in env.bench_manager.bench
        )
        assert all(
            unit is None for unit in env.shop_manager.get_shop()
        )

        # Cada devolução deve aumentar o estoque na quantidade esperada.
        for champion_id, amount in expected_returns.items():
            expected = min(
                before[champion_id] + amount,
                lobby.unit_pool.initial_counts[champion_id],
            )
            assert lobby.unit_pool.available[champion_id] == expected

        # 🔁 Uma segunda chamada não pode devolver as mesmas cópias.
        after_first_elimination = dict(lobby.unit_pool.available)
        lobby.eliminate_players()

        assert lobby.unit_pool.available == after_first_elimination

    finally:
        close = getattr(lobby, "close", None)
        if callable(close):
            close()


def test_compra_e_venda_preservam_estoque_global():
    lobby = TFTLobby(seed=789)

    try:
        lobby.reset()

        env = lobby.players[0].env
        pool = lobby.unit_pool

        # Procura uma oferta disponível.
        shop = env.shop_manager.get_shop()
        slot = next(
            i for i, champion in enumerate(shop)
            if champion is not None
        )
        champion = shop[slot]
        champion_id = env.unit_manager.get_unit_id(champion)

        assert champion_id is not None

        # A oferta já consumiu uma cópia do pool.
        available_before_buy = pool.available[champion_id]
        initial = pool.initial_counts[champion_id]

        # Compra: a cópia sai da loja e passa para o jogador.
        purchased_champion = env.shop_manager.take_unit(slot)
        assert purchased_champion is not None
        assert pool.available[champion_id] == available_before_buy

        # Simula a conversão da oferta em unidade do jogador.
        purchased_unit = env.unit_manager.create_unit(
            purchased_champion
        )
        assert purchased_unit is not None

        # A venda devolve uma cópia de 1 estrela.
        returned = pool.return_unit(purchased_unit)
        assert returned is True
        assert pool.available[champion_id] == min(
            available_before_buy + 1,
            initial,
        )
        assert pool.validate()

    finally:
        close = getattr(lobby, "close", None)
        if callable(close):
            close()


def test_venda_real_devolve_unidade_uma_unica_vez():
    from env import ActionType
    from config.GameConfig import GameConfig

    lobby = TFTLobby(seed=790)

    try:
        lobby.reset()

        env = lobby.players[0].env
        pool = lobby.unit_pool

        # Pega uma unidade real do banco do jogador.
        bench_slot = next(
            i for i, unit in enumerate(env.bench_manager.bench)
            if unit is not None
        )
        unit = env.bench_manager.bench[bench_slot]
        champion_id = unit["id"]

        copies = GameConfig.get_star_copies(
            int(unit.get("star", 1))
        )

        before = pool.available[champion_id]
        expected = min(
            before + copies,
            pool.initial_counts[champion_id],
        )

        # Executa a ação REAL de venda do ambiente.
        _, _, _, info = env.step({
            "type": ActionType.SELL,
            "bench_slot": bench_slot,
        })

        assert info["action_success"] is True
        assert info["sold_unit"]["id"] == champion_id
        assert env.bench_manager.bench[bench_slot] is None
        assert pool.available[champion_id] == expected
        assert pool.validate()

        # Uma segunda venda no mesmo slot não pode devolver cópias.
        available_after_sale = pool.available[champion_id]

        _, _, _, second_info = env.step({
            "type": ActionType.SELL,
            "bench_slot": bench_slot,
        })

        assert second_info["action_success"] is not True
        assert pool.available[champion_id] == available_after_sale
        assert pool.validate()

    finally:
        close = getattr(lobby, "close", None)
        if callable(close):
            close()


def test_reroll_real_cobra_dois_ouro_e_preserva_estoque():
    from ai.ActionMaskManager import ActionType

    lobby = TFTLobby(seed=791)

    try:
        lobby.reset()

        env = lobby.players[0].env
        pool = lobby.unit_pool

        # Garante dinheiro para o reroll.
        env.economy_manager.add_gold(2)
        gold_before = env.economy_manager.gold

        # Registra as ofertas antes de trocar a loja.
        old_shop = env.shop_manager.get_shop()
        old_ids = [
            env.unit_manager.get_unit_id(champion)
            for champion in old_shop
            if champion is not None
        ]

        assert old_ids

        _, _, _, info = env.step({
            "type": ActionType.REROLL,
        })

        assert info["action_success"] is True
        assert env.economy_manager.gold == gold_before - 2
        assert pool.validate()

        # A loja deve continuar utilizável após o reroll.
        new_shop = env.shop_manager.get_shop()
        assert len(new_shop) == env.shop_size

        # Todas as ofertas novas devem ser campeões válidos.
        for champion in new_shop:
            if champion is not None:
                assert env.unit_manager.get_unit_id(champion) is not None

    finally:
        close = getattr(lobby, "close", None)
        if callable(close):
            close()


def test_compra_com_falha_no_pagamento_devolve_oferta_ao_pool(
    monkeypatch,
):
    from ai.ActionMaskManager import ActionType

    lobby = TFTLobby(seed=792)

    try:
        lobby.reset()

        env = lobby.players[0].env
        pool = lobby.unit_pool

        # Escolhe uma oferta válida.
        shop = env.shop_manager.get_shop()
        slot = next(
            i for i, champion in enumerate(shop)
            if champion is not None
        )
        champion = shop[slot]
        champion_id = env.unit_manager.get_unit_id(champion)

        assert champion_id is not None

        # Garante saldo suficiente para passar na primeira validação.
        env.economy_manager.add_gold(100)

        available_before = pool.available[champion_id]
        gold_before = env.economy_manager.gold

        # Simula uma falha no pagamento depois da retirada da oferta.
        monkeypatch.setattr(
            env.economy_manager,
            "spend_gold",
            lambda cost: False,
        )

        _, _, _, info = env.step({
            "type": ActionType.BUY,
            "shop_slot": slot,
        })

        assert info["action_success"] is False

        # O pagamento falhou: não pode gastar ouro.
        assert env.economy_manager.gold == gold_before

        # A oferta retirada precisa voltar ao estoque.
        assert pool.available[champion_id] == min(
            available_before + 1,
            pool.initial_counts[champion_id],
        )

        # O espaço da loja foi consumido pela tentativa.
        assert env.shop_manager.get_unit(slot) is None

        assert pool.validate()

    finally:
        close = getattr(lobby, "close", None)
        if callable(close):
            close()


def test_compra_com_banco_cheio_devolve_ouro_e_unidade(
    monkeypatch,
):
    from ai.ActionMaskManager import ActionType

    lobby = TFTLobby(seed=793)

    try:
        lobby.reset()

        env = lobby.players[0].env
        pool = lobby.unit_pool

        shop = env.shop_manager.get_shop()
        slot = next(
            i for i, champion in enumerate(shop)
            if champion is not None
        )

        champion = shop[slot]
        champion_id = env.unit_manager.get_unit_id(champion)
        cost = int(champion["cost"])

        assert champion_id is not None

        env.economy_manager.add_gold(100)
        gold_before = env.economy_manager.gold
        available_before = pool.available[champion_id]

        # Simula a rejeição da unidade pelo banco.
        monkeypatch.setattr(
            env.bench_manager,
            "add_unit",
            lambda unit: False,
        )

        _, _, _, info = env.step({
            "type": ActionType.BUY,
            "shop_slot": slot,
        })

        assert info["action_success"] is False
        assert env.economy_manager.gold == gold_before
        assert pool.available[champion_id] == min(
            available_before + 1,
            pool.initial_counts[champion_id],
        )
        assert env.shop_manager.get_unit(slot) is None
        assert pool.validate()

    finally:
        close = getattr(lobby, "close", None)
        if callable(close):
            close()
