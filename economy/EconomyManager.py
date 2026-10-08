# economy/EconomyManager.py

from config.GameConfig import GameConfig


class EconomyManager:
    """
    💰 Gerencia a economia de um único jogador.

    Responsabilidades:
        - gold
        - XP
        - level
        - juros
        - ganho de gold
        - compra de XP
        - streak
        - controle econômico por round

    NÃO é responsabilidade:
        - board
        - bench
        - shop
        - UnitPool
        - combate
        - estratégia
        - reward
    """

    def __init__(self):
        self.reset()

    # =============================================================
    # 🔄 RESET
    # =============================================================

    def reset(self):
        """Reseta a economia do jogador."""

        self.gold = GameConfig.STARTING_GOLD

        self.level = 1
        self.xp = 0

        self.win_streak = 0
        self.loss_streak = 0

        self.round_gold = 0
        self.round_interest = 0
        self.round_streak_gold = 0

    # =============================================================
    # 💰 GOLD
    # =============================================================

    def add_gold(self, amount):
        """Adiciona gold ao jogador."""

        amount = max(
            0,
            int(amount)
        )

        self.gold += amount

        return amount

    def can_spend(self, amount):
        """Verifica se o jogador possui gold suficiente."""

        return (
            self.gold >= amount
        )

    def spend_gold(self, amount):
        """
        Gasta gold.

        Retorna False caso não tenha gold suficiente.
        """

        amount = int(amount)

        if amount < 0:
            return False

        if not self.can_spend(amount):
            return False

        self.gold -= amount

        return True

    # =============================================================
    # 📈 JUROS
    # =============================================================

    def get_interest(self):
        """
        Calcula o gold de juros.

        TFT utiliza 1 gold por cada 10 gold guardados,
        limitado a 5.

        Exemplo:

            0-9   -> 0
            10-19 -> 1
            20-29 -> 2
            30-39 -> 3
            40-49 -> 4
            50+   -> 5
        """

        return min(
            self.gold // 10,
            5
        )

    # =============================================================
    # 🔥 STREAK
    # =============================================================

    def register_win(self):
        """Registra uma vitória."""

        self.win_streak += 1
        self.loss_streak = 0

    def register_loss(self):
        """Registra uma derrota."""

        self.loss_streak += 1
        self.win_streak = 0

    def reset_streak(self):
        """Reseta as duas streaks."""

        self.win_streak = 0
        self.loss_streak = 0

    def get_streak(self):
        """
        Retorna a streak atual.

        Positivo = vitória
        Negativo = derrota
        """

        if self.win_streak > 0:
            return self.win_streak

        if self.loss_streak > 0:
            return -self.loss_streak

        return 0

    # =============================================================
    # 💵 GOLD DE STREAK
    # =============================================================

    def get_streak_gold(self):
        """
        Calcula gold adicional proveniente da streak.

        Mantemos simples por enquanto.

        2-3 = +1
        4-5 = +2
        6+  = +3
        """

        streak = abs(
            self.get_streak()
        )

        if streak < 2:
            return 0

        if streak <= 3:
            return 1

        if streak <= 5:
            return 2

        return 3

    # =============================================================
    # ⭐ XP
    # =============================================================

    def get_xp_to_next(self):
        """
        Retorna XP necessário para o próximo nível.
        """

        if self.level >= GameConfig.MAX_LEVEL:
            return 999

        return GameConfig.get_xp_to_next(
            self.level
        )

    def can_buy_xp(self):
        """
        Verifica se é possível comprar XP.
        """

        if self.level >= GameConfig.MAX_LEVEL:
            return False

        return self.can_spend(
            GameConfig.BUY_XP_COST
        )

    def buy_xp(self):
        """
        Compra XP.

        Retorna:

            {
                "success": bool,
                "xp_gained": int,
                "leveled_up": bool,
                "old_level": int,
                "new_level": int
            }
        """

        old_level = self.level

        if not self.can_buy_xp():

            return {
                "success": False,
                "xp_gained": 0,
                "leveled_up": False,
                "old_level": old_level,
                "new_level": self.level,
            }

        self.spend_gold(
            GameConfig.BUY_XP_COST
        )

        self.xp += GameConfig.XP_PER_BUY

        self._check_level_up()

        return {
            "success": True,
            "xp_gained": GameConfig.XP_PER_BUY,
            "leveled_up": (
                self.level > old_level
            ),
            "old_level": old_level,
            "new_level": self.level,
        }

    # =============================================================
    # 📈 XP PASSIVO
    # =============================================================

    def add_round_xp(self):
        """
        Adiciona XP automático ao final do round.
        """

        if self.level >= GameConfig.MAX_LEVEL:
            return False

        old_level = self.level

        self.xp += GameConfig.XP_PER_ROUND

        self._check_level_up()

        return self.level > old_level

    # =============================================================
    # ⬆️ LEVEL UP
    # =============================================================

    def _check_level_up(self):
        """
        Verifica e aplica todos os level ups possíveis.
        """

        while self.level < GameConfig.MAX_LEVEL:

            required = self.get_xp_to_next()

            if self.xp < required:
                break

            self.xp -= required

            self.level += 1

    # =============================================================
    # 🌅 FINAL DO ROUND
    # =============================================================

    def resolve_round(self):
        """
        Resolve a parte econômica do final do round.

        Retorna informações para o Env/RewardManager.

        IMPORTANTE:

        O Lobby continuará sendo responsável pelo avanço
        global do round.

        Este método apenas resolve a economia deste jogador.
        """

        old_gold = self.gold
        old_level = self.level

        # ---------------------------------------------------------
        # 💰 Gold base
        # ---------------------------------------------------------

        passive_gold = (
            GameConfig.PASSIVE_GOLD_PER_ROUND
        )

        self.add_gold(
            passive_gold
        )

        # ---------------------------------------------------------
        # 💵 Juros
        # ---------------------------------------------------------

        interest = self.get_interest()

        self.add_gold(
            interest
        )

        # ---------------------------------------------------------
        # 🔥 Streak
        # ---------------------------------------------------------

        streak_gold = (
            self.get_streak_gold()
        )

        self.add_gold(
            streak_gold
        )

        # ---------------------------------------------------------
        # 📈 XP
        # ---------------------------------------------------------

        leveled_up = self.add_round_xp()

        # ---------------------------------------------------------
        # 📊 Estatísticas do round
        # ---------------------------------------------------------

        self.round_gold = (
            self.gold - old_gold
        )

        self.round_interest = interest

        self.round_streak_gold = (
            streak_gold
        )

        return {
            "old_gold": old_gold,
            "new_gold": self.gold,

            "passive_gold": passive_gold,
            "interest_gold": interest,
            "streak_gold": streak_gold,

            "total_gold": (
                passive_gold
                + interest
                + streak_gold
            ),

            "old_level": old_level,
            "new_level": self.level,
            "leveled_up": leveled_up,

            "xp": self.xp,
        }

    # =============================================================
    # 📊 ESTADO
    # =============================================================

    def get_state(self):
        """
        Retorna estado econômico para debug/observation.
        """

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
        """Imprime o estado econômico."""

        print(
            "\n========== ECONOMY =========="
        )

        print(
            f"💰 Gold: {self.gold}"
        )

        print(
            f"⭐ Level: {self.level}"
        )

        print(
            f"📈 XP: {self.xp}/"
            f"{self.get_xp_to_next()}"
        )

        print(
            f"🔥 Win streak: {self.win_streak}"
        )

        print(
            f"💀 Loss streak: {self.loss_streak}"
        )

        print(
            f"🏦 Interest: {self.get_interest()}"
        )

        print(
            "============================="
        )