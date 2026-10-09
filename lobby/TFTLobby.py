# ============================================================
# 🌐 TFTLobby.py
#
# Responsabilidade:
# - Controlar 8 jogadores
# - Possuir o UnitPool global
# - Possuir o UnitManager compartilhado
# - Controlar round global
# - Matchmaking
# - Combate PvP
# - Aplicar dano
# - Eliminação
# - Ranking
#
# NÃO executa as ações internas do jogador.
# Isso pertence ao MiniTFTEnv.
# ============================================================

from dataclasses import dataclass
import random

import numpy as np

from config.GameConfig import GameConfig

from env import MiniTFTEnv

from units.UnitManager import UnitManager
from units.UnitPool import UnitPool

from combat.CombatProfileManager import (
    CombatProfileManager,
    UnitRole,
)

import sys
from pathlib import Path

# Localiza o módulo compilado pelo CMake no Windows.
_REPO_ROOT = Path(__file__).resolve().parent.parent
_CPP_BUILD_DIRS = [
    _REPO_ROOT / "cpp" / "build" / "bin" / "Release",
    _REPO_ROOT / "cpp" / "build" / "bin",
]

for _build_dir in _CPP_BUILD_DIRS:
    if _build_dir.exists() and str(_build_dir) not in sys.path:
        sys.path.insert(0, str(_build_dir))

try:
    import combat_engine
except ImportError as exc:
    raise ImportError(
        "Não foi possível importar combat_engine. "
        "Compile o módulo C++ e confira cpp/build/bin/Release."
    ) from exc

# ============================================================
# ⚔️ COMBAT RESULT
# ============================================================

@dataclass
class CombatResult:

    winner_id: int | None
    loser_id: int | None

    winner_units: int
    loser_units: int

    damage: int

    draw: bool = False


# ============================================================
# 👤 LOBBY PLAYER
# ============================================================

@dataclass
class LobbyPlayer:

    player_id: int
    env: MiniTFTEnv

    alive: bool = True
    eliminated: bool = False

    wins: int = 0
    losses: int = 0

    placement: int | None = None

    opponent_id: int | None = None

    last_combat_result: CombatResult | None = None
    last_damage_taken: int = 0


# ============================================================
# 🌐 TFT LOBBY
# ============================================================

class TFTLobby:

    PLAYERS_PER_LOBBY = 8

    def __init__(
        self,
        units_path=None,
        traits_path=None,
        seed=None,
    ):

        # --------------------------------------------------------
        # 🎲 RANDOM
        # --------------------------------------------------------

        self.seed = seed

        if seed is not None:

            random.seed(seed)
            np.random.seed(seed)

        # --------------------------------------------------------
        # 📁 PATHS
        # --------------------------------------------------------

        self.units_path = units_path
        self.traits_path = traits_path

        # --------------------------------------------------------
        # 🧬 SHARED UNIT MANAGER
        # --------------------------------------------------------

        self.combat_profile_mgr = (
            CombatProfileManager()
        )

        self.unit_manager = UnitManager(
            units_path=(
                units_path
                if units_path is not None
                else GameConfig.UNITS_PATH
            ),
            combat_profile_mgr=self.combat_profile_mgr,
        )

        # --------------------------------------------------------
        # 🌐 GLOBAL UNIT POOL
        # --------------------------------------------------------

        self.unit_pool = UnitPool(
            unit_manager=self.unit_manager
        )

        # --------------------------------------------------------
        # 👥 PLAYERS
        # --------------------------------------------------------

        self.players = []

        for player_id in range(
            self.PLAYERS_PER_LOBBY
        ):

            env = MiniTFTEnv(
                units_path=units_path,
                traits_path=traits_path,
                unit_manager=self.unit_manager,
                unit_pool=self.unit_pool,
                player_id=player_id,
                lobby=self,
            )

            self.players.append(
                LobbyPlayer(
                    player_id=player_id,
                    env=env,
                )
            )

        # --------------------------------------------------------
        # 🌍 GLOBAL STATE
        # --------------------------------------------------------

        self.stage = 1
        self.round = 1
        self.round_index = 0

        self.matchups = []

        self.previous_matchups = set()

        self.finished = False

        self.winner_id = None

        self.final_ranking = []

        # --------------------------------------------------------
        # 🧠 ACTION STATE
        # --------------------------------------------------------

        self.round_actions = {
            player.player_id: 0
            for player in self.players
        }

        self.round_finished = {
            player.player_id: False
            for player in self.players
        }

        # --------------------------------------------------------
        # 🔄 ROUND
        # --------------------------------------------------------

        self._set_round_on_players()

    # ============================================================
    # 🔄 RESET
    # ============================================================

    def reset(self):

        # --------------------------------------------------------
        # 🌐 GLOBAL POOL
        # --------------------------------------------------------

        self.unit_pool.reset()

        # --------------------------------------------------------
        # 👥 PLAYERS
        # --------------------------------------------------------

        for player in self.players:

            player.env.reset()

            player.alive = True
            player.eliminated = False

            player.wins = 0
            player.losses = 0

            player.placement = None
            player.opponent_id = None

            player.last_combat_result = None
            player.last_damage_taken = 0

        # --------------------------------------------------------
        # 🌍 GLOBAL
        # --------------------------------------------------------

        self.stage = 1
        self.round = 1
        self.round_index = 0

        self.matchups = []
        self.previous_matchups = set()

        self.finished = False
        self.winner_id = None
        self.final_ranking = []

        self.round_actions = {
            player.player_id: 0
            for player in self.players
        }

        self.round_finished = {
            player.player_id: False
            for player in self.players
        }

        self._set_round_on_players()

        return self.get_observations()

    # ============================================================
    # 📊 OBSERVATIONS
    # ============================================================

    def get_observations(self):

        observations = []

        for player in self.players:

            if not player.alive:

                observations.append(
                    np.zeros_like(
                        player.env._get_state()
                    )
                )

            else:

                observations.append(
                    player.env._get_state()
                )

        return np.asarray(
            observations,
            dtype=np.float32,
        )

    # ============================================================
    # 🎯 ACTION MASKS
    # ============================================================

    def get_action_masks(self):

        masks = []

        for player in self.players:

            # ----------------------------------------------------
            # ☠️ DEAD PLAYER
            # ----------------------------------------------------

            if not player.alive:

                masks.append(
                    self._dead_player_mask()
                )

                continue

            # ----------------------------------------------------
            # 🧠 ENV MASK
            # ----------------------------------------------------

            masks.append(
                player.env.get_action_masks()
            )

        return masks

    # ============================================================
    # ☠️ DEAD MASK
    # ============================================================

    @staticmethod
    def _dead_player_mask():

        return [
            np.array(
                [0, 0, 0, 0, 0, 0, 1],
                dtype=np.int8,
            ),
            np.zeros(
                5,
                dtype=np.int8,
            ),
            np.zeros(
                9,
                dtype=np.int8,
            ),
            np.zeros(
                28,
                dtype=np.int8,
            ),
            np.zeros(
                28,
                dtype=np.int8,
            ),
            np.zeros(
                28,
                dtype=np.int8,
            ),
        ]

    # ============================================================
    # 🎮 STEP
    # ============================================================

    def step(self, actions):

        if self.finished:

            return (
                self.get_observations(),
                np.zeros(
                    self.PLAYERS_PER_LOBBY,
                    dtype=np.float32,
                ),
                True,
                self.get_public_state(),
            )

        # --------------------------------------------------------
        # 🛡️ NORMALIZE ACTIONS
        # --------------------------------------------------------

        normalized_actions = (
            self._normalize_actions(actions)
        )

        rewards = np.zeros(
            self.PLAYERS_PER_LOBBY,
            dtype=np.float32,
        )

        infos = []

        # --------------------------------------------------------
        # 🎮 EXECUTE PLAYER ACTIONS
        # --------------------------------------------------------

        for player in self.players:

            pid = player.player_id

            if not player.alive:

                infos.append(
                    {
                        "player_id": pid,
                        "dead": True,
                    }
                )

                continue

            action = normalized_actions[pid]

            (
                _state,
                reward,
                done,
                info,
            ) = player.env.step(action)

            rewards[pid] = float(reward)

            self.round_actions[pid] += 1

            if info.get(
                "round_end",
                False,
            ):

                self.round_finished[pid] = True

            infos.append(info)

        # --------------------------------------------------------
        # 🧠 AUTOMATIC PASS SAFETY
        # --------------------------------------------------------

        self._check_round_action_limit()

        # --------------------------------------------------------
        # 🏁 CHECK ALL ALIVE PLAYERS
        # --------------------------------------------------------

        if self._all_alive_players_finished_round():

            round_info = (
                self._resolve_round()
            )

            for info in infos:

                info["round_resolved"] = True
                info["round"] = self.round
                info["matchups"] = (
                    self.matchups
                )

        else:

            round_info = {
                "round_resolved": False,
            }

        # --------------------------------------------------------
        # ☠️ ELIMINATION
        # --------------------------------------------------------

        self.eliminate_players()

        # --------------------------------------------------------
        # 🏆 FINISH
        # --------------------------------------------------------

        if self._check_finished():

            self.finished = True

            self._finalize_ranking()

        # --------------------------------------------------------
        # 📊 RETURN
        # --------------------------------------------------------

        info = {
            "players": infos,
            "round": self.round,
            "stage": self.stage,
            "finished": self.finished,
            "round_info": round_info,
        }

        return (
            self.get_observations(),
            rewards,
            self.finished,
            info,
        )

    # ============================================================
    # 🧹 NORMALIZE ACTIONS
    # ============================================================

    def _normalize_actions(self, actions):

        normalized = {}

        if actions is None:

            actions = []

        # --------------------------------------------------------
        # LIST / ARRAY
        # --------------------------------------------------------

        if isinstance(
            actions,
            (list, tuple, np.ndarray),
        ):

            for pid in range(
                self.PLAYERS_PER_LOBBY
            ):

                if pid < len(actions):

                    normalized[pid] = (
                        actions[pid]
                    )

                else:

                    normalized[pid] = {
                        "type": 6
                    }

            return normalized

        # --------------------------------------------------------
        # DICT
        # --------------------------------------------------------

        if isinstance(actions, dict):

            for pid in range(
                self.PLAYERS_PER_LOBBY
            ):

                normalized[pid] = (
                    actions.get(
                        pid,
                        actions.get(
                            str(pid),
                            {
                                "type": 6
                            },
                        ),
                    )
                )

            return normalized

        # --------------------------------------------------------
        # FALLBACK
        # --------------------------------------------------------

        for pid in range(
            self.PLAYERS_PER_LOBBY
        ):

            normalized[pid] = {
                "type": 6
            }

        return normalized

    # ============================================================
    # ⏱️ ACTION LIMIT
    # ============================================================

    def _check_round_action_limit(self):

        limit = getattr(
            GameConfig,
            "MAX_ACTIONS_PER_ROUND",
            20,
        )

        for player in self.players:

            if not player.alive:
                continue

            if (
                self.round_actions[
                    player.player_id
                ] >= limit
            ):

                self.round_finished[
                    player.player_id
                ] = True

    # ============================================================
    # 🏁 ALL PLAYERS FINISHED
    # ============================================================

    def _all_alive_players_finished_round(self):

        alive_players = [
            player
            for player in self.players
            if player.alive
        ]

        if not alive_players:
            return True

        return all(
            self.round_finished[
                player.player_id
            ]
            for player in alive_players
        )

    # ============================================================
    # 🔄 RESOLVE ROUND
    # ============================================================

    def _resolve_round(self):

        # --------------------------------------------------------
        # 💰 ECONOMY
        # --------------------------------------------------------

        economy_results = {}

        for player in self.players:

            if not player.alive:
                continue

            economy_results[
                player.player_id
            ] = (
                player.env
                .resolve_player_round()
            )

        # --------------------------------------------------------
        # ⚔️ MATCHMAKING
        # --------------------------------------------------------

        self.generate_matchups()

        # --------------------------------------------------------
        # ⚔️ COMBAT
        # --------------------------------------------------------

        combat_results = []

        for player_a, player_b in self.matchups:

            result = self.resolve_combat(
                player_a,
                player_b,
            )

            combat_results.append(
                result
            )

        # --------------------------------------------------------
        # 💰 SINCRONIZA RECOMPENSAS DE COMBATE NO RELATÓRIO
        # --------------------------------------------------------

        for player in self.players:
            economy_result = economy_results.get(
                player.player_id
            )

            if economy_result is None:
                continue

            economy = player.env.economy_manager

            # Ouro concedido pelos combates desta rodada.
            win_gold = economy.round_win_gold

            economy_result["win_gold"] = win_gold
            economy_result["total_gold"] += win_gold

            # Inclui o ouro recebido após a resolução econômica.
            economy_result["new_gold"] = economy.gold

            # Impede que o bônus apareça novamente no próximo relatório.
            economy.round_win_gold = 0

        # --------------------------------------------------------
        # ☠️ ELIMINATION
        # --------------------------------------------------------

        self.eliminate_players()

        # --------------------------------------------------------
        # 🏆 RANKING
        # --------------------------------------------------------

        self.update_ranking()

        # --------------------------------------------------------
        # 🌍 NEXT ROUND
        # --------------------------------------------------------

        if not self.finished:

            self.advance_round()

        # --------------------------------------------------------
        # 🔄 RESET ROUND FLAGS
        # --------------------------------------------------------

        for player in self.players:

            if player.alive:

                self.round_actions[
                    player.player_id
                ] = 0

                self.round_finished[
                    player.player_id
                ] = False

        return {
            "economy": economy_results,
            "combat": combat_results,
        }

    # ============================================================
    # ⚔️ MATCHMAKING
    # ============================================================

    def generate_matchups(self):

        alive_players = [
            player
            for player in self.players
            if player.alive
        ]

        random.shuffle(
            alive_players
        )

        self.matchups = []

        used_pairs = set()

        i = 0

        while i + 1 < len(alive_players):

            player_a = alive_players[i]
            player_b = alive_players[i + 1]

            pair = frozenset(
                (
                    player_a.player_id,
                    player_b.player_id,
                )
            )

            # Evita repetir confronto quando
            # ainda existem outras possibilidades.
            if (
                pair in self.previous_matchups
                and len(alive_players) > 2
            ):

                found_alternative = False

                for j in range(
                    i + 2,
                    len(alive_players),
                ):

                    candidate = alive_players[j]

                    candidate_pair = frozenset(
                        (
                            player_a.player_id,
                            candidate.player_id,
                        )
                    )

                    if candidate_pair not in self.previous_matchups:

                        alive_players[i + 1], alive_players[j] = (
                            alive_players[j],
                            alive_players[i + 1],
                        )

                        player_b = alive_players[i + 1]

                        pair = frozenset(
                            (
                                player_a.player_id,
                                player_b.player_id,
                            )
                        )

                        found_alternative = True

                        break

                # Se não encontrou alternativa,
                # aceita o confronto.
                _ = found_alternative

            self.matchups.append(
                (
                    player_a,
                    player_b,
                )
            )

            player_a.opponent_id = (
                player_b.player_id
            )

            player_b.opponent_id = (
                player_a.player_id
            )

            used_pairs.add(pair)

            i += 2

        # --------------------------------------------------------
        # 📝 STORE HISTORY
        # --------------------------------------------------------

        self.previous_matchups.update(
            used_pairs
        )

        return self.matchups

    # ============================================================
    # ⚔️ COMBAT
    # ============================================================
    def _build_cpp_combat_input(self, player_a, player_b):
        """Converte os dois tabuleiros para CombatInput do C++."""

        combat_input = combat_engine.CombatInput()
        combat_input.context = combat_engine.CombatContext.PVP

        config = combat_engine.CombatConfig()
        config.board_rows = GameConfig.BOARD_ROWS
        config.board_cols = GameConfig.BOARD_COLS
        config.max_duration = 30.0
        config.max_events = 100_000
        config.deterministic = True
        config.seed = int(self.seed or 0)

        # Registro detalhado pode ser ativado durante depuração.
        config.record_events = False
        config.record_damage = False
        config.record_positions = False

        combat_input.seed = int(self.seed or 0)
        combat_input.config = config

        team_specs = [
            (player_a, combat_engine.UnitTeam.PLAYER_A),
            (player_b, combat_engine.UnitTeam.PLAYER_B),
        ]

        next_unit_id = 0

        for player, cpp_team_type in team_specs:
            cpp_team = combat_engine.CombatTeam()
            cpp_team.team = cpp_team_type
            cpp_team.player_id = int(player.player_id)
            cpp_team.player_hp = float(player.env.hp)

            cpp_units = []

            board = player.env.board_manager.board

            for board_position, unit in enumerate(board):
                if unit is None:
                    continue

                profile = unit.get("combat_profile") or {}

                # O perfil pode conter os atributos mesmo quando a instância
                # da unidade guarda apenas identidade, estrela e UUID.
                max_hp = float(
                    profile.get("max_hp")
                    or unit.get("max_hp")
                    or unit.get("hp")
                    or 100.0
                )

                hp = float(unit.get("hp") or max_hp)

                attack_damage = float(
                    profile.get("attack_damage")
                    or unit.get("attack_damage")
                    or unit.get("ad")
                    or 30.0
                )

                attack_speed = float(
                    profile.get("attack_speed")
                    or unit.get("attack_speed")
                    or 1.0
                )

                attack_range = float(
                    profile.get("attack_range")
                    or unit.get("attack_range")
                    or 1.0
                )

                armor = float(
                    profile.get("armor")
                    or unit.get("armor")
                    or 0.0
                )

                magic_resist = float(
                    profile.get("magic_resist")
                    or unit.get("magic_resist")
                    or unit.get("mr")
                    or 0.0
                )

                # O tabuleiro Python usa índice linear: linha * colunas + coluna.
                y, x = divmod(board_position, GameConfig.BOARD_COLS)

                # Espelha o lado B para posicionar as equipes frente a frente.
                if cpp_team_type == combat_engine.UnitTeam.PLAYER_B:
                    x = GameConfig.BOARD_COLS - 1 - x

                cpp_unit = combat_engine.CombatUnit()
                cpp_unit.id = next_unit_id
                cpp_unit.api_name = str(unit.get("champion_id", unit.get("id", "")))
                cpp_unit.name = str(unit.get("name", "Unknown"))
                cpp_unit.star = int(unit.get("star", 1))
                cpp_unit.team = cpp_team_type

                role_by_id = {
                    0: combat_engine.UnitRole.TANK,
                    1: combat_engine.UnitRole.CARRY,
                    2: combat_engine.UnitRole.SUPPORT,
                    3: combat_engine.UnitRole.FIGHTER,
                    4: combat_engine.UnitRole.ASSASSIN,
                }

                cpp_unit.role = role_by_id.get(
                    int(unit.get("role", 3)),
                    combat_engine.UnitRole.FIGHTER,
                )

                position = combat_engine.CombatPosition()
                position.x = x
                position.y = y
                cpp_unit.position = position

                cpp_unit.max_hp = max(1.0, max_hp)
                cpp_unit.hp = min(max(1.0, hp), cpp_unit.max_hp)
                cpp_unit.attack_damage = max(1.0, attack_damage)
                cpp_unit.attack_speed = max(0.1, attack_speed)
                cpp_unit.attack_range = max(1.0, attack_range)
                cpp_unit.armor = armor
                cpp_unit.magic_resist = magic_resist

                cpp_unit.alive = True
                cpp_unit.can_move = True
                cpp_unit.can_attack = True
                cpp_unit.can_cast = True
                cpp_unit.source_board_position = board_position

                cpp_units.append(cpp_unit)

                # IMPORTANTE: atribui o vetor completo ao objeto C++.
                cpp_team.units = cpp_units
                next_unit_id += 1

            if cpp_team_type == combat_engine.UnitTeam.PLAYER_A:
                combat_input.player_a = cpp_team
            else:
                combat_input.player_b = cpp_team

        return combat_input
    
    def resolve_combat(self, player_a, player_b):
        # 1. Monta a entrada e executa o motor C++.
        combat_input = self._build_cpp_combat_input(
            player_a,
            player_b,
        )

        cpp_result = combat_engine.simulate(combat_input)

        if not cpp_result.success:
            raise RuntimeError(
                f"Falha no motor C++: "
                f"{cpp_result.error_code}: "
                f"{cpp_result.error_message}"
            )

        if not cpp_result.completed:
            raise RuntimeError(
                "O motor C++ aceitou a entrada, "
                "mas não concluiu a simulação."
            )

        survivors_a = int(cpp_result.player_a_survivors)
        survivors_b = int(cpp_result.player_b_survivors)

        # 2. Identifica vencedor e perdedor usando o resultado do C++.
        if cpp_result.winner == combat_engine.CombatWinner.PLAYER_A:
            winner = player_a
            loser = player_b
            winner_units = survivors_a
            loser_units = survivors_b

        elif cpp_result.winner == combat_engine.CombatWinner.PLAYER_B:
            winner = player_b
            loser = player_a
            winner_units = survivors_b
            loser_units = survivors_a

        else:
            # 3. Empate: ninguém recebe dano de jogador nem bônus de vitória.
            result = CombatResult(
                winner_id=None,
                loser_id=None,
                winner_units=survivors_a,
                loser_units=survivors_b,
                damage=0,
                draw=True,
            )

            for player in (player_a, player_b):
                player.last_combat_result = result
                player.last_damage_taken = 0
                player.env.last_combat_result = result
                player.env.last_combat_won = False
                player.env._rebuild_player_state()

            return result

        # 4. Calcula o dano ao jogador perdedor.
        damage = self._calculate_damage(winner_units)

        result = CombatResult(
            winner_id=winner.player_id,
            loser_id=loser.player_id,
            winner_units=winner_units,
            loser_units=loser_units,
            damage=damage,
            draw=False,
        )

        # 5. Atualiza estatísticas e economia dos dois jogadores.
        winner.wins += 1
        loser.losses += 1

        # O ambiente registra a sequência e o bônus de vitória.
        # O perdedor também atualiza sua sequência de derrotas.
        winner.env.apply_combat_result(result, won=True)
        loser.env.apply_combat_result(result, won=False)

        # 6. Aplica o dano somente ao jogador perdedor.
        loser.last_damage_taken = damage
        loser.env.apply_damage(damage)

        # 7. Guarda o resultado do combate.
        winner.last_combat_result = result
        loser.last_combat_result = result

        return result

    # ============================================================
    # 💪 BOARD POWER
    # ============================================================

    def _calculate_board_power(self, env):

        units = self._get_alive_units(env)

        if not units:
            return 0.0

        total = 0.0

        for unit in units:

            total += (
                self._calculate_unit_power(
                    unit
                )
            )

        # --------------------------------------------------------
        # ⭐ POSITIONING
        # --------------------------------------------------------

        try:

            positioning = float(
                env.positioning_manager
                .evaluate_board(
                    env.board_manager.board
                )
            )

        except Exception:

            positioning = 0.0

        # --------------------------------------------------------
        # 🧬 SYNERGY
        # --------------------------------------------------------

        synergy_bonus = 0.0

        try:

            active_traits = (
                env.composition_manager
                .active_traits
            )

            if isinstance(
                active_traits,
                dict,
            ):

                synergy_bonus = min(
                    10.0,
                    len(active_traits) * 1.5,
                )

        except Exception:

            synergy_bonus = 0.0

        return (
            total
            + positioning * 10.0
            + synergy_bonus
        )

    # ============================================================
    # 💪 UNIT POWER
    # ============================================================

    def _calculate_unit_power(self, unit):

        if unit is None:
            return 0.0

        cost = float(
            unit.get("cost", 1)
        )

        star = float(
            unit.get("star", 1)
        )

        role = unit.get(
            "role",
            UnitRole.FIGHTER,
        )

        # --------------------------------------------------------
        # BASE
        # --------------------------------------------------------

        power = (
            cost * 5.0
            + star * 8.0
        )

        # --------------------------------------------------------
        # ROLE
        # --------------------------------------------------------

        role_bonus = {
            UnitRole.TANK: 2.0,
            UnitRole.CARRY: 6.0,
            UnitRole.SUPPORT: 3.0,
            UnitRole.FIGHTER: 4.0,
            UnitRole.ASSASSIN: 5.0,
        }

        power += role_bonus.get(
            role,
            3.0,
        )

        # --------------------------------------------------------
        # STAR MULTIPLIER
        # --------------------------------------------------------

        if star >= 3:

            power *= 1.75

        elif star >= 2:

            power *= 1.30

        return power

    # ============================================================
    # 📦 GET BOARD UNITS
    # ============================================================

    def _get_alive_units(self, env):

        units = []

        for position in (
            env.board_manager
            .get_occupied_positions()
        ):

            unit = (
                env.board_manager
                .get_unit(position)
            )

            if unit is not None:

                units.append(unit)

        return units

    # ============================================================
    # ❤️ DAMAGE
    # ============================================================
    def _calculate_damage(self, winner_units: int) -> int:
        """Dano ao jogador: dano base do estágio + sobreviventes."""

        base_damage = GameConfig.get_stage_damage(self.stage)
        survivors = max(0, int(winner_units))

        return max(0, base_damage + survivors)

    # ============================================================
    # ☠️ ELIMINATION
    # ============================================================

    def eliminate_players(self):

        for player in self.players:

            if not player.alive:
                continue

            if player.env.hp <= 0:

                player.env.hp = 0

                player.alive = False
                player.eliminated = True

                if player.placement is None:

                    player.placement = (
                        self._next_elimination_placement()
                    )

                # ------------------------------------------------
                # 🧹 PLAYER SHOP
                # ------------------------------------------------

                try:

                    player.env.shop_manager.return_current_shop()

                except Exception:

                    pass

                # ------------------------------------------------
                # 🧹 UNITS
                # ------------------------------------------------

                self._return_player_units(
                    player.env
                )

    # ============================================================
    # 🗑️ RETURN PLAYER UNITS
    # ============================================================

    def _return_player_units(self, env):

        # --------------------------------------------------------
        # BOARD
        # --------------------------------------------------------

        board_units = []

        for position in (
            env.board_manager
            .get_occupied_positions()
        ):

            unit = (
                env.board_manager
                .get_unit(position)
            )

            if unit is not None:

                board_units.append(unit)

        for unit in board_units:

            self.unit_pool.return_unit(unit)

        # --------------------------------------------------------
        # BENCH
        # --------------------------------------------------------

        bench_units = []

        for slot in (
            env.bench_manager
            .get_occupied_slots()
        ):

            unit = (
                env.bench_manager
                .get_unit(slot)
            )

            if unit is not None:

                bench_units.append(unit)

        for unit in bench_units:

            self.unit_pool.return_unit(unit)

        # --------------------------------------------------------
        # CLEAR
        # --------------------------------------------------------

        env.board_manager.reset()
        env.bench_manager.reset()

    # ============================================================
    # 🏆 ELIMINATION PLACEMENT
    # ============================================================

    def _next_elimination_placement(self):

        eliminated = sum(
            1
            for player in self.players
            if player.eliminated
        )

        return self.PLAYERS_PER_LOBBY - eliminated

    # ============================================================
    # 🏆 UPDATE RANKING
    # ============================================================

    def update_ranking(self):

        alive = [
            player
            for player in self.players
            if player.alive
        ]

        eliminated = [
            player
            for player in self.players
            if player.eliminated
        ]

        # --------------------------------------------------------
        # DEAD ORDER
        # --------------------------------------------------------

        eliminated.sort(
            key=lambda player: (
                player.placement
                if player.placement is not None
                else 999
            )
        )

        # --------------------------------------------------------
        # ALIVE ORDER
        # --------------------------------------------------------

        alive.sort(
            key=lambda player: (
                player.env.hp,
                player.wins,
                player.env.economy_manager.level,
            ),
            reverse=True,
        )

        ranking = []

        for player in alive:

            ranking.append(
                player.player_id
            )

        for player in eliminated:

            if player.player_id not in ranking:

                ranking.append(
                    player.player_id
                )

        self.final_ranking = ranking

        return ranking

    # ============================================================
    # 🏆 FINAL RANKING
    # ============================================================

    def _finalize_ranking(self):

        alive = [
            player
            for player in self.players
            if player.alive
        ]

        # --------------------------------------------------------
        # 🥇 WINNER
        # --------------------------------------------------------

        if len(alive) == 1:

            winner = alive[0]

            winner.placement = 1

            self.winner_id = (
                winner.player_id
            )

        elif len(alive) == 0:

            self.winner_id = None

        # --------------------------------------------------------
        # OTHER ALIVE
        # --------------------------------------------------------

        alive_without_winner = [
            player
            for player in alive
            if player.player_id != self.winner_id
        ]

        alive_without_winner.sort(
            key=lambda player: (
                player.env.hp,
                player.wins,
                player.env.economy_manager.level,
            ),
            reverse=True,
        )

        next_place = 2

        for player in alive_without_winner:

            if player.placement is None:

                player.placement = next_place

                next_place += 1

        # --------------------------------------------------------
        # ELIMINATED
        # --------------------------------------------------------

        for player in self.players:

            if player.placement is None:

                player.placement = (
                    self.PLAYERS_PER_LOBBY
                )

        # --------------------------------------------------------
        # SORT
        # --------------------------------------------------------

        ordered = sorted(
            self.players,
            key=lambda player: (
                player.placement
            )
        )

        self.final_ranking = [
            player.player_id
            for player in ordered
        ]

        return self.final_ranking

    # ============================================================
    # 🌍 ADVANCE ROUND
    # ============================================================

    def advance_round(self):

        self.round_index += 1

        self.round += 1

        # --------------------------------------------------------
        # STAGE
        # --------------------------------------------------------

        # A cada 7 rounds sobe stage.
        self.stage = (
            ((self.round - 1) // 7) + 1
        )

        self._set_round_on_players()

        # --------------------------------------------------------
        # NEW MATCHUP STATE
        # --------------------------------------------------------

        for player in self.players:

            player.opponent_id = None
            player.last_damage_taken = 0

    # ============================================================
    # 🌐 SET ROUND
    # ============================================================

    def _set_round_on_players(self):

        for player in self.players:

            player.env.set_round(
                self.round
            )

    # ============================================================
    # 🏁 FINISHED
    # ============================================================

    def _check_finished(self):

        alive = [
            player
            for player in self.players
            if player.alive
        ]

        if len(alive) <= 1:

            return True

        if self.round >= GameConfig.MAX_ROUNDS:

            return True

        return False

    # ============================================================
    # 📊 IS FINISHED
    # ============================================================

    def is_finished(self):

        return self.finished

    # ============================================================
    # 📊 ALIVE PLAYERS
    # ============================================================

    def get_alive_players(self):

        return [
            player
            for player in self.players
            if player.alive
        ]

    # ============================================================
    # 📊 PUBLIC STATE
    # ============================================================

    def get_public_state(self):

        return {
            "stage": self.stage,

            "round": self.round,

            "round_index": self.round_index,

            "finished": self.finished,

            "winner_id": self.winner_id,

            "ranking": list(
                self.final_ranking
            ),

            "alive_players": [
                player.player_id
                for player in self.players
                if player.alive
            ],

            "players": [
                {
                    "player_id": player.player_id,

                    "hp": player.env.hp,

                    "gold": (
                        player.env
                        .economy_manager
                        .gold
                    ),

                    "level": (
                        player.env
                        .economy_manager
                        .level
                    ),

                    "xp": (
                        player.env
                        .economy_manager
                        .xp
                    ),

                    "alive": player.alive,

                    "eliminated": (
                        player.eliminated
                    ),

                    "wins": player.wins,

                    "losses": player.losses,

                    "placement": (
                        player.placement
                    ),

                    "opponent_id": (
                        player.opponent_id
                    ),

                    "damage_taken": (
                        player.last_damage_taken
                    ),
                }
                for player in self.players
            ],
        }

    # ============================================================
    # 🐛 DEBUG
    # ============================================================

    def debug_print(self):

        print(
            "\n"
            "============================================================"
        )

        print(
            f"🌐 TFT LOBBY "
            f"| Stage {self.stage} "
            f"| Round {self.round}"
        )

        print(
            "============================================================"
        )

        for player in self.players:

            env = player.env

            status = (
                "🟢 ALIVE"
                if player.alive
                else "🔴 ELIMINATED"
            )

            print(
                f"P{player.player_id} "
                f"{status} "
                f"| HP={env.hp:3d} "
                f"| Gold={env.economy_manager.gold:2d} "
                f"| Lv={env.economy_manager.level} "
                f"| W={player.wins} "
                f"| L={player.losses}"
            )

        print(
            "\n⚔️ MATCHUPS:"
        )

        for player_a, player_b in self.matchups:

            print(
                f"  P{player_a.player_id} "
                f"vs "
                f"P{player_b.player_id}"
            )

        if self.final_ranking:

            print(
                "\n🏆 RANKING:"
            )

            for position, player_id in enumerate(
                self.final_ranking,
                start=1,
            ):

                print(
                    f"  #{position} "
                    f"P{player_id}"
                )

        print(
            "============================================================"
        )


# ============================================================
# 🧪 SIMPLE TEST
# ============================================================

if __name__ == "__main__":

    print(
        "\n🚀 Criando TFT Lobby..."
    )

    lobby = TFTLobby(
        seed=42
    )

    print(
        "✅ Lobby criado."
    )

    print(
        f"👥 Players: {len(lobby.players)}"
    )

    print(
        f"🌐 Pool inicial: "
        f"{lobby.unit_pool.get_total_initial()}"
    )

    lobby.debug_print()

    # --------------------------------------------------------
    # 🧪 Random PASS test
    # --------------------------------------------------------

    print(
        "\n🧪 Executando alguns rounds..."
    )

    for _ in range(5):

        actions = []

        for player in lobby.players:

            if player.alive:

                actions.append(
                    {
                        "type": 6
                    }
                )

            else:

                actions.append(
                    {
                        "type": 6
                    }
                )

        _obs, _rewards, done, info = (
            lobby.step(actions)
        )

        print(
            f"Round={lobby.round} "
            f"| Alive={len(lobby.get_alive_players())} "
            f"| Finished={done}"
        )

        if done:
            break

    lobby.debug_print()