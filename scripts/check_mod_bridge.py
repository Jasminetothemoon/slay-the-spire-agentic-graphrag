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
    "src/main/java/com/stsagent/bridge/BridgeConfig.java",
    "src/main/java/com/stsagent/bridge/BridgePayload.java",
    "src/main/java/com/stsagent/bridge/GameStateCollector.java",
    "src/main/java/com/stsagent/bridge/JsonUtil.java",
    "libs/README.md",
]


def assert_contains(path: Path, needles: list[str]) -> None:
    text = path.read_text(encoding="utf-8")
    missing = [needle for needle in needles if needle not in text]
    if missing:
        raise AssertionError(f"{path} missing required text: {missing}")


def main() -> None:
    missing = [rel for rel in REQUIRED_FILES if not (MOD_DIR / rel).exists()]
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
        ["/mod/state", "/mod/recommend", "HttpURLConnection", "Content-Type"],
    )
    assert_contains(
        MOD_DIR / "src/main/java/com/stsagent/bridge/GameStateCollector.java",
        [
            "character_class",
            "current_floor",
            "deck",
            "relics",
            "potions",
            "hand_cards",
            "enemies",
            "card_pick",
            "combat",
        ],
    )
    assert_contains(
        MOD_DIR / "build.gradle",
        ["sourceCompatibility = JavaVersion.VERSION_1_8", "compileOnly fileTree", "copyJarToMods"],
    )

    print("Mod bridge structure checks passed.")


if __name__ == "__main__":
    main()
