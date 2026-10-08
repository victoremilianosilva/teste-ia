from pathlib import Path


class GameConfig:
    """
    ⚙️ Configurações estáticas do jogo.

    IMPORTANTE:
    - Não guarda estado de um jogador.
    - Não guarda gold, HP, board, bench etc.
    - Pode ser compartilhado entre os 8 jogadores.
    """

    # =========================================================
    # 📂 ARQUIVOS
    # =========================================================

    BASE_DIR = Path(__file__).resolve().parent.parent

    UNITS_PATH = BASE_DIR / "units.json"
    TRAITS_PATH = BASE_DIR / "traits.json"

    # =========================================================
    # 🎮 JOGO
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

    # =========================================================
    # 💰 ECONOMIA
    # =========================================================

    STARTING_GOLD = 0

    PASSIVE_GOLD_PER_ROUND = 5

    REROLL_COST = 2

    BUY_XP_COST = 4

    XP_PER_BUY = 4

    XP_PER_ROUND = 2

    # =========================================================
    # 📈 XP / LEVEL
    # =========================================================

    XP_TO_NEXT = {
        1: 2,
        2: 2,
        3: 6,
        4: 12,
        5: 20,
        6: 32,
        7: 50,
        8: 80,
        9: 999,
    }

    MAX_LEVEL = 9

    # =========================================================
    # 🛒 SHOP ODDS
    # =========================================================

    SHOP_ODDS = {
        1: [1.00, 0.00, 0.00, 0.00, 0.00],
        2: [0.75, 0.25, 0.00, 0.00, 0.00],
        3: [0.55, 0.30, 0.15, 0.00, 0.00],
        4: [0.25, 0.40, 0.30, 0.05, 0.00],
        5: [0.15, 0.30, 0.35, 0.15, 0.05],
        6: [0.10, 0.20, 0.35, 0.25, 0.10],
        7: [0.05, 0.15, 0.30, 0.35, 0.15],
        8: [0.03, 0.10, 0.25, 0.35, 0.27],
        9: [0.01, 0.05, 0.15, 0.30, 0.49],
    }

    # =========================================================
    # 🧠 IA / ACTION LIMITS
    # =========================================================

    MAX_ACTIONS_PER_ROUND = 20

    # =========================================================
    # 🧬 TRAITS
    # =========================================================

    TRAIT_EMBEDDING_DIM = 8

    # =========================================================
    # ⭐ UNIDADES
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
    # ⚔️ COMBATE
    # =========================================================

    # 📝 Somente configurações que ainda fazem sentido
    # para o novo sistema PvP.
    #
    # NÃO colocamos aqui:
    # - enemy_stage_power
    # - inimigos artificiais
    # - regras do antigo PvE
    # - combate contra "máquina"

    STAGE_DAMAGE = {
        1: 0,
        2: 1,
        3: 2,
        4: 4,
        5: 6,
        6: 9,
        7: 14,
    }

    # =========================================================
    # 🎯 HELPERS
    # =========================================================

    @classmethod
    def get_xp_to_next(cls, level):
        """
        Retorna o XP necessário para o próximo nível.
        """
        return cls.XP_TO_NEXT.get(level, 999)

    @classmethod
    def get_shop_odds(cls, level):
        """
        Retorna as probabilidades da loja para determinado nível.
        """
        return cls.SHOP_ODDS.get(
            level,
            cls.SHOP_ODDS[max(cls.SHOP_ODDS)]
        )

    @classmethod
    def get_star_copies(cls, star):
        """
        Quantidade equivalente de cópias de uma unidade.
        """
        return cls.STAR_COPIES.get(star, 1)