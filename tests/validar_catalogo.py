# tests/validar_catalogo.py

import sys
from pathlib import Path
from collections import Counter

# Permite executar o script diretamente dentro de tests/.
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from units.UnitManager import UnitManager


REQUIRED_STATS = (
    "max_hp",
    "attack_damage",
    "attack_speed",
    "armor",
    "magic_resist",
    "attack_range",
)

VALID_ROLES = {
    "TANK",
    "CARRY",
    "SUPPORT",
    "FIGHTER",
    "ASSASSIN",
}


def check(condition, message, errors):
    if condition:
        print(f"[OK] {message}")
    else:
        print(f"[ERRO] {message}")
        errors.append(message)


def main():
    errors = []

    print("=" * 65)
    print("VALIDAÇÃO DO CATÁLOGO TFT")
    print("=" * 65)

    # ---------------------------------------------------------
    # 1. Carregamento
    # ---------------------------------------------------------

    manager = UnitManager()
    champions = manager.champions

    check(
        len(champions) > 0,
        f"Catálogo carregado: {len(champions)} unidades",
        errors,
    )

    # ---------------------------------------------------------
    # 2. IDs originais e duplicados
    # ---------------------------------------------------------

    data_ids = [
        manager.get_data_id(champion)
        for champion in champions
    ]

    valid_ids = [
        data_id
        for data_id in data_ids
        if data_id is not None
    ]

    duplicated_ids = [
        data_id
        for data_id, count in Counter(valid_ids).items()
        if count > 1
    ]

    check(
        not duplicated_ids,
        "IDs originais únicos",
        errors,
    )

    if duplicated_ids:
        print("IDs duplicados:", duplicated_ids)

    # ---------------------------------------------------------
    # 3. Atributos
    # ---------------------------------------------------------

    missing_stats = []
    invalid_stats = []

    for champion in champions:
        name = champion.get("name", "Unknown")
        stats = champion.get("stats", {})

        for stat in REQUIRED_STATS:
            value = stats.get(stat)

            if value is None:
                missing_stats.append((name, stat))
                continue

            if (
                isinstance(value, bool)
                or not isinstance(value, (int, float))
            ):
                invalid_stats.append((name, stat, value))
                continue

            if value != value or abs(value) == float("inf"):
                invalid_stats.append((name, stat, value))

    check(
        not missing_stats,
        f"Seis atributos presentes em todas as unidades "
        f"({len(champions)} verificadas)",
        errors,
    )

    check(
        not invalid_stats,
        "Todos os atributos são numéricos e finitos",
        errors,
    )

    if missing_stats:
        print("\nAtributos ausentes:")
        for name, stat in missing_stats[:20]:
            print(f"  - {name}: {stat}")

    if invalid_stats:
        print("\nAtributos inválidos:")
        for name, stat, value in invalid_stats[:20]:
            print(f"  - {name}: {stat} = {value!r}")

    # ---------------------------------------------------------
    # 4. Role e perfil de combate
    # ---------------------------------------------------------

    invalid_roles = []
    missing_profiles = []

    for champion in champions:
        name = champion.get("name", "Unknown")
        role_name = champion.get("role_name")
        role = champion.get("role")
        profile = champion.get("combat_profile")

        normalized_role = (
            role_name.upper()
            if isinstance(role_name, str)
            else None
        )

        if normalized_role not in VALID_ROLES:
            # Também aceita enums quando role_name não está presente.
            enum_name = getattr(role, "name", None)

            if enum_name not in VALID_ROLES:
                invalid_roles.append(
                    (name, role_name, repr(role))
                )

        if not isinstance(profile, dict) or not profile:
            missing_profiles.append(name)

    check(
        not invalid_roles,
        "Role válido para todas as unidades",
        errors,
    )

    check(
        not missing_profiles,
        "Combat profile presente em todas as unidades",
        errors,
    )

    if invalid_roles:
        print("\nRoles inválidos:")
        for item in invalid_roles[:20]:
            print("  -", item)

    if missing_profiles:
        print("\nPerfis ausentes:")
        for name in missing_profiles[:20]:
            print("  -", name)

    # ---------------------------------------------------------
    # 5. Traits
    # ---------------------------------------------------------

    invalid_traits = [
        champion.get("name", "Unknown")
        for champion in champions
        if not isinstance(champion.get("traits"), list)
    ]

    units_with_traits = sum(
        bool(champion.get("traits"))
        for champion in champions
    )

    check(
        not invalid_traits,
        "Traits representadas como listas",
        errors,
    )

    print(f"Unidades com traits: {units_with_traits}")

    # ---------------------------------------------------------
    # 6. Criação de unidade
    # ---------------------------------------------------------

    champion = champions[0]

    try:
        unit_a = manager.create_unit(champion)
        unit_b = manager.create_unit(champion)

        check(
            unit_a["id"] == unit_b["id"],
            "Cópias do mesmo campeão compartilham ID interno",
            errors,
        )

        check(
            unit_a["uuid"] != unit_b["uuid"],
            "Cada instância recebe UUID único",
            errors,
        )

        check(
            unit_a["champion_id"] == unit_b["champion_id"],
            "Identificador original preservado",
            errors,
        )

        check(
            unit_a["stats"] == champion["stats"],
            "Atributos preservados na instância",
            errors,
        )

        check(
            unit_a["combat_profile"] == champion["combat_profile"],
            "Perfil de combate preservado na instância",
            errors,
        )

        check(
            manager.is_valid_unit(unit_a),
            "Instância reconhecida como unidade válida",
            errors,
        )

    except Exception as exc:
        errors.append(f"Erro criando unidades: {exc}")
        print(f"[ERRO] Criação de unidades: {exc}")

    # ---------------------------------------------------------
    # 7. Contagem e upgrade
    # ---------------------------------------------------------

    try:
        counts = manager.count_copies([unit_a, unit_b])

        check(
            counts.get(unit_a["id"]) == 2,
            "Contagem de duas cópias de uma unidade 1 estrela",
            errors,
        )

        upgraded = manager.create_upgraded_unit(
            unit_a,
            2,
        )

        check(
            upgraded["star"] == 2,
            "Criação de unidade 2 estrelas",
            errors,
        )

        check(
            upgraded["uuid"] != unit_a["uuid"],
            "Upgrade recebe novo UUID",
            errors,
        )

    except Exception as exc:
        errors.append(f"Erro nos testes de upgrade: {exc}")
        print(f"[ERRO] Upgrade: {exc}")

    # ---------------------------------------------------------
    # 8. Resultado
    # ---------------------------------------------------------

    print("\n" + "=" * 65)

    if errors:
        print(f"RESULTADO: FALHOU — {len(errors)} problema(s)")
        for error in errors:
            print(f"  - {error}")
        return 1

    print("RESULTADO: TODOS OS TESTES PASSARAM")
    print(f"Total de unidades: {len(champions)}")
    print(f"Unidades com traits: {units_with_traits}")
    print("=" * 65)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())