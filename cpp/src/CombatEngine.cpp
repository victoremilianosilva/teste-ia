
#include "CombatEngine.hpp"

#include <cmath>
#include <string>
#include <unordered_set>

namespace tft {

namespace {

/**
 * @brief Registra uma falha de validação no resultado.
 *
 * Mantemos a informação no CombatResult para que o Python possa
 * identificar a causa sem precisar interpretar mensagens genéricas.
 */
void set_error(
    CombatResult& result,
    const std::string& code,
    const std::string& message)
{
    result.success = false;
    result.completed = false;
    result.error_code = code;
    result.error_message = message;
}

/**
 * @brief Verifica se um número é finito e não negativo.
 *
 * Isso evita que valores como NaN, infinito ou atributos negativos
 * indevidos contaminem os cálculos da simulação.
 */
bool is_valid_non_negative(float value)
{
    return std::isfinite(value) && value >= 0.0f;
}

/**
 * @brief Valida uma equipe antes de iniciar o combate.
 *
 * A validação verifica:
 * - Identidade da equipe.
 * - Existência de unidades.
 * - Identificadores únicos.
 * - Vida e atributos numéricos.
 * - Estrelas e posições dentro do tabuleiro.
 *
 * O conjunto unit_ids é compartilhado entre as duas equipes para
 * impedir que duas unidades tenham o mesmo ID na mesma batalha.
 */
bool validate_team(
    const CombatTeam& team,
    UnitTeam expected_team,
    const CombatConfig& config,
    std::unordered_set<int>& unit_ids,
    CombatResult& result)
{
    // Garante que os dados da equipe correspondam ao lado esperado.
    if (team.team != expected_team) {
        set_error(
            result,
            "INVALID_TEAM",
            "A identificacao da equipe nao corresponde ao lado esperado."
        );
        return false;
    }

    // Uma batalha precisa ter pelo menos uma unidade de cada lado.
    if (team.units.empty()) {
        set_error(
            result,
            "EMPTY_TEAM",
            "Uma das equipes nao possui unidades para combater."
        );
        return false;
    }

    // A vida do jogador precisa ser válida para calcular o resultado
    // do combate e o dano posterior no lobby.
    if (!is_valid_non_negative(team.player_hp) || team.player_hp <= 0.0f) {
        set_error(
            result,
            "INVALID_PLAYER_HP",
            "A vida do jogador deve ser um numero finito maior que zero."
        );
        return false;
    }

    // Evita posições duplicadas dentro da mesma equipe.
    // Equipes diferentes podem ocupar coordenadas equivalentes,
    // pois cada lado pode usar sua própria referência de tabuleiro.
    std::unordered_set<int> occupied_positions;

    for (const CombatUnit& unit : team.units) {

        // IDs negativos não são aceitos e IDs precisam ser únicos
        // entre todas as unidades dos dois lados.
        if (unit.id < 0 || !unit_ids.insert(unit.id).second) {
            set_error(
                result,
                "INVALID_UNIT_ID",
                "Uma unidade possui ID negativo ou duplicado."
            );
            return false;
        }

        // A unidade precisa pertencer à equipe que a contém.
        if (unit.team != expected_team) {
            set_error(
                result,
                "UNIT_TEAM_MISMATCH",
                "Uma unidade esta associada a uma equipe incorreta."
            );
            return false;
        }

        // Nesta etapa, somente unidades vivas podem iniciar o combate.
        if (!unit.alive) {
            set_error(
                result,
                "DEAD_UNIT_IN_INPUT",
                "A entrada contem uma unidade marcada como morta."
            );
            return false;
        }

        // A graduação por estrelas deve estar dentro do intervalo aceito.
        if (unit.star < 1 || unit.star > 3) {
            set_error(
                result,
                "INVALID_STAR_LEVEL",
                "O nivel de estrelas da unidade deve estar entre 1 e 3."
            );
            return false;
        }

        // A posição precisa respeitar as dimensões configuradas.
        if (unit.position.x < 0 ||
            unit.position.x >= config.board_cols ||
            unit.position.y < 0 ||
            unit.position.y >= config.board_rows) {

            set_error(
                result,
                "INVALID_POSITION",
                "Uma unidade esta fora dos limites do tabuleiro."
            );
            return false;
        }

        // Converte a posição bidimensional em uma chave inteira
        // para detectar posições repetidas dentro da mesma equipe.
        const int position_key =
            unit.position.y * config.board_cols + unit.position.x;

        if (!occupied_positions.insert(position_key).second) {
            set_error(
                result,
                "DUPLICATE_POSITION",
                "Duas unidades da mesma equipe ocupam a mesma posicao."
            );
            return false;
        }

        // Vida máxima deve ser positiva e a vida atual precisa
        // estar dentro do intervalo válido.
        if (!std::isfinite(unit.max_hp) ||
            !std::isfinite(unit.hp) ||
            unit.max_hp <= 0.0f ||
            unit.hp <= 0.0f ||
            unit.hp > unit.max_hp) {

            set_error(
                result,
                "INVALID_HEALTH",
                "A vida atual ou a vida maxima da unidade e invalida."
            );
            return false;
        }

        // Velocidade de ataque precisa ser positiva para permitir
        // o agendamento de ataques na simulação.
        if (!std::isfinite(unit.attack_speed) ||
            unit.attack_speed <= 0.0f) {

            set_error(
                result,
                "INVALID_ATTACK_SPEED",
                "A velocidade de ataque deve ser finita e maior que zero."
            );
            return false;
        }

        // Valida os atributos que serão usados nos cálculos de combate.
        // Valores não finitos poderiam propagar erros numéricos.
        if (!is_valid_non_negative(unit.mana) ||
            !is_valid_non_negative(unit.max_mana) ||
            !is_valid_non_negative(unit.attack_damage) ||
            !is_valid_non_negative(unit.ability_power) ||
            !is_valid_non_negative(unit.attack_range) ||
            !is_valid_non_negative(unit.critical_strike_chance) ||
            !is_valid_non_negative(unit.critical_strike_damage) ||
            !is_valid_non_negative(unit.omnivamp)) {

            set_error(
                result,
                "INVALID_UNIT_ATTRIBUTES",
                "Uma unidade possui atributos negativos ou nao finitos."
            );
            return false;
        }

        // A mana atual não pode ultrapassar o limite configurado.
        if (unit.mana > unit.max_mana) {
            set_error(
                result,
                "INVALID_MANA",
                "A mana atual ultrapassa a mana maxima da unidade."
            );
            return false;
        }

        // A amplificação e a redução de dano podem depender de
        // modificadores e regras futuras. Por enquanto, exigimos
        // apenas valores finitos para evitar NaN e infinito.
        if (!std::isfinite(unit.damage_amplification) ||
            !std::isfinite(unit.damage_reduction) ||
            !std::isfinite(unit.armor) ||
            !std::isfinite(unit.magic_resist)) {

            set_error(
                result,
                "INVALID_DEFENSIVE_ATTRIBUTES",
                "Uma unidade possui atributos defensivos nao finitos."
            );
            return false;
        }
    }

    return true;
}

} // namespace anônimo

/**
 * @brief Valida a entrada e prepara o resultado inicial.
 *
 * IMPORTANTE:
 * Esta versão ainda não executa ataques nem movimentação.
 * O campo completed permanece falso até implementarmos a simulação real.
 */
CombatResult CombatEngine::simulate(const CombatInput& input) const
{
    CombatResult result;

    // Preserva o contexto recebido para que o chamador saiba
    // se a solicitação era um combate PvP ou PvE.
    result.context = input.context;

    // Inicializa o resultado como não concluído.
    // A operação só será marcada como concluída quando existir
    // uma simulação real que determine o vencedor.
    result.winner = CombatWinner::DRAW;
    result.completed = false;
    result.success = true;
    result.timeout = false;
    result.duration = 0.0f;
    result.events_processed = 0;

    // Valida as configurações globais antes de consultar as unidades.
    if (input.config.board_rows <= 0 ||
        input.config.board_cols <= 0) {

        set_error(
            result,
            "INVALID_BOARD_SIZE",
            "As dimensoes do tabuleiro devem ser maiores que zero."
        );
        return result;
    }

    if (!std::isfinite(input.config.max_duration) ||
        input.config.max_duration <= 0.0f) {

        set_error(
            result,
            "INVALID_MAX_DURATION",
            "A duracao maxima deve ser finita e maior que zero."
        );
        return result;
    }

    if (input.config.max_events == 0) {
        set_error(
            result,
            "INVALID_MAX_EVENTS",
            "O limite de eventos deve ser maior que zero."
        );
        return result;
    }

    // O mesmo conjunto é usado para as duas equipes, garantindo
    // que IDs repetidos entre lados diferentes também sejam rejeitados.
    std::unordered_set<int> unit_ids;

    // Valida primeiro o lado A.
    if (!validate_team(
            input.player_a,
            UnitTeam::PLAYER_A,
            input.config,
            unit_ids,
            result)) {
        return result;
    }

    // Valida o lado B.
    if (!validate_team(
            input.player_b,
            UnitTeam::PLAYER_B,
            input.config,
            unit_ids,
            result)) {
        return result;
    }

    // Se chegamos até aqui, a entrada está estruturalmente válida.
    // Ainda não existe simulação de combate nesta etapa.
    //
    // success = true significa que a entrada foi aceita.
    // completed = false significa que o combate ainda não foi executado.
    result.success = true;
    result.completed = false;
    result.error_code.clear();
    result.error_message.clear();

    return result;
}

} // namespace tft