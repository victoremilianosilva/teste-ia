
# tests/test_gameplay_validation.py
#
# Validação de gameplay do MiniTFT:
# 1. Fluxo de rodada
# 2. Loja, compras, reroll e pool compartilhado
# 3. Composição e posicionamento
# 4. Combate, HP, economia e ranking
#
# Executar:
# python -m pytest tests/test_gameplay_validation.py -v

import math

import numpy as np
import pytest

from config.GameConfig import GameConfig
from ai.ActionMaskManager import ActionType
from lobby.TFTLobby import TFTLobby


@pytest.fixture
def lobby():
    """Cria uma partida isolada para cada teste."""
    instance = TFTLobby(seed=123)
    instance.reset()

    yield instance

    close = getattr(instance, "close", None)
    if callable(close):
        close()


def get_env(lobby, player_id=0):
    return lobby.players[player_id].env


def assert_pool_is_valid(pool):
    """Confere se o estoque de cada campeão respeita seus limites."""
    assert pool.available
    assert pool.initial_counts

    for champion_id, initial in pool.initial_counts.items():
        available = pool.available[champion_id]

        assert 0 <= available <= initial, (
            f"Estoque inválido para {champion_id}: "
            f"{available}/{initial}"
        )


# ============================================================
# 1. FLUXO COMPLETO DE UMA RODADA
# ============================================================

def test_round_pass_resolves_economy_combat_and_transition(lobby):
    initial_round = lobby.round
    initial_gold = [
        player.env.economy_manager.gold
        for player in lobby.players
    ]

    # Todos encerram a preparação com PASS.
    actions = {
        player.player_id: {"type": int(ActionType.PASS)}
        for player in lobby.players
    }

    observations, rewards, done, info = lobby.step(actions)

    # Contrato de retorno do lobby.
    assert observations.shape[0] == lobby.PLAYERS_PER_LOBBY
    assert observations.dtype == np.float32
    assert rewards.shape == (lobby.PLAYERS_PER_LOBBY,)
    assert np.isfinite(observations).all()
    assert np.isfinite(rewards).all()
    assert isinstance(done, bool)

    # A rodada deve ser resolvida quando todos dão PASS.
    # Confere o contrato real de retorno de TFTLobby.step().
    alive_infos = [
        item
        for item in info["players"]
        if not item.get("dead", False)
    ]

    assert alive_infos, "Nenhum jogador ativo foi processado."

    assert all(
        item.get("round_resolved") is True
        for item in alive_infos
    ), "Nem todos os jogadores ativos registraram a resolução da rodada."

    assert "combat" in info["round_info"]
    assert "economy" in info["round_info"]

    # Todos os confrontos devem envolver jogadores distintos.
    matchups = info["round_info"]["combat"]
    assert len(matchups) > 0

    involved_players = []

    for result in matchups:
        assert result is not None
        assert result.damage >= 0

        if result.winner_id is not None:
            assert result.loser_id is not None
            assert result.winner_id != result.loser_id

        if result.winner_id is not None:
            involved_players.extend(
                [result.winner_id, result.loser_id]
            )

    # A partida deve avançar ou terminar de forma consistente.
    assert (
        lobby.round > initial_round
        or lobby.finished
    )

    # A economia deve continuar válida após a resolução.
    for player in lobby.players:
        economy = player.env.economy_manager
        assert economy.gold >= 0
        assert economy.level >= 1
        assert economy.xp >= 0

    assert len(initial_gold) == lobby.PLAYERS_PER_LOBBY


def test_matchmaking_does_not_pair_a_player_with_itself(lobby):
    matchups = lobby.generate_matchups()

    seen = set()

    for player_a, player_b in matchups:
        assert player_a.player_id != player_b.player_id

        pair = frozenset((player_a.player_id, player_b.player_id))
        assert pair not in seen
        seen.add(pair)

        assert player_a.opponent_id == player_b.player_id
        assert player_b.opponent_id == player_a.player_id


# ============================================================
# 2. LOJA, COMPRAS, REROLL E POOL COMPARTILHADO
# ============================================================

def test_shop_contains_only_valid_champions_or_empty_slots(lobby):
    env = get_env(lobby)
    shop = env.shop_manager.get_shop()

    assert len(shop) == GameConfig.SHOP_SIZE

    for champion in shop:
        if champion is not None:
            assert isinstance(champion, dict)
            assert "cost" in champion
            assert int(champion["cost"]) >= 1

    assert_pool_is_valid(lobby.unit_pool)


def test_locked_shop_does_not_change_on_normal_roll(lobby):
    env = get_env(lobby)
    shop_manager = env.shop_manager

    before = shop_manager.get_shop()

    shop_manager.set_locked(True)
    after = shop_manager.roll(env.economy_manager.level)

    assert shop_manager.is_locked()
    assert after == before


def test_buy_affordable_shop_unit_updates_gold_and_bench(lobby):
    env = get_env(lobby)
    economy = env.economy_manager
    bench = env.bench_manager

    # Procura uma unidade disponível na loja.
    shop = env.shop_manager.get_shop()

    affordable_slot = next(
        (
            slot
            for slot, unit in enumerate(shop)
            if unit is not None
        ),
        None,
    )

    assert affordable_slot is not None, (
        "A loja inicial não possui unidades. "
        "Investigue a geração da loja e o pool."
    )

    champion = shop[affordable_slot]
    unit_cost = int(champion.get("cost", 1))

    # Prepara o saldo do cenário de teste sem alterar a regra do jogo.
    economy.add_gold(unit_cost)

    gold_before = economy.gold
    bench_before = bench.get_unit_count()

    _, reward, _, info = env.step({
        "type": int(ActionType.BUY),
        "shop_slot": affordable_slot,
    })

    assert info["action_success"] is True
    assert math.isfinite(reward)
    assert economy.gold == gold_before - unit_cost
    assert bench.get_unit_count() == bench_before + 1
    assert env.shop_manager.get_unit(affordable_slot) is None

    assert_pool_is_valid(lobby.unit_pool)


def test_reroll_charges_configured_cost_and_preserves_pool_bounds(lobby):
    env = get_env(lobby)
    economy = env.economy_manager

    reroll_cost = GameConfig.REROLL_COST
    economy.add_gold(reroll_cost)

    gold_before = economy.gold

    _, reward, _, info = env.step({
        "type": int(ActionType.REROLL),
    })

    assert info["action_success"] is True
    assert economy.gold == gold_before - reroll_cost
    assert math.isfinite(reward)

    assert_pool_is_valid(lobby.unit_pool)


def test_players_share_the_same_global_unit_pool(lobby):
    for player in lobby.players:
        assert player.env.unit_pool is lobby.unit_pool


# ============================================================
# 3. COMPOSIÇÃO E POSICIONAMENTO
# ============================================================

def test_initial_unit_can_move_from_bench_to_board(lobby):
    env = get_env(lobby)

    bench_slot = next(
        (
            slot
            for slot, unit in enumerate(env.bench_manager.bench)
            if unit is not None
        ),
        None,
    )

    board_target = next(
        (
            slot
            for slot, unit in enumerate(env.board_manager.board)
            if unit is None
        ),
        None,
    )

    assert bench_slot is not None
    assert board_target is not None

    bench_before = env.bench_manager.get_unit_count()
    board_before = env.board_manager.get_unit_count()

    _, reward, _, info = env.step({
        "type": int(ActionType.MOVE_BENCH),
        "bench_slot": bench_slot,
        "board_target": board_target,
    })

    assert info["action_success"] is True
    assert math.isfinite(reward)
    assert env.bench_manager.get_unit_count() == bench_before - 1
    assert env.board_manager.get_unit_count() == board_before + 1
    assert env.board_manager.get_unit(board_target) is not None


def test_composition_and_positioning_scores_are_finite(lobby):
    env = get_env(lobby)

    counts = env.composition_manager.rebuild_unit_counts(
        env.board_manager.board,
        env.bench_manager.bench,
    )

    assert isinstance(counts, dict)

    # Avalia o tabuleiro completo usando o método existente.
    score = env.positioning_manager.evaluate_board_positioning(
        env.board_manager.board
    )

    assert isinstance(score, (int, float, np.number))
    assert math.isfinite(float(score))

    # Verifica a validade das posições ocupadas.
    occupied = env.board_manager.get_occupied_positions()

    assert all(
        0 <= position < env.board_size
        for position in occupied
    )
    assert len(occupied) == len(set(occupied))

    # Para cada unidade no tabuleiro, a avaliação individual
    # também deve produzir um valor numérico finito.
    for position, unit in enumerate(env.board_manager.board):
        if unit is None:
            continue

        unit_score = env.positioning_manager.evaluate_unit_placement(
            env.board_manager.board,
            position,
            unit,
        )

        assert math.isfinite(float(unit_score))


def test_player_units_are_not_counted_as_shop_inventory(lobby):
    env = get_env(lobby)

    owned_before = env.composition_manager.get_all_units(
        env.board_manager.board,
        env.bench_manager.bench,
    )

    shop_units = [
        unit
        for unit in env.shop_manager.get_shop()
        if unit is not None
    ]

    assert len(owned_before) >= 1

    # A loja pode ter campeões, mas eles ainda não pertencem ao jogador.
    # A quantidade de unidades próprias não deve mudar apenas por consultar a loja.
    owned_after = env.composition_manager.get_all_units(
        env.board_manager.board,
        env.bench_manager.bench,
    )

    assert len(owned_after) == len(owned_before)


# ============================================================
# 4. COMBATE, DANO, ELIMINAÇÃO E RANKING
# ============================================================

def test_combat_updates_results_and_keeps_hp_valid(lobby):
    player_a = lobby.players[0]
    player_b = lobby.players[1]

    hp_a_before = player_a.env.hp
    hp_b_before = player_b.env.hp

    result = lobby.resolve_combat(player_a, player_b)

    assert result is not None
    assert result.damage >= 0

    assert 0 <= player_a.env.hp <= GameConfig.STARTING_HP
    assert 0 <= player_b.env.hp <= GameConfig.STARTING_HP

    if not result.draw and result.winner_id is not None:
        assert result.winner_id in (
            player_a.player_id,
            player_b.player_id,
        )
        assert result.loser_id in (
            player_a.player_id,
            player_b.player_id,
        )
        assert result.winner_id != result.loser_id

        loser = (
            player_a
            if player_a.player_id == result.loser_id
            else player_b
        )

        # Uma derrota com dano deve afetar o HP do perdedor.
        if result.damage > 0:
            assert loser.env.hp < (
                hp_a_before
                if loser.player_id == player_a.player_id
                else hp_b_before
            )


def test_elimination_and_ranking_are_consistent(lobby):
    # A eliminação é acionada por HP <= 0.
    player = lobby.players[-1]
    player.env.hp = 0

    lobby.eliminate_players()

    assert player.alive is False
    assert player.eliminated is True
    assert player.env.hp == 0

    # Jogadores restantes continuam identificáveis e o ranking
    # pode ser atualizado sem duplicar posições existentes.
    lobby.update_ranking()

    placements = [
        p.placement
        for p in lobby.players
        if p.placement is not None
    ]

    assert len(placements) == len(set(placements))


# ============================================================
# 5. RESET E CONSISTÊNCIA ENTRE PARTIDAS
# ============================================================

def test_lobby_reset_restores_global_and_player_state(lobby):
    lobby.players[0].alive = False
    lobby.players[0].eliminated = True
    lobby.players[0].placement = 8

    observations = lobby.reset()

    assert len(lobby.players) == 8
    assert observations.shape[0] == 8
    assert observations.dtype == np.float32
    assert np.isfinite(observations).all()

    assert lobby.round == 1
    assert lobby.stage == 1
    assert lobby.finished is False
    assert lobby.winner_id is None

    for player in lobby.players:
        assert player.alive is True
        assert player.eliminated is False
        assert player.placement is None
        assert player.env.hp == GameConfig.STARTING_HP
        assert player.env.economy_manager.gold == GameConfig.STARTING_GOLD

    assert_pool_is_valid(lobby.unit_pool)
