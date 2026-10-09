import torch
import torch.nn as nn
import torch.nn.functional as F
from torch.distributions import Categorical


class TFTPolicy(nn.Module):
    def __init__(self, obs_dim, action_dims, hidden_size=512):
        super().__init__()
        self.obs_dim = obs_dim
        self.action_dims = action_dims
        self.num_action_types = action_dims[0]
        
        # --- DIMENSÕES BLINDADAS (Lendo de frente para trás) ---
        self.num_cell_features = 5  # [cost/5, star/3, impact, comp_score, role]
        self.pre_board_dim = 22     # Tamanho fixo do início: 10 do Core + 12 de Strategy
        self.board_flat_dim = 4 * 7 * self.num_cell_features  # 140
        
        # O contexto global passa a ser tudo que NÃO é o tabuleiro plano
        self.global_features_dim = obs_dim - self.board_flat_dim

        # Encoder Convolucional (Percepção Espacial Geométrica)
        self.board_cnn = nn.Sequential(
            nn.Conv2d(in_channels=self.num_cell_features, out_channels=32, kernel_size=3, padding=1),
            nn.ReLU(),
            nn.Conv2d(32, 64, kernel_size=3, padding=1),
            nn.ReLU(),
            nn.Flatten()
        )
        cnn_output_dim = 4 * 7 * 64  # 1792 neurônios de mapas de características

        # Encoder MLP para Dados Globais e Contextuais combinados
        self.global_mlp = nn.Sequential(
            nn.Linear(self.global_features_dim, 256),
            nn.ReLU(),
            nn.Linear(256, 256),
            nn.ReLU()
        )

        # Camada de Fusão de Alta Performance
        self.fusion = nn.Sequential(
            nn.Linear(cnn_output_dim + 256, hidden_size),
            nn.ReLU(),
            nn.Linear(hidden_size, hidden_size),
            nn.ReLU()
        )

        # --- Cabeças de Decisão Autorregressivas ---
        self.type_head = nn.Linear(hidden_size, action_dims[0])
        self.shop_head = nn.Linear(hidden_size + self.num_action_types, action_dims[1])
        self.bench_head = nn.Linear(hidden_size + self.num_action_types, action_dims[2])
        self.bench_to_board_head = nn.Linear(hidden_size + self.num_action_types, action_dims[3])
        self.board_source_head = nn.Linear(hidden_size + self.num_action_types, action_dims[4])
        self.board_move_target_head = nn.Linear(
            hidden_size + self.num_action_types + action_dims[4], action_dims[5]
        )
        self.value_head = nn.Linear(hidden_size, 1)

    def encode(self, obs):
        """ Fatia cirurgicamente o tabuleiro do meio do vetor de estado e processa em 2D """
        # FIX: se o env mudar de dimensão, o erro aparece aqui com mensagem clara
        # em vez do CNN processar features errados silenciosamente.
        assert obs.shape[-1] == self.obs_dim, (
            f"obs_dim mismatch: esperado {self.obs_dim}, recebido {obs.shape[-1]}. "
            f"Verifique se pre_board_dim={self.pre_board_dim} está alinhado com _get_state()."
        )
        # Extrai a seção geométrica do tabuleiro usando o deslocamento inicial fixo
        board_part = obs[:, self.pre_board_dim : self.pre_board_dim + self.board_flat_dim]

        # Isola e concatena todo o resto (o início do estado + a cauda dinâmica pós-tabuleiro)
        pre_part = obs[:, :self.pre_board_dim]
        post_part = obs[:, self.pre_board_dim + self.board_flat_dim :]
        global_part = torch.cat([pre_part, post_part], dim=-1)

        # Transforma o vetor plano em uma imagem estruturada (Batch, Features, Rows, Cols) -> (B, 5, 4, 7)
        board_2d = board_part.view(-1, self.num_cell_features, 4, 7)
        
        # Processamento paralelo nas sub-redes dedicadas
        cnn_features = self.board_cnn(board_2d)
        global_features = self.global_mlp(global_part)
        
        # Fusão latente
        combined = torch.cat([cnn_features, global_features], dim=-1)
        return self.fusion(combined)

    def get_value(self, obs, masks=None):
        """ Retorna a estimativa de valor do estado (ignora as máscaras se enviadas) """
        return self.value_head(self.encode(obs)).squeeze(-1)

    def get_action(self, obs, masks=None, deterministic=False):
        """ Atalho para compatibilidade com o trainer.py """
        return self.get_action_and_value(obs, masks=masks, deterministic=deterministic)

    @staticmethod
    def _mask_logits(logits, mask):
        return logits.masked_fill(mask == 0, -1e9)

    @staticmethod
    def _sample_categorical(logits, deterministic):
        if deterministic:
            return torch.argmax(logits, dim=-1)
        else:
            dist = Categorical(logits=logits)
            return dist.sample()

    def get_action_and_value(self, obs, masks=None, deterministic=False):
        device = obs.device
        batch_size = obs.shape[0]

        features = self.encode(obs)

        # --- Action type ---
        type_logits = self.type_head(features)
        if masks is not None:
            type_logits = self._mask_logits(type_logits, masks["type_mask"])
        action_type = self._sample_categorical(type_logits, deterministic)
        
        type_dist = Categorical(logits=type_logits)
        type_logprob = type_dist.log_prob(action_type)
        type_entropy = type_dist.entropy()

        total_logprob = type_logprob.clone()
        total_entropy = type_entropy.clone()

        # --- Conditioning ---
        type_onehot = F.one_hot(action_type, num_classes=self.num_action_types).float()
        conditioned = torch.cat([features, type_onehot], dim=-1)

        # Default tensors
        shop_slot = torch.zeros(batch_size, dtype=torch.long, device=device)
        bench_slot = torch.zeros(batch_size, dtype=torch.long, device=device)
        board_target = torch.zeros(batch_size, dtype=torch.long, device=device)
        board_source = torch.zeros(batch_size, dtype=torch.long, device=device)
        board_move_target = torch.zeros(batch_size, dtype=torch.long, device=device)

        # --- BUY ---
        buy_mask = action_type == 0
        if buy_mask.any():
            logits = self.shop_head(conditioned[buy_mask])
            if masks is not None:
                logits = self._mask_logits(logits, masks["shop_mask"][buy_mask])
            sampled = self._sample_categorical(logits, deterministic)
            shop_slot[buy_mask] = sampled
            dist = Categorical(logits=logits)
            total_logprob[buy_mask] += dist.log_prob(sampled)
            total_entropy[buy_mask] += dist.entropy()

        # --- MOVE BENCH ---
        move_bench_mask = action_type == 3
        if move_bench_mask.any():
            # Bench source
            logits = self.bench_head(conditioned[move_bench_mask])

            if masks is not None:
                # Máscara específica para mover unidades do banco.
                # bench_source_mask continua disponível para SELL.
                source_mask = masks.get(
                    "bench_move_source_mask",
                    masks["bench_source_mask"]
                )
                logits = self._mask_logits(
                    logits,
                    source_mask[move_bench_mask]
                )

            sampled = self._sample_categorical(logits, deterministic)
            bench_slot[move_bench_mask] = sampled
            dist = Categorical(logits=logits)
            total_logprob[move_bench_mask] += dist.log_prob(sampled)
            total_entropy[move_bench_mask] += dist.entropy()

            # Board target condicionado ao slot selecionado no banco
            logits = self.bench_to_board_head(conditioned[move_bench_mask])

            if masks is not None:
                batch_indices = torch.where(move_bench_mask)[0]

                if "bench_to_board_target_masks" in masks:
                    target_mask = masks["bench_to_board_target_masks"][
                        batch_indices,
                        sampled,
                        :
                    ]
                else:
                    # Compatibilidade com máscaras antigas.
                    target_mask = masks["board_target_mask"][move_bench_mask]

                logits = self._mask_logits(logits, target_mask)

            sampled_target = self._sample_categorical(logits, deterministic)
            board_target[move_bench_mask] = sampled_target
            dist = Categorical(logits=logits)
            total_logprob[move_bench_mask] += dist.log_prob(sampled_target)
            total_entropy[move_bench_mask] += dist.entropy()

        # --- MOVE BOARD ---
        move_board_mask = action_type == 4
        if move_board_mask.any():
            # Source
            logits = self.board_source_head(conditioned[move_board_mask])
            if masks is not None:
                logits = self._mask_logits(
                    logits,
                    masks["board_source_mask"][move_board_mask]
                )

            sampled_source = self._sample_categorical(logits, deterministic)
            board_source[move_board_mask] = sampled_source
            src_dist = Categorical(logits=logits)
            total_logprob[move_board_mask] += src_dist.log_prob(sampled_source)
            total_entropy[move_board_mask] += src_dist.entropy()

            # Target condicionado à origem selecionada
            source_onehot = F.one_hot(
                sampled_source,
                num_classes=self.action_dims[4]
            ).float()

            target_input = torch.cat(
                [conditioned[move_board_mask], source_onehot],
                dim=-1
            )
            target_logits = self.board_move_target_head(target_input)

            if masks is not None:
                full_move_masks = masks["board_move_target_masks"]
                batch_indices = torch.where(move_board_mask)[0]
                target_mask = full_move_masks[
                    batch_indices,
                    sampled_source,
                    :
                ]
                target_logits = self._mask_logits(target_logits, target_mask)

            target_sampled = self._sample_categorical(
                target_logits,
                deterministic
            )
            board_move_target[move_board_mask] = target_sampled
            target_dist = Categorical(logits=target_logits)
            total_logprob[move_board_mask] += target_dist.log_prob(target_sampled)
            total_entropy[move_board_mask] += target_dist.entropy()

        # --- SELL ---
        sell_mask = action_type == 5
        if sell_mask.any():
            logits = self.bench_head(conditioned[sell_mask])
            if masks is not None:
                # Venda continua usando a máscara original do banco.
                logits = self._mask_logits(
                    logits,
                    masks["bench_source_mask"][sell_mask]
                )

            sampled = self._sample_categorical(logits, deterministic)
            bench_slot[sell_mask] = sampled
            dist = Categorical(logits=logits)
            total_logprob[sell_mask] += dist.log_prob(sampled)
            total_entropy[sell_mask] += dist.entropy()

        actions = torch.stack([
            action_type, shop_slot, bench_slot, board_target, board_source, board_move_target
        ], dim=-1)

        value = self.value_head(features).squeeze(-1)

        return actions, total_logprob, total_entropy, value

    def evaluate_actions(self, obs, actions, masks):
        hidden = self.encode(obs)

        # Type
        type_logits = self.type_head(hidden)
        type_logits = self._mask_logits(type_logits, masks["type_mask"])
        type_dist = Categorical(logits=type_logits)
        action_type = actions[:, 0]
        total_logprob = type_dist.log_prob(action_type)
        total_entropy = type_dist.entropy()

        # Conditioning
        type_onehot = F.one_hot(action_type, num_classes=self.num_action_types).float()
        conditioned = torch.cat([hidden, type_onehot], dim=-1)

        # BUY
        buy_mask = action_type == 0
        if buy_mask.any():
            logits = self.shop_head(conditioned[buy_mask])
            logits = self._mask_logits(logits, masks["shop_mask"][buy_mask])
            dist = Categorical(logits=logits)
            total_logprob[buy_mask] += dist.log_prob(actions[buy_mask, 1])
            total_entropy[buy_mask] += dist.entropy()

        # MOVE BENCH
        move_bench_mask = action_type == 3
        if move_bench_mask.any():
            # Bench source
            logits = self.bench_head(conditioned[move_bench_mask])

            source_mask = masks.get(
                "bench_move_source_mask",
                masks["bench_source_mask"]
            )
            logits = self._mask_logits(
                logits,
                source_mask[move_bench_mask]
            )

            dist = Categorical(logits=logits)
            selected_bench_slots = actions[move_bench_mask, 2]
            total_logprob[move_bench_mask] += dist.log_prob(selected_bench_slots)
            total_entropy[move_bench_mask] += dist.entropy()

            # Target condicionado ao slot selecionado no banco
            logits = self.bench_to_board_head(conditioned[move_bench_mask])

            batch_indices = torch.where(move_bench_mask)[0]

            if "bench_to_board_target_masks" in masks:
                target_mask = masks["bench_to_board_target_masks"][
                    batch_indices,
                    selected_bench_slots,
                    :
                ]
            else:
                # Compatibilidade com máscaras antigas.
                target_mask = masks["board_target_mask"][move_bench_mask]

            logits = self._mask_logits(logits, target_mask)

            dist = Categorical(logits=logits)
            total_logprob[move_bench_mask] += dist.log_prob(
                actions[move_bench_mask, 3]
            )
            total_entropy[move_bench_mask] += dist.entropy()

        # MOVE BOARD
        move_board_mask = action_type == 4
        if move_board_mask.any():
            # Source
            logits = self.board_source_head(conditioned[move_board_mask])
            logits = self._mask_logits(
                logits,
                masks["board_source_mask"][move_board_mask]
            )
            dist = Categorical(logits=logits)
            total_logprob[move_board_mask] += dist.log_prob(
                actions[move_board_mask, 4]
            )
            total_entropy[move_board_mask] += dist.entropy()

            # Target condicionado à origem selecionada
            source_action = actions[move_board_mask, 4]
            source_onehot = F.one_hot(
                source_action,
                num_classes=self.action_dims[4]
            ).float()

            target_input = torch.cat(
                [conditioned[move_board_mask], source_onehot],
                dim=-1
            )
            target_logits = self.board_move_target_head(target_input)

            # Máscara condicional por origem
            full_move_masks = masks["board_move_target_masks"]
            batch_indices = torch.where(move_board_mask)[0]
            target_mask = full_move_masks[
                batch_indices,
                source_action,
                :
            ]
            target_logits = self._mask_logits(target_logits, target_mask)

            target_dist = Categorical(logits=target_logits)
            total_logprob[move_board_mask] += target_dist.log_prob(
                actions[move_board_mask, 5]
            )
            total_entropy[move_board_mask] += target_dist.entropy()

        # SELL
        sell_mask = action_type == 5
        if sell_mask.any():
            logits = self.bench_head(conditioned[sell_mask])
            logits = self._mask_logits(
                logits,
                masks["bench_source_mask"][sell_mask]
            )
            dist = Categorical(logits=logits)
            total_logprob[sell_mask] += dist.log_prob(actions[sell_mask, 2])
            total_entropy[sell_mask] += dist.entropy()

        value = self.value_head(hidden).squeeze(-1)
        return total_logprob, total_entropy, value