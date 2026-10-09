# ai/AntiLoopManager.py

from collections import deque


class AntiLoopManager:
    """
    🔄 Impede a IA de ficar repetindo movimentos inúteis.

    Responsabilidades:
        - guardar histórico de posições
        - detectar repetição de board
        - detectar movimento inverso
        - detectar oscilação A -> B -> A
        - bloquear movimentos recentes
        - detectar loops de bench <-> board
        - detectar swaps repetitivos

    NÃO é responsabilidade:
        - escolher estratégia
        - calcular reward
        - executar movimento
        - criar action mask
        - combate
    """

    def __init__(
        self,
        history_size=20,
        blocked_move_size=10,
        loop_threshold=2,
    ):
        self.history_size = history_size
        self.blocked_move_size = (
            blocked_move_size
        )
        self.loop_threshold = loop_threshold

        self.reset()

    # =============================================================
    # 🔄 RESET
    # =============================================================

    def reset(self):
        """Reseta todo o histórico."""

        self.position_history = deque(
            maxlen=self.history_size
        )

        self.move_history = deque(
            maxlen=self.history_size
        )

        self.blocked_moves = deque(
            maxlen=self.blocked_move_size
        )

        self.state_visits = {}

        self.last_board_signature = None

        self.last_move = None

    # =============================================================
    # 📸 BOARD SIGNATURE
    # =============================================================

    def make_board_signature(
        self,
        board,
        bench=None,
    ):
        """
        Cria uma assinatura do estado de posicionamento.

        IMPORTANTE:

        UUID é preferido porque identifica uma unidade individual.

        Caso UUID não exista, usamos:
            id + star
        """

        board_signature = []

        for position, unit in enumerate(
            board or []
        ):

            if unit is None:
                board_signature.append(
                    (
                        position,
                        None,
                    )
                )
                continue

            board_signature.append(
                (
                    position,
                    self._unit_identity(
                        unit
                    ),
                )
            )

        bench_signature = []

        for position, unit in enumerate(
            bench or []
        ):

            if unit is None:
                bench_signature.append(
                    (
                        position,
                        None,
                    )
                )
                continue

            bench_signature.append(
                (
                    position,
                    self._unit_identity(
                        unit
                    ),
                )
            )

        return (
            tuple(board_signature),
            tuple(bench_signature),
        )

    @staticmethod
    def _unit_identity(
        unit,
    ):
        """Identidade estável de uma unidade."""

        if not isinstance(
            unit,
            dict,
        ):
            return None

        uuid = unit.get(
            "uuid"
        )

        if uuid is not None:
            return (
                "uuid",
                uuid,
            )

        return (
            "unit",
            unit.get("id"),
            unit.get("star", 1),
        )

    # =============================================================
    # 📥 REGISTRAR ESTADO
    # =============================================================

    def register_state(
        self,
        board,
        bench=None,
    ):
        """
        Registra o estado atual do board/bench.

        Retorna:

            {
                "signature": ...,
                "repeated": bool,
                "visits": int
            }
        """

        signature = (
            self.make_board_signature(
                board,
                bench,
            )
        )

        self.position_history.append(
            signature
        )

        visits = (
            self.state_visits.get(
                signature,
                0
            )
            + 1
        )

        self.state_visits[
            signature
        ] = visits

        repeated = (
            visits >= self.loop_threshold
        )

        self.last_board_signature = (
            signature
        )

        return {
            "signature": signature,
            "repeated": repeated,
            "visits": visits,
        }

    # =============================================================
    # 🔄 REGISTRAR MOVIMENTO
    # =============================================================

    def register_move(
        self,
        move_type,
        source,
        target,
        unit=None,
    ):
        """
        Registra um movimento.

        Exemplo:

            MOVE_BENCH
            source=2
            target=17
        """

        move = (
            move_type,
            source,
            target,
            self._unit_identity(
                unit
            ),
        )

        self.move_history.append(
            move
        )

        self.last_move = move

        return move

    # =============================================================
    # 🚫 MOVIMENTO BLOQUEADO
    # =============================================================

    def block_move(
        self,
        move_type,
        source,
        target,
        unit=None,
    ):
        """
        Bloqueia um movimento específico.
        """

        key = self.make_move_key(
            move_type,
            source,
            target,
            unit,
        )

        self.blocked_moves.append(
            key
        )

        return key

    # =============================================================
    # 🔑 MOVE KEY
    # =============================================================

    def make_move_key(
        self,
        move_type,
        source,
        target,
        unit=None,
    ):
        """Cria uma chave estável para um movimento."""

        return (
            move_type,
            source,
            target,
            self._unit_identity(
                unit
            ),
        )

    # =============================================================
    # 🚫 VERIFICAR BLOQUEIO
    # =============================================================

    def is_move_blocked(
        self,
        move_type,
        source,
        target,
        unit=None,
    ):
        """
        Verifica se determinado movimento foi bloqueado.
        """

        key = self.make_move_key(
            move_type,
            source,
            target,
            unit,
        )

        return key in self.blocked_moves

    # =============================================================
    # 🔁 MOVIMENTO INVERSO
    # =============================================================

    def is_reverse_move(
        self,
        move_type,
        source,
        target,
        unit=None,
    ):
        """
        Detecta:

            A -> B
            B -> A

        para a mesma unidade.
        """

        if not self.last_move:
            return False

        last_type, last_source, last_target, last_unit = (
            self.last_move
        )

        current_unit = (
            self._unit_identity(
                unit
            )
        )

        if last_unit != current_unit:
            return False

        if last_type != move_type:
            return False

        return (
            last_source == target
            and last_target == source
        )

    # =============================================================
    # 🔄 OSCILAÇÃO
    # =============================================================

    def is_oscillating(
        self,
        unit,
        source,
        target,
    ):
        """
        Detecta padrões como:

            A -> B
            B -> A
            A -> B

        """

        identity = (
            self._unit_identity(
                unit
            )
        )

        if len(
            self.move_history
        ) < 2:
            return False

        recent = list(
            self.move_history
        )[-4:]

        movement_pairs = []

        for move in recent:

            move_type, src, dst, move_unit = (
                move
            )

            if move_unit != identity:
                continue

            movement_pairs.append(
                (
                    src,
                    dst,
                )
            )

        if len(
            movement_pairs
        ) < 2:
            return False

        # ---------------------------------------------------------
        # Último movimento
        # ---------------------------------------------------------

        if movement_pairs[-1] != (
            source,
            target,
        ):
            return False

        # ---------------------------------------------------------
        # Procura A -> B -> A
        # ---------------------------------------------------------

        for index in range(
            len(movement_pairs) - 1
        ):

            first = (
                movement_pairs[index]
            )

            second = (
                movement_pairs[index + 1]
            )

            if (
                first[0] == second[1]
                and first[1] == second[0]
            ):
                return True

        return False

    # =============================================================
    # 🔁 BENCH <-> BOARD
    # =============================================================
    
    def is_bench_board_loop(self, unit):
        """
        Detecta alternância entre banco e tabuleiro
        para a mesma unidade, independentemente do
        padrão de nomenclatura utilizado.
        """

        identity = self._unit_identity(unit)

        recent = list(self.move_history)[-6:]

        if len(recent) < 2:
            return False

        # Normaliza os nomes usados pelo ambiente e
        # os nomes alternativos usados pelo AntiLoopManager.
        move_aliases = {
            "MOVE_BENCH_TO_BOARD": "bench_to_board",
            "bench_to_board": "bench_to_board",
            "MOVE_BOARD_TO_BENCH": "board_to_bench",
            "board_to_bench": "board_to_bench",
        }

        relevant = []

        for move in recent:
            move_type, source, target, move_unit = move

            # Considera somente a mesma unidade.
            if move_unit != identity:
                continue

            normalized_type = move_aliases.get(move_type)

            # Ignora movimentos que não envolvem banco/tabuleiro.
            if normalized_type is None:
                continue

            relevant.append(normalized_type)

        if len(relevant) < 2:
            return False

        # Detecta movimentos alternados:
        # banco -> tabuleiro -> banco, ou vice-versa.
        for previous, current in zip(relevant, relevant[1:]):
            if previous != current:
                return True

        return False

    # =============================================================
    # 🧠 ESTADO JÁ VISITADO
    # =============================================================

    def was_state_seen(
        self,
        board,
        bench=None,
    ):
        """
        Verifica se o estado já apareceu anteriormente.
        """

        signature = (
            self.make_board_signature(
                board,
                bench,
            )
        )

        return signature in (
            self.state_visits
        )

    def get_state_visits(
        self,
        board,
        bench=None,
    ):
        """Retorna quantidade de vezes que o estado apareceu."""

        signature = (
            self.make_board_signature(
                board,
                bench,
            )
        )

        return self.state_visits.get(
            signature,
            0
        )

    # =============================================================
    # 🧮 AVALIAÇÃO DE MOVIMENTO
    # =============================================================

    def evaluate_move_risk(
        self,
        move_type,
        source,
        target,
        unit=None,
    ):
        """
        Retorna risco de loop.

        0.0 = seguro
        1.0 = extremamente suspeito
        """

        risk = 0.0

        # ---------------------------------------------------------
        # 🚫 Já bloqueado
        # ---------------------------------------------------------

        if self.is_move_blocked(
            move_type,
            source,
            target,
            unit,
        ):
            return 1.0

        # ---------------------------------------------------------
        # 🔄 Movimento inverso
        # ---------------------------------------------------------

        if self.is_reverse_move(
            move_type,
            source,
            target,
            unit,
        ):
            risk += 0.7

        # ---------------------------------------------------------
        # 🔁 Oscilação
        # ---------------------------------------------------------

        if self.is_oscillating(
            unit,
            source,
            target,
        ):
            risk += 0.8

        # ---------------------------------------------------------
        # ↔️ Bench <-> Board
        # ---------------------------------------------------------

        if self.is_bench_board_loop(
            unit
        ):
            risk += 0.9

        return min(
            1.0,
            risk
        )

    # =============================================================
    # 🚦 DEVE BLOQUEAR?
    # =============================================================

    def should_block_move(
        self,
        move_type,
        source,
        target,
        unit=None,
        board=None,
        bench=None,
    ):
        """
        Decide se o movimento deve ser bloqueado.

        Esta é a função principal que o
        ActionMaskManager poderá consultar.
        """

        # ---------------------------------------------------------
        # 🚫 Movimento explicitamente bloqueado
        # ---------------------------------------------------------

        if self.is_move_blocked(
            move_type,
            source,
            target,
            unit,
        ):
            return True

        # ---------------------------------------------------------
        # 🔄 Movimento inverso
        # ---------------------------------------------------------

        if self.is_reverse_move(
            move_type,
            source,
            target,
            unit,
        ):
            return True

        # ---------------------------------------------------------
        # 🔁 Oscilação
        # ---------------------------------------------------------

        if self.is_oscillating(
            unit,
            source,
            target,
        ):
            return True

        # ---------------------------------------------------------
        # ↔️ Bench / Board loop
        # ---------------------------------------------------------

        if self.is_bench_board_loop(
            unit
        ):
            return True

        # ---------------------------------------------------------
        # 📸 Estado futuro
        # ---------------------------------------------------------

        if (
            board is not None
            and bench is not None
        ):

            # Não simulamos o movimento aqui.
            # Isso será responsabilidade do Env/BoardManager.
            pass

        return False

    # =============================================================
    # 🧹 LIMPEZA
    # =============================================================

    def clear_old_blocks(self):
        """
        Limpa bloqueios antigos.

        Como blocked_moves é deque com maxlen,
        os mais antigos saem automaticamente.
        """

        while len(
            self.blocked_moves
        ) > self.blocked_move_size:

            self.blocked_moves.popleft()

    # =============================================================
    # 📊 ESTADO
    # =============================================================

    def get_state(self):
        """Retorna informações úteis para debug."""

        return {
            "history_size": len(
                self.position_history
            ),

            "move_history_size": len(
                self.move_history
            ),

            "blocked_moves": len(
                self.blocked_moves
            ),

            "known_states": len(
                self.state_visits
            ),

            "last_move": self.last_move,
        }

    # =============================================================
    # 🐛 DEBUG
    # =============================================================

    def debug_print(self):
        """Imprime estado do AntiLoop."""

        print(
            "\n========== ANTI LOOP =========="
        )

        print(
            f"📸 States: "
            f"{len(self.position_history)}"
        )

        print(
            f"🔄 Moves: "
            f"{len(self.move_history)}"
        )

        print(
            f"🚫 Blocked: "
            f"{len(self.blocked_moves)}"
        )

        print(
            f"🧠 Known states: "
            f"{len(self.state_visits)}"
        )

        print(
            f"➡️ Last move: "
            f"{self.last_move}"
        )

        print(
            "==============================="
        )