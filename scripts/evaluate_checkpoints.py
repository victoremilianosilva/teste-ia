"""Head-to-head evaluation of two fixed TFT policy checkpoints.

Example (PowerShell):
  python scripts/evaluate_checkpoints.py --baseline checkpoints/baseline.pt --candidate tft_checkpoint.pt --matches 40 --output reports/head_to_head.csv

Each match puts four seats on each policy and rotates the candidate seats between matches.
The script does not train either policy or write to the training checkpoint.
"""
from __future__ import annotations

import argparse
import csv
import json
import random
import sys
from collections import defaultdict
from pathlib import Path

# Running "python scripts/evaluate_checkpoints.py" makes scripts/ the
# first import directory. Add the repository root so top-level modules
# (cpp_lobby_env.py, policy.py) resolve from the project root.
_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

import numpy as np
import torch

from cpp_lobby_env import CppTFTLobbyWrapper
from policy import TFTPolicy


ACTION_DIMS = [9, 5, 9, 28, 28, 28]
PASS_ACTION = {"type": 6}


def load_policy(path: Path, obs_dim: int, device: torch.device) -> TFTPolicy:
    checkpoint = torch.load(path, map_location=device)
    state = checkpoint.get("policy", checkpoint)
    policy = TFTPolicy(obs_dim, ACTION_DIMS).to(device)
    policy.load_state_dict(state)
    policy.eval()
    return policy


def as_mask_batch(mask_list, indices, device):
    keys = mask_list[0].keys()
    return {
        key: torch.as_tensor(
            np.stack([mask_list[i][key] for i in indices]),
            dtype=torch.bool,
            device=device,
        )
        for key in keys
    }


def policy_actions(policy, observations, masks, indices, device):
    if not indices:
        return {}
    obs_batch = torch.as_tensor(
        np.asarray(observations[indices], dtype=np.float32),
        dtype=torch.float32,
        device=device,
    )
    mask_batch = as_mask_batch(masks, indices, device)
    with torch.no_grad():
        actions = policy.get_action(
            obs_batch,
            masks=mask_batch,
            deterministic=True,
        )[0].detach().cpu().numpy()
    return {idx: actions[row].astype(int).tolist() for row, idx in enumerate(indices)}


def action_dict(values):
    """Translate the six policy outputs into the native adapter's action contract."""
    action_type = int(values[0])
    result = {
        "type": action_type,
        "shop_slot": int(values[1]),
        "bench_slot": int(values[2]),
        "board_target": int(values[3]),
        "board_source": int(values[4]),
        "conditioned_board_target": int(values[5]),
    }
    if action_type == 7:
        result.update({
            "item_slot": int(values[1]),
            "item_target": int(values[2]),
        })
    elif action_type == 8:
        result.update({
            "component_first": int(values[1]),
            "component_second": int(values[2]),
            "item_target": int(values[3]),
        })
    return result


def run_match(factory, baseline, candidate, candidate_slots, seed, device, max_steps):
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)

    lobby = factory(seed=seed)
    try:
        observations = np.asarray(lobby.reset(), dtype=np.float32)
        if observations.ndim != 2 or observations.shape[0] != 8:
            raise ValueError(f"Observações inesperadas: {observations.shape}")
        obs_dim = observations.shape[-1]

        # Checkpoint models are loaded by the caller after the first lobby establishes obs_dim.
        policies = {"baseline": baseline, "candidate": candidate}
        rows = []
        final_info = {}
        per_player_action_counts = {
            player_id: {"actions": 0, "item_actions": 0, "equip_actions": 0, "craft_and_equip_actions": 0}
            for player_id in range(8)
        }
        for step in range(max_steps):
            if getattr(lobby, "finished", False):
                break
            masks = lobby.get_action_masks()
            if len(masks) != 8:
                raise ValueError(f"Esperava 8 máscaras; recebi {len(masks)}")

            candidate_indices = sorted(candidate_slots)
            baseline_indices = [i for i in range(8) if i not in candidate_slots]
            chosen = {}
            chosen.update(policy_actions(policies["candidate"], observations, masks, candidate_indices, device))
            chosen.update(policy_actions(policies["baseline"], observations, masks, baseline_indices, device))

            for player_id, action_values in chosen.items():
                if not lobby.players[player_id].alive:
                    continue
                action_type = int(action_values[0])
                counts = per_player_action_counts[player_id]
                counts["actions"] += 1
                if action_type in (7, 8):
                    counts["item_actions"] += 1
                if action_type == 7:
                    counts["equip_actions"] += 1
                elif action_type == 8:
                    counts["craft_and_equip_actions"] += 1

            actions = [
                action_dict(chosen[i]) if lobby.players[i].alive else dict(PASS_ACTION)
                for i in range(8)
            ]
            observations, _, done, info = lobby.step(actions)
            final_info = info if isinstance(info, dict) else {}
            observations = np.asarray(observations, dtype=np.float32)
            if done:
                break
        else:
            raise RuntimeError(f"Partida excedeu max_steps={max_steps}; resultado não será contabilizado.")

        get_public_state = getattr(lobby, "get_public_state", None)
        state = get_public_state() if callable(get_public_state) else final_info
        ranking = state.get("ranking") or state.get("final_ranking") or getattr(lobby, "final_ranking", [])
        placement_by_id = {}
        if isinstance(ranking, list):
            for rank, item in enumerate(ranking, start=1):
                player_id = item.get("player_id") if isinstance(item, dict) else item
                try:
                    placement_by_id[int(player_id)] = rank
                except (TypeError, ValueError):
                    continue

        players = state.get("players", [])
        if isinstance(players, list):
            for idx, player in enumerate(players):
                if not isinstance(player, dict):
                    continue
                pid = int(player.get("player_id", idx))
                place = player.get("placement")
                if place is not None:
                    try:
                        placement_by_id[pid] = int(place)
                    except (TypeError, ValueError):
                        pass

        if len(placement_by_id) < 8:
            raise RuntimeError(
                "A engine não expôs colocação para todos os jogadores; "
                "não vou inferir rankings ausentes."
            )

        for player_id in range(8):
            version = "candidate" if player_id in candidate_slots else "baseline"
            placement = placement_by_id[player_id]
            rows.append({
                "seed": seed,
                "player_id": player_id,
                "version": version,
                "placement": placement,
                "win": int(placement == 1),
                "round": state.get("round", getattr(lobby, "round", "")),
                "candidate_seats": ",".join(map(str, sorted(candidate_slots))),
                **per_player_action_counts[player_id],
            })
        return rows
    finally:
        close = getattr(lobby, "close", None)
        if callable(close):
            close()


def _metric_summary(rows):
    if not rows:
        raise ValueError("Cannot summarize an empty policy group.")
    placements = [int(row["placement"]) for row in rows]
    action_total = sum(int(row.get("actions", 0)) for row in rows)
    item_total = sum(int(row.get("item_actions", 0)) for row in rows)
    equip_total = sum(int(row.get("equip_actions", 0)) for row in rows)
    craft_total = sum(int(row.get("craft_and_equip_actions", 0)) for row in rows)
    return {
        "players": len(rows),
        "mean_placement": float(np.mean(placements)),
        "win_rate": float(np.mean([int(row["win"]) for row in rows])),
        "top4_rate": float(np.mean([int(row["placement"]) <= 4 for row in rows])),
        "actions": action_total,
        "item_actions": item_total,
        "item_action_rate": float(item_total / action_total) if action_total else 0.0,
        "equip_actions": equip_total,
        "craft_and_equip_actions": craft_total,
    }


def summarize_paired_seeds(rows, bootstrap_samples=4000, bootstrap_seed=20261023):
    """Summarize policy results and paired per-seed deltas; seed is the sampling unit."""
    if not rows:
        raise ValueError("Cannot summarize an empty evaluation.")
    by_seed = defaultdict(lambda: {"baseline": [], "candidate": []})
    for row in rows:
        seed = int(row["seed"])
        version = row["version"]
        if version not in ("baseline", "candidate"):
            raise ValueError(f"Unknown policy version: {version}")
        by_seed[seed][version].append(row)

    per_seed = []
    for seed in sorted(by_seed):
        groups = by_seed[seed]
        if len(groups["baseline"]) != 4 or len(groups["candidate"]) != 4:
            raise ValueError(
                f"Seed {seed} must contain exactly four players per policy; "
                f"got baseline={len(groups['baseline'])}, candidate={len(groups['candidate'])}."
            )
        baseline = _metric_summary(groups["baseline"])
        candidate = _metric_summary(groups["candidate"])
        per_seed.append({
            "seed": seed,
            "baseline": baseline,
            "candidate": candidate,
            "delta_candidate_minus_baseline": {
                "mean_placement": candidate["mean_placement"] - baseline["mean_placement"],
                "win_rate": candidate["win_rate"] - baseline["win_rate"],
                "top4_rate": candidate["top4_rate"] - baseline["top4_rate"],
            },
        })

    def bootstrap_ci(values):
        values = np.asarray(values, dtype=np.float64)
        if values.size == 0:
            return [0.0, 0.0]
        if values.size == 1 or bootstrap_samples <= 0:
            point = float(values.mean())
            return [point, point]
        rng = np.random.default_rng(bootstrap_seed)
        sample_indices = rng.integers(0, values.size, size=(bootstrap_samples, values.size))
        means = values[sample_indices].mean(axis=1)
        return [float(np.quantile(means, 0.025)), float(np.quantile(means, 0.975))]

    baseline_rows = [row for row in rows if row["version"] == "baseline"]
    candidate_rows = [row for row in rows if row["version"] == "candidate"]
    delta_metrics = {}
    for metric in ("mean_placement", "win_rate", "top4_rate"):
        values = [item["delta_candidate_minus_baseline"][metric] for item in per_seed]
        delta_metrics[metric] = {
            "mean": float(np.mean(values)),
            "bootstrap_95_ci": bootstrap_ci(values),
            "seed_count": len(values),
        }

    return {
        "seed_count": len(per_seed),
        "baseline": _metric_summary(baseline_rows),
        "candidate": _metric_summary(candidate_rows),
        "paired_delta_candidate_minus_baseline": delta_metrics,
        "per_seed": per_seed,
        "interpretation": (
            "Negative mean_placement delta favors candidate (lower placement is better); "
            "positive win_rate/top4_rate deltas favor candidate. Confidence intervals are "
            "paired bootstrap intervals across seeds, not proof of causality. Use enough "
            "seeds and keep the seed set fixed when comparing future checkpoints."
        ),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline", required=True, type=Path)
    parser.add_argument("--candidate", required=True, type=Path)
    parser.add_argument("--matches", type=int, default=40)
    parser.add_argument("--seed", type=int, default=20261015)
    parser.add_argument("--max-steps", type=int, default=10000)
    parser.add_argument("--output", type=Path, default=Path("reports/head_to_head.csv"))
    parser.add_argument("--json-output", type=Path, default=Path("reports/head_to_head_summary.json"))
    parser.add_argument("--bootstrap-samples", type=int, default=4000)
    args = parser.parse_args()
    if args.matches < 1:
        parser.error("--matches precisa ser >= 1")
    if args.bootstrap_samples < 0:
        parser.error("--bootstrap-samples precisa ser >= 0")
    if not args.baseline.is_file() or not args.candidate.is_file():
        parser.error("Os caminhos dos dois checkpoints precisam existir.")

    device = torch.device("cpu")
    factory = CppTFTLobbyWrapper
    print(f"Engine: C++ (única engine) | partidas: {args.matches} | device: CPU")

    # Establish observation dimensions using the selected engine.
    probe = factory(seed=args.seed)
    try:
        probe_obs = np.asarray(probe.reset(), dtype=np.float32)
        if probe_obs.ndim != 2 or probe_obs.shape[0] != 8:
            raise ValueError(f"Observações inesperadas no probe: {probe_obs.shape}")
        obs_dim = probe_obs.shape[-1]
    finally:
        close = getattr(probe, "close", None)
        if callable(close):
            close()

    baseline = load_policy(args.baseline, obs_dim, device)
    candidate = load_policy(args.candidate, obs_dim, device)

    rows = []
    for match_idx in range(args.matches):
        # Rotate which seats use the candidate to reduce seat-order bias.
        offset = match_idx % 8
        candidate_slots = {(offset + j) % 8 for j in range(4)}
        match_seed = args.seed + match_idx
        result = run_match(
            factory, baseline, candidate, candidate_slots,
            match_seed, device, args.max_steps,
        )
        rows.extend(result)
        print(f"[{match_idx + 1}/{args.matches}] seed={match_seed} concluída")

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)

    print(f"CSV: {args.output}")
    summary = summarize_paired_seeds(
        rows, bootstrap_samples=args.bootstrap_samples, bootstrap_seed=args.seed
    )
    summary["checkpoints"] = {
        "baseline": str(args.baseline),
        "candidate": str(args.candidate),
    }
    summary["engine"] = "C++"
    summary["device"] = "CPU"
    summary["seed_start"] = args.seed
    summary["matches"] = args.matches
    args.json_output.parent.mkdir(parents=True, exist_ok=True)
    args.json_output.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(f"JSON: {args.json_output}")
    for version in ("baseline", "candidate"):
        metric = summary[version]
        print(
            f"{version}: players={metric['players']} "
            f"avg_placement={metric['mean_placement']:.3f} "
            f"win_rate={metric['win_rate']:.3%} top4_rate={metric['top4_rate']:.3%}"
        )
    for metric, result in summary["paired_delta_candidate_minus_baseline"].items():
        low, high = result["bootstrap_95_ci"]
        print(f"paired Δ {metric}: {result['mean']:.4f} (bootstrap 95% CI [{low:.4f}, {high:.4f}])")


if __name__ == "__main__":
    main()
