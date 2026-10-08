import random
from copy import deepcopy

from config.GameConfig import GameConfig


class ShopManager:
    """
    🛒 Shop individual do jogador.

    O UnitPool é global.
    O ShopManager apenas retira/devolve cópias.
    """

    def __init__(
        self,
        unit_pool,
        shop_size=None,
        shop_odds=None,
    ):
        self.unit_pool = unit_pool

        self.shop_size = (
            shop_size
            if shop_size is not None
            else GameConfig.SHOP_SIZE
        )

        self.shop_odds = (
            shop_odds
            if shop_odds is not None
            else GameConfig.SHOP_ODDS
        )

        self.shop = self._create_empty_shop()

        self.locked = False

    # =============================================================
    # 🧱 ESTRUTURA
    # =============================================================

    def _create_empty_shop(self):
        return [None] * self.shop_size

    def reset(self):
        self.shop = self._create_empty_shop()
        self.locked = False

    # =============================================================
    # 🔎 CONSULTA
    # =============================================================

    def get_unit(self, slot):
        if not self.is_valid_slot(slot):
            return None

        return self.shop[slot]

    def get_shop(self):
        return [
            deepcopy(unit)
            if unit is not None
            else None
            for unit in self.shop
        ]

    def is_empty(self, slot):
        if not self.is_valid_slot(slot):
            return False

        return self.shop[slot] is None

    def is_valid_slot(self, slot):
        return (
            isinstance(slot, int)
            and 0 <= slot < self.shop_size
        )

    # =============================================================
    # 🎲 ROLL
    # =============================================================

    def roll(self, level, force=False):
        """
        Gera uma nova loja.

        Cada slot faz seu próprio sorteio de custo.
        """

        if self.locked and not force:
            return self.get_shop()

        # Devolve a loja antiga.
        self.return_current_shop()

        odds = self._get_shop_odds(level)

        for slot in range(self.shop_size):

            cost = self._roll_cost(odds)

            champion = self._draw_from_pool(
                cost
            )

            # Não substituímos o custo sorteado
            # por outra raridade.
            self.shop[slot] = champion

        return self.get_shop()

    # =============================================================
    # 🎯 ODDS
    # =============================================================

    def _get_shop_odds(self, level):
        level = int(level)

        return GameConfig.get_shop_odds(
            level
        )

    def _roll_cost(self, odds):
        costs = list(
            range(
                1,
                len(odds) + 1
            )
        )

        return random.choices(
            costs,
            weights=odds,
            k=1,
        )[0]

    # =============================================================
    # 🌐 UNIT POOL
    # =============================================================

    def _draw_from_pool(self, cost):
        if self.unit_pool is None:
            raise RuntimeError(
                "ShopManager precisa de um UnitPool."
            )

        return self.unit_pool.draw(
            cost
        )

    # =============================================================
    # 🛒 COMPRA
    # =============================================================

    def take_unit(self, slot):
        """
        Remove a unidade da loja.

        A cópia NÃO retorna ao pool.
        Ela passa a pertencer ao jogador.
        """

        if not self.is_valid_slot(slot):
            return None

        unit = self.shop[slot]

        if unit is None:
            return None

        self.shop[slot] = None

        return unit

    # =============================================================
    # ↩️ DEVOLVER SHOP
    # =============================================================

    def return_current_shop(self):
        for slot in range(self.shop_size):

            unit = self.shop[slot]

            if unit is None:
                continue

            self._return_to_pool(
                unit
            )

            self.shop[slot] = None

    def _return_to_pool(self, unit):
        if self.unit_pool is None:
            raise RuntimeError(
                "ShopManager precisa de um UnitPool."
            )

        self.unit_pool.return_unit(
            unit
        )

    # =============================================================
    # 🔄 REROLL
    # =============================================================

    def reroll(self, level):
        return self.roll(
            level,
            force=True,
        )

    # =============================================================
    # 🔒 LOCK
    # =============================================================

    def set_locked(self, locked=True):
        self.locked = bool(locked)

    def is_locked(self):
        return self.locked

    def toggle_lock(self):
        self.locked = not self.locked

        return self.locked

    # =============================================================
    # 📊 STATE
    # =============================================================

    def get_state(self):
        return {
            "shop": self.get_shop(),
            "locked": self.locked,
        }