# units/BoardManager.py

from copy import deepcopy


class BoardManager:
    """
    🧱 Gerencia exclusivamente o tabuleiro de um jogador.

    Responsabilidades:
        - armazenar o board
        - validar posições
        - adicionar unidades
        - remover unidades
        - mover unidades
        - trocar unidades
        - localizar unidades
        - consultar capacidade

    NÃO é responsabilidade deste manager:
        - reward
        - estratégia
        - posicionamento inteligente
        - combate
        - UnitPool
        - gold
        - HP
        - PPO / máscaras
    """

    def __init__(self, rows=4, cols=7):
        self.rows = rows
        self.cols = cols
        self.size = rows * cols

        self.board = self._create_empty_board()

    # =============================================================
    # 🧱 ESTRUTURA
    # =============================================================

    def _create_empty_board(self):
        """
        Cria um tabuleiro vazio.

        O projeto atual usa uma lista flat com 28 posições,
        então mantemos esse formato para não quebrar o estado
        utilizado pela policy.
        """

        return [None] * self.size

    def reset(self):
        """
        Limpa completamente o tabuleiro.
        """

        self.board = self._create_empty_board()

    # =============================================================
    # 📍 POSIÇÕES
    # =============================================================

    def is_valid_position(self, position):
        """
        Verifica se uma posição pertence ao board.
        """

        return (
            isinstance(position, int)
            and 0 <= position < self.size
        )

    def position_to_row_col(self, position):
        """
        Converte posição flat para linha/coluna.

        Exemplo:

            posição 0  -> (0, 0)
            posição 7  -> (1, 0)
            posição 27 -> (3, 6)
        """

        if not self.is_valid_position(position):
            raise ValueError(
                f"Posição inválida: {position}"
            )

        row = position // self.cols
        col = position % self.cols

        return row, col

    def row_col_to_position(self, row, col):
        """
        Converte linha/coluna para posição flat.
        """

        if not (
            isinstance(row, int)
            and isinstance(col, int)
        ):
            raise ValueError(
                "Linha e coluna precisam ser inteiros."
            )

        if not (
            0 <= row < self.rows
            and 0 <= col < self.cols
        ):
            raise ValueError(
                f"Posição inválida: ({row}, {col})"
            )

        return row * self.cols + col

    # =============================================================
    # 🔎 CONSULTA
    # =============================================================

    def get_unit(self, position):
        """
        Retorna a unidade naquela posição.

        Retorna None caso esteja vazia.
        """

        if not self.is_valid_position(position):
            return None

        return self.board[position]

    def is_empty(self, position):
        """
        Verifica se uma posição está vazia.
        """

        if not self.is_valid_position(position):
            return False

        return self.board[position] is None

    def get_occupied_positions(self):
        """
        Retorna todas as posições ocupadas.
        """

        return [
            index
            for index, unit in enumerate(self.board)
            if unit is not None
        ]

    def get_empty_positions(self):
        """
        Retorna todas as posições vazias.
        """

        return [
            index
            for index, unit in enumerate(self.board)
            if unit is None
        ]

    def get_units(self):
        """
        Retorna todas as unidades atualmente no board.

        Mantém a referência das unidades.
        """

        return [
            unit
            for unit in self.board
            if unit is not None
        ]

    def get_unit_count(self):
        """
        Quantidade atual de unidades no board.
        """

        return sum(
            unit is not None
            for unit in self.board
        )

    def get_free_slots(self):
        """
        Quantidade de espaços livres.
        """

        return self.size - self.get_unit_count()

    def is_full(self):
        """
        Verifica se o board está cheio.
        """

        return self.get_unit_count() >= self.size

    # =============================================================
    # ➕ ADICIONAR
    # =============================================================

    def add_unit(self, unit, position):
        """
        Coloca uma unidade em uma posição vazia.

        Não faz cópia da unidade.

        Retorna:
            True  -> sucesso
            False -> posição inválida/ocupada
        """

        if unit is None:
            return False

        if not self.is_valid_position(position):
            return False

        if not self.is_empty(position):
            return False

        self.board[position] = unit

        return True

    # =============================================================
    # ➖ REMOVER
    # =============================================================

    def remove_unit(self, position):
        """
        Remove e retorna a unidade de determinada posição.

        Retorna None caso esteja vazia.
        """

        if not self.is_valid_position(position):
            return None

        unit = self.board[position]

        if unit is None:
            return None

        self.board[position] = None

        return unit

    # =============================================================
    # 🔄 MOVER
    # =============================================================

    def move_unit(self, source, target):
        """
        Move uma unidade entre duas posições.

        A posição de destino precisa estar vazia.

        Retorna:
            True  -> movimento realizado
            False -> movimento inválido
        """

        if not self.is_valid_position(source):
            return False

        if not self.is_valid_position(target):
            return False

        if source == target:
            return False

        unit = self.board[source]

        if unit is None:
            return False

        if self.board[target] is not None:
            return False

        self.board[target] = unit
        self.board[source] = None

        return True

    # =============================================================
    # 🔁 TROCAR
    # =============================================================

    def swap_units(self, position_a, position_b):
        """
        Troca duas unidades de posição.

        Uma ou ambas podem estar vazias.

        Isso é útil para:
            - reposicionamento
            - troca board ↔ board
            - heurísticas de posicionamento
        """

        if not self.is_valid_position(position_a):
            return False

        if not self.is_valid_position(position_b):
            return False

        if position_a == position_b:
            return False

        self.board[position_a], self.board[position_b] = (
            self.board[position_b],
            self.board[position_a],
        )

        return True

    # =============================================================
    # 🔎 LOCALIZAR UNIDADE
    # =============================================================

    def find_unit_position(self, unit):
        """
        Procura a posição de uma determinada instância de unidade.

        Primeiro tenta identidade do objeto.

        Isso é importante porque duas unidades podem possuir
        o mesmo campeão, estrela e custo, mas UUID diferente.
        """

        if unit is None:
            return None

        for position, board_unit in enumerate(self.board):
            if board_unit is unit:
                return position

        # Fallback pelo UUID
        unit_uuid = unit.get("uuid")

        if unit_uuid is None:
            return None

        for position, board_unit in enumerate(self.board):
            if (
                board_unit is not None
                and board_unit.get("uuid") == unit_uuid
            ):
                return position

        return None

    def find_units_by_id(self, unit_id):
        """
        Retorna todas as unidades de determinado campeão.
        """

        return [
            unit
            for unit in self.board
            if (
                unit is not None
                and unit.get("id") == unit_id
            )
        ]

    # =============================================================
    # 📋 SNAPSHOT
    # =============================================================

    def get_snapshot(self):
        """
        Retorna uma cópia do estado do board.

        Útil para:
            - simulações
            - avaliação
            - debug
            - comparação antes/depois

        Não deve ser usada para substituir o board real.
        """

        return deepcopy(self.board)

    # =============================================================
    # 🔢 REPRESENTAÇÕES
    # =============================================================

    def get_position_signature(self):
        """
        Cria uma assinatura simples da posição das unidades.

        Útil para detectar:
            A -> B -> A

        O AntiLoopManager poderá usar isso depois.

        Aqui não existe nenhuma regra de anti-loop.
        Apenas fornecemos a informação.
        """

        signature = []

        for unit in self.board:
            if unit is None:
                signature.append(None)
                continue

            signature.append(
                (
                    unit.get("id"),
                    unit.get("star", 1),
                    unit.get("uuid"),
                )
            )

        return tuple(signature)

    def get_board_id_signature(self):
        """
        Assinatura mais simples do board.

        Diferente de get_position_signature(), não utiliza UUID.

        Útil quando queremos saber se a composição/posição dos
        campeões mudou independentemente da identidade da cópia.
        """

        return tuple(
            (
                unit.get("id"),
                unit.get("star", 1),
            )
            if unit is not None
            else None
            for unit in self.board
        )

    # =============================================================
    # 🧹 VALIDAÇÃO
    # =============================================================

    def validate(self):
        """
        Faz uma validação básica da estrutura do board.

        Retorna:
            True  -> estrutura válida
            False -> problema encontrado
        """

        if not isinstance(self.board, list):
            return False

        if len(self.board) != self.size:
            return False

        return True

    # =============================================================
    # 🐛 DEBUG
    # =============================================================

    def debug_print(self):
        """
        Imprime o board de maneira simples para debug.
        """

        print("\n--- BOARD ---")

        for row in range(self.rows):
            values = []

            for col in range(self.cols):
                position = self.row_col_to_position(
                    row,
                    col
                )

                unit = self.board[position]

                if unit is None:
                    values.append("[ . ]")
                else:
                    name = unit.get("name", "?")
                    values.append(
                        f"[ {name[:3]} ]"
                    )

            print(" ".join(values))

        print("-------------")