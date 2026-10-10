
import pytest

from shop.ShopManager import ShopManager


class FakePool:
    def __init__(self):
        self.available = {
            "A": 3,
            "B": 3,
            "C": 3,
        }

    def draw(self, cost):
        # O custo é ignorado neste fake.
        for name in self.available:
            if self.available[name] > 0:
                self.available[name] -= 1
                return {"id": name, "cost": cost, "star": 1}
        return None

    def return_unit(self, unit):
        if unit is not None:
            self.available[unit["id"]] += 1
            return True
        return False


def test_reroll_exists_and_replaces_shop():
    pool = FakePool()
    shop = ShopManager(
        unit_pool=pool,
        shop_size=2,
        shop_odds={1: [1.0]},
    )

    first = shop.roll(1)
    assert len(first) == 2

    second = shop.reroll(1)
    assert len(second) == 2
    assert all(unit is not None for unit in second)


def test_locked_shop_preserves_offers_on_normal_roll():
    pool = FakePool()
    shop = ShopManager(
        unit_pool=pool,
        shop_size=2,
        shop_odds={1: [1.0]},
    )

    before = shop.roll(1)
    shop.set_locked(True)

    after = shop.roll(1)

    assert after == before


def test_manual_reroll_works_even_when_locked():
    pool = FakePool()
    shop = ShopManager(
        unit_pool=pool,
        shop_size=2,
        shop_odds={1: [1.0]},
    )

    shop.roll(1)
    shop.set_locked(True)

    # O reroll manual usa force=True.
    result = shop.reroll(1)

    assert len(result) == 2
    assert shop.is_locked() is True


def test_buying_shop_unit_does_not_return_it_to_pool():
    pool = FakePool()
    shop = ShopManager(
        unit_pool=pool,
        shop_size=1,
        shop_odds={1: [1.0]},
    )

    shop.roll(1)
    unit = shop.get_unit(0)
    assert unit is not None

    stock_before_purchase = pool.available[unit["id"]]
    purchased = shop.take_unit(0)

    assert purchased["id"] == unit["id"]
    assert pool.available[unit["id"]] == stock_before_purchase
    assert shop.get_unit(0) is None


def test_duas_lojas_nao_criam_copias_acima_do_estoque():
    pool = FakePool()
    pool.available = {"A": 1}

    shop_a = ShopManager(
        unit_pool=pool,
        shop_size=1,
        shop_odds={1: [1.0]},
    )
    shop_b = ShopManager(
        unit_pool=pool,
        shop_size=1,
        shop_odds={1: [1.0]},
    )

    primeira = shop_a.roll(1)
    segunda = shop_b.roll(1)

    # A única cópia deve ficar reservada na primeira loja.
    assert primeira[0]["id"] == "A"
    assert segunda[0] is None
    assert pool.available["A"] == 0


def test_compra_e_venda_transferem_a_copia_sem_duplicar():
    pool = FakePool()
    shop = ShopManager(
        unit_pool=pool,
        shop_size=1,
        shop_odds={1: [1.0]},
    )

    shop.roll(1)
    unit = shop.get_unit(0)
    assert unit is not None

    champion_id = unit["id"]
    stock_after_roll = pool.available[champion_id]

    # 🛒 Comprar transfere a cópia para o jogador.
    purchased = shop.take_unit(0)

    assert purchased["id"] == champion_id
    assert pool.available[champion_id] == stock_after_roll
    assert shop.get_unit(0) is None

    # 💰 Vender devolve a cópia uma única vez.
    assert pool.return_unit(purchased) is True
    assert pool.available[champion_id] == stock_after_roll + 1

    # A segunda devolução não deve ser feita pelo fluxo normal.
    # O FakePool é propositalmente simples e não impede duplicações.
