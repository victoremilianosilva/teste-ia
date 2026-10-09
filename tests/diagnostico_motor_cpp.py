from pathlib import Path
import sys
import importlib

PROJECT_ROOT = Path(__file__).resolve().parent.parent

print("=" * 65)
print("DIAGNÓSTICO DO MOTOR DE COMBATE C++")
print("=" * 65)

# Localiza a extensão compilada do motor.
possible_paths = [
    PROJECT_ROOT / "cpp" / "build" / "bin" / "Release",
    PROJECT_ROOT / "cpp" / "build" / "Release",
    PROJECT_ROOT / "build",
]

for path in possible_paths:
    if path.exists():
        sys.path.insert(0, str(path))
        print(f"[PATH] {path}")

# Procura a extensão caso esteja em outro diretório.
extensions = list(PROJECT_ROOT.rglob("combat_engine*.pyd"))

if extensions:
    for extension in extensions:
        print(f"[EXTENSÃO] {extension}")
        sys.path.insert(0, str(extension.parent))
else:
    print("[AVISO] Nenhuma extensão combat_engine*.pyd encontrada.")

print("\n[1] Importando o motor...")

try:
    engine = importlib.import_module("combat_engine")
    print(f"[OK] Módulo carregado: {engine.__file__}")

    print("\n[2] Classes e funções expostas:")
    for name in dir(engine):
        if not name.startswith("_"):
            obj = getattr(engine, name)
            print(f"\n--- {name} ---")
            print(repr(obj))

            doc = getattr(obj, "__doc__", None)
            if doc:
                print("Documentação:")
                print(doc)

except Exception as exc:
    print(f"[ERRO] {type(exc).__name__}: {exc}")
    print("\nVerifique se o motor foi compilado para a versão")
    print("do Python usada no ambiente virtual.")

print("\n" + "=" * 65)
print("DIAGNÓSTICO CONCLUÍDO")
print("=" * 65)