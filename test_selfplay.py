# ============================================================
# 🧪 test_selfplay.py
#
# Teste de integração:
#
# MiniTFTEnv
#     ↓
# TFTLobby
#     ↓
# UnitPool GLOBAL
#     ↓
# 8 jogadores
#     ↓
# ações aleatórias com MASK
#     ↓
# matchmaking
#     ↓
# combate
#     ↓
# dano / eliminação
#
# NÃO treina PPO.
# Serve apenas para validar a arquitetura.
# ============================================================

import random
import traceback

import numpy as np

from lobby.TFTLobby import TFTLobby


# ============================================================
# ⚙️ CONFIG
# ============================================================

NUM_PLAYERS = 8
MAX_TEST_ROUNDS = 30

# Para o teste ser reproduzível.
RANDOM_SEED = 42


# ============================================================
# 🎲 RANDOM ACTION
# ============================================================

def choose_from_mask(mask):
    """
    Recebe uma máscara 1D e retorna um índice válido.

    Exemplo:

        [0, 1, 0, 0, 1]

    retorna 1 ou 4.
    """

    if mask is None:
        return 0

    values = np.asarray(mask).reshape(-1)

    valid = np.flatnonzero(values > 0)

    if len(valid) == 0:
        return 0

    return int(random.choice(valid.tolist()))


def build_random_action(masks):
    """
    Constrói uma ação no formato:

        [
            type,
            shop_slot,
            bench_slot,
            board_target,
            board_source,
            conditioned_board_target
        ]

    respeitando as máscaras da ActionMaskManager.
    """

    # --------------------------------------------------------
    # Caso a máscara venha como dict
    # --------------------------------------------------------

    if isinstance(masks, dict):

        type_mask = masks.get(
            "type",
            masks.get("action_type")
        )

        shop_mask = masks.get(
            "shop_slot",
            masks.get("shop")
        )

        bench_mask = masks.get(
            "bench_slot",
            masks.get("bench_source")
        )

        board_target_mask = masks.get(
            "board_target"
        )

        board_source_mask = masks.get(
            "board_source"
        )

        conditioned_target_mask = masks.get(
            "conditioned_board_target",
            masks.get("board_move_target")
        )

    # --------------------------------------------------------
    # Caso seja lista/tupla:
    #
    # [type, shop, bench, target, source, conditioned]
    # --------------------------------------------------------

    elif isinstance(masks, (list, tuple)):

        values = list(masks)

        while len(values) < 6:
            values.append(None)

        (
            type_mask,
            shop_mask,
            bench_mask,
            board_target_mask,
            board_source_mask,
            conditioned_target_mask,
        ) = values[:6]

    else:

        # Segurança.
        return [6, 0, 0, 0, 0, 0]

    # --------------------------------------------------------
    # TYPE
    # --------------------------------------------------------

    action_type = choose_from_mask(
        type_mask
    )

    # --------------------------------------------------------
    # Defaults
    # --------------------------------------------------------

    shop_slot = 0
    bench_slot = 0
    board_target = 0
    board_source = 0
    conditioned_target = 0

    # --------------------------------------------------------
    # BUY
    # --------------------------------------------------------

    if action_type == 0:

        shop_slot = choose_from_mask(
            shop_mask
        )

    # --------------------------------------------------------
    # MOVE BENCH -> BOARD
    # --------------------------------------------------------

    elif action_type == 3:

        bench_slot = choose_from_mask(
            bench_mask
        )

        board_target = choose_from_mask(
            board_target_mask
        )

    # --------------------------------------------------------
    # MOVE BOARD -> BOARD
    # --------------------------------------------------------

    elif action_type == 4:

        board_source = choose_from_mask(
            board_source_mask
        )

        conditioned_target = choose_from_mask(
            conditioned_target_mask
        )

    # --------------------------------------------------------
    # SELL
    # --------------------------------------------------------

    elif action_type == 5:

        bench_slot = choose_from_mask(
            bench_mask
        )

    # --------------------------------------------------------
    # REROLL / XP / PASS
    # --------------------------------------------------------
    #
    # Não precisam de parâmetros extras.
    #

    return [
        int(action_type),
        int(shop_slot),
        int(bench_slot),
        int(board_target),
        int(board_source),
        int(conditioned_target),
    ]


# ============================================================
# 🧠 OBSERVATION TEST
# ============================================================

def validate_observations(lobby):
    """
    Valida observações dos 8 jogadores.
    """

    observations = lobby.get_observations()

    if len(observations) != NUM_PLAYERS:

        raise AssertionError(
            f"Esperado {NUM_PLAYERS} observations, "
            f"recebido {len(observations)}"
        )

    for player_id, obs in enumerate(observations):

        if obs is None:
            raise AssertionError(
                f"Player {player_id}: observation None"
            )

        obs = np.asarray(obs)

        if obs.ndim != 1:
            raise AssertionError(
                f"Player {player_id}: "
                f"observation não é 1D: {obs.shape}"
            )

        if not np.all(
            np.isfinite(obs)
        ):
            raise AssertionError(
                f"Player {player_id}: "
                "observation possui NaN/Inf"
            )

    print(
        f"   ✅ Observations válidas "
        f"({len(observations)} players)"
    )


# ============================================================
# 🎭 MASK TEST
# ============================================================

def validate_masks(lobby):
    """
    Valida que todos os players possuem máscaras.
    """

    masks = lobby.get_action_masks()

    if len(masks) != NUM_PLAYERS:

        raise AssertionError(
            f"Esperado {NUM_PLAYERS} máscaras, "
            f"recebido {len(masks)}"
        )

    for player_id, player_masks in enumerate(masks):

        if player_masks is None:

            raise AssertionError(
                f"Player {player_id}: masks None"
            )

        if isinstance(player_masks, dict):

            type_mask = player_masks.get(
                "type",
                player_masks.get("action_type")
            )

            if type_mask is None:

                raise AssertionError(
                    f"Player {player_id}: "
                    "máscara de type ausente"
                )

            if not np.any(
                np.asarray(type_mask) > 0
            ):

                raise AssertionError(
                    f"Player {player_id}: "
                    "nenhuma ação de type válida"
                )

        elif isinstance(
            player_masks,
            (list, tuple)
        ):

            if len(player_masks) < 6:

                raise AssertionError(
                    f"Player {player_id}: "
                    f"máscara possui apenas "
                    f"{len(player_masks)} dimensões"
                )

    print(
        "   ✅ Action masks válidas"
    )


# ============================================================
# ❤️ PLAYER STATE
# ============================================================

def validate_players(lobby):

    if len(lobby.players) != NUM_PLAYERS:

        raise AssertionError(
            f"Lobby deveria possuir "
            f"{NUM_PLAYERS} players"
        )

    for player in lobby.players:

        env = player.env

        if env.hp < 0:

            raise AssertionError(
                f"Player {player.player_id}: "
                f"HP negativo: {env.hp}"
            )

        if env.hp > GameConfig.STARTING_HP:
            raise AssertionError(
                f"Player {player.player_id}: "
                f"HP acima do máximo: {env.hp}"
            )

        board_count = len(
            env.board_manager
            .get_occupied_positions()
        )

        bench_count = len(
            env.bench_manager
            .get_occupied_slots()
        )

        if board_count > env.board_size:

            raise AssertionError(
                f"Player {player.player_id}: "
                f"board excedeu capacidade: "
                f"{board_count}"
            )

        if bench_count > env.max_bench:

            raise AssertionError(
                f"Player {player.player_id}: "
                f"bench excedeu capacidade: "
                f"{bench_count}"
            )

    print(
        "   ✅ Estado dos 8 jogadores válido"
    )


# ============================================================
# 🌐 UNIT POOL
# ============================================================

def validate_unit_pool(lobby):

    pool = lobby.unit_pool

    if pool is None:

        raise AssertionError(
            "TFTLobby não possui UnitPool global"
        )

    if not pool.validate():

        raise AssertionError(
            "UnitPool.validate() retornou False"
        )

    for champion_id, available in (
        pool.available.items()
    ):

        initial = pool.initial_counts.get(
            champion_id,
            0
        )

        if available < 0:

            raise AssertionError(
                f"Pool negativo: "
                f"champion={champion_id}, "
                f"available={available}"
            )

        if available > initial:

            raise AssertionError(
                f"Pool acima do inicial: "
                f"champion={champion_id}, "
                f"{available}/{initial}"
            )

    print(
        f"   ✅ UnitPool global válido "
        f"({pool.get_total_available()} "
        f"cópias disponíveis)"
    )


# ============================================================
# ⚔️ MATCHMAKING
# ============================================================

def validate_matchups(lobby):

    alive_ids = [
        player.player_id
        for player in lobby.players
        if not player.env.done
    ]

    seen = set()

    for matchup in lobby.matchups:

        if matchup is None:
            continue

        if not isinstance(
            matchup,
            (list, tuple)
        ):
            continue

        if len(matchup) != 2:
            continue

        player_a, player_b = matchup

        if player_a == player_b:

            raise AssertionError(
                f"Matchup inválido: "
                f"player contra si mesmo: "
                f"{player_a}"
            )

        if player_a not in alive_ids:
            raise AssertionError(
                f"Matchup contém player morto: "
                f"{player_a}"
            )

        if player_b not in alive_ids:
            raise AssertionError(
                f"Matchup contém player morto: "
                f"{player_b}"
            )

        pair = tuple(
            sorted(
                [player_a, player_b]
            )
        )

        if pair in seen:

            raise AssertionError(
                f"Matchup duplicado: {pair}"
            )

        seen.add(pair)

    print(
        f"   ✅ Matchmaking válido "
        f"({len(seen)} confrontos)"
    )


# ============================================================
# 📊 LOBBY STATUS
# ============================================================

def print_lobby_status(lobby):

    alive = [
        player
        for player in lobby.players
        if not player.env.done
    ]

    print()
    print(
        "┌─────────────────────────────────────────┐"
    )

    print(
        f"│ 🌐 ROUND {lobby.round:<5} "
        f"│ Alive: {len(alive):<2}              │"
    )

    print(
        "├─────────────────────────────────────────┤"
    )

    for player in lobby.players:

        env = player.env

        status = (
            "💀"
            if env.done
            else "🟢"
        )

        board_count = len(
            env.board_manager
            .get_occupied_positions()
        )

        bench_count = len(
            env.bench_manager
            .get_occupied_slots()
        )

        print(
            f"│ {status} P{player.player_id} "
            f"HP={env.hp:3d} "
            f"Gold={env.economy_manager.gold:2d} "
            f"Lv={env.economy_manager.level} "
            f"B={board_count} "
            f"Bench={bench_count:<2} │"
        )

    print(
        "└─────────────────────────────────────────┘"
    )


# ============================================================
# 🧪 MAIN TEST
# ============================================================

def main():

    random.seed(RANDOM_SEED)
    np.random.seed(RANDOM_SEED)

    print()
    print(
        "============================================================"
    )
    print(
        "🧪 TESTE DE SELF-PLAY TFT"
    )
    print(
        "============================================================"
    )

    # --------------------------------------------------------
    # 1️⃣ CRIA LOBBY
    # --------------------------------------------------------

    print()
    print("1️⃣ Criando TFTLobby...")

    lobby = TFTLobby(
        num_players=NUM_PLAYERS
    )

    print(
        "   ✅ Lobby criada"
    )

    # --------------------------------------------------------
    # 2️⃣ RESET
    # --------------------------------------------------------

    print()
    print("2️⃣ Resetando lobby...")

    result = lobby.reset()

    print(
        "   ✅ Reset concluído"
    )

    # --------------------------------------------------------
    # 3️⃣ VALIDATE INITIAL STATE
    # --------------------------------------------------------

    print()
    print("3️⃣ Validando estado inicial...")

    validate_observations(lobby)
    validate_masks(lobby)
    validate_players(lobby)
    validate_unit_pool(lobby)

    print_lobby_status(lobby)

    # --------------------------------------------------------
    # 4️⃣ LOOP SELF-PLAY
    # --------------------------------------------------------

    print()
    print(
        "4️⃣ Iniciando self-play..."
    )

    for test_round in range(
        1,
        MAX_TEST_ROUNDS + 1
    ):

        if lobby.is_finished():

            print()
            print(
                "🏆 Lobby terminou antes "
                f"da rodada {test_round}."
            )

            break

        print()
        print(
            f"🎮 TEST ROUND "
            f"{test_round}/{MAX_TEST_ROUNDS}"
        )

        # ----------------------------------------------------
        # Máscaras atuais
        # ----------------------------------------------------

        masks = lobby.get_action_masks()

        # ----------------------------------------------------
        # Uma ação por player
        # ----------------------------------------------------

        actions = []

        for player_id in range(
            NUM_PLAYERS
        ):

            player = lobby.players[
                player_id
            ]

            if player.env.done:

                # Player morto não joga.
                actions.append(
                    [
                        6,  # PASS
                        0,
                        0,
                        0,
                        0,
                        0,
                    ]
                )

                continue

            player_mask = masks[
                player_id
            ]

            action = build_random_action(
                player_mask
            )

            actions.append(action)

        # ----------------------------------------------------
        # Mostra ações
        # ----------------------------------------------------

        print(
            "   🎯 Ações:"
        )

        for player_id, action in enumerate(
            actions
        ):

            if lobby.players[
                player_id
            ].env.done:

                continue

            print(
                f"      P{player_id}: "
                f"{action}"
            )

        # ----------------------------------------------------
        # STEP DA LOBBY
        # ----------------------------------------------------

        try:

            step_result = lobby.step(
                actions
            )

        except Exception as exc:

            print()
            print(
                "❌ ERRO DURANTE lobby.step()"
            )

            print(
                f"Tipo: {type(exc).__name__}"
            )

            print(
                f"Mensagem: {exc}"
            )

            print()
            traceback.print_exc()

            raise

        # ----------------------------------------------------
        # VALIDAÇÕES
        # ----------------------------------------------------

        validate_players(lobby)
        validate_unit_pool(lobby)

        if lobby.matchups:

            validate_matchups(lobby)

        # ----------------------------------------------------
        # STATUS
        # ----------------------------------------------------

        print_lobby_status(lobby)

        # ----------------------------------------------------
        # FINAL
        # ----------------------------------------------------

        if lobby.is_finished():

            print()
            print(
                "🏆 PARTIDA TERMINOU!"
            )

            break

    # ========================================================
    # 🏁 RESULTADO
    # ========================================================

    print()
    print(
        "============================================================"
    )
    print(
        "🏁 TESTE FINALIZADO"
    )
    print(
        "============================================================"
    )

    # --------------------------------------------------------
    # Pool
    # --------------------------------------------------------

    validate_unit_pool(lobby)

    # --------------------------------------------------------
    # Ranking
    # --------------------------------------------------------

    print()
    print(
        "🏆 RANKING:"
    )

    ranking = getattr(
        lobby,
        "final_ranking",
        None
    )

    if ranking:

        for position, player_id in enumerate(
            ranking,
            start=1
        ):

            player = lobby.players[
                player_id
            ]

            print(
                f"   #{position} "
                f"P{player_id} "
                f"HP={player.env.hp}"
            )

    else:

        print(
            "   Partida ainda não terminou."
        )

    # --------------------------------------------------------
    # Global pool
    # --------------------------------------------------------

    pool = lobby.unit_pool

    print()
    print(
        "📦 UNIT POOL:"
    )

    print(
        f"   Inicial: "
        f"{pool.get_total_initial()}"
    )

    print(
        f"   Disponível: "
        f"{pool.get_total_available()}"
    )

    print(
        f"   Retirado: "
        f"{pool.get_total_taken()}"
    )

    # --------------------------------------------------------
    # SUCCESS
    # --------------------------------------------------------

    print()
    print(
        "✅ TODOS OS TESTES DE INTEGRAÇÃO "
        "PASSARAM."
    )

    print()


# ============================================================
# 🚀 ENTRY POINT
# ============================================================

if __name__ == "__main__":
    main()