import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MOD_DIR = ROOT / "mod-bridge"


REQUIRED_FILES = [
    "settings.gradle",
    "build.gradle",
    "src/main/resources/ModTheSpire.json",
    "src/main/java/com/stsagent/bridge/StsAgentBridgeMod.java",
    "src/main/java/com/stsagent/bridge/BridgeClient.java",
    "src/main/java/com/stsagent/bridge/BridgeCaptureLogger.java",
    "src/main/java/com/stsagent/bridge/BridgeConfig.java",
    "src/main/java/com/stsagent/bridge/BridgePayload.java",
    "src/main/java/com/stsagent/bridge/GameStateCollector.java",
    "src/main/java/com/stsagent/bridge/InGameRecommendationPanel.java",
    "src/main/java/com/stsagent/bridge/JsonUtil.java",
    "src/main/java/com/stsagent/bridge/RecommendationParser.java",
    "src/main/java/com/stsagent/bridge/RecommendationResult.java",
    "libs/README.md",
]

REQUIRED_PROJECT_FILES = [
    "scripts/build_mod_bridge.ps1",
    "scripts/replay_mod_payloads.py",
    "data/mod_payload_replay_sample.jsonl",
]


def assert_contains(path: Path, needles: list[str]) -> None:
    text = path.read_text(encoding="utf-8")
    missing = [needle for needle in needles if needle not in text]
    if missing:
        raise AssertionError(f"{path} missing required text: {missing}")


def main() -> None:
    missing = [rel for rel in REQUIRED_FILES if not (MOD_DIR / rel).exists()]
    missing.extend(rel for rel in REQUIRED_PROJECT_FILES if not (ROOT / rel).exists())
    if missing:
        raise AssertionError(f"Missing Mod bridge files: {missing}")

    manifest_path = MOD_DIR / "src/main/resources/ModTheSpire.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    for field in ["modid", "name", "author_list", "description", "version", "dependencies"]:
        if field not in manifest:
            raise AssertionError(f"ModTheSpire.json missing {field}")
    if "basemod" not in manifest["dependencies"]:
        raise AssertionError("ModTheSpire.json must depend on basemod")

    assert_contains(
        MOD_DIR / "src/main/java/com/stsagent/bridge/BridgeClient.java",
        ["/mod/state", "/mod/recommend", "HttpURLConnection", "Content-Type", "RecommendationParser.parse", "lastError"],
    )
    assert_contains(
        MOD_DIR / "src/main/java/com/stsagent/bridge/StsAgentBridgeMod.java",
        ["PostRenderSubscriber", "receivePostRender", "panel.update", "panel.updateStatus", "panel.clear", "Input.Keys.F8", "Input.Keys.F9", "Input.Keys.F10", "Input.Keys.F11", "panel.toggleDebugVisible", "panel.toggleLanguage", "collector.cyclePreferredArchetype", "captureLogger.recordRecommendation"],
    )
    assert_contains(
        MOD_DIR / "src/main/java/com/stsagent/bridge/InGameRecommendationPanel.java",
        [
            "render(SpriteBatch sb)",
            "STS Agent",
            "ImageMaster.WHITE_SQUARE_IMG",
            "RecommendationResult",
            "toggleVisible",
            "toggleDebugVisible",
            "updateStatus",
            "clear()",
            "sceneDisplayName",
            "badgeText",
            "renderCandidateBadges",
            "renderCardRewardBadges",
            "renderShopBadges",
            "renderBossRelicBadges",
            "lastBadgeUnmatched",
            "lastBadgeUnmatchedLabels",
            "shopDebug",
            "chineseVisible",
            "hoveredOption",
            "renderHoveredOptionDetail",
            "optionMetricsText",
            "InputHelper.mX",
            "STATUS_STALE_AFTER_MS",
            "latest != null",
        ],
    )
    assert_contains(
        MOD_DIR / "src/main/java/com/stsagent/bridge/BridgeCaptureLogger.java",
        ["recordRecommendation", "recordState", "jsonl", "response_summary"],
    )
    assert_contains(
        MOD_DIR / "src/main/java/com/stsagent/bridge/RecommendationParser.java",
        ["scene_type", "display_badge", "why_not", "debugSummary", "objectsInArray", "optionScores", "shop_price", "shop_affordable", "preferred_archetype"],
    )
    assert_contains(
        MOD_DIR / "src/main/java/com/stsagent/bridge/RecommendationResult.java",
        ["class OptionScore", "optionScores", "findScore", "normalizeKey", "displayBadge()"],
    )
    assert_contains(
        MOD_DIR / "src/main/java/com/stsagent/bridge/BridgeConfig.java",
        ["STS_AGENT_CAPTURE", "STS_AGENT_CAPTURE_DIR", "captureDir", "STS_AGENT_ARCHETYPE", "preferredArchetype"],
    )
    assert_contains(
        MOD_DIR / "src/main/java/com/stsagent/bridge/GameStateCollector.java",
        [
            "character_class",
            "current_screen",
            "current_floor",
            "deck",
            "relics",
            "potions",
            "hand_cards",
            "enemies",
            "map_options",
            "shop_items",
            "card_pick",
            "relic_pick",
            "shopRelicIds",
            "shopPotionIds",
            "shopItems",
            "preferred_archetype",
            "cyclePreferredArchetype",
            "preferredArchetypeLabel",
            "COMBAT_REWARD",
            "BOSS_REWARD",
            "MAP",
            "firstMapRowNodes",
            "!AbstractDungeon.isScreenUp",
            "combat",
            'options.add("Skip")',
        ],
    )
    assert_contains(MOD_DIR / "src/main/java/com/stsagent/bridge/BridgePayload.java", ["hasDecision()"])
    assert_contains(
        MOD_DIR / "build.gradle",
        ["sourceCompatibility = JavaVersion.VERSION_1_8", "compileOnly fileTree", "copyJarToMods", 'options.encoding = "UTF-8"'],
    )
    assert_contains(
        ROOT / "scripts/build_mod_bridge.ps1",
        [
            ".tools\\jdk17",
            ".tools\\gradle",
            "desktop-1.0.jar",
            "BaseMod.jar",
            "ModTheSpire.jar",
            "ModsDir",
            "Resolve-ModsDir",
            "STS_AGENT_MODS_DIR",
            "local.modsdir.txt",
            "Copy-Item",
        ],
    )

    print("Mod bridge structure checks passed.")


if __name__ == "__main__":
    main()
