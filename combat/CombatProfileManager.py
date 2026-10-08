import re
from enum import IntEnum
from typing import Dict, List, Any

class UnitRole(IntEnum):
    TANK = 0
    CARRY = 1
    SUPPORT = 2
    FIGHTER = 3
    ASSASSIN = 4

class CombatProfileManager:
    FRONT_ROWS = {0, 1}
    BACK_ROWS = {2, 3}

    # Apenas palavras-chave para análise de descrição
    SUPPORT_KEYWORDS = (
        "heal", "shield", "escudo", "cura", "buff", "mana", "speed", "haste",
        "regeneração", "regenera", "protege", "aliado", "vampirismo"
    )
    TANK_KEYWORDS = ("armadura", "resistência", "defesa", "durabilidade", "provocação", "tanque")
    CARRY_KEYWORDS = ("dano", "damage", "crítico", "explosão", "fatal", "aniquila", "destrói")
    ASSASSIN_KEYWORDS = ("costas", "sombra", "mergulha", "pula", "flanqueia")

    def __init__(self):
        self._profile_cache = {}

    # =========================================================
    # PUBLIC
    # =========================================================
    def process_unit(self, unit: Dict) -> Dict:
        stats = unit.setdefault("stats", {})
        stats["range"] = max(1, stats.get("range", 0))
        unit["combat_profile"] = self._build_combat_profile(unit)
        unit["role"] = self._infer_unit_role(unit)
        return unit

    # =========================================================
    # ROLE INFERENCE (baseada principalmente nas variáveis da habilidade e descrição)
    # =========================================================
    def _infer_unit_role(self, unit: Dict) -> UnitRole:
        ability = unit.get("ability", {})
        desc = ability.get("desc", "").lower()
        variables = ability.get("variables", [])
        cost = unit.get("cost", 1)
        profile = unit.get("combat_profile", {})
        traits = unit.get("traits", [])

        scores = {role: 0.0 for role in UnitRole}

        # 1. Analisa variáveis da habilidade (fonte mais objetiva)
        damage_value = 0
        heal_shield_value = 0
        resistance_value = 0

        for var in variables:
            name = var.get("name", "").lower()
            values = var.get("value", [])
            if not values:
                continue
            max_val = max(values)
            if any(x in name for x in ("damage", "dano", "ad", "ap")):
                damage_value = max(damage_value, max_val)
                # Dano alto favorece CARRY (pesos aumentados)
                if max_val >= 80:
                    scores[UnitRole.CARRY] += 2.0
                elif max_val >= 40:
                    scores[UnitRole.CARRY] += 1.0
                # Dano em área e melee -> fighter/assassin (peso reduzido)
                if "área" in desc or "cônico" in desc or "raio" in desc:
                    scores[UnitRole.FIGHTER] += 0.2
                    scores[UnitRole.ASSASSIN] += 0.2
            if any(x in name for x in ("heal", "cura", "shield", "escudo")):
                heal_shield_value = max(heal_shield_value, max_val)
                scores[UnitRole.SUPPORT] += 1.0
                if "escudo" in name and "recebe" in desc:
                    scores[UnitRole.TANK] += 0.8
            if any(x in name for x in ("armor", "armadura", "magicresist", "defense")):
                resistance_value = max(resistance_value, max_val)
                scores[UnitRole.TANK] += 1.0

        # 2. Análise da descrição (palavras-chave)
        support_hits = sum(1 for kw in self.SUPPORT_KEYWORDS if kw in desc)
        scores[UnitRole.SUPPORT] += support_hits * 1.2

        if any(kw in desc for kw in self.CARRY_KEYWORDS):
            scores[UnitRole.CARRY] += 1.2
        if any(kw in desc for kw in self.TANK_KEYWORDS):
            scores[UnitRole.TANK] += 1.2
        if any(kw in desc for kw in self.ASSASSIN_KEYWORDS):
            scores[UnitRole.ASSASSIN] += 1.5

        # 3. Ajuste por custo
        if cost >= 4:
            scores[UnitRole.CARRY] += 0.8
        elif cost == 1:
            scores[UnitRole.CARRY] -= 0.5

        # 4. Traits como dica leve (pesos reduzidos para FIGHTER)
        trait_text = " ".join(t.lower() for t in traits)
        if any(x in trait_text for x in ("lutador", "vanguarda", "bastião", "baluarte", "guardian")):
            scores[UnitRole.TANK] += 0.8
        if any(x in trait_text for x in ("atirador de elite", "desafiante", "tecelã", "psicônico", "estrela negra")):
            scores[UnitRole.CARRY] += 0.8
        if any(x in trait_text for x in ("ladino", "assassin", "slayer", "rogue")):
            scores[UnitRole.ASSASSIN] += 1.0
        if any(x in trait_text for x in ("pastor", "replicador", "astromante")):
            if damage_value < 20:   # limite baixíssimo
                scores[UnitRole.SUPPORT] += 0.2   # peso pequeno
        if any(x in trait_text for x in ("saqueador", "mech")):
            scores[UnitRole.FIGHTER] += 0.3  # reduzido de 1.0

        # 5. Combat profile (dps, effective_hp) ajustes finos
        dps = profile.get("dps", 0)
        effective_hp = profile.get("effective_hp", 0)
        burst = profile.get("burst", 0)
        range_val = profile.get("range", 1)

        if dps > 70:
            scores[UnitRole.CARRY] += 1.5  # aumentado
        if burst > 120:
            scores[UnitRole.CARRY] += 0.8
        if effective_hp > 1500:
            scores[UnitRole.TANK] += 2.0  # aumentado
        if effective_hp < 800 and range_val > 1 and dps > 50:
            scores[UnitRole.CARRY] += 0.5
        if effective_hp > 1000 and dps > 60:
            scores[UnitRole.FIGHTER] += 0.3  # reduzido de 1.0
        if range_val <= 1 and burst > 100 and effective_hp < 1200:
            scores[UnitRole.ASSASSIN] += 1.0

        # 6. Regras de desempate: dano muito alto puxa CARRY, cura/shield puxa SUPPORT
        if damage_value >= 100 and heal_shield_value == 0:
            scores[UnitRole.SUPPORT] -= 1.0
            scores[UnitRole.CARRY] += 1.0
        if heal_shield_value >= 100 and damage_value < 50:
            scores[UnitRole.CARRY] -= 0.5

        # 7. Override manual
        if "role_override" in unit:
            return UnitRole[unit["role_override"]]

        # 8. Específico: Teemo
        if unit.get("name") == "Teemo":
            scores[UnitRole.CARRY] += 2.5
            scores[UnitRole.SUPPORT] -= 1.5

        # 9. Se ainda houver empate entre CARRY e FIGHTER, priorizar CARRY
        if scores[UnitRole.CARRY] >= scores[UnitRole.FIGHTER] - 0.5 and damage_value >= 40:
            scores[UnitRole.FIGHTER] -= 0.5

        best_role = max(scores.items(), key=lambda x: x[1])[0]

        unit["role_scores"] = {role.name: round(score, 3) for role, score in scores.items()}
        return best_role

    # =========================================================
    # COMBAT PROFILE (igual à versão anterior, com AD, ARMOR, MR)
    # =========================================================
    # =========================================================
    # COMBAT PROFILE
    # =========================================================
    def _build_combat_profile(
        self,
        unit: Dict
    ) -> Dict:

        traits = unit.get("traits", [])

        cost = unit.get("cost", 1)

        ability = unit.get("ability", {})

        desc = (
            ability.get("desc", "")
            .lower()
        )

        variables = ability.get(
            "variables",
            []
        )

        stats = unit.get("stats", {})

        # =====================================================
        # 📊 BASE STATS
        # =====================================================

        base_hp = {
            1: 500,
            2: 700,
            3: 950,
            4: 1300,
            5: 1900,
        }.get(cost, 600)

        base_armor = {
            1: 25,
            2: 35,
            3: 45,
            4: 60,
            5: 80,
        }.get(cost, 30)

        base_mr = base_armor

        base_ad = {
            1: 45,
            2: 60,
            3: 80,
            4: 105,
            5: 150,
        }.get(cost, 50)

        base_as = {
            1: 0.65,
            2: 0.70,
            3: 0.75,
            4: 0.80,
            5: 0.90,
        }.get(cost, 0.7)

        # =====================================================
        # 🧬 TRAIT MODIFIERS
        # =====================================================

        if any(
            t in traits
            for t in ["Lutador", "Brawler"]
        ):
            base_hp *= 1.30
            base_ad *= 0.90

        if any(
            t in traits
            for t in [
                "Vanguarda",
                "Bastião",
                "Baluarte"
            ]
        ):
            base_armor *= 1.40
            base_mr *= 1.40

        if any(
            t in traits
            for t in [
                "Desafiante",
                "Atirador de Elite",
                "Tecelã do Destino"
            ]
        ):
            base_as *= 1.40
            base_ad *= 1.15

        if any(
            t in traits
            for t in [
                "Ladino",
                "Caçador de Galáxia"
            ]
        ):
            base_as *= 1.20
            base_ad *= 1.10
            base_hp *= 0.85

        if any(
            t in traits
            for t in [
                "Saqueador",
                "Mech"
            ]
        ):
            base_hp *= 1.15
            base_ad *= 1.10

        # =====================================================
        # ⚡ ABILITY SCALING
        # =====================================================

        for var in variables:

            name = (
                var.get("name", "")
                .lower()
            )

            values = var.get(
                "value",
                []
            )

            if not values:
                continue

            max_val = max(values)

            # =========================
            # DAMAGE
            # =========================

            if (
                "damage" in name
                or "dano" in name
            ):
                base_ad = max(
                    base_ad,
                    max_val / 8
                )

            # =========================
            # SHIELD
            # =========================

            if (
                "shield" in name
                or "escudo" in name
            ):
                base_hp *= 1.10

        # =====================================================
        # 🎯 RANGE DETECTION
        # =====================================================

        range_val = 1

        if (
            any(
                x in desc
                for x in (
                    "alcance",
                    "distância",
                    "linha",
                    "cônico",
                )
            )
            or
            any(
                t in traits
                for t in (
                    "Atirador de Elite",
                    "Tecelã do Destino",
                )
            )
        ):
            range_val = 3

        elif any(
            x in desc
            for x in (
                "projétil",
                "raio",
                "flecha",
            )
        ):
            range_val = 2

        elif "corpo a corpo" in desc:
            range_val = 1

        # =====================================================
        # ⭐ STAR SCALING
        # =====================================================

        star = unit.get("star", 1)

        if star == 2:
            base_hp *= 1.8
            base_ad *= 1.45

        elif star >= 3:
            base_hp *= 2.8
            base_ad *= 2.0

        # =====================================================
        # 📈 FINAL COMBAT STATS
        # =====================================================

        effective_hp = (
            base_hp
            * (
                1
                + (
                    base_armor
                    + base_mr
                ) * 0.008
            )
        )

        crit_chance = 0.25
        crit_dmg = 1.4

        crit_bonus = (
            1
            + crit_chance
            * (crit_dmg - 1)
        )

        dps = (
            base_ad
            * base_as
            * crit_bonus
        )

        # =====================================================
        # 💥 SPELL DAMAGE CONTRIBUTION
        # =====================================================

        for var in variables:

            if (
                "damage"
                in var.get("name", "").lower()
            ):

                dps += (
                    max(
                        var.get("value", [0])
                    ) / 8
                )

        # =====================================================
        # 💣 BURST
        # =====================================================

        burst = (
            base_ad * 1.8
            + cost * 12
        )

        for var in variables:

            if (
                "damage"
                in var.get("name", "").lower()
            ):

                burst += (
                    max(
                        var.get("value", [0])
                    ) / 3
                )

        # =====================================================
        # 🔮 MANA
        # =====================================================

        mana = (
            stats.get("mana")
            or 100
        )

        initial_mana = (
            stats.get("initialMana")
            or 0
        )

        mana_efficiency = (
            initial_mana
            / max(1, mana)
        )

        cast_frequency = (
            base_as * 0.6
            + mana_efficiency * 1.8
        )

        # =====================================================
        # 🛡️ DURABILITY
        # =====================================================

        durability = (
            effective_hp
            + base_armor * 6
            + base_mr * 6
        )

        # =====================================================
        # ⚔️ ATTACK TIMING
        # =====================================================

        attack_interval = max(
            0.45,
            1.6 - (base_as * 0.75)
        )

        # =====================================================
        # 🔥 THREAT
        # =====================================================

        threat = (
            dps * 0.55
            + burst * 0.35
            + range_val * 8
            + cost * 10
        )

        # =====================================================
        # FRONTLINE SCORE
        # =====================================================

        frontline_score = (
            durability * 0.7
            + base_ad * 1.2
        )

        if range_val == 1:
            frontline_score *= 1.35

        # =====================================================
        # BACKLINE SCORE
        # =====================================================

        backline_score = (
            dps * 0.8
            + burst * 0.5
            + range_val * 25
        )

        # =====================================================
        # 🎯 FINAL PROFILE
        # =====================================================

        return {

            # =========================
            # RAW STATS
            # =========================

            "hp": int(base_hp),

            "max_hp": int(base_hp),

            "ad": round(base_ad, 2),

            "armor": round(base_armor, 2),

            "magic_resist": round(
                base_mr,
                2
            ),

            "attack_speed": round(
                base_as,
                3
            ),

            "range": range_val,

            "attack_range": range_val,

            # =========================
            # COMBAT RUNTIME
            # =========================

            "attack_interval": round(
                attack_interval,
                3
            ),

            "durability": round(
                durability,
                2
            ),

            "effective_hp": round(
                effective_hp,
                2
            ),

            "dps": round(dps, 2),

            "burst": round(
                burst,
                2
            ),

            # =========================
            # UTILITY
            # =========================

            "mana_efficiency": round(
                mana_efficiency,
                3
            ),

            "cast_frequency": round(
                cast_frequency,
                3
            ),

            "mobility": 0,

            "threat": round(
                threat,
                2
            ),

            # =========================
            # POSITIONING
            # =========================

            "frontline_score": round(
                frontline_score,
                2
            ),

            "backline_score": round(
                backline_score,
                2
            ),

            # =========================
            # FLAGS
            # =========================

            "glass_cannon": (
                dps > 120
                and durability < 1200
            ),

            "cost": cost,

            "star": star,
        }

    # =========================================================
    # Os helpers `is_tank`, `get_main_carry`, etc. permanecem iguais.
    # =========================================================
    # (copie da versão anterior, são idênticos)
    def is_tank(self, unit):
        return unit.get("role") == UnitRole.TANK

    def is_carry(self, unit):
        return unit.get("role") == UnitRole.CARRY

    def is_support(self, unit):
        return unit.get("role") == UnitRole.SUPPORT

    def is_fighter(self, unit):
        return unit.get("role") == UnitRole.FIGHTER

    def is_assassin(self, unit):
        return unit.get("role") == UnitRole.ASSASSIN

    def is_frontline(self, row):
        return row in self.FRONT_ROWS

    def is_backline(self, row):
        return row in self.BACK_ROWS

    def is_fragile(self, unit):
        profile = unit.get("combat_profile", {})
        return profile.get("durability", 0) < 900 and unit.get("role") in (UnitRole.CARRY, UnitRole.SUPPORT, UnitRole.ASSASSIN)

    def get_main_carry(self, board, impact_fn):
        # ... (igual)
        best_score = -999999
        best_data = None
        for row in range(4):
            for col in range(7):
                unit = board[row][col]
                if not unit:
                    continue
                score = impact_fn(unit)
                if self.is_carry(unit):
                    score *= 1.4
                score += unit.get("cost", 1) * 0.25
                if score > best_score:
                    best_score = score
                    best_data = (row, col, unit)
        return best_data

    def evaluate_positioning(self, board, impact_fn=None):
        # ... (igual)
        reward = 0.0
        carries = []
        tanks = []
        for row in range(4):
            for col in range(7):
                unit = board[row][col]
                if not unit:
                    continue
                if self.is_carry(unit):
                    carries.append((row, col, unit))
                elif self.is_tank(unit):
                    tanks.append((row, col, unit))
        for row, col, unit in carries:
            if self.is_backline(row):
                reward += 0.4
            else:
                reward -= 0.9
            if self.is_fragile(unit) and self.is_frontline(row):
                reward -= 1.2
            protected = any(t_row < row and abs(t_col - col) <= 1 for t_row, t_col, _ in tanks)
            reward += 0.6 if protected else -0.45
        for row, col, unit in tanks:
            reward += 0.3 if self.is_frontline(row) else -0.7
        return reward

    def evaluate_main_carry_safety(self, board, impact_fn):
        # ... (igual)
        carry_data = self.get_main_carry(board, impact_fn)
        if not carry_data:
            return 0.0
        row, col, unit = carry_data
        reward = 1.0 if self.is_backline(row) else -2.0
        nearby_allies = 0
        for dc in (-1, 1):
            nc = col + dc
            if 0 <= nc < 7 and board[row][nc]:
                nearby_allies += 1
        reward += nearby_allies * 0.25
        frontline_count = 0
        for r in self.FRONT_ROWS:
            for c in range(7):
                front = board[r][c]
                if front and self.is_tank(front):
                    frontline_count += 1
        reward += min(frontline_count, 4) * 0.2
        return reward

    def get_role(self, unit):
        if not unit:
            return None
        role = unit.get("role")
        if role is not None:
            return role
        role = self._infer_unit_role(unit)
        unit["role"] = role
        return role