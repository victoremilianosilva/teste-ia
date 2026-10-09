# 🤖 ai/ActionMaskManager.py
#
# Responsável por:
# - Gerar máscaras das ações válidas
# - Impedir ações impossíveis
# - Impedir movimentos inúteis/loops
# - Garantir que PASS continue disponível
#
# Action dimensions:
# [7, 5, 9, 28, 28, 28]
#
# 0 = action type
# 1 = shop slot
# 2 = bench slot
# 3 = board target
# 4 = board source
# 5 = conditioned board target

from enum import IntEnum

import numpy as np


class ActionType(IntEnum):
    BUY = 0
    REROLL = 1
    BUY_XP = 2
    MOVE_BENCH = 3
    MOVE_BOARD = 4
    SELL = 5
    PASS = 6


class ActionMaskManager:

    def __init__(
        self,
        board_manager,
        bench_manager,
        shop_manager,
        economy_manager,
        composition_manager,
        positioning_manager,
        anti_loop_manager,
        unit_manager,
    ):
        self.board_manager = board_manager
        self.bench_manager = bench_manager
        self.shop_manager = shop_manager
        self.economy_manager = economy_manager
        self.composition_manager = composition_manager
        self.positioning_manager = positioning_manager
        self.anti_loop_manager = anti_loop_manager
        self.unit_manager = unit_manager

        self.board_size = 28
        self.bench_size = 9
        self.shop_size = 5

    # ============================================================
    # 🔹 API PRINCIPAL
    # ============================================================

    def get_action_masks(self, is_alive=True):
        """
        Retorna as 6 máscaras usadas pela política.

        Formato:
            [
                type_mask,
                shop_mask,
                bench_mask,
                board_target_mask,
                board_source_mask,
                conditioned_board_target_mask
            ]
        """

        type_mask = self.get_type_mask(is_alive=is_alive)
        shop_mask = self.get_shop_mask()
        bench_mask = self.get_bench_source_mask()
        board_target_mask = self.get_board_target_mask()
        board_source_mask = self.get_board_source_mask()
        conditioned_target_mask = self.get_conditioned_board_target_mask()

        return [
            type_mask,
            shop_mask,
            bench_mask,
            board_target_mask,
            board_source_mask,
            conditioned_target_mask,
        ]

    # ============================================================
    # 🔹 ACTION TYPE
    # ============================================================

    def get_type_mask(self, is_alive=True):
        """
        Máscara da primeira cabeça:

        [BUY, REROLL, BUY_XP, MOVE_BENCH,
         MOVE_BOARD, SELL, PASS]
        """

        mask = np.zeros(7, dtype=np.float32)

        # ☠️ Jogador morto não pode executar ações.
        # PASS continua válido para evitar distribuição inválida.
        if not is_alive:
            mask[ActionType.PASS] = 1.0
            return mask

        # 🛒 BUY
        if self._has_valid_buy():
            mask[ActionType.BUY] = 1.0

        # 🔄 REROLL
        if self._has_valid_reroll():
            mask[ActionType.REROLL] = 1.0

        # ⭐ BUY XP
        if self._has_valid_buy_xp():
            mask[ActionType.BUY_XP] = 1.0

        # ↔️ BENCH -> BOARD
        if self._has_valid_bench_move():
            mask[ActionType.MOVE_BENCH] = 1.0

        # 🔀 BOARD -> BOARD
        if self._has_valid_board_move():
            mask[ActionType.MOVE_BOARD] = 1.0

        # 💰 SELL
        if self._has_valid_sell():
            mask[ActionType.SELL] = 1.0

        # ⏭️ PASS SEMPRE disponível
        mask[ActionType.PASS] = 1.0

        return mask

    # ============================================================
    # 🛒 BUY
    # ============================================================

    def get_shop_mask(self):
        """
        Máscara dos 5 slots da loja.
        """

        mask = np.zeros(self.shop_size, dtype=np.float32)

        shop = self._get_shop()

        for slot in range(min(len(shop), self.shop_size)):
            unit = shop[slot]

            if unit is None:
                continue

            cost = unit.get("cost", 1)

            # 💰 Precisa ter ouro
            if not self.economy_manager.can_spend(cost):
                continue

            # 🪑 Precisa ter espaço no bench
            if not self.bench_manager.has_free_slot():
                continue

            mask[slot] = 1.0

        # Nunca deixar a máscara completamente inválida.
        if not mask.any():
            mask[0] = 1.0

        return mask

    def _has_valid_buy(self):
        shop_mask = self.get_shop_mask()

        # Se não existe espaço no bench, nenhum BUY é possível.
        if not self.bench_manager.has_free_slot():
            return False

        shop = self._get_shop()

        for slot in range(min(len(shop), self.shop_size)):
            if shop[slot] is None:
                continue

            unit = shop[slot]
            cost = unit.get("cost", 1)

            if self.economy_manager.can_spend(cost):
                return True

        return False

    # ============================================================
    # 🔄 REROLL
    # ============================================================

    def _has_valid_reroll(self):
        try:
            return self.economy_manager.can_spend(2)
        except Exception:
            return False

    # ============================================================
    # ⭐ BUY XP
    # ============================================================

    def _has_valid_buy_xp(self):
        try:
            return self.economy_manager.can_buy_xp()
        except Exception:
            return False

    # ============================================================
    # 🪑 BENCH
    # ============================================================

    def get_bench_source_mask(self):
        """
        Máscara dos 9 slots do bench.

        Usada principalmente para:
            MOVE_BENCH
            SELL
        """

        mask = np.zeros(self.bench_size, dtype=np.float32)

        bench = self._get_bench()

        for slot in range(min(len(bench), self.bench_size)):
            unit = bench[slot]

            if unit is None:
                continue

            mask[slot] = 1.0

        # Evita máscara inválida.
        if not mask.any():
            mask[0] = 1.0

        return mask

    def _has_valid_sell(self):
        bench = self._get_bench()

        for unit in bench:
            if unit is not None:
                return True

        return False

    # ============================================================
    # 🪑 -> BOARD
    # ============================================================

    def get_board_target_mask(self):
        """
        União dos destinos válidos para MOVE_BENCH.
        A política usará a máscara condicionada à origem
        selecionada para filtrar os destinos de verdade.
        """
        mask = np.zeros(self.board_size, dtype=np.float32)
        bench = self._get_bench()

        if self._has_free_board_slot():
            empty_positions = self.board_manager.get_empty_positions()

            for slot, unit in enumerate(bench[:self.bench_size]):
                if unit is None:
                    continue

                for target in empty_positions:
                    if self._is_valid_bench_board_move(slot, target):
                        mask[target] = 1.0

        # Evita uma distribuição vazia nas cabeças auxiliares.
        if not mask.any():
            mask[0] = 1.0

        return mask


    def get_bench_to_board_target_mask(self, bench_slot):
        """
        Destinos válidos para uma origem específica do banco.
        """
        mask = np.zeros(self.board_size, dtype=np.float32)
        bench = self._get_bench()

        if not (0 <= bench_slot < min(len(bench), self.bench_size)):
            mask[0] = 1.0
            return mask

        if bench[bench_slot] is None or not self._has_free_board_slot():
            mask[0] = 1.0
            return mask

        for target in self.board_manager.get_empty_positions():
            if self._is_valid_bench_board_move(bench_slot, target):
                mask[target] = 1.0

        if not mask.any():
            mask[0] = 1.0

        return mask
    
    def _has_valid_bench_move(self):
        """
        Existe alguma unidade no bench que possa entrar no board?
        """

        if not self._has_free_board_slot():
            return False

        bench = self._get_bench()

        for slot, unit in enumerate(bench):
            if unit is None:
                continue

            for target in self.board_manager.get_empty_positions():

                if self._is_valid_bench_board_move(
                    bench_slot=slot,
                    target=target,
                ):
                    return True

        return False

    def _is_valid_bench_board_move(self, bench_slot, target):
        bench = self._get_bench()

        if bench_slot < 0 or bench_slot >= len(bench):
            return False

        unit = bench[bench_slot]

        if unit is None:
            return False

        if not self._is_valid_board_position(target):
            return False

        # 🚫 Anti-loop
        try:
            if self.anti_loop_manager.should_block_move(
                move_type="bench_to_board",
                source=bench_slot,
                target=target,
                unit=unit,
            ):
                return False
        except Exception:
            pass

        return True

    # ============================================================
    # 🔀 BOARD -> BOARD
    # ============================================================

    def get_board_source_mask(self):
        """
        Máscara das origens do tabuleiro que possuem
        pelo menos um destino real válido.
        """
        mask = np.zeros(self.board_size, dtype=np.float32)

        for source in range(self.board_size):
            board_target_mask = self.get_board_move_target_mask(source)

            # O fallback [0] não conta como destino real
            # quando a origem não possui movimento válido.
            board = self._get_board()
            if source >= len(board) or board[source] is None:
                continue

            if any(
                target != source and board_target_mask[target] > 0
                for target in range(self.board_size)
            ):
                mask[source] = 1.0

        # Fallback técnico para a distribuição categórica.
        # A ação MOVE_BOARD precisa continuar desabilitada
        # se não existir nenhuma origem válida.
        if not mask.any():
            mask[0] = 1.0

        return mask

    def get_conditioned_board_target_mask(self):
        """
        Destinos para MOVE_BOARD.

        Aqui usamos o board source atual para decidir os destinos.
        Como a política é autoregressiva, essa máscara é refinada
        posteriormente pelo source selecionado.
        """

        mask = np.zeros(self.board_size, dtype=np.float32)

        board = self._get_board()

        occupied = [
            index
            for index, unit in enumerate(board)
            if unit is not None
        ]

        # Precisa existir pelo menos 2 unidades
        # para fazer uma troca significativa.
        if len(occupied) < 2:
            mask[0] = 1.0
            return mask

        for source in occupied:

            for target in range(self.board_size):

                if source == target:
                    continue

                if self._is_valid_board_move(source, target):
                    mask[target] = 1.0

        if not mask.any():
            mask[0] = 1.0

        return mask

    def _is_valid_board_move(self, source, target):
        board = self._get_board()

        if source < 0 or source >= len(board):
            return False

        if target < 0 or target >= len(board):
            return False

        if source == target:
            return False

        source_unit = board[source]

        if source_unit is None:
            return False

        target_unit = board[target]

        # ========================================================
        # 🔁 Swap
        # ========================================================

        if target_unit is not None:

            try:
                if self.anti_loop_manager.should_block_move(
                    move_type="board_swap",
                    source=source,
                    target=target,
                    unit=source_unit,
                ):
                    return False
            except Exception:
                pass

            return True

        # ========================================================
        # 📦 Movimento para espaço vazio
        # ========================================================

        try:
            if self.anti_loop_manager.should_block_move(
                move_type="board_move",
                source=source,
                target=target,
                unit=source_unit,
            ):
                return False
        except Exception:
            pass

        return True

    def _has_valid_board_move(self):
        """
        Verifica se existe pelo menos um movimento BOARD -> BOARD
        que realmente faça sentido.

        Não basta existir uma troca.
        O AntiLoopManager precisa poder bloquear movimentos
        repetitivos.
        """

        board = self._get_board()

        occupied = [
            index
            for index, unit in enumerate(board)
            if unit is not None
        ]

        if len(occupied) < 2:
            return False

        for source in occupied:

            for target in range(self.board_size):

                if source == target:
                    continue

                if self._is_valid_board_move(source, target):
                    return True

        return False

    # ============================================================
    # 🧠 MOVIMENTO CONDICIONADO
    # ============================================================

    def get_board_move_target_mask(self, source):
        """
        Retorna os destinos válidos para uma origem específica.

        Isso é importante porque a política possui heads
        autoregressivas:

            source -> target
        """

        mask = np.zeros(self.board_size, dtype=np.float32)

        if source < 0 or source >= self.board_size:
            mask[0] = 1.0
            return mask

        board = self._get_board()

        if board[source] is None:
            mask[0] = 1.0
            return mask

        for target in range(self.board_size):

            if target == source:
                continue

            if self._is_valid_board_move(source, target):
                mask[target] = 1.0

        if not mask.any():
            mask[0] = 1.0

        return mask

    def get_bench_move_source_mask(self):
        """
        Máscara exclusiva das unidades do banco que podem
        entrar no tabuleiro em pelo menos uma posição válida.

        Diferente de get_bench_source_mask(), esta máscara
        NÃO é usada para vender unidades.
        """
        mask = np.zeros(self.bench_size, dtype=np.float32)
        bench = self._get_bench()

        if self._has_free_board_slot():
            empty_positions = self.board_manager.get_empty_positions()

            for slot, unit in enumerate(bench[:self.bench_size]):
                if unit is None:
                    continue

                for target in empty_positions:
                    if self._is_valid_bench_board_move(slot, target):
                        mask[slot] = 1.0
                        break

        # Fallback técnico: não representa um movimento válido.
        # MOVE_BENCH precisa estar desabilitado se não houver
        # nenhuma origem real válida.
        if not mask.any():
            mask[0] = 1.0

        return mask

    # ============================================================
    # 🔍 HELPERS
    # ============================================================

    def _get_board(self):
        board = getattr(self.board_manager, "board", None)

        if board is None:
            return [None] * self.board_size

        return board

    def _get_bench(self):
        bench = getattr(self.bench_manager, "bench", None)

        if bench is None:
            return [None] * self.bench_size

        return bench

    def _get_shop(self):
        try:
            return self.shop_manager.get_shop()
        except Exception:
            shop = getattr(self.shop_manager, "shop", None)

            if shop is None:
                return [None] * self.shop_size

            return shop

    def _has_free_board_slot(self):
        try:
            return len(self.board_manager.get_empty_positions()) > 0
        except Exception:
            return any(unit is None for unit in self._get_board())

    def _is_valid_board_position(self, position):
        try:
            return self.board_manager.is_valid_position(position)
        except Exception:
            return 0 <= position < self.board_size

    # ============================================================
    # 🧪 DEBUG
    # ============================================================

    def debug_print(self, is_alive=True):
        masks = self.get_action_masks(is_alive=is_alive)

        print("\n========== ACTION MASK ==========")

        print(
            "TYPE:",
            [
                ActionType(i).name
                if value > 0
                else "X"
                for i, value in enumerate(masks[0])
            ]
        )

        print("SHOP :", np.where(masks[1] > 0)[0].tolist())
        print("BENCH:", np.where(masks[2] > 0)[0].tolist())
        print("BOARD TARGET:", np.where(masks[3] > 0)[0].tolist())
        print("BOARD SOURCE:", np.where(masks[4] > 0)[0].tolist())
        print(
            "CONDITIONED TARGET:",
            np.where(masks[5] > 0)[0].tolist()
        )

        print("=================================")