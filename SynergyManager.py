import json

class SynergyManager:
    def __init__(self, trait_path):
        self.traits_data = self._load_json(trait_path)

        # milestones: { "Mage": [3,5,7] }
        self.milestones = {}
        self._build_milestones()

        # Estado atual
        self.active_traits = {}   # atingiu milestone
        self.partial_traits = {}  # quase ativando

    def _load_json(self, path):
        try:
            with open(path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                return data['traits'] if isinstance(data, dict) and 'traits' in data else data
        except Exception as e:
            print(f"Erro ao carregar traits.json: {e}")
            return []

    def _build_milestones(self):
            for t in self.traits_data:
                # Verifica se 'effects' existe e é uma lista
                if 'effects' in t and isinstance(t['effects'], list):
                    # Usamos .get('minUnits') para evitar o KeyError caso a chave não exista
                    m_list = []
                    for eff in t['effects']:
                        if isinstance(eff, dict) and 'minUnits' in eff:
                            m_list.append(eff['minUnits'])
                    
                    if m_list:
                        self.milestones[t['name']] = sorted(m_list)

    # =========================================================
    # 🔥 UPDATE (CORE)
    # =========================================================
    def update(self, board):
        """
        Atualiza:
        - active_traits → só sinergias ativas (milestone atingido)
        - partial_traits → faltando 1 unidade pra ativar
        """
        traits_count = {}
        seen_ids = set()

        # Conta unidades únicas
        for row in board:
            for u in row:
                if u and u["id"] not in seen_ids:
                    seen_ids.add(u["id"])
                    for t in u.get("traits", []):
                        traits_count[t] = traits_count.get(t, 0) + 1

        active = {}
        partial = {}

        for trait, count in traits_count.items():
            if trait not in self.milestones:
                continue

            milestones = self.milestones[trait]

            reached = sum(1 for m in milestones if count >= m)

            # ✅ ATIVA
            if reached > 0:
                active[trait] = count

            # ✅ QUASE (faltando 1 unidade pra próximo nível)
            else:
                for m in milestones:
                    if count == m - 1:
                        partial[trait] = count
                        break

        self.active_traits = active
        self.partial_traits = partial

    # =========================================================
    # 🔥 MULTIPLICADOR GLOBAL (COMBATE)
    # =========================================================
    def calculate_multiplier(self, active_traits=None):
        """
        Multiplicador total do board (usado no power).
        """
        source = active_traits if active_traits is not None else self.active_traits

        total_mult = 1.0

        for name, count in source.items():
            if name in self.milestones:
                reached = sum(1 for m in self.milestones[name] if count >= m)

                if reached > 0:
                    bonus = (reached ** 1.8) * 0.20
                    total_mult += bonus

        return total_mult

    # =========================================================
    # 🔥 MULTIPLIERS INDIVIDUAIS
    # =========================================================
    def get_all_multipliers(self, active_traits_input=None):
        source = active_traits_input if active_traits_input is not None else self.active_traits

        multipliers = {}

        for name in self.milestones.keys():
            count = source.get(name, 0)
            reached = sum(1 for m in self.milestones[name] if count >= m)

            if reached > 0:
                multipliers[name] = 1.0 + ((reached ** 1.8) * 0.20)
            else:
                multipliers[name] = 1.0

        return multipliers

    # =========================================================
    # 🔥 NÍVEL DA TRAIT
    # =========================================================
    def get_trait_level(self, trait_name, count):
        if trait_name in self.milestones:
            return sum(1 for m in self.milestones[trait_name] if count >= m)
        return 0

    # =========================================================
    # 🔥 BONUS
    # =========================================================
    def get_unit_synergy_bonus(self, unit, comp_focus=None):
        """
        Calcula o bônus de sinergia de UMA unidade.

        - Usa active_traits e partial_traits
        - Escala com nível real da sinergia (milestones)
        - Considera direção de comp (comp_focus)
        """

        if not unit:
            return 0.0

        bonus = 0.0

        for trait in unit.get("traits", []):
            count = self.active_traits.get(trait, 0)

            # 🔥 nível real da trait (0,1,2,3...)
            level = self.get_trait_level(trait, count)

            # =========================
            # ✅ SINERGIA ATIVA
            # =========================
            if level > 0:
                # escala com nível real
                trait_bonus = 1.0 + (level * 0.9)

                # bônus extra por "stack" (ex: 6 unidades > 2 unidades)
                trait_bonus += count * 0.15

            # =========================
            # 🟡 QUASE ATIVA
            # =========================
            elif trait in self.partial_traits:
                # recompensa por estar perto
                trait_bonus = 0.6 + (self.partial_traits[trait] * 0.2)

            # =========================
            # ❌ FORA DA COMP
            # =========================
            else:
                trait_bonus = -0.25

            # =========================
            # 🧠 COMP FOCUS (MEMÓRIA)
            # =========================
            if comp_focus:
                focus_strength = comp_focus.get(trait, 0)

                if focus_strength > 0:
                    # boost progressivo (não explode)
                    trait_bonus *= (1.0 + min(0.5, focus_strength * 0.08))
                else:
                    trait_bonus *= 0.85  # leve penalidade fora da direção

            bonus += trait_bonus

        return bonus