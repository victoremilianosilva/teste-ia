# units/UnitManager.py

from copy import deepcopy
from pathlib import Path
import json
import uuid

from config.GameConfig import GameConfig
from combat.CombatProfileManager import CombatProfileManager, UnitRole


class UnitManager:
    """
    🧩 Gerencia o catálogo e a criação das unidades.

    Compatível com o catálogo gerado pelo script gerar_units.py.

    Responsabilidades:
        - carregar unidades do JSON
        - preservar role e combat_profile precomputados
        - normalizar os atributos de combate
        - atribuir IDs internos
        - criar instâncias individuais
        - contar cópias
        - verificar upgrades
        - criar resultados de upgrade

    Não é responsabilidade:
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

    STAT_KEYS = (
        "max_hp",
        "attack_damage",
        "attack_speed",
        "armor",
        "magic_resist",
        "attack_range",
    )

    # Compatibilidade com o formato original do CommunityDragon.
    STAT_ALIASES = {
        "max_hp": ("max_hp", "hp"),
        "attack_damage": ("attack_damage", "damage"),
        "attack_speed": ("attack_speed", "attackSpeed"),
        "armor": ("armor",),
        "magic_resist": ("magic_resist", "magicResist", "mr"),
        "attack_range": ("attack_range", "range"),
    }

    ROLE_NAMES = {
        0: "TANK",
        1: "CARRY",
        2: "SUPPORT",
        3: "FIGHTER",
        4: "ASSASSIN",
    }

    def __init__(
        self,
        units_path=None,
        combat_profile_mgr=None,
        champions=None,
    ):
        # ---------------------------------------------------------
        # 📂 Caminho do catálogo
        # ---------------------------------------------------------

        self.units_path = self._resolve_units_path(
            units_path
        )

        # ---------------------------------------------------------
        # ⚔️ Gerenciador de perfil de combate
        # ---------------------------------------------------------

        self.combat_profile_mgr = (
            combat_profile_mgr
            if combat_profile_mgr is not None
            else CombatProfileManager()
        )

        # ---------------------------------------------------------
        # 📦 Carregamento do catálogo
        # ---------------------------------------------------------

        if champions is not None:
            self.champions = [
                self._prepare_champion(champion)
                for champion in champions
            ]
        else:
            self.champions = self._load_champions()

        if not self.champions:
            raise ValueError(
                "Nenhuma unidade foi carregada."
            )

        # ---------------------------------------------------------
        # 🆔 Índices internos
        # ---------------------------------------------------------

        self._champion_by_index = {
            index: champion
            for index, champion in enumerate(self.champions)
        }

        self._index_by_data_id = {}

        for index, champion in enumerate(self.champions):
            data_id = self.get_data_id(champion)

            if data_id is not None:
                self._index_by_data_id[data_id] = index

        print(
            f"[UnitManager] {len(self.champions)} unidades carregadas."
        )

        print(
            f"[UnitManager] Catálogo: {self.units_path}"
        )

    # =============================================================
    # 📂 RESOLVER CAMINHO
    # =============================================================

    @staticmethod
    def _resolve_units_path(units_path=None):
        """
        Resolve o arquivo do catálogo.

        Prioridade:
            1. Caminho informado explicitamente.
            2. units_gerado.json na raiz do projeto.
            3. GameConfig.UNITS_PATH.
        """

        if units_path is not None:
            return Path(units_path).expanduser().resolve()

        project_root = Path(__file__).resolve().parent.parent

        generated_path = (
            project_root / "units_gerado.json"
        )

        if generated_path.exists():
            return generated_path

        configured_path = Path(
            GameConfig.UNITS_PATH
        ).expanduser()

        if not configured_path.is_absolute():
            configured_path = (
                project_root / configured_path
            )

        return configured_path.resolve()

    # =============================================================
    # 📦 EXTRAIR UNIDADES DO JSON
    # =============================================================

    @staticmethod
    def _extract_champions(data):
        """
        Aceita diferentes estruturas de catálogo:

            [...]
            {"units": [...]}
            {"champions": [...]}
            {"data": [...]}
        """

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
                "Formato inválido para o catálogo de unidades."
            )

        if not isinstance(champions, list):
            raise ValueError(
                "A lista de unidades do JSON é inválida."
            )

        return champions

    # =============================================================
    # 📦 CARREGAR CATÁLOGO
    # =============================================================

    def _load_champions(self):
        """
        Carrega e prepara o catálogo.

        Para unidades geradas previamente, preserva:
            - stats normalizados
            - role
            - role_name
            - combat_profile

        O CombatProfileManager só é chamado quando faltam
        dados essenciais, para manter compatibilidade com
        catálogos antigos.
        """

        if not self.units_path.exists():
            raise FileNotFoundError(
                f"Arquivo de unidades não encontrado: "
                f"{self.units_path}"
            )

        with self.units_path.open(
            "r",
            encoding="utf-8",
        ) as file:
            data = json.load(file)

        champions = self._extract_champions(data)

        if not champions:
            raise ValueError(
                f"Nenhuma unidade encontrada em {self.units_path}"
            )

        processed = []

        for position, champion in enumerate(champions):
            if not isinstance(champion, dict):
                raise ValueError(
                    f"Unidade inválida na posição {position}: "
                    "esperado um objeto JSON."
                )

            prepared = self._prepare_champion(
                champion
            )

            processed.append(prepared)

        # ---------------------------------------------------------
        # 🆔 Validar IDs únicos do dataset
        # ---------------------------------------------------------

        seen_ids = set()

        for champion in processed:
            data_id = self.get_data_id(champion)

            if data_id is None:
                continue

            if data_id in seen_ids:
                raise ValueError(
                    f"ID duplicado no catálogo: {data_id}"
                )

            seen_ids.add(data_id)

        return processed

    # =============================================================
    # 🧩 PREPARAR UNIDADE DO CATÁLOGO
    # =============================================================

    def _prepare_champion(self, champion):
        """
        Normaliza uma unidade do catálogo sem alterar o JSON original.

        Não recalcula role nem combat_profile quando ambos
        já foram fornecidos pelo gerador.
        """

        if not isinstance(champion, dict):
            raise ValueError(
                "O campeão precisa ser um dicionário."
            )

        unit = deepcopy(champion)

        # ---------------------------------------------------------
        # 🏷️ Nome e custo
        # ---------------------------------------------------------

        unit["name"] = (
            unit.get("name")
            or unit.get("characterName")
            or unit.get("apiName")
            or "Unknown"
        )

        try:
            unit["cost"] = int(unit.get("cost", 1))
        except (TypeError, ValueError):
            unit["cost"] = 1

        unit["traits"] = self._normalize_traits(
            unit.get("traits", [])
        )

        # ---------------------------------------------------------
        # 📊 Atributos normalizados
        # ---------------------------------------------------------

        unit["stats"] = self._normalize_stats(
            unit.get("stats", {}),
            unit,
        )

        # ---------------------------------------------------------
        # 🛡️ Role precomputado
        # ---------------------------------------------------------

        role = unit.get("role")

        # ---------------------------------------------------------
        # ⚔️ Perfil precomputado
        # ---------------------------------------------------------

        combat_profile = unit.get(
            "combat_profile"
        )

        # Só executa o processamento antigo se faltar informação.
        # Catálogos gerados corretamente não precisam dessa etapa.
        if role is None or not isinstance(
            combat_profile,
            dict,
        ):
            unit = self.combat_profile_mgr.process_unit(
                unit
            )

            # O processador antigo pode alterar os dados.
            # Reaplicamos a normalização dos atributos.
            unit["stats"] = self._normalize_stats(
                unit.get("stats", {}),
                unit,
            )

            role = unit.get("role")

            combat_profile = unit.get(
                "combat_profile"
            )

        unit["role"] = self._normalize_role(role)

        unit["role_name"] = self._get_role_name(
            unit["role"],
            unit.get("role_name"),
        )

        if isinstance(combat_profile, dict):
            unit["combat_profile"] = deepcopy(
                combat_profile
            )
        else:
            unit["combat_profile"] = {}

        # ---------------------------------------------------------
        # 🧹 Remover dados auxiliares que não são necessários
        # ---------------------------------------------------------

        unit.pop("missing_stats", None)

        return unit

    # =============================================================
    # 📊 NORMALIZAR ATRIBUTOS
    # =============================================================

    @classmethod
    def _normalize_stats(cls, stats, champion=None):
        """
        Converte atributos do JSON para os nomes usados pelo jogo.

        Aceita tanto o formato gerado quanto o formato original.

        Exemplo:
            hp          -> max_hp
            damage      -> attack_damage
            attackSpeed -> attack_speed
            range       -> attack_range
        """

        if not isinstance(stats, dict):
            stats = {}

        champion = champion or {}
        normalized = {}

        for target_key, aliases in cls.STAT_ALIASES.items():
            value = None

            # Primeiro, procura dentro de stats.
            for alias in aliases:
                candidate = stats.get(alias)

                if cls._is_valid_number(candidate):
                    value = candidate
                    break

            # Compatibilidade com catálogos antigos que guardam
            # os atributos diretamente na unidade.
            if value is None:
                for alias in aliases:
                    candidate = champion.get(alias)

                    if cls._is_valid_number(candidate):
                        value = candidate
                        break

            if value is not None:
                normalized[target_key] = value

        # Mantém apenas os seis atributos utilizados pelo jogo.
        # Não inventa novos valores aqui: as estimativas devem ser
        # calculadas pelo script gerador do catálogo.
        return normalized

    @staticmethod
    def _is_valid_number(value):
        """
        Verifica se o valor é numérico e finito.
        """

        if isinstance(value, bool):
            return False

        if not isinstance(value, (int, float)):
            return False

        try:
            return (
                value == value
                and abs(value) != float("inf")
            )
        except (TypeError, ValueError):
            return False

    @staticmethod
    def _normalize_traits(traits):
        """
        Garante que traits seja sempre uma lista.
        """

        if traits is None:
            return []

        if isinstance(traits, list):
            return deepcopy(traits)

        if isinstance(traits, tuple):
            return list(traits)

        if isinstance(traits, str):
            return [traits] if traits else []

        return []

    # =============================================================
    # 🛡️ NORMALIZAR ROLE
    # =============================================================

    @staticmethod
    def _normalize_role(role):
        """
        Converte o role armazenado no JSON para UnitRole.

        Compatível com:
            0, 1, 2, 3, 4
            UnitRole.TANK
            "TANK", "CARRY", "SUPPORT", "FIGHTER", "ASSASSIN"
        """

        if isinstance(role, UnitRole):
            return role

        if isinstance(role, str):
            role_name = role.strip().upper()

            # Tenta primeiro pelo nome do enum.
            if hasattr(UnitRole, role_name):
                return getattr(
                    UnitRole,
                    role_name,
                )

            # Depois, tenta interpretar como número.
            try:
                role = int(role)
            except ValueError:
                return UnitRole.FIGHTER

        if isinstance(role, int):
            try:
                return UnitRole(role)
            except (ValueError, TypeError):
                return UnitRole.FIGHTER

        return UnitRole.FIGHTER

    @classmethod
    def _get_role_name(cls, role, fallback=None):
        """
        Retorna o nome textual do role.
        """

        if isinstance(fallback, str) and fallback.strip():
            return fallback.strip().upper()

        role_value = getattr(
            role,
            "value",
            role,
        )

        if isinstance(role_value, int):
            return cls.ROLE_NAMES.get(
                role_value,
                "FIGHTER",
            )

        role_name = getattr(
            role,
            "name",
            None,
        )

        if role_name:
            return str(role_name).upper()

        return "FIGHTER"

    # =============================================================
    # 🆔 IDENTIFICADOR ORIGINAL
    # =============================================================

    @staticmethod
    def get_data_id(champion):
        """
        Retorna o identificador original do dataset.

        O catálogo gerado pode utilizar apiName ou characterName,
        mesmo que não possua um campo id.
        """

        if not isinstance(champion, dict):
            return None

        for key in (
            "id",
            "apiName",
            "characterName",
            "champion_id",
        ):
            value = champion.get(key)

            if value is not None:
                return value

        return None

    # =============================================================
    # 🆔 ID INTERNO
    # =============================================================

    def get_unit_id(self, champion):
        """
        Retorna o ID interno, isto é, o índice no catálogo.
        """

        if champion is None:
            return None

        # ---------------------------------------------------------
        # 🧩 Objeto exato do catálogo
        # ---------------------------------------------------------

        for index, stored_champion in (
            self._champion_by_index.items()
        ):
            if champion is stored_champion:
                return index

        if not isinstance(champion, dict):
            return None

        # ---------------------------------------------------------
        # 🆔 Identificador original
        # ---------------------------------------------------------

        data_id = self.get_data_id(champion)

        if data_id in self._index_by_data_id:
            return self._index_by_data_id[data_id]

        # ---------------------------------------------------------
        # 🔢 Compatibilidade com ID interno
        # ---------------------------------------------------------

        if isinstance(data_id, int):
            if data_id in self._champion_by_index:
                return data_id

        return None

    # =============================================================
    # 🔎 LOCALIZAR CAMPEÃO
    # =============================================================

    def get_champion(self, champion_id):
        """
        Localiza um campeão.

        Para IDs inteiros, prioriza o índice interno.
        Para outros valores, procura o identificador do dataset.
        """

        if isinstance(champion_id, int):
            champion = self._champion_by_index.get(
                champion_id
            )

            if champion is not None:
                return champion

        index = self._index_by_data_id.get(
            champion_id
        )

        if index is None:
            return None

        return self._champion_by_index.get(index)

    # =============================================================
    # 🧱 CRIAR UNIDADE
    # =============================================================

    def create_unit(self, champion):
        """
        Cria uma instância individual para um jogador.

        A instância recebe:
            - ID interno
            - champion_id original
            - UUID próprio
            - nome, custo e traits
            - stats normalizados
            - role precomputado
            - combat_profile precomputado
            - ability, quando existir

        Cada cópia possui um UUID diferente.
        """

        if champion is None:
            raise ValueError(
                "Não é possível criar uma unidade a partir de None."
            )

        unit_id = self.get_unit_id(champion)

        if unit_id is None:
            raise ValueError(
                "Não foi possível identificar o campeão: "
                f"{champion}"
            )

        base_champion = self._champion_by_index.get(
            unit_id
        )

        if base_champion is None:
            raise ValueError(
                f"Campeão não encontrado para ID {unit_id}."
            )

        unit = {
            # -----------------------------------------------------
            # 🆔 Identidade
            # -----------------------------------------------------

            "id": unit_id,
            "champion_id": self.get_data_id(
                base_champion
            ),
            "uuid": str(uuid.uuid4()),

            # -----------------------------------------------------
            # 🏷️ Dados da unidade
            # -----------------------------------------------------

            "name": base_champion.get(
                "name",
                "Unknown",
            ),
            "cost": base_champion.get(
                "cost",
                1,
            ),
            "traits": deepcopy(
                base_champion.get("traits", [])
            ),
            "star": 1,

            # -----------------------------------------------------
            # 📊 Atributos de combate
            # -----------------------------------------------------

            "stats": deepcopy(
                base_champion.get("stats", {})
            ),

            # -----------------------------------------------------
            # 🛡️ Perfil e papel
            # -----------------------------------------------------

            "role": base_champion.get(
                "role",
                UnitRole.FIGHTER,
            ),
            "role_name": base_champion.get(
                "role_name",
                "FIGHTER",
            ),
            "combat_profile": deepcopy(
                base_champion.get(
                    "combat_profile",
                    {},
                )
            ),
        }

        # Preserva informações úteis do CommunityDragon.
        for key in (
            "apiName",
            "characterName",
            "ability",
            "icon",
            "squareIcon",
        ):
            if key in base_champion:
                unit[key] = deepcopy(
                    base_champion[key]
                )

        return unit

    # =============================================================
    # 📊 CONTAGEM DE CÓPIAS
    # =============================================================

    def count_copies(self, units):
        """
        Conta cópias equivalentes por ID interno.

        Recebe apenas unidades pertencentes ao jogador.
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

            star = unit.get("star", 1)

            copies = GameConfig.get_star_copies(
                star
            )

            counts[unit_id] = (
                counts.get(unit_id, 0) + copies
            )

        return counts

    # =============================================================
    # 🔢 CONTAR CÓPIAS DE UMA UNIDADE
    # =============================================================

    def count_unit_copies(self, units, unit_id):
        """
        Retorna o total de cópias equivalentes de um campeão.
        """

        if units is None:
            return 0

        total = 0

        for unit in units:
            if not self.is_valid_unit(unit):
                continue

            if unit.get("id") != unit_id:
                continue

            total += GameConfig.get_star_copies(
                unit.get("star", 1)
            )

        return total

    # =============================================================
    # ⬆️ ESTADO DE UPGRADE
    # =============================================================

    def get_upgrade_state(self, unit, unit_counts):
        """
        Retorna o estado de upgrade:

            0 = sem progresso
            1 = possui 2 cópias
            2 = pode formar 2★
            3 = já é 2★
            4 = próximo de 3★
            5 = já é 3★
        """

        if not self.is_valid_unit(unit):
            return 0

        star = unit.get("star", 1)
        unit_id = unit.get("id")

        if star >= 3:
            return 5

        copies = unit_counts.get(
            unit_id,
            0,
        )

        if star == 1:
            if copies >= 9:
                return 4

            if copies >= 3:
                return 2

            if copies >= 2:
                return 1

            return 0

        if star == 2:
            if copies >= 9:
                return 4

            return 3

        return 0

    # =============================================================
    # 💰 VALOR DO UPGRADE
    # =============================================================

    def get_upgrade_value(self, unit, unit_counts):
        """
        Retorna um valor heurístico de proximidade de upgrade.

        Não executa o upgrade.
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

        return values.get(state, 0.0)

    # =============================================================
    # ❓ PODE FAZER UPGRADE?
    # =============================================================

    def can_upgrade(self, unit, unit_counts):
        """
        Verifica se existem cópias suficientes para o próximo upgrade.

        A remoção das cópias continua sendo responsabilidade
        da camada que coordena Board, Bench e UnitPool.
        """

        if not self.is_valid_unit(unit):
            return False

        star = unit.get("star", 1)

        if star >= 3:
            return False

        unit_id = unit.get("id")

        copies = unit_counts.get(
            unit_id,
            0,
        )

        required = 3 if star == 1 else 9

        return copies >= required

    # =============================================================
    # ⭐ CRIAR RESULTADO DE UPGRADE
    # =============================================================

    def create_upgraded_unit(self, unit, new_star):
        """
        Cria uma nova representação da unidade com outra estrela.

        Não remove cópias nem altera Board, Bench ou UnitPool.
        """

        if not self.is_valid_unit(unit):
            raise ValueError(
                "Unidade inválida para upgrade."
            )

        current_star = unit.get("star", 1)

        if new_star <= current_star:
            raise ValueError(
                "A nova estrela precisa ser maior que a atual."
            )

        if new_star > 3:
            raise ValueError(
                "O jogo suporta no máximo 3 estrelas."
            )

        upgraded = deepcopy(unit)

        upgraded["star"] = new_star
        upgraded["uuid"] = str(uuid.uuid4())

        return upgraded

    # =============================================================
    # 📋 CATÁLOGO
    # =============================================================

    def get_all_champions(self):
        """
        Retorna o catálogo de campeões.

        Retorna uma cópia para evitar alterações acidentais
        nos dados compartilhados do catálogo.
        """

        return deepcopy(self.champions)

    def get_champions_by_cost(self, cost):
        """
        Retorna os campeões de determinado custo.
        """

        return [
            deepcopy(champion)
            for champion in self.champions
            if champion.get("cost") == cost
        ]

    # =============================================================
    # 🧹 VALIDAÇÃO
    # =============================================================

    @staticmethod
    def is_valid_unit(unit):
        """
        Validação mínima de uma unidade pertencente ao jogador.
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
        Exibe os IDs internos e dados básicos do catálogo.
        """

        print("\n========== UNIT CATALOG ==========")

        for index, champion in enumerate(self.champions):
            print(
                f"[{index}] "
                f"{champion.get('name', '?')} | "
                f"Data ID={self.get_data_id(champion)} | "
                f"Cost={champion.get('cost', '?')} | "
                f"Role={champion.get('role_name', '?')} | "
                f"Stats={len(champion.get('stats', {}))}/6"
            )

        print("==================================")