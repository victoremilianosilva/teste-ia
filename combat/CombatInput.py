from __future__ import annotations

from dataclasses import dataclass, field
from enum import IntEnum
from typing import List


# ============================================================
# Enumerations
# ============================================================

class CombatContext(IntEnum):
    PVP = 0
    PVE = 1


class UnitTeam(IntEnum):
    PLAYER_A = 0
    PLAYER_B = 1


class UnitRole(IntEnum):
    TANK = 0
    CARRY = 1
    SUPPORT = 2
    FIGHTER = 3
    ASSASSIN = 4


class DamageType(IntEnum):
    PHYSICAL = 0
    MAGIC = 1
    TRUE_DAMAGE = 2


class AbilityTargetType(IntEnum):
    SELF = 0
    ALLY = 1
    ALL_ALLIES = 2
    ENEMY = 3
    ALL_ENEMIES = 4
    AREA = 5
    RANDOM_ENEMY = 6
    LOWEST_HP_ENEMY = 7
    HIGHEST_HP_ENEMY = 8


# ============================================================
# Position
# ============================================================

@dataclass(slots=True)
class CombatPosition:
    x: int = 0
    y: int = 0


# ============================================================
# Item
# ============================================================

@dataclass(slots=True)
class CombatItem:
    id: int = -1

    api_name: str = ""
    name: str = ""

    attack_damage: float = 0.0
    ability_power: float = 0.0
    attack_speed: float = 0.0
    critical_strike_chance: float = 0.0
    critical_strike_damage: float = 0.0

    health: float = 0.0
    armor: float = 0.0
    magic_resist: float = 0.0
    mana: float = 0.0

    omnivamp: float = 0.0
    damage_amplification: float = 0.0
    damage_reduction: float = 0.0

    is_temporary: bool = False


# ============================================================
# Trait
# ============================================================

@dataclass(slots=True)
class CombatTrait:
    id: int = -1

    api_name: str = ""
    name: str = ""

    active_count: int = 0
    tier: int = 0

    active: bool = False


# ============================================================
# Ability
# ============================================================

@dataclass(slots=True)
class CombatAbility:
    id: int = -1

    api_name: str = ""
    name: str = ""
    description: str = ""

    mana_cost: float = 0.0
    initial_mana: float = 0.0

    target_type: AbilityTargetType = (
        AbilityTargetType.ENEMY
    )

    damage_type: DamageType = (
        DamageType.MAGIC
    )

    base_damage: float = 0.0
    base_healing: float = 0.0
    shield_amount: float = 0.0

    ability_power_ratio: float = 0.0
    attack_damage_ratio: float = 0.0

    area_radius: float = 0.0
    duration: float = 0.0

    has_damage: bool = False
    has_healing: bool = False
    has_shield: bool = False
    has_buff: bool = False
    has_debuff: bool = False
    has_area_effect: bool = False


# ============================================================
# Unit
# ============================================================

@dataclass(slots=True)
class CombatUnit:
    # Identity
    id: int = -1
    api_name: str = ""
    name: str = ""

    star: int = 1

    team: UnitTeam = UnitTeam.PLAYER_A
    role: UnitRole = UnitRole.FIGHTER

    # Position
    position: CombatPosition = field(
        default_factory=CombatPosition
    )

    # Health / mana
    hp: float = 0.0
    max_hp: float = 0.0

    mana: float = 0.0
    max_mana: float = 100.0

    # Offensive stats
    attack_damage: float = 0.0
    ability_power: float = 0.0

    attack_speed: float = 1.0
    attack_range: float = 1.0

    critical_strike_chance: float = 0.0
    critical_strike_damage: float = 1.0

    # Defensive stats
    armor: float = 0.0
    magic_resist: float = 0.0

    # Modifiers
    damage_amplification: float = 0.0
    damage_reduction: float = 0.0
    omnivamp: float = 0.0

    # Ability
    ability: CombatAbility = field(
        default_factory=CombatAbility
    )

    # Items
    items: List[CombatItem] = field(
        default_factory=list
    )

    # Traits
    traits: List[CombatTrait] = field(
        default_factory=list
    )

    # State
    alive: bool = True
    can_move: bool = True
    can_attack: bool = True
    can_cast: bool = True

    # Metadata
    source_board_position: int = -1


# ============================================================
# Team
# ============================================================

@dataclass(slots=True)
class CombatTeam:
    team: UnitTeam = UnitTeam.PLAYER_A

    player_id: int = -1

    player_hp: float = 100.0

    units: List[CombatUnit] = field(
        default_factory=list
    )


# ============================================================
# Global modifier
# ============================================================

@dataclass(slots=True)
class CombatModifier:
    id: str = ""
    source: str = ""

    attack_damage: float = 0.0
    ability_power: float = 0.0
    attack_speed: float = 0.0

    health: float = 0.0
    armor: float = 0.0
    magic_resist: float = 0.0

    damage_amplification: float = 0.0
    damage_reduction: float = 0.0

    duration: float = 0.0

    temporary: bool = False


# ============================================================
# Combat configuration
# ============================================================

@dataclass(slots=True)
class CombatConfig:
    board_rows: int = 4
    board_cols: int = 7

    max_duration: float = 30.0

    max_events: int = 100_000

    seed: int = 0

    deterministic: bool = True

    debug: bool = False

    record_events: bool = False
    record_damage: bool = False
    record_targets: bool = False
    record_positions: bool = False
    record_mana: bool = False
    record_abilities: bool = False


# ============================================================
# Complete input
# ============================================================

@dataclass(slots=True)
class CombatInput:
    seed: int = 0

    context: CombatContext = CombatContext.PVP

    config: CombatConfig = field(
        default_factory=CombatConfig
    )

    player_a: CombatTeam = field(
        default_factory=lambda: CombatTeam(
            team=UnitTeam.PLAYER_A
        )
    )

    player_b: CombatTeam = field(
        default_factory=lambda: CombatTeam(
            team=UnitTeam.PLAYER_B
        )
    )

    global_modifiers: List[CombatModifier] = field(
        default_factory=list
    )