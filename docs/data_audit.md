# Data Audit

The project already uses a real public-data snapshot for the main demo dataset, but the final Mod/plugin target requires stricter provenance and coverage checks.

## Current Snapshot

`data/public_full_data.json` currently contains:

- 361 cards
- 146 relics
- 42 potions
- 57 enemy entries covering monsters, elites, and bosses
- 25 mechanics/risk nodes
- 3 shop actions
- 5 path node types

Cards, relics, potions, and enemies currently include public source fields such as `source`, `source_url`, and `confidence`.

Mechanics, classes, shop actions, and path nodes are internal normalized support entities. They are labeled as `derived` or `system` by `scripts/normalize_provenance.py`.

## Run the Audit

Coverage against practical Mod MVP targets:

```powershell
.\.venv\Scripts\python.exe scripts\data_coverage_report.py --data data\public_full_data.json
```

Provenance coverage:

```powershell
.\.venv\Scripts\python.exe scripts\data_provenance_report.py --data data\public_full_data.json
```

Machine-readable output:

```powershell
.\.venv\Scripts\python.exe scripts\data_provenance_report.py --data data\public_full_data.json --json
```

## What the Report Means

`data_coverage_report.py` answers whether the dataset is broad enough for the Mod MVP.

`data_provenance_report.py` answers whether the existing entities are traceable.

- `source` coverage tells whether an entity has a named source.
- `source_url` coverage tells whether the entity can be traced to a concrete page or artifact.
- `confidence` coverage tells whether the importer marked extraction confidence.
- `patch_version` and `version` coverage identify whether entities carry version metadata.
- `relationships.missing_evidence_pct` identifies graph edges that are useful but not yet individually sourced.

## Final Data Standard

For portfolio or release claims, the final dataset should meet this standard:

- Raw game entities have `id`, `name`, `source`, `source_url`, `confidence`, and version metadata.
- Derived entities are explicitly marked as `source: derived` or `source: system`.
- Curated strategy rules are stored separately from raw game facts.
- Graph relationships that represent strategy judgments include either source evidence or a curated-rule marker.
- Data validation fails on duplicate IDs, missing required fields, and broken relationship targets.

## Known Gaps

- Enemy coverage is close to the current Mod MVP target, but a few minions/summons and encounter variants may still need live-game validation.
- Events are not yet represented as a first-class collection.
- Individual relationships now have derived provenance markers, but they are not yet field-level citations back to exact wiki lines.
- Real Mod payload names still need live-game validation against the normalized IDs.
