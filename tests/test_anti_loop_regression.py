import pytest

from ai.AntiLoopManager import AntiLoopManager


@pytest.fixture
def manager():
    return AntiLoopManager()


@pytest.fixture
def unit():
    return {
        "uuid": "unit-123",
        "id": "nasus",
        "star": 1,
    }


def test_blocks_reverse_board_move(manager, unit):
    """
    Uma unidade não deve poder voltar imediatamente
    à posição de origem após um movimento no tabuleiro.
    """
    manager.register_move(
        move_type="board_move",
        source=10,
        target=11,
        unit=unit,
    )

    assert manager.should_block_move(
        move_type="board_move",
        source=11,
        target=10,
        unit=unit,
    ) is True


def test_detects_bench_board_loop_with_environment_names(
    manager,
    unit,
):
    """
    A detecção deve reconhecer os nomes usados pelo env.py
    e identificar uma alternância entre banco e tabuleiro.
    """
    manager.register_move(
        move_type="bench_to_board",
        source=2,
        target=17,
        unit=unit,
    )

    manager.register_move(
        move_type="board_to_bench",
        source=17,
        target=2,
        unit=unit,
    )

    assert manager.should_block_move(
        move_type="bench_to_board",
        source=2,
        target=17,
        unit=unit,
    ) is True