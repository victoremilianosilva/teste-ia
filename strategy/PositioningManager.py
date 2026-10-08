# strategy/PositioningManager.py

import math

from combat.CombatProfileManager import UnitRole

class PositioningManager:
    """
    📍 Gerencia o posicionamento das unidades de um jogador.

    Responsabilidades:
        - analisar posições do board
        - encontrar vizinhos
        - avaliar uma posição
        - avaliar posicionamento completo
        - considerar role da unidade
        - avaliar proteção de carries
        - avaliar frontline/backline
        - calcular estabilidade do board
        - encontrar posições melhores

    NÃO é responsabilidade:
        - mover unidades diretamente
        - reward
        - PPO
        - estratégia econômica
        - combate completo
        - shop
    """

    EMPTY = 0

    def __init__(
        self,
        rows=4,
        cols=7,
        combat_profile_mgr=None,
    ):
        self.rows = rows
        self.cols = cols

        self.board_size = (
            rows * cols
        )

        self.combat_profile_mgr = (
            combat_profile_mgr
        )

    # =============================================================
    # 📍 POSIÇÃO
    # =============================================================

    def is_valid_position(
        self,
        position,
    ):
        """Verifica se uma posição pertence ao board."""

        return (
            isinstance(position, int)
            and 0 <= position < self.board_size
        )

    def position_to_row_col(
        self,
        position,
    ):
        """Converte posição flat para linha/coluna."""

        if not self.is_valid_position(
            position
        ):
            return None, None

        return (
            position // self.cols,
            position % self.cols,
        )

    def row_col_to_position(
        self,
        row,
        col,
    ):
        """Converte linha/coluna para posição flat."""

        if not (
            0 <= row < self.rows
            and 0 <= col < self.cols
        ):
            return None

        return (
            row * self.cols
            + col
        )

    # =============================================================
    # 👥 VIZINHOS
    # =============================================================

    def get_neighbors(
        self,
        position,
        include_diagonal=True,
    ):
        """
        Retorna posições vizinhas.

        Board:

            0  1  2  3  4  5  6
            7  8  9 10 11 12 13
           14 15 16 17 18 19 20
           21 22 23 24 25 26 27
        """

        row, col = self.position_to_row_col(
            position
        )

        if row is None:
            return []

        if include_diagonal:

            directions = [
                (-1, -1),
                (-1,  0),
                (-1,  1),
                ( 0, -1),
                ( 0,  1),
                ( 1, -1),
                ( 1,  0),
                ( 1,  1),
            ]

        else:

            directions = [
                (-1, 0),
                (1, 0),
                (0, -1),
                (0, 1),
            ]

        neighbors = []

        for dr, dc in directions:

            new_row = row + dr
            new_col = col + dc

            position = (
                self.row_col_to_position(
                    new_row,
                    new_col,
                )
            )

            if position is not None:
                neighbors.append(
                    position
                )

        return neighbors

    # =============================================================
    # 🧩 UNIDADE NA POSIÇÃO
    # =============================================================

    @staticmethod
    def get_unit(
        board,
        position,
    ):
        """Retorna unidade de uma posição."""

        if board is None:
            return None

        if not (
            0 <= position < len(board)
        ):
            return None

        return board[position]

    # =============================================================
    # 🧱 ROLE
    # =============================================================

    @staticmethod
    def get_role(
        unit,
    ):
        """
        Retorna a role da unidade.

        Mantemos fallback para FIGHTER caso a unidade
        ainda não tenha role definida.
        """

        if not isinstance(
            unit,
            dict,
        ):
            return UnitRole.FIGHTER

        role = unit.get(
            "role"
        )

        if role is None:
            return UnitRole.FIGHTER

        return role

    # =============================================================
    # 🎯 AVALIAÇÃO DE UMA POSIÇÃO
    # =============================================================

    def evaluate_unit_placement(
        self,
        board,
        position,
        unit=None,
    ):
        """
        Avalia a qualidade de colocar uma unidade em determinada
        posição.

        Quanto maior, melhor.
        """

        if not self.is_valid_position(
            position
        ):
            return -999.0

        if unit is None:
            unit = self.get_unit(
                board,
                position,
            )

        if unit is None:
            return 0.0

        role = self.get_role(
            unit
        )

        row, col = (
            self.position_to_row_col(
                position
            )
        )

        score = 0.0

        # =========================================================
        # 🛡️ TANK
        # =========================================================

        if role == UnitRole.TANK:

            # Tanks preferem frontline.
            score += (
                self._frontline_score(
                    row
                )
                * 4.0
            )

            # Queremos tanks relativamente centralizados.
            score += (
                self._center_score(
                    col
                )
                * 1.5
            )

        # =========================================================
        # ⚔️ FIGHTER
        # =========================================================

        elif role == UnitRole.FIGHTER:

            score += (
                self._frontline_score(
                    row
                )
                * 2.5
            )

            score += (
                self._center_score(
                    col
                )
                * 1.0
            )

        # =========================================================
        # 💥 ASSASSIN
        # =========================================================

        elif role == UnitRole.ASSASSIN:

            # Assassins preferem posições mais avançadas,
            # mas não devem simplesmente ocupar o mesmo lugar
            # dos tanks.
            score += (
                self._assassin_score(
                    row
                )
                * 3.0
            )

            score += (
                self._edge_score(
                    col
                )
                * 1.0
            )

        # =========================================================
        # 💚 SUPPORT
        # =========================================================

        elif role == UnitRole.SUPPORT:

            # Support fica atrás e relativamente protegido.
            score += (
                self._backline_score(
                    row
                )
                * 3.0
            )

            score += (
                self._center_score(
                    col
                )
                * 1.5
            )

        # =========================================================
        # 🎯 CARRY
        # =========================================================

        elif role == UnitRole.CARRY:

            # Carry fica atrás.
            score += (
                self._backline_score(
                    row
                )
                * 4.0
            )

            # Preferência por região central protegida.
            score += (
                self._center_score(
                    col
                )
                * 2.0
            )

        # =========================================================
        # 🧱 BORDA DO TABULEIRO
        # =========================================================

        # Uma pequena penalização por ficar completamente exposto
        # em posições ruins.
        if col == 0 or col == self.cols - 1:
            if role == UnitRole.CARRY:
                score -= 0.5

        return score

    # =============================================================
    # 🛡️ FRONTLINE
    # =============================================================

    def _frontline_score(
        self,
        row,
    ):
        """
        Quanto mais próximo da frontline, maior.

        Consideramos a linha 0 como frente.

        Isso pode ser invertido facilmente caso o lado do
        tabuleiro seja representado ao contrário.
        """

        if self.rows <= 1:
            return 1.0

        return (
            (self.rows - 1 - row)
            / (self.rows - 1)
        )

    # =============================================================
    # 🏹 BACKLINE
    # =============================================================

    def _backline_score(
        self,
        row,
    ):
        """Quanto mais próximo da backline, maior."""

        if self.rows <= 1:
            return 1.0

        return (
            row
            / (self.rows - 1)
        )

    # =============================================================
    # 💥 ASSASSIN
    # =============================================================

    def _assassin_score(
        self,
        row,
    ):
        """
        Assassins ficam em região intermediária/avançada.

        Evita colocá-los automaticamente como tanks.
        """

        if self.rows <= 1:
            return 1.0

        center = (
            self.rows - 1
        ) * 0.55

        distance = abs(
            row - center
        )

        max_distance = (
            self.rows - 1
        )

        return max(
            0.0,
            1.0 - (
                distance
                / max_distance
            )
        )

    # =============================================================
    # 🎯 CENTRO
    # =============================================================

    def _center_score(
        self,
        col,
    ):
        """Quanto mais próximo do centro, maior."""

        center = (
            self.cols - 1
        ) / 2.0

        max_distance = max(
            center,
            1.0
        )

        return max(
            0.0,
            1.0 - (
                abs(col - center)
                / max_distance
            )
        )

    # =============================================================
    # ↔️ BORDA
    # =============================================================

    def _edge_score(
        self,
        col,
    ):
        """Quanto mais próximo da borda, maior."""

        if self.cols <= 1:
            return 1.0

        distance = min(
            col,
            self.cols - 1 - col,
        )

        max_distance = (
            (self.cols - 1) / 2.0
        )

        return max(
            0.0,
            1.0 - (
                distance
                / max_distance
            )
        )

    # =============================================================
    # 🧠 PROTEÇÃO
    # =============================================================

    def evaluate_protection(
        self,
        board,
        position,
    ):
        """
        Avalia proteção de uma unidade pelos vizinhos.

        Carries e supports se beneficiam mais de aliados próximos.
        """

        unit = self.get_unit(
            board,
            position,
        )

        if unit is None:
            return 0.0

        role = self.get_role(
            unit
        )

        neighbors = (
            self.get_neighbors(
                position,
                include_diagonal=True,
            )
        )

        occupied = 0
        tanks = 0

        for neighbor_position in neighbors:

            neighbor = self.get_unit(
                board,
                neighbor_position,
            )

            if neighbor is None:
                continue

            occupied += 1

            neighbor_role = (
                self.get_role(
                    neighbor
                )
            )

            if neighbor_role == UnitRole.TANK:
                tanks += 1

        score = 0.0

        if role == UnitRole.CARRY:
            score += occupied * 0.8
            score += tanks * 1.5

        elif role == UnitRole.SUPPORT:
            score += occupied * 0.6
            score += tanks * 1.0

        elif role == UnitRole.TANK:
            score += occupied * 0.2

        return score

    # =============================================================
    # ⚔️ POSICIONAMENTO COMPLETO
    # =============================================================

    def evaluate_board_positioning(
        self,
        board,
    ):
        """
        Avalia o posicionamento inteiro do board.
        """

        if board is None:
            return 0.0

        score = 0.0

        for position, unit in enumerate(
            board
        ):

            if unit is None:
                continue

            if not isinstance(
                unit,
                dict,
            ):
                continue

            score += (
                self.evaluate_unit_placement(
                    board,
                    position,
                    unit,
                )
            )

            score += (
                self.evaluate_protection(
                    board,
                    position,
                )
            )

        return score

    # =============================================================
    # 🔎 MELHOR POSIÇÃO
    # =============================================================

    def find_best_position(
        self,
        board,
        unit,
        candidate_positions=None,
    ):
        """
        Encontra a melhor posição para uma unidade.

        Não move a unidade.

        Apenas responde qual posição seria melhor.
        """

        if candidate_positions is None:

            candidate_positions = [
                position
                for position, current_unit
                in enumerate(board)
                if current_unit is None
            ]

        best_position = None
        best_score = -math.inf

        for position in candidate_positions:

            if not self.is_valid_position(
                position
            ):
                continue

            if board[position] is not None:
                continue

            # Simula temporariamente.
            board[position] = unit

            score = (
                self.evaluate_unit_placement(
                    board,
                    position,
                    unit,
                )
            )

            score += (
                self.evaluate_protection(
                    board,
                    position,
                )
            )

            board[position] = None

            if score > best_score:

                best_score = score
                best_position = position

        return (
            best_position,
            best_score,
        )

    # =============================================================
    # 🔄 MELHOR TROCA
    # =============================================================

    def find_best_swap(
        self,
        board,
        source_position,
        candidate_positions=None,
    ):
        """
        Encontra a melhor posição para mover/trocar uma unidade.

        Não executa a troca.
        """

        if not self.is_valid_position(
            source_position
        ):
            return None, -math.inf

        unit = board[source_position]

        if unit is None:
            return None, -math.inf

        if candidate_positions is None:

            candidate_positions = [
                position
                for position in range(
                    len(board)
                )
                if position != source_position
            ]

        current_score = (
            self.evaluate_unit_placement(
                board,
                source_position,
                unit,
            )
        )

        best_position = None
        best_delta = 0.0

        for target_position in candidate_positions:

            if not self.is_valid_position(
                target_position
            ):
                continue

            if target_position == source_position:
                continue

            target_unit = board[
                target_position
            ]

            # -----------------------------------------------------
            # Simula troca
            # -----------------------------------------------------

            board[
                source_position
            ] = target_unit

            board[
                target_position
            ] = unit

            new_score = (
                self.evaluate_unit_placement(
                    board,
                    target_position,
                    unit,
                )
            )

            new_score += (
                self.evaluate_protection(
                    board,
                    target_position,
                )
            )

            # Restaura.
            board[
                source_position
            ] = unit

            board[
                target_position
            ] = target_unit

            delta = (
                new_score
                - current_score
            )

            if delta > best_delta:

                best_delta = delta
                best_position = (
                    target_position
                )

        return (
            best_position,
            best_delta,
        )

    # =============================================================
    # 🧱 ESTABILIDADE
    # =============================================================

    def get_board_signature(
        self,
        board,
    ):
        """
        Cria uma assinatura simples do posicionamento.

        Usada pelo AntiLoopManager.

        UUID é utilizado quando disponível para diferenciar
        unidades individuais.
        """

        signature = []

        for position, unit in enumerate(
            board
        ):

            if unit is None:
                signature.append(
                    (
                        position,
                        None,
                    )
                )
                continue

            signature.append(
                (
                    position,
                    unit.get(
                        "uuid",
                        unit.get(
                            "id"
                        ),
                    ),
                )
            )

        return tuple(
            signature
        )

    def is_board_stable(
        self,
        board,
        tolerance=0.01,
    ):
        """
        Determina se o board parece estar estável.

        A ideia inicial é verificar se não existem movimentos
        claramente melhores.
        """

        for source_position, unit in enumerate(
            board
        ):

            if unit is None:
                continue

            best_position, delta = (
                self.find_best_swap(
                    board,
                    source_position,
                )
            )

            if (
                best_position is not None
                and delta > tolerance
            ):
                return False

        return True

    # =============================================================
    # 📊 SCORE NORMALIZADO
    # =============================================================

    def get_normalized_positioning_score(
        self,
        board,
    ):
        """
        Retorna score de posicionamento normalizado.

        Útil para observation/reward.
        """

        if board is None:
            return 0.0

        units = [
            unit
            for unit in board
            if unit is not None
        ]

        if not units:
            return 0.0

        raw_score = (
            self.evaluate_board_positioning(
                board
            )
        )

        max_score = (
            len(units) * 10.0
        )

        if max_score <= 0:
            return 0.0

        return max(
            -1.0,
            min(
                1.0,
                raw_score / max_score
            )
        )

    def reset(self):
        """
        Reseta o estado interno do PositioningManager.

        Atualmente o manager não mantém estado persistente,
        então o reset existe apenas para manter a interface
        compatível com o MiniTFTEnv.
        """
        return None

    # =============================================================
    # 🐛 DEBUG
    # =============================================================

    def debug_board(
        self,
        board,
    ):
        """Mostra o board com roles."""

        print(
            "\n========== POSITIONING =========="
        )

        for row in range(
            self.rows
        ):

            values = []

            for col in range(
                self.cols
            ):

                position = (
                    self.row_col_to_position(
                        row,
                        col,
                    )
                )

                unit = board[
                    position
                ]

                if unit is None:
                    values.append(
                        "[ . ]"
                    )
                    continue

                role = self.get_role(
                    unit
                )

                role_names = {
                    UnitRole.TANK: "T",
                    UnitRole.CARRY: "C",
                    UnitRole.SUPPORT: "S",
                    UnitRole.FIGHTER: "F",
                    UnitRole.ASSASSIN: "A",
                }

                role_name = (
                    role_names.get(
                        role,
                        "?",
                    )
                )

                values.append(
                    f"[{role_name}]"
                )

            print(
                " ".join(values)
            )

        print(
            "================================="
        )