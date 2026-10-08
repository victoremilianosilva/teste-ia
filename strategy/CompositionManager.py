# strategy/CompositionManager.py

from collections import Counter


class CompositionManager:
    """
    🧩 Gerencia a composição de um único jogador.

    Responsabilidades:
        - unidades principais da composição
        - contagem de cópias
        - traits ativos
        - foco da composição
        - direção da composição
        - identificação de unidades core
        - avaliação básica de encaixe

    NÃO é responsabilidade:
        - board
        - bench
        - shop
        - gold
        - XP
        - combate
        - reward
        - PPO
    """

    def __init__(
        self,
        unit_manager,
        synergy_manager=None,
    ):
        self.unit_manager = unit_manager
        self.synergy_manager = synergy_manager

        self.reset()

    # =============================================================
    # 🔄 RESET
    # =============================================================

    def reset(self):
        """Reseta o estado da composição."""

        self.comp_focus = None
        self.comp_direction = None

        self.core_units = set()
        self.core_traits = set()

        self.active_traits = {}
        self.unit_counts = {}

        self.last_comp_score = 0.0

    # =============================================================
    # 📋 UNIDADES
    # =============================================================

    def get_all_units(
        self,
        board,
        bench,
    ):
        """
        Retorna todas as unidades pertencentes ao jogador.

        ⚠️ Shop NÃO entra aqui.

        Uma unidade no shop ainda não pertence ao jogador.
        """

        units = []

        if board is not None:
            units.extend(
                unit
                for unit in board
                if self.unit_manager.is_valid_unit(unit)
            )

        if bench is not None:
            units.extend(
                unit
                for unit in bench
                if self.unit_manager.is_valid_unit(unit)
            )

        return units

    # =============================================================
    # 🔢 CONTAGEM
    # =============================================================

    def rebuild_unit_counts(
        self,
        board,
        bench,
    ):
        """
        Reconstrói a quantidade de cópias por unidade.

        1★ = 1 cópia
        2★ = 3 cópias
        3★ = 9 cópias
        """

        units = self.get_all_units(
            board,
            bench,
        )

        self.unit_counts = (
            self.unit_manager.count_copies(
                units
            )
        )

        return dict(
            self.unit_counts
        )

    def count_unit(
        self,
        unit_id,
    ):
        """Retorna cópias equivalentes de uma unidade."""

        return self.unit_counts.get(
            unit_id,
            0
        )

    # =============================================================
    # 🧬 TRAITS
    # =============================================================

    def get_active_traits(
        self,
        board,
        bench=None,
    ):
        """
        Calcula as traits presentes nas unidades.

        Por padrão usamos o board para determinar a composição
        ativa, mas o método permite incluir bench quando necessário.
        """

        units = []

        if board is not None:
            units.extend(
                unit
                for unit in board
                if self.unit_manager.is_valid_unit(unit)
            )

        if bench is not None:
            units.extend(
                unit
                for unit in bench
                if self.unit_manager.is_valid_unit(unit)
            )

        trait_counts = Counter()

        for unit in units:

            traits = unit.get(
                "traits",
                []
            )

            for trait in traits:
                trait_counts[trait] += 1

        self.active_traits = dict(
            trait_counts
        )

        return dict(
            self.active_traits
        )

    # =============================================================
    # 🎯 TRAIT PRINCIPAL
    # =============================================================

    def _get_primary_trait(self):
        """
        Retorna a trait com maior presença.
        """

        if not self.active_traits:
            return None

        return max(
            self.active_traits,
            key=self.active_traits.get
        )

    # =============================================================
    # 🧭 DIREÇÃO
    # =============================================================

    def update_direction(
        self,
        board,
        bench,
    ):
        """
        Atualiza a direção atual da composição.

        A direção é baseada nas traits mais presentes.

        Exemplo:

            Magic: 4
            Tank: 2
            Assassin: 1

        -> direção = Magic
        """

        self.get_active_traits(
            board,
            bench
        )

        primary_trait = (
            self._get_primary_trait()
        )

        if primary_trait is None:
            self.comp_direction = None

        else:
            self.comp_direction = (
                primary_trait
            )

        return self.comp_direction

    # =============================================================
    # 🎯 FOCO
    # =============================================================

    def update_focus(
        self,
        board,
        bench,
    ):
        """
        Identifica unidades que parecem ser importantes
        para a composição.

        A avaliação inicial considera:
            - custo
            - estrelas
            - traits
            - quantidade de cópias
        """

        units = self.get_all_units(
            board,
            bench
        )

        if not units:
            self.comp_focus = None
            return None

        scores = {}

        for unit in units:

            unit_id = unit.get(
                "id"
            )

            if unit_id is None:
                continue

            score = (
                self._calculate_focus_score(
                    unit
                )
            )

            previous = scores.get(
                unit_id,
                0.0
            )

            scores[unit_id] = max(
                previous,
                score
            )

        if not scores:
            self.comp_focus = None
            return None

        self.comp_focus = max(
            scores,
            key=scores.get
        )

        return self.comp_focus

    def _calculate_focus_score(
        self,
        unit,
    ):
        """Calcula importância aproximada de uma unidade."""

        score = 0.0

        # ⭐ Estrelas
        star = unit.get(
            "star",
            1
        )

        score += (
            star - 1
        ) * 3.0

        # 💰 Custo
        cost = unit.get(
            "cost",
            1
        )

        score += cost * 1.5

        # 🧬 Traits
        traits = unit.get(
            "traits",
            []
        )

        score += len(traits) * 1.0

        # 📦 Quantidade de cópias
        unit_id = unit.get(
            "id"
        )

        copies = self.count_unit(
            unit_id
        )

        score += min(
            copies,
            9
        ) * 0.5

        return score

    # =============================================================
    # ⭐ CORE UNITS
    # =============================================================

    def update_core_units(
        self,
        board,
        bench,
    ):
        """
        Atualiza conjunto de unidades consideradas core.
        """

        units = self.get_all_units(
            board,
            bench
        )

        if not units:
            self.core_units.clear()
            return set()

        scored = []

        for unit in units:

            unit_id = unit.get(
                "id"
            )

            if unit_id is None:
                continue

            score = (
                self._calculate_focus_score(
                    unit
                )
            )

            scored.append(
                (
                    unit_id,
                    score
                )
            )

        scored.sort(
            key=lambda item: item[1],
            reverse=True
        )

        # Mantemos no máximo 3 unidades core.
        self.core_units = {
            unit_id
            for unit_id, _ in scored[:3]
        }

        return set(
            self.core_units
        )

    # =============================================================
    # 🧬 CORE TRAITS
    # =============================================================

    def update_core_traits(self):
        """
        Define traits mais importantes para a composição.
        """

        if not self.active_traits:
            self.core_traits.clear()
            return set()

        ordered = sorted(
            self.active_traits.items(),
            key=lambda item: item[1],
            reverse=True
        )

        self.core_traits = {
            trait
            for trait, count in ordered[:3]
            if count >= 2
        }

        return set(
            self.core_traits
        )

    # =============================================================
    # 🔄 UPDATE COMPLETO
    # =============================================================

    def update(
        self,
        board,
        bench,
    ):
        """
        Atualiza todo o estado da composição.
        """

        self.rebuild_unit_counts(
            board,
            bench
        )

        self.get_active_traits(
            board,
            bench
        )

        self.update_direction(
            board,
            bench
        )

        self.update_focus(
            board,
            bench
        )

        self.update_core_units(
            board,
            bench
        )

        self.update_core_traits()

        return self.get_state()

    # =============================================================
    # 🧮 SCORE DE UNIDADE
    # =============================================================

    def get_unit_comp_score(
        self,
        unit,
    ):
        """
        Avalia quanto uma unidade combina com a composição atual.
        """

        if not self.unit_manager.is_valid_unit(
            unit
        ):
            return 0.0

        score = 0.0

        unit_id = unit.get(
            "id"
        )

        # ---------------------------------------------------------
        # 🎯 Unidade core
        # ---------------------------------------------------------

        if unit_id in self.core_units:
            score += 5.0

        # ---------------------------------------------------------
        # 🧭 Direção
        # ---------------------------------------------------------

        direction = self.comp_direction

        if direction is not None:

            if direction in unit.get(
                "traits",
                []
            ):
                score += 3.0

        # ---------------------------------------------------------
        # 🧬 Traits core
        # ---------------------------------------------------------

        for trait in unit.get(
            "traits",
            []
        ):

            if trait in self.core_traits:
                score += 2.0

        # ---------------------------------------------------------
        # ⭐ Upgrade
        # ---------------------------------------------------------

        star = unit.get(
            "star",
            1
        )

        if star >= 2:
            score += 2.0

        if star >= 3:
            score += 4.0

        # ---------------------------------------------------------
        # 💰 Custo
        # ---------------------------------------------------------

        score += (
            unit.get(
                "cost",
                1
            ) * 0.5
        )

        return score

    # =============================================================
    # 🧩 CORE UNIT
    # =============================================================

    def is_core_unit(
        self,
        unit,
    ):
        """Verifica se uma unidade faz parte do core."""

        if not self.unit_manager.is_valid_unit(
            unit
        ):
            return False

        return (
            unit.get("id")
            in self.core_units
        )

    # =============================================================
    # 🧬 CORE TRAIT
    # =============================================================

    def is_core_trait(
        self,
        trait,
    ):
        """Verifica se uma trait faz parte do core."""

        return trait in self.core_traits

    # =============================================================
    # 📊 ESTADO
    # =============================================================

    def get_state(self):
        """
        Retorna o estado atual da composição.
        """

        return {
            "focus": self.comp_focus,
            "direction": self.comp_direction,

            "core_units": list(
                self.core_units
            ),

            "core_traits": list(
                self.core_traits
            ),

            "active_traits": dict(
                self.active_traits
            ),

            "unit_counts": dict(
                self.unit_counts
            ),
        }

    # =============================================================
    # 🐛 DEBUG
    # =============================================================

    def debug_print(self):
        """Imprime o estado da composição."""

        print(
            "\n========== COMPOSITION =========="
        )

        print(
            f"🎯 Focus: {self.comp_focus}"
        )

        print(
            f"🧭 Direction: "
            f"{self.comp_direction}"
        )

        print(
            f"⭐ Core units: "
            f"{list(self.core_units)}"
        )

        print(
            f"🧬 Core traits: "
            f"{list(self.core_traits)}"
        )

        print(
            f"📊 Active traits: "
            f"{self.active_traits}"
        )

        print(
            "================================="
        )