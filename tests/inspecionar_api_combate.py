from pathlib import Path
import sys
import importlib

ROOT = Path(__file__).resolve().parent.parent
ENGINE_DIR = ROOT / "cpp" / "build" / "bin" / "Release"
sys.path.insert(0, str(ENGINE_DIR))

import combat_engine as ce


def inspect_class(name):
    cls = getattr(ce, name)

    print(f"\n{'=' * 60}")
    print(f"CLASSE: {name}")
    print("=" * 60)

    print("\nConstrutor:")
    print(getattr(cls, "__init__", None).__doc__)

    print("\nDocumentação:")
    print(cls.__doc__)

    try:
        obj = cls()
        print("\n[OK] Instância criada sem argumentos")
        print("Atributos disponíveis:")

        for attr in dir(obj):
            if attr.startswith("_"):
                continue

            try:
                value = getattr(obj, attr)
                if not callable(value):
                    print(f"  {attr} = {value!r}")
                else:
                    print(f"  {attr} (método)")
            except Exception as exc:
                print(f"  {attr} [não foi possível ler: {exc}]")

    except Exception as exc:
        print(f"\n[INFO] Não aceita construtor vazio: {exc}")


print("INSPEÇÃO DA API DO MOTOR C++")

for class_name in [
    "CombatInput",
    "CombatUnit",
    "CombatTeam",
    "CombatPosition",
    "CombatResult",
    "CombatUnitResult",
    "CombatConfig",
    "CombatAbility",
    "CombatTrait",
    "CombatItem",
    "CombatModifier",
]:
    inspect_class(class_name)

print("\n" + "=" * 60)
print("FIM DA INSPEÇÃO")
print("=" * 60)