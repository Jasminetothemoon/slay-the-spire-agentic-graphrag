# Captured Payload Import Report

This report summarizes machine-seeded eval candidates generated from Java Mod JSONL payloads.

Important: imported cases are marked `machine_seeded_needs_human_review`. They should be reviewed before being merged into `data/public_eval_cases.json`.

- Output candidate file: `data/captured_eval_candidates.json`
- Input files: `data/mod_payload_replay_sample.jsonl`
- Raw records: 1
- Imported eval candidates: 1
- Skipped records: 0

## Coverage

| Query Type | Candidates |
| --- | ---: |
| card_pick | 1 |

## Screens

| Screen | Candidates |
| --- | ---: |
| CARD_REWARD | 1 |

## Quality Flags

| Flag | Count |
| --- | ---: |
| low_top_separation | 1 |

## Review Priority

| Priority | Count |
| --- | ---: |
| high | 1 |

## Next Review Steps

1. Open the generated candidate JSON.
2. For each case, inspect `metadata.replay_top`, `score_gap`, `quality_flags`, and `top_reasons`.
3. Change `label_status` to `human_labeled` after review.
4. Adjust `expected_top` and `acceptable` if the machine-seeded recommendation is not the human label.
5. Merge reviewed cases into the fixed eval set or keep them as a separate real-payload eval file.

## Sample Case IDs

- `captured_capture_replay_sample_card_reward_card_pick_1760000000000_1_1`