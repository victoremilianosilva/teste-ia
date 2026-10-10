
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


from collections import Counter

from config.GameConfig import GameConfig


def test_ciclo_completo_partida_eliminacao_reset_e_nova_partida():
    lobby = TFTLobby(seed=2026)

    def assert_pool_conserved():
        """Confere o estoque incluindo lojas, banco e tabuleiro."""
        circulation = Counter()

        for player in lobby.players:
            env = player.env

            # Banco e tabuleiro: unidades podem representar
            # mais de uma cópia quando possuem estrelas.
            owned_units = (
                list(env.bench_manager.bench)
                + list(env.board_manager.board)
            )

            for unit in owned_units:
                if unit is not None:
                    copies = GameConfig.get_star_copies(
                        int(unit.get("star", 1))
                    )
                    circulation[unit["id"]] += copies

            # Cada oferta na loja representa uma cópia.
            for champion in env.shop_manager.get_shop():
                if champion is not None:
                    champion_id = env.unit_manager.get_unit_id(
                        champion
                    )

                    assert champion_id is not None, (
                        f"Oferta sem ID válido: {champion}"
                    )
                    circulation[champion_id] += 1

        # Verifica TODOS os campeões, não apenas o último ID.
        for champion_id, initial in (
            lobby.unit_pool.initial_counts.items()
        ):
            available = lobby.unit_pool.available[champion_id]

            assert 0 <= available <= initial, (
                f"Estoque inválido para {champion_id}: "
                f"{available}/{initial}"
            )

            assert (
                available + circulation[champion_id] == initial
            ), (
                f"Estoque inconsistente para {champion_id}: "
                f"disponível={available}, "
                f"em circulação={circulation[champion_id]}, "
                f"inicial={initial}"
            )

        assert lobby.unit_pool.validate()

    try:
        # =====================================================
        # 1. INICIALIZAÇÃO
        # =====================================================
        observations = lobby.reset()

        assert observations.shape[0] == 8
        assert len(lobby.players) == 8
        assert all(player.alive for player in lobby.players)

        assert_pool_conserved()

        # =====================================================
        # 2. PREPARAÇÃO E UMA RODADA REAL
        # =====================================================

        # Coloca a unidade inicial de cada jogador no tabuleiro.
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
                f"Jogador {player.player_id} sem unidade no banco"
            )

            move_actions.append({
                "type": 3,  # MOVE_BENCH
                "bench_slot": bench_slot,
                "board_target": player.player_id,
            })

        _, _, done, _ = lobby.step(move_actions)
        assert done is False

        for player in lobby.players:
            assert any(
                unit is not None
                for unit in player.env.board_manager.board
            ), f"Jogador {player.player_id} sem unidade no tabuleiro"

        # Todos encerram a preparação para resolver o combate.
        _, rewards, done, info = lobby.step(
            [{"type": 6} for _ in lobby.players]  # PASS
        )

        assert rewards.shape == (8,)
        # ⚔️ Confirma que a rodada gerou resultados de combate.
        round_info = info["round_info"]

        assert "combat" in round_info, (
            "A resposta não contém os resultados de combate."
        )

        assert len(round_info["combat"]) > 0, (
            "Nenhum combate foi registrado na rodada."
        )
        assert len(info["round_info"]["combat"]) == 4
        assert done is False

        assert_pool_conserved()

        # =====================================================
        # 3. CONCLUSÃO CONTROLADA DA LOBBY
        # =====================================================

        # Mantém um sobrevivente e força os demais a serem
        # eliminados pelo fluxo normal de lobby.step().
        # ☠️ 1. Força o HP a zero nos sete jogadores que serão eliminados.
        survivor = lobby.players[0]

        for player in lobby.players:
            if player.player_id != survivor.player_id:
                player.env.hp = 0

        # 🧹 2. Executa o fluxo real de eliminação, fora do combate.
        lobby.eliminate_players()

        assert all(
            not player.alive and player.eliminated
            for player in lobby.players
            if player.player_id != survivor.player_id
        )

        assert survivor.alive
        assert len(lobby.get_alive_players()) == 1

        # 🏆 3. Deixa o fluxo normal da lobby finalizar a partida.
        _, _, done, info = lobby.step(
            [{"type": 6} for _ in lobby.players]
        )

        assert done is True
        assert info["finished"] is True

        assert len(lobby.get_alive_players()) == 1
        assert lobby.get_alive_players()[0].player_id == (
            survivor.player_id
        )

        eliminated_players = [
            player for player in lobby.players
            if player.eliminated
        ]

        assert len(eliminated_players) == 7

        # Os jogadores eliminados devem estar sem unidades
        # no banco, tabuleiro e loja.
        for player in eliminated_players:
            env = player.env

            assert all(
                unit is None
                for unit in env.bench_manager.bench
            )
            assert all(
                unit is None
                for unit in env.board_manager.board
            )
            assert all(
                offer is None
                for offer in env.shop_manager.get_shop()
            )

        assert_pool_conserved()

        # Eliminar novamente não pode devolver cópias extras.
        stock_after_elimination = dict(lobby.unit_pool.available)

        lobby.eliminate_players()

        assert lobby.unit_pool.available == stock_after_elimination
        assert_pool_conserved()

        # =====================================================
        # 4. RESET DA LOBBY
        # =====================================================
        observations = lobby.reset()

        assert observations.shape[0] == 8
        assert len(lobby.players) == 8
        assert all(player.alive for player in lobby.players)
        assert all(not player.eliminated for player in lobby.players)
        assert lobby.is_finished() is False
        assert lobby.winner_id is None

        assert_pool_conserved()

        # =====================================================
        # 5. INÍCIO DA SEGUNDA PARTIDA
        # =====================================================

        # Confirma que a nova partida consegue movimentar unidades
        # e resolver novamente uma rodada.
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

            assert bench_slot is not None

            move_actions.append({
                "type": 3,
                "bench_slot": bench_slot,
                "board_target": player.player_id,
            })

        _, _, done, _ = lobby.step(move_actions)
        assert done is False

        _, rewards, done, info = lobby.step(
            [{"type": 6} for _ in lobby.players]
        )

        assert rewards.shape == (8,)
        assert done is False
        # ⚔️ Confirma que a rodada gerou resultados de combate.
        round_info = info["round_info"]

        assert "combat" in round_info, (
            "A resposta não contém os resultados de combate."
        )

        assert len(round_info["combat"]) > 0, (
            "Nenhum combate foi registrado na rodada."
        )

        assert_pool_conserved()

    finally:
        close = getattr(lobby, "close", None)

        if callable(close):
            close()


def test_pareamento_ignora_jogadores_eliminados():
    """Jogadores eliminados não podem participar dos combates."""
    lobby = TFTLobby(seed=123)

    try:
        lobby.reset()

        # ☠️ Elimina um jogador pelo fluxo da lobby.
        eliminated = lobby.players[-1]
        eliminated.env.hp = 0
        lobby.eliminate_players()

        assert eliminated.alive is False
        assert eliminated.eliminated is True

        # ⚔️ Gera os pareamentos com 7 jogadores vivos.
        matchups = lobby.generate_matchups()

        # 7 jogadores vivos = 3 combates e 1 jogador sem adversário.
        assert len(matchups) == 3

        participants = []

        for player_a, player_b in matchups:
            assert player_a.alive
            assert player_b.alive
            assert not player_a.eliminated
            assert not player_b.eliminated
            assert player_a.player_id != player_b.player_id

            participants.extend([
                player_a.player_id,
                player_b.player_id,
            ])

        # Nenhum jogador participa de dois combates na mesma rodada.
        assert len(participants) == len(set(participants))

        # O eliminado não pode aparecer em nenhum pareamento.
        assert eliminated.player_id not in participants

        # Todos os participantes dos combates estão vivos.
        assert all(
            lobby.players[pid].alive
            for pid in participants
        )

    finally:
        close = getattr(lobby, "close", None)
        if callable(close):
            close()


def test_jogador_eliminado_nao_executa_acoes():
    """A lobby deve ignorar as ações de jogadores eliminados."""
    lobby = TFTLobby(seed=456)

    try:
        lobby.reset()

        eliminated = lobby.players[-1]
        eliminated.env.hp = 0
        lobby.eliminate_players()

        # 🚫 Se o ambiente tentar executar uma ação desse jogador,
        # o teste falha imediatamente.
        def forbidden_step(action):
            raise AssertionError(
                "Um jogador eliminado executou env.step()."
            )

        eliminated.env.step = forbidden_step

        actions = [{"type": 6} for _ in lobby.players]

        observations, rewards, done, info = lobby.step(actions)

        # 📊 O contrato de saída continua preservado.
        assert observations.shape[0] == 8
        assert rewards.shape == (8,)
        assert info["finished"] == done

        # O jogador eliminado deve estar identificado como morto.
        eliminated_info = next(
            item
            for item in info["players"]
            if item["player_id"] == eliminated.player_id
        )

        assert eliminated_info["dead"] is True

        # O combate da rodada deve envolver somente jogadores vivos.
        combat_results = info["round_info"].get("combat", [])

        for result in combat_results:
            if result.winner_id is not None:
                assert lobby.players[result.winner_id].alive

            if result.loser_id is not None:
                assert lobby.players[result.loser_id].alive

    finally:
        close = getattr(lobby, "close", None)
        if callable(close):
            close()


def test_pareamento_em_sequencia_com_eliminacoes():
    """Valida os pareamentos conforme jogadores são eliminados."""
    lobby = TFTLobby(seed=789)

    try:
        lobby.reset()

        for expected_alive in range(8, 1, -1):
            alive_players = lobby.get_alive_players()

            assert len(alive_players) == expected_alive

            matchups = lobby.generate_matchups()

            # Cada combate precisa de dois jogadores.
            assert len(matchups) == expected_alive // 2

            participants = []

            for player_a, player_b in matchups:
                assert player_a.alive
                assert player_b.alive
                assert not player_a.eliminated
                assert not player_b.eliminated
                assert player_a.player_id != player_b.player_id

                participants.extend([
                    player_a.player_id,
                    player_b.player_id,
                ])

            # Nenhum jogador pode aparecer em dois combates.
            assert len(participants) == len(set(participants))

            # Todos os participantes precisam estar vivos.
            assert set(participants).issubset({
                player.player_id
                for player in alive_players
            })

            # Em quantidade ímpar, um jogador fica sem pareamento.
            if expected_alive % 2 == 1:
                assert len(alive_players) - len(participants) == 1
            else:
                assert len(alive_players) == len(participants)

            # Elimina um jogador para testar a próxima configuração.
            if expected_alive > 2:
                player_to_eliminate = alive_players[-1]
                player_to_eliminate.env.hp = 0

                lobby.eliminate_players()

                assert not player_to_eliminate.alive
                assert player_to_eliminate.eliminated

    finally:
        close = getattr(lobby, "close", None)
        if callable(close):
            close()


def test_jogador_sem_pareamento_nao_recebe_dano_de_combate():
    """O jogador sem adversário não deve sofrer dano de combate."""
    lobby = TFTLobby(seed=321)

    try:
        lobby.reset()

        # ☠️ Reduz a lobby para 7 jogadores vivos.
        eliminated = lobby.players[-1]
        eliminated.env.hp = 0
        lobby.eliminate_players()

        alive_players = lobby.get_alive_players()
        assert len(alive_players) == 7

        # ⚔️ Gera três combates: um jogador ficará sem adversário.
        matchups = lobby.generate_matchups()

        assert len(matchups) == 3

        participants = {
            player.player_id
            for pair in matchups
            for player in pair
        }

        unmatched = [
            player
            for player in alive_players
            if player.player_id not in participants
        ]

        assert len(unmatched) == 1
        bye_player = unmatched[0]

        # 📌 Guarda o estado antes da resolução dos combates.
        hp_before = bye_player.env.hp
        damage_before = bye_player.last_damage_taken
        previous_result = bye_player.last_combat_result

        # ⚔️ Resolve apenas os combates realmente pareados.
        results = [
            lobby.resolve_combat(player_a, player_b)
            for player_a, player_b in matchups
        ]

        assert len(results) == 3

        # 🛡️ O jogador sem adversário não pode sofrer dano.
        assert bye_player.env.hp == hp_before
        assert bye_player.last_damage_taken == damage_before

        # Nenhum combate pode apontar o jogador sem adversário.
        for result in results:
            assert result.winner_id != bye_player.player_id
            assert result.loser_id != bye_player.player_id

        # O resultado individual não pode ser alterado por combates
        # dos quais esse jogador não participou.
        assert bye_player.last_combat_result is previous_result

    finally:
        close = getattr(lobby, "close", None)
        if callable(close):
            close()


def test_jogador_sem_pareamento_no_fluxo_integrado():
    """Valida o jogador sem adversário usando lobby.step()."""
    lobby = TFTLobby(seed=654)

    try:
        lobby.reset()

        # Elimina um jogador: ficam 7 vivos.
        eliminated = lobby.players[-1]
        eliminated.env.hp = 0
        lobby.eliminate_players()

        alive_players = lobby.get_alive_players()
        assert len(alive_players) == 7

        # Identifica quem fica sem adversário.
        matchups = lobby.generate_matchups()
        assert len(matchups) == 3

        paired_ids = {
            player.player_id
            for pair in matchups
            for player in pair
        }

        unmatched = [
            player
            for player in alive_players
            if player.player_id not in paired_ids
        ]

        assert len(unmatched) == 1
        bye_player = unmatched[0]

        hp_before = bye_player.env.hp
        damage_before = bye_player.last_damage_taken
        result_before = bye_player.last_combat_result

        # Todos os jogadores enviam PASS.
        actions = [{"type": 6} for _ in lobby.players]

        observations, rewards, done, info = lobby.step(actions)

        # A lobby mantém as saídas esperadas.
        assert len(observations) == len(lobby.players)
        assert len(rewards) == len(lobby.players)

        # O jogador sem adversário não deve sofrer dano de combate.
        assert bye_player.env.hp == hp_before
        assert bye_player.last_damage_taken == damage_before

        # Seu resultado individual não deve ser sobrescrito
        # apenas por ter passado pelo fluxo da lobby.
        assert bye_player.last_combat_result is result_before

        # O jogador eliminado continua fora da partida.
        assert not eliminated.alive
        assert eliminated.eliminated

    finally:
        close = getattr(lobby, "close", None)
        if callable(close):
            close()


def test_opponent_id_consistente_apos_eliminacoes_e_pareamento_impar():
    """Nenhum jogador deve manter um adversário inválido após o pareamento."""
    lobby = TFTLobby(seed=987)

    try:
        lobby.reset()

        # ☠️ Elimina um jogador: restam 7 vivos.
        eliminated = lobby.players[-1]
        eliminated.env.hp = 0
        lobby.eliminate_players()

        alive_players = lobby.get_alive_players()
        assert len(alive_players) == 7

        # ⚔️ Primeiro pareamento: 3 combates e 1 jogador sem adversário.
        first_matchups = lobby.generate_matchups()
        assert len(first_matchups) == 3

        first_paired_ids = {
            player.player_id
            for pair in first_matchups
            for player in pair
        }

        first_unmatched = [
            player
            for player in alive_players
            if player.player_id not in first_paired_ids
        ]

        assert len(first_unmatched) == 1
        first_bye = first_unmatched[0]

        # Todos os adversários atribuídos devem estar vivos
        # e apontar de volta para o jogador correspondente.
        alive_by_id = {
            player.player_id: player
            for player in alive_players
        }

        for player_a, player_b in first_matchups:
            assert player_a.opponent_id == player_b.player_id
            assert player_b.opponent_id == player_a.player_id
            assert player_a.opponent_id in alive_by_id
            assert player_b.opponent_id in alive_by_id

        # 🔎 Segundo pareamento: a quantidade continua ímpar.
        # O jogador que ficou sem adversário pode mudar.
        second_matchups = lobby.generate_matchups()
        assert len(second_matchups) == 3

        second_paired_ids = {
            player.player_id
            for pair in second_matchups
            for player in pair
        }

        second_unmatched = [
            player
            for player in alive_players
            if player.player_id not in second_paired_ids
        ]

        assert len(second_unmatched) == 1

        for player_a, player_b in second_matchups:
            assert player_a.opponent_id == player_b.player_id
            assert player_b.opponent_id == player_a.player_id

        # ☠️ Elimina mais um jogador.
        another = next(
            player
            for player in alive_players
            if player.player_id != first_bye.player_id
        )
        another.env.hp = 0
        lobby.eliminate_players()

        remaining = lobby.get_alive_players()
        assert len(remaining) == 6

        # 🔁 Novo pareamento: todos devem enfrentar alguém vivo.
        third_matchups = lobby.generate_matchups()
        assert len(third_matchups) == 3

        remaining_by_id = {
            player.player_id: player
            for player in remaining
        }

        for player_a, player_b in third_matchups:
            assert player_a.player_id in remaining_by_id
            assert player_b.player_id in remaining_by_id
            assert player_a.opponent_id == player_b.player_id
            assert player_b.opponent_id == player_a.player_id

        # Nenhum jogador eliminado pode aparecer nos novos combates.
        paired_ids = {
            player.player_id
            for pair in third_matchups
            for player in pair
        }

        assert eliminated.player_id not in paired_ids
        assert another.player_id not in paired_ids

    finally:
        close = getattr(lobby, "close", None)
        if callable(close):
            close()


def test_jogador_sem_pareamento_nao_mantem_oponente_antigo():
    """O jogador sem par não deve manter referência a um adversário anterior."""
    lobby = TFTLobby(seed=1357)

    try:
        lobby.reset()

        # ☠️ Deixa 7 jogadores vivos.
        eliminated = lobby.players[-1]
        eliminated.env.hp = 0
        lobby.eliminate_players()

        alive_players = lobby.get_alive_players()
        assert len(alive_players) == 7

        # ⚔️ Primeiro pareamento.
        first_matchups = lobby.generate_matchups()
        assert len(first_matchups) == 3

        first_paired_ids = {
            player.player_id
            for pair in first_matchups
            for player in pair
        }

        first_unmatched = [
            player
            for player in alive_players
            if player.player_id not in first_paired_ids
        ]

        assert len(first_unmatched) == 1
        bye_player = first_unmatched[0]

        # Simula uma referência antiga para reproduzir o caso de risco.
        old_opponent = next(
            player
            for player in alive_players
            if player.player_id != bye_player.player_id
        )
        bye_player.opponent_id = old_opponent.player_id

        # 🔁 Novo pareamento: o jogador pode continuar sem adversário.
        second_matchups = lobby.generate_matchups()

        second_paired_ids = {
            player.player_id
            for pair in second_matchups
            for player in pair
        }

        second_unmatched = [
            player
            for player in alive_players
            if player.player_id not in second_paired_ids
        ]

        assert len(second_unmatched) == 1

        # Se ele ficou sem par novamente, a referência antiga deve ser limpa.
        if second_unmatched[0].player_id == bye_player.player_id:
            assert bye_player.opponent_id is None

    finally:
        close = getattr(lobby, "close", None)
        if callable(close):
            close()
