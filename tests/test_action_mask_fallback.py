
import numpy as np
import pytest
import torch

from trainer import Trainer
from ai.ActionMaskManager import ActionType


def create_masks():
    """Cria máscaras para os 8 jogadores de uma lobby."""
    players = []

    for _ in range(Trainer.PLAYERS_PER_LOBBY):
        players.append({
            "type_mask": np.ones(7, dtype=np.float32),
            "shop_mask": np.ones(5, dtype=np.float32),
            "bench_source_mask": np.ones(9, dtype=np.float32),
            "board_target_mask": np.ones(28, dtype=np.float32),
            "board_source_mask": np.ones(28, dtype=np.float32),
            "board_move_target_masks": np.ones(
                (28, 28), dtype=np.float32
            ),
            "bench_move_source_mask": np.ones(
                9, dtype=np.float32
            ),
            "bench_to_board_target_masks": np.ones(
                (9, 28), dtype=np.float32
            ),
        })

    return [players]


@pytest.fixture
def trainer():
    instance = Trainer.__new__(Trainer)
    instance.num_envs = 1
    instance.num_agents = Trainer.PLAYERS_PER_LOBBY
    instance.device = torch.device("cpu")
    return instance


def test_empty_type_mask_falls_back_to_pass(trainer):
    gym_masks = create_masks()
    gym_masks[0][0]["type_mask"] = np.zeros(7)

    masks = trainer._flatten_masks(gym_masks)

    assert masks["type_mask"][0].sum().item() == 1
    assert masks["type_mask"][0, ActionType.PASS].item()


def test_dead_player_has_only_pass_as_valid_type(trainer):
    gym_masks = create_masks()
    gym_masks[0][3]["type_mask"] = np.zeros(7)

    masks = trainer._flatten_masks(gym_masks)

    expected = torch.zeros(7, dtype=torch.bool)
    expected[ActionType.PASS] = True

    assert torch.equal(masks["type_mask"][3], expected)


def test_empty_type_mask_gets_valid_auxiliary_fallbacks(trainer):
    gym_masks = create_masks()
    gym_masks[0][0]["type_mask"] = np.zeros(7)

    masks = trainer._flatten_masks(gym_masks)

    # As cabeças categóricas precisam ter pelo menos
    # uma opção válida para evitar distribuições inválidas.
    for key in (
        "shop_mask",
        "bench_source_mask",
        "board_target_mask",
        "board_source_mask",
    ):
        assert masks[key][0].any(), f"{key} ficou vazia"


def test_all_zero_type_masks_are_repaired_for_every_player(trainer):
    gym_masks = create_masks()

    for player in gym_masks[0]:
        player["type_mask"] = np.zeros(7)

    masks = trainer._flatten_masks(gym_masks)

    expected = torch.zeros(7, dtype=torch.bool)
    expected[ActionType.PASS] = True

    for agent_idx in range(trainer.num_agents):
        assert torch.equal(masks["type_mask"][agent_idx], expected)


def test_all_auxiliary_masks_have_expected_shapes(trainer):
    masks = trainer._flatten_masks(create_masks())

    for key, shape in Trainer.MASK_SHAPES.items():
        assert tuple(masks[key].shape) == (
            trainer.num_agents,
            *shape,
        )
        assert masks[key].dtype == torch.bool
