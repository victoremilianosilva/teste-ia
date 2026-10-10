
import torch

from policy import TFTPolicy
from trainer import Trainer


def create_test_batch():
    """Cria um lote que exercita diferentes caminhos da política."""
    batch_size = 5
    obs_dim = 162

    obs = torch.randn(batch_size, obs_dim)

    # BUY, MOVE_BENCH, MOVE_BOARD, SELL e PASS.
    action_types = [0, 3, 4, 5, 6]

    masks = {
        "type_mask": torch.zeros(batch_size, 7, dtype=torch.bool),
        "shop_mask": torch.zeros(batch_size, 5, dtype=torch.bool),
        "bench_source_mask": torch.zeros(
            batch_size, 9, dtype=torch.bool
        ),
        "board_target_mask": torch.zeros(
            batch_size, 28, dtype=torch.bool
        ),
        "board_source_mask": torch.zeros(
            batch_size, 28, dtype=torch.bool
        ),
        "board_move_target_masks": torch.zeros(
            batch_size, 28, 28, dtype=torch.bool
        ),
        "bench_move_source_mask": torch.zeros(
            batch_size, 9, dtype=torch.bool
        ),
        "bench_to_board_target_masks": torch.zeros(
            batch_size, 9, 28, dtype=torch.bool
        ),
    }

    for i, action_type in enumerate(action_types):
        masks["type_mask"][i, action_type] = True

    # BUY: apenas o slot 2 é permitido.
    masks["shop_mask"][:, 2] = True

    # SELL: apenas o slot 7 do banco é permitido.
    masks["bench_source_mask"][:, 7] = True

    # MOVE_BENCH: origem 4 e destino 17.
    masks["bench_move_source_mask"][:, 4] = True
    masks["bench_to_board_target_masks"][:, 4, 17] = True

    # MOVE_BOARD: origem 9 e destino condicionado 18.
    masks["board_source_mask"][:, 9] = True
    masks["board_move_target_masks"][:, 9, 18] = True

    # Máscara genérica de destino, para compatibilidade.
    masks["board_target_mask"][:, 17] = True

    return obs, masks, action_types


def test_collection_and_evaluation_logprobs_match():
    torch.manual_seed(42)

    obs, masks, expected_types = create_test_batch()

    policy = TFTPolicy(
        obs_dim=obs.shape[-1],
        action_dims=Trainer.ACTION_DIMS,
        hidden_size=32,
    )

    policy.eval()

    with torch.no_grad():
        actions, collected_logprobs, _, values = (
            policy.get_action_and_value(
                obs,
                masks=masks,
                deterministic=True,
            )
        )

        evaluated_logprobs, entropy, evaluated_values = (
            policy.evaluate_actions(
                obs,
                actions,
                masks=masks,
            )
        )

    # Todos os caminhos de ação planejados foram exercitados.
    assert actions[:, 0].tolist() == expected_types

    # Coleta e avaliação precisam calcular a mesma probabilidade.
    assert torch.allclose(
        collected_logprobs,
        evaluated_logprobs,
        atol=1e-5,
        rtol=1e-5,
    )

    assert torch.allclose(values, evaluated_values, atol=1e-5)

    assert torch.isfinite(collected_logprobs).all()
    assert torch.isfinite(evaluated_logprobs).all()
    assert torch.isfinite(entropy).all()
    assert torch.isfinite(values).all()


def test_sampled_actions_respect_masks():
    torch.manual_seed(123)

    obs, masks, expected_types = create_test_batch()

    policy = TFTPolicy(
        obs_dim=obs.shape[-1],
        action_dims=Trainer.ACTION_DIMS,
        hidden_size=32,
    )

    policy.eval()

    with torch.no_grad():
        actions, logprobs, entropy, values = policy.get_action_and_value(
            obs,
            masks=masks,
            deterministic=False,
        )

    assert actions[:, 0].tolist() == expected_types

    # BUY
    assert actions[0, 1].item() == 2

    # MOVE_BENCH: origem e destino condicionais
    assert actions[1, 2].item() == 4
    assert actions[1, 3].item() == 17

    # MOVE_BOARD: origem e destino condicionais
    assert actions[2, 4].item() == 9
    assert actions[2, 5].item() == 18

    # SELL
    assert actions[3, 2].item() == 7

    assert torch.isfinite(logprobs).all()
    assert torch.isfinite(entropy).all()
    assert torch.isfinite(values).all()
