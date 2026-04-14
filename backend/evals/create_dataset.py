"""
Create the golden eval dataset in LangSmith.

Two dataset groups:
  - "qlankr-eval-indexed"   → Qlankr repo (pre-indexed in GitNexus, tests full pipeline)
  - "qlankr-eval-github"    → External repos (no indexing, tests GitHub-only fallback)

Run once:
    cd backend && python -m evals.create_dataset
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), "../../.env"))

from langsmith import Client

client = Client()


def _upsert_dataset(name: str, description: str, examples: list[dict]) -> None:
    for ds in client.list_datasets():
        if ds.name == name:
            client.delete_dataset(dataset_id=ds.id)
            break
    dataset = client.create_dataset(name, description=description)
    client.create_examples(dataset_id=dataset.id, examples=examples)
    print(f"  Created '{name}' with {len(examples)} examples")


# ── Dataset 1: Qlankr repo (pre-indexed) ─────────────────────────────────────
# These PRs are from the Qlankr repo itself — must be indexed in GitNexus first.
# Tests the full pipeline: GitHub MCP + GitNexus MCP.

INDEXED_EXAMPLES = [
    {
        "_category": "large feature — agent + indexer rewrite",
        "inputs": {
            "pr_url": "https://github.com/aircode610/Qlankr/pull/9",
        },
        "outputs": {
            "expected_components": [
                "ReAct Agent",
                "Indexer",
                "API Endpoints",
            ],
            "expected_risks": [
                "agent can exhaust tool budget without submitting result",
                "MCP subprocess cold start latency",
                "no auth guard on debug endpoints",
            ],
            "expected_tools": [
                # Gather stage — GitHub
                "get_pull_request",
                "get_pull_request_files",
                "get_pull_request_comments",
                "get_file_contents",
                # Gather stage — GitNexus (repo is indexed)
                "cypher",
                "impact",
                # Unit stage
                "submit_unit_tests",
                # Integration stage — GitNexus
                "query",
                "context",
            ],
            "min_components": 2,
            "expect_gitnexus": True,
        },
    },
]


# ── Dataset 2: External repos (GitHub-only, no indexing) ──────────────────────
# These repos are NOT indexed in GitNexus. The agent should fall back to
# GitHub-only analysis and set confidence to "low".

GITHUB_ONLY_EXAMPLES = [
    # ── OpenTTD: small bugfix — 1 file ────────────────────────────────────────
    {
        "_category": "small bugfix — 1 file",
        "inputs": {
            "pr_url": "https://github.com/OpenTTD/OpenTTD/pull/15268",
        },
        "outputs": {
            "expected_components": [
                "Script API — Cargo Income",
                "Cargo Economy",
            ],
            "expected_risks": [
                "integer overflow in days_in_transit * 2 / 5 with large input values",
                "AI scripts relying on exact out-of-range return values will silently get different results",
                "documented max (637) diverges from actual safe max (163838)",
                "clamping before arithmetic changes observable behaviour",
            ],
            "expected_tools": [
                "get_pull_request",
                "get_pull_request_files",
                "get_pull_request_comments",
                "get_file_contents",
                "submit_unit_tests",
            ],
            "min_components": 1,
            "expect_gitnexus": False,
        },
    },
    # ── OpenTTD: small bugfix — road stop crash ───────────────────────────────
    {
        "_category": "small bugfix — 1 file",
        "inputs": {
            "pr_url": "https://github.com/OpenTTD/OpenTTD/pull/15270",
        },
        "outputs": {
            "expected_components": [
                "Station Construction",
                "Road Infrastructure",
            ],
            "expected_risks": [
                "crash regression if OWNER_NONE guard is removed or refactored",
                "behaviour change: players can now over-build drive-through stops on own one-way roads",
                "other callers of CheckFlatLandRoadStop may have unexamined assumptions",
                "backport risk — fix marked for stable branch",
            ],
            "expected_tools": [
                "get_pull_request",
                "get_pull_request_files",
                "get_pull_request_comments",
                "get_file_contents",
                "submit_unit_tests",
            ],
            "min_components": 1,
            "expect_gitnexus": False,
        },
    },
    # ── OpenTTD: large feature — 13 files ─────────────────────────────────────
    {
        "_category": "large feature — 13 files",
        "inputs": {
            "pr_url": "https://github.com/OpenTTD/OpenTTD/pull/14461",
        },
        "outputs": {
            "expected_components": [
                "Town Cargo Tracking",
                "Town Graph UI",
                "Save/Load System",
                "Script API — Town",
            ],
            "expected_risks": [
                "save file format change — loading from older saves",
                "memory layout change in town struct",
                "cargo history array replaced — data loss if migration incomplete",
                "graph UI does not handle towns with no cargo history",
            ],
            "expected_tools": [
                "get_pull_request",
                "get_pull_request_files",
                "get_pull_request_comments",
                "get_file_contents",
                "search_code",
                "submit_unit_tests",
            ],
            "min_components": 3,
            "expect_gitnexus": False,
        },
    },
    # ── OpenTTD: refactor — 30 files ──────────────────────────────────────────
    {
        "_category": "refactor — 30 files",
        "inputs": {
            "pr_url": "https://github.com/OpenTTD/OpenTTD/pull/13948",
        },
        "outputs": {
            "expected_components": [
                "Order Management",
                "Vehicle System",
                "Save/Load System",
                "Order GUI",
            ],
            "expected_risks": [
                "savegame compatibility — new SLV version required",
                "order iteration correctness — pointer-based traversal replaced with vector indexing",
                "order backup and restore broken if index mapping mishandled",
                "link graph refresh depends on order traversal order",
            ],
            "expected_tools": [
                "get_pull_request",
                "get_pull_request_files",
                "get_pull_request_comments",
                "get_file_contents",
                "search_code",
                "submit_unit_tests",
            ],
            "min_components": 3,
            "expect_gitnexus": False,
        },
    },
    # ── OpenTTD: new files only — new Script API class ────────────────────────
    {
        "_category": "new files only — nothing in graph",
        "inputs": {
            "pr_url": "https://github.com/OpenTTD/OpenTTD/pull/12015",
        },
        "outputs": {
            "expected_components": [
                "Script API — TileList",
                "Station Coverage",
            ],
            "expected_risks": [
                "new class not yet in knowledge graph — agent must rely on file contents alone",
                "ScriptTileList_StationCoverage exposes catchment_tiles directly — stale tile data",
                "regression tests only cover happy path",
            ],
            "expected_tools": [
                "get_pull_request",
                "get_pull_request_files",
                "get_pull_request_comments",
                "get_file_contents",
                "submit_unit_tests",
            ],
            "min_components": 1,
            "expect_gitnexus": False,
        },
    },
    # ── osu!: large feature — SongSelectV2 ────────────────────────────────────
    {
        "_category": "large feature — new screen (80+ files)",
        "inputs": {
            "pr_url": "https://github.com/ppy/osu/pull/32854",
        },
        "outputs": {
            "expected_components": [
                "SongSelectV2",
                "BeatmapCarouselV2",
                "PanelBeatmapSet / PanelBeatmap",
                "BeatmapLeaderboardWedge",
            ],
            "expected_risks": [
                "leaderboard not connected to selected beatmap bindable — scores never load",
                "no skin layer on new panels — custom skins silently ignored",
                "working beatmap bindable not propagated to OsuGame.Beatmap",
                "music not driven from new screen — track stays fixed",
                "filter control not wired — search produces no visible change",
            ],
            "expected_tools": [
                "get_pull_request",
                "get_pull_request_files",
                "get_pull_request_comments",
                "get_file_contents",
                "search_code",
                "list_directory",
                "submit_unit_tests",
            ],
            "min_components": 4,
            "expect_gitnexus": False,
        },
    },
    # ── Cataclysm-DDA: gameplay bugfix — 4 files ─────────────────────────────
    {
        "_category": "gameplay bugfix — underwater melee",
        "inputs": {
            "pr_url": "https://github.com/CleverRaven/Cataclysm-DDA/pull/86390",
        },
        "outputs": {
            "expected_components": [
                "Monster Melee Attack",
                "Monster Spellcasting Actor",
                "Melee Actor",
                "Gun Actor",
            ],
            "expected_risks": [
                "asymmetric guard logic — melee_attack checks target tile but mattack_actors do not",
                "attacks silently return false with no miss message or log entry",
                "incomplete coverage — other mattack_actors left unpatched",
                "no symmetric fix for surface attacker vs submerged target",
                "no automated tests added — regression risk",
            ],
            "expected_tools": [
                "get_pull_request",
                "get_pull_request_files",
                "get_pull_request_comments",
                "get_file_contents",
                "search_code",
                "submit_unit_tests",
            ],
            "min_components": 3,
            "expect_gitnexus": False,
        },
    },
]


if __name__ == "__main__":
    print("Creating LangSmith datasets...")
    _upsert_dataset(
        "qlankr-eval-indexed",
        "Qlankr PRs with GitNexus indexing — tests full pipeline (GitHub + GitNexus MCP)",
        INDEXED_EXAMPLES,
    )
    _upsert_dataset(
        "qlankr-eval-github",
        "External repo PRs without indexing — tests GitHub-only fallback path",
        GITHUB_ONLY_EXAMPLES,
    )
    print("Done.")
