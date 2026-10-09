
"""Testes de regressão para o contrato da ação MOVE_BOARD."""

import unittest

from env import MiniTFTEnv


class MoveBoardActionContractTests(unittest.TestCase):

    def setUp(self):
        # O normalizador não precisa inicializar todo o ambiente.
        self.env = MiniTFTEnv.__new__(MiniTFTEnv)

    def test_accepts_trainer_policy_field(self):
        action = self.env._sanitize_action({
            "type": 4,
            "board_source": 11,
            "board_move_target": 23,
        })

        self.assertEqual(action["board_source"], 11)
        self.assertEqual(
            action["conditioned_board_target"], 23
        )

    def test_preserves_legacy_conditioned_target(self):
        action = self.env._sanitize_action({
            "type": 4,
            "conditioned_board_target": 19,
        })

        self.assertEqual(
            action["conditioned_board_target"], 19
        )

    def test_preserves_legacy_board_target(self):
        action = self.env._sanitize_action({
            "type": 4,
            "board_target": 17,
        })

        self.assertEqual(
            action["conditioned_board_target"], 17
        )

    def test_sixth_dimension_is_target(self):
        action = self.env._sanitize_action(
            [4, 0, 0, 0, 11, 25]
        )

        self.assertEqual(action["board_source"], 11)
        self.assertEqual(
            action["conditioned_board_target"], 25
        )


if __name__ == "__main__":
    unittest.main()
