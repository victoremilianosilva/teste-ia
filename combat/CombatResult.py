from __future__ import annotations

from dataclasses import dataclass, field
from enum import IntEnum
from typing import List


# ============================================================
# Enumerations
# ============================================================

class CombatWinner(IntEnum):
    DRAW = 0
    PLAYER_A = 1
    PLAYER_B = 2


class UnitTeam(IntEnum):
    PLAYER_A = 0
    PLAYER_B = 1


class DamageType(IntEnum):
    PHYSICAL = 0
    MAGIC = 1
    TRUE_DAMAGE = 2


class CombatContext(IntEnum):
    PVP = 0
    PVE = 1


# ============================================================
# Unit result
# ============================================================

@dataclass(slots=True)
class CombatUnitResult:
    unit_id: int = -1

    team: UnitTeam = UnitTeam.PLAYER_A

    survived: bool = False

    initial_hp: float = 0.0
    final_hp: float = 0.0

    damage_dealt: float = 0.0
    damage_taken: float = 0.0

    healing_done: float = 0.0

    kills: int = 0

    attacks: int = 0
    ability_casts: int = 0

    final_x: int = 0
    final_y: int = 0


# ============================================================
# Damage event
# ============================================================

@dataclass(slots=True)
class DamageEvent:
    timestamp: float = 0.0

    source_unit_id: int = -1
    target_unit_id: int = -1

    damage_type: DamageType = DamageType.PHYSICAL

    raw_damage: float = 0.0
    final_damage: float = 0.0

    critical: bool = False
    ability_damage: bool = False


# ============================================================
# Attack event
# ============================================================

@dataclass(slots=True)
class AttackEvent:
    timestamp: float = 0.0

    source_unit_id: int = -1
    target_unit_id: int = -1

    critical: bool = False

    damage: float = 0.0


# ============================================================
# Ability event
# ============================================================

@dataclass(slots=True)
class AbilityEvent:
    timestamp: float = 0.0

    source_unit_id: int = -1

    ability_id: str = ""

    target_unit_ids: List[int] = field(
        default_factory=list
    )

    damage: float = 0.0
    healing: float = 0.0
    shield: float = 0.0


# ============================================================
# Position event
# ============================================================

@dataclass(slots=True)
class PositionEvent:
    timestamp: float = 0.0

    unit_id: int = -1

    from_x: int = 0
    from_y: int = 0

    to_x: int = 0
    to_y: int = 0


# ============================================================
# Death event
# ============================================================

@dataclass(slots=True)
class DeathEvent:
    timestamp: float = 0.0

    unit_id: int = -1

    killer_unit_id: int = -1


# ============================================================
# Generic event
# ============================================================

@dataclass(slots=True)
class CombatEvent:
    timestamp: float = 0.0

    type: str = ""

    source_unit_id: int = -1
    target_unit_id: int = -1

    value: float = 0.0

    data: str = ""


# ============================================================
# Complete result
# ============================================================

@dataclass(slots=True)
class CombatResult:
    winner: CombatWinner = CombatWinner.DRAW

    context: CombatContext = CombatContext.PVP

    duration: float = 0.0

    events_processed: int = 0

    timeout: bool = False

    completed: bool = False

    # Player damage
    player_a_damage: float = 0.0
    player_b_damage: float = 0.0

    # Team statistics
    player_a_survivors: int = 0
    player_b_survivors: int = 0

    player_a_deaths: int = 0
    player_b_deaths: int = 0

    player_a_damage_dealt: float = 0.0
    player_b_damage_dealt: float = 0.0

    # Units
    units: List[CombatUnitResult] = field(
        default_factory=list
    )

    # Debug / replay
    events: List[CombatEvent] = field(
        default_factory=list
    )

    damage_events: List[DamageEvent] = field(
        default_factory=list
    )

    attack_events: List[AttackEvent] = field(
        default_factory=list
    )

    ability_events: List[AbilityEvent] = field(
        default_factory=list
    )

    position_events: List[PositionEvent] = field(
        default_factory=list
    )

    death_events: List[DeathEvent] = field(
        default_factory=list
    )

    # Error
    success: bool = True

    error_code: str = ""

    error_message: str = ""