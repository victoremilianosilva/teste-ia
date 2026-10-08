# units/UnitManager.py

from copy import deepcopy
from pathlib import Path
import json
import uuid

from config.GameConfig import GameConfig
from combat.CombatProfileManager import CombatProfileManager, UnitRole

class UnitManager:
    """
    🧩 Gerencia os dados e a criação das unidades.

    Este manager pode ser compartilhado pelos 8 jogadores,
    pois não guarda estado específico de nenhum jogador.

    Responsabilidades:
        - carregar campeões
        - definir ID interno dos campeões
        - criar instâncias de unidades
        - localizar campeões
        - contar cópias
        - verificar upgrades
        - criar resultado de upgrade

    NÃO é responsabilidade:
        - board
        - bench
        - shop
        - UnitPool
        - gold
        - XP
        - combate
        - reward
        - estratégia
    """

    def __init__(
        self,
        units_path=None,
        combat_profile_mgr=None,
        champions=None,
    ):
        self.units_path = Path(
            units_path or GameConfig.UNITS_PATH
        )

        # Pode ser compartilhado entre os 8 jogadores.
        self.combat_profile_mgr = (
            combat_profile_mgr
            if combat_profile_mgr is not None
            else CombatProfileManager()
        )

        # ---------------------------------------------------------
        # 📦 Campeões
        # ---------------------------------------------------------

        if champions is not None:
            self.champions = champions
        else:
            self.champions = self._load_champions()

        if not self.champions:
            raise ValueError(
                "Nenhum campeão foi carregado."
            )

        # ---------------------------------------------------------
        # 🆔 Índices
        #
        # ID INTERNO:
        #     índice dentro de self.champions
        #
        # ID DO JSON:
        #     valor original de champion["id"]
        #
        # Não misturamos os dois.
        # ---------------------------------------------------------

        self._champion_by_index = {
            index: champion
            for index, champion in enumerate(self.champions)
        }

        self._index_by_data_id = {}

        for index, champion in enumerate(self.champions):

            # ---------------------------------------------------------
            # 🆔 Identificador original do dataset
            # ---------------------------------------------------------

            data_id = (
                champion.get("id")
                or champion.get("apiName")
                or champion.get("characterName")
            )

            if data_id is not None:
                self._index_by_data_id[data_id] = index

    # =============================================================
    # 📦 CARREGAMENTO
    # =============================================================

    def _load_champions(self):
        """
        Carrega os campeões do units.json.

        O arquivo pode ser:
            - uma lista
            - {"units": [...]}
            - {"champions": [...]}
            - {"data": [...]}
        """

        if not self.units_path.exists():
            raise FileNotFoundError(
                f"Arquivo de unidades não encontrado: "
                f"{self.units_path}"
            )

        with open(
            self.units_path,
            "r",
            encoding="utf-8",
        ) as file:
            data = json.load(file)

        if isinstance(data, list):

            champions = data

        elif isinstance(data, dict):

            champions = (
                data.get("units")
                or data.get("champions")
                or data.get("data")
                or []
            )

        else:
            raise ValueError(
                "Formato inválido para units.json."
            )

        if not champions:
            raise ValueError(
                "Nenhuma unidade encontrada em units.json."
            )

        processed = []

        for champion in champions:

            champion = deepcopy(champion)

            # -----------------------------------------------------
            # ⚔️ Processa perfil de combate uma única vez.
            # -----------------------------------------------------

            champion = self.combat_profile_mgr.process_unit(
                champion
            )

            processed.append(champion)

        return processed

    # =============================================================
    # 🆔 ID INTERNO
    # =============================================================
    def get_unit_id(self, champion):
        """
        Retorna o ID interno do campeão.

        O ID interno é o índice do campeão no catálogo.

        O dataset atual pode não possuir ``id``.
        Nesse caso utilizamos:

            1. id
            2. apiName
            3. characterName

        como identificador do campeão.
        """

        if champion is None:
            return None

        # ---------------------------------------------------------
        # 🧩 Se for exatamente o objeto do catálogo
        # ---------------------------------------------------------

        for index, stored_champion in self._champion_by_index.items():

            if champion is stored_champion:
                return index

        # ---------------------------------------------------------
        # 🆔 Procurar pelo identificador do dataset
        # ---------------------------------------------------------

        data_id = (
            champion.get("id")
            or champion.get("apiName")
            or champion.get("characterName")
            or champion.get("champion_id")
        )

        if data_id in self._index_by_data_id:
            return self._index_by_data_id[data_id]

        # ---------------------------------------------------------
        # 🔢 Caso já seja um ID interno
        # ---------------------------------------------------------

        if isinstance(data_id, int):

            if data_id in self._champion_by_index:
                return data_id

        return None


    # =============================================================
    # 🆔 ID ORIGINAL DO JSON
    # =============================================================
    def get_data_id(self, champion):
        """
        Retorna o identificador original do campeão no dataset.
        """

        if champion is None:
            return None

        return (
            champion.get("id")
            or champion.get("apiName")
            or champion.get("characterName")
            or champion.get("champion_id")
        )


    # =============================================================
    # 🔎 LOCALIZAR CAMPEÃO
    # =============================================================

    def get_champion(self, champion_id):
        """
        Localiza um campeão.

        Prioridade:

        1. ID interno
        2. ID original do JSON
        """

        # ---------------------------------------------------------
        # ID interno
        # ---------------------------------------------------------

        if isinstance(champion_id, int):

            champion = self._champion_by_index.get(
                champion_id
            )

            if champion is not None:
                return champion

        # ---------------------------------------------------------
        # ID original do JSON
        # ---------------------------------------------------------

        index = self._index_by_data_id.get(
            champion_id
        )

        if index is None:
            return None

        return self._champion_by_index.get(index)

    # =============================================================
    # 🧱 CRIAÇÃO DE UNIDADE
    # =============================================================

    def create_unit(self, champion):
        """
        Cria uma nova instância de unidade pertencente a um jogador.

        Cada instância recebe:
            - ID interno
            - UUID próprio
            - star
            - role
            - combat_profile

        O UUID diferencia cópias individuais do mesmo campeão.
        """

        if champion is None:
            raise ValueError(
                "Não é possível criar unidade a partir de None."
            )

        unit_id = self.get_unit_id(champion)

        if unit_id is None:
            raise ValueError(
                f"Não foi possível identificar o campeão: "
                f"{champion}"
            )

        # Campeão original do catálogo.
        base_champion = self.get_champion(unit_id)

        if base_champion is None:
            raise ValueError(
                f"Campeão não encontrado para ID {unit_id}."
            )

        unit = {
            # -----------------------------------------------------
            # 🆔 ID utilizado internamente pelo jogo
            # -----------------------------------------------------
            "id": unit_id,

            # -----------------------------------------------------
            # 🆔 ID original do JSON, quando existir
            # -----------------------------------------------------
            "champion_id": self.get_data_id(
                base_champion
            ),

            "name": base_champion.get(
                "name",
                "Unknown",
            ),

            "cost": base_champion.get(
                "cost",
                1,
            ),

            "traits": list(
                base_champion.get(
                    "traits",
                    []
                )
            ),

            "star": 1,

            # -----------------------------------------------------
            # 🆔 Identidade da cópia individual
            # -----------------------------------------------------
            "uuid": str(
                uuid.uuid4()
            ),
        }

        # =========================================================
        # 🛡️ ROLE
        # =========================================================

        role = base_champion.get(
            "role"
        )

        if role is None:
            role = UnitRole.FIGHTER

        unit["role"] = role

        # =========================================================
        # ⚔️ PERFIL DE COMBATE
        # =========================================================

        combat_profile = base_champion.get(
            "combat_profile"
        )

        if combat_profile is not None:
            unit["combat_profile"] = deepcopy(
                combat_profile
            )

        return unit

    # =============================================================
    # 📊 CONTAGEM DE CÓPIAS
    # =============================================================

    def count_copies(self, units):
        """
        Conta quantas cópias equivalentes de cada campeão
        o jogador possui.

        IMPORTANTE:

        Só deve receber unidades realmente pertencentes ao jogador.

        Shop e UnitPool não entram aqui.
        """

        counts = {}

        if units is None:
            return counts

        for unit in units:

            if not self.is_valid_unit(unit):
                continue

            unit_id = unit.get("id")

            if unit_id is None:
                continue

            star = unit.get(
                "star",
                1
            )

            copies = GameConfig.get_star_copies(
                star
            )

            counts[unit_id] = (
                counts.get(unit_id, 0)
                + copies
            )

        return counts

    # =============================================================
    # 🔢 CONTAR CÓPIAS DE UM CAMPEÃO
    # =============================================================

    def count_unit_copies(
        self,
        units,
        unit_id,
    ):
        """
        Retorna quantas cópias equivalentes de um campeão
        o jogador possui.
        """

        if units is None:
            return 0

        total = 0

        for unit in units:

            if not self.is_valid_unit(unit):
                continue

            if unit.get("id") != unit_id:
                continue

            star = unit.get(
                "star",
                1
            )

            total += GameConfig.get_star_copies(
                star
            )

        return total

    # =============================================================
    # ⬆️ ESTADO DE UPGRADE
    # =============================================================

    def get_upgrade_state(
        self,
        unit,
        unit_counts,
    ):
        """
        Retorna o estado de upgrade.

        Valores:

            0 = sem progresso
            1 = possui 2 cópias
            2 = pode formar 2★
            3 = já é 2★
            4 = próximo de 3★
            5 = já é 3★
        """

        if not self.is_valid_unit(unit):
            return 0

        star = unit.get(
            "star",
            1
        )

        unit_id = unit.get(
            "id"
        )

        # ---------------------------------------------------------
        # ⭐ 3★
        # ---------------------------------------------------------

        if star >= 3:
            return 5

        copies = unit_counts.get(
            unit_id,
            0
        )

        # ---------------------------------------------------------
        # ⭐ 1★
        # ---------------------------------------------------------

        if star == 1:

            if copies >= 9:
                return 4

            if copies >= 3:
                return 2

            if copies >= 2:
                return 1

            return 0

        # ---------------------------------------------------------
        # ⭐ 2★
        # ---------------------------------------------------------

        if star == 2:

            if copies >= 9:
                return 4

            return 3

        return 0

    # =============================================================
    # 💰 VALOR DO UPGRADE
    # =============================================================

    def get_upgrade_value(
        self,
        unit,
        unit_counts,
    ):
        """
        Retorna um valor heurístico de proximidade de upgrade.

        Não aplica upgrade.
        """

        if not self.is_valid_unit(unit):
            return 0.0

        state = self.get_upgrade_state(
            unit,
            unit_counts,
        )

        values = {
            0: 0.0,
            1: 0.5,
            2: 1.0,
            3: 0.5,
            4: 1.0,
            5: 0.0,
        }

        return values.get(
            state,
            0.0,
        )

    # =============================================================
    # ❓ PODE UPGRADE?
    # =============================================================

    def can_upgrade(
        self,
        unit,
        unit_counts,
    ):
        """
        Verifica se a quantidade total de cópias permite
        o próximo upgrade.

        ⚠️ Isso apenas verifica quantidade.

        A execução real do upgrade precisará consumir as cópias
        corretamente e será coordenada pelo Env/UnitPool.
        """

        if not self.is_valid_unit(unit):
            return False

        star = unit.get(
            "star",
            1
        )

        if star >= 3:
            return False

        unit_id = unit.get(
            "id"
        )

        copies = unit_counts.get(
            unit_id,
            0
        )

        required = (
            3
            if star == 1
            else 9
        )

        return copies >= required

    # =============================================================
    # ⭐ CRIAR RESULTADO DE UPGRADE
    # =============================================================

    def create_upgraded_unit(
        self,
        unit,
        new_star,
    ):
        """
        Cria uma nova representação da unidade com a nova estrela.

        NÃO:
            - remove outras unidades
            - altera Board
            - altera Bench
            - altera UnitPool
            - concede recompensa

        Isso será responsabilidade da camada que coordena
        ownership.
        """

        if not self.is_valid_unit(unit):
            raise ValueError(
                "Unidade inválida para upgrade."
            )

        current_star = unit.get(
            "star",
            1
        )

        if new_star <= current_star:
            raise ValueError(
                "A nova estrela precisa ser maior "
                "que a estrela atual."
            )

        if new_star > 3:
            raise ValueError(
                "O jogo suporta no máximo 3 estrelas."
            )

        upgraded = deepcopy(unit)

        upgraded["star"] = new_star

        # Nova identidade lógica.
        upgraded["uuid"] = str(
            uuid.uuid4()
        )

        return upgraded

    # =============================================================
    # 📋 CATÁLOGO
    # =============================================================

    def get_all_champions(self):
        """
        Retorna o catálogo de campeões.

        Preferimos não modificar diretamente os objetos retornados.
        """

        return self.champions

    def get_champions_by_cost(self, cost):
        """
        Retorna campeões de determinado custo.
        """

        return [
            champion
            for champion in self.champions
            if champion.get("cost") == cost
        ]

    # =============================================================
    # 🧹 VALIDAÇÃO
    # =============================================================

    @staticmethod
    def is_valid_unit(unit):
        """
        Validação mínima de uma unidade pertencente a jogador.
        """

        if not isinstance(unit, dict):
            return False

        required = (
            "id",
            "name",
            "cost",
            "star",
            "uuid",
        )

        return all(
            key in unit
            for key in required
        )

    # =============================================================
    # 🐛 DEBUG
    # =============================================================

    def debug_print_catalog(self):
        """
        Mostra o catálogo e seus IDs.
        """

        print("\n========== UNIT CATALOG ==========")

        for index, champion in enumerate(
            self.champions
        ):
            print(
                f"[{index}] "
                f"{champion.get('name', '?')} | "
                f"JSON ID={champion.get('id')} | "
                f"Cost={champion.get('cost', '?')}"
            )

        print("==================================")