# 🤖 ai/RewardManager.py
#
# Responsável exclusivamente pela recompensa do jogador.
#
# IMPORTANTE:
# O RewardManager NÃO aplica dano, NÃO altera HP,
# NÃO altera gold e NÃO executa combate.
#
# Ele apenas recebe informações do estado/resultado
# e calcula a recompensa.
#
# Fluxo:
#
# CombatSimulator
#       ↓
#   CombatResult
#       ↓
#     Lobby
#       ↓
# RewardManager.calculate_combat_reward()
#       ↓
#      PPO
#

import math


class RewardManager:

    def __init__(
        self,
        economy_manager,
        composition_manager,
        positioning_manager,
    ):
        self.economy_manager = economy_manager
        self.composition_manager = composition_manager
        self.positioning_manager = positioning_manager

        # 🧠 Estado anterior utilizado para calcular deltas.
        self.previous_board_power = 0.0
        self.previous_positioning_score = 0.0
        self.previous_synergy_score = 0.0
        self.previous_level = 1
        self.previous_gold = 0

        # ⚔️ Resultado do último combate
        self.last_combat_reward = 0.0

        # 📊 Estatísticas
        self.total_reward = 0.0
        self.round_reward = 0.0

    # ============================================================
    # 🔄 RESET
    # ============================================================

    def reset(self):
        self.previous_board_power = 0.0
        self.previous_positioning_score = 0.0
        self.previous_synergy_score = 0.0

        self.previous_level = 1
        self.previous_gold = 0

        self.last_combat_reward = 0.0

        self.total_reward = 0.0
        self.round_reward = 0.0

    # ============================================================
    # ⚔️ COMBATE
    # ============================================================

    def calculate_combat_reward(
        self,
        won,
        damage_dealt=0,
        damage_taken=0,
        enemy_alive=0,
        own_alive=0,
    ):
        """
        Calcula recompensa referente ao combate.

        O combate em si NÃO é executado aqui.

        Parâmetros:
            won:
                True se venceu.

            damage_dealt:
                Dano causado ao adversário.

            damage_taken:
                Dano recebido.

            enemy_alive:
                Quantidade de unidades inimigas sobreviventes.

            own_alive:
                Quantidade de unidades próprias sobreviventes.
        """

        reward = 0.0

        # 🏆 Vitória
        if won:
            reward += 2.0

        # 💀 Derrota
        else:
            reward -= 2.0

        # ⚔️ Dano causado
        if damage_dealt > 0:
            reward += min(
                math.tanh(damage_dealt / 10.0),
                1.0
            )

        # 🛡️ Sobrevivência das próprias unidades
        if own_alive > 0:
            reward += min(
                own_alive * 0.05,
                0.25
            )

        # ☠️ Sobrevivência inimiga
        if enemy_alive > 0:
            reward -= min(
                enemy_alive * 0.05,
                0.25
            )

        # 💔 Penalidade por dano recebido
        if damage_taken > 0:
            reward -= min(
                math.tanh(damage_taken / 15.0),
                0.75
            )

        self.last_combat_reward = reward

        return reward

    # ============================================================
    # 📈 POWER DELTA
    # ============================================================

    def calculate_power_reward(self, current_power):
        """
        Recompensa baseada na evolução da força do board.

        Não recompensa simplesmente ter board forte.
        Recompensa evolução.
        """

        current_power = float(current_power)

        delta = (
            current_power
            - self.previous_board_power
        )

        self.previous_board_power = current_power

        if abs(delta) < 1e-6:
            return 0.0

        # 📉 Evita valores absurdamente grandes.
        return math.tanh(delta / 10.0)

    # ============================================================
    # 🧩 SYNERGY
    # ============================================================

    def calculate_synergy_reward(self, synergy_score):
        """
        Recompensa evolução das sinergias.
        """

        synergy_score = float(synergy_score)

        delta = (
            synergy_score
            - self.previous_synergy_score
        )

        self.previous_synergy_score = synergy_score

        return math.tanh(delta)

    # ============================================================
    # 📍 POSITIONING
    # ============================================================

    def calculate_positioning_reward(self, positioning_score):
        """
        Recompensa melhoria de posicionamento.
        """

        positioning_score = float(positioning_score)

        delta = (
            positioning_score
            - self.previous_positioning_score
        )

        self.previous_positioning_score = positioning_score

        # Pequena influência.
        return math.tanh(delta) * 0.5

    # ============================================================
    # ⭐ LEVEL
    # ============================================================

    def calculate_level_reward(self, level):
        """
        Recompensa mudança de nível.

        Level up é positivo, mas propositalmente
        não recebe recompensa enorme.
        """

        level = int(level)

        if level <= self.previous_level:
            return 0.0

        delta = level - self.previous_level

        self.previous_level = level

        return min(
            delta * 0.5,
            1.5
        )

    # ============================================================
    # 💰 ECONOMIA
    # ============================================================

    def calculate_economy_reward(
        self,
        gold,
        level,
        hp,
    ):
        """
        Pequena recompensa pela saúde econômica.

        Não tenta ensinar uma estratégia específica.
        """

        gold = float(gold)
        level = int(level)
        hp = float(hp)

        reward = 0.0

        # 💰 Interesse
        if gold >= 10:
            reward += 0.05

        if gold >= 20:
            reward += 0.05

        if gold >= 30:
            reward += 0.05

        if gold >= 40:
            reward += 0.05

        if gold >= 50:
            reward += 0.05

        # ❤️ HP continua sendo importante.
        if hp <= 15:
            reward -= 0.15

        elif hp <= 30:
            reward -= 0.05

        return reward

    # ============================================================
    # 🔥 STREAK
    # ============================================================

    def calculate_streak_reward(
        self,
        win_streak,
        loss_streak,
    ):
        """
        Pequena recompensa por manter uma sequência.

        Não é grande o suficiente para fazer a IA
        sacrificar o board apenas para manter streak.
        """

        reward = 0.0

        if win_streak >= 2:
            reward += min(
                win_streak * 0.03,
                0.15
            )

        if loss_streak >= 2:
            reward += min(
                loss_streak * 0.02,
                0.10
            )

        return reward

    # ============================================================
    # 🧱 BOARD
    # ============================================================

    def calculate_board_reward(
        self,
        board_units,
        max_board_units,
    ):
        """
        Pequeno incentivo para ocupar o board.

        Evita recompensar simplesmente qualquer unidade.
        """

        if max_board_units <= 0:
            return 0.0

        occupied = len([
            unit
            for unit in board_units
            if unit is not None
        ])

        ratio = occupied / float(max_board_units)

        return ratio * 0.15

    # ============================================================
    # 🎯 AÇÃO
    # ============================================================

    def calculate_action_reward(
        self,
        action_type,
        action_success,
        action_value=0.0,
    ):
        """
        Recompensa/penalidade pequena pela qualidade
        da ação executada.

        O objetivo é evitar que o agente fique executando
        ações inúteis.
        """

        if not action_success:
            return -0.10

        reward = 0.0

        # Valor calculado pelo ambiente/manager.
        reward += float(action_value)

        return reward

    # ============================================================
    # 🧠 REWARD TOTAL
    # ============================================================

    def calculate_total_reward(
        self,
        combat_reward=0.0,
        power_reward=0.0,
        synergy_reward=0.0,
        positioning_reward=0.0,
        level_reward=0.0,
        economy_reward=0.0,
        streak_reward=0.0,
        board_reward=0.0,
        action_reward=0.0,
    ):
        """
        Junta os componentes da recompensa.

        Os pesos são deliberadamente moderados.
        """

        reward = (
            combat_reward
            + power_reward
            + synergy_reward
            + positioning_reward
            + level_reward
            + economy_reward
            + streak_reward
            + board_reward
            + action_reward
        )

        # 🛡️ Limita valores extremos.
        reward = max(
            -5.0,
            min(5.0, reward)
        )

        self.round_reward = reward
        self.total_reward += reward

        return reward

    # ============================================================
    # 📊 ESTADO
    # ============================================================

    def get_state(self):
        return {
            "previous_board_power": self.previous_board_power,
            "previous_positioning_score": self.previous_positioning_score,
            "previous_synergy_score": self.previous_synergy_score,
            "previous_level": self.previous_level,
            "previous_gold": self.previous_gold,
            "last_combat_reward": self.last_combat_reward,
            "round_reward": self.round_reward,
            "total_reward": self.total_reward,
        }

    # ============================================================
    # 🐛 DEBUG
    # ============================================================

    def debug_print(self):
        print("\n========== REWARD MANAGER ==========")

        print(
            f"Last Combat Reward: "
            f"{self.last_combat_reward:+.3f}"
        )

        print(
            f"Round Reward: "
            f"{self.round_reward:+.3f}"
        )

        print(
            f"Total Reward: "
            f"{self.total_reward:+.3f}"
        )

        print(
            f"Previous Board Power: "
            f"{self.previous_board_power:.3f}"
        )

        print(
            f"Previous Positioning: "
            f"{self.previous_positioning_score:.3f}"
        )

        print(
            f"Previous Synergy: "
            f"{self.previous_synergy_score:.3f}"
        )

        print("====================================")