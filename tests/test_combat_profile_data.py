import copy
import json
import sys
from pathlib import Path

# ============================================================
# CONFIGURAÇÃO
# ============================================================

TESTS_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = TESTS_DIR.parent

SOURCE_FILE = TESTS_DIR / "units.json"
OUTPUT_FILE = PROJECT_ROOT / "units_gerado.json"
REPORT_FILE = PROJECT_ROOT / "relatorio_units_gerado.txt"

SET_DESEJADO = "17"

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from combat.CombatProfileManager import (
    CombatProfileManager,
    UnitRole,
)


# ============================================================
# MAPEAMENTO DOS ATRIBUTOS
# ============================================================

STAT_MAP = {
    "hp": "max_hp",
    "damage": "attack_damage",
    "attackSpeed": "attack_speed",
    "armor": "armor",
    "magicResist": "magic_resist",
    "range": "attack_range",
}

REQUIRED_STATS = list(STAT_MAP.values())


# ============================================================
# VALORES-BASE ESTIMADOS POR CUSTO
#
# Usados somente quando o JSON não possui um atributo válido.
# Não representam valores oficiais do TFT.
# ============================================================

BASE_BY_COST = {
    1: {
        "max_hp": 650.0,
        "attack_damage": 45.0,
        "attack_speed": 0.70,
        "armor": 30.0,
        "magic_resist": 30.0,
    },
    2: {
        "max_hp": 750.0,
        "attack_damage": 50.0,
        "attack_speed": 0.70,
        "armor": 35.0,
        "magic_resist": 35.0,
    },
    3: {
        "max_hp": 850.0,
        "attack_damage": 55.0,
        "attack_speed": 0.75,
        "armor": 35.0,
        "magic_resist": 35.0,
    },
    4: {
        "max_hp": 950.0,
        "attack_damage": 60.0,
        "attack_speed": 0.75,
        "armor": 40.0,
        "magic_resist": 40.0,
    },
    5: {
        "max_hp": 1100.0,
        "attack_damage": 65.0,
        "attack_speed": 0.80,
        "armor": 40.0,
        "magic_resist": 40.0,
    },
    6: {
        "max_hp": 1200.0,
        "attack_damage": 70.0,
        "attack_speed": 0.80,
        "armor": 45.0,
        "magic_resist": 45.0,
    },
    7: {
        "max_hp": 1300.0,
        "attack_damage": 75.0,
        "attack_speed": 0.85,
        "armor": 45.0,
        "magic_resist": 45.0,
    },
    8: {
        "max_hp": 1400.0,
        "attack_damage": 80.0,
        "attack_speed": 0.85,
        "armor": 50.0,
        "magic_resist": 50.0,
    },
    9: {
        "max_hp": 1500.0,
        "attack_damage": 85.0,
        "attack_speed": 0.90,
        "armor": 50.0,
        "magic_resist": 50.0,
    },
}

# Ajustes relativos por role.
# São aplicados apenas aos atributos que precisam ser estimados.
ROLE_MODIFIERS = {
    "TANK": {
        "max_hp": 1.20,
        "attack_damage": 0.85,
        "attack_speed": 0.90,
        "armor": 1.25,
        "magic_resist": 1.25,
    },
    "CARRY": {
        "max_hp": 0.95,
        "attack_damage": 1.20,
        "attack_speed": 1.15,
        "armor": 0.90,
        "magic_resist": 0.90,
    },
    "SUPPORT": {
        "max_hp": 1.00,
        "attack_damage": 0.85,
        "attack_speed": 0.95,
        "armor": 1.00,
        "magic_resist": 1.00,
    },
    "FIGHTER": {
        "max_hp": 1.10,
        "attack_damage": 1.05,
        "attack_speed": 1.00,
        "armor": 1.05,
        "magic_resist": 1.05,
    },
    "ASSASSIN": {
        "max_hp": 0.90,
        "attack_damage": 1.10,
        "attack_speed": 1.10,
        "armor": 0.90,
        "magic_resist": 0.90,
    },
}

# Alcance estimado somente quando estiver ausente ou inválido.
ROLE_RANGE = {
    "TANK": 1.0,
    "CARRY": 4.0,
    "SUPPORT": 3.0,
    "FIGHTER": 1.0,
    "ASSASSIN": 1.0,
}

# Limites de segurança para evitar valores absurdos.
# Não substituem atributos reais válidos.
STAT_LIMITS = {
    "max_hp": (1.0, 5000.0),
    "attack_damage": (0.0, 500.0),
    "attack_speed": (0.1, 3.0),
    "armor": (0.0, 300.0),
    "magic_resist": (0.0, 300.0),
    "attack_range": (0.0, 10.0),
}


# ============================================================
# LEITURA DO JSON
# ============================================================

def load_json(path):
    if not path.exists():
        raise FileNotFoundError(
            f"Arquivo não encontrado: {path}"
        )

    with path.open("r", encoding="utf-8-sig") as file:
        return json.load(file)


def get_set_champions(data, desired_set):
    sets = data.get("sets", {})

    if isinstance(sets, dict):
        selected = sets.get(str(desired_set))

        if isinstance(selected, dict):
            champions = selected.get("champions", [])

            if isinstance(champions, list):
                return champions

    set_data = data.get("setData", [])

    if isinstance(set_data, list):
        for item in set_data:
            if not isinstance(item, dict):
                continue

            set_id = str(
                item.get("number", item.get("name", ""))
            )

            if set_id == str(desired_set):
                champions = item.get("champions", [])

                if isinstance(item.get("champions"), list):
                    return champions

    raise ValueError(
        f"Set {desired_set} não encontrado."
    )


# ============================================================
# VALIDAÇÃO DOS ATRIBUTOS
# ============================================================

def is_valid_number(value):
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and value == value
        and abs(value) != float("inf")
    )


def extract_stats(champion):
    source_stats = champion.get("stats") or {}

    if not isinstance(source_stats, dict):
        source_stats = {}

    normalized = {}
    missing = []

    for source_key, target_key in STAT_MAP.items():
        value = source_stats.get(source_key)

        if is_valid_number(value):
            minimum, maximum = STAT_LIMITS[target_key]

            if minimum <= value <= maximum:
                normalized[target_key] = float(value)
                continue

        normalized[target_key] = None
        missing.append(target_key)

    return normalized, missing


def has_traits(champion):
    traits = champion.get("traits")

    return isinstance(traits, list) and len(traits) > 0


def normalize_cost(value):
    if not is_valid_number(value):
        return 1

    return max(1, min(9, int(value)))


# ============================================================
# ROLE E PERFIL DE COMBATE
# ============================================================

def create_profile_manager():
    return CombatProfileManager()


def process_with_existing_algorithm(manager, champion):
    """
    Executa o algoritmo existente do projeto.

    Os atributos são disponibilizados no nível superior porque
    o CombatProfileManager atual lê esses campos dessa forma.
    """
    processed = manager.process_unit(
        copy.deepcopy(champion)
    )

    if not isinstance(processed, dict):
        raise ValueError(
            f"process_unit não retornou um dicionário para "
            f"{champion.get('name')}."
        )

    return processed


def role_name_from_value(value):
    try:
        return UnitRole(int(value)).name.upper()
    except (ValueError, TypeError):
        return "FIGHTER"


# ============================================================
# ESTIMATIVA DOS CAMPOS AUSENTES
# ============================================================

def estimate_missing_stats(stats, missing, cost, role_name):
    """
    Preserva todos os atributos válidos.

    Para campos ausentes:
      - usa a base correspondente ao custo;
      - ajusta os atributos conforme a role;
      - estima alcance conforme a role.
    """
    base = BASE_BY_COST.get(
        cost,
        BASE_BY_COST[1],
    )

    modifiers = ROLE_MODIFIERS.get(
        role_name,
        ROLE_MODIFIERS["FIGHTER"],
    )

    estimates = {}

    for field in missing:
        if field == "attack_range":
            value = ROLE_RANGE.get(
                role_name,
                1.0,
            )
        else:
            value = (
                base[field]
                * modifiers.get(field, 1.0)
            )

        minimum, maximum = STAT_LIMITS[field]
        value = max(minimum, min(maximum, value))

        stats[field] = round(float(value), 4)
        estimates[field] = stats[field]

    return estimates


# ============================================================
# GERAÇÃO DO CATÁLOGO
# ============================================================

def generate_units():
    print(f"Lendo arquivo: {SOURCE_FILE}")

    data = load_json(SOURCE_FILE)
    champions = get_set_champions(
        data,
        SET_DESEJADO,
    )

    manager = create_profile_manager()

    generated_units = []
    skipped_without_traits = []
    report_lines = []

    total_estimated_fields = 0
    units_with_estimates = 0

    report_lines.append(
        f"Relatório de geração — Set {SET_DESEJADO}"
    )
    report_lines.append("=" * 70)

    print(f"Registros encontrados: {len(champions)}")

    for original in champions:
        if not isinstance(original, dict):
            continue

        name = original.get("name", "Desconhecido")
        api_name = original.get("apiName")

        # Regra acordada para este conjunto.
        if not has_traits(original):
            skipped_without_traits.append(name)
            continue

        if not api_name:
            raise ValueError(
                f"{name}: apiName ausente. "
                "Geração cancelada para evitar IDs inválidos."
            )

        cost = normalize_cost(original.get("cost"))
        stats, missing = extract_stats(original)

        # ----------------------------------------------------
        # PRIMEIRA PASSAGEM: inferência da role
        # ----------------------------------------------------

        # Valores genéricos provisórios permitem executar
        # o algoritmo existente mesmo quando faltam atributos.
        provisional = copy.deepcopy(stats)

        base = BASE_BY_COST[cost]

        for field in REQUIRED_STATS:
            if provisional[field] is None:
                if field == "attack_range":
                    provisional[field] = 1.0
                else:
                    provisional[field] = base[field]

        role_input = copy.deepcopy(original)
        role_input["cost"] = cost

        # Os atributos usados pelo CombatProfileManager
        # precisam estar também no nível superior.
        role_input.update(provisional)

        first_pass = process_with_existing_algorithm(
            manager,
            role_input,
        )

        initial_role = role_name_from_value(
            first_pass.get("role", int(UnitRole.FIGHTER))
        )

        # ----------------------------------------------------
        # SEGUNDA PASSAGEM: estimativas específicas da role
        # ----------------------------------------------------

        estimates = estimate_missing_stats(
            stats=stats,
            missing=missing,
            cost=cost,
            role_name=initial_role,
        )

        # Todos os atributos normalizados agora estão preenchidos.
        final_input = copy.deepcopy(original)
        final_input["cost"] = cost
        final_input.update(stats)

        # Executa novamente o algoritmo real para produzir
        # o perfil de combate definitivo.
        processed = process_with_existing_algorithm(
            manager,
            final_input,
        )

        final_role_value = processed.get(
            "role",
            int(UnitRole.FIGHTER),
        )

        try:
            final_role = UnitRole(int(final_role_value))
        except (TypeError, ValueError):
            raise ValueError(
                f"{name}: role final inválida: "
                f"{final_role_value}"
            )

        combat_profile = processed.get("combat_profile")

        if not isinstance(combat_profile, dict):
            raise ValueError(
                f"{name}: combat_profile não foi gerado."
            )

        # ----------------------------------------------------
        # MONTA O REGISTRO FINAL
        # ----------------------------------------------------

        unit = copy.deepcopy(original)

        unit["name"] = name
        unit["apiName"] = api_name
        unit["cost"] = cost
        unit["traits"] = list(original["traits"])

        # Formato normalizado pedido para o catálogo.
        unit["stats"] = {
            field: stats[field]
            for field in REQUIRED_STATS
        }

        # Role e perfil calculados previamente.
        unit["role"] = int(final_role)
        unit["role_name"] = final_role.name.lower()
        unit["combat_profile"] = combat_profile

        # Não deixar campos antigos que indiquem falta de dados.
        unit.pop("missing_stats", None)

        generated_units.append(unit)

        # ----------------------------------------------------
        # RELATÓRIO DE ESTIMATIVAS
        # ----------------------------------------------------

        if estimates:
            units_with_estimates += 1
            total_estimated_fields += len(estimates)

        report_lines.append(
            f"\n{name} | API: {api_name} | custo: {cost}"
        )
        report_lines.append(
            f"  Role inicial: {initial_role}"
        )
        report_lines.append(
            f"  Role final: {final_role.name.lower()}"
        )

        if estimates:
            report_lines.append(
                "  Atributos estimados:"
            )

            for field, value in estimates.items():
                report_lines.append(
                    f"    {field}: {value}"
                )
        else:
            report_lines.append(
                "  Atributos estimados: nenhum"
            )

    # ========================================================
    # VALIDAÇÃO FINAL
    # ========================================================

    if not generated_units:
        raise RuntimeError(
            "Nenhuma unidade jogável foi gerada."
        )

    # Evita IDs duplicados no catálogo.
    api_names = [
        unit["apiName"]
        for unit in generated_units
    ]

    if len(api_names) != len(set(api_names)):
        raise RuntimeError(
            "Existem apiName duplicados. "
            "Geração cancelada."
        )

    # Verifica se todos os atributos estão presentes.
    for unit in generated_units:
        for field in REQUIRED_STATS:
            value = unit["stats"].get(field)

            if not is_valid_number(value):
                raise RuntimeError(
                    f"{unit['name']}: atributo inválido "
                    f"após estimativa: {field}={value}"
                )

    # ========================================================
    # SALVAMENTO
    # ========================================================

    with OUTPUT_FILE.open("w", encoding="utf-8") as file:
        json.dump(
            generated_units,
            file,
            ensure_ascii=False,
            indent=2,
        )

    role_counts = {}

    for unit in generated_units:
        role = unit["role_name"]
        role_counts[role] = role_counts.get(role, 0) + 1

    report_lines.extend([
        "",
        "=" * 70,
        "RESUMO",
        "=" * 70,
        f"Set: {SET_DESEJADO}",
        f"Registros no conjunto: {len(champions)}",
        f"Unidades geradas: {len(generated_units)}",
        f"Unidades sem traits ignoradas: {len(skipped_without_traits)}",
        f"Unidades com estimativas: {units_with_estimates}",
        f"Total de campos estimados: {total_estimated_fields}",
        "",
        "Distribuição de roles:",
    ])

    for role, count in sorted(role_counts.items()):
        report_lines.append(f"  {role}: {count}")

    report_lines.extend([
        "",
        "Observações:",
        "- Atributos numéricos válidos foram preservados.",
        "- Atributos ausentes ou inválidos foram estimados.",
        "- As estimativas não são dados oficiais do TFT.",
        "- Role e combat_profile foram pré-calculados.",
        "- O arquivo de origem não foi modificado.",
    ])

    REPORT_FILE.write_text(
        "\n".join(report_lines),
        encoding="utf-8",
    )

    # ========================================================
    # RESULTADO
    # ========================================================

    print("\n========== GERAÇÃO CONCLUÍDA ==========")
    print(f"Set: {SET_DESEJADO}")
    print(f"Registros na fonte: {len(champions)}")
    print(f"Unidades geradas: {len(generated_units)}")
    print(
        f"Unidades sem traits ignoradas: "
        f"{len(skipped_without_traits)}"
    )
    print(f"Unidades com estimativas: {units_with_estimates}")
    print(f"Campos estimados: {total_estimated_fields}")

    print("\nDistribuição de roles:")

    for role, count in sorted(role_counts.items()):
        print(f"  {role}: {count}")

    print(f"\nJSON gerado: {OUTPUT_FILE}")
    print(f"Relatório: {REPORT_FILE}")
    print("\nO arquivo de origem permanece intacto.")


if __name__ == "__main__":
    generate_units()