from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent.parent
ENGINE_DIR = ROOT / "cpp" / "build" / "bin" / "Release"
sys.path.insert(0, str(ENGINE_DIR))

import combat_engine as ce


def criar_unidade(
    nome: str,
    unit_id: int,
    team,
    x: int,
    y: int,
    hp: float,
    dano: float,
    velocidade: float,
    alcance: float,
):
    unit = ce.CombatUnit()

    unit.id = unit_id
    unit.name = nome
    unit.api_name = nome
    unit.team = team

    unit.position.x = x
    unit.position.y = y

    unit.max_hp = hp
    unit.hp = hp
    unit.attack_damage = dano
    unit.attack_speed = velocidade
    unit.attack_range = alcance

    unit.armor = 30.0
    unit.magic_resist = 30.0
    unit.max_mana = 100.0
    unit.mana = 0.0
    unit.star = 1
    unit.alive = True
    unit.can_attack = True
    unit.can_cast = True
    unit.can_move = True

    unit.role = ce.UnitRole.FIGHTER

    return unit


def main():
    print("=" * 65)
    print("TESTE DE INTEGRAÇÃO PYTHON -> C++")
    print("=" * 65)

    # Configuração da simulação.
    combat_input = ce.CombatInput()
    config = combat_input.config

    config.board_cols = 7
    config.board_rows = 4
    config.max_duration = 30.0
    config.max_events = 100000
    config.deterministic = True
    config.seed = 42

    # Habilita registros para facilitar a análise.
    config.record_events = True
    config.record_damage = True
    config.record_positions = True

    combat_input.context = ce.CombatContext.PVP
    combat_input.seed = 42

    # Equipe A.
    team_a = combat_input.player_a
    team_a.player_id = 1
    team_a.team = ce.UnitTeam.PLAYER_A
    team_a.player_hp = 100.0

    team_a.units = [
        criar_unidade(
            nome="Lutador_A",
            unit_id=1,
            team=ce.UnitTeam.PLAYER_A,
            x=1,
            y=1,
            hp=500.0,
            dano=50.0,
            velocidade=1.0,
            alcance=1.0,
        )
    ]

    # Equipe B.
    team_b = combat_input.player_b
    team_b.player_id = 2
    team_b.team = ce.UnitTeam.PLAYER_B
    team_b.player_hp = 100.0

    team_b.units = [
        criar_unidade(
            nome="Lutador_B",
            unit_id=2,
            team=ce.UnitTeam.PLAYER_B,
            x=5,
            y=1,
            hp=500.0,
            dano=40.0,
            velocidade=1.0,
            alcance=1.0,
        )
    ]

    print("\n[1] Entrada preparada")
    print(f"Unidades da equipe A: {len(team_a.units)}")
    print(f"Unidades da equipe B: {len(team_b.units)}")
    print(f"Duração máxima: {config.max_duration}s")

    print("\n[2] Executando simulate()...")

    try:
        result = ce.simulate(combat_input)
    except Exception as exc:
        print(f"[FALHA] Exceção durante a simulação: {exc}")
        raise

    print("\n[3] Resultado")
    print(f"Sucesso: {result.success}")
    print(f"Combate concluído: {result.completed}")
    print(f"Erro: {result.error_code} - {result.error_message}")
    print(f"Vencedor: {result.winner}")
    print(f"Duração: {result.duration:.2f}s")
    print(f"Timeout: {result.timeout}")
    print(f"Eventos processados: {result.events_processed}")

    print("\n[4] Estatísticas")
    print(f"Dano causado por A: {result.player_a_damage_dealt}")
    print(f"Dano causado por B: {result.player_b_damage_dealt}")
    print(f"Mortes de A: {result.player_a_deaths}")
    print(f"Mortes de B: {result.player_b_deaths}")
    print(f"Sobreviventes de A: {result.player_a_survivors}")
    print(f"Sobreviventes de B: {result.player_b_survivors}")

    print("\n[5] Resultados individuais")
    for unit_result in result.units:
        print(
            f"ID={unit_result.unit_id} | "
            f"Equipe={unit_result.team} | "
            f"HP final={unit_result.final_hp:.2f} | "
            f"Dano={unit_result.damage_dealt:.2f} | "
            f"Ataques={unit_result.attacks} | "
            f"Sobreviveu={unit_result.survived}"
        )

    print("\n[6] Eventos registrados")
    print(f"Eventos gerais: {len(result.events)}")
    print(f"Eventos de dano: {len(result.damage_events)}")
    print(f"Eventos de posição: {len(result.position_events)}")

    if not result.success:
        raise RuntimeError(
            f"O motor retornou falha: "
            f"{result.error_code} - {result.error_message}"
        )

    assert result.duration >= 0, "Duração negativa."
    assert result.events_processed >= 0, "Contagem de eventos inválida."

    print("\n[OK] A chamada Python -> C++ retornou um resultado válido.")
    print("Confira as estatísticas acima para validar o comportamento.")


if __name__ == "__main__":
    main()