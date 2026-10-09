
from types import SimpleNamespace

import pytest

from config.GameConfig import GameConfig
from economy.EconomyManager import EconomyManager
from lobby.TFTLobby import TFTLobby, CombatResult, combat_engine


def make_player(player_id):
    """Cria um jogador de teste com a economia real."""
    economy = EconomyManager()

    env = SimpleNamespace(
        hp=GameConfig.STARTING_HP,
        economy_manager=economy,
        last_combat_result=None,
        last_combat_won=False,
        done=False,
    )

    env._rebuild_player_state = lambda: None

    def apply_combat_result(result, won):
        env.last_combat_result = result
        env.last_combat_won = bool(won)

        if won:
            economy.register_pvp_win()
        else:
            economy.register_loss()

    def apply_damage(damage):
        if env.done:
            return

        env.hp = max(0, env.hp - max(0, int(damage)))

        if env.hp == 0:
            env.done = True

    env.apply_combat_result = apply_combat_result
    env.apply_damage = apply_damage

    return SimpleNamespace(
        player_id=player_id,
        env=env,
        wins=0,
        losses=0,
        alive=True,
        eliminated=False,
        last_combat_result=None,
        last_damage_taken=0,
    )

def make_lobby(monkeypatch, winner, survivors_a=2, survivors_b=0):
    """Simula o motor C++, mantendo a economia real."""
    lobby = TFTLobby.__new__(TFTLobby)
    lobby.stage = 1

    player_a = make_player(1)
    player_b = make_player(2)

    cpp_result = SimpleNamespace(
        success=True,
        completed=True,
        winner=winner,
        player_a_survivors=survivors_a,
        player_b_survivors=survivors_b,
    )

    monkeypatch.setattr(
        lobby,
        "_build_cpp_combat_input",
        lambda a, b: object(),
    )
    monkeypatch.setattr(
        combat_engine,
        "simulate",
        lambda _: cpp_result,
    )

    return lobby, player_a, player_b


def test_vitoria_concede_ouro_e_atualiza_sequencia(monkeypatch):
    """Vitória deve conceder ouro e registrar win streak."""
    lobby, player_a, player_b = make_lobby(
        monkeypatch,
        combat_engine.CombatWinner.PLAYER_A,
        survivors_a=3,
        survivors_b=0,
    )

    economy = player_a.env.economy_manager
    gold_before = economy.gold

    lobby.resolve_combat(player_a, player_b)

    assert economy.gold == gold_before + GameConfig.WIN_GOLD
    assert economy.win_streak == 1
    assert economy.loss_streak == 0


def test_derrota_atualiza_sequencia_sem_ouro_de_vitoria(monkeypatch):
    """Derrota não deve conceder ouro de vitória."""
    lobby, player_a, player_b = make_lobby(
        monkeypatch,
        combat_engine.CombatWinner.PLAYER_B,
        survivors_a=0,
        survivors_b=2,
    )

    economy_a = player_a.env.economy_manager
    gold_before = economy_a.gold

    lobby.resolve_combat(player_a, player_b)

    assert economy_a.gold == gold_before
    assert economy_a.loss_streak == 1
    assert economy_a.win_streak == 0


def test_relatorio_economico_contabiliza_ouro_de_vitoria(monkeypatch):
    """
    Verifica se o relatório econômico contabiliza a recompensa.
    Este teste deve revelar a divergência atual.
    """
    lobby, player_a, player_b = make_lobby(
        monkeypatch,
        combat_engine.CombatWinner.PLAYER_A,
        survivors_a=3,
        survivors_b=0,
    )

    economy = player_a.env.economy_manager

    lobby.resolve_combat(player_a, player_b)

    result = economy.resolve_round(1)

    assert result["win_gold"] == GameConfig.WIN_GOLD
    assert result["total_gold"] == (
        result["base_gold"]
        + result["interest_gold"]
        + result["streak_gold"]
        + GameConfig.WIN_GOLD
    )


def test_empate_nao_altera_economia(monkeypatch):
    """Empate não deve conceder ouro nem alterar streaks."""
    lobby, player_a, player_b = make_lobby(
        monkeypatch,
        combat_engine.CombatWinner.DRAW,
        survivors_a=1,
        survivors_b=1,
    )

    economy_a = player_a.env.economy_manager
    economy_b = player_b.env.economy_manager

    gold_a = economy_a.gold
    gold_b = economy_b.gold

    lobby.resolve_combat(player_a, player_b)

    assert economy_a.gold == gold_a
    assert economy_b.gold == gold_b

    assert economy_a.win_streak == 0
    assert economy_a.loss_streak == 0
    assert economy_b.win_streak == 0
    assert economy_b.loss_streak == 0

def test_vencedor_e_perdedor_atualizam_economia_corretamente(
    monkeypatch,
):
    lobby, player_a, player_b = make_lobby(
        monkeypatch,
        combat_engine.CombatWinner.PLAYER_A,
        survivors_a=3,
        survivors_b=0,
    )

    economy_a = player_a.env.economy_manager
    economy_b = player_b.env.economy_manager

    gold_a_before = economy_a.gold
    gold_b_before = economy_b.gold

    lobby.resolve_combat(player_a, player_b)

    # O vencedor recebe o bônus de vitória.
    assert economy_a.gold == gold_a_before + GameConfig.WIN_GOLD
    assert economy_a.win_streak == 1
    assert economy_a.loss_streak == 0

    # O perdedor não recebe bônus de vitória, mas sua sequência
    # de derrotas é atualizada para o cálculo da renda da rodada.
    assert economy_b.gold == gold_b_before
    assert economy_b.win_streak == 0
    assert economy_b.loss_streak == 1

def test_ouro_de_vitoria_nao_deve_acumular_entre_relatorios(monkeypatch):
    """
    Verifica se o relatório de vitória de uma rodada não é
    contado novamente na rodada seguinte.
    """
    economy = EconomyManager()

    economy.register_pvp_win()
    first = economy.resolve_round(1)

    second = economy.resolve_round(2)

    assert first["win_gold"] == GameConfig.WIN_GOLD
    assert second["win_gold"] == 0