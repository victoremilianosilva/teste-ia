from config.GameConfig import GameConfig


class EconomyManager:
    """
    💰 Economia de um único jogador.

    Responsabilidades:
        - gold
        - XP
        - level
        - juros
        - renda
        - streak
        - compra de XP

    Não controla:
        - shop
        - pool
        - board
        - combate
    """

    def __init__(self):
        self.reset()

    # =============================================================
    # 🔄 RESET
    # =============================================================

    def reset(self):
        self.gold = GameConfig.STARTING_GOLD

        self.level = GameConfig.STARTING_LEVEL
        self.xp = GameConfig.STARTING_XP

        self.win_streak = 0
        self.loss_streak = 0

        self.round_gold = 0
        self.round_interest = 0
        self.round_streak_gold = 0
        self.round_base_gold = 0
        self.round_win_gold = 0

    # =============================================================
    # 💰 GOLD
    # =============================================================

    def add_gold(self, amount):
        amount = max(0, int(amount))

        self.gold += amount

        return amount

    def can_spend(self, amount):
        amount = int(amount)

        if amount < 0:
            return False

        return self.gold >= amount

    def spend_gold(self, amount):
        amount = int(amount)

        if amount < 0:
            return False

        if not self.can_spend(amount):
            return False

        self.gold -= amount

        return True

    # =============================================================
    # 🏦 JUROS
    # =============================================================

    def get_interest(self, gold=None):
        """
        Calcula juros com base no gold armazenado.

        0-9   -> 0
        10-19 -> 1
        20-29 -> 2
        30-39 -> 3
        40-49 -> 4
        50+   -> 5
        """

        if gold is None:
            gold = self.gold

        gold = max(0, int(gold))

        return min(
            gold // 10,
            GameConfig.MAX_INTEREST,
        )

    # =============================================================
    # 🔥 STREAK
    # =============================================================

    def register_win(self):
        self.win_streak += 1
        self.loss_streak = 0

    def register_loss(self):
        self.loss_streak += 1
        self.win_streak = 0

    def reset_streak(self):
        self.win_streak = 0
        self.loss_streak = 0

    def get_streak(self):
        if self.win_streak > 0:
            return self.win_streak

        if self.loss_streak > 0:
            return -self.loss_streak

        return 0

    def get_streak_gold(self):
        return GameConfig.get_streak_gold(
            self.get_streak()
        )

    # =============================================================
    # ⭐ XP
    # =============================================================

    def get_xp_to_next(self):
        if self.level >= GameConfig.MAX_LEVEL:
            return 0

        return GameConfig.get_xp_to_next(
            self.level
        )

    def can_buy_xp(self):
        if self.level >= GameConfig.MAX_LEVEL:
            return False

        return self.can_spend(
            GameConfig.BUY_XP_COST
        )

    def buy_xp(self):
        old_level = self.level

        if not self.can_buy_xp():
            return {
                "success": False,
                "xp_gained": 0,
                "leveled_up": False,
                "old_level": old_level,
                "new_level": self.level,
            }

        if not self.spend_gold(
            GameConfig.BUY_XP_COST
        ):
            return {
                "success": False,
                "xp_gained": 0,
                "leveled_up": False,
                "old_level": old_level,
                "new_level": self.level,
            }

        self.xp += GameConfig.XP_PER_BUY

        self._check_level_up()

        return {
            "success": True,
            "xp_gained": GameConfig.XP_PER_BUY,
            "leveled_up": self.level > old_level,
            "old_level": old_level,
            "new_level": self.level,
        }

    def add_round_xp(self):
        """
        +2 XP grátis no fim de cada round.
        """

        if self.level >= GameConfig.MAX_LEVEL:
            return False

        old_level = self.level

        self.xp += GameConfig.XP_PER_ROUND

        self._check_level_up()

        return self.level > old_level

    def _check_level_up(self):
        """
        Aplica todos os level-ups possíveis.

        XP excedente permanece para o próximo nível.
        """

        while self.level < GameConfig.MAX_LEVEL:

            required = self.get_xp_to_next()

            if required <= 0:
                break

            if self.xp < required:
                break

            self.xp -= required
            self.level += 1

    # =============================================================
    # 🏆 VITÓRIA
    # =============================================================

    def register_pvp_win(self):
        """
        Vitória de PvP dá +1 gold.
        """

        self.register_win()

        self.add_gold(
            GameConfig.WIN_GOLD
        )

        self.round_win_gold += (
            GameConfig.WIN_GOLD
        )

    # =============================================================
    # 🌅 FINAL DO ROUND
    # =============================================================

    def resolve_round(self, round_number):
        """
        Resolve a economia do round.

        Ordem:

            1. calcula juros sobre gold guardado
            2. adiciona renda base
            3. adiciona streak
            4. adiciona XP grátis

        O +1 da vitória PvP é aplicado quando o combate
        termina, através de register_pvp_win().
        """

        round_number = int(round_number)

        old_gold = self.gold
        old_level = self.level

        # =========================================================
        # 🏦 JUROS
        # =========================================================
        #
        # IMPORTANTE:
        # Calcula ANTES de adicionar a renda do round.
        # =========================================================

        interest = self.get_interest(
            self.gold
        )

        # =========================================================
        # 💰 RENDA BASE
        # =========================================================

        base_gold = GameConfig.get_round_gold(
            round_number
        )

        # =========================================================
        # 🔥 STREAK
        # =========================================================

        streak_gold = self.get_streak_gold()

        # =========================================================
        # 💵 APLICA GOLD
        # =========================================================

        self.add_gold(base_gold)
        self.add_gold(interest)
        self.add_gold(streak_gold)

        # =========================================================
        # ⭐ XP
        # =========================================================

        leveled_up = self.add_round_xp()

        # =========================================================
        # 📊 ESTATÍSTICAS
        # =========================================================

        self.round_base_gold = base_gold
        self.round_interest = interest
        self.round_streak_gold = streak_gold

        self.round_gold = (
            self.gold - old_gold
        )

        result = {
            "round": round_number,

            "old_gold": old_gold,
            "new_gold": self.gold,

            "base_gold": base_gold,
            "passive_gold": base_gold,

            "interest_gold": interest,
            "streak_gold": streak_gold,
            "win_gold": self.round_win_gold,

            "total_gold": (
                base_gold
                + interest
                + streak_gold
                + self.round_win_gold
            ),

            "old_level": old_level,
            "new_level": self.level,

            "leveled_up": leveled_up,

            "xp": self.xp,
            "xp_to_next": self.get_xp_to_next(),
        }

        self.round_win_gold = 0

        return result

    # =============================================================
    # 📊 STATE
    # =============================================================

    def get_state(self):
        return {
            "gold": self.gold,

            "level": self.level,
            "xp": self.xp,
            "xp_to_next": self.get_xp_to_next(),

            "win_streak": self.win_streak,
            "loss_streak": self.loss_streak,
            "streak": self.get_streak(),

            "interest": self.get_interest(),
            "streak_gold": self.get_streak_gold(),
        }

    # =============================================================
    # 🐛 DEBUG
    # =============================================================

    def debug_print(self):
        print()
        print("=" * 45)
        print("💰 ECONOMY")
        print("=" * 45)

        print(
            f"Gold       : {self.gold}"
        )

        print(
            f"Level      : {self.level}"
        )

        print(
            f"XP         : "
            f"{self.xp}/{self.get_xp_to_next()}"
        )

        print(
            f"Win streak : {self.win_streak}"
        )

        print(
            f"Loss streak: {self.loss_streak}"
        )

        print(
            f"Interest   : {self.get_interest()}"
        )

        print(
            f"Streak gold: {self.get_streak_gold()}"
        )

        print("=" * 45)