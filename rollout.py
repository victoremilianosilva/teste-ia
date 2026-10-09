import torch


class RolloutBuffer:
    """
    RolloutBuffer para PPO com Self-Play.

    ================================================================
    MODELO DE DADOS
    ================================================================

    O buffer NÃO precisa conhecer diretamente o conceito de "lobby".

    O Trainer pode transformar:

        N lobbies × 8 jogadores

    em:

        N * 8 agentes

    Exemplo:

        4 lobbies × 8 jogadores = 32 agentes

    O buffer então trabalha com:

        num_steps × 32

    Cada agente possui seu próprio:

        - observation
        - action
        - reward
        - done
        - value
        - advantage
        - return
        - action masks

    ================================================================
    SELF-PLAY
    ================================================================

    É importante que `dones` seja individual.

    Exemplo:

        Player 0 -> eliminado
        Player 1 -> vivo
        Player 2 -> vivo
        ...

    Então:

        dones = [1, 0, 0, 0, 0, 0, 0, 0]

    O GAE do Player 0 termina naquele ponto enquanto os outros
    continuam normalmente.

    ================================================================
    """

    def __init__(
        self,
        num_steps,
        num_envs,
        obs_dim,
        action_dim,
        device,
        mask_shapes=None
    ):
        self.device = device

        self.num_steps = int(num_steps)

        # ============================================================
        # AGENTES
        # ============================================================
        #
        # IMPORTANTE:
        #
        # No self-play, `num_envs` representa o número de agentes
        # simultaneamente coletados pelo Trainer.
        #
        # Exemplo:
        #
        #   4 lobbies × 8 jogadores = 32
        #
        #   num_envs = 32
        #
        # ============================================================

        self.num_envs = int(num_envs)

        self.obs_dim = int(obs_dim)
        self.action_dim = int(action_dim)

        self.total_transitions = (
            self.num_steps * self.num_envs
        )

        self.ptr = 0

        # ============================================================
        # DADOS PRINCIPAIS
        # ============================================================

        self.obs = torch.zeros(
            (
                self.num_steps,
                self.num_envs,
                self.obs_dim
            ),
            dtype=torch.float32,
            device=self.device
        )

        self.actions = torch.zeros(
            (
                self.num_steps,
                self.num_envs,
                self.action_dim
            ),
            dtype=torch.long,
            device=self.device
        )

        self.logprobs = torch.zeros(
            (
                self.num_steps,
                self.num_envs
            ),
            dtype=torch.float32,
            device=self.device
        )

        self.rewards = torch.zeros(
            (
                self.num_steps,
                self.num_envs
            ),
            dtype=torch.float32,
            device=self.device
        )

        # ============================================================
        # DONE INDIVIDUAL
        # ============================================================
        #
        # Cada jogador possui seu próprio episódio.
        #
        # Isso é essencial no self-play.
        #
        # Exemplo:
        #
        # P0 morreu:
        #
        # dones[t] =
        # [1, 0, 0, 0, 0, 0, 0, 0]
        #
        # O GAE do P0 é interrompido.
        # Os outros jogadores continuam.
        #
        # ============================================================

        self.dones = torch.zeros(
            (
                self.num_steps,
                self.num_envs
            ),
            dtype=torch.float32,
            device=self.device
        )

        self.values = torch.zeros(
            (
                self.num_steps,
                self.num_envs
            ),
            dtype=torch.float32,
            device=self.device
        )

        # ============================================================
        # GAE / RETURNS
        # ============================================================

        self.advantages = torch.zeros(
            (
                self.num_steps,
                self.num_envs
            ),
            dtype=torch.float32,
            device=self.device
        )

        self.returns = torch.zeros(
            (
                self.num_steps,
                self.num_envs
            ),
            dtype=torch.float32,
            device=self.device
        )

        self.valid = torch.zeros(
            (self.num_steps, self.num_envs),
            dtype=torch.bool,
            device=self.device,
        )

        # ============================================================
        # ACTION MASKS
        # ============================================================

        self.masks = {}

        if mask_shapes is not None:

            for name, shape in mask_shapes.items():

                self.masks[name] = torch.zeros(
                    (
                        self.num_steps,
                        self.num_envs,
                        *shape
                    ),
                    dtype=torch.bool,
                    device=self.device
                )

    # =================================================================
    # ADD
    # =================================================================

    def add(
        self,
        obs,
        actions,
        logprobs,
        rewards,
        dones,
        values,
        masks_dict,
        valid=None,
    ):
        """
        Adiciona uma transição de todos os agentes.

        No self-play:

            obs.shape
                [num_agents, obs_dim]

            actions.shape
                [num_agents, action_dim]

            rewards.shape
                [num_agents]

            dones.shape
                [num_agents]

        Onde:

            num_agents = num_lobbies * 8
        """

        if valid is None:
            valid = torch.ones(
                self.num_envs,
                dtype=torch.bool,
                device=self.device,
            )
        else:
            valid = self._to_tensor(
                valid,
                dtype=torch.bool,
            )

        if tuple(valid.shape) != (self.num_envs,):
            raise ValueError(
                f"Shape inválido para valid: {tuple(valid.shape)}"
            )

        self.valid[self.ptr].copy_(valid)

        if self.ptr >= self.num_steps:
            raise RuntimeError(
                f"RolloutBuffer cheio: "
                f"ptr={self.ptr}, "
                f"num_steps={self.num_steps}"
            )

        # ============================================================
        # CONVERSÃO PARA TENSOR
        # ============================================================

        obs = self._to_tensor(
            obs,
            dtype=torch.float32
        )

        actions = self._to_tensor(
            actions,
            dtype=torch.long
        )

        logprobs = self._to_tensor(
            logprobs,
            dtype=torch.float32
        )

        rewards = self._to_tensor(
            rewards,
            dtype=torch.float32
        )

        dones = self._to_tensor(
            dones,
            dtype=torch.float32
        )

        values = self._to_tensor(
            values,
            dtype=torch.float32
        )

        # ============================================================
        # VALIDAR BATCH
        # ============================================================

        self._validate_step_shapes(
            obs,
            actions,
            logprobs,
            rewards,
            dones,
            values
        )

        # ============================================================
        # SALVAR
        # ============================================================

        self.obs[self.ptr].copy_(obs)
        self.actions[self.ptr].copy_(actions)
        self.logprobs[self.ptr].copy_(logprobs)
        self.rewards[self.ptr].copy_(rewards)
        self.dones[self.ptr].copy_(dones)
        self.values[self.ptr].copy_(values)

        # ============================================================
        # MÁSCARAS
        # ============================================================

        if masks_dict is None:
            masks_dict = {}

        for key, mask_tensor in masks_dict.items():

            mask_tensor = self._to_tensor(
                mask_tensor,
                dtype=torch.bool
            )

            # --------------------------------------------------------
            # Se a máscara ainda não existe, cria dinamicamente.
            # --------------------------------------------------------

            if key not in self.masks:

                if mask_tensor.ndim < 2:
                    raise ValueError(
                        f"Máscara '{key}' inválida. "
                        f"Esperado pelo menos 2 dimensões."
                    )

                self.masks[key] = torch.zeros(
                    (
                        self.num_steps,
                        self.num_envs,
                        *mask_tensor.shape[1:]
                    ),
                    dtype=torch.bool,
                    device=self.device
                )

            # --------------------------------------------------------
            # Validação
            # --------------------------------------------------------

            expected_shape = (
                self.num_envs,
                *self.masks[key].shape[2:]
            )

            if tuple(mask_tensor.shape) != expected_shape:

                raise ValueError(
                    f"Shape inválido para máscara '{key}': "
                    f"recebido={tuple(mask_tensor.shape)}, "
                    f"esperado={expected_shape}"
                )

            self.masks[key][self.ptr].copy_(mask_tensor)

        # ============================================================
        # PRÓXIMO PASSO
        # ============================================================

        self.ptr += 1

    # =================================================================
    # TENSOR HELPER
    # =================================================================

    def _to_tensor(
        self,
        value,
        dtype
    ):
        """
        Converte numpy/list/tensor para tensor no device correto.
        """

        if isinstance(value, torch.Tensor):

            return value.to(
                device=self.device,
                dtype=dtype
            )

        return torch.as_tensor(
            value,
            dtype=dtype,
            device=self.device
        )

    # =================================================================
    # VALIDATE
    # =================================================================

    def _validate_step_shapes(
        self,
        obs,
        actions,
        logprobs,
        rewards,
        dones,
        values
    ):
        """
        Garante que todos os agentes estejam sincronizados.

        Isso ajuda bastante a detectar problemas quando o lobby
        possuir jogadores eliminados.
        """

        expected_obs = (
            self.num_envs,
            self.obs_dim
        )

        expected_actions = (
            self.num_envs,
            self.action_dim
        )

        expected_vector = (
            self.num_envs
        )

        if tuple(obs.shape) != expected_obs:

            raise ValueError(
                f"obs com shape inválido: "
                f"{tuple(obs.shape)} != {expected_obs}"
            )

        if tuple(actions.shape) != expected_actions:

            raise ValueError(
                f"actions com shape inválido: "
                f"{tuple(actions.shape)} != {expected_actions}"
            )

        if tuple(logprobs.shape) != expected_vector:

            raise ValueError(
                f"logprobs com shape inválido: "
                f"{tuple(logprobs.shape)} != {expected_vector}"
            )

        if tuple(rewards.shape) != expected_vector:

            raise ValueError(
                f"rewards com shape inválido: "
                f"{tuple(rewards.shape)} != {expected_vector}"
            )

        if tuple(dones.shape) != expected_vector:

            raise ValueError(
                f"dones com shape inválido: "
                f"{tuple(dones.shape)} != {expected_vector}"
            )

        if tuple(values.shape) != expected_vector:

            raise ValueError(
                f"values com shape inválido: "
                f"{tuple(values.shape)} != {expected_vector}"
            )

    # =================================================================
    # GAE
    # =================================================================

    def compute_returns_and_advantages(
        self,
        next_value,
        next_done,
        gamma=0.99,
        gae_lambda=0.95
    ):
        """
        Calcula GAE separadamente para cada agente.

        ==============================================================
        SELF-PLAY
        ==============================================================

        `num_envs` pode representar:

            lobby_count × 8

        Cada índice é tratado independentemente.

        Exemplo:

            agent 0 -> morreu
            agent 1 -> vivo
            agent 2 -> vivo

        O done do agent 0 não interfere nos demais.

        ==============================================================
        """

        with torch.no_grad():

            # --------------------------------------------------------
            # Converter entradas
            # --------------------------------------------------------

            next_value = self._to_tensor(
                next_value,
                dtype=torch.float32
            ).reshape(self.num_envs)

            next_done = self._to_tensor(
                next_done,
                dtype=torch.float32
            ).reshape(self.num_envs)

            # --------------------------------------------------------
            # GAE atual de cada agente
            # --------------------------------------------------------

            gae = torch.zeros(
                self.num_envs,
                dtype=torch.float32,
                device=self.device
            )

            # --------------------------------------------------------
            # Backward pass
            # --------------------------------------------------------

            for t in range(
                self.num_steps - 1,
                -1,
                -1
            ):

                if t == self.num_steps - 1:

                    # Depois do último passo coletado
                    next_non_terminal = (
                        1.0 - next_done
                    )

                    next_values = next_value

                else:

                    # ------------------------------------------------
                    # O done produzido pela ação t determina se
                    # podemos utilizar V(s[t+1]).
                    # ------------------------------------------------

                    next_non_terminal = (
                        1.0 - self.dones[t]
                    )

                    next_values = (
                        self.values[t + 1]
                    )

                # ----------------------------------------------------
                # TD ERROR
                # ----------------------------------------------------

                delta = (
                    self.rewards[t]
                    + gamma
                    * next_values
                    * next_non_terminal
                    - self.values[t]
                )

                # ----------------------------------------------------
                # GAE
                # ----------------------------------------------------

                gae = (
                    delta
                    + gamma
                    * gae_lambda
                    * next_non_terminal
                    * gae
                )

                self.advantages[t] = gae

            # ========================================================
            # RETURNS
            # ========================================================

            self.returns = (
                self.advantages
                + self.values
            )

    # =================================================================
    # NORMALIZE ADVANTAGES
    # =================================================================

    def normalize_advantages(self, eps=1e-8):
        """
        Normaliza advantages globalmente.

        Isso é feito depois do rollout completo e antes dos updates
        PPO.

        No self-play isso permite misturar experiências dos
        diferentes jogadores/lobbies.
        """

        advantages = self.advantages.reshape(-1)

        mean = advantages.mean()
        std = advantages.std(unbiased=False)

        self.advantages = (
            self.advantages - mean
        ) / (
            std + eps
        )

    # =================================================================
    # BATCHES
    # =================================================================

    def get_batches(
        self,
        batch_size,
        normalize_advantages=False
    ):
        """
        Retorna mini-batches PPO.

        O flatten transforma:

            [num_steps, num_agents, ...]

        em:

            [num_steps * num_agents, ...]

        Isso permite misturar experiências de:

            lobby 0 / player 0
            lobby 0 / player 1
            ...
            lobby 1 / player 0
            ...

        durante o treinamento PPO.
        """

        if self.ptr == 0:
            raise RuntimeError(
                "Não é possível gerar batches: "
                "RolloutBuffer está vazio."
            )

        # ============================================================
        # NÚMERO REAL DE STEPS
        # ============================================================

        # Normalmente será num_steps.
        # Manter baseado em ptr deixa o buffer mais robusto caso
        # algum rollout termine antecipadamente.

        steps = self.ptr

        total_transitions = (
            steps * self.num_envs
        )

        valid_indices = torch.nonzero(
            self.valid[:steps].reshape(-1),
            as_tuple=False,
        ).squeeze(-1)

        if valid_indices.numel() == 0:
            return

        indices = valid_indices[
            torch.randperm(
                valid_indices.numel(),
                device=self.device,
            )
        ]
        
        # ============================================================
        # ADVANTAGE
        # ============================================================

        advantages = self.advantages[:steps]

        if normalize_advantages:

            mean = advantages.mean()
            std = advantages.std(
                unbiased=False
            )

            advantages = (
                advantages - mean
            ) / (
                std + 1e-8
            )

        # ============================================================
        # FLATTEN
        # ============================================================

        flat_obs = self.obs[:steps].reshape(
            total_transitions,
            self.obs_dim
        )

        flat_actions = self.actions[:steps].reshape(
            total_transitions,
            self.action_dim
        )

        flat_logprobs = self.logprobs[:steps].reshape(
            total_transitions
        )

        flat_advantages = advantages.reshape(
            total_transitions
        )

        flat_returns = self.returns[:steps].reshape(
            total_transitions
        )

        flat_values = self.values[:steps].reshape(
            total_transitions
        )

        # ============================================================
        # MÁSCARAS
        # ============================================================

        flat_masks = {}

        for key, mask_tensor in self.masks.items():

            flat_masks[key] = (
                mask_tensor[:steps]
                .reshape(
                    total_transitions,
                    *mask_tensor.shape[2:]
                )
            )

        # ============================================================
        # SHUFFLE
        # ============================================================

        indices = torch.randperm(
            total_transitions,
            device=self.device
        )

        # ============================================================
        # MINI-BATCHES
        # ============================================================

        for start in range(
            0,
            total_transitions,
            batch_size
        ):

            end = min(
                start + batch_size,
                total_transitions
            )

            batch_idx = indices[
                start:end
            ]

            yield {
                "obs": flat_obs[batch_idx],

                "actions": flat_actions[
                    batch_idx
                ],

                "logprobs": flat_logprobs[
                    batch_idx
                ],

                "advantages": flat_advantages[
                    batch_idx
                ],

                "returns": flat_returns[
                    batch_idx
                ],

                "values": flat_values[
                    batch_idx
                ],

                "masks": {
                    key: value[batch_idx]
                    for key, value in flat_masks.items()
                }
            }

    # =================================================================
    # READY
    # =================================================================

    def is_full(self):
        """Indica se o rollout atingiu num_steps."""

        return self.ptr >= self.num_steps

    # =================================================================
    # SIZE
    # =================================================================

    def size(self):
        """
        Retorna o número de transições armazenadas.
        """

        return self.ptr * self.num_envs

    # =================================================================
    # RESET
    # =================================================================

    def reset(self):
        """
        Limpa o rollout atual.

        Os tensores são reutilizados para evitar alocações
        desnecessárias a cada rollout.
        """

        self.ptr = 0

        # ------------------------------------------------------------
        # Não precisamos zerar todos os tensores aqui.
        #
        # O próximo rollout sobrescreverá as posições utilizadas.
        # ------------------------------------------------------------

    # =================================================================
    # DEBUG
    # =================================================================

    def debug_info(self):
        """
        Informações úteis para verificar o self-play.
        """

        return {
            "num_steps": self.num_steps,
            "num_agents": self.num_envs,
            "total_transitions": self.size(),
            "obs_dim": self.obs_dim,
            "action_dim": self.action_dim,
            "ptr": self.ptr,
            "full": self.is_full(),
            "mask_names": list(self.masks.keys()),
        }