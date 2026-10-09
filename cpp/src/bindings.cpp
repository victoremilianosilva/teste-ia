#include <pybind11/pybind11.h>
#include <pybind11/stl.h>

#include "CombatInput.hpp"
#include "CombatResult.hpp"
#include "CombatEngine.hpp"

namespace py = pybind11;

using namespace tft;

PYBIND11_MODULE(combat_engine, module)
{
    module.doc() = "TFT Combat Engine - Python/C++ contract";

    // =========================================================
    // ENUMS
    // =========================================================

    py::enum_<CombatContext>(module, "CombatContext")
        .value("PVP", CombatContext::PVP)
        .value("PVE", CombatContext::PVE);

    py::enum_<UnitTeam>(module, "UnitTeam")
        .value("PLAYER_A", UnitTeam::PLAYER_A)
        .value("PLAYER_B", UnitTeam::PLAYER_B);

    py::enum_<UnitRole>(module, "UnitRole")
        .value("TANK", UnitRole::TANK)
        .value("CARRY", UnitRole::CARRY)
        .value("SUPPORT", UnitRole::SUPPORT)
        .value("FIGHTER", UnitRole::FIGHTER)
        .value("ASSASSIN", UnitRole::ASSASSIN);

    py::enum_<DamageType>(module, "DamageType")
        .value("PHYSICAL", DamageType::PHYSICAL)
        .value("MAGIC", DamageType::MAGIC)
        .value("TRUE_DAMAGE", DamageType::TRUE_DAMAGE);

    py::enum_<AbilityTargetType>(module, "AbilityTargetType")
        .value("SELF", AbilityTargetType::SELF)
        .value("ALLY", AbilityTargetType::ALLY)
        .value("ALL_ALLIES", AbilityTargetType::ALL_ALLIES)
        .value("ENEMY", AbilityTargetType::ENEMY)
        .value("ALL_ENEMIES", AbilityTargetType::ALL_ENEMIES)
        .value("AREA", AbilityTargetType::AREA)
        .value("RANDOM_ENEMY", AbilityTargetType::RANDOM_ENEMY)
        .value("LOWEST_HP_ENEMY", AbilityTargetType::LOWEST_HP_ENEMY)
        .value("HIGHEST_HP_ENEMY", AbilityTargetType::HIGHEST_HP_ENEMY);

    py::enum_<CombatWinner>(module, "CombatWinner")
        .value("DRAW", CombatWinner::DRAW)
        .value("PLAYER_A", CombatWinner::PLAYER_A)
        .value("PLAYER_B", CombatWinner::PLAYER_B);

    // =========================================================
    // POSITION
    // =========================================================

    py::class_<CombatPosition>(module, "CombatPosition")
        .def(py::init<>())
        .def_readwrite("x", &CombatPosition::x)
        .def_readwrite("y", &CombatPosition::y);

    // =========================================================
    // ITEM
    // =========================================================

    py::class_<CombatItem>(module, "CombatItem")
        .def(py::init<>())
        .def_readwrite("id", &CombatItem::id)
        .def_readwrite("api_name", &CombatItem::api_name)
        .def_readwrite("name", &CombatItem::name)
        .def_readwrite("attack_damage", &CombatItem::attack_damage)
        .def_readwrite("ability_power", &CombatItem::ability_power)
        .def_readwrite("attack_speed", &CombatItem::attack_speed)
        .def_readwrite("critical_strike_chance",
                       &CombatItem::critical_strike_chance)
        .def_readwrite("critical_strike_damage",
                       &CombatItem::critical_strike_damage)
        .def_readwrite("health", &CombatItem::health)
        .def_readwrite("armor", &CombatItem::armor)
        .def_readwrite("magic_resist", &CombatItem::magic_resist)
        .def_readwrite("mana", &CombatItem::mana)
        .def_readwrite("omnivamp", &CombatItem::omnivamp)
        .def_readwrite("damage_amplification",
                       &CombatItem::damage_amplification)
        .def_readwrite("damage_reduction",
                       &CombatItem::damage_reduction)
        .def_readwrite("is_temporary", &CombatItem::is_temporary);

    // =========================================================
    // TRAIT
    // =========================================================

    py::class_<CombatTrait>(module, "CombatTrait")
        .def(py::init<>())
        .def_readwrite("id", &CombatTrait::id)
        .def_readwrite("api_name", &CombatTrait::api_name)
        .def_readwrite("name", &CombatTrait::name)
        .def_readwrite("active_count", &CombatTrait::active_count)
        .def_readwrite("tier", &CombatTrait::tier)
        .def_readwrite("active", &CombatTrait::active);

    // =========================================================
    // ABILITY
    // =========================================================

    py::class_<CombatAbility>(module, "CombatAbility")
        .def(py::init<>())
        .def_readwrite("id", &CombatAbility::id)
        .def_readwrite("api_name", &CombatAbility::api_name)
        .def_readwrite("name", &CombatAbility::name)
        .def_readwrite("description", &CombatAbility::description)
        .def_readwrite("mana_cost", &CombatAbility::mana_cost)
        .def_readwrite("initial_mana", &CombatAbility::initial_mana)
        .def_readwrite("target_type", &CombatAbility::target_type)
        .def_readwrite("damage_type", &CombatAbility::damage_type)
        .def_readwrite("base_damage", &CombatAbility::base_damage)
        .def_readwrite("base_healing", &CombatAbility::base_healing)
        .def_readwrite("shield_amount", &CombatAbility::shield_amount)
        .def_readwrite("ability_power_ratio",
                       &CombatAbility::ability_power_ratio)
        .def_readwrite("attack_damage_ratio",
                       &CombatAbility::attack_damage_ratio)
        .def_readwrite("area_radius", &CombatAbility::area_radius)
        .def_readwrite("duration", &CombatAbility::duration)
        .def_readwrite("has_damage", &CombatAbility::has_damage)
        .def_readwrite("has_healing", &CombatAbility::has_healing)
        .def_readwrite("has_shield", &CombatAbility::has_shield)
        .def_readwrite("has_buff", &CombatAbility::has_buff)
        .def_readwrite("has_debuff", &CombatAbility::has_debuff)
        .def_readwrite("has_area_effect",
                       &CombatAbility::has_area_effect);

    // =========================================================
    // UNIT
    // =========================================================

    py::class_<CombatUnit>(module, "CombatUnit")
        .def(py::init<>())
        .def_readwrite("id", &CombatUnit::id)
        .def_readwrite("api_name", &CombatUnit::api_name)
        .def_readwrite("name", &CombatUnit::name)
        .def_readwrite("star", &CombatUnit::star)
        .def_readwrite("team", &CombatUnit::team)
        .def_readwrite("role", &CombatUnit::role)
        .def_readwrite("position", &CombatUnit::position)
        .def_readwrite("hp", &CombatUnit::hp)
        .def_readwrite("max_hp", &CombatUnit::max_hp)
        .def_readwrite("mana", &CombatUnit::mana)
        .def_readwrite("max_mana", &CombatUnit::max_mana)
        .def_readwrite("attack_damage", &CombatUnit::attack_damage)
        .def_readwrite("ability_power", &CombatUnit::ability_power)
        .def_readwrite("attack_speed", &CombatUnit::attack_speed)
        .def_readwrite("attack_range", &CombatUnit::attack_range)
        .def_readwrite("critical_strike_chance",
                       &CombatUnit::critical_strike_chance)
        .def_readwrite("critical_strike_damage",
                       &CombatUnit::critical_strike_damage)
        .def_readwrite("armor", &CombatUnit::armor)
        .def_readwrite("magic_resist", &CombatUnit::magic_resist)
        .def_readwrite("damage_amplification",
                       &CombatUnit::damage_amplification)
        .def_readwrite("damage_reduction",
                       &CombatUnit::damage_reduction)
        .def_readwrite("omnivamp", &CombatUnit::omnivamp)
        .def_readwrite("ability", &CombatUnit::ability)
        .def_readwrite("items", &CombatUnit::items)
        .def_readwrite("traits", &CombatUnit::traits)
        .def_readwrite("alive", &CombatUnit::alive)
        .def_readwrite("can_move", &CombatUnit::can_move)
        .def_readwrite("can_attack", &CombatUnit::can_attack)
        .def_readwrite("can_cast", &CombatUnit::can_cast)
        .def_readwrite("source_board_position",
                       &CombatUnit::source_board_position);

    // =========================================================
    // TEAM
    // =========================================================

    py::class_<CombatTeam>(module, "CombatTeam")
        .def(py::init<>())
        .def_readwrite("team", &CombatTeam::team)
        .def_readwrite("player_id", &CombatTeam::player_id)
        .def_readwrite("player_hp", &CombatTeam::player_hp)
        .def_readwrite("units", &CombatTeam::units);

    // =========================================================
    // MODIFIER
    // =========================================================

    py::class_<CombatModifier>(module, "CombatModifier")
        .def(py::init<>())
        .def_readwrite("id", &CombatModifier::id)
        .def_readwrite("source", &CombatModifier::source)
        .def_readwrite("attack_damage", &CombatModifier::attack_damage)
        .def_readwrite("ability_power", &CombatModifier::ability_power)
        .def_readwrite("attack_speed", &CombatModifier::attack_speed)
        .def_readwrite("health", &CombatModifier::health)
        .def_readwrite("armor", &CombatModifier::armor)
        .def_readwrite("magic_resist", &CombatModifier::magic_resist)
        .def_readwrite("damage_amplification",
                       &CombatModifier::damage_amplification)
        .def_readwrite("damage_reduction",
                       &CombatModifier::damage_reduction)
        .def_readwrite("duration", &CombatModifier::duration)
        .def_readwrite("temporary", &CombatModifier::temporary);

    // =========================================================
    // CONFIG
    // =========================================================

    py::class_<CombatConfig>(module, "CombatConfig")
        .def(py::init<>())
        .def_readwrite("board_rows", &CombatConfig::board_rows)
        .def_readwrite("board_cols", &CombatConfig::board_cols)
        .def_readwrite("max_duration", &CombatConfig::max_duration)
        .def_readwrite("max_events", &CombatConfig::max_events)
        .def_readwrite("seed", &CombatConfig::seed)
        .def_readwrite("deterministic", &CombatConfig::deterministic)
        .def_readwrite("debug", &CombatConfig::debug)
        .def_readwrite("record_events", &CombatConfig::record_events)
        .def_readwrite("record_damage", &CombatConfig::record_damage)
        .def_readwrite("record_targets", &CombatConfig::record_targets)
        .def_readwrite("record_positions", &CombatConfig::record_positions)
        .def_readwrite("record_mana", &CombatConfig::record_mana)
        .def_readwrite("record_abilities",
                       &CombatConfig::record_abilities);

    // =========================================================
    // INPUT
    // =========================================================

    py::class_<CombatInput>(module, "CombatInput")
        .def(py::init<>())
        .def_readwrite("seed", &CombatInput::seed)
        .def_readwrite("context", &CombatInput::context)
        .def_readwrite("config", &CombatInput::config)
        .def_readwrite("player_a", &CombatInput::player_a)
        .def_readwrite("player_b", &CombatInput::player_b)
        .def_readwrite("global_modifiers",
                       &CombatInput::global_modifiers);

    // =========================================================
    // UNIT RESULT
    // =========================================================

    py::class_<CombatUnitResult>(module, "CombatUnitResult")
        .def(py::init<>())
        .def_readwrite("unit_id", &CombatUnitResult::unit_id)
        .def_readwrite("team", &CombatUnitResult::team)
        .def_readwrite("survived", &CombatUnitResult::survived)
        .def_readwrite("initial_hp", &CombatUnitResult::initial_hp)
        .def_readwrite("final_hp", &CombatUnitResult::final_hp)
        .def_readwrite("damage_dealt", &CombatUnitResult::damage_dealt)
        .def_readwrite("damage_taken", &CombatUnitResult::damage_taken)
        .def_readwrite("healing_done", &CombatUnitResult::healing_done)
        .def_readwrite("kills", &CombatUnitResult::kills)
        .def_readwrite("attacks", &CombatUnitResult::attacks)
        .def_readwrite("ability_casts", &CombatUnitResult::ability_casts)
        .def_readwrite("final_x", &CombatUnitResult::final_x)
        .def_readwrite("final_y", &CombatUnitResult::final_y);

    // =========================================================
    // DAMAGE EVENT
    // =========================================================

    py::class_<DamageEvent>(module, "DamageEvent")
        .def(py::init<>())
        .def_readwrite("timestamp", &DamageEvent::timestamp)
        .def_readwrite("source_unit_id", &DamageEvent::source_unit_id)
        .def_readwrite("target_unit_id", &DamageEvent::target_unit_id)
        .def_readwrite("damage_type", &DamageEvent::damage_type)
        .def_readwrite("raw_damage", &DamageEvent::raw_damage)
        .def_readwrite("final_damage", &DamageEvent::final_damage)
        .def_readwrite("critical", &DamageEvent::critical)
        .def_readwrite("ability_damage", &DamageEvent::ability_damage);

    // =========================================================
    // ATTACK EVENT
    // =========================================================

    py::class_<AttackEvent>(module, "AttackEvent")
        .def(py::init<>())
        .def_readwrite("timestamp", &AttackEvent::timestamp)
        .def_readwrite("source_unit_id", &AttackEvent::source_unit_id)
        .def_readwrite("target_unit_id", &AttackEvent::target_unit_id)
        .def_readwrite("critical", &AttackEvent::critical)
        .def_readwrite("damage", &AttackEvent::damage);

    // =========================================================
    // ABILITY EVENT
    // =========================================================

    py::class_<AbilityEvent>(module, "AbilityEvent")
        .def(py::init<>())
        .def_readwrite("timestamp", &AbilityEvent::timestamp)
        .def_readwrite("source_unit_id", &AbilityEvent::source_unit_id)
        .def_readwrite("ability_id", &AbilityEvent::ability_id)
        .def_readwrite("target_unit_ids", &AbilityEvent::target_unit_ids)
        .def_readwrite("damage", &AbilityEvent::damage)
        .def_readwrite("healing", &AbilityEvent::healing)
        .def_readwrite("shield", &AbilityEvent::shield);

    // =========================================================
    // POSITION EVENT
    // =========================================================

    py::class_<PositionEvent>(module, "PositionEvent")
        .def(py::init<>())
        .def_readwrite("timestamp", &PositionEvent::timestamp)
        .def_readwrite("unit_id", &PositionEvent::unit_id)
        .def_readwrite("from_x", &PositionEvent::from_x)
        .def_readwrite("from_y", &PositionEvent::from_y)
        .def_readwrite("to_x", &PositionEvent::to_x)
        .def_readwrite("to_y", &PositionEvent::to_y);

    // =========================================================
    // DEATH EVENT
    // =========================================================

    py::class_<DeathEvent>(module, "DeathEvent")
        .def(py::init<>())
        .def_readwrite("timestamp", &DeathEvent::timestamp)
        .def_readwrite("unit_id", &DeathEvent::unit_id)
        .def_readwrite("killer_unit_id", &DeathEvent::killer_unit_id);

    // =========================================================
    // GENERIC EVENT
    // =========================================================

    py::class_<CombatEvent>(module, "CombatEvent")
        .def(py::init<>())
        .def_readwrite("timestamp", &CombatEvent::timestamp)
        .def_readwrite("type", &CombatEvent::type)
        .def_readwrite("source_unit_id", &CombatEvent::source_unit_id)
        .def_readwrite("target_unit_id", &CombatEvent::target_unit_id)
        .def_readwrite("value", &CombatEvent::value)
        .def_readwrite("data", &CombatEvent::data);

    // =========================================================
    // RESULT
    // =========================================================

    py::class_<CombatResult>(module, "CombatResult")
        .def(py::init<>())
        .def_readwrite("winner", &CombatResult::winner)
        .def_readwrite("context", &CombatResult::context)
        .def_readwrite("duration", &CombatResult::duration)
        .def_readwrite("events_processed", &CombatResult::events_processed)
        .def_readwrite("timeout", &CombatResult::timeout)
        .def_readwrite("completed", &CombatResult::completed)
        .def_readwrite("player_a_damage", &CombatResult::player_a_damage)
        .def_readwrite("player_b_damage", &CombatResult::player_b_damage)
        .def_readwrite("player_a_survivors", &CombatResult::player_a_survivors)
        .def_readwrite("player_b_survivors", &CombatResult::player_b_survivors)
        .def_readwrite("player_a_deaths", &CombatResult::player_a_deaths)
        .def_readwrite("player_b_deaths", &CombatResult::player_b_deaths)
        .def_readwrite("player_a_damage_dealt",
                       &CombatResult::player_a_damage_dealt)
        .def_readwrite("player_b_damage_dealt",
                       &CombatResult::player_b_damage_dealt)
        .def_readwrite("units", &CombatResult::units)
        .def_readwrite("events", &CombatResult::events)
        .def_readwrite("damage_events", &CombatResult::damage_events)
        .def_readwrite("attack_events", &CombatResult::attack_events)
        .def_readwrite("ability_events", &CombatResult::ability_events)
        .def_readwrite("position_events", &CombatResult::position_events)
        .def_readwrite("death_events", &CombatResult::death_events)
        .def_readwrite("success", &CombatResult::success)
        .def_readwrite("error_code", &CombatResult::error_code)
        .def_readwrite("error_message", &CombatResult::error_message);
       
        module.def(
            "simulate",
            [](const tft::CombatInput& input)
            {
                const tft::CombatEngine engine;
                return engine.simulate(input);
            },
            py::arg("combat_input"),
            "Executa uma simulacao de combate"
        );
    }