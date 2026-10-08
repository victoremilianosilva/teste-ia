# shop/ShopManager.py

from copy import deepcopy

from config.GameConfig import GameConfig


class ShopManager:
    """
    🛒 Gerencia o shop individual de um jogador.

    IMPORTANTE:
    O ShopManager NÃO possui as cópias globais dos campeões.

    As cópias vêm do UnitPool global.

    Fluxo:

        UnitPool
            ↓
        ShopManager
            ↓
        jogador compra
            ↓
        MiniTFTEnv / UnitManager
            ↓
        unidade passa a ser propriedade do jogador

    Responsabilidades:
        - manter os 5 slots do shop
        - gerar shop utilizando o UnitPool
        - remover unidade comprada
        - devolver shop ao UnitPool
        - reroll
        - consultar slots

    NÃO é responsabilidade:
        - gold
        - compra propriamente dita
        - criação da unidade do jogador
        - board
        - bench
        - reward
        - estratégia
        - combate
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

        # 🔒 Preparado para lock de shop.
        # O action space atual não possui LOCK, então por enquanto
        # isso não interfere no fluxo.
        self.locked = False

    # =============================================================
    # 🧱 ESTRUTURA
    # =============================================================

    def _create_empty_shop(self):
        """
        Cria os slots vazios do shop.
        """

        return [None] * self.shop_size

    def reset(self):
        """
        Reseta o shop.

        IMPORTANTE:
        Quem chamar reset deve decidir se o shop antigo precisa
        ser devolvido ao UnitPool antes.

        Por isso este método NÃO devolve unidades automaticamente.
        """

        self.shop = self._create_empty_shop()
        self.locked = False

    # =============================================================
    # 🔎 CONSULTA
    # =============================================================

    def get_unit(self, slot):
        """
        Retorna o campeão presente em determinado slot.
        """

        if not self.is_valid_slot(slot):
            return None

        return self.shop[slot]

    def get_shop(self):
        """
        Retorna o estado atual do shop.

        Retorna cópias para evitar alteração acidental.
        """

        return [
            deepcopy(unit)
            if unit is not None
            else None
            for unit in self.shop
        ]

    def is_empty(self, slot):
        """
        Verifica se um slot está vazio.
        """

        if not self.is_valid_slot(slot):
            return False

        return self.shop[slot] is None

    def is_valid_slot(self, slot):
        """
        Verifica se o slot existe.
        """

        return (
            isinstance(slot, int)
            and 0 <= slot < self.shop_size
        )

    # =============================================================
    # 🎲 ROLL
    # =============================================================

    def roll(self, level, force=False):
        """
        Gera um novo shop utilizando o UnitPool.

        `level` determina as probabilidades de custo.

        force=True ignora o estado de lock.

        Retorna:
            cópia do shop atual.
        """

        if self.locked and not force:
            return self.get_shop()

        # ---------------------------------------------------------
        # 1️⃣ Devolve o shop antigo para o pool
        # ---------------------------------------------------------

        self.return_current_shop()

        # ---------------------------------------------------------
        # 2️⃣ Sorteia novos campeões
        # ---------------------------------------------------------

        odds = self._get_shop_odds(level)

        for slot in range(self.shop_size):

            cost = self._roll_cost(odds)

            champion = self._draw_from_pool(cost)

            # -----------------------------------------------------
            # Se não existir mais unidade daquele custo,
            # tentamos outros custos disponíveis.
            # -----------------------------------------------------

            if champion is None:
                champion = self._draw_fallback_from_pool(
                    preferred_cost=cost,
                    odds=odds,
                )

            self.shop[slot] = champion

        return self.get_shop()

    # =============================================================
    # 🎯 CUSTO
    # =============================================================

    def _get_shop_odds(self, level):
        """
        Retorna as probabilidades correspondentes ao nível.
        """

        if level in self.shop_odds:
            return self.shop_odds[level]

        # Usa o maior nível conhecido como fallback.
        max_level = max(self.shop_odds)

        return self.shop_odds[max_level]

    def _roll_cost(self, odds):
        """
        Sorteia o custo de uma unidade.

        odds:

            [custo1, custo2, custo3, custo4, custo5]
        """

        import random

        costs = list(range(1, len(odds) + 1))

        return random.choices(
            costs,
            weights=odds,
            k=1,
        )[0]

    # =============================================================
    # 🌐 UNIT POOL
    # =============================================================

    def _draw_from_pool(self, cost):
        """
        Solicita uma unidade de determinado custo ao UnitPool.

        O UnitPool será responsável por verificar se ainda existe
        uma cópia disponível.

        Contrato esperado:

            unit_pool.draw(cost)

        Retorno:
            campeão/unidade disponível
            ou None
        """

        if self.unit_pool is None:
            raise RuntimeError(
                "ShopManager precisa de um UnitPool."
            )

        return self.unit_pool.draw(cost)

    def _draw_fallback_from_pool(
        self,
        preferred_cost,
        odds,
    ):
        """
        Tenta encontrar outro custo caso o custo sorteado esteja
        esgotado no UnitPool.

        Isso evita deixar slots vazios simplesmente porque não há
        mais cópias daquele custo.
        """

        # Primeiro tenta o custo sorteado.
        champion = self._draw_from_pool(
            preferred_cost
        )

        if champion is not None:
            return champion

        # Depois tenta outros custos.
        costs = list(range(1, len(odds) + 1))

        # Coloca o custo original no final porque já tentamos.
        costs = [
            cost
            for cost in costs
            if cost != preferred_cost
        ]

        for cost in costs:

            champion = self._draw_from_pool(cost)

            if champion is not None:
                return champion

        # Pool realmente sem unidade disponível.
        return None

    # =============================================================
    # 🛒 COMPRA
    # =============================================================

    def take_unit(self, slot):
        """
        Remove uma unidade do shop e a entrega ao chamador.

        IMPORTANTE:

        A unidade NÃO volta para o UnitPool.

        Isso representa:

            UnitPool
                 ↓
              Shop
                 ↓
             compra
                 ↓
             jogador

        Depois que o jogador comprar, a cópia pertence a ele.

        Retorna:
            unidade
            ou None
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
        """
        Devolve todas as unidades atualmente presentes no shop
        para o UnitPool.

        Depois disso, os slots ficam vazios.
        """

        for slot in range(self.shop_size):

            unit = self.shop[slot]

            if unit is None:
                continue

            self._return_to_pool(unit)

            self.shop[slot] = None

    def _return_to_pool(self, unit):
        """
        Devolve uma unidade ao UnitPool.

        Contrato esperado:

            unit_pool.return_unit(unit)
        """

        if self.unit_pool is None:
            raise RuntimeError(
                "ShopManager precisa de um UnitPool."
            )

        self.unit_pool.return_unit(unit)

    # =============================================================
    # 🔄 REROLL
    # =============================================================

    def reroll(self, level):
        """
        Gera um novo shop.

        A cobrança de gold NÃO acontece aqui.

        O EconomyManager/MiniTFTEnv será responsável por verificar:

            gold >= REROLL_COST

        e descontar o custo.

        Aqui cuidamos apenas da troca das unidades.
        """

        return self.roll(
            level=level,
            force=True,
        )

    # =============================================================
    # 🔒 LOCK
    # =============================================================

    def set_locked(self, locked=True):
        """
        Ativa/desativa o lock do shop.
        """

        self.locked = bool(locked)

    def toggle_lock(self):
        """
        Alterna o estado de lock.
        """

        self.locked = not self.locked

        return self.locked

    def is_locked(self):
        """
        Retorna True caso o shop esteja travado.
        """

        return self.locked

    # =============================================================
    # 📊 UTILITÁRIOS
    # =============================================================

    def get_available_slots(self):
        """
        Retorna os slots que possuem unidades.
        """

        return [
            slot
            for slot, unit in enumerate(self.shop)
            if unit is not None
        ]

    def get_empty_slots(self):
        """
        Retorna os slots vazios.
        """

        return [
            slot
            for slot, unit in enumerate(self.shop)
            if unit is None
        ]

    def has_units(self):
        """
        Verifica se existe pelo menos uma unidade no shop.
        """

        return any(
            unit is not None
            for unit in self.shop
        )

    def get_unit_count(self):
        """
        Retorna quantas unidades existem atualmente no shop.
        """

        return sum(
            unit is not None
            for unit in self.shop
        )

    # =============================================================
    # 🐛 DEBUG
    # =============================================================

    def debug_print(self):
        """
        Mostra o shop atual.
        """

        print("\n--- SHOP ---")

        for slot, unit in enumerate(self.shop):

            if unit is None:
                print(f"[{slot}] Vazio")
                continue

            print(
                f"[{slot}] "
                f"{unit.get('name', '?')} "
                f"(cost={unit.get('cost', '?')})"
            )

        print(
            f"Locked: {self.locked}"
        )

        print("-------------")