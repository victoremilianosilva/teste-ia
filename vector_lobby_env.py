
import numpy as np


class LobbyVectorEnv:
    """
    Adaptador vetorizado para TFTLobby.

    Cada ambiente representa uma lobby com 8 jogadores.
    Não cria uma policy por jogador: o Trainer continua
    compartilhando a mesma TFTPolicy entre todos.
    """

    PLAYERS_PER_LOBBY = 8

    def __init__(self, env_fns):
        self.envs = [make_env() for make_env in env_fns]
        self.num_envs = len(self.envs)

        if self.num_envs == 0:
            raise ValueError("É necessário criar pelo menos uma lobby.")

    def reset(self):
        observations = [env.reset() for env in self.envs]
        return np.stack(observations).astype(np.float32)

    def env_method(self, method_name, *args, **kwargs):
        """Mantém compatibilidade com as chamadas do Trainer."""
        return [
            getattr(env, method_name)(*args, **kwargs)
            for env in self.envs
        ]

    def step(self, actions):
        """
        Entrada:
            actions: [lobby][jogador]

        Saídas:
            observations: (lobbies, 8, obs_dim)
            rewards:      (lobbies, 8)
            dones:        (lobbies, 8)
            infos:        uma info por lobby
        """
        if len(actions) != self.num_envs:
            raise ValueError(
                f"Recebi ações para {len(actions)} lobbies; "
                f"esperava {self.num_envs}."
            )

        all_obs = []
        all_rewards = []
        all_dones = []
        all_infos = []

        for env, lobby_actions in zip(self.envs, actions):
            obs, rewards, lobby_done, info = env.step(lobby_actions)

            rewards = np.asarray(rewards, dtype=np.float32)
            if rewards.shape != (self.PLAYERS_PER_LOBBY,):
                raise ValueError(
                    f"Shape de rewards inválido: {rewards.shape}"
                )

            # O done individual acontece quando o jogador é eliminado.
            dones = np.asarray(
                [not player.alive for player in env.players],
                dtype=np.bool_,
            )

            # Quando a partida termina, todos os episódios individuais
            # terminam, inclusive o do vencedor.
            if lobby_done:
                dones[:] = True

            info = dict(info)
            info["lobby_done"] = bool(lobby_done)

            # Salva a observação terminal antes de reiniciar a lobby.
            # A recompensa terminal e o ranking já foram calculados
            # por TFTLobby.step().
            obs = np.asarray(obs, dtype=np.float32)

            if lobby_done:
                obs = env.reset()

            all_obs.append(obs)
            all_rewards.append(rewards)
            all_dones.append(dones)
            all_infos.append(info)

        return (
            np.stack(all_obs).astype(np.float32),
            np.stack(all_rewards).astype(np.float32),
            np.stack(all_dones).astype(np.bool_),
            all_infos,
        )

    def close(self):
        for env in self.envs:
            close_method = getattr(env, "close", None)
            if callable(close_method):
                close_method()