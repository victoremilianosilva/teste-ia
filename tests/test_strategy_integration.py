import unittest

from strategy.StrategyManager import (
    Strategy,
    StrategyManager,
)


class StrategyManagerIntegrationTests(unittest.TestCase):

    def setUp(self):
        self.manager = StrategyManager()

    def decide(self, **overrides):
        params = {
            "hp": 100,
            "gold": 10,
            "level": 4,
            "xp": 0,
            "board_power": 30,
            "bench_strength": 0,
            "win_streak": 0,
            "loss_streak": 0,
            "round_number": 1,
            "active_traits": 0,
            "comp_focus": None,
            "comp_direction": None,
        }
        params.update(overrides)

        return self.manager.decide_strategy(**params)

    def test_critical_hp_selects_all_in(self):
        result = self.decide(hp=10)

        self.assertEqual(
            result["strategy"],
            Strategy.ALL_IN,
        )

    def test_low_hp_selects_stabilize(self):
        result = self.decide(hp=25)

        self.assertEqual(
            result["strategy"],
            Strategy.STABILIZE,
        )

    def test_changed_only_when_strategy_changes(self):
        first = self.decide(hp=10)
        second = self.decide(hp=10)

        self.assertTrue(first["changed"])
        self.assertFalse(second["changed"])

    def test_strategy_age_increases_without_change(self):
        self.decide(hp=10)
        self.decide(hp=10)

        self.assertEqual(
            self.manager.strategy_age,
            1,
        )


if __name__ == "__main__":
    unittest.main()
