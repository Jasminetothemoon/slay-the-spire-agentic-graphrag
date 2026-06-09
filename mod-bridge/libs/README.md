# Local Mod Dependencies

Place local Slay the Spire modding jars here before building the Java bridge.

Expected jars:

- `desktop-1.0.jar` or the equivalent Slay the Spire game jar.
- `ModTheSpire.jar`.
- `BaseMod.jar`.

These files are intentionally not committed because they come from the local game/mod installation.

The Gradle build uses every `*.jar` in this folder as `compileOnly`, so filenames do not need to match exactly.
