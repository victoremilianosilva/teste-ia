import random
import traceback

import numpy as np

from config.GameConfig import GameConfig
from lobby.tft_loby import TFTLobby


# ============================================================
# CONFIG
# ============================================================

SEED = 42
MAX_TEST_ROUNDS = 30
NUM_PLAYERS = 8


# ============================================================
# HELPERS
# ============================================================

def choose_from_mask(mask):
    """
    Escolhe aleatoriamente uma ação válida dentro de uma máscara.
    """
    valid = np.flatnonzero(np.asarray(mask, dtype=np.float32) > 0)

    if len(valid) == 0:
        return 0

    return int(random.choice(valid.tolist()))


def build_random_action(masks):
    """
    Monta uma ação no formato esperado pelo TFTLobby.

    Estrutura:

        [
            action_type,
            shop_slot,
            bench_slot,
            board_target,
            board_source,
            conditioned_board_target
        ]
    """

    # --------------------------------------------------------
    # Caso a máscara venha como dict
    # --------------------------------------------------------

    if isinstance(masks, dict):
        type_mask = masks.get("type", masks.get("action_type"))

        if type_mask is None:
            raise RuntimeError(
                f"Máscara sem action type: {masks.keys()}"
            )

        action_type = choose_from_mask(type_mask)

        shop_mask = masks.get("shop", np.ones(5))
        bench_mask = masks.get("bench", np.ones(9))
        board_target_mask = masks.get(
            "board_target",
            np.ones(28),
        )
        board_source_mask = masks.get(
            "board_source",
            np.ones(28),
        )
        conditioned_target_mask = masks.get(
            "conditioned_board_target",
            np.ones(28),
        )

    # --------------------------------------------------------
    # Caso a máscara seja uma lista/tupla
    # --------------------------------------------------------

    elif isinstance(masks, (list, tuple)):
        if len(masks) < 6:
            raise RuntimeError(
                f"Máscara com apenas {len(masks)} dimensões. "
                f"Esperado: 6."
            )

        action_type = choose_from_mask(masks[0])

        shop_mask = masks[1]
        bench_mask = masks[2]
        board_target_mask = masks[3]
        board_source_mask = masks[4]
        conditioned_target_mask = masks[5]

    else:
        raise RuntimeError(
            f"Formato de máscara desconhecido: {type(masks)}"
        )

    # --------------------------------------------------------
    # Monta ação
    # --------------------------------------------------------

    action = [
        action_type,
        choose_from_mask(shop_mask),
        choose_from_mask(bench_mask),
        choose_from_mask(board_target_mask),
        choose_from_mask(board_source_mask),
        choose_from_mask(conditioned_target_mask),
    ]

    return action


def validate_observations(lobby):
    """
    Verifica se os jogadores estão produzindo observações válidas.
    """

    observations = lobby.get_observations()

    if observations is None:
        raise RuntimeError("get_observations() retornou None.")

    if len(observations) != NUM_PLAYERS:
        raise RuntimeError(
            f"Esperado {NUM_PLAYERS} observations, "
            f"recebido {len(observations)}."
        )

    for player_id, obs in enumerate(observations):

        if obs is None:
            continue

        obs = np.asarray(obs)

        if obs.ndim != 1:
            raise RuntimeError(
                f"Player {player_id}: observation "
                f"não é 1D: shape={obs.shape}"
            )

        if not np.all(np.isfinite(obs)):
            raise RuntimeError(
                f"Player {player_id}: observation possui "
                f"NaN ou Inf."
            )


def validate_masks(lobby):
    """
    Verifica as máscaras dos 8 jogadores.
    """

    masks = lobby.get_action_masks()

    if masks is None:
        raise RuntimeError(
            "get_action_masks() retornou None."
        )

    if len(masks) != NUM_PLAYERS:
        raise RuntimeError(
            f"Esperado {NUM_PLAYERS} máscaras, "
            f"recebido {len(masks)}."
        )

    for player_id, player_masks in enumerate(masks):

        if isinstance(player_masks, dict):

            required = [
                "type",
                "shop",
                "bench",
                "board_target",
                "board_source",
                "conditioned_board_target",
            ]

            for key in required:
                if key not in player_masks:
                    raise RuntimeError(
                        f"Player {player_id}: "
                        f"máscara sem '{key}'."
                    )

        elif isinstance(player_masks, (list, tuple)):

            if len(player_masks) != 6:
                raise RuntimeError(
                    f"Player {player_id}: "
                    f"esperado 6 máscaras, "
                    f"recebido {len(player_masks)}."
                )

        else:
            raise RuntimeError(
                f"Player {player_id}: "
                f"formato de máscara inválido: "
                f"{type(player_masks)}"
            )


def validate_players(lobby):
    """
    Verifica o estado básico dos 8 jogadores.
    """

    if len(lobby.players) != NUM_PLAYERS:
        raise RuntimeError(
            f"Lobby deveria possuir {NUM_PLAYERS} jogadores, "
            f"possui {len(lobby.players)}."
        )

    for player in lobby.players:

        env = player.env

        # HP
        if env.hp < 0:
            raise RuntimeError(
                f"Player {player.player_id}: HP negativo."
            )

        if env.hp > GameConfig.STARTING_HP:
            raise RuntimeError(
                f"Player {player.player_id}: "
                f"HP acima do inicial."
            )

        # Board
        occupied_board = len(
            env.board_manager.get_occupied_positions()
        )

        if occupied_board > GameConfig.BOARD_SIZE:
            raise RuntimeError(
                f"Player {player.player_id}: "
                f"board excedeu capacidade."
            )

        # Bench
        occupied_bench = len(
            env.bench_manager.get_occupied_slots()
        )

        if occupied_bench > GameConfig.MAX_BENCH:
            raise RuntimeError(
                f"Player {player.player_id}: "
                f"bench excedeu capacidade."
            )


def validate_unit_pool(lobby):
    """
    Verifica a integridade do UnitPool global.
    """

    pool = lobby.unit_pool

    if pool is None:
        raise RuntimeError(
            "Lobby não possui UnitPool."
        )

    if not pool.validate():
        raise RuntimeError(
            "UnitPool inválido."
        )

    for champion_id, available in pool.available.items():

        initial = pool.initial_counts.get(
            champion_id,
            0,
        )

        if available < 0:
            raise RuntimeError(
                f"Pool: champion {champion_id} "
                f"ficou negativo."
            )

        if available > initial:
            raise RuntimeError(
                f"Pool: champion {champion_id} "
                f"possui mais cópias disponíveis "
                f"que o inicial."
            )


def print_lobby_status(lobby):
    """
    Imprime um resumo da partida.
    """

    print()
    print("=" * 70)
    print(
        f"ROUND {lobby.round} | "
        f"STAGE {lobby.stage}"
    )
    print("=" * 70)

    for player in lobby.players:

        env = player.env

        alive = not env.done

        board_count = len(
            env.board_manager.get_occupied_positions()
        )

        bench_count = len(
            env.bench_manager.get_occupied_slots()
        )

        gold = env.economy_manager.gold
        level = env.economy_manager.level

        status = "ALIVE" if alive else "DEAD"

        print(
            f"P{player.player_id} | "
            f"{status:<5} | "
            f"HP={env.hp:3d} | "
            f"Gold={gold:2d} | "
            f"Lvl={level} | "
            f"Board={board_count:2d} | "
            f"Bench={bench_count:2d} | "
            f"W={player.wins} | "
            f"L={player.losses}"
        )

    print(
        f"\nPool: "
        f"{lobby.unit_pool.get_total_available()} "
        f"/ "
        f"{lobby.unit_pool.get_total_initial()}"
    )


# ============================================================
# MAIN TEST
# ============================================================

def main():

    print()
    print("=" * 70)
    print("        TFT SELF-PLAY INTEGRATION TEST")
    print("=" * 70)
    print()

    random.seed(SEED)
    np.random.seed(SEED)

    try:

        # ----------------------------------------------------
        # Criar lobby
        # ----------------------------------------------------

        print("[1/6] Criando lobby...")

        lobby = TFTLobby(
            seed=SEED
        )

        print(
            f"      Lobby criado com "
            f"{len(lobby.players)} jogadores."
        )

        if len(lobby.players) != NUM_PLAYERS:
            raise RuntimeError(
                f"Lobby deveria ter {NUM_PLAYERS} jogadores."
            )

        # ----------------------------------------------------
        # Reset
        # ----------------------------------------------------

        print("[2/6] Resetando lobby...")

        lobby.reset()

        print("      Reset OK.")

        # ----------------------------------------------------
        # Validações iniciais
        # ----------------------------------------------------

        print("[3/6] Validando estado inicial...")

        validate_observations(lobby)
        validate_masks(lobby)
        validate_players(lobby)
        validate_unit_pool(lobby)

        print("      Observations OK.")
        print("      Masks OK.")
        print("      Players OK.")
        print("      UnitPool OK.")

        print_lobby_status(lobby)

        # ----------------------------------------------------
        # Self-play
        # ----------------------------------------------------

        print()
        print("[4/6] Iniciando self-play...")
        print()

        for test_round in range(
            1,
            MAX_TEST_ROUNDS + 1,
        ):

            if lobby.is_finished():
                print(
                    "\nLobby terminou antes do "
                    f"round {test_round}."
                )
                break

            # ------------------------------------------------
            # Obter máscaras
            # ------------------------------------------------

            masks = lobby.get_action_masks()

            # ------------------------------------------------
            # Criar ações para os 8 jogadores
            # ------------------------------------------------

            actions = []

            for player_id, player in enumerate(
                lobby.players
            ):

                # Jogador morto/eliminado
                if player.env.done:

                    actions.append(
                        [6, 0, 0, 0, 0, 0]
                    )

                    continue

                # Jogador vivo
                action = build_random_action(
                    masks[player_id]
                )

                actions.append(action)

            # ------------------------------------------------
            # Executar passo
            # ------------------------------------------------

            lobby.step(actions)

            # ------------------------------------------------
            # Validar depois do passo
            # ------------------------------------------------

            validate_observations(lobby)
            validate_masks(lobby)
            validate_players(lobby)
            validate_unit_pool(lobby)

            print_lobby_status(lobby)

        # ----------------------------------------------------
        # Resultado
        # ----------------------------------------------------

        print()
        print("[5/6] Resultado final")
        print()

        print_lobby_status(lobby)

        if hasattr(
            lobby,
            "final_ranking",
        ):
            print("\nRanking:")

            for position, player in enumerate(
                lobby.final_ranking,
                start=1,
            ):
                print(
                    f"{position}º - "
                    f"Player {player.player_id}"
                )

        # ----------------------------------------------------
        # Pool final
        # ----------------------------------------------------

        print()
        print("[6/6] Validação final do UnitPool...")

        validate_unit_pool(lobby)

        print(
            f"      Cópias iniciais : "
            f"{lobby.unit_pool.get_total_initial()}"
        )

        print(
            f"      Cópias disponíveis: "
            f"{lobby.unit_pool.get_total_available()}"
        )

        print(
            f"      Cópias tomadas   : "
            f"{lobby.unit_pool.get_total_taken()}"
        )

        print()
        print("=" * 70)
        print("              TESTE FINALIZADO")
        print("=" * 70)
        print()

    except Exception as exc:

        print()
        print("=" * 70)
        print("                  ERRO NO TESTE")
        print("=" * 70)

        print()
        print(
            f"{type(exc).__name__}: {exc}"
        )

        print()
        print("TRACEBACK COMPLETO:")
        print()

        traceback.print_exc()

        print()
        print("=" * 70)

        raise


if __name__ == "__main__":
    main()
