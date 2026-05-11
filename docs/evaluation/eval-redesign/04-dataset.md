# Dataset Expansion

Two new LangSmith datasets for bug reproduction. Kept separate so real vs. synthetic scores are readable independently.

Existing PR analysis datasets (`qlankr-eval-indexed`, `qlankr-eval-github`) are unchanged — Approach C (calibration-first) fixes judges before adding more signal.

---

## `qlankr-eval-bugs-real` — 6 Examples

All sourced from **closed issues with a linked fix PR**. Ground truth is verified against the fix diff, not inferred.

---

### Example 1 — OpenTTD: UI Crash (existing, keep)

**Category:** UI crash — widget layout assertion
**Repo:** OpenTTD
**Why kept:** Only existing example. Solid ground truth. Good baseline.

```python
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
```

---

### Example 2 — OpenTTD: Savegame Corruption

**Category:** Data corruption across save/load + game system boundary
**Why useful:** Tests cross-subsystem detection — touches `saveload/` and a game-logic system.

```python
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
```

---

### Example 3 — Cataclysm-DDA: Gameplay Logic Crash

**Category:** Gameplay crash — flat directory, semantic component inference required
**Why useful:** `src/` is entirely flat — no subdirectories. Agent must infer component from filename and content, not path structure.

```python
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
```

---

### Example 4 — Cataclysm-DDA: Vehicle System Data Bug

**Category:** Data bug — bot-labeled `Vehicles`, verifiable against ground truth tags
**Why useful:** Well-labeled by the bot auto-tagger, making component verification deterministic.

```python
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
```

---

### Example 5 — osu!: UI Regression Across .NET Project Boundary

**Category:** UI regression — cross-project impact in .NET solution
**Why useful:** Tests whether agent understands `.NET` project references as component boundaries.

```python
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
```

---

### Example 6 — Luanti: Cross-Layer Bug (C++ Bindings + Lua)

**Category:** Cross-layer crash — C++ engine + Lua scripting boundary
**Why useful:** Hardest example. Bug traces from Lua game logic (`builtin/`) through C++ Lua bindings (`src/script/`) into the engine. Tests multi-layer call chain detection.

```python
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
```

---

## `qlankr-eval-bugs-synthetic` — 6 Adversarial Examples

Crafted to stress-test specific pipeline failure modes. None of these exist in any real repo — no LLM has been trained on the answers.

---

### Synthetic 1 — "Misleading Stack Trace"

**Stresses:** Mechanics stage — does the agent trace upstream from crash site to real cause?

```python
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
    # Root cause is in zone_transition which sets a negative size before calling Allocate.
},
```

---

### Synthetic 2 — "Buried Prerequisites"

**Stresses:** Reproduction plan stage — does the agent surface all 4 hidden conditions?

```python
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
    # Key: reproduction plan must include ALL FOUR conditions:
    # hard difficulty + two-handed sword + <25% health + Drowned Knight enemy + underwater
    # A plan missing any of these will not reliably reproduce the crash.
},
```

---

### Synthetic 3 — "Intermittent Race Condition"

**Stresses:** Triage (correct category) + Reproduction (must not fake deterministic steps)

```python
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
    # Key: reproduction plan must NOT have deterministic click-by-click steps.
    # It should describe a stress-test approach (10+ players, run for N minutes)
    # and acknowledge non-determinism. A plan saying "step 3: crash occurs" is wrong.
},
```

---

### Synthetic 4 — "Upstream Cause, Downstream Crash"

**Stresses:** Component detection — does the agent identify both the save system AND the renderer?

```python
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
    # Key: the root cause is in saveload.cpp (writes a corrupt entity list).
    # The crash site is RenderScene. Agent must identify saveload as the root cause,
    # not just the renderer as the affected component.
},
```

---

### Synthetic 5 — "Silent Data Corruption"

**Stresses:** Triage categorization (data, not crash) + severity assessment (medium, not critical)

```python
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
    # Key: agent must classify as "data" not "crash" or "UI".
    # Severity must be "medium" — no crash, gameplay continues, just wrong display.
    # A "critical" or "crash" classification is incorrect.
},
```

---

### Synthetic 6 — "Config-Dependent Trigger Buried in Prose"

**Stresses:** Mechanics + reproduction — does the agent find the LOD flag buried in the description?

```python
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
    # Key: the trigger is ultra graphics quality setting + 200+ entities on screen.
    # The root cause is the LOD culling system incorrectly suppressing minimap events.
    # A reproduction plan that doesn't include "ultra graphics" and "200+ NPCs" as
    # prerequisites will not reliably reproduce the issue.
},
```

---

## Summary

| Dataset | Examples | Ground Truth Source |
|---|---|---|
| `qlankr-eval-bugs-real` | 6 | Closed issues + fix PRs from OpenTTD, Cataclysm-DDA, osu!, Luanti |
| `qlankr-eval-bugs-synthetic` | 6 | Hand-crafted, each targeting a specific pipeline failure mode |
| `qlankr-eval-github` | 7 (existing) | Human-curated from OpenTTD, osu!, Cataclysm-DDA PRs |
| `qlankr-eval-indexed` | 1 (existing) | Qlankr repo with GitNexus indexing |
