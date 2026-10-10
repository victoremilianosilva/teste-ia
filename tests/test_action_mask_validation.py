
import numpy as np
import pytest
import torch

from trainer import Trainer


@pytest.fixture
def trainer():
    """Cria um Trainer sem inicializar ambientes ou o modelo."""
    instance = Trainer.__new__(Trainer)
    instance.num_envs = 1
    instance.num_agents = Trainer.PLAYERS_PER_LOBBY
    instance.device = torch.device("cpu")
    return instance


def create_valid_masks():
    """Cria máscaras válidas para os 8 jogadores de uma lobby."""
    player_masks = []

    for _ in range(Trainer.PLAYERS_PER_LOBBY):
        player_masks.append({
            "type_mask": np.array(
                [1, 0, 0, 0, 0, 0, 1], dtype=np.float32
            ),
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

    return [player_masks]


def test_valid_masks_are_converted_to_bool_tensors(trainer):
    masks = trainer._flatten_masks(create_valid_masks())

    assert set(masks.keys()) == set(Trainer.MASK_SHAPES.keys())

    for key, shape in Trainer.MASK_SHAPES.items():
        assert isinstance(masks[key], torch.Tensor)
        assert masks[key].dtype == torch.bool
        assert tuple(masks[key].shape) == (
            Trainer.PLAYERS_PER_LOBBY,
            *shape,
        )


def test_rejects_wrong_mask_dimensions(trainer):
    gym_masks = create_valid_masks()
    gym_masks[0][0]["shop_mask"] = np.ones(4)

    with pytest.raises(ValueError, match="shop_mask"):
        trainer._flatten_masks(gym_masks)


def test_rejects_string_mask_type(trainer):
    gym_masks = create_valid_masks()
    gym_masks[0][0]["shop_mask"] = np.array(["x"] * 5)

    with pytest.raises(TypeError):
        trainer._flatten_masks(gym_masks)


@pytest.mark.parametrize("invalid_value", [2, -1, 0.5])
def test_rejects_values_other_than_zero_or_one(
    trainer, invalid_value
):
    gym_masks = create_valid_masks()
    gym_masks[0][0]["shop_mask"] = np.array(
        [1, 0, invalid_value, 1, 0],
        dtype=np.float32,
    )

    with pytest.raises(ValueError):
        trainer._flatten_masks(gym_masks)


@pytest.mark.parametrize("invalid_value", [np.nan, np.inf, -np.inf])
def test_rejects_nan_and_infinity(trainer, invalid_value):
    gym_masks = create_valid_masks()
    gym_masks[0][0]["shop_mask"] = np.array(
        [1, 0, invalid_value, 1, 0],
        dtype=np.float32,
    )

    with pytest.raises(ValueError):
        trainer._flatten_masks(gym_masks)


def test_rejects_missing_required_mask(trainer):
    gym_masks = create_valid_masks()
    del gym_masks[0][0]["shop_mask"]

    with pytest.raises(KeyError):
        trainer._flatten_masks(gym_masks)


def test_rejects_wrong_number_of_lobbies(trainer):
    gym_masks = create_valid_masks()
    gym_masks.append(create_valid_masks()[0])

    with pytest.raises(ValueError, match="Número de máscaras"):
        trainer._flatten_masks(gym_masks)


def test_rejects_wrong_number_of_players(trainer):
    gym_masks = create_valid_masks()
    gym_masks[0].pop()

    with pytest.raises(ValueError, match="jogadores"):
        trainer._flatten_masks(gym_masks)
