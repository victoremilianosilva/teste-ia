from pathlib import Path


class GameConfig:
    """
    ⚙️ Configurações estáticas do TFT.

    Não guarda estado de jogador.
    Pode ser compartilhado entre todos os jogadores da lobby.
    """

    # =========================================================
    # 📂 ARQUIVOS
    # =========================================================

    BASE_DIR = Path(__file__).resolve().parent.parent

    UNITS_PATH = BASE_DIR / "units.json"
    TRAITS_PATH = BASE_DIR / "traits.json"

    # =========================================================
    # 🎮 LOBBY
    # =========================================================

    NUM_PLAYERS = 8
    MAX_ROUNDS = 45

    # =========================================================
    # 🧩 TABULEIRO
    # =========================================================

    BOARD_ROWS = 4
    BOARD_COLS = 7
    BOARD_SIZE = BOARD_ROWS * BOARD_COLS

    MAX_BENCH = 9
    SHOP_SIZE = 5

    # =========================================================
    # ❤️ JOGADOR
    # =========================================================

    STARTING_HP = 100

    # TFT começa no nível 2.
    STARTING_LEVEL = 2
    STARTING_XP = 0

    # =========================================================
    # 💰 ECONOMIA
    # =========================================================

    STARTING_GOLD = 0

    REROLL_COST = 2

    BUY_XP_COST = 4
    XP_PER_BUY = 4
    XP_PER_ROUND = 2

    # =========================================================
    # 💵 RENDA BASE POR ROUND
    # =========================================================
    #
    # O lobby usa round global:
    #
    # round 1 -> abertura / 1-1
    # round 2 -> 1-2
    # round 3 -> 1-3
    # round 4 -> 1-4
    # round 5 -> 2-1
    # round 6+ -> 2-2+
    #
    # O round 1 não entrega a renda normal.
    # =========================================================

    ROUND_GOLD = {
        1: 0,
        2: 2,
        3: 2,
        4: 3,
        5: 4,
    }

    DEFAULT_ROUND_GOLD = 5

    # =========================================================
    # 🏦 JUROS
    # =========================================================

    INTEREST_PER_10_GOLD = 1
    MAX_INTEREST = 5

    # =========================================================
    # 🔥 STREAK
    # =========================================================
    #
    # 0-1 -> +0
    # 2-4 -> +1
    # 5   -> +2
    # 6+  -> +3
    #
    # Vale tanto para WIN quanto LOSS streak.
    # =========================================================

    STREAK_GOLD = {
        2: 1,
        3: 1,
        4: 1,
        5: 2,
    }

    STREAK_GOLD_AT_6_PLUS = 3

    # Vitória em PvP.
    WIN_GOLD = 1

    # =========================================================
    # ⭐ XP / LEVEL
    # =========================================================
    #
    # Nível inicial = 2
    #
    # Level 2 -> 3 = 2 XP
    # Level 3 -> 4 = 6 XP
    # Level 4 -> 5 = 10 XP
    # Level 5 -> 6 = 20 XP
    # Level 6 -> 7 = 36 XP
    # Level 7 -> 8 = 56 XP
    # Level 8 -> 9 = 68 XP
    # Level 9 -> 10 = 68 XP
    # =========================================================

    XP_TO_NEXT = {
        2: 2,
        3: 6,
        4: 10,
        5: 20,
        6: 36,
        7: 56,
        8: 68,
        9: 68,
    }

    MAX_LEVEL = 10

    # =========================================================
    # 🛒 SHOP ODDS
    # =========================================================
    #
    # Índices:
    #
    # [1-cost, 2-cost, 3-cost, 4-cost, 5-cost]
    #
    # Cada slot da loja faz seu próprio sorteio.
    # =========================================================

    SHOP_ODDS = {
        1: [1.00, 0.00, 0.00, 0.00, 0.00],
        2: [1.00, 0.00, 0.00, 0.00, 0.00],
        3: [0.75, 0.25, 0.00, 0.00, 0.00],
        4: [0.55, 0.30, 0.15, 0.00, 0.00],
        5: [0.45, 0.33, 0.20, 0.02, 0.00],
        6: [0.30, 0.40, 0.25, 0.05, 0.00],
        7: [0.16, 0.30, 0.43, 0.10, 0.01],
        8: [0.15, 0.20, 0.32, 0.30, 0.03],
        9: [0.10, 0.17, 0.25, 0.33, 0.15],
        10: [0.05, 0.10, 0.20, 0.40, 0.25],
    }

    # =========================================================
    # 🧠 IA
    # =========================================================

    MAX_ACTIONS_PER_ROUND = 20

    # =========================================================
    # 🧬 TRAITS
    # =========================================================

    TRAIT_EMBEDDING_DIM = 8

    # =========================================================
    # ⭐ STAR
    # =========================================================

    STAR_COPIES = {
        1: 1,
        2: 3,
        3: 9,
    }

    STAR_MULTIPLIER = {
        1: 1,
        2: 3,
        3: 9,
    }

    # =========================================================
    # 💥 PLAYER DAMAGE
    # =========================================================
    #
    # Dano = dano base do estágio
    #       + unidades sobreviventes do vencedor
    #
    # Não usamos power difference.
    # =========================================================

    STAGE_DAMAGE = {
        1: 0,
        2: 2,
        3: 6,
        4: 7,
        5: 10,
        6: 12,
        7: 17,
    }

    STAGE_DAMAGE_DEFAULT = 17

    # =========================================================
    # 🎯 HELPERS
    # =========================================================

    @classmethod
    def get_xp_to_next(cls, level):
        if level >= cls.MAX_LEVEL:
            return 0

        return cls.XP_TO_NEXT.get(level, 0)

    @classmethod
    def get_shop_odds(cls, level):
        if level in cls.SHOP_ODDS:
            return cls.SHOP_ODDS[level]

        max_level = max(cls.SHOP_ODDS)

        return cls.SHOP_ODDS[max_level]

    @classmethod
    def get_round_gold(cls, round_number):
        round_number = int(round_number)

        return cls.ROUND_GOLD.get(
            round_number,
            cls.DEFAULT_ROUND_GOLD,
        )

    @classmethod
    def get_streak_gold(cls, streak):
        streak = abs(int(streak))

        if streak < 2:
            return 0

        if streak >= 6:
            return cls.STREAK_GOLD_AT_6_PLUS

        return cls.STREAK_GOLD.get(streak, 0)

    @classmethod
    def get_stage_damage(cls, stage):
        stage = int(stage)

        return cls.STAGE_DAMAGE.get(
            stage,
            cls.STAGE_DAMAGE_DEFAULT,
        )

    @classmethod
    def get_star_copies(cls, star):
        return cls.STAR_COPIES.get(
            int(star),
            1,
        )