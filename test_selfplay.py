import random
import traceback

import numpy as np

from config.GameConfig import GameConfig
from lobby.TFTLobby import TFTLobby


# ============================================================
# CONFIG
# ============================================================

SEED = 42
MAX_TEST_ROUNDS = 30
NUM_PLAYERS = 8

# Mostra as ações escolhidas pelos jogadores.
SHOW_ACTIONS = True

# Mostra a composição da shop.
SHOW_SHOP = True

# Mostra detalhes econômicos.
SHOW_ECONOMY = True

# Mostra detalhes do pool.
SHOW_POOL = True


# ============================================================
# HELPERS
# ============================================================

def choose_from_mask(mask):
    """
    Escolhe aleatoriamente uma ação válida dentro de uma máscara.
    """

    valid = np.flatnonzero(
        np.asarray(mask, dtype=np.float32) > 0
    )

    if len(valid) == 0:
        return 0

    return int(
        random.choice(valid.tolist())
    )


def action_name(action_type):
    """
    Converte o índice da ação para nome legível.
    """

    names = {
        0: "BUY",
        1: "REROLL",
        2: "BUY_XP",
        3: "MOVE_BENCH",
        4: "MOVE_BOARD",
        5: "SELL",
        6: "PASS",
    }

    return names.get(
        int(action_type),
        f"UNKNOWN({action_type})"
    )


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

        type_mask = masks.get(
            "type",
            masks.get("action_type")
        )

        if type_mask is None:
            raise RuntimeError(
                f"Máscara sem action type: "
                f"{masks.keys()}"
            )

        action_type_value = choose_from_mask(
            type_mask
        )

        shop_mask = masks.get(
            "shop",
            np.ones(5)
        )

        bench_mask = masks.get(
            "bench",
            np.ones(9)
        )

        board_target_mask = masks.get(
            "board_target",
            np.ones(28)
        )

        board_source_mask = masks.get(
            "board_source",
            np.ones(28)
        )

        conditioned_target_mask = masks.get(
            "conditioned_board_target",
            np.ones(28)
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

        action_type_value = choose_from_mask(
            masks[0]
        )

        shop_mask = masks[1]
        bench_mask = masks[2]
        board_target_mask = masks[3]
        board_source_mask = masks[4]
        conditioned_target_mask = masks[5]

    else:

        raise RuntimeError(
            f"Formato de máscara desconhecido: "
            f"{type(masks)}"
        )

    # --------------------------------------------------------
    # Monta ação
    # --------------------------------------------------------

    action = [
        action_type_value,
        choose_from_mask(shop_mask),
        choose_from_mask(bench_mask),
        choose_from_mask(board_target_mask),
        choose_from_mask(board_source_mask),
        choose_from_mask(conditioned_target_mask),
    ]

    return action


# ============================================================
# PLAYER HELPERS
# ============================================================

def get_player_id(player):
    """
    Extrai o ID de um jogador independentemente do formato.
    """

    if hasattr(player, "player_id"):
        return player.player_id

    if isinstance(player, (int, np.integer)):
        return int(player)

    if isinstance(player, dict):

        if "player_id" in player:
            return player["player_id"]

        if "id" in player:
            return player["id"]

    return str(player)


def get_economy(player):
    """
    Retorna o EconomyManager do jogador.
    """

    if not hasattr(player, "env"):
        return None

    return getattr(
        player.env,
        "economy_manager",
        None,
    )


def get_shop_units(player):
    """
    Retorna a shop atual do jogador.
    """

    if not hasattr(player, "env"):
        return []

    shop_manager = getattr(
        player.env,
        "shop_manager",
        None,
    )

    if shop_manager is None:
        return []

    try:
        shop = shop_manager.get_shop()

        if shop is None:
            return []

        return shop

    except Exception:
        return []


def get_unit_name(unit):
    """
    Extrai nome de uma unidade de forma tolerante.
    """

    if unit is None:
        return "---"

    if isinstance(unit, dict):

        return (
            unit.get("name")
            or unit.get("characterName")
            or unit.get("apiName")
            or unit.get("champion_id")
            or "UNKNOWN"
        )

    return str(unit)


def get_unit_cost(unit):
    """
    Extrai custo da unidade.
    """

    if unit is None:
        return None

    if isinstance(unit, dict):

        value = (
            unit.get("cost")
            or unit.get("tier")
            or unit.get("price")
        )

        try:
            return int(value)

        except (TypeError, ValueError):
            return None

    return None


def get_unit_star(unit):
    """
    Extrai estrela da unidade.
    """

    if unit is None:
        return None

    if isinstance(unit, dict):

        value = unit.get(
            "star",
            unit.get(
                "stars",
                1
            )
        )

        try:
            return int(value)

        except (TypeError, ValueError):
            return None

    return None


# ============================================================
# SHOP PRINT
# ============================================================

def format_shop(player):
    """
    Formata a shop:

        [0] Ashe 1★ $1
        [1] Garen 2★ $2
        ...
    """

    shop = get_shop_units(player)

    if not shop:
        return "Shop indisponível"

    result = []

    for slot, unit in enumerate(shop):

        if unit is None:
            result.append(
                f"[{slot}] ---"
            )

            continue

        name = get_unit_name(unit)
        cost = get_unit_cost(unit)
        star = get_unit_star(unit)

        cost_text = (
            f"${cost}"
            if cost is not None
            else "$?"
        )

        star_text = (
            f"{star}★"
            if star is not None
            else "?★"
        )

        result.append(
            f"[{slot}] "
            f"{name} "
            f"{star_text} "
            f"{cost_text}"
        )

    return " | ".join(result)


# ============================================================
# BOARD / BENCH
# ============================================================

def get_board_count(player):
    """
    Quantidade de unidades no board.
    """

    try:
        return len(
            player.env.board_manager
            .get_occupied_positions()
        )

    except Exception:
        return 0


def get_bench_count(player):
    """
    Quantidade de unidades no bench.
    """

    try:
        return len(
            player.env.bench_manager
            .get_occupied_slots()
        )

    except Exception:
        return 0


# ============================================================
# RANKING
# ============================================================

def get_ranking(lobby):
    """
    Obtém o ranking final do lobby.
    """

    if hasattr(lobby, "final_ranking"):

        ranking = lobby.final_ranking

        if ranking is not None:
            return ranking

    if hasattr(lobby, "ranking"):

        ranking = lobby.ranking

        if ranking is not None:
            return ranking

    if hasattr(lobby, "get_ranking"):

        ranking = lobby.get_ranking()

        if ranking is not None:
            return ranking

    # --------------------------------------------------------
    # Fallback
    # --------------------------------------------------------

    players = list(
        lobby.players
    )

    players.sort(
        key=lambda player: (
            not player.env.done,
            player.env.hp,
            player.wins,
            -player.losses,
        ),
        reverse=True,
    )

    return players


def print_ranking(lobby):
    """
    Imprime ranking final.
    """

    ranking = get_ranking(lobby)

    print()
    print("🏆 RANKING FINAL")
    print("-" * 75)

    if not ranking:
        print("Nenhum ranking disponível.")
        return

    for position, player in enumerate(
        ranking,
        start=1,
    ):

        player_id = get_player_id(player)

        # ----------------------------------------------------
        # LobbyPlayer
        # ----------------------------------------------------

        if hasattr(player, "env"):

            env = player.env

            print(
                f"{position:2d}º - "
                f"Player {player_id} | "
                f"HP={env.hp:3d} | "
                f"W={player.wins:2d} | "
                f"L={player.losses:2d}"
            )

            continue

        # ----------------------------------------------------
        # ID
        # ----------------------------------------------------

        if isinstance(
            player,
            (int, np.integer)
        ):

            player_id = int(player)

            real_player = None

            if (
                0 <= player_id
                < len(lobby.players)
            ):

                candidate = (
                    lobby.players[player_id]
                )

                if (
                    candidate.player_id
                    == player_id
                ):
                    real_player = candidate

            if real_player is not None:

                env = real_player.env

                print(
                    f"{position:2d}º - "
                    f"Player {player_id} | "
                    f"HP={env.hp:3d} | "
                    f"W={real_player.wins:2d} | "
                    f"L={real_player.losses:2d}"
                )

            else:

                print(
                    f"{position:2d}º - "
                    f"Player {player_id}"
                )

            continue

        # ----------------------------------------------------
        # Dict
        # ----------------------------------------------------

        if isinstance(player, dict):

            hp = player.get(
                "hp",
                "?"
            )

            wins = player.get(
                "wins",
                "?"
            )

            losses = player.get(
                "losses",
                "?"
            )

            print(
                f"{position:2d}º - "
                f"Player {player_id} | "
                f"HP={hp} | "
                f"W={wins} | "
                f"L={losses}"
            )

            continue

        # ----------------------------------------------------
        # Fallback
        # ----------------------------------------------------

        print(
            f"{position:2d}º - "
            f"Player {player_id}"
        )


# ============================================================
# VALIDATE OBSERVATIONS
# ============================================================

def validate_observations(lobby):

    observations = lobby.get_observations()

    if observations is None:
        raise RuntimeError(
            "get_observations() retornou None."
        )

    if len(observations) != NUM_PLAYERS:
        raise RuntimeError(
            f"Esperado {NUM_PLAYERS} observations, "
            f"recebido {len(observations)}."
        )

    for player_id, obs in enumerate(
        observations
    ):

        if obs is None:
            continue

        obs = np.asarray(obs)

        if obs.ndim != 1:

            raise RuntimeError(
                f"Player {player_id}: "
                f"observation não é 1D: "
                f"shape={obs.shape}"
            )

        if not np.all(
            np.isfinite(obs)
        ):

            raise RuntimeError(
                f"Player {player_id}: "
                f"observation possui NaN ou Inf."
            )


# ============================================================
# VALIDATE MASKS
# ============================================================

def validate_masks(lobby):

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

    for player_id, player_masks in enumerate(
        masks
    ):

        if isinstance(
            player_masks,
            dict
        ):

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

        elif isinstance(
            player_masks,
            (list, tuple)
        ):

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


# ============================================================
# VALIDATE ECONOMY
# ============================================================

def validate_economy(lobby):
    """
    Valida regras básicas da economia.
    """

    for player in lobby.players:

        env = player.env
        economy = env.economy_manager

        # ----------------------------------------------------
        # Gold
        # ----------------------------------------------------

        if economy.gold < 0:

            raise RuntimeError(
                f"Player {player.player_id}: "
                f"gold negativo: {economy.gold}"
            )

        # ----------------------------------------------------
        # Level
        # ----------------------------------------------------

        if economy.level < GameConfig.STARTING_LEVEL:

            raise RuntimeError(
                f"Player {player.player_id}: "
                f"level inválido: "
                f"{economy.level}"
            )

        if economy.level > GameConfig.MAX_LEVEL:

            raise RuntimeError(
                f"Player {player.player_id}: "
                f"level acima do máximo: "
                f"{economy.level}"
            )

        # ----------------------------------------------------
        # XP
        # ----------------------------------------------------

        if economy.xp < 0:

            raise RuntimeError(
                f"Player {player.player_id}: "
                f"XP negativo."
            )

        # ----------------------------------------------------
        # Streak
        # ----------------------------------------------------

        if economy.win_streak > 0:
            if economy.loss_streak != 0:

                raise RuntimeError(
                    f"Player {player.player_id}: "
                    f"win_streak e loss_streak "
                    f"simultaneamente ativos."
                )

        if economy.loss_streak > 0:
            if economy.win_streak != 0:

                raise RuntimeError(
                    f"Player {player.player_id}: "
                    f"loss_streak e win_streak "
                    f"simultaneamente ativos."
                )

        # ----------------------------------------------------
        # Interest
        # ----------------------------------------------------

        interest = economy.get_interest()

        expected_interest = min(
            economy.gold // 10,
            GameConfig.MAX_INTEREST,
        )

        if interest != expected_interest:

            raise RuntimeError(
                f"Player {player.player_id}: "
                f"interest inconsistente. "
                f"Atual={interest}, "
                f"Esperado={expected_interest}"
            )


# ============================================================
# VALIDATE PLAYERS
# ============================================================

def validate_players(lobby):

    if len(lobby.players) != NUM_PLAYERS:

        raise RuntimeError(
            f"Lobby deveria possuir "
            f"{NUM_PLAYERS} jogadores, "
            f"possui {len(lobby.players)}."
        )

    for player in lobby.players:

        env = player.env

        # ----------------------------------------------------
        # HP
        # ----------------------------------------------------

        if env.hp < 0:

            raise RuntimeError(
                f"Player {player.player_id}: "
                f"HP negativo."
            )

        if env.hp > GameConfig.STARTING_HP:

            raise RuntimeError(
                f"Player {player.player_id}: "
                f"HP acima do inicial."
            )

        # ----------------------------------------------------
        # BOARD
        # ----------------------------------------------------

        occupied_board = get_board_count(
            player
        )

        if occupied_board > GameConfig.BOARD_SIZE:

            raise RuntimeError(
                f"Player {player.player_id}: "
                f"board excedeu capacidade."
            )

        # ----------------------------------------------------
        # BENCH
        # ----------------------------------------------------

        occupied_bench = get_bench_count(
            player
        )

        if occupied_bench > GameConfig.MAX_BENCH:

            raise RuntimeError(
                f"Player {player.player_id}: "
                f"bench excedeu capacidade."
            )


# ============================================================
# VALIDATE UNIT POOL
# ============================================================

def validate_unit_pool(lobby):

    pool = lobby.unit_pool

    if pool is None:

        raise RuntimeError(
            "Lobby não possui UnitPool."
        )

    if not pool.validate():

        raise RuntimeError(
            "UnitPool inválido."
        )

    for champion_id, available in (
        pool.available.items()
    ):

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


# ============================================================
# SNAPSHOT ECONOMY
# ============================================================

def snapshot_players(lobby):
    """
    Guarda estado antes do round.

    Usado para calcular deltas.
    """

    snapshot = {}

    for player in lobby.players:

        economy = player.env.economy_manager

        snapshot[player.player_id] = {
            "hp": player.env.hp,
            "gold": economy.gold,
            "xp": economy.xp,
            "level": economy.level,
            "win_streak": economy.win_streak,
            "loss_streak": economy.loss_streak,
            "wins": player.wins,
            "losses": player.losses,
        }

    return snapshot


def print_round_changes(
    lobby,
    previous_snapshot,
):
    """
    Mostra mudanças econômicas depois do round.
    """

    print()
    print("📈 ALTERAÇÕES DO ROUND")
    print("-" * 110)

    for player in lobby.players:

        old = previous_snapshot.get(
            player.player_id
        )

        if old is None:
            continue

        economy = player.env.economy_manager

        gold_delta = (
            economy.gold
            - old["gold"]
        )

        xp_delta = (
            economy.xp
            - old["xp"]
        )

        hp_delta = (
            player.env.hp
            - old["hp"]
        )

        win_delta = (
            player.wins
            - old["wins"]
        )

        loss_delta = (
            player.losses
            - old["losses"]
        )

        print(
            f"P{player.player_id} | "
            f"Gold {old['gold']:2d} -> "
            f"{economy.gold:2d} "
            f"({gold_delta:+3d}) | "
            f"XP {old['xp']:2d} -> "
            f"{economy.xp:2d} "
            f"({xp_delta:+3d}) | "
            f"Lvl {old['level']} -> "
            f"{economy.level} | "
            f"HP {old['hp']:3d} -> "
            f"{player.env.hp:3d} "
            f"({hp_delta:+4d}) | "
            f"W {old['wins']} -> "
            f"{player.wins} "
            f"({win_delta:+2d}) | "
            f"L {old['losses']} -> "
            f"{player.losses} "
            f"({loss_delta:+2d})"
        )


# ============================================================
# PRINT ACTIONS
# ============================================================

def print_actions(
    lobby,
    actions,
):
    """
    Mostra as ações escolhidas pelos jogadores.
    """

    print()
    print("🎲 AÇÕES")
    print("-" * 90)

    for player_id, action in enumerate(
        actions
    ):

        player = lobby.players[player_id]

        if player.env.done:

            print(
                f"P{player_id} | DEAD | PASS"
            )

            continue

        action_type = action[0]

        print(
            f"P{player_id} | "
            f"{action_name(action_type):10s} | "
            f"shop={action[1]} | "
            f"bench={action[2]} | "
            f"target={action[3]} | "
            f"source={action[4]} | "
            f"cond={action[5]}"
        )


# ============================================================
# PRINT SHOP
# ============================================================

def print_shops(lobby):

    if not SHOW_SHOP:
        return

    print()
    print("🛒 SHOPS")
    print("-" * 120)

    for player in lobby.players:

        if player.env.done:

            print(
                f"P{player.player_id} | DEAD"
            )

            continue

        economy = player.env.economy_manager

        print(
            f"P{player.player_id} | "
            f"Gold={economy.gold:2d} | "
            f"{format_shop(player)}"
        )


# ============================================================
# PRINT ECONOMY DETAILS
# ============================================================

def print_economy_details(lobby):

    if not SHOW_ECONOMY:
        return

    print()
    print("💰 ECONOMIA DETALHADA")
    print("-" * 120)

    for player in lobby.players:

        economy = player.env.economy_manager

        streak = economy.get_streak()

        if streak > 0:
            streak_text = (
                f"W{streak}"
            )
        elif streak < 0:
            streak_text = (
                f"L{abs(streak)}"
            )
        else:
            streak_text = "0"

        print(
            f"P{player.player_id} | "
            f"Gold={economy.gold:2d} | "
            f"Lvl={economy.level:2d} | "
            f"XP={economy.xp:2d}/"
            f"{economy.get_xp_to_next():2d} | "
            f"Interest={economy.get_interest()} | "
            f"Streak={streak_text:>3s} | "
            f"StreakGold="
            f"{economy.get_streak_gold()}"
        )


# ============================================================
# PRINT LOBBY STATUS
# ============================================================

def print_lobby_status(lobby):

    print()
    print("=" * 120)

    print(
        f"ROUND {lobby.round} | "
        f"STAGE {lobby.stage}"
    )

    print("=" * 120)

    for player in lobby.players:

        env = player.env
        economy = env.economy_manager

        alive = not env.done

        status = (
            "ALIVE"
            if alive
            else "DEAD"
        )

        board_count = get_board_count(
            player
        )

        bench_count = get_bench_count(
            player
        )

        streak = economy.get_streak()

        if streak > 0:
            streak_text = f"W{streak}"
        elif streak < 0:
            streak_text = f"L{abs(streak)}"
        else:
            streak_text = "-"

        print(
            f"P{player.player_id} | "
            f"{status:<5} | "
            f"HP={env.hp:3d} | "
            f"Gold={economy.gold:2d} | "
            f"Lvl={economy.level:2d} | "
            f"XP={economy.xp:2d}/"
            f"{economy.get_xp_to_next():2d} | "
            f"Int={economy.get_interest()} | "
            f"Streak={streak_text:<3} | "
            f"Board={board_count:2d} | "
            f"Bench={bench_count:2d} | "
            f"W={player.wins:2d} | "
            f"L={player.losses:2d}"
        )

    # --------------------------------------------------------
    # Pool
    # --------------------------------------------------------

    if SHOW_POOL:

        available = (
            lobby.unit_pool
            .get_total_available()
        )

        initial = (
            lobby.unit_pool
            .get_total_initial()
        )

        taken = (
            lobby.unit_pool
            .get_total_taken()
        )

        print()
        print(
            f"🌐 POOL | "
            f"Disponível={available} | "
            f"Tomadas={taken} | "
            f"Inicial={initial}"
        )


# ============================================================
# RULE VALIDATION
# ============================================================

def validate_rules(lobby):
    """
    Valida as regras fundamentais adicionadas nesta etapa.
    """

    # --------------------------------------------------------
    # XP / LEVEL
    # --------------------------------------------------------

    if GameConfig.MAX_LEVEL != 10:

        raise RuntimeError(
            "MAX_LEVEL deveria ser 10."
        )

    expected_xp = {
        2: 2,
        3: 6,
        4: 10,
        5: 20,
        6: 36,
        7: 56,
        8: 68,
        9: 68,
    }

    for level, xp in expected_xp.items():

        actual = (
            GameConfig.get_xp_to_next(
                level
            )
        )

        if actual != xp:

            raise RuntimeError(
                f"XP inválido no level {level}: "
                f"atual={actual}, "
                f"esperado={xp}"
            )

    # --------------------------------------------------------
    # SHOP ODDS
    # --------------------------------------------------------

    for level, odds in (
        GameConfig.SHOP_ODDS.items()
    ):

        total = sum(odds)

        if not np.isclose(
            total,
            1.0,
            atol=1e-6,
        ):

            raise RuntimeError(
                f"Shop odds do level {level} "
                f"não somam 100%: {total}"
            )

    # --------------------------------------------------------
    # POOL
    # --------------------------------------------------------

    expected_pool = {
        1: 30,
        2: 25,
        3: 18,
        4: 10,
        5: 9,
    }

    actual_pool = getattr(
        lobby.unit_pool,
        "copies_by_cost",
        None,
    )

    if actual_pool is not None:

        for cost, expected in (
            expected_pool.items()
        ):

            actual = actual_pool.get(
                cost
            )

            if actual != expected:

                raise RuntimeError(
                    f"Pool do custo {cost} "
                    f"incorreto: "
                    f"atual={actual}, "
                    f"esperado={expected}"
                )

    # --------------------------------------------------------
    # ECONOMY
    # --------------------------------------------------------

    for player in lobby.players:

        economy = player.env.economy_manager

        if economy.level < 2:

            raise RuntimeError(
                f"Player {player.player_id}: "
                f"começou abaixo do level 2."
            )

        if economy.gold < 0:

            raise RuntimeError(
                f"Player {player.player_id}: "
                f"gold negativo."
            )


# ============================================================
# MAIN TEST
# ============================================================

def main():

    print()
    print("=" * 120)
    print("                    TFT SELF-PLAY RULES TEST")
    print("=" * 120)

    print()
    print(f"Seed           : {SEED}")
    print(f"Players        : {NUM_PLAYERS}")
    print(f"Max rounds     : {MAX_TEST_ROUNDS}")
    print(f"Max level      : {GameConfig.MAX_LEVEL}")
    print(
        f"Pool           : "
        f"30 / 25 / 18 / 10 / 9"
    )
    print(
        f"Reroll         : "
        f"{GameConfig.REROLL_COST} gold"
    )
    print(
        f"Buy XP         : "
        f"{GameConfig.BUY_XP_COST} gold "
        f"→ {GameConfig.XP_PER_BUY} XP"
    )
    print(
        f"Round XP       : "
        f"+{GameConfig.XP_PER_ROUND}"
    )
    print(
        f"Win gold       : "
        f"+{GameConfig.WIN_GOLD}"
    )
    print()

    # --------------------------------------------------------
    # Seeds
    # --------------------------------------------------------

    random.seed(SEED)
    np.random.seed(SEED)

    try:

        # ====================================================
        # 1. CRIAR LOBBY
        # ====================================================

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
                f"Lobby deveria ter "
                f"{NUM_PLAYERS} jogadores."
            )

        # ====================================================
        # 2. RESET
        # ====================================================

        print("[2/6] Resetando lobby...")

        lobby.reset()

        print("      Reset OK.")

        # ====================================================
        # 3. VALIDAÇÕES INICIAIS
        # ====================================================

        print(
            "[3/6] Validando estado inicial..."
        )

        validate_observations(lobby)
        validate_masks(lobby)
        validate_players(lobby)
        validate_economy(lobby)
        validate_unit_pool(lobby)
        validate_rules(lobby)

        print("      Observations OK.")
        print("      Masks OK.")
        print("      Players OK.")
        print("      Economy OK.")
        print("      UnitPool OK.")
        print("      Rules OK.")

        print_lobby_status(lobby)

        print_economy_details(lobby)
        print_shops(lobby)

        # ====================================================
        # 4. SELF-PLAY
        # ====================================================

        print()
        print(
            "[4/6] Iniciando self-play..."
        )
        print()

        rounds_completed = 0

        for test_round in range(
            1,
            MAX_TEST_ROUNDS + 1,
        ):

            # ------------------------------------------------
            # Lobby terminou?
            # ------------------------------------------------

            if lobby.is_finished():

                print(
                    "\n🏁 Lobby terminou antes do "
                    f"round {test_round}."
                )

                break

            # ------------------------------------------------
            # Snapshot ANTES do round
            # ------------------------------------------------

            previous_snapshot = (
                snapshot_players(
                    lobby
                )
            )

            # ------------------------------------------------
            # Obter máscaras
            # ------------------------------------------------

            masks = (
                lobby.get_action_masks()
            )

            # ------------------------------------------------
            # Criar ações
            # ------------------------------------------------

            actions = []

            for player_id, player in enumerate(
                lobby.players
            ):

                # ------------------------------------------------
                # Jogador morto
                # ------------------------------------------------

                if player.env.done:

                    actions.append(
                        [
                            6,
                            0,
                            0,
                            0,
                            0,
                            0,
                        ]
                    )

                    continue

                # ------------------------------------------------
                # Jogador vivo
                # ------------------------------------------------

                action = build_random_action(
                    masks[player_id]
                )

                actions.append(action)

            # ------------------------------------------------
            # Mostrar ações
            # ------------------------------------------------

            if SHOW_ACTIONS:

                print_actions(
                    lobby,
                    actions,
                )

            # ------------------------------------------------
            # Executar passo
            # ------------------------------------------------

            lobby.step(actions)

            rounds_completed += 1

            # ------------------------------------------------
            # Validações
            # ------------------------------------------------

            validate_observations(
                lobby
            )

            validate_masks(
                lobby
            )

            validate_players(
                lobby
            )

            validate_economy(
                lobby
            )

            validate_unit_pool(
                lobby
            )

            validate_rules(
                lobby
            )

            # ------------------------------------------------
            # Status
            # ------------------------------------------------

            print_lobby_status(
                lobby
            )

            # ------------------------------------------------
            # Economia
            # ------------------------------------------------

            print_round_changes(
                lobby,
                previous_snapshot,
            )

            print_economy_details(
                lobby
            )

            # ------------------------------------------------
            # Shop
            # ------------------------------------------------

            print_shops(
                lobby
            )

        # ====================================================
        # 5. RESULTADO FINAL
        # ====================================================

        print()
        print(
            "[5/6] Resultado final"
        )

        print()
        print(
            f"Rounds executados: "
            f"{rounds_completed}"
        )

        print_lobby_status(
            lobby
        )

        # ----------------------------------------------------
        # Ranking
        # ----------------------------------------------------

        print_ranking(
            lobby
        )

        # ====================================================
        # 6. UNIT POOL FINAL
        # ====================================================

        print()
        print(
            "[6/6] Validação final do UnitPool..."
        )

        validate_unit_pool(
            lobby
        )

        available = (
            lobby.unit_pool
            .get_total_available()
        )

        initial = (
            lobby.unit_pool
            .get_total_initial()
        )

        taken = (
            lobby.unit_pool
            .get_total_taken()
        )

        print()
        print(
            f"      Cópias iniciais    : "
            f"{initial}"
        )

        print(
            f"      Cópias disponíveis : "
            f"{available}"
        )

        print(
            f"      Cópias tomadas     : "
            f"{taken}"
        )

        print(
            f"      Integridade        : "
            f"{'OK' if available + taken == initial else 'ERRO'}"
        )

        # ====================================================
        # FINAL
        # ====================================================

        print()
        print("=" * 120)
        print("                    TESTE FINALIZADO")
        print("=" * 120)
        print()

    except Exception as exc:

        print()
        print("=" * 120)
        print("                         ERRO NO TESTE")
        print("=" * 120)

        print()

        print(
            f"{type(exc).__name__}: {exc}"
        )

        print()
        print("TRACEBACK COMPLETO:")
        print()

        traceback.print_exc()

        print()
        print("=" * 120)

        raise


# ============================================================
# ENTRY POINT
# ============================================================

if __name__ == "__main__":
    main()