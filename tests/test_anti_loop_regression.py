
import pytest

from ai.AntiLoopManager import AntiLoopManager


@pytest.fixture
def anti_loop():
    return AntiLoopManager()


@pytest.fixture
def unit_a():
    return {"uuid": "unit-a", "id": "Nasus", "star": 1}


@pytest.fixture
def unit_b():
    return {"uuid": "unit-b", "id": "Teemo", "star": 1}


def test_blocks_reverse_move_for_same_unit(anti_loop, unit_a):
    # A unidade foi movida da posição 4 para a 12.
    anti_loop.register_move(
        "MOVE_BOARD", 4, 12, unit_a
    )

    # Tentar voltar para a posição anterior deve ser bloqueado.
    assert anti_loop.should_block_move(
        "MOVE_BOARD", 12, 4, unit_a
    )


def test_blocks_repeated_move(anti_loop, unit_a):
    anti_loop.block_move(
        "MOVE_BOARD", 4, 12, unit_a
    )

    assert anti_loop.should_block_move(
        "MOVE_BOARD", 4, 12, unit_a
    )


def test_detects_bench_board_oscillation(anti_loop, unit_a):
    anti_loop.register_move(
        "MOVE_BENCH_TO_BOARD", 2, 12, unit_a
    )
    anti_loop.register_move(
        "MOVE_BOARD_TO_BENCH", 12, 2, unit_a
    )

    # Uma nova tentativa de mover a unidade deve ser bloqueada
    # enquanto o histórico indicar essa alternância.
    assert anti_loop.should_block_move(
        "MOVE_BENCH_TO_BOARD", 2, 12, unit_a
    )


def test_does_not_block_independent_unit_move(
    anti_loop, unit_a, unit_b
):
    anti_loop.register_move(
        "MOVE_BOARD", 4, 12, unit_a
    )

    # Outro campeão, com outra origem e destino, não deve ser
    # bloqueado apenas porque a primeira unidade se moveu.
    assert not anti_loop.should_block_move(
        "MOVE_BOARD", 5, 13, unit_b
    )


def test_reset_clears_loop_history(anti_loop, unit_a):
    anti_loop.register_move(
        "MOVE_BOARD", 4, 12, unit_a
    )

    anti_loop.reset()

    assert not anti_loop.should_block_move(
        "MOVE_BOARD", 12, 4, unit_a
    )
    assert anti_loop.get_state()["move_history_size"] == 0
