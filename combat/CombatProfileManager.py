from enum import IntEnum
from typing import Any, Dict, Optional


class UnitRole(IntEnum):
    """
    Papel estratégico da unidade.

    Usado pela IA e pelo sistema de posicionamento.
    Não contém lógica de combate.
    """

    TANK = 0
    CARRY = 1
    SUPPORT = 2
    FIGHTER = 3
    ASSASSIN = 4


class CombatProfileManager:
    """
    Analisa as características de uma unidade e gera um perfil
    estratégico.

    Responsabilidades:
        - Inferir o papel da unidade.
        - Identificar características úteis para posicionamento.
        - Preparar dados básicos para futura integração com C++.

    NÃO é responsabilidade deste componente:
        - Simular combate.
        - Calcular dano.
        - Escolher alvos.
        - Controlar HP durante combate.
        - Controlar mana durante combate.
        - Executar ataques.
        - Executar habilidades.
        - Executar loops/ticks de combate.
    """

    _ROLE_KEYWORDS = {
        UnitRole.TANK: (
            "shield",
            "armor",
            "defense",
            "defensive",
            "taunt",
            "damage reduction",
            "barrier",
            "protect",
        ),
        UnitRole.CARRY: (
            "attack damage",
            "critical",
            "crit",
            "damage",
            "projectile",
            "rapid fire",
            "attack speed",
        ),
        UnitRole.SUPPORT: (
            "heal",
            "healing",
            "shield",
            "buff",
            "ally",
            "all allies",
            "mana",
            "restore",
            "protect",
        ),
        UnitRole.FIGHTER: (
            "melee",
            "strike",
            "physical damage",
            "attack",
            "damage",
            "lifesteal",
        ),
        UnitRole.ASSASSIN: (
            "dash",
            "jump",
            "backline",
            "lowest health",
            "furthest",
            "farther",
        ),
    }

    _FRONTLINE_ROLES = {
        UnitRole.TANK,
        UnitRole.FIGHTER,
    }

    _BACKLINE_ROLES = {
        UnitRole.CARRY,
        UnitRole.SUPPORT,
        UnitRole.ASSASSIN,
    }

    def __init__(self):
        self._profile_cache: Dict[Any, Dict[str, Any]] = {}

    # ============================================================
    # PUBLIC API
    # ============================================================

    def process_unit(
        self,
        unit: Optional[Dict[str, Any]],
    ) -> Optional[Dict[str, Any]]:
        """
        Processa uma unidade e adiciona informações derivadas
        necessárias para a IA.

        Não altera os atributos fundamentais da unidade.
        """

        if unit is None:
            return None

        profile = self.get_profile(unit)

        # Mantém compatibilidade com o restante do projeto.
        unit["combat_profile"] = profile
        unit["role"] = profile["role"]

        return unit

    def get_profile(self, unit: Dict[str, Any]) -> Dict[str, Any]:
        """
        Retorna o perfil estratégico da unidade.
        """

        unit_id = self._get_unit_identifier(unit)

        if unit_id is not None and unit_id in self._profile_cache:
            return self._profile_cache[unit_id]

        role = self._infer_unit_role(unit)

        profile = {
            "role": int(role),
            "role_name": role.name.lower(),

            # Posicionamento
            "frontline": self.is_frontline_role(role),
            "backline": self.is_backline_role(role),

            # Flags estratégicas
            "is_tank": role == UnitRole.TANK,
            "is_carry": role == UnitRole.CARRY,
            "is_support": role == UnitRole.SUPPORT,
            "is_fighter": role == UnitRole.FIGHTER,
            "is_assassin": role == UnitRole.ASSASSIN,

            # Dados básicos utilizados pela IA
            # e posteriormente enviados ao C++.
            "attack_range": self._get_numeric(
                unit,
                "attack_range",
                0.0,
            ),
            "attack_speed": self._get_numeric(
                unit,
                "attack_speed",
                0.0,
            ),
            "attack_damage": self._get_numeric(
                unit,
                "attack_damage",
                unit.get("ad", 0.0),
            ),
            "armor": self._get_numeric(
                unit,
                "armor",
                0.0,
            ),
            "magic_resist": self._get_numeric(
                unit,
                "magic_resist",
                unit.get("mr", 0.0),
            ),
            "max_hp": self._get_numeric(
                unit,
                "max_hp",
                unit.get("hp", 0.0),
            ),
            "max_mana": self._get_numeric(
                unit,
                "max_mana",
                0.0,
            ),
        }

        if unit_id is not None:
            self._profile_cache[unit_id] = profile

        return profile

    # ============================================================
    # ROLE
    # ============================================================

    def get_role(
        self,
        unit: Optional[Dict[str, Any]],
    ) -> UnitRole:
        if unit is None:
            return UnitRole.FIGHTER

        profile = self.get_profile(unit)

        try:
            return UnitRole(profile["role"])
        except (KeyError, ValueError):
            return UnitRole.FIGHTER

    def is_tank(self, unit: Optional[Dict[str, Any]]) -> bool:
        return self.get_role(unit) == UnitRole.TANK

    def is_carry(self, unit: Optional[Dict[str, Any]]) -> bool:
        return self.get_role(unit) == UnitRole.CARRY

    def is_support(self, unit: Optional[Dict[str, Any]]) -> bool:
        return self.get_role(unit) == UnitRole.SUPPORT

    def is_fighter(self, unit: Optional[Dict[str, Any]]) -> bool:
        return self.get_role(unit) == UnitRole.FIGHTER

    def is_assassin(self, unit: Optional[Dict[str, Any]]) -> bool:
        return self.get_role(unit) == UnitRole.ASSASSIN

    def is_frontline(self, unit: Optional[Dict[str, Any]]) -> bool:
        return self.is_frontline_role(self.get_role(unit))

    def is_backline(self, unit: Optional[Dict[str, Any]]) -> bool:
        return self.is_backline_role(self.get_role(unit))

    # ============================================================
    # ROLE INFERENCE
    # ============================================================

    def _infer_unit_role(
        self,
        unit: Dict[str, Any],
    ) -> UnitRole:
        """
        Infere o papel estratégico da unidade.

        Não utiliza traits para determinar o papel.

        Utiliza:
            - descrição da habilidade
            - HP
            - armor
            - MR
            - attack damage
            - attack speed
            - attack range
        """

        scores = {
            UnitRole.TANK: 0.0,
            UnitRole.CARRY: 0.0,
            UnitRole.SUPPORT: 0.0,
            UnitRole.FIGHTER: 0.0,
            UnitRole.ASSASSIN: 0.0,
        }

        description = self._get_ability_text(unit)

        # --------------------------------------------------------
        # Análise da habilidade
        # --------------------------------------------------------

        if description:
            text = description.lower()

            for role, keywords in self._ROLE_KEYWORDS.items():
                for keyword in keywords:
                    if keyword in text:
                        scores[role] += 1.0

        # --------------------------------------------------------
        # Stats
        # --------------------------------------------------------

        attack_range = self._get_numeric(
            unit,
            "attack_range",
            0.0,
        )

        attack_speed = self._get_numeric(
            unit,
            "attack_speed",
            0.0,
        )

        attack_damage = self._get_numeric(
            unit,
            "attack_damage",
            unit.get("ad", 0.0),
        )

        armor = self._get_numeric(
            unit,
            "armor",
            0.0,
        )

        magic_resist = self._get_numeric(
            unit,
            "magic_resist",
            unit.get("mr", 0.0),
        )

        hp = self._get_numeric(
            unit,
            "max_hp",
            unit.get("hp", 0.0),
        )

        # --------------------------------------------------------
        # Tank
        # --------------------------------------------------------

        if hp >= 800:
            scores[UnitRole.TANK] += 2.0

        if hp >= 1100:
            scores[UnitRole.TANK] += 1.0

        if armor >= 40:
            scores[UnitRole.TANK] += 1.5

        if magic_resist >= 40:
            scores[UnitRole.TANK] += 1.0

        # --------------------------------------------------------
        # Carry
        # --------------------------------------------------------

        if attack_damage >= 70:
            scores[UnitRole.CARRY] += 1.5

        if attack_speed >= 0.8:
            scores[UnitRole.CARRY] += 1.0

        # --------------------------------------------------------
        # Fighter
        # --------------------------------------------------------

        if 0 < attack_range <= 1:
            scores[UnitRole.FIGHTER] += 1.0

            if armor >= 30 or hp >= 700:
                scores[UnitRole.FIGHTER] += 1.0

        # --------------------------------------------------------
        # Long range
        # --------------------------------------------------------

        if attack_range >= 3:
            scores[UnitRole.CARRY] += 0.5
            scores[UnitRole.SUPPORT] += 0.25

        # --------------------------------------------------------
        # Assassin
        # --------------------------------------------------------

        if description:
            text = description.lower()

            assassin_keywords = self._ROLE_KEYWORDS[
                UnitRole.ASSASSIN
            ]

            if any(
                keyword in text
                for keyword in assassin_keywords
            ):
                scores[UnitRole.ASSASSIN] += 2.0

        return max(
            scores,
            key=scores.get,
        )

    # ============================================================
    # POSITIONING
    # ============================================================

    @staticmethod
    def is_frontline_role(role: UnitRole) -> bool:
        return role in CombatProfileManager._FRONTLINE_ROLES

    @staticmethod
    def is_backline_role(role: UnitRole) -> bool:
        return role in CombatProfileManager._BACKLINE_ROLES

    # ============================================================
    # DATA EXTRACTION
    # ============================================================

    @staticmethod
    def _get_unit_identifier(
        unit: Dict[str, Any],
    ) -> Any:
        """
        Obtém um identificador estável da unidade.
        """

        for key in (
            "id",
            "champion_id",
            "apiName",
            "characterName",
        ):
            value = unit.get(key)

            if value is not None:
                return value

        return None

    @staticmethod
    def _get_numeric(
        unit: Dict[str, Any],
        key: str,
        default: float = 0.0,
    ) -> float:
        value = unit.get(key, default)

        try:
            return float(value)
        except (TypeError, ValueError):
            return default

    @staticmethod
    def _get_ability_text(
        unit: Dict[str, Any],
    ) -> str:
        """
        Extrai a descrição da habilidade sem depender
        de uma estrutura específica do catálogo.
        """

        ability = unit.get("ability")

        if isinstance(ability, str):
            return ability

        if isinstance(ability, dict):
            for key in (
                "description",
                "desc",
                "name",
                "effect",
            ):
                value = ability.get(key)

                if isinstance(value, str):
                    return value

        for key in (
            "ability_description",
            "ability_desc",
            "description",
        ):
            value = unit.get(key)

            if isinstance(value, str):
                return value

        return ""

    # ============================================================
    # C++ INTEGRATION
    # ============================================================

    def build_combat_input(
        self,
        unit: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Prepara os dados básicos de uma unidade para o futuro
        CombatBridge.

        IMPORTANTE:
        Este método NÃO executa combate.

        Ele apenas transforma os dados Python em uma estrutura
        simples que posteriormente poderá ser convertida para
        CombatInput no C++.
        """

        profile = self.get_profile(unit)

        return {
            "id": self._get_unit_identifier(unit),

            "star": int(
                unit.get("star", 1)
            ),

            "hp": self._get_numeric(
                unit,
                "hp",
                profile["max_hp"],
            ),

            "max_hp": profile["max_hp"],

            "mana": self._get_numeric(
                unit,
                "mana",
                0.0,
            ),

            "max_mana": profile["max_mana"],

            "attack_damage": profile["attack_damage"],
            "attack_speed": profile["attack_speed"],

            "armor": profile["armor"],
            "magic_resist": profile["magic_resist"],

            "attack_range": profile["attack_range"],

            "role": profile["role"],
        }

    # ============================================================
    # CACHE / LIFECYCLE
    # ============================================================

    def clear_cache(self) -> None:
        self._profile_cache.clear()

    def reset(self) -> None:
        """
        Limpa o cache para um novo ciclo do ambiente.
        """

        self.clear_cache()