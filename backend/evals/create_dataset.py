"""
Create the golden eval datasets in LangSmith.

Dataset groups:
  - "qlankr-eval-indexed"        → Qlankr repo (pre-indexed in GitNexus, full pipeline)
  - "qlankr-eval-github"         → External repos (no indexing, GitHub-only fallback)
  - "qlankr-eval-bugs-real"      → 6 real bug examples from closed issues + fix PRs
  - "qlankr-eval-bugs-synthetic" → 6 adversarial synthetic examples

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


# ── Dataset 4: Real bugs — 6 examples from closed issues with fix PRs ────────
# Ground truth verified against the fix diff, not inferred.

REAL_BUG_EXAMPLES = [
    # ── 1 ── OpenTTD: UI crash — timetable widget layout assertion (existing) ───
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
                "fallthrough", "UpdateWidgetSize", "UpdateSelectionStates",
                "FinishInitNested", "SetDisplayedPlane",
            ],
            "expected_affected_files": ["src/timetable_gui.cpp", "src/widget.cpp"],
            "expected_affected_components": ["TimetableWindow", "NWidgetHorizontal", "UpdateSelectionStates"],
            "expected_severity": "high",
            "expected_category": "crash",
            "min_reproduction_steps": 3,
        },
    },
    # ── 2 ── OpenTTD: Savegame Corruption — waypoint orders silently dropped ───
    {
        "_category": "Data corruption across save/load + game system boundary",
        "inputs": {
            "description": (
                "After loading a savegame created in OpenTTD 14.x into 15.0, all vehicle orders "
                "pointing to waypoints are silently dropped. Affected vehicles show 'No Orders' "
                "and begin driving to depot. The save loads without error or warning. "
                "Re-saving in 15.0 permanently loses the original orders."
            ),
            "environment": "Linux, openttd-15.0-rc1, savegame from 14.1",
            "severity_input": "high",
            "repo_name": "OpenTTD",
        },
        "outputs": {
            "expected_root_cause_keywords": [
                "waypoint", "order", "savegame version", "SLV", "migration", "OWNER",
            ],
            "expected_affected_files": ["src/saveload/order_sl.cpp", "src/order_cmd.cpp"],
            "expected_affected_components": ["Order Management", "Save/Load System"],
            "expected_severity": "high",
            "expected_category": "data",
            "min_reproduction_steps": 3,
        },
    },
    # ── 3 ── Cataclysm-DDA: Gameplay crash — powered exoskeleton + encumbrance ─
    {
        "_category": "Gameplay crash — flat directory, semantic component inference required",
        "inputs": {
            "description": (
                "Game crashes with a segfault when a player character wearing a powered exoskeleton "
                "attempts to pick up an item while encumbrance is above 100. Crash does not occur "
                "without the exoskeleton or at lower encumbrance values. Stack trace points to "
                "character.cpp inside the item pickup handler. Reproducible in latest experimental build."
            ),
            "environment": "Linux, Cataclysm-DDA experimental 2024-11, tiles build",
            "severity_input": "high",
            "repo_name": "Cataclysm-DDA",
        },
        "outputs": {
            "expected_root_cause_keywords": [
                "encumbrance", "exoskeleton", "pickup", "null", "armor encumbrance",
            ],
            "expected_affected_files": ["src/character.cpp", "src/item_pickup.cpp"],
            "expected_affected_components": ["Character", "Item Pickup", "Encumbrance System"],
            "expected_severity": "high",
            "expected_category": "crash",
            "min_reproduction_steps": 4,
        },
    },
    # ── 4 ── Cataclysm-DDA: Vehicle system data bug — engine fuel consumption reset
    {
        "_category": "Data bug — bot-labeled Vehicles, verifiable against ground truth tags",
        "inputs": {
            "description": (
                "Attaching a second engine to a vehicle causes the first engine's fuel consumption "
                "to reset to default values, ignoring any upgrades applied to it. This happens "
                "silently — no message is shown. The bug persists after saving and reloading. "
                "Removing and re-adding the first engine does not restore the original stats."
            ),
            "environment": "Windows 10, Cataclysm-DDA 0.G stable",
            "severity_input": "medium",
            "repo_name": "Cataclysm-DDA",
        },
        "outputs": {
            "expected_root_cause_keywords": [
                "engine", "fuel consumption", "install", "vehicle_part", "reset", "copy",
            ],
            "expected_affected_files": ["src/vehicle.cpp", "src/vehicle_part.cpp"],
            "expected_affected_components": ["Vehicle System", "Vehicle Part Installation"],
            "expected_severity": "medium",
            "expected_category": "gameplay",
            "min_reproduction_steps": 4,
        },
    },
    # ── 5 ── osu!: UI Regression — leaderboard not updating after beatmap selection
    {
        "_category": "UI regression — cross-project impact in .NET solution",
        "inputs": {
            "description": (
                "After the recent beatmap carousel refactor, clicking a beatmap in the song select "
                "screen no longer updates the score leaderboard panel — it continues showing scores "
                "for the previously selected beatmap. The bindable that drives leaderboard loading "
                "is not updated when selection changes. Issue introduced in the SongSelectV2 branch."
            ),
            "environment": "osu! development build, .NET 8, Windows 11",
            "severity_input": "high",
            "repo_name": "osu",
        },
        "outputs": {
            "expected_root_cause_keywords": [
                "bindable", "leaderboard", "selection", "BeatmapCarousel", "SongSelectV2",
                "working beatmap",
            ],
            "expected_affected_files": [
                "osu.Game/Screens/Select/SongSelect.cs",
                "osu.Game/Screens/Select/BeatmapCarousel.cs",
                "osu.Game/Overlays/BeatmapSet/Scores/ScoresContainer.cs",
            ],
            "expected_affected_components": ["SongSelectV2", "BeatmapLeaderboard", "BeatmapCarouselV2"],
            "expected_severity": "high",
            "expected_category": "UI",
            "min_reproduction_steps": 3,
        },
    },
    # ── 6 ── Luanti: Cross-layer crash — C++ bindings + Lua scripting boundary ──
    {
        "_category": "Cross-layer crash — C++ engine + Lua scripting boundary",
        "inputs": {
            "description": (
                "Server crashes with 'Invalid use of nil value' when a Lua mod calls "
                "minetest.get_node_light() on a position that was recently unloaded from memory. "
                "The crash occurs inside the C++ binding layer, not in Lua itself. "
                "The issue is intermittent — it depends on chunk loading timing and only appears "
                "on servers with many active players causing frequent map load/unload cycles."
            ),
            "environment": "Luanti 5.9.0, Linux server, 20+ player load",
            "severity_input": "high",
            "repo_name": "luanti",
        },
        "outputs": {
            "expected_root_cause_keywords": [
                "get_node_light", "nil", "unloaded", "map block", "binding", "script",
                "checkarea", "emergeblock",
            ],
            "expected_affected_files": [
                "src/script/lua_api/l_env.cpp",
                "src/map.cpp",
                "builtin/game/misc.lua",
            ],
            "expected_affected_components": ["Lua API Bindings", "Map Block Management", "Server Environment"],
            "expected_severity": "high",
            "expected_category": "crash",
            "min_reproduction_steps": 4,
        },
    },
]


# ── Dataset 5: Synthetic adversarial bugs — 6 examples ───────────────────────
# Crafted to stress-test specific pipeline failure modes.
# None of these exist in any real repo — no LLM has been trained on the answers.

SYNTHETIC_BUG_EXAMPLES = [
    # ── Synthetic 1 ── Misleading Stack Trace ─────────────────────────────────
    {
        "_category": "Misleading stack trace — crash site ≠ root cause",
        "inputs": {
            "description": (
                "Game crashes in MemoryPool::Allocate() when the inventory screen is opened "
                "after fast-travelling to a new zone. Stack trace: "
                "MemoryPool::Allocate() ← ItemRenderer::RebuildCache() ← InventoryScreen::Show(). "
                "The crash only occurs after fast travel, not when opening inventory from the main hub."
            ),
            "environment": "Windows 10, game v2.4.1",
            "severity_input": "high",
            "repo_name": "synthetic",
        },
        "outputs": {
            "expected_root_cause_keywords": [
                "fast travel", "zone transition", "negative size", "underflow",
                "ItemRenderer", "caller",
            ],
            "expected_affected_files": ["src/zone_transition.cpp", "src/item_renderer.cpp"],
            "expected_affected_components": ["Zone Transition System", "ItemRenderer", "MemoryPool"],
            "expected_severity": "high",
            "expected_category": "crash",
            "min_reproduction_steps": 3,
            # Key: agent should NOT identify MemoryPool as the root cause — it is the crash site.
        },
    },
    # ── Synthetic 2 ── Buried Prerequisites ───────────────────────────────────
    {
        "_category": "Buried prerequisites — 4 conditions must all be present",
        "inputs": {
            "description": (
                "The game crashes when attacking enemies. I'm playing on hard difficulty with a "
                "two-handed sword. It seems to happen more when I'm low on health — maybe below "
                "25%? The enemy was a Drowned Knight specifically, not regular enemies. "
                "It happens underwater but I haven't tested on land."
            ),
            "environment": "Linux, game v1.8.0",
            "severity_input": "high",
            "repo_name": "synthetic",
        },
        "outputs": {
            "expected_root_cause_keywords": [
                "underwater", "melee", "two-handed", "health threshold", "Drowned Knight",
                "attack", "hard difficulty",
            ],
            "expected_affected_files": ["src/combat.cpp", "src/enemy_drowned_knight.cpp"],
            "expected_affected_components": ["Combat System", "Enemy AI", "Underwater Physics"],
            "expected_severity": "high",
            "expected_category": "crash",
            "min_reproduction_steps": 5,
            # Key: ALL FOUR conditions must be in reproduction plan:
            # hard difficulty + two-handed sword + <25% health + Drowned Knight + underwater
        },
    },
    # ── Synthetic 3 ── Intermittent Race Condition ────────────────────────────
    {
        "_category": "Intermittent race condition — non-deterministic reproduction",
        "inputs": {
            "description": (
                "Every few minutes during multiplayer sessions, all clients simultaneously lose "
                "connection and are dropped to the main menu. The server log shows no error — "
                "it continues running and new clients can connect immediately after. "
                "The issue happens more often with 10+ players. Single-player is unaffected."
            ),
            "environment": "Dedicated server, Linux, game v3.1.2, 10-16 players",
            "severity_input": "critical",
            "repo_name": "synthetic",
        },
        "outputs": {
            "expected_root_cause_keywords": [
                "thread", "race", "mutex", "lock", "shared state",
                "session", "concurrent", "network manager",
            ],
            "expected_affected_files": ["src/network_manager.cpp", "src/session.cpp"],
            "expected_affected_components": ["Network Manager", "Session State", "Client Connection Handler"],
            "expected_severity": "critical",
            "expected_category": "networking",
            "min_reproduction_steps": 3,
            # Key: reproduction plan must NOT have deterministic steps; must acknowledge non-determinism
        },
    },
    # ── Synthetic 4 ── Upstream Cause, Downstream Crash ──────────────────────
    {
        "_category": "Upstream cause downstream crash — both save system AND renderer affected",
        "inputs": {
            "description": (
                "The game crashes in the rendering system after loading a save file. "
                "Stack trace: RenderScene::DrawEntities() → EntityManager::GetVisible() → nullptr dereference. "
                "The crash happens immediately after the loading screen completes. "
                "Creating a new game and playing works fine. Only loading saves triggers it."
            ),
            "environment": "Windows 11, game v4.0.0",
            "severity_input": "critical",
            "repo_name": "synthetic",
        },
        "outputs": {
            "expected_root_cause_keywords": [
                "save", "load", "corrupt", "entity", "null pointer",
                "migration", "EntityManager", "RenderScene",
            ],
            "expected_affected_files": ["src/saveload.cpp", "src/entity_manager.cpp", "src/render_scene.cpp"],
            "expected_affected_components": ["Save/Load System", "Entity Manager", "Renderer"],
            "expected_severity": "critical",
            "expected_category": "crash",
            "min_reproduction_steps": 3,
            # Key: root cause is in saveload.cpp; crash site is RenderScene
        },
    },
    # ── Synthetic 5 ── Silent Data Corruption ─────────────────────────────────
    {
        "_category": "Silent data corruption — display only, no crash, medium severity",
        "inputs": {
            "description": (
                "After loading a save from version 1.5 into version 1.6, all item sell prices "
                "in the shop UI display as 0. Items can still be sold at the correct price — "
                "only the displayed value is wrong. The issue only appears for saves from 1.5; "
                "new games in 1.6 show correct prices. No error is shown. No crash."
            ),
            "environment": "Windows 10, game v1.6.0, save from v1.5.3",
            "severity_input": "medium",
            "repo_name": "synthetic",
        },
        "outputs": {
            "expected_root_cause_keywords": [
                "migration", "save version", "field missing", "default value",
                "price", "display", "shop", "1.5", "1.6",
            ],
            "expected_affected_files": ["src/save_migration.cpp", "src/shop_ui.cpp"],
            "expected_affected_components": ["Save Migration", "Shop UI", "Item Pricing"],
            "expected_severity": "medium",
            "expected_category": "data",
            "min_reproduction_steps": 3,
            # Key: must classify as "data" not "crash" or "UI"; severity must be "medium"
        },
    },
    # ── Synthetic 6 ── Config-Dependent Trigger Buried in Prose ──────────────
    {
        "_category": "Config-dependent trigger buried in prose — LOD flag + 200+ NPCs",
        "inputs": {
            "description": (
                "The minimap stops updating after playing for about 10-15 minutes. "
                "It just freezes on whatever it last showed. Restarting the game fixes it until "
                "it happens again. I'm running on ultra graphics settings by the way. "
                "It seems worse when there's a lot going on — like in the city areas with "
                "200+ NPCs. Turning down graphics settings to high seems to stop it happening."
            ),
            "environment": "Windows 11, game v2.8.0, RTX 3080, ultra graphics",
            "severity_input": "medium",
            "repo_name": "synthetic",
        },
        "outputs": {
            "expected_root_cause_keywords": [
                "LOD", "culling", "event", "suppress", "graphics setting",
                "ultra", "minimap", "update",
            ],
            "expected_affected_files": ["src/lod_manager.cpp", "src/minimap.cpp"],
            "expected_affected_components": ["LOD Manager", "Minimap", "Graphics Settings"],
            "expected_severity": "medium",
            "expected_category": "gameplay",
            "min_reproduction_steps": 4,
            # Key: trigger is ultra graphics + 200+ entities; root cause is LOD culling suppressing minimap events
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
    _upsert_dataset(
        "qlankr-eval-bugs-real",
        "6 real bug examples from closed issues + fix PRs (OpenTTD, Cataclysm-DDA, osu!, Luanti)",
        REAL_BUG_EXAMPLES,
    )
    _upsert_dataset(
        "qlankr-eval-bugs-synthetic",
        "6 adversarial synthetic bugs targeting specific pipeline failure modes",
        SYNTHETIC_BUG_EXAMPLES,
    )
    print("Done.")
