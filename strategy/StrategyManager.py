# strategy/StrategyManager.py

from enum import IntEnum


class Strategy(IntEnum):
    """
    🎯 Estratégias possíveis da IA.
    """

    ECON = 0
    STABILIZE = 1
    FAST8 = 2
    SLOWROLL = 3
    ALL_IN = 4
    WINSTREAK = 5
    LOSS_STREAK = 6


class StrategyManager:
    """
    🧠 Gerencia a estratégia de um jogador.

    Responsabilidades:
        - escolher estratégia
        - calcular confiança
        - analisar estado econômico
        - analisar HP
        - analisar streak
        - analisar nível
        - analisar força do board
        - detectar necessidade de estabilização
        - atualizar estratégia

    NÃO é responsabilidade:
        - executar ações
        - comprar unidades
        - mover unidades
        - reward
        - PPO
        - combate
    """

    def __init__(
        self,
        max_level=9,
    ):
        self.max_level = max_level

        self.strategy = Strategy.ECON
        self.previous_strategy = None

        self.confidence = 0.0

        self.strategy_age = 0

        self.last_reason = ""

    # =============================================================
    # 🔄 RESET
    # =============================================================

    def reset(self):
        """Reseta o estado estratégico."""

        self.strategy = Strategy.ECON
        self.previous_strategy = None

        self.confidence = 0.0

        self.strategy_age = 0

        self.last_reason = ""

    # =============================================================
    # 🧠 DECISÃO
    # =============================================================

    def decide_strategy(
        self,
        *,
        hp,
        gold,
        level,
        xp,
        board_power,
        bench_strength=0.0,
        win_streak=0,
        loss_streak=0,
        round_number=1,
        active_traits=0,
        comp_focus=None,
        comp_direction=None,
    ):
        """
        Decide a estratégia atual.

        A decisão é baseada no estado do jogador.

        IMPORTANTE:

        Este método NÃO executa nenhuma ação.
        Apenas escolhe a intenção estratégica.
        """

        # =========================================================
        # 🚨 SITUAÇÕES CRÍTICAS
        # =========================================================

        if hp <= 15:

            strategy = Strategy.ALL_IN

            reason = (
                "HP crítico"
            )

            confidence = 0.95

            return self._apply_strategy(
                strategy,
                confidence,
                reason,
            )

        # =========================================================
        # 🩸 HP BAIXO
        # =========================================================

        if hp <= 30:

            strategy = Strategy.STABILIZE

            reason = (
                "HP baixo"
            )

            confidence = 0.85

            return self._apply_strategy(
                strategy,
                confidence,
                reason,
            )

        # =========================================================
        # 💀 LOSS STREAK
        # =========================================================

        if loss_streak >= 5:

            strategy = Strategy.LOSS_STREAK

            reason = (
                "Loss streak prolongada"
            )

            confidence = 0.80

            return self._apply_strategy(
                strategy,
                confidence,
                reason,
            )

        # =========================================================
        # 🔥 WIN STREAK
        # =========================================================

        if win_streak >= 4 and hp >= 60:

            strategy = Strategy.WINSTREAK

            reason = (
                "Win streak + HP saudável"
            )

            confidence = 0.80

            return self._apply_strategy(
                strategy,
                confidence,
                reason,
            )

        # =========================================================
        # 💰 ECONOMIA FORTE
        # =========================================================

        if (
            gold >= 40
            and level <= 7
            and hp >= 50
        ):

            strategy = Strategy.ECON

            reason = (
                "Economia forte"
            )

            confidence = 0.85

            return self._apply_strategy(
                strategy,
                confidence,
                reason,
            )

        # =========================================================
        # 🚀 FAST 8
        # =========================================================

        if (
            level >= 7
            and gold >= 30
            and hp >= 50
        ):

            strategy = Strategy.FAST8

            reason = (
                "Economia suficiente para acelerar nível"
            )

            confidence = 0.75

            return self._apply_strategy(
                strategy,
                confidence,
                reason,
            )

        # =========================================================
        # 🐌 SLOW ROLL
        # =========================================================

        if (
            level <= 6
            and gold >= 30
            and board_power >= 40
        ):

            strategy = Strategy.SLOWROLL

            reason = (
                "Board estável + economia para rolagem"
            )

            confidence = 0.70

            return self._apply_strategy(
                strategy,
                confidence,
                reason,
            )

        # =========================================================
        # 🛡️ ESTABILIZAÇÃO
        # =========================================================

        if board_power < 25:

            strategy = Strategy.STABILIZE

            reason = (
                "Board abaixo do esperado"
            )

            confidence = 0.70

            return self._apply_strategy(
                strategy,
                confidence,
                reason,
            )

        # =========================================================
        # 💰 ECON PADRÃO
        # =========================================================

        strategy = Strategy.ECON

        reason = (
            "Estado econômico neutro"
        )

        confidence = 0.50

        return self._apply_strategy(
            strategy,
            confidence,
            reason,
        )

    # =============================================================
    # 🔄 APLICAR ESTRATÉGIA
    # =============================================================

    def _apply_strategy(
        self,
        strategy,
        confidence,
        reason,
    ):
        """
        Atualiza o estado interno da estratégia.
        """

        if strategy != self.strategy:

            self.previous_strategy = (
                self.strategy
            )

            self.strategy_age = 0

        else:
            self.strategy_age += 1

        self.strategy = strategy

        self.confidence = max(
            0.0,
            min(
                1.0,
                confidence,
            )
        )

        self.last_reason = reason

        return {
            "strategy": self.strategy,
            "confidence": self.confidence,
            "reason": self.last_reason,
            "changed": (
                self.previous_strategy
                != self.strategy
            ),
        }

    # =============================================================
    # 📊 CONFIANÇA
    # =============================================================

    def compute_strategy_confidence(
        self,
        *,
        hp,
        gold,
        board_power,
        level,
        win_streak=0,
        loss_streak=0,
    ):
        """
        Calcula uma confiança independente da estratégia.

        Útil para observation/debug.
        """

        confidence = 0.5

        # HP
        if hp <= 20:
            confidence += 0.25

        elif hp >= 80:
            confidence += 0.10

        # Economia
        if gold >= 40:
            confidence += 0.15

        elif gold < 10:
            confidence -= 0.10

        # Board
        if board_power >= 70:
            confidence += 0.15

        elif board_power <= 20:
            confidence -= 0.15

        # Streak
        if win_streak >= 4:
            confidence += 0.10

        if loss_streak >= 4:
            confidence += 0.10

        # Level
        if level >= 8:
            confidence += 0.10

        return max(
            0.0,
            min(
                1.0,
                confidence,
            )
        )

    # =============================================================
    # 🎯 SCORE POR ESTRATÉGIA
    # =============================================================

    def get_strategy_score(
        self,
        strategy,
        *,
        hp,
        gold,
        level,
        board_power,
        win_streak=0,
        loss_streak=0,
    ):
        """
        Calcula o quanto determinada estratégia combina
        com o estado atual.

        Isso permite posteriormente substituir regras rígidas
        por uma escolha baseada em scores.
        """

        score = 0.0

        # =========================================================
        # 💰 ECON
        # =========================================================

        if strategy == Strategy.ECON:

            score += min(
                gold / 50.0,
                1.0
            ) * 5.0

            if hp >= 60:
                score += 2.0

            if loss_streak >= 3:
                score += 1.0

        # =========================================================
        # 🛡️ STABILIZE
        # =========================================================

        elif strategy == Strategy.STABILIZE:

            if hp < 50:
                score += 4.0

            if board_power < 40:
                score += 4.0

            if loss_streak >= 2:
                score += 2.0

        # =========================================================
        # 🚀 FAST 8
        # =========================================================

        elif strategy == Strategy.FAST8:

            if level >= 6:
                score += 2.0

            if gold >= 30:
                score += 3.0

            if hp >= 50:
                score += 2.0

        # =========================================================
        # 🐌 SLOWROLL
        # =========================================================

        elif strategy == Strategy.SLOWROLL:

            if level <= 6:
                score += 3.0

            if gold >= 30:
                score += 3.0

            if board_power >= 30:
                score += 2.0

        # =========================================================
        # 🔥 ALL IN
        # =========================================================

        elif strategy == Strategy.ALL_IN:

            if hp <= 25:
                score += 6.0

            if loss_streak >= 5:
                score += 2.0

            if board_power < 30:
                score += 2.0

        # =========================================================
        # 🔥 WIN STREAK
        # =========================================================

        elif strategy == Strategy.WINSTREAK:

            if win_streak >= 3:
                score += 5.0

            if hp >= 60:
                score += 2.0

            if board_power >= 40:
                score += 2.0

        # =========================================================
        # 💀 LOSS STREAK
        # =========================================================

        elif strategy == Strategy.LOSS_STREAK:

            if loss_streak >= 3:
                score += 5.0

            if hp >= 40:
                score += 1.0

        return score

    # =============================================================
    # 🎯 MELHOR ESTRATÉGIA
    # =============================================================

    def choose_best_strategy(
        self,
        *,
        hp,
        gold,
        level,
        board_power,
        win_streak=0,
        loss_streak=0,
    ):
        """
        Escolhe a estratégia através de score.

        Esta função é mais flexível que decide_strategy()
        e pode ser usada posteriormente para substituir
        completamente as regras.
        """

        strategies = list(
            Strategy
        )

        scores = {}

        for strategy in strategies:

            scores[strategy] = (
                self.get_strategy_score(
                    strategy,
                    hp=hp,
                    gold=gold,
                    level=level,
                    board_power=board_power,
                    win_streak=win_streak,
                    loss_streak=loss_streak,
                )
            )

        best_strategy = max(
            scores,
            key=scores.get
        )

        return (
            best_strategy,
            scores,
        )

    # =============================================================
    # 🔍 UTILITÁRIOS
    # =============================================================

    def is_strategy(
        self,
        strategy,
    ):
        """Verifica estratégia atual."""

        return (
            self.strategy == strategy
        )

    def is_economy_strategy(self):
        """Verifica se estratégia prioriza economia."""

        return self.strategy in {
            Strategy.ECON,
            Strategy.SLOWROLL,
            Strategy.FAST8,
        }

    def is_aggressive(self):
        """Verifica se estratégia é agressiva."""

        return self.strategy in {
            Strategy.ALL_IN,
            Strategy.STABILIZE,
            Strategy.WINSTREAK,
        }

    # =============================================================
    # 📊 ESTADO
    # =============================================================

    def get_state(self):
        """Retorna estado estratégico."""

        return {
            "strategy": int(
                self.strategy
            ),

            "strategy_name": (
                self.strategy.name
            ),

            "previous_strategy": (
                None
                if self.previous_strategy is None
                else int(
                    self.previous_strategy
                )
            ),

            "confidence": (
                self.confidence
            ),

            "strategy_age": (
                self.strategy_age
            ),

            "reason": (
                self.last_reason
            ),
        }

    # =============================================================
    # 🐛 DEBUG
    # =============================================================

    def debug_print(self):
        """Imprime estado estratégico."""

        print(
            "\n========== STRATEGY =========="
        )

        print(
            f"🎯 Strategy: "
            f"{self.strategy.name}"
        )

        print(
            f"📊 Confidence: "
            f"{self.confidence:.2f}"
        )

        print(
            f"⏱️ Age: "
            f"{self.strategy_age}"
        )

        print(
            f"💡 Reason: "
            f"{self.last_reason}"
        )

        print(
            "=============================="
        )