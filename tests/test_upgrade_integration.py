# tests/test_upgrade_integration.py

import unittest
from copy import deepcopy
from uuid import uuid4

from env import MiniTFTEnv
from units.BoardManager import BoardManager
from units.BenchManager import BenchManager
from ai.ActionMaskManager import ActionType


# ============================================================
# 🧪 DEPENDÊNCIAS SIMPLES PARA ISOLAR O FLUXO DE COMPRA
# ============================================================

class FakeEconomyManager:
    def __init__(self, gold=100):
        self.gold = gold

    def can_spend(self, amount):
        return self.gold >= amount

    def spend_gold(self, amount):
        if not self.can_spend(amount):
            return False

        self.gold -= amount
        return True

    def add_gold(self, amount):
        self.gold += amount


class FakeShopManager:
    def __init__(self):
        self.shop = [None] * 5

    def set_available(self, unit_id, cost=1):
        self.shop[0] = {
            "id": unit_id,
            "name": f"Unit {unit_id}",
            "cost": cost,
        }

    def get_shop(self):
        return self.shop

    def take_unit(self, slot):
        if slot < 0 or slot >= len(self.shop):
            return None

        unit = self.shop[slot]
        self.shop[slot] = None
        return unit


class FakeUnitManager:
    def create_unit(self, champion):
        return {
            **deepcopy(champion),
            "uuid": str(uuid4()),
            "star": 1,
        }

    def create_upgraded_unit(self, unit, new_star):
        upgraded = deepcopy(unit)
        upgraded["uuid"] = str(uuid4())
        upgraded["star"] = new_star
        return upgraded


class FakeRewardManager:
    def calculate_action_reward(
        self,
        action_type,
        success,
        action_value=0.0,
    ):
        return action_value


# ============================================================
# ⭐ TESTES DE INTEGRAÇÃO DO UPGRADE
# ============================================================

class UpgradeIntegrationTests(unittest.TestCase):

    def setUp(self):
        # Criamos o ambiente sem carregar catálogo, lobby ou pool.
        # Os managers de tabuleiro e banco são os reais do projeto.
        self.env = MiniTFTEnv.__new__(MiniTFTEnv)

        self.env.board_manager = BoardManager(
            rows=4,
            cols=7,
        )

        self.env.bench_manager = BenchManager(
            max_bench=9,
        )

        self.env.economy_manager = FakeEconomyManager(
            gold=100,
        )

        self.env.shop_manager = FakeShopManager()
        self.env.unit_manager = FakeUnitManager()
        self.env.reward_manager = FakeRewardManager()

        self.env.shop_size = 5
        self.env.unit_pool = None

    # --------------------------------------------------------
    # 🛒 Executa uma compra pelo fluxo real do MiniTFTEnv
    # --------------------------------------------------------

    def buy_unit(self, unit_id, cost=1):
        self.env.shop_manager.set_available(
            unit_id,
            cost,
        )

        info = {
            "action_success": False,
        }

        reward = self.env._execute_buy(
            {
                "shop_slot": 0,
            },
            info,
        )

        return reward, info

    # --------------------------------------------------------
    # 🔎 Consulta unidades do jogador
    # --------------------------------------------------------

    def get_owned_units(self):
        return [
            unit
            for unit in self.env.board_manager.board
            if unit is not None
        ] + [
            unit
            for unit in self.env.bench_manager.bench
            if unit is not None
        ]

    # --------------------------------------------------------
    # ✅ 3 cópias de 1★ devem virar uma de 2★
    # --------------------------------------------------------

    def test_three_one_star_units_upgrade_to_two_stars(self):
        for _ in range(3):
            _, info = self.buy_unit(unit_id=10)

        units = self.get_owned_units()

        self.assertTrue(info["action_success"])
        self.assertTrue(info.get("upgrade", False))

        self.assertEqual(len(units), 1)
        self.assertEqual(units[0]["id"], 10)
        self.assertEqual(units[0]["star"], 2)

        # Três compras de custo 1.
        self.assertEqual(self.env.economy_manager.gold, 97)

        # O resultado deve ter uma identidade própria.
        self.assertTrue(units[0].get("uuid"))

    # --------------------------------------------------------
    # 🚫 IDs diferentes não podem ser combinados
    # --------------------------------------------------------

    def test_different_unit_ids_do_not_merge(self):
        self.buy_unit(unit_id=10)
        self.buy_unit(unit_id=10)
        _, info = self.buy_unit(unit_id=20)

        units = self.get_owned_units()

        self.assertFalse(info.get("upgrade", False))
        self.assertEqual(len(units), 3)
        self.assertTrue(
            all(unit["star"] == 1 for unit in units)
        )

        self.assertEqual(
            sum(unit["id"] == 10 for unit in units),
            2,
        )

        self.assertEqual(
            sum(unit["id"] == 20 for unit in units),
            1,
        )


    def test_three_two_star_units_upgrade_to_three_stars(self):
        # Arrange: cria três cópias de 2★ do mesmo campeão.
        for _ in range(3):
            unit = {
                "id": 10,
                "name": "Unit 10",
                "cost": 1,
                "star": 2,
                "uuid": str(uuid4()),
            }
            self.assertTrue(self.env.bench_manager.add_unit(unit))

        purchased_unit = self.env.bench_manager.get_unit(2)

        # Act: tenta realizar o upgrade.
        upgraded = self.env._try_upgrade_unit(purchased_unit)

        # Assert: deve sobrar somente uma unidade de 3★.
        units = self.get_owned_units()

        self.assertIsNotNone(upgraded)
        self.assertEqual(upgraded["id"], 10)
        self.assertEqual(upgraded["star"], 3)
        self.assertEqual(len(units), 1)
        self.assertEqual(units[0]["star"], 3)
        self.assertTrue(units[0]["uuid"])

    def test_two_two_star_units_do_not_upgrade(self):
        # Arrange: duas cópias não são suficientes.
        for _ in range(2):
            unit = {
                "id": 10,
                "name": "Unit 10",
                "cost": 1,
                "star": 2,
                "uuid": str(uuid4()),
            }
            self.assertTrue(self.env.bench_manager.add_unit(unit))

        purchased_unit = self.env.bench_manager.get_unit(1)

        # Act
        upgraded = self.env._try_upgrade_unit(purchased_unit)

        # Assert
        units = self.get_owned_units()

        self.assertIsNone(upgraded)
        self.assertEqual(len(units), 2)
        self.assertTrue(all(unit["star"] == 2 for unit in units))


    def test_upgrade_to_three_stars_across_bench_and_board(self):
        # Arrange: cria três unidades de 2★ do mesmo campeão.
        units_created = []

        for _ in range(3):
            unit = {
                "id": 10,
                "name": "Unit 10",
                "cost": 1,
                "star": 2,
                "uuid": str(uuid4()),
            }

            units_created.append(unit)

        # Duas unidades no banco.
        self.assertTrue(
            self.env.bench_manager.add_unit(units_created[0])
        )
        self.assertTrue(
            self.env.bench_manager.add_unit(units_created[1])
        )

        # Uma unidade no tabuleiro.
        board_unit = units_created[2]
        # Coloca a terceira unidade na posição 0 do tabuleiro.
        placed = self.env.board_manager.add_unit(
            board_unit, 0
        )
        self.assertTrue(placed)

        # Act: tenta evoluir a unidade do banco.
        purchased_unit = self.env.bench_manager.get_unit(1)
        upgraded = self.env._try_upgrade_unit(purchased_unit)

        # Assert: deve existir apenas uma unidade de 3★.
        owned_units = self.get_owned_units()

        self.assertIsNotNone(upgraded)
        self.assertEqual(upgraded["star"], 3)
        self.assertEqual(upgraded["id"], 10)
        self.assertEqual(len(owned_units), 1)
        self.assertEqual(owned_units[0]["star"], 3)


    def test_chained_upgrade_from_one_star_to_three_stars(self):
        # Arrange: cria 3 unidades de 1★ e 2 unidades de 2★.
        for star, quantity in [(1, 3), (2, 2)]:
            for _ in range(quantity):
                unit = {
                    "id": 10,
                    "name": "Unit 10",
                    "cost": 1,
                    "star": star,
                    "uuid": str(uuid4()),
                }

                added = self.env.bench_manager.add_unit(unit)
                self.assertTrue(added)

        # Act: tenta evoluir uma das unidades de 1★.
        unit_to_upgrade = self.env.bench_manager.get_unit(2)
        upgraded = self.env._try_upgrade_unit(unit_to_upgrade)

        # Assert: esperamos uma única unidade de 3★.
        owned_units = self.get_owned_units()

        self.assertIsNotNone(upgraded)
        self.assertEqual(upgraded["id"], 10)
        self.assertEqual(upgraded["star"], 3)
        self.assertEqual(len(owned_units), 1)
        self.assertEqual(owned_units[0]["star"], 3)


if __name__ == "__main__":
    unittest.main()