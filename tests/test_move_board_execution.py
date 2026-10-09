"""Testes de regressão para a execução real de MOVE_BOARD."""

import unittest
from unittest.mock import Mock

from env import MiniTFTEnv
from units.BoardManager import BoardManager
from ai.ActionMaskManager import ActionType


class MoveBoardExecutionTests(unittest.TestCase):

    def setUp(self):
        # Criamos apenas os componentes necessários para testar
        # a movimentação, sem inicializar toda a partida.
        self.env = MiniTFTEnv.__new__(MiniTFTEnv)

        self.env.board_manager = BoardManager(rows=4, cols=7)

        self.env.anti_loop_manager = Mock()
        self.env.anti_loop_manager.should_block_move.return_value = False

        self.env.reward_manager = Mock()
        self.env.reward_manager.calculate_action_reward.return_value = 0.02

        self.info = {"action_success": False}

    def execute_move(self, source, target):
        return self.env._execute_move_board(
            {
                "board_source": source,
                "conditioned_board_target": target,
            },
            self.info,
        )

    def test_moves_unit_to_empty_position(self):
        unit = {"id": "Nasus", "star": 1}
        self.env.board_manager.add_unit(unit, 3)

        reward = self.execute_move(3, 10)

        self.assertIsNone(self.env.board_manager.get_unit(3))
        self.assertIs(self.env.board_manager.get_unit(10), unit)
        self.assertTrue(self.info["action_success"])
        self.assertEqual(reward, 0.02)

    def test_swaps_two_occupied_positions(self):
        unit_a = {"id": "Nasus", "star": 1}
        unit_b = {"id": "Pyke", "star": 1}

        self.env.board_manager.add_unit(unit_a, 3)
        self.env.board_manager.add_unit(unit_b, 10)

        reward = self.execute_move(3, 10)

        self.assertIs(self.env.board_manager.get_unit(3), unit_b)
        self.assertIs(self.env.board_manager.get_unit(10), unit_a)
        self.assertTrue(self.info["action_success"])
        self.assertEqual(reward, 0.02)

    def test_rejects_same_source_and_target(self):
        unit = {"id": "Nasus", "star": 1}
        self.env.board_manager.add_unit(unit, 3)

        reward = self.execute_move(3, 3)

        self.assertIs(self.env.board_manager.get_unit(3), unit)
        self.assertFalse(self.info["action_success"])
        self.assertEqual(reward, -0.10)

    def test_rejects_out_of_range_positions(self):
        unit = {"id": "Nasus", "star": 1}
        self.env.board_manager.add_unit(unit, 3)

        for source, target in [(-1, 10), (28, 10), (3, -1), (3, 28)]:
            with self.subTest(source=source, target=target):
                self.info = {"action_success": False}

                reward = self.execute_move(source, target)

                self.assertIs(self.env.board_manager.get_unit(3), unit)
                self.assertFalse(self.info["action_success"])
                self.assertEqual(reward, -0.10)

    def test_rejects_empty_source(self):
        reward = self.execute_move(3, 10)

        self.assertIsNone(self.env.board_manager.get_unit(10))
        self.assertFalse(self.info["action_success"])
        self.assertEqual(reward, -0.10)

    def test_rejects_move_blocked_by_anti_loop(self):
        unit = {"id": "Nasus", "star": 1}
        self.env.board_manager.add_unit(unit, 3)
        self.env.anti_loop_manager.should_block_move.return_value = True

        reward = self.execute_move(3, 10)

        self.assertIs(self.env.board_manager.get_unit(3), unit)
        self.assertIsNone(self.env.board_manager.get_unit(10))
        self.assertFalse(self.info["action_success"])
        self.assertEqual(reward, -0.10)

    def test_registers_successful_move_with_anti_loop_manager(self):
        unit = {"id": "Nasus", "star": 1}
        self.env.board_manager.add_unit(unit, 3)

        self.execute_move(3, 10)

        self.env.anti_loop_manager.register_move.assert_called_once_with(
            move_type="board_move",
            source=3,
            target=10,
            unit=unit,
        )


if __name__ == "__main__":
    unittest.main()
