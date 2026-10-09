
# tests/test_unit_pool_regression.py

import pytest

from units.UnitPool import UnitPool


class FakeUnitManager:
    """Catálogo mínimo para testar o UnitPool isoladamente."""

    def __init__(self):
        self.champions = [
            {"id": "champion_a", "name": "Campeão A", "cost": 1},
            {"id": "champion_b", "name": "Campeão B", "cost": 2},
            {"id": "champion_c", "name": "Campeão C", "cost": 3},
        ]
        self.ids = {
            id(champion): index
            for index, champion in enumerate(self.champions)
        }

    def get_all_champions(self):
        return self.champions

    def get_unit_id(self, champion):
        return self.ids.get(id(champion))


@pytest.fixture
def pool():
    manager = FakeUnitManager()

    return UnitPool(
        unit_manager=manager,
        copies_by_cost={
            1: 30,
            2: 25,
            3: 18,
        },
    )


# ---------------------------------------------------------
# 1. ESTADO INICIAL
# ---------------------------------------------------------

def test_pool_inicia_com_quantidades_corretas(pool):
    assert pool.get_initial_count(0) == 30
    assert pool.get_initial_count(1) == 25
    assert pool.get_initial_count(2) == 18

    assert pool.get_available(0) == 30
    assert pool.get_available(1) == 25
    assert pool.get_available(2) == 18

    assert pool.validate()


def test_total_inicial_e_total_disponivel_estao_corretos(pool):
    assert pool.get_total_initial() == 73
    assert pool.get_total_available() == 73
    assert pool.get_total_taken() == 0


# ---------------------------------------------------------
# 2. RETIRADA DE CÓPIAS
# ---------------------------------------------------------

def test_draw_reduz_estoque_em_exatamente_uma_copia(
    pool,
    monkeypatch,
):
    monkeypatch.setattr(
        "units.UnitPool.random.choice",
        lambda candidates: candidates[0],
    )

    initial = pool.get_available(0)

    unit = pool.draw(1)

    assert unit is not None
    assert pool.get_available(0) == initial - 1
    assert pool.get_total_taken() == 1
    assert pool.validate()


def test_draw_retorna_copia_independente_do_catalogo(
    pool,
    monkeypatch,
):
    monkeypatch.setattr(
        "units.UnitPool.random.choice",
        lambda candidates: candidates[0],
    )

    catalog_unit = pool.unit_manager.champions[0]
    unit = pool.draw(1)

    assert unit is not None
    assert unit is not catalog_unit

    unit["name"] = "Nome alterado"
    unit["novo_campo"] = True

    assert catalog_unit["name"] == "Campeão A"
    assert "novo_campo" not in catalog_unit


def test_draw_rejeita_custo_sem_unidades_disponiveis(
    pool,
    monkeypatch,
):
    monkeypatch.setattr(
        "units.UnitPool.random.choice",
        lambda candidates: candidates[0],
    )

    for _ in range(30):
        assert pool.draw(1) is not None

    assert pool.draw(1) is None
    assert pool.get_available(0) == 0
    assert pool.validate()


def test_draw_rejeita_custo_invalido(pool):
    assert pool.draw("inválido") is None
    assert pool.draw(None) is None
    assert pool.draw(99) is None


# ---------------------------------------------------------
# 3. DEVOLUÇÃO DE CÓPIAS
# ---------------------------------------------------------

@pytest.mark.parametrize(
    ("star", "expected_copies"),
    [
        (1, 1),
        (2, 3),
        (3, 9),
    ],
)
def test_return_unit_devolve_copias_conforme_estrelas(
    pool,
    star,
    expected_copies,
):
    pool.available[0] -= expected_copies

    unit = {
        "id": 0,
        "star": star,
    }

    assert pool.return_unit(unit) is True
    assert pool.get_available(0) == 30
    assert pool.validate()


def test_return_copies_nao_ultrapassa_estoque_inicial(pool):
    pool.available[0] = 28

    assert pool.return_copies(0, 10) is True
    assert pool.get_available(0) == 30
    assert pool.validate()


def test_return_copies_rejeita_quantidade_invalida(pool):
    assert pool.return_copies(0, 0) is False
    assert pool.return_copies(0, -1) is False
    assert pool.return_copies(999, 1) is False
    assert pool.return_copies(0, "inválido") is False

    assert pool.get_available(0) == 30


@pytest.mark.parametrize(
    "unit",
    [
        None,
        "não é uma unidade",
        {},
        {"star": 1},
        {"id": 999, "star": 1},
        {"id": 0, "star": 0},
    ],
)
def test_return_unit_rejeita_unidades_invalidas(pool, unit):
    assert pool.return_unit(unit) is False
    assert pool.validate()


def test_nao_devolve_copias_quando_pool_ja_esta_cheio(pool):
    assert pool.return_copies(0, 1) is False
    assert pool.get_available(0) == 30


# ---------------------------------------------------------
# 4. RESET
# ---------------------------------------------------------

def test_reset_restaura_estoque_inicial(pool):
    pool.available[0] = 10
    pool.available[1] = 5
    pool.available[2] = 2

    assert pool.validate()

    pool.reset()

    assert pool.get_available(0) == 30
    assert pool.get_available(1) == 25
    assert pool.get_available(2) == 18

    assert pool.get_initial_count(0) == 30
    assert pool.get_initial_count(1) == 25
    assert pool.get_initial_count(2) == 18

    assert pool.get_total_taken() == 0
    assert pool.validate()


def test_reset_reconstroi_estado_apos_remocao_de_entrada(pool):
    del pool.available[0]
    del pool.initial_counts[1]

    pool.reset()

    assert pool.get_available(0) == 30
    assert pool.get_available(1) == 25
    assert pool.get_available(2) == 18
    assert pool.validate()


# ---------------------------------------------------------
# 5. VALIDAÇÃO E ISOLAMENTO DO ESTADO
# ---------------------------------------------------------

def test_validate_detecta_quantidade_negativa(pool):
    pool.available[0] = -1

    assert pool.validate() is False


def test_validate_detecta_quantidade_acima_do_inicial(pool):
    pool.available[0] = 31

    assert pool.validate() is False


def test_get_state_retorna_copia_independente(pool):
    state = pool.get_state()
    state[0] = 0
    state[999] = 100

    assert pool.get_available(0) == 30
    assert 999 not in pool.available


def test_get_initial_state_retorna_copia_independente(pool):
    state = pool.get_initial_state()
    state[0] = 0

    assert pool.get_initial_count(0) == 30
    assert pool.validate()
