
import numpy as np
import pytest

from ai.ActionMaskManager import ActionMaskManager


class FakeBoardManager:
    def __init__(self, board=None):
        self.board = board if board is not None else [None] * 28

    def get_empty_positions(self):
        return [
            i for i, unit in enumerate(self.board)
            if unit is None
        ]

    def is_valid_position(self, position):
        return isinstance(position, int) and 0 <= position < 28


class FakeBenchManager:
    def __init__(self, bench=None):
        self.bench = bench if bench is not None else [None] * 9

    def has_free_slot(self):
        return any(unit is None for unit in self.bench)


class FakeAntiLoopManager:
    def __init__(self, blocked=None):
        self.blocked = blocked or set()

    def should_block_move(
        self, move_type, source, target, unit
    ):
        return (move_type, source, target) in self.blocked


@pytest.fixture
def setup_manager():
    board = FakeBoardManager()
    bench = FakeBenchManager()
    anti_loop = FakeAntiLoopManager()

    manager = ActionMaskManager(
        board_manager=board,
        bench_manager=bench,
        shop_manager=None,
        economy_manager=None,
        composition_manager=None,
        positioning_manager=None,
        anti_loop_manager=anti_loop,
        unit_manager=None,
    )

    return manager, board, bench, anti_loop


def test_board_targets_exclude_the_source(setup_manager):
    manager, board, _, _ = setup_manager
    board.board[5] = {"name": "Unit A"}

    mask = manager.get_board_move_target_mask(5)

    assert mask.shape == (28,)
    assert mask[5] == 0
    assert mask[6] == 1
    assert mask.dtype == np.float32


def test_empty_board_source_has_no_real_destinations(
    setup_manager,
):
    manager, _, _, _ = setup_manager

    mask = manager.get_board_move_target_mask(5)

    # Índice 0 é apenas o fallback técnico.
    assert mask[0] == 1
    assert np.count_nonzero(mask) == 1


def test_invalid_board_source_uses_fallback(setup_manager):
    manager, _, _, _ = setup_manager

    mask = manager.get_board_move_target_mask(28)

    assert mask[0] == 1
    assert np.count_nonzero(mask) == 1


def test_bench_targets_only_include_empty_positions(
    setup_manager,
):
    manager, board, bench, _ = setup_manager

    bench.bench[2] = {"name": "Unit A"}
    board.board[4] = {"name": "Unit B"}

    mask = manager.get_bench_to_board_target_mask(2)

    assert mask.shape == (28,)
    assert mask[4] == 0
    assert mask[0] == 1
    assert mask[1] == 1
    assert mask.dtype == np.float32


def test_empty_bench_slot_has_no_real_destinations(
    setup_manager,
):
    manager, _, _, _ = setup_manager

    mask = manager.get_bench_to_board_target_mask(3)

    assert mask[0] == 1
    assert np.count_nonzero(mask) == 1


def test_bench_move_respects_anti_loop(setup_manager):
    manager, board, bench, anti_loop = setup_manager

    bench.bench[2] = {"name": "Unit A"}
    anti_loop.blocked.add(("bench_to_board", 2, 0))

    mask = manager.get_bench_to_board_target_mask(2)

    assert mask[0] == 0
    assert mask[1] == 1


def test_board_move_respects_anti_loop(setup_manager):
    manager, board, _, anti_loop = setup_manager

    board.board[5] = {"name": "Unit A"}
    anti_loop.blocked.add(("board_move", 5, 6))

    mask = manager.get_board_move_target_mask(5)

    assert mask[5] == 0
    assert mask[6] == 0
    assert mask[7] == 1


def test_board_swap_respects_anti_loop(setup_manager):
    manager, board, _, anti_loop = setup_manager

    board.board[5] = {"name": "Unit A"}
    board.board[6] = {"name": "Unit B"}
    anti_loop.blocked.add(("board_swap", 5, 6))

    mask = manager.get_board_move_target_mask(5)

    assert mask[6] == 0
    assert mask[7] == 1
