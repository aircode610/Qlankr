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


# ── Dataset 3: Bug reproduction examples (Sprint 3) ──────────────────────────
# Each example has a real bug description + ground truth root cause, affected
# files, and components so evaluators can measure pipeline accuracy.

BUG_EXAMPLES = [
    # ── 1 ── OpenTTD: UI crash — timetable widget layout assertion ────────────
    {
        "_category": "UI crash — widget layout assertion",
        "inputs": {
            "description": (
                'After disabling "Show arrival and departure date on timetable" in '
                "Settings → Interface → Timetable settings, opening any vehicle's "
                'timetable window causes an immediate crash with assertion failure: '
                '"cur_height < max_smallest" at widget.cpp line 1578 inside '
                "NWidgetHorizontal::SetupSmallestSize(). Reproducible 100% on a "
                "fresh game with no mods. Reverting the setting prevents the crash."
            ),
            "environment": "Windows 11, openttd-15.0-beta3",
            "severity_input": "high",
            "repo_name": "OpenTTD",
        },
        "outputs": {
            "expected_root_cause_keywords": [
                "fallthrough",
                "UpdateWidgetSize",
                "UpdateSelectionStates",
                "FinishInitNested",
                "SetDisplayedPlane",
            ],
            "expected_affected_files": [
                "src/timetable_gui.cpp",
                "src/widget.cpp",
            ],
            "expected_affected_components": [
                "TimetableWindow",
                "NWidgetHorizontal",
                "UpdateSelectionStates",
            ],
            "expected_severity": "high",
            "expected_category": "crash",
            "min_reproduction_steps": 3,
        },
    },

    # ── 2 ── osu! — Editor: collection mutation during enumeration ────────────
    # Real issue: https://github.com/ppy/osu/issues/18527
    {
        "_category": "editor crash — collection mutation during enumeration",
        "inputs": {
            "description": (
                "In the osu!(lazer) beatmap editor, opening the Timing screen "
                "and attempting to add a new control point crashes the game to "
                "desktop with an unhandled System.InvalidOperationException: "
                "'Collection was modified; enumeration operation may not execute.' "
                "The crash originates in TimingScreen.ControlPointList.addNew() "
                "at TimingScreen.cs line 194 inside a List<T>.Enumerator.MoveNext() "
                "call. Steps: (1) Open any beatmap in the editor. "
                "(2) Navigate to the Timing screen. "
                "(3) Select the first timing point in the list. "
                "(4) Select any effect control point. "
                "(5) Click the Add button. Game crashes immediately."
            ),
            "environment": "osu!lazer 5adbf85 (2022-06-02), Linux/Windows",
            "severity_input": "medium",
            "repo_name": "ppy/osu",
        },
        "outputs": {
            "expected_root_cause_keywords": [
                "addNew",
                "List enumeration",
                "collection modified",
                "ControlPointList",
                "TimingScreen",
            ],
            "expected_affected_files": [
                "osu.Game/Screens/Edit/Timing/TimingScreen.cs",
            ],
            "expected_affected_components": [
                "TimingScreen",
                "ControlPointList",
                "BeatmapEditor",
            ],
            "expected_severity": "medium",
            "expected_category": "crash",
            "min_reproduction_steps": 4,
        },
    },

    # ── 3 ── OpenTTD — Vehicle cloning: pool assertion on stale order station ─
    # Real issue: https://github.com/OpenTTD/OpenTTD/issues/10223
    {
        "_category": "data-integrity crash — pool assertion on deleted station order",
        "inputs": {
            "description": (
                "Cloning any vehicle whose order list contains a reference to a "
                "recently-deleted station crashes OpenTTD with an assertion in "
                "pool_type.hpp: 'index < this->first_unused'. "
                "The crash appears in the pool Get() accessor called from "
                "vehicle_cmd.cpp after CloneVehicle returns INVALID_VEHICLE "
                "without marking the result as failed, so the caller passes the "
                "stale index back into the pool. "
                "Steps: (1) Create a train and give it an order to stop at "
                "Station A. (2) Delete Station A. (3) Open the train list and "
                "click the Clone Vehicle button. (4) Click on the train to clone "
                "it. Game crashes immediately with a popup loop — clicking OK "
                "re-shows the same dialog and no crash log is written."
            ),
            "environment": "OpenTTD 13.0-beta2 / nightly 20221205, Windows/Linux",
            "severity_input": "high",
            "repo_name": "OpenTTD",
        },
        "outputs": {
            "expected_root_cause_keywords": [
                "CloneVehicle",
                "INVALID_VEHICLE",
                "total_cost",
                "CMD_FAILED",
                "pool_type",
                "first_unused",
            ],
            "expected_affected_files": [
                "src/vehicle_cmd.cpp",
                "src/core/pool_type.hpp",
            ],
            "expected_affected_components": [
                "Vehicle Cloning",
                "Order Management",
                "Command System",
            ],
            "expected_severity": "high",
            "expected_category": "crash",
            "min_reproduction_steps": 4,
        },
    },

    # ── 4 ── Cataclysm-DDA — Chinese locale: multi-byte string in tile ID ─────
    # Real issue: https://github.com/CleverRaven/Cataclysm-DDA/issues/78547
    {
        "_category": "encoding crash — multi-byte string in tile ID construction",
        "inputs": {
            "description": (
                "On the macOS tiles build of Cataclysm-DDA, loading or entering "
                "a map tile that contains graffiti written in Chinese (or any "
                "multi-byte UTF-8 text) crashes the game with: "
                "'Assertion failed: (sz != static_cast<size_t>(-1)), function "
                "utf8_to_wstr, file catacharset.cpp, line 350.' "
                "Root cause: cata_tiles.cpp constructs a tile ID from the "
                "graffiti string by calling remove_punctuations() in output.cpp. "
                "That function iterates the string byte-by-byte calling "
                "std::ispunct() on each byte; for multi-byte UTF-8 sequences "
                "this corrupts the string, and the downstream utf8_to_wstr() "
                "call then fails the size assertion. "
                "Steps: (1) Start a new game on macOS tiles build. "
                "(2) Find or place a graffiti tile whose text contains Chinese "
                "characters. (3) Move the character adjacent to the tile — game "
                "crashes during map rendering."
            ),
            "environment": (
                "Cataclysm-DDA experimental 2024-12-13, macOS 14 (Sonoma), tiles build"
            ),
            "severity_input": "high",
            "repo_name": "CleverRaven/Cataclysm-DDA",
        },
        "outputs": {
            "expected_root_cause_keywords": [
                "remove_punctuations",
                "ispunct",
                "multi-byte",
                "utf8_to_wstr",
                "tile_id",
                "cata_tiles",
            ],
            "expected_affected_files": [
                "src/cata_tiles.cpp",
                "src/output.cpp",
                "src/catacharset.cpp",
            ],
            "expected_affected_components": [
                "Tile Renderer",
                "String / Charset Utilities",
                "Graffiti Rendering",
            ],
            "expected_severity": "high",
            "expected_category": "crash",
            "min_reproduction_steps": 3,
        },
    },

    # ── 5 ── Cataclysm-DDA — Faction manager: null deref on vehicle examine ───
    # Real issue: https://github.com/CleverRaven/Cataclysm-DDA/issues/80567
    {
        "_category": "null-pointer crash — faction lookup when examining vehicle",
        "inputs": {
            "description": (
                "Examining an APC (or other faction-owned vehicle) in "
                "Cataclysm-DDA crashes the game with a segfault inside "
                "faction_manager::get(const faction_id &id, const bool complain). "
                "The crash trace shows the loop over faction_manager's internal "
                "vector finds no matching faction_id and falls off the end, "
                "returning a reference to a null/garbage faction object which is "
                "then dereferenced by the vehicle inspection UI. "
                "Steps: (1) Start or load a save that has military vehicles "
                "spawned on the map. (2) Locate an APC or military truck. "
                "(3) Move one step adjacent to the APC. "
                "(4) Press 'e' (examine) on the APC tile. "
                "Game crashes immediately with signal 11 / segfault."
            ),
            "environment": (
                "Cataclysm-DDA experimental 2024-11-13 (76de484), Windows 10 22H2, tiles"
            ),
            "severity_input": "high",
            "repo_name": "CleverRaven/Cataclysm-DDA",
        },
        "outputs": {
            "expected_root_cause_keywords": [
                "faction_manager::get",
                "faction_id",
                "null faction",
                "vehicle examine",
                "faction_no_faction",
            ],
            "expected_affected_files": [
                "src/faction.cpp",
                "src/vehicle.cpp",
            ],
            "expected_affected_components": [
                "Faction Manager",
                "Vehicle Examination",
                "Map Interaction",
            ],
            "expected_severity": "high",
            "expected_category": "crash",
            "min_reproduction_steps": 4,
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
    _upsert_dataset(
        "qlankr-eval-bugs",
        "Bug descriptions with ground truth root cause — tests Sprint 3 bug reproduction pipeline",
        BUG_EXAMPLES,
    )
    print("Done.")
