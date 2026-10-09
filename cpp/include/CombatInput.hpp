#pragma once

#include <cstdint>
#include <string>
#include <vector>


namespace tft
{

// ============================================================
// Enumerations
// ============================================================

enum class CombatContext : std::uint8_t
{
    PVP = 0,
    PVE = 1
};


enum class UnitTeam : std::uint8_t
{
    PLAYER_A = 0,
    PLAYER_B = 1
};


enum class UnitRole : std::uint8_t
{
    TANK = 0,
    CARRY = 1,
    SUPPORT = 2,
    FIGHTER = 3,
    ASSASSIN = 4
};


enum class DamageType : std::uint8_t
{
    PHYSICAL = 0,
    MAGIC = 1,
    TRUE_DAMAGE = 2
};


enum class AbilityTargetType : std::uint8_t
{
    SELF = 0,
    ALLY = 1,
    ALL_ALLIES = 2,
    ENEMY = 3,
    ALL_ENEMIES = 4,
    AREA = 5,
    RANDOM_ENEMY = 6,
    LOWEST_HP_ENEMY = 7,
    HIGHEST_HP_ENEMY = 8
};


// ============================================================
// Position
// ============================================================

struct CombatPosition
{
    int x = 0;
    int y = 0;
};


// ============================================================
// Item
// ============================================================

struct CombatItem
{
    int id = -1;

    std::string api_name;
    std::string name;

    // Valores genéricos de atributos.
    float attack_damage = 0.0f;
    float ability_power = 0.0f;
    float attack_speed = 0.0f;
    float critical_strike_chance = 0.0f;
    float critical_strike_damage = 0.0f;

    float health = 0.0f;
    float armor = 0.0f;
    float magic_resist = 0.0f;
    float mana = 0.0f;

    float omnivamp = 0.0f;
    float damage_amplification = 0.0f;
    float damage_reduction = 0.0f;

    bool is_temporary = false;
};


// ============================================================
// Trait
// ============================================================

struct CombatTrait
{
    int id = -1;

    std::string api_name;
    std::string name;

    int active_count = 0;
    int tier = 0;

    bool active = false;
};


// ============================================================
// Ability
// ============================================================

struct CombatAbility
{
    int id = -1;

    std::string api_name;
    std::string name;
    std::string description;

    float mana_cost = 0.0f;
    float initial_mana = 0.0f;

    AbilityTargetType target_type =
        AbilityTargetType::ENEMY;

    DamageType damage_type =
        DamageType::MAGIC;

    float base_damage = 0.0f;
    float base_healing = 0.0f;

    float shield_amount = 0.0f;

    float ability_power_ratio = 0.0f;
    float attack_damage_ratio = 0.0f;

    float area_radius = 0.0f;

    float duration = 0.0f;

    bool has_damage = false;
    bool has_healing = false;
    bool has_shield = false;
    bool has_buff = false;
    bool has_debuff = false;
    bool has_area_effect = false;
};


// ============================================================
// Unit
// ============================================================

struct CombatUnit
{
    // --------------------------------------------------------
    // Identity
    // --------------------------------------------------------

    int id = -1;

    std::string api_name;
    std::string name;

    int star = 1;

    UnitTeam team = UnitTeam::PLAYER_A;
    UnitRole role = UnitRole::FIGHTER;

    // --------------------------------------------------------
    // Position
    // --------------------------------------------------------

    CombatPosition position;

    // --------------------------------------------------------
    // Base combat state
    // --------------------------------------------------------

    float hp = 0.0f;
    float max_hp = 0.0f;

    float mana = 0.0f;
    float max_mana = 100.0f;

    // --------------------------------------------------------
    // Offensive stats
    // --------------------------------------------------------

    float attack_damage = 0.0f;
    float ability_power = 0.0f;

    float attack_speed = 1.0f;

    float attack_range = 1.0f;

    float critical_strike_chance = 0.0f;
    float critical_strike_damage = 1.0f;

    // --------------------------------------------------------
    // Defensive stats
    // --------------------------------------------------------

    float armor = 0.0f;
    float magic_resist = 0.0f;

    // --------------------------------------------------------
    // Combat modifiers
    // --------------------------------------------------------

    float damage_amplification = 0.0f;
    float damage_reduction = 0.0f;

    float omnivamp = 0.0f;

    // --------------------------------------------------------
    // Ability
    // --------------------------------------------------------

    CombatAbility ability;

    // --------------------------------------------------------
    // Equipment
    // --------------------------------------------------------

    std::vector<CombatItem> items;

    // --------------------------------------------------------
    // Traits
    // --------------------------------------------------------

    std::vector<CombatTrait> traits;

    // --------------------------------------------------------
    // State flags
    // --------------------------------------------------------

    bool alive = true;
    bool can_move = true;
    bool can_attack = true;
    bool can_cast = true;

    // --------------------------------------------------------
    // Metadata
    // --------------------------------------------------------

    int source_board_position = -1;
};


// ============================================================
// Team
// ============================================================

struct CombatTeam
{
    UnitTeam team = UnitTeam::PLAYER_A;

    int player_id = -1;

    float player_hp = 100.0f;

    std::vector<CombatUnit> units;
};


// ============================================================
// Combat modifiers
// ============================================================

struct CombatModifier
{
    std::string id;
    std::string source;

    float attack_damage = 0.0f;
    float ability_power = 0.0f;
    float attack_speed = 0.0f;

    float health = 0.0f;
    float armor = 0.0f;
    float magic_resist = 0.0f;

    float damage_amplification = 0.0f;
    float damage_reduction = 0.0f;

    float duration = 0.0f;

    bool temporary = false;
};


// ============================================================
// Combat configuration
// ============================================================

struct CombatConfig
{
    // --------------------------------------------------------
    // Board
    // --------------------------------------------------------

    int board_rows = 4;
    int board_cols = 7;

    // --------------------------------------------------------
    // Simulation
    // --------------------------------------------------------

    float max_duration = 30.0f;

    // Segurança contra bugs no engine.
    std::uint64_t max_events = 100000;

    // --------------------------------------------------------
    // RNG
    // --------------------------------------------------------

    std::uint64_t seed = 0;

    bool deterministic = true;

    // --------------------------------------------------------
    // Debug
    // --------------------------------------------------------

    bool debug = false;

    bool record_events = false;

    bool record_damage = false;

    bool record_targets = false;

    bool record_positions = false;

    bool record_mana = false;

    bool record_abilities = false;
};


// ============================================================
// Complete combat input
// ============================================================

struct CombatInput
{
    // --------------------------------------------------------
    // Match
    // --------------------------------------------------------

    std::uint64_t seed = 0;

    CombatContext context =
        CombatContext::PVP;

    // --------------------------------------------------------
    // Global configuration
    // --------------------------------------------------------

    CombatConfig config;

    // --------------------------------------------------------
    // Teams
    // --------------------------------------------------------

    CombatTeam player_a;

    CombatTeam player_b;

    // --------------------------------------------------------
    // Global modifiers
    // --------------------------------------------------------

    std::vector<CombatModifier> global_modifiers;
};

} // namespace tft