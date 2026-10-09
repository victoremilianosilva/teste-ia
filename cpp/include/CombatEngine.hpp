
#pragma once

// Entrada e resultado padronizados do motor de combate.
#include "CombatInput.hpp"
#include "CombatResult.hpp"

namespace tft {

/**
 * @brief Responsável por executar as simulações de combate.
 *
 * Esta classe mantém a lógica de combate no C++.
 * O Python envia um CombatInput e recebe um CombatResult,
 * sem precisar executar cada ataque ou evento individualmente.
 */
class CombatEngine {
public:
    // Construtor padrão: o motor ainda não precisa manter estado
    // entre diferentes chamadas de simulação.
    CombatEngine() = default;

    /**
     * @brief Executa uma simulação usando a entrada recebida.
     *
     * Nesta etapa, o método valida a entrada e prepara o resultado.
     * A movimentação, os ataques e as habilidades serão implementados
     * nas próximas etapas.
     *
     * @param input Dados das equipes, unidades e configurações.
     * @return Resultado contendo o status da operação e possíveis erros.
     */
    CombatResult simulate(const CombatInput& input) const;
};

} // namespace tft