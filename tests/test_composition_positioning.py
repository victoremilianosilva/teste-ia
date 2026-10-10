
"""Testes de composição e posicionamento."""

from collections import Counter

from strategy.CompositionManager import CompositionManager
from strategy.PositioningManager import PositioningManager


class FakeUnitManager:
    """Implementação mínima para testar o CompositionManager."""

    @staticmethod
    def is_valid_unit(unit):
        return isinstance(unit, dict) and unit.get("id") is not None

    def count_copies(self, units):
        counts = Counter()

        for unit in units:
            if not self.is_valid_unit(unit):
                continue

            # 1 estrela = 1 cópia; 2 estrelas = 3; 3 estrelas = 9.
            copies_by_star = {1: 1, 2: 3, 3: 9}
            counts[unit["id"]] += copies_by_star.get(
                unit.get("star", 1), 1
            )

        return dict(counts)


def make_unit(unit_id, traits, star=1, role="FIGHTER"):
    return {
        "id": unit_id,
        "traits": traits,
        "star": star,
        "cost": 2,
        "role": role,
    }


def test_bench_units_count_as_owned_copies():
    manager = CompositionManager(FakeUnitManager())

    board = [make_unit(1, ["Mage"])]
    bench = [
        make_unit(1, ["Mage"]),
        make_unit(2, ["Tank"], star=2),
    ]

    counts = manager.rebuild_unit_counts(board, bench)

    assert counts[1] == 2
    assert counts[2] == 3

def test_positioning_score_is_finite():
    manager = PositioningManager(rows=4, cols=7)

    board = [None] * 28
    board[0] = make_unit(1, ["Tank"], role="TANK")
    board[1] = make_unit(2, ["Carry"], role="CARRY")

    score = manager.evaluate_board_positioning(board)

    assert isinstance(score, (int, float))
    assert score == score  # Não é NaN.
    assert abs(score) != float("inf")


def test_find_best_position_does_not_change_board():
    manager = PositioningManager(rows=4, cols=7)

    board = [None] * 28
    board[0] = make_unit(1, ["Tank"], role="TANK")
    carry = make_unit(2, ["Carry"], role="CARRY")
    original_board = list(board)

    position, score = manager.find_best_position(
        board,
        carry,
        candidate_positions=[1, 2, 3],
    )

    assert position in [1, 2, 3]
    assert isinstance(score, (int, float))
    assert board == original_board
