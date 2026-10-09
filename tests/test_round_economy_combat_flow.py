from types import SimpleNamespace
from unittest.mock import Mock

from config.GameConfig import GameConfig
from economy.EconomyManager import EconomyManager
from lobby.TFTLobby import TFTLobby, CombatResult


def make_player(player_id):
    economy = EconomyManager()

    env = SimpleNamespace(
        economy_manager=economy,
        resolve_player_round=lambda: economy.resolve_round(1),
    )

    return SimpleNamespace(
        player_id=player_id,
        env=env,
        alive=True,
        eliminated=False,
        wins=0,
        losses=0,
        placement=None,
        opponent_id=None,
        last_combat_result=None,
        last_damage_taken=0,
    )


def test_real_round_flow_registers_win_gold_once(monkeypatch):
    # Arrange: cria um lobby mínimo, mas usa _resolve_round real.
    lobby = TFTLobby.__new__(TFTLobby)

    player_a = make_player(0)
    player_b = make_player(1)

    lobby.players = [player_a, player_b]
    lobby.matchups = [(player_a, player_b)]
    lobby.stage = 1
    lobby.round = 1
    lobby.finished = False
    lobby.round_actions = {0: 0, 1: 0}
    lobby.round_finished = {0: False, 1: False}

    # Isola os métodos periféricos para testar o fluxo econômico.
    monkeypatch.setattr(lobby, "generate_matchups", lambda: None)
    monkeypatch.setattr(lobby, "eliminate_players", lambda: None)
    monkeypatch.setattr(lobby, "update_ranking", lambda: None)
    monkeypatch.setattr(lobby, "advance_round", lambda: None)

    def fake_resolve_combat(winner, loser):
        winner.env.economy_manager.register_pvp_win()
        loser.env.economy_manager.register_loss()

        return CombatResult(
            winner_id=winner.player_id,
            loser_id=loser.player_id,
            winner_units=2,
            loser_units=0,
            damage=0,
        )

    monkeypatch.setattr(lobby, "resolve_combat", fake_resolve_combat)

    # Act: executa o método real do lobby.
    result = lobby._resolve_round()

    winner_report = result["economy"][player_a.player_id]
    loser_report = result["economy"][player_b.player_id]

    winner_economy = player_a.env.economy_manager
    loser_economy = player_b.env.economy_manager

    # Assert: o bônus deve aparecer no relatório da rodada atual.
    assert winner_report["win_gold"] == GameConfig.WIN_GOLD

    assert winner_report["total_gold"] == (
        winner_report["base_gold"]
        + winner_report["interest_gold"]
        + winner_report["streak_gold"]
        + GameConfig.WIN_GOLD
    )

    assert winner_report["new_gold"] == winner_economy.gold

    # O perdedor não deve receber bônus de vitória.
    assert loser_report["win_gold"] == 0
    assert loser_report["new_gold"] == loser_economy.gold

    # O bônus não pode ficar pendente para a próxima rodada.
    next_report = winner_economy.resolve_round(2)

    assert next_report["win_gold"] == 0

    # O combate deve ter sido incluído no resultado do lobby.
    assert len(result["combat"]) == 1