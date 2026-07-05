## Project Context

- This is a Python pipeline project for EV vehicle simulation (~824 vehicles target scale)
- Common libraries: pandas, osmnx, geopandas — always verify imports are added when using these
- Preserve existing routing/location-selection logic when optimizing; prefer incremental changes over rewrites
- Key files: `Step_1_prod.py` (trip generation), `Dom_center.py` (visualization), `Functions_step_1.py` (helpers)

## Verification Before Claiming Fixes

- Always run the actual failing command/test after making changes to confirm the fix works before reporting success
- For pandas/numpy changes, verify with a quick repro snippet
- Check imports are added when introducing new library calls (e.g., osmnx, geopandas)
- Never mark a task done without showing the verification command output

## Scope Clarification

- Before implementing a fix, confirm whether the issue is narrow (single case) or systemic (all parking types/zones/categories)
- For data pipeline bugs, check if the same pattern exists in sibling code paths before patching just one
- Enumerate all affected code paths first, then propose narrow vs. systemic fix with reasoning

## Optimization and Refactoring

- Before changing any core logic, state the current hypothesis and proposed approach for approval
- For performance work on critical paths, benchmark first, identify the hotspot, and propose minimal targeted changes
- Do not restructure routing or location-selection logic without explicit approval
- If a refactor introduces more than one bug in sequence, stop and propose a full plan rather than continuing to patch
