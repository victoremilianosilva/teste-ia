#pragma once

#include "CombatInput.hpp"
#include "CombatResult.hpp"

namespace tft {

class CombatEngine {
public:
    CombatEngine() = default;

    CombatResult simulate(const CombatInput& input) const;
};

} // namespace tft