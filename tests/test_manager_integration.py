
import pytest
from unittest.mock import patch

from ai.ActionMaskManager import ActionType
from config.GameConfig import GameConfig
from lobby.TFTLobby import TFTLobby


def test_shop_economy_units_strategy_integration():
    # Arrange: inicializa o lobby e utiliza o ambiente real
    # de um dos jogadores.
    lobby = TFTLobby(seed=123)

    try:
        lobby.reset()

        env = lobby.players[0].env

        # 1. Confirma que os managers estão conectados
        # às instâncias utilizadas pelo ambiente.
        assert (
            env.action_mask_manager.economy_manager
            is env.economy_manager
        )
        assert (
            env.action_mask_manager.shop_manager
            is env.shop_manager
        )
        assert (
            env.action_mask_manager.unit_manager
            is env.unit_manager
        )

        # Dá ouro suficiente para comprar e fazer reroll.
        env.economy_manager.add_gold(30)

        # 2. Encontra uma oferta válida e acessível.
        shop = env.shop_manager.get_shop()

        affordable_slots = [
            slot
            for slot, champion in enumerate(shop)
            if champion is not None
            and int(champion.get("cost", 1))
            <= env.economy_manager.gold
        ]

        assert affordable_slots, (
            "A loja não possui nenhuma oferta comprável."
        )

        shop_slot = affordable_slots[0]
        champion = shop[shop_slot]
        cost = int(champion.get("cost", 1))

        gold_before_buy = env.economy_manager.gold
        owned_before_buy = len(env._get_all_units())

        # 3. Executa a compra pelo fluxo real do ambiente.
        _, _, done, buy_info = env.step({
            "type": int(ActionType.BUY),
            "shop_slot": shop_slot,
        })

        assert done is False
        assert buy_info["action_success"] is True
        assert buy_info["bought_unit"] is not None

        # A economia deve descontar exatamente o custo.
        assert env.economy_manager.gold == (
            gold_before_buy - cost
        )

        # A unidade comprada deve continuar representada
        # entre as unidades possuídas, mesmo se houve upgrade.
        bought_unit = buy_info["bought_unit"]

        owned_units = env._get_all_units()

        assert any(
            unit.get("id") == bought_unit.get("id")
            for unit in owned_units
        ), "A unidade comprada não foi encontrada no estado do jogador."

        # A compra não pode aumentar a quantidade de unidades
        # em mais de uma, pois pode ocorrer uma fusão automática.
        assert len(owned_units) <= owned_before_buy + 1

        # A composição e a estratégia devem estar atualizadas.
        assert env.composition_manager is not None
        assert env.strategy_manager is not None
        assert isinstance(
            env.strategy_manager.last_reason, str
        )

        # 4. Prepara o reroll e registra o saldo.
        env.economy_manager.add_gold(10)
        gold_before_reroll = env.economy_manager.gold

        # O spy confirma a chamada, mas deixa o reroll real executar.
        with patch.object(
            env.shop_manager,
            "reroll",
            wraps=env.shop_manager.reroll,
        ) as reroll_spy:

            _, _, done, reroll_info = env.step({
                "type": int(ActionType.REROLL),
            })

        assert done is False
        assert reroll_info["action_success"] is True

        reroll_spy.assert_called_once_with(
            env.economy_manager.level
        )

        # O reroll deve cobrar o custo configurado.
        assert env.economy_manager.gold == (
            gold_before_reroll - GameConfig.REROLL_COST
        )

        # A loja continua com a quantidade esperada de espaços.
        refreshed_shop = env.shop_manager.get_shop()

        assert len(refreshed_shop) == env.shop_size

        # A composição e a estratégia continuam operacionais
        # após a atualização da loja.
        assert env.composition_manager is not None
        assert env.strategy_manager is not None

    finally:
        close = getattr(lobby, "close", None)

        if callable(close):
            close()
