import unittest

from config.GameConfig import GameConfig
from shop.ShopManager import ShopManager


class ShopManagerOddsTests(unittest.TestCase):

    def test_uses_custom_shop_odds(self):
        custom_odds = {
            2: [0.80, 0.20, 0.00, 0.00, 0.00],
            3: [0.50, 0.30, 0.20, 0.00, 0.00],
        }

        manager = ShopManager(
            unit_pool=None,
            shop_odds=custom_odds,
        )

        self.assertEqual(
            manager._get_shop_odds(2),
            custom_odds[2],
        )

    def test_uses_custom_odds_for_requested_level(self):
        custom_odds = {
            2: [1.00, 0.00, 0.00, 0.00, 0.00],
            4: [0.20, 0.30, 0.30, 0.20, 0.00],
        }

        manager = ShopManager(
            unit_pool=None,
            shop_odds=custom_odds,
        )

        self.assertEqual(
            manager._get_shop_odds(4),
            custom_odds[4],
        )

    def test_unknown_level_uses_highest_configured_level(self):
        custom_odds = {
            2: [1.00, 0.00, 0.00, 0.00, 0.00],
            4: [0.20, 0.30, 0.30, 0.20, 0.00],
        }

        manager = ShopManager(
            unit_pool=None,
            shop_odds=custom_odds,
        )

        self.assertEqual(
            manager._get_shop_odds(3),
            custom_odds[4],
        )

    def test_empty_custom_config_uses_game_config(self):
        manager = ShopManager(
            unit_pool=None,
            shop_odds={},
        )

        self.assertEqual(
            manager._get_shop_odds(4),
            GameConfig.get_shop_odds(4),
        )


if __name__ == "__main__":
    unittest.main()
