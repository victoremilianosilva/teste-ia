import torch
import torch.optim as optim
import numpy as np
import os

from torch.utils.tensorboard import SummaryWriter

from lobby.TFTLobby import TFTLobby

from vector_lobby_env import LobbyVectorEnv

from policy import TFTPolicy
from rollout import RolloutBuffer
from ppo import PPOTrainer

from strategy.StrategyManager import Strategy
from ai.ActionMaskManager import ActionType

class Trainer:

    # ================================================================
    # 🏟️ CONFIGURAÇÃO DA LOBBY
    # ================================================================

    PLAYERS_PER_LOBBY = 8

    # ================================================================
    # 🎮 ACTION SPACE
    # ================================================================

    ACTION_DIMS = [
        7,   # type
        5,   # shop_slot
        9,   # bench_slot
        28,  # board_target
        28,  # board_source
        28   # board_move_target
    ]

    ACTION_DIM = 6

    # ================================================================
    # 🎭 MASK SHAPES
    # ================================================================

    MASK_SHAPES = {
        "type_mask": (7,),
        "shop_mask": (5,),
        "bench_source_mask": (9,),
        "board_target_mask": (28,),
        "board_source_mask": (28,),
        "board_move_target_masks": (28, 28),
        "bench_move_source_mask": (9,),
        "bench_to_board_target_masks": (9, 28),
    }

    def __init__(
        self,
        num_envs=4,
        use_subprocess=True
    ):

        # ============================================================
        # 🖥️ DEVICE
        # ============================================================

        print(
            f"GPU disponível: "
            f"{torch.cuda.is_available()}"
        )

        if torch.cuda.is_available():

            print(
                f"GPU nome: "
                f"{torch.cuda.get_device_name(0)}"
            )

            print(
                f"Memória total: "
                f"{torch.cuda.get_device_properties(0).total_memory / 1e9:.2f} GB"
            )

        # ------------------------------------------------------------
        # Mantendo CPU por enquanto
        # ------------------------------------------------------------

        # self.device = torch.device(
        #     "cuda" if torch.cuda.is_available()
        #     else "cpu"
        # )

        self.device = torch.device("cpu")

        # ============================================================
        # 🏟️ ENV CONFIG
        # ============================================================

        # IMPORTANTE:
        #
        # Agora num_envs representa:
        #
        #     número de LOBBIES
        #
        # e não número de jogadores.
        #
        # Exemplo:
        #
        #     num_envs = 4
        #
        #     4 lobbies
        #     × 8 jogadores
        #     = 32 agentes
        #
        self.num_envs = num_envs

        self.use_subprocess = use_subprocess

        self.num_agents = (
            self.num_envs
            * self.PLAYERS_PER_LOBBY
        )

        print(
            f"🏟️ Lobbies: {self.num_envs}"
        )

        print(
            f"👥 Jogadores por lobby: "
            f"{self.PLAYERS_PER_LOBBY}"
        )

        print(
            f"🤖 Agentes totais: "
            f"{self.num_agents}"
        )

        # ============================================================
        # 📊 TENSORBOARD
        # ============================================================

        self.writer = SummaryWriter(
            "tft_logs/AkameIA_V1"
        )

        # ============================================================
        # 🏭 ENV FACTORY
        # ============================================================

        def make_env():
            return TFTLobby()

        # ============================================================
        # 🚀 VECTOR ENV
        # ============================================================

        # LobbyVectorEnv é serial: uma instância por lobby.
        # Inicializamos independentemente de use_subprocess.
        self.vec_env = LobbyVectorEnv(
            [make_env for _ in range(self.num_envs)]
        )

        dummy_obs = self.vec_env.reset()

        if dummy_obs.ndim != 3:
            raise ValueError(
                "Esperava observações no formato "
                "(num_lobbies, 8, obs_dim), "
                f"recebi {dummy_obs.shape}"
            )

        self.obs_dim = dummy_obs.shape[-1]

        print(f"📐 Observation dim: {self.obs_dim}")
        print(f"📐 Vec observation shape: {dummy_obs.shape}")

        # ============================================================
        # 🧠 POLICY
        # ============================================================

        self.policy = TFTPolicy(
            self.obs_dim,
            self.ACTION_DIMS
        ).to(self.device)

        # ============================================================
        # 💾 CHECKPOINT
        # ============================================================

        self.start_update = 1

        checkpoint_path = (
            "tft_checkpoint.pt"
        )

        if os.path.exists(
            checkpoint_path
        ):

            print(
                "📂 Carregando checkpoint completo..."
            )

            checkpoint = torch.load(
                checkpoint_path,
                map_location=self.device
            )

            self.policy.load_state_dict(
                checkpoint["policy"]
            )

            print(
                "✅ Pesos da política carregados."
            )

            # --------------------------------------------------------
            # OPTIMIZER
            # --------------------------------------------------------

            self.optimizer = optim.Adam(
                self.policy.parameters(),
                lr=3e-4,
                eps=1e-5
            )

            if "optimizer" in checkpoint:

                self.optimizer.load_state_dict(
                    checkpoint["optimizer"]
                )

                print(
                    "✅ Estado do optimizer restaurado."
                )

            # --------------------------------------------------------
            # SCHEDULER
            # --------------------------------------------------------

            self.scheduler = (
                optim.lr_scheduler.CosineAnnealingLR(
                    self.optimizer,
                    T_max=2000,
                    eta_min=5e-5
                )
            )

            if "scheduler" in checkpoint:

                self.scheduler.load_state_dict(
                    checkpoint["scheduler"]
                )

                print(
                    "✅ Estado do scheduler restaurado."
                )

            # --------------------------------------------------------
            # UPDATE
            # --------------------------------------------------------

            self.start_update = (
                checkpoint.get(
                    "update",
                    0
                )
                + 1
            )

            print(
                f"▶️ Retomando do update "
                f"{self.start_update}"
            )

            print(
                "⚠️ ATENÇÃO: o checkpoint anterior "
                "foi treinado antes do Self-Play."
            )

            print(
                "⚠️ Os pesos são compatíveis com a "
                "policy, mas o comportamento aprendido "
                "é de ambiente antigo."
            )

        else:

            print(
                "⚠️ Nenhum checkpoint encontrado, "
                "iniciando do zero."
            )

            self.optimizer = optim.Adam(
                self.policy.parameters(),
                lr=3e-4,
                eps=1e-5
            )

            self.scheduler = (
                optim.lr_scheduler.CosineAnnealingLR(
                    self.optimizer,
                    T_max=2000,
                    eta_min=5e-5
                )
            )

        # ============================================================
        # 🧠 PPO TRAINER
        # ============================================================

        self.ppo = PPOTrainer(
            self.policy,
            self.optimizer,
            self.writer,
            clip_coef=0.2,
            ent_coef=0.02,
            vf_coef=0.5,
            max_grad_norm=0.5,
            target_kl=0.02
        )

    # ================================================================
    # 🔄 FLATTEN OBSERVATIONS
    # ================================================================

    def _flatten_observations(
        self,
        observations
    ):
        """
        Converte:

            (num_lobbies, 8, obs_dim)

        para:

            (num_lobbies * 8, obs_dim)

        Exemplo:

            (4, 8, 300)
                ↓
            (32, 300)
        """

        observations = np.asarray(
            observations,
            dtype=np.float32
        )

        expected_shape = (
            self.num_envs,
            self.PLAYERS_PER_LOBBY,
            self.obs_dim
        )

        if observations.shape != expected_shape:

            raise ValueError(
                "Shape de observation inválido: "
                f"{observations.shape} "
                f"!= {expected_shape}"
            )

        return observations.reshape(
            self.num_agents,
            self.obs_dim
        )

    # ================================================================
    # 🎭 FLATTEN MASKS
    # ================================================================

    def _flatten_masks(
        self,
        gym_masks
    ):
        """
        Converte as máscaras:

            lobby 0
                player 0
                player 1
                ...
                player 7

            lobby 1
                player 0
                ...

        para:

            num_agents

        Retorna um dicionário:

            {
                "type_mask":        (agents, 7),
                "shop_mask":        (agents, 5),
                ...
            }

        ============================================================
        ⚠️ JOGADOR MORTO
        ============================================================

        Jogador morto recebe máscara de PASS.

        PASS = ActionType.PASS = 6

        Isso evita distribuição categórica inválida.
        """

        flat_masks = {}

        # ------------------------------------------------------------
        # Quantidade de lobbies
        # ------------------------------------------------------------

        if len(gym_masks) != self.num_envs:

            raise ValueError(
                f"Número de máscaras recebido "
                f"({len(gym_masks)}) != "
                f"num_envs ({self.num_envs})"
            )

        # ------------------------------------------------------------
        # Percorrer lobbies
        # ------------------------------------------------------------

        for lobby_idx in range(
            self.num_envs
        ):

            lobby_masks = gym_masks[
                lobby_idx
            ]

            if len(lobby_masks) != self.PLAYERS_PER_LOBBY:

                raise ValueError(
                    f"Lobby {lobby_idx} possui "
                    f"{len(lobby_masks)} jogadores "
                    f"nas máscaras."
                )

        # ------------------------------------------------------------
        # Cada máscara
        # ------------------------------------------------------------

        for key, shape in self.MASK_SHAPES.items():

            values = []

            for lobby_idx in range(
                self.num_envs
            ):

                lobby_masks = gym_masks[
                    lobby_idx
                ]

                for player_idx in range(
                    self.PLAYERS_PER_LOBBY
                ):

                    player_mask = np.asarray(
                        lobby_masks[
                            player_idx
                        ][key],
                        dtype=np.bool_
                    )

                    expected_shape = shape

                    if player_mask.shape != expected_shape:

                        raise ValueError(
                            f"Máscara '{key}' inválida "
                            f"para lobby={lobby_idx}, "
                            f"player={player_idx}: "
                            f"{player_mask.shape} "
                            f"!= {expected_shape}"
                        )

                    values.append(
                        player_mask
                    )

            flat_mask = np.asarray(
                values,
                dtype=np.bool_
            )

            flat_masks[key] = torch.as_tensor(
                flat_mask,
                dtype=torch.bool,
                device=self.device
            )

        # ============================================================
        # ☠️ CORREÇÃO DE JOGADORES MORTOS
        # ============================================================

        type_mask = flat_masks[
            "type_mask"
        ]

        for agent_idx in range(
            self.num_agents
        ):

            # Se não existe nenhuma ação válida,
            # consideramos o jogador eliminado.

            if not torch.any(
                type_mask[agent_idx]
            ):

                # ----------------------------------------------------
                # Todas as ações inválidas
                # ----------------------------------------------------

                type_mask[
                    agent_idx
                ].fill_(False)

                # ----------------------------------------------------
                # PASS = 6
                # ----------------------------------------------------

                type_mask[
                    agent_idx,
                    int(ActionType.PASS)
                ] = True

                # ----------------------------------------------------
                # As outras cabeças não importam para PASS,
                # mas precisamos fornecer uma categoria válida
                # para evitar Categorical com logits inválidos.
                # ----------------------------------------------------

                flat_masks[
                    "shop_mask"
                ][agent_idx].fill_(False)

                flat_masks[
                    "shop_mask"
                ][agent_idx, 0] = True

                flat_masks[
                    "bench_source_mask"
                ][agent_idx].fill_(False)

                flat_masks[
                    "bench_source_mask"
                ][agent_idx, 0] = True

                flat_masks[
                    "board_target_mask"
                ][agent_idx].fill_(False)

                flat_masks[
                    "board_target_mask"
                ][agent_idx, 0] = True

                flat_masks[
                    "board_source_mask"
                ][agent_idx].fill_(False)

                flat_masks[
                    "board_source_mask"
                ][agent_idx, 0] = True

                flat_masks[
                    "board_move_target_masks"
                ][agent_idx].fill_(False)

                flat_masks[
                    "board_move_target_masks"
                ][agent_idx, 0, 0] = True

        return flat_masks

    # ================================================================
    # 🎮 ACTIONS → DICTS
    # ================================================================

    def _actions_to_lobby_format(
        self,
        actions
    ):
        """
        Converte ações da policy:

            (num_agents, 6)

        para:

            [
                [
                    player0,
                    player1,
                    ...
                    player7
                ],
                [
                    player0,
                    ...
                ]
            ]

        Formato exigido pelo TFTGymEnv.
        """

        actions = actions.detach().cpu().numpy()

        expected_shape = (
            self.num_agents,
            self.ACTION_DIM
        )

        if actions.shape != expected_shape:

            raise ValueError(
                f"Shape de actions inválido: "
                f"{actions.shape} "
                f"!= {expected_shape}"
            )

        lobby_actions = []

        for lobby_idx in range(
            self.num_envs
        ):

            players = []

            for player_idx in range(
                self.PLAYERS_PER_LOBBY
            ):

                agent_idx = (
                    lobby_idx
                    * self.PLAYERS_PER_LOBBY
                    + player_idx
                )

                action = actions[
                    agent_idx
                ]

                players.append({
                    "type": int(
                        action[0]
                    ),

                    "shop_slot": int(
                        action[1]
                    ),

                    "bench_slot": int(
                        action[2]
                    ),

                    "board_target": int(
                        action[3]
                    ),

                    "board_source": int(
                        action[4]
                    ),

                    "board_move_target": int(
                        action[5]
                    )
                })

            lobby_actions.append(
                players
            )

        return lobby_actions

    # ================================================================
    # 📊 REWARDS → FLAT
    # ================================================================

    def _flatten_vector(
        self,
        values,
        name
    ):
        """
        Converte:

            (num_lobbies, 8)

        para:

            (num_lobbies * 8,)
        """

        values = np.asarray(
            values,
            dtype=np.float32
        )

        expected_shape = (
            self.num_envs,
            self.PLAYERS_PER_LOBBY
        )

        if values.shape != expected_shape:

            raise ValueError(
                f"{name} possui shape "
                f"{values.shape}, "
                f"esperado {expected_shape}"
            )

        return values.reshape(
            self.num_agents
        )

    # ================================================================
    # 🧠 STRATEGY LOGGING
    # ================================================================

    def _collect_strategy_counts(
        self,
        strategies
    ):
        """
        strategies vem como:

            [
                [
                    strategy_p0,
                    ...
                    strategy_p7
                ],
                ...
            ]

        Conta todos os jogadores.
        """

        counts = np.zeros(
            len(Strategy),
            dtype=np.int32
        )

        for lobby_strategies in strategies:

            for strategy in lobby_strategies:

                if strategy is None:
                    continue

                try:

                    counts[
                        strategy.value
                    ] += 1

                except (
                    AttributeError,
                    IndexError
                ):

                    pass

        return counts

    # ================================================================
    # 🏋️ TRAIN
    # ================================================================

    def train(
        self,
        total_updates=1000,
        rollout_steps=128
    ):

        start = self.start_update

        end = (
            start
            + total_updates
        )

        print(
            f"🔄 Executando updates "
            f"de {start} até {end - 1} "
            f"(total de {total_updates} updates)"
        )

        print(
            f"🏟️ Lobbies simultâneas: "
            f"{self.num_envs}"
        )

        print(
            f"👥 Jogadores por lobby: "
            f"{self.PLAYERS_PER_LOBBY}"
        )

        print(
            f"🤖 Agentes simultâneos: "
            f"{self.num_agents}"
        )

        # ============================================================
        # 📦 ROLLOUT BUFFER
        # ============================================================

        rollout = RolloutBuffer(
            rollout_steps,
            self.num_agents,
            self.obs_dim,
            self.ACTION_DIM,
            self.device,
            self.MASK_SHAPES
        )

        # ============================================================
        # 🔄 RESET
        # ============================================================

        raw_obs = self.vec_env.reset()

        obs_np = self._flatten_observations(
            raw_obs
        )

        obs = torch.as_tensor(
            obs_np,
            dtype=torch.float32,
            device=self.device
        )

        # ============================================================
        # DONE INDIVIDUAL
        # ============================================================

        dones = torch.zeros(
            self.num_agents,
            dtype=torch.float32,
            device=self.device
        )

        # ============================================================
        # 📈 EPISODE RETURNS
        # ============================================================

        episode_returns = np.zeros(
            self.num_agents,
            dtype=np.float32
        )

        # Evita registrar várias vezes o mesmo episódio individual.
        episode_active = np.ones(
            self.num_agents,
            dtype=np.bool_,
        )

        # ☠️ Controle de jogadores que ainda podem gerar experiências.
        # Começam todos ativos no início das partidas.
        active_agents = np.ones(
            self.num_agents,
            dtype=np.bool_,
        )

        episode_history = []

        print(
            f"🚀 Iniciando treinamento em "
            f"{self.device}"
        )

        print(
            f"🏟️ {self.num_envs} lobbies "
            f"× {self.PLAYERS_PER_LOBBY} jogadores "
            f"= {self.num_agents} agentes"
        )

        # ============================================================
        # 🔁 UPDATE LOOP
        # ============================================================

        for update in range(
            start,
            end
        ):

            rollout.reset()

            # --------------------------------------------------------
            # LOGGING
            # --------------------------------------------------------

            action_type_counts = np.zeros(
                7,
                dtype=np.int32
            )

            strategy_counts = np.zeros(
                len(Strategy),
                dtype=np.int32
            )

            self.policy.eval()

            # ========================================================
            # 📥 COLETA DE EXPERIÊNCIAS
            # ========================================================

            for step in range(
                rollout_steps
            ):

                # ====================================================
                # 🎭 MÁSCARAS
                # ====================================================

                gym_masks = (
                    self.vec_env.env_method(
                        "get_action_masks"
                    )
                )

                masks = self._flatten_masks(
                    gym_masks
                )

                # ====================================================
                # 🧠 STRATEGIES
                # ====================================================

                current_strategies = (
                    self.vec_env.env_method(
                        "get_strategies"
                    )
                )

                current_strategy_counts = (
                    self._collect_strategy_counts(
                        current_strategies
                    )
                )

                strategy_counts += (
                    current_strategy_counts
                )


                # 📸 Fotografa quem pode gerar experiência neste passo.
                # A cópia precisa acontecer ANTES da ação.
                transition_valid = active_agents.copy()

                # ====================================================
                # 🤖 POLICY
                # ====================================================

                with torch.no_grad():

                    (
                        actions,
                        logprobs,
                        _,
                        values
                    ) = self.policy.get_action(
                        obs,
                        masks=masks
                    )

                # ====================================================
                # 📊 ACTION LOGGING
                # ====================================================

                action_np = (
                    actions.detach()
                    .cpu()
                    .numpy()
                )

                for agent_idx in range(
                    self.num_agents
                ):

                    action_type = int(
                        action_np[
                            agent_idx,
                            0
                        ]
                    )

                    if (
                        0 <= action_type < 7
                    ):

                        action_type_counts[
                            action_type
                        ] += 1

                # ====================================================
                # 🎮 CONVERTER PARA LOBBIES
                # ====================================================

                lobby_actions = (
                    self._actions_to_lobby_format(
                        actions
                    )
                )

                # ====================================================
                # 🏟️ EXECUTAR LOBBIES
                # ====================================================

                (
                    next_obs_raw,
                    rewards_raw,
                    lobby_dones_raw,
                    infos
                ) = self.vec_env.step(
                    lobby_actions
                )

                # ====================================================
                # 👀 NEXT OBS
                # ====================================================

                next_obs_np = (
                    self._flatten_observations(
                        next_obs_raw
                    )
                )

                next_obs = torch.as_tensor(
                    next_obs_np,
                    dtype=torch.float32,
                    device=self.device
                )

                # ====================================================
                # ❤️ REWARDS
                # ====================================================

                rewards_np = (
                    self._flatten_vector(
                        rewards_raw,
                        "rewards"
                    )
                )

                rewards = torch.as_tensor(
                    rewards_np,
                    dtype=torch.float32,
                    device=self.device
                )

                # ====================================================
                # ☠️ PLAYER DONES
                # ====================================================

                player_dones_np = (
                    self._flatten_vector(
                        lobby_dones_raw,
                        "player_dones"
                    )
                )

                # ☠️ Atualiza a atividade depois da ação.
                # A transição deste passo já foi marcada em transition_valid.

                for lobby_idx, info in enumerate(infos):
                    start_idx = lobby_idx * self.PLAYERS_PER_LOBBY
                    end_idx = start_idx + self.PLAYERS_PER_LOBBY

                    if info.get("lobby_done", False):
                        # A partida terminou e a lobby foi reiniciada.
                        # Os oito jogadores podem gerar novas experiências.
                        active_agents[start_idx:end_idx] = True
                    else:
                        # Jogadores eliminados não geram experiências
                        # nos próximos passos da mesma partida.
                        active_agents[start_idx:end_idx] &= (
                            ~player_dones_np[start_idx:end_idx].astype(np.bool_)
                        )

                next_dones = torch.as_tensor(
                    player_dones_np,
                    dtype=torch.float32,
                    device=self.device
                )

                # ====================================================
                # 📦 ROLLOUT
                # ====================================================

                rollout.add(
                    obs,
                    actions,
                    logprobs,
                    rewards,
                    next_dones,
                    values,
                    masks,
                    valid=transition_valid,
                )

                # ====================================================
                # 🔄 UPDATE STATE
                # ====================================================

                obs = next_obs

                dones = next_dones

                episode_returns += (
                    rewards_np
                )

                
                # ============================================================
                # 📊 EPISODE LOG — UM REGISTRO POR EPISÓDIO
                # ============================================================

                for agent_idx, done in enumerate(player_dones_np):
                    if done and episode_active[agent_idx]:
                        ret = float(episode_returns[agent_idx])

                        self.writer.add_scalar(
                            "charts/episode_return",
                            ret,
                            len(episode_history),
                        )

                        episode_history.append(ret)
                        episode_returns[agent_idx] = 0.0
                        episode_active[agent_idx] = False

                # Quando a lobby termina, todos os oito jogadores iniciam
                # um novo episódio na próxima partida.
                for lobby_idx, info in enumerate(infos):
                    if info.get("lobby_done", False):
                        start_idx = lobby_idx * self.PLAYERS_PER_LOBBY
                        end_idx = start_idx + self.PLAYERS_PER_LOBBY

                        episode_active[start_idx:end_idx] = True
                        episode_returns[start_idx:end_idx] = 0.0

            # ========================================================
            # 🧮 BOOTSTRAP VALUE
            # ========================================================

            gym_masks = (
                self.vec_env.env_method(
                    "get_action_masks"
                )
            )

            next_masks = self._flatten_masks(
                gym_masks
            )

            with torch.no_grad():

                next_value = (
                    self.policy.get_value(
                        obs,
                        masks=next_masks
                    )
                )

            rollout.compute_returns_and_advantages(
                next_value,
                dones
            )

            # ========================================================
            # 🔥 ENTROPY COEFFICIENT
            # ========================================================

            initial_ent = 0.02

            final_ent = 0.005

            decay_rate = 2.0

            progress = (
                update
                / max(
                    1,
                    total_updates
                )
            )

            progress = min(
                progress,
                1.0
            )

            self.ppo.ent_coef = (
                final_ent
                + (
                    initial_ent
                    - final_ent
                )
                * np.exp(
                    -decay_rate
                    * progress
                )
            )

            self.writer.add_scalar(
                "charts/entropy_coef",
                self.ppo.ent_coef,
                update
            )

            
            # ========================================================
            # 📊 ENTROPY SAMPLE
            # ========================================================

            with torch.no_grad():

                # ----------------------------------------------------
                # Selecionar somente transições válidas
                # ----------------------------------------------------

                valid_indices = torch.nonzero(
                    rollout.valid[:rollout.ptr].reshape(-1),
                    as_tuple=False,
                ).squeeze(-1)

                if valid_indices.numel() > 0:

                    sample_obs = (
                        rollout.obs[:rollout.ptr]
                        .reshape(
                            -1,
                            rollout.obs.shape[-1]
                        )[valid_indices]
                    )

                    sample_actions = (
                        rollout.actions[:rollout.ptr]
                        .reshape(
                            -1,
                            rollout.actions.shape[-1]
                        )[valid_indices]
                    )

                    sample_masks = {
                        k: v[:rollout.ptr].reshape(
                            -1,
                            *v.shape[2:]
                        )[valid_indices]
                        for k, v in rollout.masks.items()
                    }

                    # ------------------------------------------------
                    # Limitar a amostra às primeiras 256 transições
                    # válidas, não às primeiras 256 posições do buffer.
                    # ------------------------------------------------

                    sample_size = min(
                        256,
                        sample_obs.shape[0]
                    )

                    sample_obs = sample_obs[:sample_size]
                    sample_actions = sample_actions[:sample_size]

                    sample_masks = {
                        k: v[:sample_size]
                        for k, v in sample_masks.items()
                    }

                    (
                        _,
                        entropy_sample,
                        _
                    ) = self.policy.evaluate_actions(
                        sample_obs,
                        sample_actions,
                        masks=sample_masks
                    )

                    self.writer.add_scalar(
                        "entropy/total_mean",
                        entropy_sample.mean().item(),
                        update
                    )

            # ========================================================
            # 🧠 PPO UPDATE
            # ========================================================

            self.policy.train()

            self.ppo.update(
                rollout,
                batch_size=64,
                epochs=4
            )

            # ========================================================
            # 📉 SCHEDULER
            # ========================================================

            self.scheduler.step()

            current_lr = (
                self.optimizer
                .param_groups[0]["lr"]
            )

            self.writer.add_scalar(
                "charts/learning_rate",
                current_lr,
                update
            )
  
            # ========================================================
            # 📊 GENERAL LOGS
            # ========================================================
            mean_reward = None
            valid_mask = rollout.valid[:rollout.ptr]

            if valid_mask.any():

                valid_rewards = (
                    rollout.rewards[:rollout.ptr][valid_mask]
                )

                valid_values = (
                    rollout.values[:rollout.ptr][valid_mask]
                )

                valid_advantages = (
                    rollout.advantages[:rollout.ptr][valid_mask]
                )

                mean_reward = valid_rewards.mean().item()

                self.writer.add_scalar(
                    "charts/mean_reward",
                    mean_reward,
                    update
                )

                self.writer.add_scalar(
                    "charts/value_mean",
                    valid_values.mean().item(),
                    update
                )

                self.writer.add_scalar(
                    "charts/advantage_mean",
                    valid_advantages.mean().item(),
                    update
                )

            # ========================================================
            # 👥 AGENTS
            # ========================================================

            self.writer.add_scalar(
                "selfplay/num_lobbies",
                self.num_envs,
                update
            )

            self.writer.add_scalar(
                "selfplay/players_per_lobby",
                self.PLAYERS_PER_LOBBY,
                update
            )

            self.writer.add_scalar(
                "selfplay/total_agents",
                self.num_agents,
                update
            )

            # ========================================================
            # 🎭 STRATEGIES
            # ========================================================

            for strat in Strategy:

                self.writer.add_scalar(
                    f"strategy/{strat.name}",
                    strategy_counts[
                        strat.value
                    ],
                    update
                )

            # ========================================================
            # 📈 EPISODE RETURN
            # ========================================================

            if len(episode_history) > 0:

                self.writer.add_scalar(
                    "charts/episode_return_mean_100",
                    np.mean(
                        episode_history[-100:]
                    ),
                    update
                )

            # ========================================================
            # 🏆 PRINT
            # ========================================================

            if update % 5 == 0 and mean_reward is not None:

                print(
                    f"📊 UPDATE {update} | "
                    f"Reward: "
                    f"{mean_reward:.3f} | "
                    f"Agents: {self.num_agents} | "
                    f"Ent: "
                    f"{self.ppo.ent_coef:.5f}"
                )

                # ----------------------------------------------------
                # ACTION COUNTS
                # ----------------------------------------------------

                for idx, count in enumerate(
                    action_type_counts
                ):

                    try:

                        action_name = (
                            ActionType(
                                idx
                            ).name
                        )

                    except ValueError:

                        action_name = (
                            f"UNKNOWN_{idx}"
                        )

                    self.writer.add_scalar(
                        f"actions/{action_name}",
                        count,
                        update
                    )

            # ========================================================
            # 💾 CHECKPOINT
            # ========================================================

            if update % 40 == 0:

                torch.save(
                    {
                        "policy":
                            self.policy.state_dict(),

                        "optimizer":
                            self.optimizer.state_dict(),

                        "scheduler":
                            self.scheduler.state_dict(),

                        "update":
                            update
                    },
                    "tft_checkpoint.pt"
                )

                print(
                    f"💾 Checkpoint salvo | "
                    f"update={update}"
                )

        # ============================================================
        # 🔚 CLOSE
        # ============================================================

        self.vec_env.close()

        self.writer.close()


# ====================================================================
# 🚀 MAIN
# ====================================================================

if __name__ == "__main__":

    # ================================================================
    # 🏟️ IMPORTANTE
    # ================================================================
    #
    # Agora:
    #
    #     num_envs = número de LOBBIES
    #
    # Exemplo:
    #
    #     4 lobbies
    #     × 8 jogadores
    #     = 32 agentes
    #
    # ================================================================

    trainer = Trainer(
        num_envs=4,
        use_subprocess=True
    )

    trainer.train(
        total_updates=2000,
        rollout_steps=128
    )