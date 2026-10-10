# ============================================================
# 🎮 env.py
#
# MiniTFTEnv
#
# Responsabilidade:
# - Estado individual de um jogador
# - Coordenar os managers
# - Executar ações
# - Construir observation
#
# NÃO controla:
# ❌ os 8 jogadores
# ❌ matchmaking
# ❌ combate global
# ❌ dano global
# ❌ round global
# ❌ UnitPool global
# ============================================================

from copy import deepcopy
from pathlib import Path
import random

import numpy as np

from config.GameConfig import GameConfig

from units.UnitManager import UnitManager
from units.BoardManager import BoardManager
from units.BenchManager import BenchManager

from shop.ShopManager import ShopManager

from economy.EconomyManager import EconomyManager

from strategy.StrategyManager import StrategyManager
from strategy.CompositionManager import CompositionManager
from strategy.PositioningManager import PositioningManager

from ai.AntiLoopManager import AntiLoopManager
from ai.ActionMaskManager import ActionMaskManager, ActionType
from ai.RewardManager import RewardManager

from SynergyManager import SynergyManager
from combat.CombatProfileManager import CombatProfileManager, UnitRole
class MiniTFTEnv:

    # ============================================================
    # 🔧 INIT
    # ============================================================

    def __init__(
        self,
        units_path=None,
        traits_path=None,
        unit_manager=None,
        unit_pool=None,
        player_id=0,
        lobby=None,
    ):
        self.player_id = player_id
        self.lobby = lobby

        # --------------------------------------------------------
        # 📁 CONFIG
        # --------------------------------------------------------

        self.units_path = Path(
            units_path or GameConfig.UNITS_PATH
        )

        self.traits_path = Path(
            traits_path or GameConfig.TRAITS_PATH
        )

        self.rows = GameConfig.BOARD_ROWS
        self.cols = GameConfig.BOARD_COLS

        self.board_size = GameConfig.BOARD_SIZE
        self.max_bench = GameConfig.MAX_BENCH
        self.shop_size = GameConfig.SHOP_SIZE
        self.max_rounds = GameConfig.MAX_ROUNDS

        # --------------------------------------------------------
        # 🧬 SHARED STATIC DATA
        # --------------------------------------------------------

        if unit_manager is None:

            self.combat_profile_mgr =  CombatProfileManager()

            self.unit_manager = UnitManager(
                units_path=self.units_path,
                combat_profile_mgr=self.combat_profile_mgr,
            )

        else:

            self.unit_manager = unit_manager

            self.combat_profile_mgr = (
                getattr(
                    unit_manager,
                    "combat_profile_mgr",
                    CombatProfileManager(),
                )
            )

        # --------------------------------------------------------
        # 🌐 GLOBAL POOL
        # --------------------------------------------------------

        # Criado pelo TFTLobby.
        self.unit_pool = unit_pool

        # --------------------------------------------------------
        # 🧬 TRAITS
        # --------------------------------------------------------

        self.synergy_mgr = SynergyManager(
            self.traits_path
        )

        # --------------------------------------------------------
        # 🧩 PLAYER MANAGERS
        # --------------------------------------------------------

        self.board_manager = BoardManager(
            rows=self.rows,
            cols=self.cols,
        )

        self.bench_manager = BenchManager(
            max_bench=self.max_bench,
        )

        self.economy_manager = EconomyManager()

        self.shop_manager = ShopManager(
            unit_pool=self.unit_pool,
            shop_size=self.shop_size,
        )

        self.composition_manager = CompositionManager(
            unit_manager=self.unit_manager,
        )

        self.positioning_manager = PositioningManager(
            rows=self.rows,
            cols=self.cols,
        )

        self.strategy_manager = StrategyManager()

        self.anti_loop_manager = AntiLoopManager()

        self.reward_manager = RewardManager(
            economy_manager=self.economy_manager,
            composition_manager=self.composition_manager,
            positioning_manager=self.positioning_manager,
        )

        self.action_mask_manager = ActionMaskManager(
            board_manager=self.board_manager,
            bench_manager=self.bench_manager,
            shop_manager=self.shop_manager,
            economy_manager=self.economy_manager,
            composition_manager=self.composition_manager,
            positioning_manager=self.positioning_manager,
            anti_loop_manager=self.anti_loop_manager,
            unit_manager=self.unit_manager,
        )

        # --------------------------------------------------------
        # ❤️ PLAYER STATE
        # --------------------------------------------------------

        self.hp = GameConfig.STARTING_HP

        # O Lobby sobrescreve com o round global.
        self.round = 1

        self.done = False

        self.last_combat_won = False
        self.last_combat_result = None
        self.last_reward = 0.0

        # --------------------------------------------------------
        # 🧠 TRAITS
        # --------------------------------------------------------

        self._build_trait_index()

        # --------------------------------------------------------
        # 📊 STATS
        # --------------------------------------------------------

        self.action_count = 0
        self.round_action_count = 0
        self.total_actions = 0

        # --------------------------------------------------------
        # 🔄 RESET
        # --------------------------------------------------------

        self.reset()

    # ============================================================
    # 🔄 RESET
    # ============================================================

    def reset(self):
        """
        Reseta somente o jogador.

        IMPORTANTE:
        Não reseta UnitPool.
        O UnitPool pertence ao TFTLobby.
        """

        self.hp = GameConfig.STARTING_HP

        self.round = 1

        self.done = False

        self.last_combat_won = False
        self.last_combat_result = None
        self.last_reward = 0.0

        self.action_count = 0
        self.round_action_count = 0
        self.total_actions = 0

        # --------------------------------------------------------
        # 🧹 MANAGERS
        # --------------------------------------------------------

        self.board_manager.reset()
        self.bench_manager.reset()

        self.economy_manager.reset()

        self.composition_manager.reset()
        self.positioning_manager.reset()

        self.strategy_manager.reset()
        self.anti_loop_manager.reset()
        self.reward_manager.reset()

        # --------------------------------------------------------
        # 🪑 STARTING UNIT
        # --------------------------------------------------------

        self._create_starting_unit()

        # --------------------------------------------------------
        # 🛒 SHOP
        # --------------------------------------------------------

        self._roll_shop()

        # --------------------------------------------------------
        # 🔄 STATE
        # --------------------------------------------------------

        self._rebuild_player_state()

        return self._get_state()

    # ============================================================
    # 🪑 STARTING UNIT
    # ============================================================
    def _create_starting_unit(self):
        """
        Cria a unidade inicial do jogador e coloca no bench.

        A unidade é retirada do UnitPool global.
        """

        # ============================================================
        # 1. Verifica se existe espaço
        # ============================================================

        if not self.bench_manager.has_free_slot():
            raise RuntimeError(
                "Não foi possível criar a unidade inicial: "
                "bench está cheio."
            )

        # ============================================================
        # 2. Pega uma unidade do pool
        # ============================================================

        champion = self.unit_pool.draw(1)

        if champion is None:
            raise RuntimeError(
                "Não foi possível criar a unidade inicial: "
                "UnitPool não retornou nenhum campeão de custo 1."
            )

        # ============================================================
        # 3. Cria a unidade pertencente ao jogador
        # ============================================================

        unit = self.unit_manager.create_unit(champion)

        if unit is None:
            raise RuntimeError(
                f"UnitManager não conseguiu criar a unidade:\n"
                f"{champion}"
            )

        # ============================================================
        # 4. Coloca no bench
        # ============================================================

        success = self.bench_manager.add_unit(unit)

        if not success:
            # Se por algum motivo falhar, devolvemos a unidade
            # para o pool global.

            try:
                self.unit_pool.return_unit(unit)
            except Exception:
                pass

            raise RuntimeError(
                "Não foi possível colocar a unidade inicial "
                "no bench.\n"
                f"Unidade: {unit}\n"
                f"Slots livres: "
                f"{self.bench_manager.get_free_slots()}"
            )

        return unit

    # ============================================================
    # 🛒 SHOP
    # ============================================================

    def _roll_shop(self):

        if self.done:
            return

        self.shop_manager.roll(
            self.economy_manager.level
        )

    # ============================================================
    # 🎮 STEP
    # ============================================================

    def step(self, action):
        """
        Executa UMA ação deste jogador.

        O round global NÃO é incrementado aqui.
        """

        if self.done:

            return (
                self._get_state(),
                0.0,
                True,
                {
                    "dead": True,
                    "player_id": self.player_id,
                },
            )

        self.action_count += 1
        self.round_action_count += 1
        self.total_actions += 1

        action = self._sanitize_action(action)

        action_type = int(
            action.get(
                "type",
                ActionType.PASS,
            )
        )

        info = {
            "player_id": self.player_id,
            "action_type": action_type,
            "action_success": False,
            "round_end": False,
        }

        reward = 0.0

        # --------------------------------------------------------
        # 🎯 EXECUTE
        # --------------------------------------------------------

        if action_type == ActionType.BUY:

            reward = self._execute_buy(
                action,
                info,
            )

        elif action_type == ActionType.REROLL:

            reward = self._execute_reroll(
                info
            )

        elif action_type == ActionType.BUY_XP:

            reward = self._execute_buy_xp(
                info
            )

        elif action_type == ActionType.MOVE_BENCH:

            reward = self._execute_move_bench(
                action,
                info,
            )

        elif action_type == ActionType.MOVE_BOARD:

            reward = self._execute_move_board(
                action,
                info,
            )

        elif action_type == ActionType.SELL:

            reward = self._execute_sell(
                action,
                info,
            )

        elif action_type == ActionType.PASS:

            reward = self._execute_pass(
                info
            )

        else:

            reward = -0.10
            info["invalid_action"] = True

        # --------------------------------------------------------
        # 🧠 REBUILD
        # --------------------------------------------------------

        self._rebuild_player_state()

        # --------------------------------------------------------
        # ☠️ DEATH
        # --------------------------------------------------------

        if self.hp <= 0:

            self.hp = 0
            self.done = True

        info["hp"] = self.hp
        info["gold"] = self.economy_manager.gold
        info["level"] = self.economy_manager.level

        self.last_reward = float(reward)

        return (
            self._get_state(),
            float(reward),
            self.done,
            info,
        )

    # ============================================================
    # 🧹 SANITIZE ACTION
    # ============================================================

    def _sanitize_action(self, action):

        if isinstance(action, np.ndarray):

            if action.ndim == 1:
                action = action.tolist()

        if isinstance(action, (list, tuple)):

            values = list(action)

            while len(values) < 6:
                values.append(0)

            return {
                "type": int(values[0]),
                "shop_slot": int(values[1]),
                "bench_slot": int(values[2]),
                "board_target": int(values[3]),
                "board_source": int(values[4]),
                "conditioned_board_target": int(values[5]),
            }

        if isinstance(action, dict):

            return {
                "type": int(
                    action.get(
                        "type",
                        ActionType.PASS,
                    )
                ),
                "shop_slot": int(
                    action.get(
                        "shop_slot",
                        0,
                    )
                ),
                "bench_slot": int(
                    action.get(
                        "bench_slot",
                        0,
                    )
                ),
                "board_target": int(
                    action.get(
                        "board_target",
                        0,
                    )
                ),
                "board_source": int(
                    action.get(
                        "board_source",
                        0,
                    )
                ),
                "conditioned_board_target": int(
                    action.get(
                        "board_move_target",
                        action.get(
                            "conditioned_board_target",
                            action.get(
                                "board_target",
                                0,
                            ),
                        ),
                    )
                ),
            }

        return {
            "type": ActionType.PASS,
            "shop_slot": 0,
            "bench_slot": 0,
            "board_target": 0,
            "board_source": 0,
            "conditioned_board_target": 0,
        }

    # ============================================================
    # 🛒 BUY
    # ============================================================

    def _execute_buy(self, action, info):

        slot = int(
            action.get(
                "shop_slot",
                0,
            )
        )

        if slot < 0 or slot >= self.shop_size:
            return -0.10

        if not self.bench_manager.has_free_slot():
            return -0.10

        shop = self.shop_manager.get_shop()

        if slot >= len(shop):
            return -0.10

        champion = shop[slot]

        if champion is None:
            return -0.10

        cost = int(
            champion.get(
                "cost",
                1,
            )
        )

        if not self.economy_manager.can_spend(cost):
            return -0.10

        # --------------------------------------------------------
        # 🛒 REMOVE SHOP
        # --------------------------------------------------------

        purchased_champion = (
            self.shop_manager.take_unit(slot)
        )

        if purchased_champion is None:
            return -0.10

        # --------------------------------------------------------
        # 💰 PAY
        # --------------------------------------------------------

        if not self.economy_manager.spend_gold(cost):

            # A cópia saiu da shop.
            self.unit_pool.return_unit(
                purchased_champion
            )

            return -0.10

        # --------------------------------------------------------
        # 🧬 CREATE OWNED UNIT
        # --------------------------------------------------------

        purchased_unit = (
            self.unit_manager.create_unit(
                purchased_champion
            )
        )

        # --------------------------------------------------------
        # 🪑 BENCH
        # --------------------------------------------------------

        if not self.bench_manager.add_unit(
            purchased_unit
        ):

            self.economy_manager.add_gold(cost)

            self.unit_pool.return_unit(
                purchased_unit
            )

            return -0.10

        info["action_success"] = True
        info["bought_unit"] = purchased_unit

        # --------------------------------------------------------
        # ⭐ AUTO UPGRADE
        # --------------------------------------------------------

        upgraded = self._try_upgrade_unit(
            purchased_unit
        )

        if upgraded is not None:

            info["upgrade"] = True
            info["upgraded_unit"] = upgraded

            return (
                self.reward_manager
                .calculate_action_reward(
                    ActionType.BUY,
                    True,
                    action_value=0.30,
                )
            )

        # --------------------------------------------------------
        # 🛒 NORMAL BUY
        # --------------------------------------------------------

        return (
            self.reward_manager
            .calculate_action_reward(
                ActionType.BUY,
                True,
                action_value=0.05,
            )
        )

    # ============================================================
    # 🔄 REROLL
    # ============================================================

    def _execute_reroll(self, info):

        cost = GameConfig.REROLL_COST

        if not self.economy_manager.can_spend(cost):
            return -0.10

        if not self.economy_manager.spend_gold(cost):
            return -0.10

        try:

            self.shop_manager.reroll(
                self.economy_manager.level
            )

        except Exception:

            self.economy_manager.add_gold(cost)

            return -0.10

        info["action_success"] = True

        return (
            self.reward_manager
            .calculate_action_reward(
                ActionType.REROLL,
                True,
                action_value=-0.01,
            )
        )

    # ============================================================
    # ⭐ BUY XP
    # ============================================================

    def _execute_buy_xp(self, info):

        if not self.economy_manager.can_buy_xp():
            return -0.10

        old_level = self.economy_manager.level

        if not self.economy_manager.buy_xp():
            return -0.10

        new_level = self.economy_manager.level

        info["action_success"] = True

        reward = 0.02

        if new_level > old_level:

            reward += (
                self.reward_manager
                .calculate_level_reward(
                    new_level
                )
            )

        return reward

    # ============================================================
    # 🪑 BENCH -> BOARD
    # ============================================================

    def _execute_move_bench(self, action, info):

        bench_slot = int(action["bench_slot"])
        target = int(action["board_target"])

        if not self._is_valid_bench_slot(bench_slot):
            return -0.10

        if not self.board_manager.is_valid_position(target):
            return -0.10

        unit = self.bench_manager.get_unit(
            bench_slot
        )

        if unit is None:
            return -0.10

        # --------------------------------------------------------
        # 🚫 ANTI LOOP
        # --------------------------------------------------------

        if self.anti_loop_manager.should_block_move(
            move_type="bench_to_board",
            source=bench_slot,
            target=target,
            unit=unit,
        ):
            return -0.10

        # --------------------------------------------------------
        # 📍 TARGET EMPTY
        # --------------------------------------------------------

        if self.board_manager.get_unit(target) is not None:
            return -0.10

        # --------------------------------------------------------
        # 🔄 MOVE
        # --------------------------------------------------------

        removed = self.bench_manager.remove_unit(
            bench_slot
        )

        if removed is None:
            return -0.10

        if not self.board_manager.add_unit(
            removed,
            target,
        ):

            self.bench_manager.add_unit(
                removed,
                bench_slot,
            )

            return -0.10

        self.anti_loop_manager.register_move(
            move_type="bench_to_board",
            source=bench_slot,
            target=target,
            unit=removed,
        )

        info["action_success"] = True
        info["moved_unit"] = removed

        try:

            positioning_score = (
                self.positioning_manager
                .evaluate_board(
                    self.board_manager.board
                )
            )

        except Exception:

            positioning_score = 0.0

        return (
            self.reward_manager
            .calculate_action_reward(
                ActionType.MOVE_BENCH,
                True,
                action_value=(
                    positioning_score * 0.05
                ),
            )
        )

    # ============================================================
    # 🔀 BOARD -> BOARD
    # ============================================================

    def _execute_move_board(self, action, info):

        source = int(action["board_source"])

        target = int(
            action["conditioned_board_target"]
        )

        if not self.board_manager.is_valid_position(source):
            return -0.10

        if not self.board_manager.is_valid_position(target):
            return -0.10

        if source == target:
            return -0.10

        unit = self.board_manager.get_unit(source)

        if unit is None:
            return -0.10

        target_unit = self.board_manager.get_unit(target)

        move_type = (
            "board_swap"
            if target_unit is not None
            else "board_move"
        )

        # --------------------------------------------------------
        # 🚫 ANTI LOOP
        # --------------------------------------------------------

        if self.anti_loop_manager.should_block_move(
            move_type=move_type,
            source=source,
            target=target,
            unit=unit,
        ):
            return -0.10

        # --------------------------------------------------------
        # 🔄 MOVE / SWAP
        # --------------------------------------------------------

        if target_unit is None:

            success = self.board_manager.move_unit(
                source,
                target,
            )

        else:

            success = self.board_manager.swap_units(
                source,
                target,
            )

        if not success:
            return -0.10

        self.anti_loop_manager.register_move(
            move_type=move_type,
            source=source,
            target=target,
            unit=unit,
        )

        info["action_success"] = True

        return (
            self.reward_manager
            .calculate_action_reward(
                ActionType.MOVE_BOARD,
                True,
                action_value=0.02,
            )
        )

    # ============================================================
    # 💰 SELL
    # ============================================================

    def _execute_sell(self, action, info):

        bench_slot = int(action["bench_slot"])

        if not self._is_valid_bench_slot(bench_slot):
            return -0.10

        unit = self.bench_manager.get_unit(
            bench_slot
        )

        if unit is None:
            return -0.10

        is_core = (
            self.composition_manager
            .is_core_unit(unit)
        )

        removed = self.bench_manager.remove_unit(
            bench_slot
        )

        if removed is None:
            return -0.10

        sell_value = self.economy_manager.get_sell_value(removed)

        self.economy_manager.add_gold(
            sell_value
        )

        # --------------------------------------------------------
        # 🌐 RETURN TO GLOBAL POOL
        # --------------------------------------------------------

        if self.unit_pool is not None:

            self.unit_pool.return_unit(
                removed
            )

        info["action_success"] = True
        info["sold_unit"] = removed
        info["sell_value"] = sell_value

        if is_core:
            return -0.15

        return 0.05

    # ============================================================
    # 💰 SELL VALUE
    # ============================================================

    def _get_sell_value(self, unit):
        return self.economy_manager.get_sell_value(unit)

    # ============================================================
    # ⏭️ PASS
    # ============================================================

    def _execute_pass(self, info):

        info["action_success"] = True
        info["round_end"] = True

        # O Lobby controla o avanço global.

        return 0.0

    # ============================================================
    # 🔄 PLAYER ROUND END
    # ============================================================

    def resolve_player_round(self):

        if self.done:
            return {}

        result = (
            self.economy_manager
            .resolve_round(
                self.round
            )
        )

        self.round_action_count = 0

        # Nova shop para o próximo round.
        self._roll_shop()

        self._rebuild_player_state()

        return result

    # ============================================================
    # 🌐 ROUND SET BY LOBBY
    # ============================================================

    def set_round(self, round_number):

        self.round = int(round_number)

    # ============================================================
    # ⚔️ COMBAT RESULT
    # ============================================================

    def apply_combat_result(
        self,
        combat_result,
        won,
    ):
        """
        Apenas registra o resultado local.
        """

        self.last_combat_result = combat_result
        self.last_combat_won = bool(won)

        if won:
            self.economy_manager.register_pvp_win()
        else:
            self.economy_manager.register_loss()

        self._rebuild_player_state()

    # ============================================================
    # ❤️ DAMAGE
    # ============================================================

    def apply_damage(self, damage):

        if self.done:
            return

        damage = max(
            0,
            int(damage),
        )

        self.hp = max(
            0,
            self.hp - damage,
        )

        if self.hp <= 0:

            self.hp = 0
            self.done = True

    # ============================================================
    # 🔄 REBUILD PLAYER STATE
    # ============================================================
    def _rebuild_player_state(self):
        owned_units = self._get_all_units()

        self.composition_manager.update(
            self.board_manager.get_units(),
            self.bench_manager.get_units()
        )

        # Atualiza a estratégia com a composição já recalculada.
        self._update_strategy()

        try:
            self.anti_loop_manager.register_state(
                self.board_manager.board,
                self.bench_manager.bench,
            )

        except TypeError:
            try:
                self.anti_loop_manager.register_state(
                    self.board_manager.board
                )
            except Exception:
                pass


    def _update_strategy(self):
        """
        Atualiza a estratégia com base no estado atual do jogador.

        Este método apenas decide a intenção estratégica.
        Ele não executa ações nem altera o contrato do PPO.
        """
        economy = self.economy_manager

        # Estimativa de força do tabuleiro.
        # Cada unidade contribui conforme custo e estrelas.
        board_power = sum(
            float(unit.get("cost", 1))
            * float(unit.get("star", 1))
            * 2.0
            for unit in self.board_manager.board
            if unit is not None
        )

        # Força aproximada das unidades que estão no banco.
        bench_strength = sum(
            float(unit.get("cost", 1))
            * float(unit.get("star", 1))
            for unit in self.bench_manager.bench
            if unit is not None
        )

        # Quantidade de traits presentes na composição.
        active_traits = len(
            self.composition_manager.active_traits
        )

        return self.strategy_manager.decide_strategy(
            hp=self.hp,
            gold=economy.gold,
            level=economy.level,
            xp=economy.xp,
            board_power=board_power,
            bench_strength=bench_strength,
            win_streak=economy.win_streak,
            loss_streak=economy.loss_streak,
            round_number=self.round,
            active_traits=active_traits,
            comp_focus=self.composition_manager.comp_focus,
            comp_direction=self.composition_manager.comp_direction,
        )


    # ============================================================
    # 📦 ALL OWNED UNITS
    # ============================================================

    def _get_all_units(self):

        units = []

        for unit in self.board_manager.board:

            if unit is not None:
                units.append(unit)

        for unit in self.bench_manager.bench:

            if unit is not None:
                units.append(unit)

        return units

    # ============================================================
    # 🧬 TRAIT INDEX
    # ============================================================

    def _build_trait_index(self):

        self._trait_to_idx = {}

        all_champions = (
            self.unit_manager
            .get_all_champions()
        )

        for champion in all_champions:

            for trait in champion.get(
                "traits",
                [],
            ):

                if trait not in self._trait_to_idx:

                    self._trait_to_idx[
                        trait
                    ] = len(
                        self._trait_to_idx
                    )

    # ============================================================
    # 📊 OBSERVATION
    # ============================================================

    def _get_state(self):

        # ========================================================
        # 1️⃣ CORE
        # ========================================================

        core = np.zeros(
            22,
            dtype=np.float32,
        )

        economy = self.economy_manager

        core[0] = self.hp / 100.0
        core[1] = economy.gold / 50.0
        core[2] = economy.level / 9.0

        xp_to_next = max(
            1,
            economy.get_xp_to_next(),
        )

        core[3] = (
            economy.xp
            / float(xp_to_next)
        )

        core[4] = economy.win_streak / 10.0
        core[5] = economy.loss_streak / 10.0

        core[6] = (
            self.round
            / max(1, self.max_rounds)
        )

        core[7] = (
            len(
                self.board_manager
                .get_occupied_positions()
            )
            / float(
                max(1, economy.level)
            )
        )

        core[8] = (
            len(
                self.bench_manager
                .get_occupied_slots()
            )
            / float(self.max_bench)
        )

        core[9] = (
            len(
                self.shop_manager
                .get_shop()
            )
            / float(self.shop_size)
        )

        strategy = int(
            self.strategy_manager.strategy
        )

        for i in range(7):

            core[10 + i] = (
                1.0
                if strategy == i
                else 0.0
            )

        # ========================================================
        # 2️⃣ BOARD
        # ========================================================

        board_features = np.zeros(
            140,
            dtype=np.float32,
        )

        for position, unit in enumerate(
            self.board_manager.board
        ):

            if unit is None:
                continue

            offset = position * 5

            board_features[offset] = 1.0

            board_features[offset + 1] = (
                float(unit.get("cost", 1))
                / 5.0
            )

            board_features[offset + 2] = (
                float(unit.get("star", 1))
                / 3.0
            )

            board_features[offset + 3] = (
                self._role_to_state_value(
                    unit.get(
                        "role",
                        UnitRole.FIGHTER,
                    )
                )
            )

            board_features[offset + 4] = (
                self._get_unit_strength(unit)
            )

        # ========================================================
        # 3️⃣ BENCH
        # ========================================================

        bench_features = np.zeros(
            45,
            dtype=np.float32,
        )

        for position, unit in enumerate(
            self.bench_manager.bench
        ):

            if unit is None:
                continue

            offset = position * 5

            bench_features[offset] = 1.0

            bench_features[offset + 1] = (
                float(unit.get("cost", 1))
                / 5.0
            )

            bench_features[offset + 2] = (
                float(unit.get("star", 1))
                / 3.0
            )

            bench_features[offset + 3] = (
                self._role_to_state_value(
                    unit.get(
                        "role",
                        UnitRole.FIGHTER,
                    )
                )
            )

            bench_features[offset + 4] = (
                self._get_unit_strength(unit)
            )

        # ========================================================
        # 4️⃣ SHOP
        # ========================================================

        shop_features = np.zeros(
            25,
            dtype=np.float32,
        )

        shop = self.shop_manager.get_shop()

        for position, unit in enumerate(
            shop[:self.shop_size]
        ):

            if unit is None:
                continue

            offset = position * 5

            shop_features[offset] = 1.0

            shop_features[offset + 1] = (
                float(unit.get("cost", 1))
                / 5.0
            )

            shop_features[offset + 2] = 1.0

            shop_features[offset + 3] = (
                self._role_to_state_value(
                    unit.get(
                        "role",
                        UnitRole.FIGHTER,
                    )
                )
            )

        # ========================================================
        # 5️⃣ EXTRA
        # ========================================================

        extra = np.zeros(
            5,
            dtype=np.float32,
        )

        extra[0] = (
            len(
                self.board_manager
                .get_occupied_positions()
            )
            / 28.0
        )

        extra[1] = (
            len(
                self.bench_manager
                .get_occupied_slots()
            )
            / 9.0
        )

        extra[2] = (
            economy.gold / 50.0
        )

        extra[3] = (
            economy.level / 9.0
        )

        extra[4] = (
            self.hp / 100.0
        )

        # ========================================================
        # 6️⃣ SYNERGY
        # ========================================================

        synergy = np.zeros(
            5,
            dtype=np.float32,
        )

        active_traits = (
            self.composition_manager.active_traits
        )

        if isinstance(active_traits, dict):

            values = list(
                active_traits.values()
            )

            for i, value in enumerate(
                values[:5]
            ):

                if isinstance(
                    value,
                    (int, float),
                ):

                    synergy[i] = min(
                        1.0,
                        float(value) / 5.0,
                    )

                elif isinstance(
                    value,
                    (list, tuple),
                ):

                    synergy[i] = min(
                        1.0,
                        len(value) / 5.0,
                    )

        # ========================================================
        # 7️⃣ POSITIONING
        # ========================================================

        positioning = np.zeros(
            4,
            dtype=np.float32,
        )

        try:

            positioning[0] = (
                self.positioning_manager
                .evaluate_board(
                    self.board_manager.board
                )
            )

        except Exception:

            positioning[0] = 0.0

        positioning[1] = (
            self._get_frontline_ratio()
        )

        positioning[2] = (
            self._get_backline_ratio()
        )

        positioning[3] = (
            self._get_role_balance()
        )

        # ========================================================
        # 8️⃣ TRAITS
        # ========================================================

        trait_vector = np.zeros(
            len(self._trait_to_idx),
            dtype=np.float32,
        )

        if isinstance(
            self.composition_manager.active_traits,
            dict,
        ):

            for trait, count in (
                self.composition_manager
                .active_traits
                .items()
            ):

                index = self._trait_to_idx.get(
                    trait
                )

                if index is None:
                    continue

                try:

                    value = float(count)

                except (
                    TypeError,
                    ValueError,
                ):

                    continue

                trait_vector[index] = min(
                    1.0,
                    value / 5.0,
                )

        # ========================================================
        # 9️⃣ CAPACITY
        # ========================================================

        capacity = np.array(
            [
                self._get_board_capacity() / 9.0,
                self._get_free_bench() / 9.0,
            ],
            dtype=np.float32,
        )

        # ========================================================
        # 🔗 CONCAT
        # ========================================================

        return np.concatenate(
            [
                core,
                board_features,
                bench_features,
                shop_features,
                extra,
                synergy,
                positioning,
                trait_vector,
                capacity,
            ]
        ).astype(np.float32)

    # ============================================================
    # 💪 UNIT STRENGTH
    # ============================================================

    def _get_unit_strength(self, unit):

        cost = float(
            unit.get("cost", 1)
        )

        star = float(
            unit.get("star", 1)
        )

        return min(
            1.0,
            (
                cost / 5.0 * 0.5
                + star / 3.0 * 0.5
            ),
        )

    # ============================================================
    # 🎭 ROLE
    # ============================================================

    def _role_to_state_value(self, role):

        if role == UnitRole.TANK:
            return 0.2

        if role == UnitRole.CARRY:
            return 0.4

        if role == UnitRole.SUPPORT:
            return 0.6

        if role == UnitRole.FIGHTER:
            return 0.8

        if role == UnitRole.ASSASSIN:
            return 1.0

        return 0.0

    # ============================================================
    # 📍 FRONTLINE
    # ============================================================

    def _get_frontline_ratio(self):

        occupied = 0
        frontline = 0

        for position, unit in enumerate(
            self.board_manager.board
        ):

            if unit is None:
                continue

            occupied += 1

            row = position // self.cols

            if row <= 1:
                frontline += 1

        if occupied == 0:
            return 0.0

        return frontline / occupied

    # ============================================================
    # 📍 BACKLINE
    # ============================================================

    def _get_backline_ratio(self):

        occupied = 0
        backline = 0

        for position, unit in enumerate(
            self.board_manager.board
        ):

            if unit is None:
                continue

            occupied += 1

            row = position // self.cols

            if row >= 2:
                backline += 1

        if occupied == 0:
            return 0.0

        return backline / occupied

    # ============================================================
    # 🎭 ROLE BALANCE
    # ============================================================

    def _get_role_balance(self):

        roles = []

        for unit in self.board_manager.board:

            if unit is None:
                continue

            roles.append(
                unit.get(
                    "role",
                    UnitRole.FIGHTER,
                )
            )

        if not roles:
            return 0.0

        unique_roles = len(set(roles))

        return min(
            1.0,
            unique_roles / 5.0,
        )

    # ============================================================
    # 📦 BOARD CAPACITY
    # ============================================================

    def _get_board_capacity(self):

        occupied = len(
            self.board_manager
            .get_occupied_positions()
        )

        return max(
            0,
            self.economy_manager.level - occupied,
        )

    # ============================================================
    # 📦 FREE BENCH
    # ============================================================
    def _get_free_bench(self):
        """
        Retorna a quantidade de slots livres no bench.
        """

        return self.bench_manager.get_free_slots()


    # ============================================================
    # 🔍 BENCH SLOT
    # ============================================================

    def _is_valid_bench_slot(self, slot):

        return (
            0 <= int(slot) < self.max_bench
        )

    # ============================================================
    # 🎯 ACTION MASKS
    # ============================================================

    def get_action_masks(self):

        return (
            self.action_mask_manager
            .get_action_masks(
                is_alive=not self.done
            )
        )

    # ============================================================
    # 🧠 STRATEGY
    # ============================================================

    def get_strategy(self):

        return self.strategy_manager.strategy

    def get_strategy_state(self):

        return (
            self.strategy_manager
            .get_state()
        )

    # ============================================================
    # 🧩 COMPOSITION
    # ============================================================

    def get_composition_state(self):

        return (
            self.composition_manager
            .get_state()
        )

    # ============================================================
    # ⭐ UPGRADE
    # ============================================================
    def _try_upgrade_unit(self, purchased_unit):
        """
        3 × 1★ -> 1 × 2★
        3 × 2★ -> 1 × 3★

        O UnitPool não é alterado durante o upgrade.
        """

        if purchased_unit is None:
            return None

        current_star = int(purchased_unit.get("star", 1))

        if current_star >= 3:
            return None

        unit_id = purchased_unit.get("id")
        purchased_uuid = purchased_unit.get("uuid")

        if unit_id is None or purchased_uuid is None:
            return None

        # --------------------------------------------------------
        # 🔎 ENCONTRAR CÓPIAS COMPATÍVEIS
        # --------------------------------------------------------

        candidates = []

        for location, slot, unit in self._iter_owned_units():
            if unit is None:
                continue

            if unit.get("id") != unit_id:
                continue

            if int(unit.get("star", 1)) != current_star:
                continue

            candidates.append((location, slot, unit))

        if len(candidates) < 3:
            return None

        # A cópia comprada deve participar do upgrade.
        # A ordenação é estável para as demais unidades.
        candidates.sort(
            key=lambda candidate: (
                candidate[2].get("uuid") != purchased_uuid
            )
        )

        selected = candidates[:3]

        # Confirma que a cópia comprada foi selecionada.
        if not any(
            unit.get("uuid") == purchased_uuid
            for _, _, unit in selected
        ):
            return None

        # --------------------------------------------------------
        # 📍 DEFINIR POSIÇÃO PREFERENCIAL
        # --------------------------------------------------------

        upgrade_location = None
        upgrade_slot = None

        for location, slot, unit in selected:
            if unit.get("uuid") == purchased_uuid:
                upgrade_location = location
                upgrade_slot = slot
                break

        if upgrade_location is None:
            upgrade_location, upgrade_slot, _ = selected[0]

        # --------------------------------------------------------
        # 🛡️ VALIDAR TODAS AS POSIÇÕES ANTES DE ALTERAR
        # --------------------------------------------------------

        for location, slot, expected_unit in selected:
            if location == "board":
                actual_unit = self.board_manager.get_unit(slot)
            elif location == "bench":
                actual_unit = self.bench_manager.get_unit(slot)
            else:
                return None

            if actual_unit is None:
                return None

            # Evita remover uma unidade diferente caso o estado
            # tenha mudado desde a coleta dos candidatos.
            if actual_unit.get("uuid") != expected_unit.get("uuid"):
                return None

        # --------------------------------------------------------
        # ⭐ CRIAR A UNIDADE MELHORADA ANTES DAS REMOÇÕES
        # --------------------------------------------------------

        try:
            upgraded = self.unit_manager.create_upgraded_unit(
                purchased_unit,
                current_star + 1,
            )
        except (ValueError, TypeError, KeyError):
            return None

        # --------------------------------------------------------
        # 🗑️ REMOVER AS TRÊS CÓPIAS
        # --------------------------------------------------------

        removed_units = []

        for location, slot, _ in selected:
            removed = self._remove_owned_unit(location, slot)

            if removed is None:
                # Restaura as cópias já removidas.
                for old_location, old_slot, old_unit in reversed(
                    removed_units
                ):
                    restored = self._place_owned_unit(
                        old_location,
                        old_slot,
                        old_unit,
                    )

                    if not restored:
                        raise RuntimeError(
                            "Falha ao restaurar unidade após "
                            "erro durante upgrade."
                        )

                return None

            removed_units.append((location, slot, removed))

        # --------------------------------------------------------
        # 📍 POSICIONAR A UNIDADE MELHORADA
        # --------------------------------------------------------

        success = self._place_owned_unit(
            upgrade_location,
            upgrade_slot,
            upgraded,
        )

        if not success:
            # A posição original pode ter sido ocupada ou
            # não estar mais disponível; tenta o banco.
            success = self.bench_manager.add_unit(upgraded)

        if not success:
            # Tenta restaurar as unidades originais para não
            # perder cópias caso nenhum destino esteja disponível.
            for old_location, old_slot, old_unit in reversed(
                removed_units
            ):
                restored = self._place_owned_unit(
                    old_location,
                    old_slot,
                    old_unit,
                )

                if not restored:
                    raise RuntimeError(
                        "Falha ao restaurar unidades após "
                        "falha no posicionamento do upgrade."
                    )

            raise RuntimeError(
                "Não foi possível posicionar a unidade "
                "após upgrade."
            )

        return upgraded

    # ============================================================
    # 📋 ITERATE OWNED
    # ============================================================

    def _iter_owned_units(self):

        for position, unit in enumerate(
            self.board_manager.board
        ):

            if unit is not None:

                yield (
                    "board",
                    position,
                    unit,
                )

        for slot, unit in enumerate(
            self.bench_manager.bench
        ):

            if unit is not None:

                yield (
                    "bench",
                    slot,
                    unit,
                )

    # ============================================================
    # 🗑️ REMOVE OWNED
    # ============================================================

    def _remove_owned_unit(
        self,
        location,
        slot,
    ):

        if location == "board":

            return (
                self.board_manager
                .remove_unit(slot)
            )

        if location == "bench":

            return (
                self.bench_manager
                .remove_unit(slot)
            )

        return None

    # ============================================================
    # 📍 PLACE OWNED
    # ============================================================

    def _place_owned_unit(
        self,
        location,
        slot,
        unit,
    ):

        if location == "board":

            return (
                self.board_manager
                .add_unit(
                    unit,
                    slot,
                )
            )

        if location == "bench":

            try:

                return (
                    self.bench_manager
                    .add_unit(
                        unit,
                        slot,
                    )
                )

            except TypeError:

                return (
                    self.bench_manager
                    .add_unit(unit)
                )

        return False

    # ============================================================
    # 📊 PUBLIC STATE
    # ============================================================

    def get_public_state(self):

        return {
            "player_id": self.player_id,

            "hp": self.hp,

            "gold": (
                self.economy_manager.gold
            ),

            "level": (
                self.economy_manager.level
            ),

            "xp": (
                self.economy_manager.xp
            ),

            "round": self.round,

            "strategy": int(
                self.strategy_manager.strategy
            ),

            "alive": not self.done,

            "board": deepcopy(
                self.board_manager.board
            ),

            "bench": deepcopy(
                self.bench_manager.bench
            ),

            "shop": deepcopy(
                self.shop_manager.get_shop()
            ),
        }

    # ============================================================
    # 🐛 DEBUG
    # ============================================================

    def debug_print(self):

        print(
            "\n"
            "=========================================="
        )

        print(
            f"🎮 PLAYER {self.player_id}"
        )

        print(
            "=========================================="
        )

        print(
            f"❤️ HP: {self.hp}"
        )

        print(
            f"💰 Gold: "
            f"{self.economy_manager.gold}"
        )

        print(
            f"⭐ Level: "
            f"{self.economy_manager.level}"
        )

        print(
            f"📈 XP: "
            f"{self.economy_manager.xp}"
        )

        print(
            f"🔄 Round: {self.round}"
        )

        print(
            f"🧠 Strategy: "
            f"{self.strategy_manager.strategy.name}"
        )

        print(
            f"🏆 Win streak: "
            f"{self.economy_manager.win_streak}"
        )

        print(
            f"💀 Loss streak: "
            f"{self.economy_manager.loss_streak}"
        )

        # --------------------------------------------------------
        # 🪑 BENCH
        # --------------------------------------------------------

        print("\n🪑 BENCH:")

        for i, unit in enumerate(
            self.bench_manager.bench
        ):

            if unit is None:

                print(
                    f"  [{i}] Empty"
                )

            else:

                print(
                    f"  [{i}] "
                    f"{unit.get('name', '?')} "
                    f"{unit.get('star', 1)}★ "
                    f"UUID={unit.get('uuid', '?')}"
                )

        # --------------------------------------------------------
        # ⚔️ BOARD
        # --------------------------------------------------------

        print("\n⚔️ BOARD:")

        for row in range(self.rows):

            values = []

            for col in range(self.cols):

                position = (
                    row * self.cols
                    + col
                )

                unit = (
                    self.board_manager
                    .get_unit(position)
                )

                if unit is None:

                    values.append("[ . ]")

                else:

                    values.append(
                        f"[{unit.get('name', '?')[:3]}]"
                    )

            print(
                " ".join(values)
            )

        # --------------------------------------------------------
        # 🛒 SHOP
        # --------------------------------------------------------

        print("\n🛒 SHOP:")

        for i, unit in enumerate(
            self.shop_manager.get_shop()
        ):

            if unit is None:

                print(
                    f"  [{i}] Empty"
                )

            else:

                print(
                    f"  [{i}] "
                    f"{unit.get('name', '?')} "
                    f"${unit.get('cost', '?')}"
                )

        print(
            "=========================================="
        )