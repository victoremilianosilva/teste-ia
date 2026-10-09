import torch
import torch.nn.functional as F
from torch.utils.tensorboard import SummaryWriter


class PPOTrainer:

    def __init__(
        self,
        policy,
        optimizer,
        writer,
        clip_coef=0.2,
        ent_coef=0.02,
        vf_coef=0.5,
        max_grad_norm=0.5,
        target_kl=0.02
    ):
        """
        PPO Trainer compatível com Self-Play.

        ================================================================
        SELF-PLAY
        ================================================================

        A policy é compartilhada entre todos os jogadores.

            Player 0 ─┐
            Player 1  │
            Player 2  │
            ...       ├──> mesma TFTPolicy
            Player 7  │
                      │
                      └──> PPOTrainer

        O RolloutBuffer transforma:

            lobbies × 8 jogadores

        em um batch de agentes.

        Portanto, este trainer não precisa conhecer diretamente
        o conceito de lobby.
        """

        self.policy = policy
        self.optimizer = optimizer

        # ============================================================
        # PPO CONFIG
        # ============================================================

        self.clip_coef = clip_coef
        self.ent_coef = ent_coef
        self.vf_coef = vf_coef

        self.max_grad_norm = max_grad_norm
        self.target_kl = target_kl

        # ============================================================
        # TENSORBOARD
        # ============================================================

        self.writer = writer
        self.update_step = 0

    # =================================================================
    # PPO LOSS
    # =================================================================

    def compute_loss(
        self,
        obs,
        actions,
        old_logprobs,
        old_values,
        advantages,
        returns,
        masks,
    ):
        """
        Calcula a loss PPO de um mini-batch.

        O batch pode conter experiências de vários jogadores,
        vários lobbies e vários rounds.

        A policy continua sendo compartilhada.
        """

        # ============================================================
        # POLICY EVALUATION
        # ============================================================

        (
            new_logprob,
            entropy,
            new_values
        ) = self.policy.evaluate_actions(
            obs,
            actions,
            masks=masks
        )

        # ============================================================
        # GARANTIR SHAPES
        # ============================================================

        new_values = new_values.reshape(-1)
        old_values = old_values.reshape(-1)

        old_logprobs = old_logprobs.reshape(-1)

        advantages = advantages.reshape(-1)
        returns = returns.reshape(-1)

        new_logprob = new_logprob.reshape(-1)
        entropy = entropy.reshape(-1)

        # ============================================================
        # PPO RATIO
        # ============================================================

        logratio = (
            new_logprob
            - old_logprobs
        )

        ratio = logratio.exp()

        # ============================================================
        # POLICY LOSS
        # ============================================================

        pg_loss1 = (
            -advantages * ratio
        )

        pg_loss2 = (
            -advantages
            * torch.clamp(
                ratio,
                1.0 - self.clip_coef,
                1.0 + self.clip_coef
            )
        )

        pg_loss = torch.max(
            pg_loss1,
            pg_loss2
        ).mean()

        # ============================================================
        # VALUE CLIPPING
        # ============================================================

        value_pred_clipped = (
            old_values
            + torch.clamp(
                new_values - old_values,
                -self.clip_coef,
                self.clip_coef
            )
        )

        value_loss_unclipped = (
            returns - new_values
        ).pow(2)

        value_loss_clipped = (
            returns - value_pred_clipped
        ).pow(2)

        v_loss = (
            0.5
            * torch.max(
                value_loss_unclipped,
                value_loss_clipped
            ).mean()
        )

        # ============================================================
        # ENTROPY
        # ============================================================

        entropy_loss = entropy.mean()

        # ============================================================
        # TOTAL LOSS
        # ============================================================

        loss = (
            pg_loss
            - self.ent_coef * entropy_loss
            + self.vf_coef * v_loss
        )

        # ============================================================
        # METRICS
        # ============================================================

        with torch.no_grad():

            # --------------------------------------------------------
            # Approximate KL
            # --------------------------------------------------------

            approx_kl = (
                old_logprobs
                - new_logprob
            ).mean()

            # --------------------------------------------------------
            # Clip fraction
            # --------------------------------------------------------

            clip_fraction = (
                (
                    torch.abs(
                        ratio - 1.0
                    ) > self.clip_coef
                )
                .float()
                .mean()
            )

            # --------------------------------------------------------
            # Ratio médio
            # --------------------------------------------------------

            batch_ratio = ratio.mean()

        return (
            loss,
            pg_loss.detach(),
            v_loss.detach(),
            entropy_loss.detach(),
            approx_kl.detach(),
            clip_fraction.detach(),
            batch_ratio.detach()
        )

    # =================================================================
    # UPDATE
    # =================================================================

    def update(
        self,
        rollout,
        batch_size=256,
        epochs=4
    ):
        """
        Executa uma atualização PPO completa.

        ================================================================
        SELF-PLAY
        ================================================================

        O rollout pode conter:

            8 jogadores
            16 jogadores
            32 jogadores
            ...

        dependendo de quantos lobbies o Trainer estiver executando.

        O PPO não precisa saber a origem das experiências.
        """

        # ============================================================
        # VALIDAR ROLLOUT
        # ============================================================

        if rollout.ptr <= 0:

            print(
                "⚠️ PPO Update ignorado: rollout vazio."
            )

            return

        # ============================================================
        # NORMALIZAÇÃO DAS ADVANTAGES
        # ============================================================

        rollout.normalize_advantages()

        # ============================================================
        # MÉTRICAS
        # ============================================================

        mean_loss = 0.0
        mean_pg = 0.0
        mean_v = 0.0
        mean_entropy = 0.0
        mean_kl = 0.0
        mean_clipfrac = 0.0
        mean_ratio = 0.0

        total_batches = 0

        stop_early = False

        # ============================================================
        # PPO EPOCHS
        # ============================================================

        for epoch in range(epochs):

            if stop_early:
                break

            for batch in rollout.get_batches(
                batch_size=batch_size,
                normalize_advantages=False
            ):

                # ====================================================
                # COMPUTE LOSS
                # ====================================================

                (
                    loss,
                    pg_loss,
                    v_loss,
                    entropy_loss,
                    approx_kl,
                    clip_fraction,
                    batch_ratio
                ) = self.compute_loss(

                    batch["obs"],
                    batch["actions"],

                    batch["logprobs"],
                    batch["values"],

                    batch["advantages"],
                    batch["returns"],

                    batch["masks"]
                )

                # ====================================================
                # SEGURANÇA NUMÉRICA
                # ====================================================

                if not torch.isfinite(loss):

                    print(
                        "⚠️ PPO: loss inválida. "
                        "Update interrompido."
                    )

                    stop_early = True
                    break

                # ====================================================
                # BACKPROP
                # ====================================================

                self.optimizer.zero_grad(
                    set_to_none=True
                )

                loss.backward()

                # ====================================================
                # GRADIENT CLIPPING
                # ====================================================

                torch.nn.utils.clip_grad_norm_(
                    self.policy.parameters(),
                    self.max_grad_norm
                )

                self.optimizer.step()

                # ====================================================
                # MÉTRICAS
                # ====================================================

                mean_loss += loss.item()
                mean_pg += pg_loss.item()
                mean_v += v_loss.item()
                mean_entropy += entropy_loss.item()
                mean_kl += approx_kl.item()
                mean_clipfrac += clip_fraction.item()

                # ====================================================
                # CORREÇÃO:
                #
                # O valor retornado pelo batch agora é chamado
                # batch_ratio, enquanto mean_ratio continua sendo
                # apenas o acumulador.
                # ====================================================

                mean_ratio += batch_ratio.item()

                total_batches += 1

                # ====================================================
                # KL EARLY STOP
                # ====================================================

                if approx_kl.item() > self.target_kl:

                    stop_early = True

                    print(
                        f"🛑 PPO Early Stop | "
                        f"KL={approx_kl.item():.5f} "
                        f"> {self.target_kl:.5f}"
                    )

                    break

        # ============================================================
        # TENSORBOARD
        # ============================================================

        if total_batches > 0:

            mean_loss /= total_batches
            mean_pg /= total_batches
            mean_v /= total_batches
            mean_entropy /= total_batches
            mean_kl /= total_batches
            mean_clipfrac /= total_batches
            mean_ratio /= total_batches

            # --------------------------------------------------------
            # LOSS
            # --------------------------------------------------------

            self.writer.add_scalar(
                "loss/total",
                mean_loss,
                self.update_step
            )

            self.writer.add_scalar(
                "loss/policy",
                mean_pg,
                self.update_step
            )

            self.writer.add_scalar(
                "loss/value",
                mean_v,
                self.update_step
            )

            self.writer.add_scalar(
                "loss/entropy",
                mean_entropy,
                self.update_step
            )

            # --------------------------------------------------------
            # PPO
            # --------------------------------------------------------

            self.writer.add_scalar(
                "ppo/approx_kl",
                mean_kl,
                self.update_step
            )

            self.writer.add_scalar(
                "ppo/clip_fraction",
                mean_clipfrac,
                self.update_step
            )

            self.writer.add_scalar(
                "ppo/mean_ratio",
                mean_ratio,
                self.update_step
            )

            # --------------------------------------------------------
            # SELF-PLAY / ROLLOUT
            # --------------------------------------------------------
            
            valid_mask = rollout.valid[:rollout.ptr]

            valid_rewards = (
                rollout.rewards[:rollout.ptr][valid_mask]
            )

            valid_dones = (
                rollout.dones[:rollout.ptr][valid_mask]
            )

            valid_transitions = int(
                valid_mask.sum().item()
            )

            self.writer.add_scalar(
                "rollout/num_agents",
                rollout.num_envs,
                self.update_step
            )

            self.writer.add_scalar(
                "rollout/transitions",
                valid_transitions,
                self.update_step
            )

            self.writer.add_scalar(
                "rollout/mean_reward",
                valid_rewards.mean().item(),
                self.update_step
            )

            self.writer.add_scalar(
                "rollout/mean_done",
                valid_dones.mean().item(),
                self.update_step
            )

            # --------------------------------------------------------
            # TRAINING
            # --------------------------------------------------------

            self.writer.add_scalar(
                "training/epochs",
                epochs,
                self.update_step
            )

            self.writer.add_scalar(
                "training/batch_size",
                batch_size,
                self.update_step
            )

        # ============================================================
        # UPDATE COUNTER
        # ============================================================

        self.update_step += 1