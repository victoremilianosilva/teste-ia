
#include "CombatEngine.hpp"

namespace tft {

CombatResult CombatEngine::simulate(const CombatInput& input) const
{
    CombatResult result;

    result.context = input.context;
    result.winner = CombatWinner::DRAW;

    result.duration = 0.0f;
    result.events_processed = 0;

    result.timeout = false;
    result.completed = false;
    result.success = true;

    result.player_a_damage = 0.0f;
    result.player_b_damage = 0.0f;

    result.player_a_survivors = 0;
    result.player_b_survivors = 0;

    result.player_a_deaths = 0;
    result.player_b_deaths = 0;

    result.player_a_damage_dealt = 0.0f;
    result.player_b_damage_dealt = 0.0f;

    return result;
}

} // namespace tft