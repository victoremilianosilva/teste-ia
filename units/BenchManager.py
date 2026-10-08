# units/BenchManager.py

from copy import deepcopy


class BenchManager:
    """
    🪑 Gerencia o banco (bench) de um jogador.

    Responsabilidades:
        - armazenar unidades do bench
        - adicionar unidades
        - remover unidades
        - mover unidades entre slots
        - localizar unidades
        - verificar capacidade
        - trocar unidades de posição

    NÃO é responsabilidade deste manager:
        - decidir se deve comprar
        - decidir se deve vender
        - reward
        - estratégia
        - anti-loop
        - UnitPool
        - gold
        - combate
        - board
    """

    def __init__(self, max_bench=9):
        self.max_bench = max_bench
        self.bench = self._create_empty_bench()

    # =============================================================
    # 🧱 ESTRUTURA
    # =============================================================

    def _create_empty_bench(self):
        """
        Cria um bench vazio.

        Mantemos uma lista flat porque o projeto atual trabalha
        com slots de 0 até 8.
        """

        return [None] * self.max_bench

    def reset(self):
        """
        Limpa completamente o bench.
        """

        self.bench = self._create_empty_bench()

    # =============================================================
    # 📍 POSIÇÕES
    # =============================================================

    def is_valid_position(self, position):
        """
        Verifica se o slot existe.
        """

        return (
            isinstance(position, int)
            and 0 <= position < self.max_bench
        )

    # =============================================================
    # 🔎 CONSULTA
    # =============================================================

    def get_unit(self, position):
        """
        Retorna a unidade de determinado slot.

        Retorna None se estiver vazio ou inválido.
        """

        if not self.is_valid_position(position):
            return None

        return self.bench[position]

    def is_empty(self, position):
        """
        Verifica se determinado slot está vazio.
        """

        if not self.is_valid_position(position):
            return False

        return self.bench[position] is None

    def get_units(self):
        """
        Retorna todas as unidades existentes no bench.
        """

        return [
            unit
            for unit in self.bench
            if unit is not None
        ]

    def get_occupied_positions(self):
        """
        Retorna os slots ocupados.
        """

        return [
            index
            for index, unit in enumerate(self.bench)
            if unit is not None
        ]

    def get_empty_positions(self):
        """
        Retorna os slots livres.
        """

        return [
            index
            for index, unit in enumerate(self.bench)
            if unit is None
        ]

    def get_free_slot(self):
        """
        Retorna o primeiro slot livre.

        Retorna None caso o bench esteja cheio.
        """

        for index, unit in enumerate(self.bench):
            if unit is None:
                return index

        return None

    # =============================================================
    # 📊 CAPACIDADE
    # =============================================================

    def get_unit_count(self):
        """
        Quantidade de unidades no bench.
        """

        return sum(
            unit is not None
            for unit in self.bench
        )

    def get_free_slots(self):
        """
        Quantidade de slots livres.
        """

        return self.max_bench - self.get_unit_count()

    def is_full(self):
        """
        Verifica se o bench está cheio.
        """

        return self.get_free_slots() == 0

    # =============================================================
    # ➕ ADICIONAR
    # =============================================================

    def add_unit(self, unit, position=None):
        """
        Adiciona uma unidade ao bench.

        Se position for None:
            utiliza o primeiro slot livre.

        Retorna:
            índice utilizado em caso de sucesso
            None em caso de falha
        """

        if unit is None:
            return None

        # ---------------------------------------------------------
        # Slot específico
        # ---------------------------------------------------------

        if position is not None:

            if not self.is_valid_position(position):
                return None

            if not self.is_empty(position):
                return None

            self.bench[position] = unit

            return position

        # ---------------------------------------------------------
        # Primeiro slot disponível
        # ---------------------------------------------------------

        free_slot = self.get_free_slot()

        if free_slot is None:
            return None

        self.bench[free_slot] = unit

        return free_slot

    # =============================================================
    # ➖ REMOVER
    # =============================================================

    def remove_unit(self, position):
        """
        Remove uma unidade do bench e retorna a unidade.

        Retorna None caso o slot esteja vazio.
        """

        if not self.is_valid_position(position):
            return None

        unit = self.bench[position]

        if unit is None:
            return None

        self.bench[position] = None

        return unit

    # =============================================================
    # 🔄 MOVER DENTRO DO BENCH
    # =============================================================

    def move_unit(self, source, target):
        """
        Move uma unidade para outro slot vazio.

        Não permite sobrescrever outra unidade.
        """

        if not self.is_valid_position(source):
            return False

        if not self.is_valid_position(target):
            return False

        if source == target:
            return False

        unit = self.bench[source]

        if unit is None:
            return False

        if self.bench[target] is not None:
            return False

        self.bench[target] = unit
        self.bench[source] = None

        return True

    # =============================================================
    # 🔁 TROCAR
    # =============================================================

    def swap_units(self, position_a, position_b):
        """
        Troca duas posições do bench.

        Uma ou ambas podem estar vazias.
        """

        if not self.is_valid_position(position_a):
            return False

        if not self.is_valid_position(position_b):
            return False

        if position_a == position_b:
            return False

        self.bench[position_a], self.bench[position_b] = (
            self.bench[position_b],
            self.bench[position_a],
        )

        return True

    # =============================================================
    # 🔎 LOCALIZAR UNIDADE
    # =============================================================

    def find_unit_position(self, unit):
        """
        Procura uma unidade pelo objeto ou UUID.
        """

        if unit is None:
            return None

        # Primeiro tenta identidade.
        for position, bench_unit in enumerate(self.bench):
            if bench_unit is unit:
                return position

        # Depois tenta UUID.
        unit_uuid = unit.get("uuid")

        if unit_uuid is None:
            return None

        for position, bench_unit in enumerate(self.bench):

            if (
                bench_unit is not None
                and bench_unit.get("uuid") == unit_uuid
            ):
                return position

        return None

    def find_units_by_id(self, unit_id):
        """
        Retorna todas as unidades de determinado campeão.
        """

        return [
            unit
            for unit in self.bench
            if (
                unit is not None
                and unit.get("id") == unit_id
            )
        ]

    # =============================================================
    # 🔄 TRANSFERÊNCIA
    # =============================================================

    def remove_unit_instance(self, unit):
        """
        Remove uma unidade específica do bench.

        Útil quando outro manager já possui a referência da unidade.
        """

        position = self.find_unit_position(unit)

        if position is None:
            return None

        return self.remove_unit(position)

    def add_unit_instance(self, unit, position=None):
        """
        Alias explícito para adicionar uma unidade existente.

        Não cria uma nova cópia.
        """

        return self.add_unit(
            unit,
            position=position
        )

    # =============================================================
    # 📋 SNAPSHOT
    # =============================================================

    def get_snapshot(self):
        """
        Retorna uma cópia do estado atual do bench.

        Útil para:
            - simulação
            - debug
            - comparação de estados
        """

        return deepcopy(self.bench)

    # =============================================================
    # 🔐 ASSINATURAS
    # =============================================================

    def get_position_signature(self):
        """
        Assinatura incluindo UUID.

        Útil para detectar movimentações repetidas da mesma cópia.
        """

        signature = []

        for unit in self.bench:

            if unit is None:
                signature.append(None)
                continue

            signature.append(
                (
                    unit.get("id"),
                    unit.get("star", 1),
                    unit.get("uuid"),
                )
            )

        return tuple(signature)

    def get_bench_id_signature(self):
        """
        Assinatura sem UUID.

        Representa apenas:
            campeão + estrela
        """

        return tuple(
            (
                unit.get("id"),
                unit.get("star", 1),
            )
            if unit is not None
            else None
            for unit in self.bench
        )

    # =============================================================
    # 🧹 VALIDAÇÃO
    # =============================================================

    def validate(self):
        """
        Verifica se a estrutura interna do bench está consistente.
        """

        if not isinstance(self.bench, list):
            return False

        if len(self.bench) != self.max_bench:
            return False

        return True

    # =============================================================
    # 🐛 DEBUG
    # =============================================================

    def debug_print(self):
        """
        Imprime o bench para debug.
        """

        print("\n--- BENCH ---")

        for index, unit in enumerate(self.bench):

            if unit is None:
                print(f"[{index}] Vazio")
                continue

            print(
                f"[{index}] "
                f"{unit.get('name', '?')} "
                f"{unit.get('star', 1)}★ "
                f"(id={unit.get('id')})"
            )

        print("-------------")