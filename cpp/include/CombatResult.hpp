#pragma once

#include "CombatInput.hpp"
#include <cstdint>
#include <string>
#include <vector>


namespace tft
{

// ============================================================
// Combat outcome
// ============================================================

enum class CombatWinner : std::uint8_t
{
    DRAW = 0,
    PLAYER_A = 1,
    PLAYER_B = 2
};


// ============================================================
// Unit result
// ============================================================

struct CombatUnitResult
{
    int unit_id = -1;

    UnitTeam team = UnitTeam::PLAYER_A;

    bool survived = false;

    float initial_hp = 0.0f;
    float final_hp = 0.0f;

    float damage_dealt = 0.0f;
    float damage_taken = 0.0f;

    float healing_done = 0.0f;

    int kills = 0;

    int attacks = 0;
    int ability_casts = 0;

    int final_x = 0;
    int final_y = 0;
};


// ============================================================
// Damage event
// ============================================================

struct DamageEvent
{
    float timestamp = 0.0f;

    int source_unit_id = -1;
    int target_unit_id = -1;

    DamageType damage_type =
        DamageType::PHYSICAL;

    float raw_damage = 0.0f;
    float final_damage = 0.0f;

    bool critical = false;

    bool ability_damage = false;
};


// ============================================================
// Attack event
// ============================================================

struct AttackEvent
{
    float timestamp = 0.0f;

    int source_unit_id = -1;
    int target_unit_id = -1;

    bool critical = false;

    float damage = 0.0f;
};


// ============================================================
// Ability event
// ============================================================

struct AbilityEvent
{
    float timestamp = 0.0f;

    int source_unit_id = -1;

    std::string ability_id;

    std::vector<int> target_unit_ids;

    float damage = 0.0f;

    float healing = 0.0f;

    float shield = 0.0f;
};


// ============================================================
// Position event
// ============================================================

struct PositionEvent
{
    float timestamp = 0.0f;

    int unit_id = -1;

    int from_x = 0;
    int from_y = 0;

    int to_x = 0;
    int to_y = 0;
};


// ============================================================
// Death event
// ============================================================

struct DeathEvent
{
    float timestamp = 0.0f;

    int unit_id = -1;

    int killer_unit_id = -1;
};


// ============================================================
// Generic combat event
// ============================================================

struct CombatEvent
{
    float timestamp = 0.0f;

    std::string type;

    int source_unit_id = -1;
    int target_unit_id = -1;

    float value = 0.0f;

    std::string data;
};


// ============================================================
// Complete combat result
// ============================================================

struct CombatResult
{
    // --------------------------------------------------------
    // Outcome
    // --------------------------------------------------------

    CombatWinner winner =
        CombatWinner::DRAW;

    CombatContext context =
        CombatContext::PVP;

    // --------------------------------------------------------
    // Match information
    // --------------------------------------------------------

    float duration = 0.0f;

    std::uint64_t events_processed = 0;

    bool timeout = false;

    bool completed = false;

    // --------------------------------------------------------
    // Player damage
    // --------------------------------------------------------

    float player_a_damage = 0.0f;

    float player_b_damage = 0.0f;

    // --------------------------------------------------------
    // Team statistics
    // --------------------------------------------------------

    int player_a_survivors = 0;
    int player_b_survivors = 0;

    int player_a_deaths = 0;
    int player_b_deaths = 0;

    float player_a_damage_dealt = 0.0f;
    float player_b_damage_dealt = 0.0f;

    // --------------------------------------------------------
    // Unit results
    // --------------------------------------------------------

    std::vector<CombatUnitResult> units;

    // --------------------------------------------------------
    // Debug / replay
    // --------------------------------------------------------

    std::vector<CombatEvent> events;

    std::vector<DamageEvent> damage_events;

    std::vector<AttackEvent> attack_events;

    std::vector<AbilityEvent> ability_events;

    std::vector<PositionEvent> position_events;

    std::vector<DeathEvent> death_events;

    // --------------------------------------------------------
    // Error information
    // --------------------------------------------------------

    bool success = true;

    std::string error_code;

    std::string error_message;
};

} // namespace tft