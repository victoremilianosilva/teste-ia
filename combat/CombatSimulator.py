# ⚔️ combat/CombatSimulator.py
#
# Simula uma batalha PvP entre dois jogadores.
#
# IMPORTANTE:
#
# CombatSimulator NÃO:
#   ❌ altera HP
#   ❌ altera gold
#   ❌ altera streak
#   ❌ elimina jogador
#   ❌ avança round
#
# Ele apenas:
#
#   Player A board
#          │
#          ├─────── Combat ───────┐
#          │                      │
#   Player B board               │
#          │                      │
#          └──── CombatResult ◄───┘
#
# O TFTLobby é responsável por aplicar o resultado.


from dataclasses import dataclass
from copy import deepcopy
import math
import random


@dataclass
class CombatResult:
    """
    Resultado de uma batalha PvP.
    """

    winner_id: int
    loser_id: int

    player_a_alive: int
    player_b_alive: int

    damage_to_a: int
    damage_to_b: int

    duration: float

    player_a_power: float
    player_b_power: float

    player_a_damage_dealt: float
    player_b_damage_dealt: float

    timeout: bool = False

    def is_draw(self):
        return self.winner_id == -1

    def get_damage_for(self, player_id):
        if player_id == self.winner_id:
            return self.damage_to_b

        if player_id == self.loser_id:
            return self.damage_to_a

        return 0


class CombatSimulator:

    def __init__(
        self,
        combat_profile_mgr=None,
        max_duration=30.0,
        tick_rate=0.25,
        randomize_positions=True,
    ):
        self.combat_profile_mgr = combat_profile_mgr

        # ⏱️ Tempo máximo da batalha.
        self.max_duration = max_duration

        # ⏱️ Cada tick representa aproximadamente
        # 250ms de combate.
        self.tick_rate = tick_rate

        self.randomize_positions = randomize_positions

    # ============================================================
    # ⚔️ PUBLIC API
    # ============================================================

    def simulate(self, player_a, player_b):
        """
        Simula uma batalha entre dois MiniTFTEnv.

        Retorna:
            CombatResult
        """

        board_a = self._get_board(player_a)
        board_b = self._get_board(player_b)

        units_a = self._prepare_units(board_a, player_id=0)
        units_b = self._prepare_units(board_b, player_id=1)

        # 💤 Se um dos boards estiver vazio.
        if not units_a and not units_b:
            return self._draw_result(
                player_a,
                player_b,
                0.0,
                0.0,
            )

        if not units_a:
            return self._automatic_loss(
                player_a,
                player_b,
                units_a,
                units_b,
            )

        if not units_b:
            return self._automatic_loss(
                player_b,
                player_a,
                units_b,
                units_a,
            )

        time = 0.0

        total_damage_a = 0.0
        total_damage_b = 0.0

        # ========================================================
        # 🔄 LOOP DE COMBATE
        # ========================================================

        while time < self.max_duration:

            alive_a = self._alive_units(units_a)
            alive_b = self._alive_units(units_b)

            if not alive_a:
                return self._build_result(
                    winner_id=1,
                    loser_id=0,
                    units_a=units_a,
                    units_b=units_b,
                    damage_a=total_damage_a,
                    damage_b=total_damage_b,
                    duration=time,
                    power_a=self._calculate_team_power(units_a),
                    power_b=self._calculate_team_power(units_b),
                )

            if not alive_b:
                return self._build_result(
                    winner_id=0,
                    loser_id=1,
                    units_a=units_a,
                    units_b=units_b,
                    damage_a=total_damage_a,
                    damage_b=total_damage_b,
                    duration=time,
                    power_a=self._calculate_team_power(units_a),
                    power_b=self._calculate_team_power(units_b),
                )

            # ====================================================
            # 🎯 CADA UNIDADE ESCOLHE UM ALVO
            # ====================================================

            targets_a = self._select_targets(
                alive_a,
                alive_b,
            )

            targets_b = self._select_targets(
                alive_b,
                alive_a,
            )

            # ====================================================
            # ⚔️ CALCULAR DANO
            # ====================================================

            attacks_a = self._calculate_attacks(
                alive_a,
                targets_a,
            )

            attacks_b = self._calculate_attacks(
                alive_b,
                targets_b,
            )

            # ====================================================
            # 💥 APLICAR ATAQUES SIMULTANEAMENTE
            # ====================================================

            damage_a = self._apply_attacks(
                attacks_a,
                alive_b,
            )

            damage_b = self._apply_attacks(
                attacks_b,
                alive_a,
            )

            total_damage_b += damage_a
            total_damage_a += damage_b

            time += self.tick_rate

        # ========================================================
        # ⏱️ TIMEOUT
        # ========================================================

        alive_a = self._alive_units(units_a)
        alive_b = self._alive_units(units_b)

        power_a = self._calculate_remaining_power(alive_a)
        power_b = self._calculate_remaining_power(alive_b)

        if power_a > power_b:
            winner_id = 0
            loser_id = 1

        elif power_b > power_a:
            winner_id = 1
            loser_id = 0

        else:
            winner_id = -1
            loser_id = -1

        if winner_id == -1:
            return self._draw_result(
                player_a,
                player_b,
                total_damage_a,
                total_damage_b,
                duration=time,
                power_a=power_a,
                power_b=power_b,
                timeout=True,
            )

        return self._build_result(
            winner_id=winner_id,
            loser_id=loser_id,
            units_a=units_a,
            units_b=units_b,
            damage_a=total_damage_a,
            damage_b=total_damage_b,
            duration=time,
            power_a=power_a,
            power_b=power_b,
            timeout=True,
        )

    # ============================================================
    # 📦 BOARD
    # ============================================================

    def _get_board(self, player):
        """
        Aceita:
            MiniTFTEnv
            BoardManager
            lista diretamente
        """

        if player is None:
            return []

        # MiniTFTEnv
        board_manager = getattr(
            player,
            "board_manager",
            None,
        )

        if board_manager is not None:
            board = getattr(
                board_manager,
                "board",
                None,
            )

            if board is not None:
                return board

        # Compatibilidade temporária
        board = getattr(player, "board", None)

        if board is not None:
            return board

        return []

    # ============================================================
    # 🧬 PREPARAR UNIDADES
    # ============================================================

    def _prepare_units(self, board, player_id):
        """
        Cria uma cópia de combate das unidades.

        Nunca altera a unidade original do jogador.
        """

        units = []

        for position, unit in enumerate(board):

            if unit is None:
                continue

            if not isinstance(unit, dict):
                continue

            combat_unit = deepcopy(unit)

            combat_unit["_combat_id"] = (
                f"{player_id}:{position}:"
                f"{unit.get('uuid', position)}"
            )

            combat_unit["_player_id"] = player_id
            combat_unit["_position"] = position

            combat_unit["_alive"] = True

            # ❤️ HP
            combat_unit["_hp"] = self._get_max_hp(
                combat_unit
            )

            combat_unit["_max_hp"] = combat_unit["_hp"]

            # ⏱️ Controle de ataque
            combat_unit["_attack_timer"] = 0.0

            units.append(combat_unit)

        return units

    # ============================================================
    # ❤️ STATS
    # ============================================================

    def _get_max_hp(self, unit):
        profile = unit.get("combat_profile", {})

        hp = (
            profile.get("hp")
            or profile.get("health")
            or unit.get("hp")
            or unit.get("health")
        )

        if hp is None:
            hp = self._default_hp(unit)

        star = unit.get("star", 1)

        # ⭐ Escalonamento simples por estrela.
        multiplier = {
            1: 1.0,
            2: 1.75,
            3: 3.0,
        }.get(star, 1.0)

        return max(
            1.0,
            float(hp) * multiplier
        )

    def _default_hp(self, unit):
        """
        Fallback caso units.json ainda não possua
        informações completas de combate.
        """

        cost = float(
            unit.get("cost", 1)
        )

        return 500.0 + (
            cost * 100.0
        )

    def _get_attack_damage(self, unit):
        profile = unit.get("combat_profile", {})

        damage = (
            profile.get("attack_damage")
            or profile.get("damage")
            or profile.get("ad")
            or unit.get("attack_damage")
            or unit.get("damage")
        )

        if damage is None:
            damage = (
                50.0
                + float(unit.get("cost", 1)) * 10.0
            )

        star = unit.get("star", 1)

        multiplier = {
            1: 1.0,
            2: 1.5,
            3: 2.25,
        }.get(star, 1.0)

        return float(damage) * multiplier

    def _get_defense(self, unit):
        profile = unit.get("combat_profile", {})

        defense = (
            profile.get("armor")
            or profile.get("defense")
            or profile.get("resistance")
            or unit.get("armor")
        )

        if defense is None:
            defense = 20.0

        star = unit.get("star", 1)

        return float(defense) * (
            1.0 + (star - 1) * 0.5
        )

    def _get_attack_speed(self, unit):
        profile = unit.get("combat_profile", {})

        speed = (
            profile.get("attack_speed")
            or profile.get("as")
            or unit.get("attack_speed")
        )

        if speed is None:
            speed = 1.0

        return max(
            0.25,
            float(speed)
        )

    def _get_range(self, unit):
        profile = unit.get("combat_profile", {})

        attack_range = (
            profile.get("range")
            or profile.get("attack_range")
            or unit.get("range")
        )

        if attack_range is None:
            attack_range = 1

        return max(
            1,
            int(attack_range)
        )

    # ============================================================
    # 🎯 TARGET SELECTION
    # ============================================================

    def _select_targets(
        self,
        attackers,
        enemies,
    ):
        """
        Cada unidade escolhe um alvo.

        Prioridade:
            1. alvo válido mais próximo
            2. menor HP
            3. maior ameaça
        """

        targets = {}

        alive_enemies = self._alive_units(
            enemies
        )

        if not alive_enemies:
            return targets

        for attacker in attackers:

            if not attacker.get("_alive", False):
                continue

            target = self._select_target(
                attacker,
                alive_enemies,
            )

            if target is not None:
                targets[
                    attacker["_combat_id"]
                ] = target

        return targets

    def _select_target(
        self,
        attacker,
        enemies,
    ):
        if not enemies:
            return None

        attacker_position = attacker.get(
            "_position",
            0,
        )

        attacker_row = attacker_position // 7
        attacker_col = attacker_position % 7

        attack_range = self._get_range(
            attacker
        )

        candidates = []

        for enemy in enemies:

            enemy_position = enemy.get(
                "_position",
                0,
            )

            enemy_row = enemy_position // 7
            enemy_col = enemy_position % 7

            distance = (
                abs(attacker_row - enemy_row)
                + abs(attacker_col - enemy_col)
            )

            if distance > attack_range:
                # 📍 Ainda pode ser escolhido como alvo
                # caso nenhum alvo esteja no alcance.
                pass

            hp = enemy.get(
                "_hp",
                1.0,
            )

            threat = self._calculate_threat(
                enemy
            )

            candidates.append(
                (
                    distance,
                    hp,
                    -threat,
                    enemy,
                )
            )

        # 🎯 Prioriza distância.
        # Depois HP.
        candidates.sort(
            key=lambda item: (
                item[0],
                item[1],
                item[2],
            )
        )

        return candidates[0][3]

    def _calculate_threat(self, unit):
        damage = self._get_attack_damage(unit)
        speed = self._get_attack_speed(unit)

        return damage * speed

    # ============================================================
    # ⚔️ ATAQUES
    # ============================================================

    def _calculate_attacks(
        self,
        attackers,
        targets,
    ):
        attacks = []

        for attacker in attackers:

            if not attacker.get("_alive", False):
                continue

            combat_id = attacker.get(
                "_combat_id"
            )

            target = targets.get(
                combat_id
            )

            if target is None:
                continue

            # ⏱️ Cooldown
            attacker["_attack_timer"] -= (
                self.tick_rate
            )

            if attacker["_attack_timer"] > 0:
                continue

            attack_speed = self._get_attack_speed(
                attacker
            )

            attacker["_attack_timer"] = (
                1.0 / attack_speed
            )

            damage = self._calculate_damage(
                attacker,
                target,
            )

            attacks.append(
                (
                    attacker,
                    target,
                    damage,
                )
            )

        return attacks

    def _calculate_damage(
        self,
        attacker,
        target,
    ):
        attack_damage = self._get_attack_damage(
            attacker
        )

        defense = self._get_defense(
            target
        )

        # 🛡️ Redução de dano simples.
        mitigation = 100.0 / (
            100.0 + max(0.0, defense)
        )

        damage = (
            attack_damage
            * mitigation
            * self.tick_rate
        )

        return max(
            1.0,
            damage
        )

    def _apply_attacks(
        self,
        attacks,
        enemies,
    ):
        total_damage = 0.0

        for attacker, target, damage in attacks:

            if not attacker.get("_alive", False):
                continue

            if not target.get("_alive", False):
                continue

            target["_hp"] -= damage

            total_damage += damage

            if target["_hp"] <= 0:

                target["_hp"] = 0.0
                target["_alive"] = False

        return total_damage

    # ============================================================
    # 💪 POWER
    # ============================================================

    def _calculate_team_power(self, units):
        power = 0.0

        for unit in units:

            if unit is None:
                continue

            hp = self._get_max_hp(unit)
            damage = self._get_attack_damage(unit)
            defense = self._get_defense(unit)
            speed = self._get_attack_speed(unit)

            power += (
                hp * 0.01
                + damage * speed * 0.5
                + defense * 0.25
            )

        return power

    def _calculate_remaining_power(self, units):
        power = 0.0

        for unit in units:

            if not unit.get("_alive", False):
                continue

            max_hp = unit.get(
                "_max_hp",
                1.0,
            )

            hp = unit.get(
                "_hp",
                0.0,
            )

            hp_ratio = (
                hp / max_hp
                if max_hp > 0
                else 0.0
            )

            power += (
                self._get_attack_damage(unit)
                * self._get_attack_speed(unit)
                * hp_ratio
            )

            power += (
                self._get_defense(unit)
                * 0.2
            )

        return power

    # ============================================================
    # ❤️ ALIVE
    # ============================================================

    @staticmethod
    def _alive_units(units):
        return [
            unit
            for unit in units
            if unit.get("_alive", False)
        ]

    # ============================================================
    # 📊 RESULT
    # ============================================================

    def _build_result(
        self,
        winner_id,
        loser_id,
        units_a,
        units_b,
        damage_a,
        damage_b,
        duration,
        power_a,
        power_b,
        timeout=False,
    ):
        alive_a = self._alive_units(
            units_a
        )

        alive_b = self._alive_units(
            units_b
        )

        # 💥 Dano de sobrevivência.
        #
        # Quanto mais unidades sobreviventes,
        # maior o dano aplicado ao perdedor.
        if winner_id == 0:
            damage_to_b = self._calculate_final_damage(
                alive_a
            )
            damage_to_a = 0

        elif winner_id == 1:
            damage_to_a = self._calculate_final_damage(
                alive_b
            )
            damage_to_b = 0

        else:
            damage_to_a = 0
            damage_to_b = 0

        return CombatResult(
            winner_id=winner_id,
            loser_id=loser_id,

            player_a_alive=len(alive_a),
            player_b_alive=len(alive_b),

            damage_to_a=int(damage_to_a),
            damage_to_b=int(damage_to_b),

            duration=float(duration),

            player_a_power=float(power_a),
            player_b_power=float(power_b),

            player_a_damage_dealt=float(damage_b),
            player_b_damage_dealt=float(damage_a),

            timeout=timeout,
        )

    def _draw_result(
        self,
        player_a,
        player_b,
        damage_a,
        damage_b,
        duration=0.0,
        power_a=0.0,
        power_b=0.0,
        timeout=False,
    ):
        return CombatResult(
            winner_id=-1,
            loser_id=-1,

            player_a_alive=0,
            player_b_alive=0,

            damage_to_a=0,
            damage_to_b=0,

            duration=float(duration),

            player_a_power=float(power_a),
            player_b_power=float(power_b),

            player_a_damage_dealt=float(
                damage_a
            ),
            player_b_damage_dealt=float(
                damage_b
            ),

            timeout=timeout,
        )

    def _automatic_loss(
        self,
        loser_player,
        winner_player,
        loser_units,
        winner_units,
    ):
        winner_id = 1 if not loser_units else 0
        loser_id = 0 if not loser_units else 1

        winner_alive = len(
            self._alive_units(
                winner_units
            )
        )

        damage = max(
            1,
            self._calculate_final_damage(
                self._alive_units(
                    winner_units
                )
            )
        )

        if loser_units:
            # Caso extremamente improvável:
            # fallback defensivo.
            damage = 1

        if winner_id == 0:
            return CombatResult(
                winner_id=0,
                loser_id=1,

                player_a_alive=winner_alive,
                player_b_alive=0,

                damage_to_a=0,
                damage_to_b=damage,

                duration=0.0,

                player_a_power=self._calculate_team_power(
                    winner_units
                ),
                player_b_power=0.0,

                player_a_damage_dealt=float(damage),
                player_b_damage_dealt=0.0,
            )

        return CombatResult(
            winner_id=1,
            loser_id=0,

            player_a_alive=0,
            player_b_alive=winner_alive,

            damage_to_a=damage,
            damage_to_b=0,

            duration=0.0,

            player_a_power=0.0,
            player_b_power=self._calculate_team_power(
                winner_units
            ),

            player_a_damage_dealt=0.0,
            player_b_damage_dealt=float(damage),
        )

    def _calculate_final_damage(self, alive_units):
        """
        Dano recebido pelo jogador perdedor.

        Por enquanto usamos:
            número de unidades sobreviventes
            + pequena contribuição do custo/estrela.

        Depois podemos ligar isso ao StageDamage
        do GameConfig.
        """

        if not alive_units:
            return 1

        damage = 1

        for unit in alive_units:

            cost = int(
                unit.get("cost", 1)
            )

            star = int(
                unit.get("star", 1)
            )

            damage += cost

            if star >= 2:
                damage += 1

            if star >= 3:
                damage += 1

        return max(
            1,
            damage
        )

    # ============================================================
    # 🐛 DEBUG
    # ============================================================

    def debug_result(self, result):
        print("\n========== COMBAT RESULT ==========")

        if result.is_draw():
            print("⚖️ RESULTADO: EMPATE")
        else:
            print(
                f"🏆 VENCEDOR: Player "
                f"{result.winner_id}"
            )

            print(
                f"💀 PERDEDOR: Player "
                f"{result.loser_id}"
            )

        print(
            f"❤️ Player A alive: "
            f"{result.player_a_alive}"
        )

        print(
            f"❤️ Player B alive: "
            f"{result.player_b_alive}"
        )

        print(
            f"💥 Damage A: "
            f"{result.damage_to_a}"
        )

        print(
            f"💥 Damage B: "
            f"{result.damage_to_b}"
        )

        print(
            f"⚔️ Power A: "
            f"{result.player_a_power:.2f}"
        )

        print(
            f"⚔️ Power B: "
            f"{result.player_b_power:.2f}"
        )

        print(
            f"⏱️ Duration: "
            f"{result.duration:.2f}s"
        )

        print(
            f"⌛ Timeout: "
            f"{result.timeout}"
        )

        print("===================================")