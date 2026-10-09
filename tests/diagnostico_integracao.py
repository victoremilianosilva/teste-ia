from pathlib import Path
import sys

# Localiza a raiz do projeto e adiciona ao caminho de importação.
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from config.GameConfig import GameConfig
from lobby.TFTLobby import TFTLobby


def main():
    print("=" * 65)
    print("DIAGNÓSTICO DE INTEGRAÇÃO — CATÁLOGO E COMBATE")
    print("=" * 65)

    project_root = Path(__file__).resolve().parent.parent
    generated_path = (project_root / "units_gerado.json").resolve()

    print("\n[1] Caminhos")
    print("Catálogo gerado:", generated_path)
    print("GameConfig.UNITS_PATH:", GameConfig.UNITS_PATH)

    print("\n[2] Inicializando lobby...")
    lobby = TFTLobby()

    manager = lobby.unit_manager

    actual_path = manager.units_path.resolve()

    print("Catálogo carregado pelo lobby:", actual_path)
    print("Quantidade carregada:", len(manager.champions))

    if actual_path == generated_path:
        print("[OK] O lobby utiliza units_gerado.json.")
    else:
        print("[ATENÇÃO] O lobby utiliza outro caminho.")
        print("Precisamos corrigir a configuração antes de avançar.")

    print("\n[3] Conferindo os dados que serão usados no combate")

    champions = manager.champions

    if not champions:
        raise RuntimeError("O catálogo do lobby está vazio.")

    for champion in champions[:5]:
        profile = champion.get("combat_profile") or {}
        stats = champion.get("stats") or {}

        print(f"\nUnidade: {champion.get('name')}")
        print("  ID original:", manager.get_data_id(champion))
        print("  Role:", champion.get("role"))
        print("  Role name:", champion.get("role_name"))
        print("  Stats:", stats)

        print("  Perfil de combate:")
        for key in (
            "max_hp",
            "attack_damage",
            "attack_speed",
            "attack_range",
            "armor",
            "magic_resist",
        ):
            print(f"    {key}: {profile.get(key, '<AUSENTE>')}")

        missing = [
            key
            for key in (
                "max_hp",
                "attack_damage",
                "attack_speed",
                "attack_range",
                "armor",
                "magic_resist",
            )
            if profile.get(key) is None
        ]

        if missing:
            print("[ATENÇÃO] Campos ausentes no perfil:", missing)

    print("\n[4] Testando a criação de uma instância")

    champion = champions[0]
    unit = manager.create_unit(champion)

    print("Nome:", unit.get("name"))
    print("ID interno:", unit.get("id"))
    print("UUID:", unit.get("uuid"))
    print("Role:", unit.get("role"))
    print("Stats:", unit.get("stats"))
    print("Combat profile:", unit.get("combat_profile"))

    print("\n" + "=" * 65)
    print("DIAGNÓSTICO CONCLUÍDO")
    print("=" * 65)


if __name__ == "__main__":
    main()