# Interview playbook: a geospatial API service in 3 hours

This playbook runs a timed, 3-hour build of a Python API service with CoderPad's two built-in models: a database schema and a repeatable, audited ingestion of the provided JSON files, read-only REST endpoints, structured JSON logs, and great-circle analysis (lengths, zone passes and trajectory intersections) that is stored in the database and served by the API. Each phase gives the human-only steps, the copy-paste prompts with the model each one targets, the verification commands with their expected practice results, a recovery prompt, talking points and a commit checkpoint. Placeholders carry the practice values; on the day only those values change, and PLAN.md records them.

Contents:

- Top section
  - [How to use this playbook](#how-to-use-this-playbook)
  - [Session setup](#session-setup)
  - [Time budget](#time-budget)
  - [Model routing](#model-routing)
  - [Token rules](#token-rules)
  - [Prompt contract, kickoff header and gate](#prompt-contract-kickoff-header-and-gate)
  - [AI-use habits the grader wants to see](#ai-use-habits-the-grader-wants-to-see)
  - [Human-only steps](#human-only-steps)
  - [AI log and commit tags](#ai-log-and-commit-tags)
  - [Placeholders and PLAN.md](#placeholders-and-planmd)
  - [Conventions block](#conventions-block)
- Phases
  - [Phase 0 — Orient and plan (0–15 min)](#phase-0--orient-and-plan-015-min)
  - [Phase 1 — Project setup (15–30 min)](#phase-1--project-setup-1530-min)
  - [Phase 2 — Database models and migrations (30–48 min)](#phase-2--database-models-and-migrations-3048-min)
  - [Phase 3 — JSON ingestion (48–73 min)](#phase-3--json-ingestion-4873-min)
  - [Phase 4 — Read-only API (73–93 min)](#phase-4--read-only-api-7393-min)
  - [Phase 5 — Structured logging (93–103 min)](#phase-5--structured-logging-93103-min)
  - [Phase 6 — Geospatial analysis (103–153 min)](#phase-6--geospatial-analysis-103153-min)
  - [Phase 7 — Tests and verification (153–170 min)](#phase-7--tests-and-verification-153170-min)
- Appendices
  - [Appendix A — Reference architecture](#appendix-a--reference-architecture)
  - [Appendix B — Great-circle math cheat sheet](#appendix-b--great-circle-math-cheat-sheet)
  - [Appendix C — PostGIS contingency](#appendix-c--postgis-contingency)
  - [Appendix D — No-Postgres fallback (SQLite)](#appendix-d--no-postgres-fallback-sqlite)
  - [Appendix E — Adapting to the real brief](#appendix-e--adapting-to-the-real-brief)
  - [Appendix F — Prompting patterns and token economy](#appendix-f--prompting-patterns-and-token-economy)
  - [Appendix G — Final 5-minute demo](#appendix-g--final-5-minute-demo)

## How to use this playbook

- Work top to bottom. Each phase interleaves Human steps (no AI) with prompts, runs the gate after every prompt, and ends with Verify and a Checkpoint commit. Paste each prompt into the model it names, and run every Verify block yourself.
- Prompts carry placeholders written `<NAME=value>`, with the practice value already filled in. On the day, change only the value, using what PLAN.md records (see Placeholders and PLAN.md).
- PLAN.md is the shared memory. Phase 0 writes it; later prompts cite it as "PLAN §n" (section n of PLAN.md), so a change in the brief is one PLAN edit, not ten prompt edits.
- The playbook carries prompts, specs and tooling, not prebuilt service code: the models write the service live from these specs. Literal code appears only where it pins a verified library trap (the `NAMING` convention, `render_item`, the logging processor lists) and in human-pasted configuration (the pyproject block, `.env`, `gate`, the PLAN skeleton).
- Minutes are elapsed minutes from the session start. Tripwires and cuts are decided in advance (see Time budget).
- Every command runs from the repo root; the comment after a Verify command is its practice result. Long-running commands (pytest, alembic, `uv add`, `verify.sh`) carry a `timeout`, so a hang costs at most a few minutes. The appendices are reference material for the live session.

## Session setup

Work in one terminal at the repo root. Shell state does not carry over: in every new terminal, re-run the exports and paste `gate` again (or keep both in a file outside the repo, such as `~/session.sh`, and `source` it).

```bash
export BRIEF=INSTRUCTIONS.md DATA_DIR=data          # Human step 0.a
export SAMPLE_TRJ=FLT-1003 SAMPLE_ZONE=ZN-POLE       # Human step 0.b, ids taken from DATA_PROFILE.md
```

- `BRIEF` and `DATA_DIR` are exported in Human step 0.a, the two sample ids in Human step 0.b once DATA_PROFILE.md shows real ids. On the day, only the values change.
- Verify blocks write `"$BRIEF"`, `"$DATA_DIR"`, `"/trajectories/$SAMPLE_TRJ"` and `"/zones/$SAMPLE_ZONE"`.
- Shell variables never reach committed files, because a grader's shell does not have them. NOTES.md and README.md carry literal ids (P7.3 gets the SAMPLE_TRJ value in its prompt), and `scripts/verify.sh` defaults to its argument, then `$DATA_DIR`, then the DATA_DIR value that P7.2 writes into it.

The `gate` function, first pasted in Human step 1.a (it needs `uv` and ruff):

```bash
gate() {   # "gate lint" skips pytest: used after P2.1 and P6.3, before the human step creates the migration
  git status --short && git diff --stat
  hits=$(grep -rnE "session\.query\(|declarative_base|orm_mode|class Config:|@validator|@root_validator|parse_obj|from pydantic import BaseSettings|AsyncSession|create_async_engine|asyncpg|aiosqlite|func\.now\(\)|text\('now\(\)'\)|on_event\(|postgresql://|psycopg2|utcnow" src tests migrations scripts 2>/dev/null)
  if [ -n "$hits" ]; then printf '%s\n' "$hits"; echo "FORBIDDEN API FOUND"; else echo "conventions grep clean"; fi
  uv run ruff format -q . && uv run ruff check --fix -q . || return 1
  [ "${1:-}" = lint ] || timeout 120 uv run pytest -q -x 2>&1 | tail -n 15
}
```

- `gate` runs the scope check (`git status`, `git diff --stat`), the forbidden-API grep, `ruff format` plus `ruff check --fix`, then the last 15 lines of pytest, stopped after 120 s if it hangs. `gate lint` skips pytest.
- The grep result is captured, not tested by exit status. GNU grep exits 2 when a listed directory is missing (`migrations/` until Human step 2.a), even after printing a match, so `&& … || echo clean` would report "clean" over a forbidden API.
- When and how to run it: see Prompt contract, kickoff header and gate.

## Time budget

### Phases (sum: 180 minutes)

| Phase | Title | Start–end | Min | Steps inside the phase (H = human, no AI) |
|---|---|---|---|---|
| 0 | Orient and plan | 0–15 | 15 | H0.a env check, read brief (0–5) · P0.1 S profiler (5–8) · H0.b landmark check + PLAN skeleton (8–10) · P0.2 L PLAN.md (10–13) · review + checkpoint (13–15) |
| 1 | Project setup | 15–30 | 15 | H1.a uv init/add, pyproject block, `.env` (15–19) · P1.1 S skeleton (19–27) · verify + checkpoint (27–30) |
| 2 | Database models and migrations | 30–48 | 18 | H2.a alembic init (30–31) · P2.1 L models, env.py, conftest, migration tests; `gate lint` (31–40) · H2.b autogenerate 0001, ruff format, review, full gate + commit (40–46) · verify + checkpoint (46–48) |
| 3 | JSON ingestion | 48–73 | 25 | P3.1 L records + unit tests (48–58) · P3.2 L service, CLI, DB tests (58–70) · verify + checkpoint (70–73) |
| 4 | Read-only API | 73–93 | 20 | P4.1 L trajectories pattern (73–84) · P4.2 S zones copy (84–90) · verify + checkpoint (90–93) |
| 5 | Structured logging | 93–103 | 10 | P5.1 S logging + middleware + tests (93–100) · verify + checkpoint (100–103) |
| 6 | Geospatial analysis | 103–153 | 50 | P6.1 L geodesy + analytic tests (103–118) · P6.2 S oracle tests (118–124) · P6.3 S analysis models; `gate lint` (124–127) · H6.a autogenerate 0002, ruff format, review, full gate + commit (127–131) · P6.4 L runner + CLI + tests (131–143) · P6.5 L API exposure (143–151) · verify + checkpoint (151–153) |
| 7 | Tests and verification | 153–170 | 17 | P7.1 S check_invariants.py (153–157) · P7.2 S smoke.py + verify.sh; the human's `verify.sh` run is saved for P7.3 (157–163) · P7.3 S README + NOTES from that saved output (163–167) · verify.sh + checkpoint (167–170) |
| — | Buffer | 170–180 | 10 | Final `verify.sh`, demo rehearsal (see Appendix G — Final 5-minute demo), push. Spend it only after 170; earlier overruns trigger tripwires or cuts, not buffer. P7.4 (optional review) is not scheduled: it runs only on time saved earlier |

Check: 15 + 15 + 18 + 25 + 20 + 10 + 50 + 17 + 10 = 180. Phase 6 gets 50 minutes because it is the graded differentiator and the main source of silent bugs. Its five gate commits group as 6a math (P6.1, P6.2), 6b persistence (P6.3 committed with H6.a, then P6.4) and 6c API (P6.5).

### Tripwires (check at the minute; if it fails, act immediately, without debugging)

| Min | Check | Action if it fails |
|---|---|---|
| 10 | Postgres reachable with the brief's credentials | Use SQLite now: two `.env` lines (see Appendix D — No-Postgres fallback (SQLite)) |
| 15 | PLAN.md committed | Commit it as is; park doubts in PLAN §10 |
| 27 | **SQLite switch:** `/health` reports `"database":"ok"` | Write the SQLite `.env` lines; rerun Verify 1 |
| 47 | 0001 applied and `alembic check` clean (H2.b is scheduled to end at 46) | Hand-fix the file using the review checklist of Human step 2.b (it is usually item 2 or 5); defer `test_round_trip` |
| 58 | **Full-refresh decision**, before sending P3.2: P3.1 green (`tests/test_records.py` 16 passed) | Send P3.2 in its full-refresh variant (cut 8) |
| 73 | Second run is a no-op (inserted 0, updated 0) and stores no duplicate rows | Duplicate rows or a failed run: send Verify 3's "If it fails" prompt. Otherwise (for example `updated 20`) ship it, apply cut 8's "Also change" lines to `verify.sh` and NOTES, and note it in NOTES "Known limitations" |
| 90 | Trajectory list/detail/404/422 tests green | Skip P4.2 (zone endpoints; zone passes still show in trajectory detail). Also remove smoke check f (`SMOKE OK (7 checks)`), the zone checks of Verify 4 and 6, and P6.5's `test_zone_detail_passes`. Phase 4 then expects 6 passed (suite 33); later suites are 2 lower, and from Phase 6 on 3 lower |
| 105 | **Analysis must have started** | Start P6.1 now; Phase 5 keeps only what is green (basic JSON logs + middleware) |
| 120 | `tests/test_geodesy.py` green | Cut 7 (overlap handling and touch band). Never drop T1–T4 (except T3's 3-D clause under cut 6), T6–T9 or the crossing cases of T10/T11 |
| 135 | P6.4 started | Persist metrics and passes first, then intersections (never cut); take the time from the cuts still ahead (1 and 4, then 10) |
| 152 | Analysis fields visible in `GET /trajectories/{id}` (P6.5 is scheduled to end at 151) | Finish the trajectory detail first (`analysis`, `zone_passes`, `intersections`; never cut); drop the unfinished zone part (aggregates and `ZoneDetail.passes`, cut 1's scope) |
| 165 | **Feature freeze:** `bash scripts/verify.sh` ends `VERIFY OK` | Fix only the failing step; README becomes 20 lines (cut 10's scope) |
| 177 | Final commit made | Commit and push now |

Two more triggers:

- **Calibration at minute 30:** if P0.1 or P1.1 needed a retry, P5.1 and P6.2 move to the large model.
- **Token tripwire:** see Token rules.

### Cut list (cheapest loss first; minutes saved)

- When behind, apply the first cut whose "Decide by" minute is still ahead. A cut decided after its minute saves nothing, because that prompt has already been sent; skip it and take the next one.
- Make the cut's "Also change" edits before sending the affected prompt. Removing a case from a prompt's test list before the prompt is sent is a scope change, not a test edit.
- Cut 7 is the one exception. It is applied at its tripwire (minute 120), so it removes cases already written in `tests/test_geodesy.py`; the human deletes them by hand, and NOTES "Known limitations" says so.
- P7.4 (the optional large review) is not on this list. It is unscheduled and runs only on time saved earlier, so skipping it saves nothing.

| # | Cut | Saves | Decide by (min) | Also change |
|---|---|---|---|---|
| 1 | Zone `analysis` aggregates (`pass_count`, `trajectory_count`) | 3 | 143 (P6.5) | P6.5 leaves zone `analysis` null; `test_zone_detail_passes` keeps only its 2-passes assert; Verify 6 drops the ZN-BAFFIN `pass_count` check |
| 2 | `started_after` / `started_before` list filters | 4 | 73 (P4.1) | P4.1 drops `test_started_filters`: P4.1 expects 5 passed, Phase 4 7 (suite 34), then 37 and ≥ 62 |
| 3 | `stale` flag and `input_hash` | 3 | 124 (P6.3) | P6.3 omits `input_hash`; P6.5 removes `stale` from `TrajectoryAnalysisOut`; P7.1's check 7 drops its stale clause |
| 4 | `scripts/check_invariants.py` (P7.1) | 4 | 153 (P7.1) | P7.2's `verify.sh` has no invariants step; Verify 7 and NOTES drop `INVARIANTS OK` |
| 5 | P6.2 oracle tests (the analytic table stays) | 6 | 118 (P6.2) | Phase 6 expects ≥ 56; Verify 6 runs only `tests/test_geodesy.py`; NOTES' geo row cites the analytic table only |
| 6 | `length_3d_km` and altitudes at events (the nullable columns and fields stay, null) | 4 | 103 (P6.1) | Remove T3's `path_length_3d_km` clause from P6.1's table before sending it; P6.5's tests drop their altitude asserts |
| 7 | Overlap handling and the ±1 m touch band (co-linear segment pairs are skipped and counted in the log) | 5 | 120 (tripwire) | Drop T5's touch case, the overlap cases of T10/T11 and `test_overlap_pair` (Phase 6 expects ≥ 62). Analyze then reports 7 intersections: X1's two overlap rows are gone. S7 becomes a crossing pass of about 0.02 km, so Verify 6 drops its `"kind":"touch"` check. The hand deletion is its own commit (`cut 7: …`), so Verify 6's `git log` count for `tests/test_geodesy.py` becomes 2 |
| 8 | Hash-based change detection → full-refresh ingestion | 8 | 58 (P3.2) | P3.2 variant: in the run's one transaction, delete all stored trajectories and zones (points and analysis rows cascade), then insert every valid record. No preload, no hash comparison, no update path, so a run must include every file, as the default `data` does. Run 2 reports inserted 20 (Verify 3). P3.2's three re-run tests assert stored rows and row counts instead of updated/unchanged. P7.2's `verify.sh` ingest-2 step asserts `status` plus unchanged `gisdb stats` entity counts. NOTES "Known limitations" |
| 9 | `ingest_rejections` table → reason codes only in logs and counts | 5 | 31 (P2.1) | P2.1 omits the model, so 0001 has 4 tables (checklist item 3 says 4); P3.2 logs each rejection and its tests assert counts, not rows; `gisdb stats` lists no `ingest_rejections` |
| 10 | README cut to 20 lines; NOTES keeps only the evidence map | 2 | 163 (P7.3) | Verify 7 expects README ≤ 20 and NOTES ≤ 20 lines |

Total: 44 minutes. 23 of them are still available after minute 105 (cuts 1, 3, 4, 5, 7 and 10).

### Never cut

- Migrations 0001 and 0002 through Alembic, reviewed (`Reviewed:` line).
- Idempotent ingestion with run accounting: re-running on unchanged files leaves the same rows and never duplicates them. With hash detection (the default; cut 8 removes it), run 2 reports inserted 0 and updated 0.
- Trajectory list and detail with pagination, 404 and 422.
- JSON logs with `request_id` and the `X-Request-ID` header.
- Great-circle length, zone entry/exit with interpolated times, and trajectory crossings: persisted and returned by the API.
- The analytic geo tests: T1–T11, minus the cases that cuts 6 and 7 remove.
- `scripts/verify.sh` → `VERIFY OK`.
- A green commit per phase and `AI_LOG.md`.

## Model routing

| Id | Title | Model | Why this model |
|---|---|---|---|
| P0.1 | Data profiler script | small | One stdlib script from an exact spec; calibration probe 1 |
| P0.2 | PLAN.md from brief + profile | large | Synthesis over an unseen brief; mistakes propagate everywhere |
| P1.1 | Project skeleton | small | Boilerplate with exact file list and code shapes; calibration probe 2 |
| P2.1 | Models, Alembic env.py, test fixtures | large | Interlocking schema invariants and the Alembic traps |
| P3.1 | Record parsing and normalization + unit tests | large | Where silent data errors hide (order, units, time zones) |
| P3.2 | Ingestion service, CLI, DB tests | large | Transactions, idempotency, run accounting |
| P4.1 | Trajectory endpoints (the API pattern) + tests | large | Sets the contract and query pattern that P4.2 and P6.5 copy |
| P4.2 | Zone endpoints copying P4.1 + tests | small | Pattern copy, tests catch drift |
| P5.1 | Structured logging, request IDs, JSON 500 + tests | small | Known recipe given verbatim; escalate on the first failure |
| P6.1 | Geodesy core + analytic tests T1–T11 | large | Numerically subtle; the prompt is the spec |
| P6.2 | Property + geographiclib oracle tests | small | Mechanical recipe; value lies in independence |
| P6.3 | Analysis result models | small | Exact column list copying the 0001 style |
| P6.4 | Analysis runner, `analyze` CLI, tests | large | Orchestration, transactions, interpolation |
| P6.5 | Analysis in the API + tests | large | Joins, perspective flip, no N+1 |
| P7.1 | `scripts/check_invariants.py` | small | Fixed check list |
| P7.2 | `scripts/smoke.py` + `scripts/verify.sh` | small | Fixed step list (calls P7.1's script) |
| P7.3 | README.md + NOTES.md | small | Summarizes facts it is given |
| P7.4 | Optional review (no edits) | large | Finds defects a small model would miss; unscheduled, only on time saved earlier |

17 mandatory prompts (8 large, 9 small) plus the optional large P7.4.

### Escalation

- **Small fails once:** send the phase's "If it fails" prompt to the same chat with the failure tail (≤ 20 lines).
- **Small fails a second time, or fails once after minute 120:** re-send the original prompt to the large model in a fresh chat, with the failure tail.
- **Large fails twice:** fix it by hand or apply the cut list.
- **Any fix of ≤ 5 lines:** make it by hand with no AI, and note "hand fix" in AI_LOG.md.
- **Geometry and unit conversions:** never retried on the small model.
- **Exception:** P5.1 escalates to the large model on its first failure.
- **Calibration at minute 30:** P0.1 and P1.1 are the small model's probes. If either needed a retry, P5.1 and P6.2 move to the large model.

## Token rules

- A fresh chat per phase, opened with the kickoff header (see Prompt contract, kickoff header and gate). A phase that uses both models needs one chat per model, sometimes more; each phase's Chats line lists them.
- Only `DATA_PROFILE.md` reaches the models, never raw `data/*.json`.
- Paste only the failing tail (≤ 20 lines). Ask for terse replies.
- **Tripwire:** stop and narrow a prompt that passes about 300k tokens or about 15 tool calls.
- **Expected spend:** small 9 × 20–60k plus large 9 × 60–200k, plus 50% for retries. That is roughly 1.1–3.5M tokens ((0.18–0.54M + 0.54–1.8M) × 1.5), well inside 10–20M.

## Prompt contract, kickoff header and gate

Every prompt in this playbook has this shape (braces mark the parts that differ per prompt):

```text
[P{N}.{k} — {title}] (model: small|large)
READ: {files and PLAN.md sections}
CHANGE ONLY: {exact file list}
TASK:
1. {numbered steps with exact names, signatures, library calls; never "appropriate", "robust", "etc."}
DONE WHEN: {command} -> {expected output}
Agent rules: follow PLAN.md §1 Conventions. Change only the CHANGE ONLY files. Never edit tests to make them pass. Never run git. Reply with the changed files and the last 15 lines of any command you ran.
```

**Kickoff header**, pasted as the first message of each phase's fresh chat:

```text
Context: a timed build of a Python API service in this repo. First read PLAN.md §1 Conventions and §11 Status, then only the files a prompt lists under READ. Never list directories recursively; never open .venv/, uv.lock or data/*.json. Keep replies terse: changed files plus the last 15 lines of any command output. If you cannot run commands, give me the exact commands to run. Wait for my first prompt.
```

**Gate after every prompt (~60 s).** The `gate` function is in Session setup.

1. Run `gate`. Restore any file the agent changed outside CHANGE ONLY (`git restore FILE`, delete stray new files). Keep the formatting-only changes that the gate's own `ruff format` / `--fix` made.
2. If the gate or the DONE WHEN fails, stage everything (`git add -A`) first, then send the "If it fails" prompt. Afterwards `git diff --stat -- tests/` shows only what the fix changed. It must be empty, or touch only the test file that the failing prompt itself created, never an expected value. Test files of earlier prompts (the human-owned values in `test_records`, `test_ingest`, `test_api`, `test_geodesy`, `test_analysis`) never change.
3. Append the AI_LOG.md row (see AI log and commit tags).
4. Commit with `git add -A && git commit -qm "P{N}.{k}: {what} [AI: small|large]"`.

**Exceptions:**

- **Phase 0:** before `uv init` exists, the gate is only `git status --short` and the commit. P0.1's AI_LOG row and commit come at the end of Human step 0.b, which creates AI_LOG.md.
- **P2.1 and P6.3:** run `gate lint`; pytest stays red until Human step 2.b / 6.a has generated and applied the migration. Until then the new tables do not exist: `test_no_drift` fails, and every DB test errors in the `db` fixture. The full `gate`, the AI_LOG row and one commit follow that human step, for example `P2.1: models, env.py, fixtures; 0001 reviewed [AI: large]`.

## AI-use habits the grader wants to see

- **Plan first.** The human reads the brief; PLAN.md exists before any code; the models see `DATA_PROFILE.md`, never raw data.
- **Every prompt is explicit:** it names its model (and Model routing says why), its READ and CHANGE ONLY files, and its DONE WHEN.
- **Expected test values exist before code:** they are written into the prompts, and `git diff --stat -- tests/` after any fix prompt proves they were never edited.
- **Migrations are reviewed by a human** against a checklist; the `Reviewed:` line in each migration records it.
- **The gate runs after every prompt:** scope check, forbidden-API grep, ruff, pytest.
- **Evidence:** one AI_LOG.md row per prompt and an `[AI: …]` tag on every prompt and phase commit (human-step commits say `[human]`).
- **Escalation by rule** (Model routing); fixes of ≤ 5 lines are typed by hand and logged as "hand fix".
- **Fresh chats and short failure tails:** a new chat per phase with the kickoff header; ≤ 20 lines of output per recovery prompt.

## Human-only steps

Never delegated:

- Reading the brief.
- The environment check and the DB decision.
- The coordinate-order landmark check.
- Pasting the PLAN.md skeleton and Conventions; the 2-minute PLAN.md review by direct edit.
- `uv init` and `uv add`; the pyproject tool block; `.gitignore` lines; `.env`.
- `alembic init`; `alembic revision --autogenerate`; `ruff format` on the new migration; migration review and the `Reviewed:` line.
- Every Verify command; the gate; commits; AI_LOG.md rows.
- Owning the expected test values (they are in the prompts before any code exists).
- Checking README claims.
- Asking the interviewer the open questions.

## AI log and commit tags

`AI_LOG.md` at the repo root, created in Human step 0.b:

```text
# AI usage log
| min | prompt | model | ask | verified by | outcome |
|---|---|---|---|---|---|
| 07 | P0.1 | small | stdlib data profiler | ran it; coord ranges prove [lon, lat] | accepted |
```

- `outcome` is one of: `accepted`, `accepted + hand fix (N lines)`, `retried`, `escalated to large`, `replaced by hand`.
- Append a row by hand in about 20 seconds, for example:

```bash
echo '| 13 | P0.2 | large | PLAN.md from brief + profile | 11 headings; read §3 and §8 | accepted |' >> AI_LOG.md
```

- **Per-prompt commit tag:** `[AI: small]` or `[AI: large]`, for example `P3.1: record parsing and normalization [AI: large]`. Each prompt below gives its commit message on its "Why" line.
- **Phase checkpoint tag:** `[AI: P3.1 L, P3.2 L; human: {what the human did}]`. Each checkpoint first ticks its phase in PLAN §11, so the commit is never empty.
- **Human-step commits** (H1.a, H2.a) carry `[human]`. They keep the next prompt's `git status` down to its CHANGE ONLY files.

## Placeholders and PLAN.md

**Placeholders.** Syntax `<NAME=value>`: NAME in upper snake case, the value is the practice value, written in full at every occurrence.

- On the day, overwrite only the value, using what PLAN.md records (P0.2 ends PLAN §3 with a "Placeholder values" table).
- PLAN §1 Conventions tells the model: "Tokens written `<NAME=value>` in a prompt mean: use `value`."
- Placeholders appear only inside prompt (`text`) blocks. Bash blocks use the shell variables of Session setup instead. The one exception is the body of a quoted heredoc (`<<'EOF'`), such as Human step 0.b's PLAN.md skeleton, which is literal text.
- Anything else brief-specific is cited as "per PLAN §n".

| Name | Meaning | First filled | Practice value |
|---|---|---|---|
| `BRIEF` | Instructions file | Phase 0, Human step 0.a | `INSTRUCTIONS.md` |
| `DATA_DIR` | Directory of provided JSON files | Phase 0, Human step 0.a | `data` |
| `DB_URL` | Dev database URL | Phase 0 env check → PLAN §9 | `postgresql+psycopg://gis:gis@localhost:5432/gis` |
| `TEST_DB_URL` | Test database URL (name must contain `test`) | Phase 0 → PLAN §9 | `postgresql+psycopg://gis:gis@localhost:5432/gis_test` |
| `TRAJECTORY_SOURCE` | File, record list and natural key of trajectory records | P0.2 → PLAN §3 | `flights.json → "flights" list; key flight_id` |
| `POINT_SOURCE` | Position list inside a trajectory record and its fields | P0.2 → PLAN §3 | `positions[]: ts, coord, alt_ft` |
| `ZONE_SOURCE` | File, record list and natural key of zone records | P0.2 → PLAN §3 | `zones.json → GeoJSON "features" list (geometry Point); key = feature "id"` |
| `TRAJECTORY_ATTRS` | Descriptive source fields → trajectory columns | P0.2 → PLAN §3 | `callsign → callsign, aircraft.icao_type → aircraft_type, origin → origin, destination → destination` |
| `ZONE_ATTRS` | Descriptive source fields → zone columns | P0.2 → PLAN §3 | `properties.name → name` |
| `COORD_ORDER` | Order inside coordinate arrays | Human step 0.b (landmark check) → PLAN §3 | `[lon, lat]` |
| `TIME_FORMATS` | Accepted timestamp forms | P0.2 → PLAN §3 | `ISO-8601 with Z or ±HH:MM offset, or integer Unix epoch seconds` |
| `ALT_UNIT` | Altitude field and unit | P0.2 → PLAN §3 | `alt_ft in feet (x 0.3048 -> alt_m), may be null` |
| `RADIUS_UNITS` | Radius field and unit field | P0.2 → PLAN §3 | `properties.radius with properties.radius_unit "NM" (x 1.852) or "km"` |
| `EARTH_RADIUS_KM` | Sphere radius | P0.2 → PLAN §8 | `6371.0088` |
| `TOL_KM` | Geometric tolerance: max(0.001, coordinate quantization). T5 assumes it is below 0.004; above that, the T5 rule of Appendix E — Adapting to the real brief applies | P0.2 → PLAN §8 | `0.001` |
| `SAMPLE_TRJ` | A trajectory id used in NOTES.md commands (P7.3 writes it literally) | Human step 0.b, from DATA_PROFILE.md; after Phase 6, switch to one with a zone pass if it has none | `FLT-1003` |

**PLAN.md.** Human step 0.b creates it by pasting this skeleton, with §1 filled from the Conventions block. P0.2 fills §2–§11. Check: `grep -c '^## ' PLAN.md` prints `11`.

```text
# PLAN
## 1. Conventions
## 2. Brief
## 3. Data mapping
## 4. Schema
## 5. Ingestion
## 6. API
## 7. Logging
## 8. Analysis
## 9. Commands
## 10. Decisions and open questions
## 11. Status
```

| Section | Content (written by P0.2 unless noted) | Cited by |
|---|---|---|
| §1 Conventions | The Conventions block, verbatim (pasted by the candidate) | every prompt |
| §2 Brief | Numbered requirements R1..Rn in the brief's words; analysis requirements quoted verbatim | P0.2, P7.3 |
| §3 Data mapping | Names (brief term → generic table); per file: record list path, entity, natural key; every source field → column, type, unit, conversion; coordinate order with the landmark proof; timestamp forms; validation rules → reason codes; the "Placeholder values" table | P2.1, P3.1, P3.2 |
| §4 Schema | Default schema plus DELTA lines for brief-specific columns | P2.1, P6.3 |
| §5 Ingestion | Default ingestion design plus DELTA lines | P3.1, P3.2 |
| §6 API | Default API plus DELTA lines | P4.1, P4.2, P6.5 |
| §7 Logging | The event catalogue (event, level, fields) plus DELTA lines | P3.2, P5.1, P6.4 |
| §8 Analysis | Earth model, definitions (the brief's wording, adapted), `TOL_KM` with the arithmetic (6 decimals → 0.11 m → 0.001 km), storage | P6.1, P6.4, P6.5, P7.1 |
| §9 Commands | migrate / ingest / analyze / stats / serve / test / verify, with the DB URLs | P1.1, P7.2, P7.3 |
| §10 Decisions and open questions | Assumptions taken, plus ≤ 5 questions for the interviewer | P7.3 |
| §11 Status | Checklist Phase 0..7, one line `- [ ] Phase N: {title}` each (the candidate ticks a phase at each checkpoint) | kickoff header |

## Conventions block

Pasted verbatim as PLAN.md §1 by Human step 0.b. Every prompt's Agent rules point here.

```text
- Tokens written <NAME=value> in a prompt mean: use value.
- Stack: Python 3.12, code stays 3.11-compatible (no `type X = ...`, no `class C[T]`); uv only (`uv add`, `uv run`; never pip, never requirements.txt); FastAPI + uvicorn; SQLAlchemy 2.x typed ORM; Alembic; psycopg 3; Pydantic v2 + pydantic-settings; structlog; pytest + fastapi.testclient; ruff.
- Layout: package gisdb in src/gisdb/ (config, db, models, logging_config, records, ingest, geodesy, analysis, cli, api/{app,deps,schemas,routes}); migrations/; tests/; scripts/. Import as gisdb.<module>. No extra layers (no repositories, services packages, DI frameworks).
- SQLAlchemy: class Base(DeclarativeBase) in models.py with the naming convention; Mapped[...], mapped_column(), relationship(), select(), session.scalars()/.execute()/.get(). NEVER declarative_base(), Column() in models, session.query(), engine.execute().
- Sync only: create_engine, sessionmaker, Session; endpoints are plain def. NEVER AsyncSession, create_async_engine, asyncpg, aiosqlite, async def endpoints.
- Database URL only from settings (GISDB_DATABASE_URL). Postgres URLs are postgresql+psycopg://. NEVER postgresql:// or psycopg2.
- Keys: id = internal integer PK, never in the API; <x>_id = natural string key used in URLs and JSON (exception: ingest_run_id and analysis_run_id in CLI output and logs are the runs' integer id); <x>_pk = integer FK to <x>s.id. Units in names: _km, _m, _s. Times are timezone-aware UTC.
- Types: UTCDateTime and JSONType from gisdb.models; server_default=text("CURRENT_TIMESTAMP"), NEVER func.now(); String(n) + named CheckConstraint instead of Enum; no ARRAY, no Geography.
- Coordinates: in code a position is (lat, lon) in degrees; [lon, lat] exists only at the JSON boundary in records.py.
- Pydantic v2: model_config = ConfigDict(...), field_validator, model_validator, model_validate, model_dump. NEVER class Config, orm_mode, @validator, @root_validator, parse_obj, .dict(). Settings: from pydantic_settings import BaseSettings, SettingsConfigDict.
- FastAPI: Annotated parameters (Annotated[Session, Depends(get_session)], Annotated[int, Query(ge=1, le=500)] = 50); GET routes only; NEVER @app.on_event.
- Logging: log = structlog.get_logger(__name__); log.info("area.object.verb", key=value) with names from PLAN §7; logs go to stderr; NEVER print() in src/ (a CLI writes its one JSON result line with sys.stdout.write); never log whole payloads or coordinate arrays.
- Errors: catch specific exceptions (e.g. sqlalchemy.exc.SQLAlchemyError, json.JSONDecodeError); `except Exception` only to log.exception(...) or to re-raise; inside except, raise NewError(...) from exc.
- Geo: sphere R = 6371.0088 km; all geodesy in src/gisdb/geodesy.py with math only; NEVER interpolate, average or subtract raw lat/lon.
- Migrations: the human runs autogenerate and reviews. NEVER create or edit files in migrations/versions/.
- Tests: NEVER weaken, skip or delete a test or an expected value to make it pass; if a test looks wrong, stop and say why.
- Scope: change only the files the prompt names; add dependencies only when the prompt names them; never run git; never leave a server running; after 3 failed attempts at the same command, stop and report.
- Replies: changed files (one line each) plus the last 15 lines of any command you ran; never paste whole files back.
```

## Phase 0 — Orient and plan (0–15 min)

**Goal:** know the brief, the data and the environment before any code exists; write PLAN.md.   **Model:** mixed   **Done when:** DATA_PROFILE.md, PLAN.md (11 sections) and AI_LOG.md are committed, the coordinate order is proven by a landmark, and the DB decision is made.

Chats: P0.1 in a fresh small-model chat, P0.2 in a fresh large-model chat, each opened with the kickoff header (see Prompt contract, kickoff header and gate).

Clock (see Time budget): tripwire 10, Postgres reachable with the brief's credentials, else SQLite; tripwire 15, PLAN.md committed.

#### Human step 0.a — Read the brief and check the environment (no AI)

```bash
date +%H:%M                                            # session start: tripwire minutes count from here
export BRIEF=INSTRUCTIONS.md DATA_DIR=data
cat "$BRIEF"                                           # read it yourself (3 min)
ls -la "$DATA_DIR"; python3 --version; uv --version || echo "NO UV"   # flights.json, zones.json; Python 3.12.3, uv 0.11.16
git branch --show-current || echo "NO GIT REPO"        # development (none: git init)
git config user.email || echo "NO GIT IDENTITY"         # an address (none: git config user.name 'Your Name'; git config user.email 'you@example.com')
pg_isready -h localhost -p 5432 || echo "NO POSTGRES ON 5432"        # localhost:5432 - accepting connections
PGCONNECT_TIMEOUT=5 PGPASSWORD=gis psql -h localhost -U gis -d gis -tAc "select 1" || echo "NO PSQL ACCESS"       # 1
PGCONNECT_TIMEOUT=5 PGPASSWORD=gis psql -h localhost -U gis -d gis_test -tAc "select 1" || echo "NO TEST DB"     # 1 (none: see Appendix D — No-Postgres fallback (SQLite))
env | grep -iE 'database|postgres|^pg' || true          # any DB settings the environment provides
```

Every gate and checkpoint commits, and conftest refuses a test URL without `test` in its database name, so the git and test-DB lines matter as much as the server check. **Tripwire 10:** no reachable Postgres with the brief's credentials means SQLite: Human step 1.a then writes the SQLite `.env` lines, and P0.2 gets the SQLite URLs as DB_URL and TEST_DB_URL (see Appendix D — No-Postgres fallback (SQLite)).

#### Prompt 0.1 — Data profiler (model: small)

```text
[P0.1 — Data profiler] (model: small)
READ: nothing. PLAN.md does not exist yet; this prompt is the whole spec. Do not open the data files yourself.
CHANGE ONLY: scripts/profile_data.py (new)
TASK:
1. Standard library only, under 150 lines, lines of at most 100 characters, a main() function and `if __name__ == "__main__": main()`. Usage: python3 scripts/profile_data.py FILE [FILE ...]. It prints Markdown to stdout and never prints whole records or whole lists.
2. For each FILE print, in this order:
   a. "## " followed by the path as given.
   b. One bullet with the top-level JSON type and the record list found: the top-level list itself, or else the first list of objects under a top-level key, preferring "features". Format example: - top level: object; records: "flights" (list, 15 items); other keys: exported_at, source
   c. A Markdown table | path | types | n | nulls | min | max | distinct | example | with one row per dotted path inside the records. Nested objects give a.b; a list of objects becomes name[] and its items' fields are profiled as name[].field; a list of at most 4 scalars is expanded per index as name[0], name[1]. n = values seen at the path; nulls = how many of them were null; types = the type names seen; min and max for numbers (not booleans); distinct for strings (counting stops at 1000); example = the first non-null value, cut to 40 characters.
   d. "- repeated keys: " followed by every value seen more than once in a record-level field named id or ending in _id, written as VALUE xCOUNT, or "none".
   e. "- timestamp forms: " for every path whose example looks like a timestamp (a string starting with an ISO date YYYY-MM-DD, or an integer above 1e9): the counts over all its values of Z, ±HH:MM, no offset, epoch int and other.
3. Catch only OSError and json.JSONDecodeError, per file: print the error under that file's heading and continue with the next file.
DONE WHEN: python3 scripts/profile_data.py <DATA_DIR=data>/*.json | grep '^## ' -> one heading line per data file, and the script exits 0
Agent rules: follow PLAN.md §1 Conventions. Change only the CHANGE ONLY files. Never edit tests to make them pass. Never run git. Reply with the changed files and the last 15 lines of any command you ran.
```

Practice values: `DATA_DIR=data`

Why small: one stdlib script from an exact spec, and calibration probe 1 (see Model routing). Commit message, made at the end of Human step 0.b: `P0.1: data profiler; DATA_PROFILE.md, PLAN skeleton, AI log [AI: small]`.

Then run the gate and log the prompt (top section). In Phase 0 the gate is `git status --short`, which should show only `?? scripts/`; P0.1's AI_LOG row and commit come at the end of Human step 0.b.

#### Human step 0.b — Landmark check, PLAN skeleton, AI log, sample ids (no AI)

```bash
python3 scripts/profile_data.py "$DATA_DIR"/*.json > DATA_PROFILE.md
grep -c '^## ' DATA_PROFILE.md                       # 2 (one section per file)
grep -E 'coord\[|coordinates\[' DATA_PROFILE.md      # positions[].coord[0]: min -166.203515, max 178.303493, example -0.4543 (beyond ±90, so longitude); positions[].coord[1]: min 35.5494, max 91.2, example 51.47; (51.47, -0.4543) is London Heathrow: order [lon, lat]; geometry.coordinates[0]: min -179.95, max 0.0
grep -E 'alt_ft|radius' DATA_PROFILE.md              # alt_ft: 2 nulls, max 39000; properties.radius: min -5, max 75; properties.radius_unit: distinct 2
grep -E 'repeated keys|timestamp forms' DATA_PROFILE.md   # flights: FLT-1004 x2; positions[].ts: Z 141, ±HH:MM 41, epoch int 28
cat > PLAN.md <<'EOF'
# PLAN
## 1. Conventions
- Tokens written <NAME=value> in a prompt mean: use value.
- Stack: Python 3.12, code stays 3.11-compatible (no `type X = ...`, no `class C[T]`); uv only (`uv add`, `uv run`; never pip, never requirements.txt); FastAPI + uvicorn; SQLAlchemy 2.x typed ORM; Alembic; psycopg 3; Pydantic v2 + pydantic-settings; structlog; pytest + fastapi.testclient; ruff.
- Layout: package gisdb in src/gisdb/ (config, db, models, logging_config, records, ingest, geodesy, analysis, cli, api/{app,deps,schemas,routes}); migrations/; tests/; scripts/. Import as gisdb.<module>. No extra layers (no repositories, services packages, DI frameworks).
- SQLAlchemy: class Base(DeclarativeBase) in models.py with the naming convention; Mapped[...], mapped_column(), relationship(), select(), session.scalars()/.execute()/.get(). NEVER declarative_base(), Column() in models, session.query(), engine.execute().
- Sync only: create_engine, sessionmaker, Session; endpoints are plain def. NEVER AsyncSession, create_async_engine, asyncpg, aiosqlite, async def endpoints.
- Database URL only from settings (GISDB_DATABASE_URL). Postgres URLs are postgresql+psycopg://. NEVER postgresql:// or psycopg2.
- Keys: id = internal integer PK, never in the API; <x>_id = natural string key used in URLs and JSON (exception: ingest_run_id and analysis_run_id in CLI output and logs are the runs' integer id); <x>_pk = integer FK to <x>s.id. Units in names: _km, _m, _s. Times are timezone-aware UTC.
- Types: UTCDateTime and JSONType from gisdb.models; server_default=text("CURRENT_TIMESTAMP"), NEVER func.now(); String(n) + named CheckConstraint instead of Enum; no ARRAY, no Geography.
- Coordinates: in code a position is (lat, lon) in degrees; [lon, lat] exists only at the JSON boundary in records.py.
- Pydantic v2: model_config = ConfigDict(...), field_validator, model_validator, model_validate, model_dump. NEVER class Config, orm_mode, @validator, @root_validator, parse_obj, .dict(). Settings: from pydantic_settings import BaseSettings, SettingsConfigDict.
- FastAPI: Annotated parameters (Annotated[Session, Depends(get_session)], Annotated[int, Query(ge=1, le=500)] = 50); GET routes only; NEVER @app.on_event.
- Logging: log = structlog.get_logger(__name__); log.info("area.object.verb", key=value) with names from PLAN §7; logs go to stderr; NEVER print() in src/ (a CLI writes its one JSON result line with sys.stdout.write); never log whole payloads or coordinate arrays.
- Errors: catch specific exceptions (e.g. sqlalchemy.exc.SQLAlchemyError, json.JSONDecodeError); `except Exception` only to log.exception(...) or to re-raise; inside except, raise NewError(...) from exc.
- Geo: sphere R = 6371.0088 km; all geodesy in src/gisdb/geodesy.py with math only; NEVER interpolate, average or subtract raw lat/lon.
- Migrations: the human runs autogenerate and reviews. NEVER create or edit files in migrations/versions/.
- Tests: NEVER weaken, skip or delete a test or an expected value to make it pass; if a test looks wrong, stop and say why.
- Scope: change only the files the prompt names; add dependencies only when the prompt names them; never run git; never leave a server running; after 3 failed attempts at the same command, stop and report.
- Replies: changed files (one line each) plus the last 15 lines of any command you ran; never paste whole files back.
## 2. Brief
## 3. Data mapping
## 4. Schema
## 5. Ingestion
## 6. API
## 7. Logging
## 8. Analysis
## 9. Commands
## 10. Decisions and open questions
## 11. Status
EOF
grep -c '^## ' PLAN.md                               # 11
# if P0.1 needed a retry, change the row's outcome below (retried, escalated to large, ...) before pasting
cat > AI_LOG.md <<'EOF'
# AI usage log
| min | prompt | model | ask | verified by | outcome |
|---|---|---|---|---|---|
| 07 | P0.1 | small | stdlib data profiler | ran it; coord ranges prove [lon, lat] | accepted |
EOF
export SAMPLE_TRJ=FLT-1003 SAMPLE_ZONE=ZN-POLE       # practice ids; on the day take a trajectory id and a zone id from DATA_PROFILE.md
git status --short                                   # ?? AI_LOG.md, ?? DATA_PROFILE.md, ?? PLAN.md, ?? scripts/
git add -A && git commit -qm "P0.1: data profiler; DATA_PROFILE.md, PLAN skeleton, AI log [AI: small]"
```

#### Prompt 0.2 — PLAN.md (model: large)

```text
[P0.2 — PLAN.md] (model: large)
READ: <BRIEF=INSTRUCTIONS.md> (all of it), DATA_PROFILE.md, PLAN.md §1.
CHANGE ONLY: PLAN.md (fill §2–§11 under the existing headings; keep §1 unchanged).
TASK:
1. Fill §2–§11 under the exact existing headings, at most 180 lines in total: terse bullets and tables, every decision a concrete value, no code. Add no other "## " headings (use "###" or bold text).
2. §2 Brief: numbered requirements R1..Rn in the brief's words; quote each analysis requirement verbatim.
3. §3 Data mapping, from DATA_PROFILE.md only; never open the files in <DATA_DIR=data>. Give: names (brief term -> generic table trajectories, trajectory_points or zones); per file: record list path, entity, natural key; every source field -> column, type, unit, conversion; the coordinate order <COORD_ORDER=[lon, lat]> with its landmark proof (the index whose values go beyond ±90 is the longitude; name one known place); the timestamp forms with their counts; validation rules -> reason codes (the codes of the Ingestion line below). End §3 with a table "Placeholder values" (NAME | value) for TRAJECTORY_SOURCE (file, record list, natural key), POINT_SOURCE (position list and its fields), ZONE_SOURCE (file, record list, natural key), TRAJECTORY_ATTRS (descriptive source fields -> trajectory columns), ZONE_ATTRS (descriptive source fields -> zone columns), COORD_ORDER, TIME_FORMATS, ALT_UNIT (field and unit) and RADIUS_UNITS (radius field and unit field).
4. §4–§8 start from the DEFAULT DESIGN block below: §4 = its Names, 0001 and 0002 lines; §5 = Ingestion; §6 = API; §7 = Logging, written as a table event | level | fields with every event of that line; §8 = Analysis. Add one "DELTA: ..." line for each change the brief requires.
5. §8 also gives the brief's analysis definitions (its wording, adapted to the generic names), the TOL_KM arithmetic (coordinates with N decimals -> 10^-N degrees x 111.2 km; TOL_KM = max(0.001 km, that); e.g. 6 decimals -> 0.11 m -> 0.001 km), and where each result is stored (0002 tables) and served (API fields).
6. §9 Commands, one line each: migrate (uv run alembic upgrade head), ingest (uv run gisdb ingest [PATH ...], default <DATA_DIR=data>), analyze (uv run gisdb analyze), stats (uv run gisdb stats), serve (uv run gisdb serve [--host 127.0.0.1] [--port 8000]), test (uv run pytest -q), verify (bash scripts/verify.sh [DATA_DIR], last line VERIFY OK). Then the dev database URL <DB_URL=postgresql+psycopg://gis:gis@localhost:5432/gis> and the test database URL <TEST_DB_URL=postgresql+psycopg://gis:gis@localhost:5432/gis_test> (its database name contains "test").
7. §10 Decisions and open questions: the assumptions taken, one line each with its reason; then at most 5 questions for the interviewer, most important first.
8. §11 Status: exactly these eight lines: "- [ ] Phase 0: Orient and plan", "- [ ] Phase 1: Project setup", "- [ ] Phase 2: Database models and migrations", "- [ ] Phase 3: JSON ingestion", "- [ ] Phase 4: Read-only API", "- [ ] Phase 5: Structured logging", "- [ ] Phase 6: Geospatial analysis", "- [ ] Phase 7: Tests and verification".
DEFAULT DESIGN (keep unless the brief requires a change; record each change as "DELTA: ...")
- Names: tables trajectories (+ trajectory_points) and zones; natural keys trajectory_id, zone_id (String(64) UNIQUE); surrogate integer id PKs; FKs named <x>_pk.
- 0001: ingest_runs (status, files JSON, seen/inserted/updated/unchanged/duplicates/rejected, CHECK seen = sum when succeeded), ingest_rejections (reason_code, detail, payload), trajectories (descriptive columns from §3, started_at, ended_at, point_count >= 2, content_hash), trajectory_points (PK trajectory_pk+seq; ts, lat, lon, alt_m; UNIQUE trajectory_pk+ts), zones (center_lat, center_lon, radius_km in (0, 10000), content_hash).
- 0002: analysis_runs (algorithm_version, earth_radius_km, tol_km, counts), trajectory_metrics (length_km, length_3d_km, duration_s, zone_pass_count, intersection_count, input_hash), zone_passes (entry/exit kind, lat, lon, time, alt_m; distance_inside_km, duration_s), trajectory_intersections (a_pk < b_pk; kind crossing|overlap_start|overlap_end; lat, lon; time_a, time_b, time_gap_s).
- Ingestion: `gisdb ingest [PATH...]`; one run row per call; normalize to UTC, degrees (lat, lon), km, m; sort and de-duplicate points; sha256 of the normalized record; insert/update/unchanged by natural key; exact duplicates counted; rejections with codes invalid_file, missing_field, invalid_value, out_of_range, invalid_timestamp, too_few_points, conflicting_points, duplicate_key_conflict.
- API (GET only, no prefix): /health, /trajectories (limit 1-500 default 50, offset, started_after, started_before), /trajectories/{trajectory_id}, /trajectories/{trajectory_id}/points, /zones, /zones/{zone_id}; envelope {items, total, limit, offset}; 404 {"detail": "<entity> '<id>' not found"}; analysis fields present and null until analyzed.
- Logging: structlog JSON on stderr; request-id middleware and X-Request-ID header. Events (level; fields): app.startup (info; version, db_dialect); http.request (info; status_code, duration_ms, plus request_id, method, path); http.unhandled_error (error; exception); health.check.failed (warning; error); ingest.run.started (info; ingest_run_id, paths); ingest.file.read (info; ingest_run_id, file, sha256, records); ingest.record.rejected (warning; ingest_run_id, file, record_index, record_key, reason_code); ingest.record.duplicate (info; ingest_run_id, file, record_index, record_key); ingest.run.finished (info; ingest_run_id, status, seen, inserted, updated, unchanged, duplicates, rejected, duration_ms); ingest.run.failed (error; ingest_run_id, error); analysis.run.started (info; analysis_run_id, trajectories, zones, algorithm_version); analysis.run.finished (info; analysis_run_id, status, trajectories, zone_passes, intersections, duration_ms); analysis.run.failed (error; analysis_run_id, error).
- Analysis: sphere R = <EARTH_RADIUS_KM=6371.0088> km; n-vectors; great-circle length; zone passes with entry/exit kinds crossing|track_start|track_end|touch (1 m band); trajectory intersections with both times (constant speed per segment); overlaps as start/end rows; full recompute in one transaction; TOL_KM = <TOL_KM=0.001>.
DONE WHEN: grep -c '^## ' PLAN.md -> 11
Agent rules: follow PLAN.md §1 Conventions. Change only the CHANGE ONLY files. Never edit tests to make them pass. Never run git. Reply with the changed files and the last 15 lines of any command you ran.
```

Practice values:

- `BRIEF=INSTRUCTIONS.md`
- `DATA_DIR=data`
- `COORD_ORDER=[lon, lat]`
- `DB_URL=postgresql+psycopg://gis:gis@localhost:5432/gis`
- `TEST_DB_URL=postgresql+psycopg://gis:gis@localhost:5432/gis_test`
- `EARTH_RADIUS_KM=6371.0088`
- `TOL_KM=0.001`

Why large: synthesis over an unseen brief, and its mistakes propagate everywhere. Commit message: `P0.2: PLAN.md from brief and profile [AI: large]`.

Then run the gate and log the prompt (top section). Phase 0 gate: `git status --short` lists only PLAN.md, as modified; append the P0.2 row, then commit with `git add -A && git commit -qm` and that message.

#### Verify 0

```bash
grep -c '^## ' PLAN.md                                              # 11
awk '/^## 3\./,/^## 4\./' PLAN.md | grep -cE 'lon, ?lat|feet|NM'    # >= 3 (section-scoped: the §1 Conventions cannot satisfy it)
awk '/^## 8\./,/^## 9\./' PLAN.md | grep -c 6371.0088               # >= 1
grep -c 'ingest.record.duplicate' PLAN.md                           # >= 1 (the full event catalogue reached §7)
grep -c '^- \[ \] Phase [0-7]:' PLAN.md                             # 8 (the §11 lines the checkpoints tick)
head -5 AI_LOG.md                                                   # the header, then the P0.1 and P0.2 rows
```

Then review PLAN.md for 2 minutes by direct edit (no re-prompt):

- §2: count the brief's numbered asks; none is missing.
- §3: coordinate order with the landmark; units (feet, NM/km) with factors; every timestamp form; natural keys; the profile's repeated key is covered by the duplicate rule; the "Placeholder values" table matches the profile.
- §8: every analysis requirement maps to a stored table/column and an API field; the `TOL_KM` arithmetic is there.
- §9: the URLs match the environment check (or SQLite).
- §10: at most 5 questions; ask the interviewer the top one now.

#### If it fails

```text
PLAN.md §3 is wrong. DATA_PROFILE.md's coordinate rows prove the order is <COORD_ORDER=[lon, lat]> (the index whose values go beyond ±90 is the longitude). The radius and its unit are <RADIUS_UNITS=properties.radius with properties.radius_unit "NM" (x 1.852) or "km">; the altitude is <ALT_UNIT=alt_ft in feet (x 0.3048 -> alt_m), may be null>. Fix §3 and §8 only; change no other section.
```

Practice values:

- `COORD_ORDER=[lon, lat]`
- `RADIUS_UNITS=properties.radius with properties.radius_unit "NM" (x 1.852) or "km"`
- `ALT_UNIT=alt_ft in feet (x 0.3048 -> alt_m), may be null`

P0.1 (profiler) fails instead: send "Fix only scripts/profile_data.py: standard library only, the output format of the prompt unchanged. Failure output (last 20 lines) follows:" with the tail to the same chat.

#### Talking points

- PLAN.md is context compression: every later prompt cites a section instead of re-explaining the brief.
- I read the brief myself; the models saw a profile, not raw data.
- Swapped lat/lon is valid-looking garbage, so I checked a landmark before writing code.

#### Checkpoint 0

```bash
sed -i 's/^- \[ \] Phase 0:/- [x] Phase 0:/' PLAN.md && grep -n '^- \[x\] Phase 0:' PLAN.md   # the line now reads - [x] Phase 0: Orient and plan
git add -A && git commit -m "phase 0: plan and data profile [AI: P0.1 S, P0.2 L; human: env check, landmark check, PLAN review]"
```

**Tripwire 15:** commit by minute 15 even if PLAN.md is imperfect; park doubts in PLAN §10.

## Phase 1 — Project setup (15–30 min)

**Goal:** a runnable uv project with settings, DB engine, basic JSON logs, `/health`, CLI and `api_get.py`.   **Model:** small   **Done when:** `ruff` is clean, `pytest` gives 1 passed, and `/health` says the database is ok.

Chat: a fresh small-model chat, opened with the kickoff header.

Clock (see Time budget): tripwire 27, `/health` reports `"database":"ok"`, else switch to SQLite; calibration at minute 30, if P0.1 or P1.1 needed a retry, P5.1 and P6.2 move to the large model.

#### Human step 1.a — uv project, tool config, .env, gate (no AI)

```bash
uv init --package --name gisdb --python 3.12 --vcs none --author-from none .
sed -i 's/requires-python = ">=3.12"/requires-python = ">=3.11"/' pyproject.toml
timeout 300 uv add fastapi "uvicorn[standard]" "sqlalchemy>=2.0,<3" alembic "psycopg[binary]" pydantic-settings structlog
timeout 300 uv add --dev pytest httpx ruff geographiclib
printf '.env\n.venv/\n__pycache__/\n*.sqlite3\n' >> .gitignore   # uv init --vcs none writes no .gitignore
grep -n authors pyproject.toml || echo "no authors"      # expect: no authors
cat >> pyproject.toml <<'EOF'

[tool.pytest.ini_options]
testpaths = ["tests"]
filterwarnings = ["ignore:Using `httpx` with `starlette.testclient` is deprecated"]

[tool.ruff]
line-length = 100
target-version = "py311"
extend-exclude = ["temp", "practice", "*.md"]

[tool.ruff.lint]
select = ["E", "W", "F", "I", "B", "UP", "SIM", "T20", "BLE", "DTZ"]

[tool.ruff.lint.per-file-ignores]
"scripts/*" = ["T20", "BLE001", "E501"]
"migrations/*" = ["E501"]
"tests/*" = ["E501"]
EOF
uv run ruff format -q scripts && uv run ruff check --fix -q scripts   # expect no output; hand-fix any reported line (≤ 5 lines)
cat > .env.example <<'EOF'   # on the day: the two URLs of PLAN §9
GISDB_DATABASE_URL=postgresql+psycopg://gis:gis@localhost:5432/gis
GISDB_TEST_DATABASE_URL=postgresql+psycopg://gis:gis@localhost:5432/gis_test
GISDB_LOG_LEVEL=INFO
EOF
cp .env.example .env
# SQLite (decided at minute 10 or 27) instead of the cp line:
# printf 'GISDB_DATABASE_URL=sqlite:///./gisdb.sqlite3\nGISDB_TEST_DATABASE_URL=sqlite:///./gisdb_test.sqlite3\nGISDB_LOG_LEVEL=INFO\n' > .env
gate() {   # "gate lint" skips pytest: used after P2.1 and P6.3, before the human step creates the migration
  git status --short && git diff --stat
  hits=$(grep -rnE "session\.query\(|declarative_base|orm_mode|class Config:|@validator|@root_validator|parse_obj|from pydantic import BaseSettings|AsyncSession|create_async_engine|asyncpg|aiosqlite|func\.now\(\)|text\('now\(\)'\)|on_event\(|postgresql://|psycopg2|utcnow" src tests migrations scripts 2>/dev/null)
  if [ -n "$hits" ]; then printf '%s\n' "$hits"; echo "FORBIDDEN API FOUND"; else echo "conventions grep clean"; fi
  uv run ruff format -q . && uv run ruff check --fix -q . || return 1
  [ "${1:-}" = lint ] || timeout 120 uv run pytest -q -x 2>&1 | tail -n 15
}
git add -A && git commit -qm "H1.a: uv project, dependencies, tool config [human]"
```

The `ruff` line brings the Phase 0 profiler up to the project rules before any gate runs; no later prompt may change that file. It lints only `scripts/`, because uv's template `src/gisdb/__init__.py` still holds a `print` until P1.1 replaces it. The httpx deprecation warning from Starlette is harmless (the pytest filter above silences it); never turn warnings into errors.

#### Prompt 1.1 — Project skeleton (model: small)

```text
[P1.1 — Project skeleton] (model: small)
READ: PLAN.md §1 and §9; pyproject.toml.
CHANGE ONLY: src/gisdb/__init__.py, src/gisdb/config.py, src/gisdb/db.py, src/gisdb/logging_config.py, src/gisdb/api/__init__.py, src/gisdb/api/app.py, src/gisdb/cli.py, scripts/api_get.py, tests/test_health.py, pyproject.toml (the [project.scripts] line only).
TASK:
1. src/gisdb/__init__.py: replace uv's template (its main() prints) with a one-line docstring and __version__ = "0.1.0".
2. src/gisdb/config.py: class Settings(BaseSettings) with model_config = SettingsConfigDict(env_prefix="GISDB_", env_file=".env", extra="ignore") and the fields database_url: str = "<DB_URL=postgresql+psycopg://gis:gis@localhost:5432/gis>", test_database_url: str = "<TEST_DB_URL=postgresql+psycopg://gis:gis@localhost:5432/gis_test>", log_level: str = "INFO", cors_origins: list[str] = ["*"] (GISDB_CORS_ORIGINS is a JSON list). get_settings() -> Settings, decorated with functools.lru_cache. Importing the module has no side effects.
3. src/gisdb/db.py: make_engine(url: str) -> Engine. If url starts with "sqlite": create_engine(url, connect_args={"check_same_thread": False}) plus a sqlalchemy.event "connect" listener on that engine that runs PRAGMA foreign_keys=ON. Otherwise: create_engine(url, pool_pre_ping=True, connect_args={"options": "-c timezone=UTC"}). Module level: engine = make_engine(get_settings().database_url) and SessionLocal = sessionmaker(bind=engine, expire_on_commit=False). get_session() yields a Session inside "with SessionLocal() as session:".
4. src/gisdb/logging_config.py: configure_logging(level: str) -> None calls structlog.configure(processors=[structlog.contextvars.merge_contextvars, structlog.processors.add_log_level, structlog.processors.TimeStamper(fmt="iso", utc=True), structlog.processors.format_exc_info, structlog.processors.JSONRenderer()], wrapper_class=structlog.make_filtering_bound_logger(level), logger_factory=structlog.PrintLoggerFactory(file=sys.stderr), cache_logger_on_first_use=False).
5. src/gisdb/api/__init__.py: empty. src/gisdb/api/app.py: log = structlog.get_logger(__name__); create_app() -> FastAPI calls configure_logging(get_settings().log_level), builds FastAPI(title="gisdb", version="0.1.0") and adds GET /health (tags=["health"], a plain def with session: Annotated[Session, Depends(get_session)]): session.execute(text("SELECT 1")), then return {"status": "ok", "database": "ok"}; on sqlalchemy.exc.SQLAlchemyError (never Exception: ruff BLE001) call log.warning("health.check.failed", error=str(exc)) and return JSONResponse(status_code=503, content={"status": "degraded", "database": "error"}). Before returning the app, log.info("app.startup", version="0.1.0", db_dialect=engine.dialect.name). Module level: app = create_app(). No @app.on_event.
6. src/gisdb/cli.py: main(argv: list[str] | None = None) -> int calls configure_logging(get_settings().log_level) first, then parses argparse with prog="gisdb" and required subcommands. For now only "serve", with --host (default 127.0.0.1) and --port (int, default 8000): uvicorn.run("gisdb.api.app:app", host=args.host, port=args.port, log_config=None, access_log=False), then return 0. The file ends with: if __name__ == "__main__": raise SystemExit(main())
7. pyproject.toml: change only the [project.scripts] entry, to gisdb = "gisdb.cli:main".
8. scripts/api_get.py: usage uv run python scripts/api_get.py [--request-id ID] PATH [PATH ...]. Inside main(), first call warnings.filterwarnings("ignore", message="Using `httpx` with `starlette.testclient`"), then import TestClient from fastapi.testclient and app from gisdb.api.app (imports inside main keep ruff E402 quiet). GET each PATH in-process with TestClient(app): no server, no port; send the X-Request-ID header when --request-id is given. For each PATH print one line: the status code, a space, the PATH, a space, then json.dumps(body, sort_keys=True, separators=(",", ":")), or the raw response text when the body is not JSON. Always exit 0. Logs stay on stderr.
9. tests/test_health.py: test_health_ok: TestClient(app).get("/health") returns status 200 and the JSON {"status": "ok", "database": "ok"}.
DONE WHEN: uv run ruff check . && uv run pytest -q -> All checks passed! and 1 passed
Agent rules: follow PLAN.md §1 Conventions. Change only the CHANGE ONLY files. Never edit tests to make them pass. Never run git. Reply with the changed files and the last 15 lines of any command you ran.
```

Practice values:

- `DB_URL=postgresql+psycopg://gis:gis@localhost:5432/gis`
- `TEST_DB_URL=postgresql+psycopg://gis:gis@localhost:5432/gis_test`

Why small: boilerplate with an exact file list and code shapes, and calibration probe 2 (see Model routing). Commit message: `P1.1: project skeleton, settings, health, CLI [AI: small]`.

Then run the gate and log the prompt (top section).

#### Verify 1

```bash
uv run ruff check . && timeout 120 uv run pytest -q   # All checks passed! … 1 passed
uv run python scripts/api_get.py /health             # 200 /health {"database":"ok","status":"ok"} (plus one JSON app.startup line on stderr)
uv run gisdb --help | head -3                        # usage: gisdb …
grep -n authors pyproject.toml || echo "no authors"  # no authors
```

#### If it fails

```text
pytest cannot import gisdb, or /health returns 503. Keep the src layout (package in src/gisdb) and [project.scripts] gisdb = "gisdb.cli:main", and run uv sync once. The database URL comes only from settings (GISDB_DATABASE_URL in .env); a Postgres URL starts with postgresql+psycopg://. /health catches sqlalchemy.exc.SQLAlchemyError, never Exception. Fix only the Prompt 1.1 files. Failure output (last 20 lines) follows:
```

**Tripwire 27:** if `/health` still reports a database error, write the SQLite `.env` lines (Human step 1.a, commented line) and rerun Verify 1; see Appendix D — No-Postgres fallback (SQLite). **Calibration at minute 30:** if P0.1 or P1.1 needed a retry, P5.1 and P6.2 move to the large model.

#### Talking points

- I typed the scaffolding myself; it costs zero tokens and cannot hallucinate a package name.
- One `.env` switches Postgres to SQLite; nothing else changes.
- `--author-from none` keeps my git identity out of a public `pyproject.toml`.

#### Checkpoint 1

```bash
sed -i 's/^- \[ \] Phase 1:/- [x] Phase 1:/' PLAN.md && grep -n '^- \[x\] Phase 1:' PLAN.md   # the line now reads - [x] Phase 1: Project setup
git add -A && git commit -m "phase 1: uv project, settings, health, CLI [AI: P1.1 S; human: uv init/add, tool config]"
```

## Phase 2 — Database models and migrations (30–48 min)

**Goal:** a normalized core schema and reviewed migration 0001.   **Model:** large   **Done when:** `0001 (head)`, `alembic check` is clean, the `Reviewed:` line is present, and `pytest` gives 5 passed.

Chat: a fresh large-model chat, opened with the kickoff header.

Clock (see Time budget): cut 9 before P2.1 (minute 31); tripwire 47, 0001 applied and `alembic check` clean.

#### Human step 2.a — alembic init (no AI)

```bash
uv run alembic init migrations                       # Creating directory .../migrations ... done (alembic.ini, env.py, script.py.mako, versions/)
git add -A && git commit -qm "H2.a: alembic init [human]"   # so git diff shows exactly what P2.1 changes in env.py
```

#### Prompt 2.1 — Models, env.py, test fixtures (model: large)

```text
[P2.1 — Models, env.py, test fixtures] (model: large)
READ: PLAN.md §1, §3, §4; src/gisdb/config.py; src/gisdb/db.py; migrations/env.py (alembic's template).
CHANGE ONLY: src/gisdb/models.py (new), migrations/env.py, tests/conftest.py (new), tests/test_migrations.py (new).
TASK:
1. src/gisdb/models.py header, exactly:
   NAMING = {"ix": "ix_%(column_0_label)s", "uq": "uq_%(table_name)s_%(column_0_N_name)s",
             "ck": "ck_%(table_name)s_%(constraint_name)s",
             "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s", "pk": "pk_%(table_name)s"}
   class UTCDateTime(TypeDecorator) with impl = DateTime(timezone=True) and cache_ok = True. Bind: None -> None; naive -> raise ValueError("naive datetime"); aware -> value.astimezone(UTC). Result: None -> None; naive (SQLite) -> value.replace(tzinfo=UTC); aware -> value.astimezone(UTC).
   JSONType = JSON().with_variant(JSONB(), "postgresql")
   class Base(DeclarativeBase): metadata = MetaData(naming_convention=NAMING)
2. Column rules: Mapped[...] with mapped_column() everywhere; timestamps UTCDateTime; floats Float; integer PKs Integer; created_at, updated_at and started_at use server_default=text("CURRENT_TIMESTAMP"); counters are Integer NOT NULL default=0. CHECKs are CheckConstraint(sql, name=SHORT_NAME) with the short names below; the convention renders name="lat_range" on trajectory_points as ck_trajectory_points_lat_range. UNIQUE via unique=True or UniqueConstraint; indexes via index=True.
3. The five models (class, table: columns; constraints and indexes):
   - IngestRun, ingest_runs: id Integer PK; started_at UTCDateTime NOT NULL default CURRENT_TIMESTAMP; finished_at UTCDateTime NULL; status String(16) NOT NULL; files JSONType NOT NULL (list of {path, sha256, records}); seen, inserted, updated, unchanged, duplicates, rejected Integer NOT NULL default 0; error Text NULL. CHECK status_valid: status IN ('running', 'succeeded', 'failed'). CHECK accounting: status <> 'succeeded' OR seen = inserted + updated + unchanged + duplicates + rejected.
   - IngestRejection, ingest_rejections: id Integer PK; ingest_run_pk Integer NOT NULL FK -> ingest_runs.id ON DELETE CASCADE, indexed; entity String(16) NOT NULL; source_file String(255) NOT NULL; record_index Integer NULL (NULL = whole file); record_key String(64) NULL; reason_code String(32) NOT NULL; detail Text NOT NULL; payload JSONType NULL (the raw record). CHECK entity_valid: entity IN ('trajectory', 'zone', 'file'). CHECK reason_code_valid: reason_code IN ('invalid_file', 'missing_field', 'invalid_value', 'out_of_range', 'invalid_timestamp', 'too_few_points', 'conflicting_points', 'duplicate_key_conflict').
   - Trajectory, trajectories: id Integer PK; trajectory_id String(64) NOT NULL UNIQUE; the descriptive columns of <TRAJECTORY_ATTRS=callsign → callsign, aircraft.icao_type → aircraft_type, origin → origin, destination → destination>, all NULL, typed per PLAN §4 (for these attrs: callsign String(32), aircraft_type String(16), origin String(8), destination String(8)); started_at UTCDateTime NOT NULL, indexed; ended_at UTCDateTime NOT NULL; point_count Integer NOT NULL; content_hash String(64) NOT NULL; source_file String(255) NOT NULL; last_ingest_run_pk Integer NULL FK -> ingest_runs.id ON DELETE SET NULL, indexed; created_at, updated_at UTCDateTime NOT NULL default CURRENT_TIMESTAMP. CHECK min_points: point_count >= 2. CHECK time_order: ended_at >= started_at. Relationship points: ordered by TrajectoryPoint.seq, cascade="all, delete-orphan", passive_deletes=True (read-only use; ingestion writes points with Core statements).
   - TrajectoryPoint, trajectory_points: trajectory_pk Integer FK -> trajectories.id ON DELETE CASCADE and seq Integer (0..n-1 in time order) form the composite PK; ts UTCDateTime NOT NULL; lat, lon Float NOT NULL; alt_m Float NULL. UNIQUE (trajectory_pk, ts). CHECK lat_range: lat >= -90 AND lat <= 90. CHECK lon_range: lon >= -180 AND lon < 180. CHECK seq_nonneg: seq >= 0.
   - Zone, zones: id Integer PK; zone_id String(64) NOT NULL UNIQUE; name String(128) NULL, from <ZONE_ATTRS=properties.name → name>; center_lat, center_lon, radius_km Float NOT NULL; content_hash String(64) NOT NULL; source_file String(255) NOT NULL; last_ingest_run_pk Integer NULL FK -> ingest_runs.id ON DELETE SET NULL, indexed; created_at, updated_at as in trajectories. CHECK lat_range: center_lat >= -90 AND center_lat <= 90. CHECK lon_range: center_lon >= -180 AND center_lon < 180. CHECK radius_range: radius_km > 0 AND radius_km < 10000.
4. migrations/env.py, keeping the template's offline and online functions:
   - run fileConfig(config.config_file_name) only if config.config_file_name is not None and config.attributes.get("configure_logger", True) (the tests pass False);
   - target_metadata = Base.metadata;
   - get_url() returns config.attributes.get("database_url") or get_settings().database_url; never read sqlalchemy.url from alembic.ini;
   - online mode connects with make_engine(get_url()) from gisdb.db;
   - both modes call context.configure(..., compare_type=True, render_as_batch=get_url().startswith("sqlite"), render_item=render_item);
   - imports for the hook: from sqlalchemy import JSON (SQLAlchemy's generic JSON, not the postgresql dialect's: that one is a subclass and isinstance misses the column type) and from gisdb.models import Base, UTCDateTime;
   - this hook, exactly (without it Alembic renders the custom types without imports and the upgrade fails with NameError):
     def render_item(type_, obj, autogen_context):
         if type_ == "type" and isinstance(obj, UTCDateTime):
             return "sa.DateTime(timezone=True)"
         if type_ == "type" and isinstance(obj, JSON):
             autogen_context.imports.add("from sqlalchemy.dialects import postgresql")
             return "sa.JSON().with_variant(postgresql.JSONB(), 'postgresql')"
         return False
5. tests/conftest.py. At the very top, before anything imports gisdb.db: from gisdb.config import Settings; url = Settings().test_database_url; raise RuntimeError unless the last path segment of url (url.rsplit("/", 1)[-1]) contains "test"; os.environ["GISDB_DATABASE_URL"] = url. Mark the later imports "# noqa: E402". Fixtures:
   - migrated_db (scope="session"): cfg = Config("alembic.ini"); cfg.attributes["configure_logger"] = False; command.downgrade(cfg, "base"); command.upgrade(cfg, "head"); yield gisdb.db.engine.
   - db (function scope; uses migrated_db): in one engine.begin() block, conn.execute(t.delete()) for t in reversed(Base.metadata.sorted_tables); then yield a SessionLocal() session and close it afterwards.
   - client (uses db): yield TestClient(app), app from gisdb.api.app (its get_session already points at the test database).
   - write_json: returns f(name, obj) -> Path that writes json.dumps(obj) to tmp_path / name.
   - make_trajectory (uses db): returns f(trajectory_id, points, **attrs) -> Trajectory, where points is a list of (iso_ts, lat, lon, alt_m) tuples in time order. It sets point_count, started_at and ended_at (first and last ts, parsed with datetime.fromisoformat), content_hash = "0" * 64 and source_file = "test", applies attrs, inserts the points with seq 0..n-1, commits and returns the trajectory.
   - make_zone (uses db): returns f(zone_id, lat, lon, radius_km, **attrs) -> Zone with content_hash = "0" * 64 and source_file = "test"; commits and returns it.
6. tests/test_migrations.py, exactly 4 tests:
   - test_no_drift: on a connection of the migrated engine, compare_metadata(MigrationContext.configure(conn, opts={"compare_type": True}), Base.metadata) == [].
   - test_round_trip (uses migrated_db, not db): command.downgrade(cfg, "base"), command.upgrade(cfg, "head"), then the current revision equals ScriptDirectory.from_config(cfg).get_current_head().
   - test_point_lat_check: inserting a trajectory point with lat 95 raises sqlalchemy.exc.IntegrityError (roll back afterwards).
   - test_trajectory_id_unique: a second trajectory with the same trajectory_id raises IntegrityError (roll back afterwards).
7. Do NOT create or edit files in migrations/versions/ and do not run alembic revision: I run autogenerate and review it myself. pytest stays red until then (the tables do not exist yet); do not try to fix that. When done, tell me to run autogenerate.
DONE WHEN: uv run python -c "import gisdb.models" -> exit code 0
Agent rules: follow PLAN.md §1 Conventions. Change only the CHANGE ONLY files. Never edit tests to make them pass. Never run git. Reply with the changed files and the last 15 lines of any command you ran.
```

Practice values:

- `TRAJECTORY_ATTRS=callsign → callsign, aircraft.icao_type → aircraft_type, origin → origin, destination → destination`
- `ZONE_ATTRS=properties.name → name`

Why large: interlocking schema invariants and the Alembic traps. Commit message, made at the end of Human step 2.b: `P2.1: models, env.py, fixtures; 0001 reviewed [AI: large]`.

Cut 9 (decide by minute 31): before sending, delete the IngestRejection item of TASK step 3; the review's item 3 then expects 4 tables.

Then run `gate lint`; log and commit after Human step 2.b.

#### Human step 2.b — Autogenerate, format and review 0001 (no AI)

```bash
timeout 120 uv run alembic revision --autogenerate -m "core schema" --rev-id 0001   # Generating .../migrations/versions/0001_core_schema.py ... done
uv run ruff format -q migrations/versions && uv run ruff check --fix -q migrations/versions   # expect no output
f=migrations/versions/0001_core_schema.py
grep -nE '^(revision|down_revision)' "$f"            # item 1: revision ... = "0001"; down_revision ... = None
grep -nE "gisdb\.|models\.|[^.]Text\(\)" "$f" || echo clean   # item 2: clean
for p in op.create_table sa.CheckConstraint ondelete= sa.UniqueConstraint op.create_index CURRENT_TIMESTAMP 'sa.DateTime(timezone=True)' 'with_variant(postgresql.JSONB()'; do printf '%-34s %s\n' "$p" "$(grep -cF "$p" "$f")"; done   # items 3-6, practice: 5, 12, 4, 3, 4, 5, 9, 2 (cut 9: 4 tables, fewer constraints)
sed -n '/def downgrade/,$p' "$f"                     # item 7: indexes and tables dropped in reverse dependency order, ingest_runs last
timeout 120 uv run alembic upgrade head && timeout 120 uv run alembic downgrade base && timeout 120 uv run alembic upgrade head && timeout 120 uv run alembic check   # item 8: ends with No new upgrade operations detected.
sed -i '1a Reviewed: checklist 1-8 OK' "$f" && grep -n "Reviewed:" "$f"   # 2:Reviewed: checklist 1-8 OK (inside the docstring)
gate                                                 # conventions grep clean … 5 passed
echo '| 46 | P2.1 | large | models, env.py, conftest, migration tests | gate lint; 0001 checklist 1-8; gate 5 passed | accepted |' >> AI_LOG.md
git add -A && git commit -qm "P2.1: models, env.py, fixtures; 0001 reviewed [AI: large]"
```

Review checklist (4 minutes; the commands above give the evidence):

1. The revision is `"0001"` with `down_revision = None`.
2. `grep -nE "gisdb\.|models\.|[^.]Text\(\)"` prints nothing (render_item worked).
3. 0001 creates exactly the 5 core tables (4 under cut 9).
4. Every PK, FK (with `ondelete`), UNIQUE, CHECK and index of the models is present, named with `op.f("...")`.
5. Server defaults are `sa.text("CURRENT_TIMESTAMP")`, never `now()`.
6. Timestamps are `sa.DateTime(timezone=True)`; JSON columns are `sa.JSON().with_variant(postgresql.JSONB(), "postgresql")`.
7. `downgrade()` drops indexes and tables in reverse dependency order.
8. The upgrade, downgrade to base, upgrade and check line ends with `No new upgrade operations detected.`

The ruff line runs before the review, so the gate never rewrites a reviewed migration and `verify.sh`'s `ruff format --check` passes. **Tripwire 47:** if 0001 is not applied with a clean `alembic check` by minute 47, hand-fix the file using this checklist (it is usually item 2 or 5) and defer `test_round_trip`.

#### Verify 2

```bash
timeout 120 uv run alembic current                   # 0001 (head)
timeout 120 uv run alembic downgrade base && timeout 120 uv run alembic upgrade head && timeout 120 uv run alembic check   # … No new upgrade operations detected.
grep -nE "gisdb\.|models\.|[^.]Text\(\)|now\(\)" migrations/versions/0001_core_schema.py || echo clean   # clean
grep -c "Reviewed:" migrations/versions/0001_core_schema.py   # 1
timeout 120 uv run pytest -q                         # 5 passed
```

#### If it fails

Empty autogenerate (the upgrade has no `create_table`):

```text
Autogenerate produced an empty migration. In migrations/env.py import Base from gisdb.models, set target_metadata = Base.metadata and take the URL from get_settings(). Change env.py only. Failure output (last 20 lines) follows:
```

`NameError` on upgrade:

```text
The upgrade fails with NameError. Add the render_item hook exactly as specified (UTCDateTime -> sa.DateTime(timezone=True); JSON -> sa.JSON().with_variant(postgresql.JSONB(), 'postgresql') plus the import; JSON is imported from sqlalchemy, not from the postgresql dialect). Change env.py only. Failure output (last 20 lines) follows:
```

After either fix, delete the generated `migrations/versions/0001_core_schema.py` and run Human step 2.b again.

#### Talking points

- Units live in column names; CHECKs are the last line of defense.
- Points are a child table: normalized and PostGIS-ready.
- Autogenerate drafted the migration and I reviewed it like a PR. It misses CHECK changes on existing tables, server defaults and renames.
- Surrogate integer keys plus a natural-key UNIQUE make the integer canonical-pair CHECK possible.

#### Checkpoint 2

```bash
sed -i 's/^- \[ \] Phase 2:/- [x] Phase 2:/' PLAN.md && grep -n '^- \[x\] Phase 2:' PLAN.md   # the line now reads - [x] Phase 2: Database models and migrations
git add -A && git commit -m "phase 2: models and reviewed migration 0001 [AI: P2.1 L; human: autogenerate, checklist review]"
```

## Phase 3 — JSON ingestion (48–73 min)

**Goal:** a validating, idempotent, audited `gisdb ingest`.   **Model:** large   **Done when:** run 1 and run 2 print the expected lines of Verify 3 and `pytest` gives 27 passed.

Chat: a fresh large-model chat, opened with the kickoff header; P3.1 and P3.2 share it.

Clock (see Time budget): tripwire 58 before sending P3.2, `tests/test_records.py` 16 passed, else send P3.2's cut-8 variant; tripwire 73, the second run is a no-op.

#### Prompt 3.1 — Record parsing and normalization (model: large)

```text
[P3.1 — Record parsing and normalization] (model: large)
READ: PLAN.md §1, §3, §5; DATA_PROFILE.md.
CHANGE ONLY: src/gisdb/records.py (new), tests/test_records.py (new).
TASK:
1. src/gisdb/records.py is pure: no database, no imports from gisdb.db or gisdb.models. Sources, per PLAN §3: trajectory records <TRAJECTORY_SOURCE=flights.json → "flights" list; key flight_id>; their points <POINT_SOURCE=positions[]: ts, coord, alt_ft>; zone records <ZONE_SOURCE=zones.json → GeoJSON "features" list (geometry Point); key = feature "id">; descriptive fields <TRAJECTORY_ATTRS=callsign → callsign, aircraft.icao_type → aircraft_type, origin → origin, destination → destination> and <ZONE_ATTRS=properties.name → name>.
2. Public names: RecordRejected(Exception), raised as RecordRejected(code, detail) and exposing .code and .detail; REASON_CODES = ("invalid_file", "missing_field", "invalid_value", "out_of_range", "invalid_timestamp", "too_few_points", "conflicting_points", "duplicate_key_conflict"); frozen dataclasses PointRecord(seq, ts, lat, lon, alt_m), TrajectoryRecord(trajectory_id, callsign, aircraft_type, origin, destination, started_at, ended_at, points: tuple[PointRecord, ...], content_hash) and ZoneRecord(zone_id, name, center_lat, center_lon, radius_km, content_hash); functions load_records(path) -> tuple[str, list[dict]], normalize_trajectory(raw) -> TrajectoryRecord, normalize_zone(raw) -> ZoneRecord, record_key(entity, raw) -> str | None, reason_from_validation_error(exc) -> str, content_hash(payload) -> str.
3. load_records(path) parses the file and detects its entity from the shapes of step 1: ("trajectory", the trajectory record list) or ("zone", the zone record list); invalid JSON or any other shape raises RecordRejected("invalid_file", ...). record_key(entity, raw) returns the natural key of step 1 when raw is a dict and the key is a non-empty string, else None.
4. Source models: Pydantic v2 with model_config = ConfigDict(extra="ignore"), one per source shape of step 1. Every optional field gets an explicit "= None" (in Pydantic v2, str | None without a default is still required). Timestamps are AwareDatetime (<TIME_FORMATS=ISO-8601 with Z or ±HH:MM offset, or integer Unix epoch seconds>: it accepts these and rejects naive strings); coordinate pairs are tuple[float, float]; the natural key is str with Field(min_length=1, max_length=64). Shapes: PositionIn(ts: AwareDatetime, coord: tuple[float, float], alt_ft: float | None = None); AircraftIn(icao_type: str | None = None); FlightIn(flight_id: str 1-64 chars, callsign: str | None = None, aircraft: AircraftIn | None = None, origin: str | None = None, destination: str | None = None, positions: list[PositionIn]); ZoneFeatureIn(id: str 1-64 chars, geometry: GeometryIn(type: Literal["Point"], coordinates: tuple[float, float]), properties: PropertiesIn(name: str | None = None, radius: float, radius_unit: str)).
5. Normalization, in this order; the first failure rejects the whole record (never repair a record or drop single points):
   a. model_validate. On ValidationError, reason_from_validation_error maps the first error, checking the rules in this order: type "missing", or any error whose input is None -> missing_field; a type starting with "datetime" or "timezone" -> invalid_timestamp; greater_than, greater_than_equal, less_than, less_than_equal -> out_of_range; anything else -> invalid_value.
   b. Positions: ts = ts.astimezone(UTC) (Pydantic keeps +02:00); unpack each pair in <COORD_ORDER=[lon, lat]> order; latitude outside [-90, 90] or longitude outside [-180, 180] -> out_of_range; then lon = ((lon + 180) % 360) - 180, so 180 becomes -180; altitude per <ALT_UNIT=alt_ft in feet (x 0.3048 -> alt_m), may be null>.
   c. Sort by ts; drop exact duplicate points (same ts, lat, lon, alt_m); two points left with the same ts -> conflicting_points; fewer than 2 points -> too_few_points; then seq = 0..n-1 and started_at / ended_at = the first / last ts.
   d. Zones: the centre pair in the same order with the same range rule; radius per <RADIUS_UNITS=properties.radius with properties.radius_unit "NM" (x 1.852) or "km">, the unit compared case-insensitively ("nm" x 1.852, "km" x 1.0); any other unit -> invalid_value; radius_km must satisfy 0 < radius_km < 10000, else out_of_range.
   e. content_hash(payload) = the sha256 hex digest of json.dumps(payload, sort_keys=True, separators=(",", ":"), default=lambda v: v.isoformat()). Trajectory payload: {trajectory_id, callsign, aircraft_type, origin, destination, points: [[ts, lat, lon, alt_m], ...]} after b and c. Zone payload: {zone_id, name, center_lat, center_lon, radius_km}. So epoch vs ISO, offset vs Z and unknown fields give the same hash.
6. tests/test_records.py: pure (no fixtures, no database); every input is built in the source format of step 1. The expected values are mine: never change them. Exactly these 16 test items:
   - test_coord_order_and_altitude: a position at lat 51.47, lon -0.4543, written in the source order (here [-0.4543, 51.47]), altitude 1000 ft -> lat 51.47, lon -0.4543, alt_m 304.8 (pytest.approx).
   - test_timestamps_to_utc: "2024-05-01T11:35:55+02:00" -> 2024-05-01T09:35:55Z; 1714543200 -> 2024-05-01T06:00:00Z.
   - test_points_sorted_and_deduplicated: positions at 09:10Z, 09:00Z and 09:05Z, in that order, plus an exact copy of the 09:05Z one -> 3 points in time order with seq 0, 1, 2, started_at 09:00Z, ended_at 09:10Z.
   - test_lon_180_normalized: longitude 180 -> -180.
   - test_zone_radius_units: 25 NM -> radius_km approx 46.3; 9.26 km -> 9.26.
   - test_hash_ignores_format: the same instants written as epoch ints, as ISO Z and as +02:00 offsets, one copy with an extra unknown field -> equal content_hash; a changed callsign -> a different hash.
   - test_optional_fields_absent: a record without callsign, aircraft, origin and destination is accepted, with callsign, aircraft_type, origin and destination all None.
   - test_rejections, parametrized over 9 cases, each asserting RecordRejected.code: natural key absent -> missing_field; natural key null -> missing_field; latitude 91.2 -> out_of_range; ts "2024-05-01T25:61:00Z" -> invalid_timestamp; naive ts "2024-05-01T09:00:00" -> invalid_timestamp; one position -> too_few_points; zone radius -5 NM -> out_of_range; zone unit "mi" -> invalid_value; the same ts at two different positions -> conflicting_points.
DONE WHEN: uv run pytest -q tests/test_records.py -> 16 passed
Agent rules: follow PLAN.md §1 Conventions. Change only the CHANGE ONLY files. Never edit tests to make them pass. Never run git. Reply with the changed files and the last 15 lines of any command you ran.
```

Practice values:

- `TRAJECTORY_SOURCE=flights.json → "flights" list; key flight_id`
- `POINT_SOURCE=positions[]: ts, coord, alt_ft`
- `ZONE_SOURCE=zones.json → GeoJSON "features" list (geometry Point); key = feature "id"`
- `TRAJECTORY_ATTRS=callsign → callsign, aircraft.icao_type → aircraft_type, origin → origin, destination → destination`
- `ZONE_ATTRS=properties.name → name`
- `TIME_FORMATS=ISO-8601 with Z or ±HH:MM offset, or integer Unix epoch seconds`
- `COORD_ORDER=[lon, lat]`
- `ALT_UNIT=alt_ft in feet (x 0.3048 -> alt_m), may be null`
- `RADIUS_UNITS=properties.radius with properties.radius_unit "NM" (x 1.852) or "km"`

Why large: silent data errors hide here (coordinate order, units, time zones). Commit message: `P3.1: record parsing and normalization [AI: large]`.

On the day, rewrite the "Shapes:" sentence of TASK step 4 from PLAN §3; it is the only practice-specific code shape in this prompt.

Then run the gate and log the prompt (top section).

**Tripwire 58** (before sending P3.2): `tests/test_records.py` must be 16 passed. If not, send Prompt 3.2 with its cut-8 variant (below).

#### Prompt 3.2 — Ingestion service, CLI, DB tests (model: large)

```text
[P3.2 — Ingestion service, CLI, DB tests] (model: large)
READ: PLAN.md §1, §3, §5, §7; src/gisdb/records.py; src/gisdb/models.py; src/gisdb/db.py; src/gisdb/cli.py; tests/conftest.py.
CHANGE ONLY: src/gisdb/ingest.py (new), src/gisdb/cli.py, tests/test_ingest.py (new).
TASK:
1. src/gisdb/ingest.py: run_ingest(paths: list[Path], session_factory=SessionLocal) -> dict, with log = structlog.get_logger(__name__) and the event names and fields of PLAN §7, exactly. A directory in paths expands to its *.json files sorted by name (not recursive); files are taken as given.
2. Transaction 1: insert IngestRun(status="running", files=[]), commit, keep its id; log ingest.run.started (ingest_run_id, paths).
3. Transaction 2 holds every data write of the run:
   a. Preload {trajectory_id: (id, content_hash)} and {zone_id: (id, content_hash)}, one select each; keep seen_in_run = {(entity, key): content_hash}.
   b. Per file: read the bytes and their sha256; entity, records = load_records(path); append {"path": str(path), "sha256": ..., "records": len(records)} to a files list; log ingest.file.read (ingest_run_id, file, sha256, records). If load_records raises RecordRejected (invalid_file): add one IngestRejection (entity "file", record_index None, record_key None, payload None) and append the file with records 0; seen += 1, rejected += 1; log ingest.record.rejected; go to the next file.
   c. Per record (record_index 0-based): seen += 1; key = record_key(entity, raw); then normalize_trajectory or normalize_zone:
      - RecordRejected: add IngestRejection(entity, source_file = the path as given, record_index, record_key = key, reason_code = exc.code, detail = exc.detail[:500], payload = raw); rejected += 1; log ingest.record.rejected (ingest_run_id, file, record_index, record_key, reason_code).
      - Key already in seen_in_run: the same content_hash -> duplicates += 1 and log ingest.record.duplicate (ingest_run_id, file, record_index, record_key); a different one -> reject it as duplicate_key_conflict, exactly as above (the first copy wins).
      - Otherwise set seen_in_run[(entity, key)] = content_hash and compare with the preload. Key not in the DB: insert, inserted += 1 (a trajectory: session.add(Trajectory(...)), session.flush() for its id, then session.execute(insert(TrajectoryPoint), rows)). Hash differs: update the scalar columns, content_hash, source_file, last_ingest_run_pk and updated_at = datetime.now(UTC), replace the points (step 4), updated += 1. Same hash: write nothing, unchanged += 1. Inserted and updated rows get source_file and last_ingest_run_pk = the run's id.
   d. Finally, on the run row, set the six counts, files (assign the new list: JSON columns do not track in-place changes), status="succeeded" and finished_at = datetime.now(UTC); commit; log ingest.run.finished (ingest_run_id, status, seen, inserted, updated, unchanged, duplicates, rejected, duration_ms).
4. Point replacement: never reassign trajectory.points. Use Core statements: session.execute(delete(TrajectoryPoint).where(TrajectoryPoint.trajectory_pk == pk)), session.flush(), then session.execute(insert(TrajectoryPoint), rows). Otherwise the unit of work can insert the new rows before deleting the old ones and collide on UNIQUE (trajectory_pk, ts).
5. On any exception: roll back; in a new session set status="failed", error=str(exc)[:500] and finished_at, and commit; log ingest.run.failed (ingest_run_id, error); re-raise.
6. run_ingest returns {"ingest_run_id", "status", "seen", "inserted", "updated", "unchanged", "duplicates", "rejected"}, keys in this order.
7. src/gisdb/cli.py (keep serve unchanged): "ingest" takes PATH arguments (nargs="*", default ["<DATA_DIR=data>"]), calls run_ingest, writes exactly one line with sys.stdout.write(json.dumps(result) + "\n") and returns 0 if status == "succeeded", else 1 (an exception propagates: exit code 1). "stats" writes one line, json.dumps({table.name: row count for table in Base.metadata.sorted_tables}, sort_keys=True). Logs stay on stderr.
8. tests/test_ingest.py, exactly 6 tests. Each uses the db, write_json and tmp_path fixtures and calls run_ingest([tmp_path], SessionLocal). The mini files use the source format that records.load_records accepts: a trajectory file with 3 valid records (3 points each) + an exact copy of one of them + 1 record with latitude 95, and a zone file with 2 valid records. The expected values are mine: never change them.
   - test_first_run_counts: seen 7, inserted 5, updated 0, unchanged 0, duplicates 1, rejected 1; exactly one rejection row, reason_code out_of_range, with its payload stored.
   - test_second_run_is_noop: the second run: inserted 0, updated 0, unchanged 5, duplicates 1, rejected 1.
   - test_changed_record_updates: change a valid record that has no copy in the file (a changed copy would become duplicate_key_conflict): a new callsign and one point fewer -> updated 1, unchanged 4, and the stored point_count drops by 1.
   - test_format_only_change_is_unchanged: the same instants rewritten as epoch seconds instead of ISO strings -> unchanged 5.
   - test_conflicting_duplicate_rejected: the same key twice with different content -> one rejection duplicate_key_conflict; the first copy is stored.
   - test_accounting_identity: run the mini files twice, then once more after a change; every run has status "succeeded" and seen == inserted + updated + unchanged + duplicates + rejected.
   Also reply with the exact counts your tests expect.
DONE WHEN: uv run pytest -q -> 27 passed
Agent rules: follow PLAN.md §1 Conventions. Change only the CHANGE ONLY files. Never edit tests to make them pass. Never run git. Reply with the changed files and the last 15 lines of any command you ran.
```

Practice values: `DATA_DIR=data`

Why large: transactions, idempotency and run accounting. Commit message: `P3.2: ingestion service, ingest and stats CLI, DB tests [AI: large]`.

Cut-8 variant (when tripwire 58 fails, or when you take cut 8 by minute 58): insert this paragraph into the prompt, just before its DONE WHEN line: "FULL-REFRESH VARIANT (overrides step 3a, the update path of step 3c, step 4 and the expected values of tests 2-4): no preload, no hash comparison, no update path. At the start of transaction 2, delete all stored trajectories and zones with Core delete statements (their points cascade). Then insert every valid record whose key was not seen earlier in this run (inserted += 1); updated and unchanged stay 0, so a run must include every file. Duplicates, duplicate_key_conflict and rejections work as before. test_second_run_is_noop, test_changed_record_updates and test_format_only_change_is_unchanged assert the stored rows and row counts (the same 5 rows after a re-run; the new callsign and point_count after the change; the same rows after the epoch rewrite) instead of updated/unchanged counts."

Cut 9 (taken at minute 31): insert, just before the DONE WHEN line, "There is no ingest_rejections table: log each rejection (ingest.record.rejected) and count it; the tests assert counts, not rejection rows."

Then run the gate and log the prompt (top section).

#### Verify 3

```bash
timeout 120 uv run alembic downgrade base && timeout 120 uv run alembic upgrade head   # resets the dev DB; ends with Running upgrade  -> 0001, core schema
uv run gisdb ingest "$DATA_DIR" 2>/dev/null          # {"ingest_run_id": 1, "status": "succeeded", "seen": 26, "inserted": 20, "updated": 0, "unchanged": 0, "duplicates": 1, "rejected": 5}
uv run gisdb ingest "$DATA_DIR" 2>/dev/null          # {"ingest_run_id": 2, "status": "succeeded", "seen": 26, "inserted": 0, "updated": 0, "unchanged": 20, "duplicates": 1, "rejected": 5} (cut 8: "inserted": 20, "unchanged": 0)
uv run gisdb stats 2>/dev/null                       # {"ingest_rejections": 10, "ingest_runs": 2, "trajectories": 10, "trajectory_points": 184, "zones": 10} (cut 9: no ingest_rejections key)
uv run python -c "from sqlalchemy import select; from gisdb.db import SessionLocal; from gisdb.models import IngestRejection as R; print(SessionLocal().execute(select(R.record_index, R.record_key, R.reason_code).where(R.ingest_run_pk == 1).order_by(R.id)).all())"   # [(10, 'FLT-1011', 'too_few_points'), (11, 'FLT-1012', 'out_of_range'), (12, 'FLT-1013', 'invalid_timestamp'), (13, None, 'missing_field'), (10, 'ZN-CHANNEL', 'out_of_range')] (skip under cut 9)
timeout 120 uv run pytest -q                         # 27 passed
```

**Tripwire 73:** run 2 must be a no-op (inserted 0, updated 0) and `stats` must show the same entity counts as after run 1. Duplicate rows or a failed run: send the prompt below. Otherwise (for example `updated 20`) ship it, apply cut 8's "Also change" lines to `verify.sh` and NOTES, and note it in NOTES "Known limitations".

#### If it fails

```text
The second ingest run must be a no-op. Compare the content_hash of the normalized record with the stored one before writing; skip unchanged records; replace points (Core delete, flush, insert) only when the hash changed. Change src/gisdb/ingest.py only; do not touch tests. Failure output (last 20 lines) follows:
```

P3.1's parsing tests fail instead: send "Fix src/gisdb/records.py only; the expected values in tests/test_records.py stay. Check the error-mapping rules in their order (missing or input None first) and convert ts with astimezone(UTC). Failure output (last 20 lines) follows:" with the tail to the same chat.

#### Talking points

- Natural key plus normalized hash: re-runs are no-ops, and format-only changes stay unchanged.
- The run row is committed first, and the accounting CHECK is enforced by the DB.
- I reject whole records rather than silently drop points, and I never "fix" swapped coordinates.

#### Checkpoint 3

```bash
sed -i 's/^- \[ \] Phase 3:/- [x] Phase 3:/' PLAN.md && grep -n '^- \[x\] Phase 3:' PLAN.md   # the line now reads - [x] Phase 3: JSON ingestion
git add -A && git commit -m "phase 3: idempotent auditable ingestion [AI: P3.1 L, P3.2 L; human: rerun proof]"
```

## Phase 4 — Read-only API (73–93 min)

**Goal:** paginated list, detail and points endpoints with response models; the analysis fields are present, and null, from now on.   **Model:** mixed   **Done when:** `tests/test_api.py` gives 8 passed (suite 35) and the `api_get.py` checks of Verify 4 match.

Chats: P4.1 in a fresh large-model chat, P4.2 in a fresh small-model chat, each opened with the kickoff header (see Prompt contract, kickoff header and gate).

Clock (see Time budget): cut 2 before sending P4.1 (minute 73); tripwire 90, the trajectory list, detail, 404 and 422 tests green, else skip P4.2.

#### Prompt 4.1 — Trajectory endpoints, the pattern (model: large)

```text
[P4.1 — Trajectory endpoints, the pattern] (model: large)
READ: PLAN.md §1 Conventions and §6 API; src/gisdb/models.py; src/gisdb/db.py; src/gisdb/api/app.py; tests/conftest.py.
CHANGE ONLY: src/gisdb/api/schemas.py (new), src/gisdb/api/deps.py (new), src/gisdb/api/routes.py (new), src/gisdb/api/app.py, tests/test_api.py (new)
TASK:
1. deps.py: SessionDep = Annotated[Session, Depends(get_session)], with get_session from gisdb.db.
2. schemas.py: Pydantic v2 response models with exactly these fields. Models built from ORM rows use model_config = ConfigDict(from_attributes=True). Datetime fields are datetime; UTC values serialize with a trailing Z. No model ever has an internal id or *_pk field.
   - Page(BaseModel, Generic[T]): items: list[T], total: int, limit: int, offset: int
   - HealthOut: status: str, database: str
   - PointOut: seq: int, ts: datetime, lat: float, lon: float, alt_m: float | None
   - PassEndpointOut: kind: str, lat: float, lon: float, time: datetime, alt_m: float | None
   - ZonePassOut: trajectory_id: str, zone_id: str, seq: int, entry: PassEndpointOut, exit: PassEndpointOut, distance_inside_km: float, duration_s: float
   - IntersectionOut: other_trajectory_id: str, seq: int, kind: str, lat: float, lon: float, time_self: datetime, time_other: datetime, time_gap_s: float, alt_self_m: float | None, alt_other_m: float | None
   - TrajectoryAnalysisOut: length_km: float, length_3d_km: float | None, duration_s: float, zone_pass_count: int, intersection_count: int, analyzed_at: datetime, algorithm_version: str, earth_radius_km: float, stale: bool
   - TrajectorySummary: trajectory_id: str; one str | None field per descriptive trajectory column of <TRAJECTORY_ATTRS=callsign → callsign, aircraft.icao_type → aircraft_type, origin → origin, destination → destination> (the names right of each arrow); started_at: datetime; ended_at: datetime; point_count: int; analysis: TrajectoryAnalysisOut | None = None
   - TrajectoryDetail(TrajectorySummary): zone_passes: list[ZonePassOut] = [], intersections: list[IntersectionOut] = []
   - ZoneCenter: lat: float, lon: float
   - ZoneAnalysisOut: pass_count: int, trajectory_count: int, analyzed_at: datetime
   - ZoneSummary: zone_id: str; one str | None field per descriptive zone column of <ZONE_ATTRS=properties.name → name> (the names right of each arrow); center: ZoneCenter; radius_km: float; analysis: ZoneAnalysisOut | None = None
   - ZoneDetail(ZoneSummary): passes: list[ZonePassOut] = []
   - ZoneSummary has a @model_validator(mode="before") classmethod: when the input is not a dict (an ORM Zone row), it returns a dict with zone_id, the descriptive zone columns, center = {"lat": obj.center_lat, "lon": obj.center_lon} and radius_km. ZoneDetail inherits it, so ZoneSummary.model_validate(row) and ZoneDetail.model_validate(row) both work.
3. routes.py: trajectories_router = APIRouter(prefix="/trajectories", tags=["trajectories"]). Plain def endpoints with a session: SessionDep parameter; queries use select() with session.scalars() / session.scalar().
   - GET with path "" (the URL is exactly /trajectories) -> Page[TrajectorySummary]. Query params: limit: Annotated[int, Query(ge=1, le=500)] = 50; offset: Annotated[int, Query(ge=0)] = 0; started_after: Annotated[AwareDatetime | None, Query()] = None; started_before: Annotated[AwareDatetime | None, Query()] = None (a naive datetime gives 422). Filters: started_at >= started_after, started_at < started_before. ORDER BY trajectory_id. total = session.scalar(select(func.count()).select_from(stmt.subquery())) over the same filtered statement, before ORDER BY/LIMIT/OFFSET. Load no relationships; analysis stays None.
   - GET "/{trajectory_id}" -> TrajectoryDetail (analysis None, empty lists). Unknown id: raise HTTPException(status_code=404, detail=f"trajectory '{trajectory_id}' not found").
   - GET "/{trajectory_id}/points" -> Page[PointOut] with the same limit/offset params, ORDER BY seq, total = the trajectory's point count; the same 404 for an unknown id.
4. app.py, inside create_app() only: app.include_router(trajectories_router) and app.add_middleware(CORSMiddleware, allow_origins=get_settings().cors_origins, allow_methods=["GET"], allow_headers=["*"], expose_headers=["X-Request-ID"]); give the existing /health route response_model=HealthOut (its body and its 503 JSONResponse stay as they are). Change nothing else in app.py.
5. tests/test_api.py, using the client and make_trajectory fixtures of tests/conftest.py. A helper seeds three trajectories in this order (points are (iso_ts, lat, lon, alt_m)):
   T-C: ("2024-05-01T10:00:00Z", 0.0, 0.0, None), ("2024-05-01T10:10:00Z", 0.0, 1.0, None)
   T-A: ("2024-05-01T08:00:00Z", 10.0, 10.0, 0.0), ("2024-05-01T08:10:00Z", 10.0, 11.0, 300.0), ("2024-05-01T08:20:00Z", 10.0, 12.0, 600.0)
   T-B: ("2024-05-01T12:00:00Z", 20.0, 20.0, None), ("2024-05-01T12:10:00Z", 20.0, 21.0, None)
   Write exactly these 6 tests; pass query values with client.get(path, params={...}):
   - test_list_pagination: limit=2 -> items T-A, T-B; total 3, limit 2, offset 0. limit=2, offset=2 -> items [T-C], total 3.
   - test_list_limit_validation: limit=0, limit=501 and offset=-1 each -> 422.
   - test_detail_404: /trajectories/NOPE and /trajectories/NOPE/points -> 404 with body exactly {"detail": "trajectory 'NOPE' not found"}.
   - test_detail_before_analysis: /trajectories/T-A -> 200; analysis is None; zone_passes == []; intersections == []; started_at == "2024-05-01T08:00:00Z"; ended_at == "2024-05-01T08:20:00Z"; point_count == 3; "id" is not a key of the body.
   - test_points_ordered: /trajectories/T-A/points -> seq [0, 1, 2], total 3, first ts "2024-05-01T08:00:00Z"; limit=1, offset=2 -> one item, seq 2.
   - test_started_filters: started_after "2024-05-01T09:00:00Z" -> T-B, T-C (total 2); started_before "2024-05-01T11:00:00Z" -> T-A, T-C; started_after "2024-05-01T11:00:00+02:00" (09:00Z) -> T-B, T-C; started_after "2024-05-01T09:00:00" (naive) -> 422.
DONE WHEN: uv run pytest -q tests/test_api.py -> 6 passed
Agent rules: follow PLAN.md §1 Conventions. Change only the CHANGE ONLY files. Never edit tests to make them pass. Never run git. Reply with the changed files and the last 15 lines of any command you ran.
```

Practice values:

- `TRAJECTORY_ATTRS=callsign → callsign, aircraft.icao_type → aircraft_type, origin → origin, destination → destination`
- `ZONE_ATTRS=properties.name → name`

Why large: it sets the response contract and the query pattern (pagination, COUNT total, 404 text) that P4.2 and P6.5 copy. Commit message: `P4.1: trajectory endpoints and response models [AI: large]`.

Then run the gate and log the prompt (top section).

Cut 2 (decide by minute 73, before sending): delete the `started_after`/`started_before` params, the filter sentence and `test_started_filters` from the prompt; it then writes 5 tests and expects `5 passed`.

#### Prompt 4.2 — Zone endpoints (model: small)

```text
[P4.2 — Zone endpoints] (model: small)
READ: PLAN.md §6 API; src/gisdb/api/routes.py; src/gisdb/api/schemas.py; tests/test_api.py; tests/conftest.py (its make_zone fixture).
CHANGE ONLY: src/gisdb/api/routes.py, src/gisdb/api/app.py, tests/test_api.py
TASK: copy the trajectories pattern in routes.py exactly: the same Annotated limit/offset params, the same COUNT for total, the same 404 style, plain def endpoints with SessionDep. Do not change existing routes, schemas or tests.
1. routes.py: zones_router = APIRouter(prefix="/zones", tags=["zones"]).
   - GET with path "" -> Page[ZoneSummary]; limit/offset as for trajectories; ORDER BY zone_id; items built with ZoneSummary.model_validate(row) (its validator builds center).
   - GET "/{zone_id}" -> ZoneDetail.model_validate(row). Unknown id: raise HTTPException(status_code=404, detail=f"zone '{zone_id}' not found").
2. app.py: include zones_router in create_app(), next to trajectories_router. Change nothing else.
3. tests/test_api.py: append exactly 2 tests. Seed make_zone("Z-B", 10.0, 20.0, 46.3), then make_zone("Z-A", -5.5, 179.5, 9.26). Pass query values with params={...}.
   - test_zones_list_and_detail: /zones -> items Z-A, Z-B, total 2; limit=1, offset=1 -> one item Z-B, total 2; /zones/Z-B -> 200, center == {"lat": 10.0, "lon": 20.0}, radius_km == 46.3, analysis is None, passes == [], "id" is not a key of the body.
   - test_zone_404: /zones/NOPE -> 404 with body exactly {"detail": "zone 'NOPE' not found"}.
DONE WHEN: uv run pytest -q tests/test_api.py -> 8 passed
Agent rules: follow PLAN.md §1 Conventions. Change only the CHANGE ONLY files. Never edit tests to make them pass. Never run git. Reply with the changed files and the last 15 lines of any command you ran.
```

Practice values: none (no placeholders).

Why small: a pattern copy with an exact route list; the tests catch drift. Commit message: `P4.2: zone endpoints [AI: small]`.

Then run the gate and log the prompt (top section).

#### Verify 4

```bash
timeout 120 uv run pytest -q tests/test_api.py                         # 8 passed
grep -nE '^\s+(id|[a-z_]+_pk)\s*:' src/gisdb/api/schemas.py || echo "no internal ids"   # no internal ids
uv run python scripts/api_get.py "/trajectories?limit=2" 2>/dev/null | grep -oE '^[0-9]{3}|"total":[0-9]+|"trajectory_id":"[^"]+"' | paste -sd' '   # 200 "trajectory_id":"FLT-1001" "trajectory_id":"FLT-1002" "total":10
uv run python scripts/api_get.py /trajectories/NOPE 2>/dev/null         # 404 /trajectories/NOPE {"detail":"trajectory 'NOPE' not found"}
uv run python scripts/api_get.py "/trajectories?limit=0" 2>/dev/null | cut -d' ' -f1,2   # 422 /trajectories?limit=0
uv run python scripts/api_get.py "/zones/$SAMPLE_ZONE" 2>/dev/null | grep -oE '^[0-9]{3}|"center":\{[^}]*\}|"radius_km":[0-9.]+' | paste -sd' '   # 200 "center":{"lat":90.0,"lon":0.0} "radius_km":138.9  (75 NM, [lon, lat] read correctly)
# Practice-data ids below; on the day use equivalents from DATA_PROFILE.md (last page, an offset timestamp, a shuffled track) or skip them:
uv run python scripts/api_get.py "/trajectories?limit=2&offset=9" 2>/dev/null | grep -oE '^[0-9]{3}|"total":[0-9]+|"trajectory_id":"[^"]+"' | paste -sd' '   # 200 "trajectory_id":"FLT-1010" "total":10
uv run python scripts/api_get.py /trajectories/FLT-1009 2>/dev/null | grep -oE '"started_at":"[^"]+"'   # "started_at":"2024-05-01T09:35:55Z"  (+02:00 in the source, stored as UTC)
uv run python scripts/api_get.py "/trajectories/FLT-1006/points?limit=1" 2>/dev/null | grep -oE '"seq":[0-9]+|"ts":"[^"]+"|"total":[0-9]+' | paste -sd' '   # "seq":0 "ts":"2024-05-01T02:00:00Z" "total":8  (shuffled in the source, sorted on ingest)
timeout 120 uv run pytest -q                                           # 35 passed
```

The `api_get.py` lines read the dev database that Verify 3 filled. Under cuts: cut 2 gives `7 passed` and suite 34; P4.2 skipped at tripwire 90 gives `6 passed` and suite 33, and the `/zones` line is dropped.

#### If it fails

```text
The Phase 4 API checks fail: limit=0 returns 200, or total equals len(items). Make limit Annotated[int, Query(ge=1, le=500)] = 50 and compute total with SELECT COUNT over the same filtered query before limit/offset (select(func.count()).select_from(stmt.subquery())). Change src/gisdb/api/routes.py only; do not touch tests. Failure output (last 20 lines) follows:
```

For a 500 with `ResponseValidationError` instead, send: "Responses fail validation. Models built from rows need ConfigDict(from_attributes=True) and are built with model_validate(row) inside the endpoint, while the session is open; ZoneSummary's model_validator(mode="before") builds center from center_lat and center_lon. Change src/gisdb/api/schemas.py and src/gisdb/api/routes.py only; do not touch tests. Failure output (last 20 lines) follows:"

#### Talking points

- Response models decouple the API from the ORM; internal ids never leak, and the schemas grep proves it.
- The contract came first: the analysis fields exist now as null, so the client sees no breaking change when the analysis lands. Null means "not analyzed", distinct from zero counts.
- Offset pagination with a COUNT total over a stable ORDER BY suits a web table; keyset pagination is the next step for large tables.
- The large model set the pattern and the small model copied it: one consistent API for a fraction of the tokens.

#### Checkpoint 4

```bash
sed -i 's/^- \[ \] Phase 4:/- [x] Phase 4:/' PLAN.md && grep -n '^- \[x\] Phase 4:' PLAN.md   # the line now reads - [x] Phase 4: Read-only API
git add -A && git commit -m "phase 4: read-only API [AI: P4.1 L, P4.2 S; human: contract review]"
```

## Phase 5 — Structured logging (93–103 min)

**Goal:** JSON logs everywhere, request IDs, uvicorn routed through the same JSON, and a JSON 500.   **Model:** small   **Done when:** `tests/test_logging.py` gives 3 passed (suite 38) and the `http.request` line carries `request_id` `verify-5`.

Chat: P5.1 in a fresh small-model chat, opened with the kickoff header; use a large-model chat instead if calibration at minute 30 moved P5.1 (see Model routing). P5.1 escalates to the large model on its first failure.

Clock (see Time budget): tripwire 105, analysis must have started; if this phase overruns, keep what is green (basic JSON logs plus the middleware) and send P6.1.

#### Prompt 5.1 — Logging and middleware (model: small)

```text
[P5.1 — Logging and middleware] (model: small)
READ: PLAN.md §1 Conventions and §7 Logging; src/gisdb/logging_config.py; src/gisdb/api/app.py; src/gisdb/cli.py; tests/conftest.py.
CHANGE ONLY: src/gisdb/logging_config.py, src/gisdb/api/app.py, tests/test_logging.py (new)
TASK:
1. logging_config.py: configure_logging(level) keeps its signature; replace its body with this recipe (structlog's stdlib integration):
   shared = [structlog.contextvars.merge_contextvars, structlog.stdlib.add_log_level, structlog.stdlib.add_logger_name, structlog.processors.TimeStamper(fmt="iso", utc=True)]
   structlog.configure(processors=[*shared, structlog.processors.StackInfoRenderer(), structlog.stdlib.ProcessorFormatter.wrap_for_formatter], logger_factory=structlog.stdlib.LoggerFactory(), wrapper_class=structlog.stdlib.BoundLogger, cache_logger_on_first_use=False)
   formatter = structlog.stdlib.ProcessorFormatter(foreign_pre_chain=shared, processors=[structlog.stdlib.ProcessorFormatter.remove_processors_meta, structlog.processors.format_exc_info, structlog.processors.JSONRenderer()])
2. Root handler: remove any root handler that has the attribute _gisdb_handler; add one logging.StreamHandler(sys.stderr) with _gisdb_handler = True and that formatter; set the root level to level. NEVER assign root.handlers (it empties pytest's caplog).
3. For the loggers "uvicorn", "uvicorn.error" and "uvicorn.access": clear their handlers and set propagate = True. Set "uvicorn.access" to WARNING (the middleware logs requests) and "httpx" to WARNING (TestClient's per-request INFO lines).
4. Keep create_app() calling configure_logging(get_settings().log_level), which runs at import time through app = create_app(). cli.py must already call configure_logging in main() and run uvicorn.run(..., log_config=None, access_log=False) for serve; if it does not, stop and tell me (cli.py is not in CHANGE ONLY).
5. app.py, inside create_app(): @app.middleware("http") async def request_context(request, call_next). The middleware is async def with await call_next(request) because Starlette requires it; endpoints stay plain def.
   a. rid = the X-Request-ID request header if it fully matches ^[A-Za-z0-9._-]{1,64}$, else uuid.uuid4().hex.
   b. structlog.contextvars.clear_contextvars(), then bind_contextvars(request_id=rid, method=request.method, path=request.url.path).
   c. start = time.perf_counter(). Wrap only the call_next call in try/except Exception: call log.exception("http.unhandled_error") and use JSONResponse({"detail": "internal server error", "request_id": rid}, status_code=500) as the response (no traceback in the body).
   d. Set response.headers["X-Request-ID"] = rid on every response, the 500 included.
   e. log.info("http.request", status_code=response.status_code, duration_ms=round((time.perf_counter() - start) * 1000, 1)); then clear_contextvars() and return the response.
6. tests/test_logging.py (fixture client). Read logs only through pytest's caplog: caplog.set_level("INFO"); events = [r.msg for r in caplog.records if isinstance(r.msg, dict)]. Never use structlog.testing.capture_logs, capsys or root.handlers =.
   - test_request_id_logged: GET /health with header X-Request-ID: test-123 -> response header X-Request-ID == "test-123"; one event has event "http.request", request_id "test-123", status_code 200, a duration_ms key, level "info" and a timestamp ending in "Z".
   - test_invalid_request_id_replaced: header X-Request-ID: "bad id with spaces" -> the response header X-Request-ID is 32 lowercase hex characters.
   - test_unhandled_error_json: inside the test, app.add_api_route("/test-boom", ...) with an endpoint that raises RuntimeError("boom"); GET /test-boom -> 500 and body == {"detail": "internal server error", "request_id": the response's X-Request-ID header}; an event "http.unhandled_error" with level "error" was logged.
DONE WHEN: uv run pytest -q tests/test_logging.py -> 3 passed
Agent rules: follow PLAN.md §1 Conventions. Change only the CHANGE ONLY files. Never edit tests to make them pass. Never run git. Reply with the changed files and the last 15 lines of any command you ran.
```

Practice values: none (no placeholders).

Why small: a known recipe given almost verbatim, with the traps named; it escalates to the large model on its first failure. Commit message: `P5.1: JSON logging, request-id middleware, JSON 500 [AI: small]`.

Then run the gate and log the prompt (top section).

#### Verify 5

```bash
timeout 120 uv run pytest -q tests/test_logging.py                     # 3 passed
uv run python scripts/api_get.py --request-id verify-5 /health 2>&1 >/dev/null | grep '"http.request"'   # one JSON line: "request_id": "verify-5", "status_code": 200, "duration_ms": ..., "level": "info", "timestamp" ending in Z
uv run gisdb ingest "$DATA_DIR" 2>/tmp/ingest5.log >/dev/null; tail -n 1 /tmp/ingest5.log   # the "ingest.run.finished" JSON line with "inserted": 0, "updated": 0, "unchanged": 20
python3 -c 'import json; [json.loads(s) for s in open("/tmp/ingest5.log") if s.strip()]; print("all JSON")'   # all JSON
timeout 120 uv run pytest -q                                           # 38 passed
```

No server runs here; `scripts/smoke.py` proves uvicorn's JSON output in Phase 7. Under cuts: cut 8 (full refresh) shows `"inserted": 20` on the finished line; cut 2 gives suite 37; P4.2 skipped gives suite 36.

#### If it fails

P5.1 escalates on its first failure (see Model routing): stage everything (`git add -A`), open a fresh large-model chat with the kickoff header and re-send Prompt 5.1 with the failure tail (at most 20 lines). If the large model's attempt fails too, send this follow-up in that chat with the new tail:

```text
Log lines are not JSON, or http.request lacks request_id. Use structlog's stdlib LoggerFactory with ProcessorFormatter on ONE root handler marked _gisdb_handler (never assign root.handlers). Bind request_id with structlog.contextvars in the middleware before call_next. Tests read caplog records whose msg is a dict. Change logging_config.py, app.py and test_logging.py only. Failure output (last 20 lines) follows:
```

#### Talking points

- One request ID correlates every line of a request, and `X-Request-ID` echoes it to the client on every response, 404, 422 and 500 included.
- Event names are a stable contract (PLAN §7); dashboards and alerts key off them, never off message text.
- Logs carry ids and counts, never payloads or coordinate arrays.
- Logs go to stderr and CLI results to stdout, so `2>/dev/null` gives a clean result line.
- I test logs through caplog: structlog's `capture_logs` drops contextvars, `capsys` sees nothing, and assigning `root.handlers` empties caplog. Knowing that kept the model from writing a test that passes for the wrong reason.

#### Checkpoint 5

```bash
sed -i 's/^- \[ \] Phase 5:/- [x] Phase 5:/' PLAN.md && grep -n '^- \[x\] Phase 5:' PLAN.md   # the line now reads - [x] Phase 5: Structured logging
git add -A && git commit -m "phase 5: structured logging with request ids [AI: P5.1 S; human: log review]"
```

## Phase 6 — Geospatial analysis (103–153 min)

**Goal:** a verified geodesy core; results persisted idempotently through migration 0002 and exposed by the API.   **Model:** mixed   **Done when:** the geodesy tests are green and `tests/test_geodesy.py` was never edited after P6.1; 0002 is reviewed; `analyze` twice gives 14 passes and 9 intersections; the API shows the analysis; the suite has ≥ 63 passed.

Five gate commits: P6.1, P6.2, P6.3 together with Human step 6.a, P6.4, P6.5. They group into 6a math (P6.1, P6.2), 6b persistence (P6.3 with H6.a, P6.4) and 6c API (P6.5).

Chats: P6.1 in a fresh large-model chat; P6.2 and P6.3 in one fresh small-model chat; P6.4 and P6.5 in one fresh large-model chat; each opens with the kickoff header. If calibration at minute 30 moved P6.2 to the large model, send it in a fresh large-model chat and P6.3 in a fresh small-model chat.

Clock (see Time budget): cut 6 before P6.1 (minute 103); tripwire 105, P6.1 sent; cut 5 before P6.2 (118); tripwire 120, `tests/test_geodesy.py` green, else cut 7; cut 3 before P6.3 (124); tripwire 135, P6.4 started; cut 1 before P6.5 (143); tripwire 152, analysis fields visible in `GET /trajectories/{trajectory_id}`.

Before P6.1: the T1–T11 values, the oracle's sphere (6371008.8 m) and the 222.390160 km test values assume R = 6371.0088 km. If PLAN §8 records another radius, ask the interviewer first; if it must change, recompute those values before sending P6.1 (see Appendix E — Adapting to the real brief, E.4). If PLAN §8's `TOL_KM` exceeds 0.004 km, adjust T5 first (see Appendix E — Adapting to the real brief, E.3).

#### Prompt 6.1 — Geodesy core and analytic tests (model: large)

```text
[P6.1 — Geodesy core and analytic tests] (model: large)
READ: PLAN.md §1 Conventions and §8 Analysis. The specification and the test table are below; read no other file.
CHANGE ONLY: src/gisdb/geodesy.py (new), tests/test_geodesy.py (new)
TASK:
1. Write the tests FIRST, exactly from the table, then the implementation: tests/test_geodesy.py has at least one test function per row T1-T11, with every expected value exactly as written.
2. Then write src/gisdb/geodesy.py exactly to the specification. Standard library only (math, dataclasses, datetime): no numpy, shapely or pyproj, no DB code, no imports from gisdb. Each function gets a docstring of at most 4 lines.
3. Test inputs are (lat, lon) in degrees. Path functions take TrackPoint lists; interpolate, segment_circle_interval and segment_intersections take n-vectors from to_nvec, and their results convert back with from_nvec.
4. Run uv run pytest -q tests/test_geodesy.py and uv run ruff check src tests; fix until green. Do NOT loosen a tolerance or change an expected value to make a test pass. If you believe a value is wrong, stop and tell me.

SPECIFICATION
Model and conventions
- Sphere: EARTH_RADIUS_KM = <EARTH_RADIUS_KM=6371.0088>. TOL_KM = <TOL_KM=0.001> (1 m) for every boundary, tangency, overlap and dedupe decision; TOL_RAD = TOL_KM / EARTH_RADIUS_KM; ZERO_RAD = 1e-12 (shorter segments are "stationary").
- Internally every position is an n-vector (unit 3-vector). NEVER interpolate, average or subtract raw lat/lon. Convert to lat/lon only for output.
- Fractions f along a segment are fractions of ARC LENGTH; time and altitude at f are linear: t = t0 + f*(t1 - t0).
- Segments are minor arcs (< 180 deg). Circles need 0 < radius_km < 10000.

Types: @dataclass(frozen=True) TrackPoint(lat, lon, time: datetime | None = None, alt_m: float | None = None);
ZonePass(seq, entry_kind, exit_kind, entry_lat, entry_lon, entry_time, entry_alt_m, exit_lat, exit_lon, exit_time, exit_alt_m, distance_inside_km, duration_s | None);
TrackHit(kind, lat, lon, seg_a, seg_b, dist_along_a_km, dist_along_b_km, time_a, time_b, alt_a_m, alt_b_m).

1 to_nvec(lat, lon) = (cos(phi)cos(lam), cos(phi)sin(lam), sin(phi)); from_nvec(v) = (deg(atan2(z, hypot(x, y))), normalize_lon(deg(atan2(y, x)))); normalize_lon(x) = ((x + 180) % 360) - 180.
2 angle(a, b) = atan2(|a x b|, a . b)   [radians, accurate from 0 to pi; never acos(a . b)]
3 distance_km(lat1, lon1, lat2, lon2) = R * angle(...). haversine_km(...): h = sin^2(dphi/2) + cos(phi1)cos(phi2)sin^2(dlam/2); clamp h to [0, 1]; return 2R*atan2(sqrt(h), sqrt(1-h)). (An independent formula, used to cross-check.)
4 path_length_km(points) = sum of consecutive distance_km (0 for < 2 points). path_length_3d_km(points) = sum of hypot(theta*(R + (h1+h2)/2000), (h2-h1)/1000) with h in metres; None if any alt_m is None. (Not the straight ECEF chord: it tunnels through the Earth.)
5 interpolate(a, b, f): theta = angle(a, b); if theta < ZERO_RAD return a; n = unit(a x b); u = n x a; return a*cos(f*theta) + u*sin(f*theta).
6 segment_circle_interval(a, b, c, radius_km) -> (f0, f1, is_touch) | None   [the part of arc a->b inside the closed disc]
   rho = radius_km/R; theta = angle(a, b)
   if theta < ZERO_RAD: return (0.0, 1.0, False) if angle(a, c) <= rho else None
   n = unit(a x b); u = n x a; A = a.c; B = u.c; C = n.c
   xt  = atan2(|C|, hypot(A, B))   # angular distance from c to the great circle
   tau = atan2(B, A)               # angle from a (towards b) of the point nearest c
   if xt > rho + TOL_RAD: return None
   if xt >= rho - TOL_RAD:         # tangent band
       t = tau mod 2pi; return (t/theta, t/theta, True) if t <= theta else None
   delta = acos(min(1, cos(rho)/cos(xt)))      # spherical Pythagoras: cos rho = cos xt * cos delta
   for s in (0, 2pi, -2pi): t0 = max(0, tau-delta+s); t1 = min(theta, tau+delta+s); if t0 <= t1: return (t0/theta, t1/theta, False)
   return None
7 circle_passes(points, center_lat, center_lon, radius_km) -> list[ZonePass]
   - 0 points: []. 1 point: inside -> one pass track_start -> track_end (0 km, 0 s), else [].
   - Walk the segments in order, calling 6. Extend the open pass with segment i's interval iff the open pass ended on segment i-1 with (1-f1)*len(i-1) <= TOL_KM AND f0*len(i) <= TOL_KM; otherwise start a new pass. (A vertex on the boundary never splits or duplicates a pass; a stationary segment inside extends the duration.)
   - entry_kind = "track_start" if the pass starts on segment 0 with f0*len0 <= TOL_KM; else "touch" if every piece was a touch or the pass length <= TOL_KM; else "crossing". exit_kind is symmetric, with "track_end" on the last segment.
   - entry/exit lat/lon via interpolate; time/alt by linear f; distance_inside_km from cumulative lengths; duration_s = exit_time - entry_time; seq = 1, 2, ... in track order.
8 segment_intersections(a1, b1, a2, b2) -> list[(kind, nvec)]
   if angle(a1, b1) < ZERO_RAD or angle(a2, b2) < ZERO_RAD: return []
   n1 = unit(a1 x b1); n2 = unit(a2 x b2); theta1 = angle(a1, b1)
   if |n1.a2| <= TOL_RAD and |n1.b2| <= TOL_RAD:      # co-linear: arc 2 lies on great circle 1 within 1 m
       u1 = n1 x a1; t(p) = atan2(p.u1, p.a1); lo, hi = sorted(t(a2), t(b2)); if hi - lo > pi: lo, hi = hi, lo + 2pi
       t0 = max(0, lo); t1 = min(theta1, hi)
       if t1 - t0 < -TOL_RAD: return []
       if t1 - t0 <= TOL_RAD: return [("crossing", interpolate(a1, b1, t0/theta1))]
       return [("overlap_start", interpolate(a1, b1, t0/theta1)), ("overlap_end", interpolate(a1, b1, t1/theta1))]
   x = unit(n1 x n2)
   for p in (x, -x): if on_arc(p, a1, b1) and on_arc(p, a2, b2): return [("crossing", p)]
   return []
   on_arc(p, a, b) := angle(a, p) + angle(p, b) - angle(a, b) <= TOL_RAD   (p is already on both great circles)
9 bounding_cap(points) -> (centre_nvec | None, radius_rad): centre = unit(sum of n-vectors), radius = max_i(angle(centre, mid_i) + theta_i/2), mid_i = interpolate(seg_i, 0.5) (a single point: radius 0); if |sum| < 1e-9 return (None, pi). Every point of the track lies inside this cap.
   track_intersections(a_points, b_points) -> list[TrackHit]
   - Skip the pair if the two bounding caps are disjoint (angle(centres) > rA + rB + TOL_RAD). Skip segment pairs with angle(mid_i, mid_j) > (theta_i + theta_j)/2 + TOL_RAD, and zero-length segments. (Caps, not lat/lon boxes: boxes break at +-180, at the poles and on poleward-bulging arcs.)
   - For each hit: f = min(1, angle(seg_start, p)/theta) on each track; times and alts by linear f; along-track km from cumulative lengths.
   - Merge overlap pieces contiguous along track A (gap <= TOL_KM); drop crossings inside a merged overlap (+-TOL_KM); dedupe crossings with |d dist_along_a| <= TOL_KM and |d dist_along_b| <= TOL_KM (a shared vertex is found by up to 4 segment pairs). Return sorted by dist_along_a_km.

Tests. Compare positions with distance_km(actual, expected) <= 0.001 (expected values are rounded to 6 decimals), never raw longitude (+-180 and the pole's longitude are ambiguous). Distances: pytest.approx(abs=1e-6) unless noted. Times: T0 = 2024-05-01T12:00Z, "@m" means T0 + m minutes.
T1 distance (0,0)-(0,1) = (0,0)-(1,0) = 111.195080; (60,0)-(60,1) = 55.597011; (52,179)-(52,-179) = 136.912738; (85,0)-(85,180) = 1111.950802; (0,0)-(0,180) = 20015.114442 (abs 1e-3); haversine_km == distance_km within 1e-9 for 1000 pairs from random.Random(42) (lat uniform -90..90, lon -180..180).
T2 interpolate((50,-50), (50,50), 0.5) is (61.659226, 0.0). A lat/lon average would give (50, 0).
T3 path_length_km([(50,-50), GC midpoint, (50,50)]) == distance (50,-50)-(50,50) = 6560.222 (abs 1e-3); path_length_3d_km([(0,0) alt 0 m, (0,1) alt 10000 m]) = 111.730751; None if an altitude is missing.
T4 zone (0,0) r=50, track (0,-1)@0 -> (0,1)@20: one pass crossing->crossing, entry (0,-0.449660) at 12:05:30.204, exit (0,0.449660) at 12:14:29.796 (+-1 ms), distance_inside 100.000000.
T5 track (-1,1)@0 -> (1,1)@20, centre (0,0): r=111.195080 -> one pass touch/touch at (0,1); r=111.190080 -> []; r=111.200080 -> one crossing pass, distance_inside 2.109063 (abs 1e-5).
T6 track (50,-50) -> (50,50): zone (61,0) r=100 -> 1 pass, distance_inside 136.043038; zone (50,0) r=200 -> [].
T7 track (52,179) -> (52,-179), zone (52,180) r=30 -> 1 pass, distance_inside 59.992612; the same with zone lon -180.
T8 track (85,0) -> (85,180), zone (90,0) r=100 -> 1 pass, entry (89.100680, 0), exit (89.100680, 180), distance_inside 200.000000; the same with zone lon 123.
T9 [(0,0)@0, (0,1)@10] r=50 -> track_start->crossing, 50.0; [(0,-1)@0, (0,0)@10] -> crossing->track_end; [(0,-1)@0, (0,1)@20, (0.4,1)@25, (0.4,-1)@45] -> 2 passes, 100.0 and 45.655685; [(0,-1)@0, (0,-0.449660181862269)@10, (0,0)@15, (0,1)@25] -> exactly 1 pass, 100.0; [(0,-1)@0, (0,0)@10, (0,0)@40, (0,1)@50] -> 1 pass, duration_s 2339.592 (abs 1e-3); [(0.1,0.1)@0] -> one track_start->track_end pass.
T10 arcs: (0,-1)->(0,1) with (-1,0)->(1,0) -> crossing (0,0); with (-1,180)->(1,180) -> [] (antipodal candidate); with (0.5,0)->(1,0) -> [] (stops short); with (0,0)->(1,0) -> crossing (0,0) (T-junction). (0,0)->(0,2) with itself, and with (0,2)->(0,0) -> overlap_start (0,0), overlap_end (0,2). (0,0)->(0,1) with (0,2)->(0,3) -> []. (-1,179.5)->(1,-179.5) with (1,179.5)->(-1,-179.5) -> crossing (0,180). (85,0)->(85,180) with (85,90)->(85,-90) -> crossing at lat 90. Result counts are unchanged by swapping the two arcs and by reversing both.
T11 track_intersections: A=[(0,-2)@0, (0,0)@10, (0,2)@20], B=[(-2,0)@5, (0,0)@15, (2,0)@25] -> exactly 1 crossing at (0,0), time_a 12:10, time_b 12:15. Two identical 4-point routes (0,0),(0,1),(0,2),(0,3) -> exactly [overlap_start, overlap_end].

DONE WHEN: uv run pytest -q tests/test_geodesy.py -> all passed (at least 11 tests); uv run ruff check src tests -> All checks passed!
Agent rules: follow PLAN.md §1 Conventions. Change only the CHANGE ONLY files. Never edit tests to make them pass. Never run git. Reply with the changed files and the last 15 lines of any command you ran.
```

Practice values:

- `EARTH_RADIUS_KM=6371.0088`
- `TOL_KM=0.001`

Why large: numerically subtle code where silent bugs live; the prompt is the spec and the table is the oracle, so the model has nothing to invent. Commit message: `P6.1: geodesy core and analytic tests [AI: large]`.

Then run the gate and log the prompt (top section).

Cut 6 (decide by minute 103, before sending): delete T3's clause `path_length_3d_km([(0,0) alt 0 m, (0,1) alt 10000 m]) = 111.730751; None if an altitude is missing.` from the table. Tripwire 120, if `tests/test_geodesy.py` is not green: cut 7. Delete by hand T5's touch case and the overlap cases of T10/T11, commit that deletion on its own (`cut 7: drop overlap and touch-band cases`), and note it for NOTES "Known limitations". Never drop T1–T4 (except T3's 3-D clause under cut 6), T6–T9 or the crossing cases of T10/T11.

#### Prompt 6.2 — Oracle and property tests (model: small)

```text
[P6.2 — Oracle and property tests] (model: small)
READ: PLAN.md §1 Conventions; in src/gisdb/geodesy.py only the public function signatures, dataclass fields and constants (not the function bodies).
CHANGE ONLY: tests/test_geodesy_oracle.py (new)
TASK:
1. Write the test file exactly to the recipe below. Tests only; never change src/.

RECIPE
Add tests/test_geodesy_oracle.py (tests only; do not modify src/). geographiclib is a dev dependency: from geographiclib.geodesic import Geodesic; SPHERE = Geodesic(6371008.8, 0.0) (exact sphere; metres; f = 0).
Use random.Random(seed) loops, NOT hypothesis. N = 200 for tests 1-4 and 7, N_ORACLE = 100 for tests 5-6. Deterministic.
Helpers: rand_point(rng) = (degrees(asin(rng.uniform(-1, 1))), rng.uniform(-180, 180)); dest(lat, lon, azi, km) = SPHERE.Direct(lat, lon, azi, km*1000) -> (lat2, normalize_lon(lon2)); sdist(p, q) = SPHERE.Inverse(...)["s12"]/1000; rand_track(rng) = a start point plus 1-4 more points, each dest(prev, azimuth + uniform(-60, 60), uniform(20, 600)).
1 distance_km matches sdist within 1e-6 km.
2 interpolate: for random a, b (b up to 19000 km away) and f: distance(a, p) = f*d and distance(p, b) = (1-f)*d within 1e-6 km.
3 Inserting the great-circle midpoint into any segment leaves path_length_km unchanged within 1e-6 km.
4 Longitude-shift invariance: add the same random dlon to every longitude (wrap via normalize_lon) -> same path length and the same list of pass distances (rounded to 1e-5 km).
5 Circle oracle: scenario = rand_track; centre = dest(a random point on a random segment, random azimuth, uniform(0, 600) km); r = uniform(5, 700). Oracle: per segment, line = SPHERE.InverseLine(...); g(s) = sdist(line.Position(s*1000), centre) - r sampled every 1 km (at least 2 samples); each sign change refined with 60 bisection steps -> entry/exit along-track positions; inside at s=0 iff g(0) <= 0. Skip the case if on ANY segment min(sampled g) lies in (-1 km, +1 km) (near-tangent). Assert: same number of passes as circle_passes; each distance_inside_km within 1e-5 km of the oracle interval; every "crossing" point is at distance r +- 1e-6 km from the centre; the first pass is track_start iff the oracle starts inside; at least 80% of the cases were checked.
6 Arc oracle: random arc A (10-3000 km); arc B (10-3000 km, random azimuth) through a point within 200 km of A or of its extension. Oracle: sample B at 400 steps; signed cross-track of each sample relative to A = asin(sin(a13)*sin(azi13 - azi12)) using SPHERE.Inverse from A's start (a12 in degrees, azi1); bisect sign changes; keep roots with sdist(a1, x) + sdist(x, a2) - sdist(a1, a2) < 1e-6. Skip cases with a root within 2 m of an endpoint. Assert the same count as segment_intersections, and positions within 1e-5 km.
7 bounding_cap(rand_track) contains the track: for every segment, 51 interpolated points all satisfy angle(centre, p) <= radius + 1e-12.
Run: uv run pytest tests/test_geodesy_oracle.py -q (must finish in < 20 s). If a case fails, print its inputs; do not change src/.

DONE WHEN: uv run pytest -q tests/test_geodesy_oracle.py -> 7 passed, in under 20 s
Agent rules: follow PLAN.md §1 Conventions. Change only the CHANGE ONLY files. Never edit tests to make them pass. Never run git. Reply with the changed files and the last 15 lines of any command you ran.
```

Practice values: none (no placeholders).

Why small: a mechanical recipe whose value lies in being independent of the implementation, not clever. It runs after minute 120, so a failure goes straight to the large model: geometry is never retried on the small one. Commit message: `P6.2: geographiclib oracle and property tests [AI: small]`.

Then run the gate and log the prompt (top section).

Cut 5 (decide by minute 118): skip P6.2. Phase 6 then expects ≥ 56 and Verify 6 runs only `tests/test_geodesy.py`.

#### Prompt 6.3 — Analysis result models (model: small)

```text
[P6.3 — Analysis result models] (model: small)
READ: PLAN.md §4 Schema; src/gisdb/models.py.
CHANGE ONLY: src/gisdb/models.py
TASK:
1. Append four models after the existing ones, copying their style exactly: Mapped[...] with mapped_column(), UTCDateTime for timestamps, Float, Integer primary keys, String(n), named CheckConstraint entries in __table_args__, ForeignKey(..., ondelete="CASCADE"), index=True on indexed columns. Every column is NOT NULL unless marked NULL. No relationships. Do not change the existing models.
2. AnalysisRun, table "analysis_runs": id Integer PK; started_at UTCDateTime NOT NULL, server_default=text("CURRENT_TIMESTAMP"); finished_at UTCDateTime NULL; status String(16); algorithm_version String(32); earth_radius_km Float; tol_km Float; trajectories, zones, zone_passes, intersections Integer, default=0; error Text NULL. CheckConstraint("status IN ('running', 'succeeded', 'failed')", name="status_valid").
3. TrajectoryMetrics, table "trajectory_metrics": trajectory_pk Integer, primary key and ForeignKey("trajectories.id", ondelete="CASCADE"); analysis_run_pk Integer, ForeignKey("analysis_runs.id", ondelete="CASCADE"), index=True; length_km Float; length_3d_km Float NULL; duration_s Float; zone_pass_count Integer; intersection_count Integer; input_hash String(64). CheckConstraint("length_km >= 0", name="length_nonneg"); CheckConstraint("duration_s >= 0", name="duration_nonneg").
4. ZonePass, table "zone_passes": id Integer PK; analysis_run_pk Integer, FK analysis_runs.id CASCADE, index=True; trajectory_pk Integer, FK trajectories.id CASCADE; zone_pk Integer, FK zones.id CASCADE, index=True; seq Integer; entry_kind String(16); entry_lat Float; entry_lon Float; entry_time UTCDateTime; entry_alt_m Float NULL; exit_kind String(16); exit_lat Float; exit_lon Float; exit_time UTCDateTime; exit_alt_m Float NULL; distance_inside_km Float; duration_s Float. UniqueConstraint("trajectory_pk", "zone_pk", "seq"); CheckConstraint("entry_kind IN ('crossing', 'track_start', 'touch')", name="entry_kind_valid"); CheckConstraint("exit_kind IN ('crossing', 'track_end', 'touch')", name="exit_kind_valid"); CheckConstraint("distance_inside_km >= 0", name="distance_nonneg"); CheckConstraint("duration_s >= 0", name="duration_nonneg").
5. TrajectoryIntersection, table "trajectory_intersections": id Integer PK; analysis_run_pk Integer, FK analysis_runs.id CASCADE, index=True; trajectory_a_pk Integer, FK trajectories.id CASCADE; trajectory_b_pk Integer, FK trajectories.id CASCADE, index=True; seq Integer; kind String(16); lat Float; lon Float; segment_a Integer; segment_b Integer; time_a UTCDateTime; time_b UTCDateTime; time_gap_s Float; alt_a_m Float NULL; alt_b_m Float NULL. Constraints:
   - CheckConstraint("trajectory_a_pk < trajectory_b_pk", name="canonical_pair")
   - CheckConstraint("kind IN ('crossing', 'overlap_start', 'overlap_end')", name="kind_valid")
   - CheckConstraint("time_gap_s >= 0", name="gap_nonneg")
   - UniqueConstraint("trajectory_a_pk", "trajectory_b_pk", "seq", name="uq_trajectory_intersections_pair_seq"), an explicit name because the convention's name would hit Postgres's 63-character limit.
6. Do NOT create a migration. When done, stop and tell me to run autogenerate.
DONE WHEN: uv run python -c "import gisdb.models as m; print(sorted(m.Base.metadata.tables))" -> ['analysis_runs', 'ingest_rejections', 'ingest_runs', 'trajectories', 'trajectory_intersections', 'trajectory_metrics', 'trajectory_points', 'zone_passes', 'zones']
Agent rules: follow PLAN.md §1 Conventions. Change only the CHANGE ONLY files. Never edit tests to make them pass. Never run git. Reply with the changed files and the last 15 lines of any command you ran.
```

Practice values: none (no placeholders).

Why small: an exact column list that copies the 0001 style; the migration review in Human step 6.a catches mistakes. Commit message, made at the end of Human step 6.a: `P6.3: analysis result models; 0002 reviewed [AI: small]`.

Then run `gate lint`; log and commit after Human step 6.a.

Cut 3 (decide by minute 124, before sending): delete `input_hash String(64);` from item 3. P6.4 then sets no `input_hash`, P6.5 drops `stale`, and P7.1's check 7 drops its stale clause. Cut 9 taken earlier: the DONE WHEN list has no `ingest_rejections`.

#### Human step 6.a — Autogenerate, format and review migration 0002 (no AI)

```bash
timeout 120 uv run alembic revision --autogenerate -m "analysis results" --rev-id 0002   # Generating .../migrations/versions/0002_analysis_results.py ... done
uv run ruff format -q migrations/versions && uv run ruff check --fix -q migrations/versions   # expect no output
f=migrations/versions/0002_analysis_results.py
grep -nE '^(revision|down_revision)' "$f"            # item 1: revision ... = "0002"; down_revision ... = "0001"
grep -nE 'gisdb\.|models\.|[^.]Text\(\)|now\(\)' "$f" || echo clean   # items 2 and 5: clean
grep -c 'op.create_table' "$f"                       # item 3: 4
sed -n '/^def upgrade/,/^def downgrade/p' "$f" | grep -cE 'alter_column|add_column|drop_'   # item 3: 0 (upgrade touches no 0001 table)
grep -c 'CheckConstraint' "$f"                       # item 4: 10
grep -c 'ondelete="CASCADE"' "$f"                    # item 4: 8
grep -c 'op.create_index' "$f"                       # item 4: 5 (on SQLite they read batch_op.create_index)
grep -n 'uq_trajectory_intersections_pair_seq' "$f"  # item 4: one line, name= as a plain string
sed -n '/def downgrade/,$p' "$f"                     # item 7: indexes and tables dropped in reverse dependency order
timeout 120 uv run alembic upgrade head && timeout 120 uv run alembic downgrade 0001 && timeout 120 uv run alembic upgrade head && timeout 120 uv run alembic check   # item 8: ends with No new upgrade operations detected. (downgrading only to 0001 keeps the ingested data)
sed -i '1a Reviewed: checklist 1-8 OK' "$f" && grep -n "Reviewed:" "$f"   # 2:Reviewed: checklist 1-8 OK (inside the docstring)
gate                                                 # conventions grep clean … 56 or more passed (38 + P6.1 + P6.2)
echo '| 131 | P6.3 | small | analysis result models | gate lint; 0002 checklist 1-8; gate 56+ passed | accepted |' >> AI_LOG.md
git add -A && git commit -qm "P6.3: analysis result models; 0002 reviewed [AI: small]"
```

The review checklist for 0002 (4 minutes):

1. `revision = "0002"`, `down_revision = "0001"`.
2. `render_item` worked: no `gisdb.`, `models.` or bare `Text()`.
3. Exactly the 4 analysis tables are created; `upgrade()` has no `alter_column`, `add_column` or `drop_*` on 0001 tables.
4. Every PK, FK (with `ondelete`), UNIQUE, CHECK and index of the models is present and named with `op.f("...")`, except `uq_trajectory_intersections_pair_seq`, which is a plain string.
5. Server defaults are `sa.text("CURRENT_TIMESTAMP")` (SQLite renders `"(CURRENT_TIMESTAMP)"`), never `now()`.
6. Timestamps are `sa.DateTime(timezone=True)`.
7. `downgrade()` drops indexes and tables in reverse dependency order.
8. The upgrade, downgrade to 0001, upgrade and check line ends with `No new upgrade operations detected.`

If the review fails, delete `migrations/versions/0002_analysis_results.py`, fix the model (by hand if ≤ 5 lines, otherwise the P6.3 follow-up under If it fails), and repeat this step. Under cut 5 the gate expects 49 or more; subtract 1 under cut 2 and 2 if P4.2 was skipped.

#### Prompt 6.4 — Analysis runner, CLI, tests (model: large)

```text
[P6.4 — Analysis runner, CLI, tests] (model: large)
READ: PLAN.md §1, §7 and §8; in src/gisdb/geodesy.py only the public signatures, dataclass fields and constants; src/gisdb/models.py; src/gisdb/db.py; src/gisdb/cli.py; tests/conftest.py.
CHANGE ONLY: src/gisdb/analysis.py (new), src/gisdb/cli.py, tests/test_analysis.py (new)
TASK:
1. src/gisdb/analysis.py: run_analysis(session_factory=SessionLocal) -> dict, with SessionLocal from gisdb.db. Import the math module as `from gisdb import geodesy` and call geodesy.circle_passes and so on, because gisdb.models.ZonePass and geodesy.ZonePass share a name. Current time is datetime.now(UTC).
2. Transaction 1: insert AnalysisRun(status="running", algorithm_version="sphere-nvector-v1", earth_radius_km=geodesy.EARTH_RADIUS_KM, tol_km=geodesy.TOL_KM), whose values must equal <EARTH_RADIUS_KM=6371.0088> and <TOL_KM=0.001>; count the trajectories and zones; commit. Log analysis.run.started with analysis_run_id, trajectories, zones, algorithm_version.
3. Transaction 2, one transaction for all results:
   a. Load all trajectories ordered by id with their points (selectinload, points ordered by seq) and all zones ordered by id. Convert each trajectory to a list of geodesy.TrackPoint(lat, lon, time=ts, alt_m=alt_m).
   b. Delete all rows of trajectory_intersections, zone_passes and trajectory_metrics, in that order, then flush.
   c. Per trajectory: length_km = geodesy.path_length_km(points); length_3d_km = geodesy.path_length_3d_km(points) (None if any altitude is missing); duration_s = (ended_at - started_at).total_seconds(); cap_centre, cap_radius = geodesy.bounding_cap(points).
   d. Per (trajectory, zone): skip the zone when cap_centre is not None and geodesy.angle(cap_centre, geodesy.to_nvec(center_lat, center_lon)) > cap_radius + radius_km / geodesy.EARTH_RADIUS_KM + geodesy.TOL_RAD. Otherwise geodesy.circle_passes(points, center_lat, center_lon, radius_km) gives one ZonePass row per result, copying seq, both kinds, positions, times and altitudes, distance_inside_km and duration_s.
   e. Per pair a.id < b.id: geodesy.track_intersections(a_points, b_points) gives TrajectoryIntersection rows with trajectory_a_pk = a.id, trajectory_b_pk = b.id, seq = 1..n in the returned order, segment_a = seg_a, segment_b = seg_b, kind, lat, lon, time_a, time_b, alt_a_m, alt_b_m, and time_gap_s = abs((time_a - time_b).total_seconds()).
   f. One TrajectoryMetrics row per trajectory: length_km, length_3d_km, duration_s, zone_pass_count (its zone_passes rows), intersection_count (rows where it is a or b), input_hash = the trajectory's content_hash.
   g. Set the run's trajectories, zones, zone_passes and intersections counts, status="succeeded" and finished_at; commit. Log analysis.run.finished with analysis_run_id, status, trajectories, zone_passes, intersections, duration_ms.
4. On any exception: roll back, then in a new transaction set the run's status="failed", error=str(exc)[:500] and finished_at; log analysis.run.failed with analysis_run_id and error; re-raise.
5. Return {"analysis_run_id": ..., "status": ..., "trajectories": ..., "zones": ..., "zone_passes": ..., "intersections": ...} with the keys in that order.
6. cli.py: add the analyze subcommand, mirroring the ingest subcommand: it calls run_analysis() and writes the returned dict as one JSON line with sys.stdout.write; exit code 0 when status is "succeeded", else 1; failures are handled exactly as ingest handles them.
7. tests/test_analysis.py (DB tests; fixtures db, make_trajectory, make_zone; points are (iso_ts, lat, lon, alt_m)). Seed for tests a-c: make_trajectory("T-EQ", [("2024-05-01T12:00:00Z", 0.0, -1.0, None), ("2024-05-01T12:20:00Z", 0.0, 1.0, None)]); make_trajectory("T-MER", [("2024-05-01T12:00:00Z", -1.0, 0.0, None), ("2024-05-01T12:20:00Z", 1.0, 0.0, None)]); make_zone("Z-0", 0.0, 0.0, 50.0); then run_analysis().
   a. test_equator_meridian: exactly 1 zone pass per trajectory, entry_kind and exit_kind "crossing"; entries T-EQ (0, -0.449660) and T-MER (-0.449660, 0) within 1e-6 degrees, both entry_time 2024-05-01T12:05:30.204Z within 1 ms; exactly 1 intersection, kind "crossing", at (0, 0) within 1e-6 degrees, time_gap_s 0.0 (abs 1e-6); every metrics row has length_km 222.390160 (abs 1e-6), zone_pass_count 1 and intersection_count 1.
   b. test_rerun_identical: run_analysis() a second time; the rows of zone_passes, trajectory_intersections and trajectory_metrics equal those of the first run when id and analysis_run_pk are ignored.
   c. test_run_provenance: the returned dict and the latest analysis_runs row show status "succeeded", algorithm_version "sphere-nvector-v1", earth_radius_km <EARTH_RADIUS_KM=6371.0088>, tol_km <TOL_KM=0.001>, trajectories 2, zones 1, zone_passes 2, intersections 1.
   d. test_overlap_pair: its own seed only, no zones: make_trajectory("T-R1", points at (0,0), (0,1), (0,2), (0,3) at 12:00, 12:10, 12:20, 12:30) and make_trajectory("T-R2", the same positions at 13:00, 13:10, 13:20, 13:30), altitudes None; run_analysis() -> exactly 2 intersection rows whose kinds by seq are ["overlap_start", "overlap_end"].
DONE WHEN: uv run pytest -q tests/test_analysis.py -> 4 passed
Agent rules: follow PLAN.md §1 Conventions. Change only the CHANGE ONLY files. Never edit tests to make them pass. Never run git. Reply with the changed files and the last 15 lines of any command you ran.
```

Practice values:

- `EARTH_RADIUS_KM=6371.0088`
- `TOL_KM=0.001`

Why large: orchestration, transactions, interpolated times and the cap prefilter in one module. Commit message: `P6.4: analysis runner and analyze CLI [AI: large]`.

Then run the gate and log the prompt (top section).

Under cut 7, delete test d from the prompt before sending; under cut 3, delete `input_hash` from item 3f. Tripwire 135: if P6.4 has not started, persist metrics and passes first, then intersections (never cut), and take the time from cuts 1 and 4, then 10.

#### Prompt 6.5 — Analysis in the API (model: large)

```text
[P6.5 — Analysis in the API] (model: large)
READ: PLAN.md §1, §6 and §8; src/gisdb/api/schemas.py; src/gisdb/api/routes.py; src/gisdb/models.py; the run_analysis signature in src/gisdb/analysis.py; tests/conftest.py.
CHANGE ONLY: src/gisdb/api/routes.py, src/gisdb/api/schemas.py, tests/test_api.py
TASK: fill the analysis fields the response models already have; field names and URLs do not change.
1. Trajectory analysis, list and detail: from trajectory_metrics joined to analysis_runs. TrajectoryAnalysisOut takes length_km, length_3d_km, duration_s, zone_pass_count and intersection_count from the metrics row; analyzed_at = the run's finished_at; algorithm_version and earth_radius_km from the run; stale = metrics.input_hash != the trajectory's content_hash. analysis is null when the trajectory has no metrics row.
2. Zone analysis, list and detail: ZoneAnalysisOut pass_count = the number of its zone_passes rows; trajectory_count = the number of distinct trajectory_pk among them; analyzed_at = finished_at of the latest analysis_runs row with status "succeeded". analysis is null when no succeeded analysis_runs row exists.
3. Lists in details: TrajectoryDetail.zone_passes ordered by (entry_time, zone_id); ZoneDetail.passes ordered by (trajectory_id, seq); TrajectoryDetail.intersections ordered by (other_trajectory_id, seq). ZonePassOut takes trajectory_id and zone_id from the joined trajectories and zones rows, and entry/exit from the entry_* and exit_* columns.
4. Intersection perspective: a stored row has trajectory a (the lower pk) and b. Viewed from a: other = b, time_self = time_a, alt_self_m = alt_a_m, time_other = time_b, alt_other_m = alt_b_m. Viewed from b, flip it: other = a, time_self = time_b, alt_self_m = alt_b_m, time_other = time_a, alt_other_m = alt_a_m. kind, lat, lon, seq and time_gap_s stay as stored.
5. No N+1: a list endpoint loads the analysis for the whole page in one extra query (filtered to the page's pks); a detail endpoint runs a fixed number of queries.
6. tests/test_api.py: add exactly 3 tests sharing this seed, created in this order so T-EQ gets the lower pk: make_trajectory("T-EQ", [("2024-05-01T12:00:00Z", 0.0, -1.0, 1000.0), ("2024-05-01T12:20:00Z", 0.0, 1.0, 1000.0)]); make_trajectory("T-MER", [("2024-05-01T12:05:00Z", -1.0, 0.0, 2000.0), ("2024-05-01T12:25:00Z", 1.0, 0.0, 2000.0)]); make_zone("Z-0", 0.0, 0.0, 50.0); then run_analysis() from gisdb.analysis. Compare times by parsing them with datetime.fromisoformat, within 1 ms.
   - test_detail_with_analysis: GET /trajectories/T-EQ: analysis.length_km 222.390160 (abs 1e-6) and analysis.stale false; zone_passes[0].zone_id "Z-0" and zone_passes[0].entry.kind "crossing"; intersections[0]: other_trajectory_id "T-MER", kind "crossing", time_self 2024-05-01T12:10:00Z, time_other 2024-05-01T12:15:00Z, time_gap_s 300.0 (abs 1e-3), alt_self_m 1000.0, alt_other_m 2000.0 (abs 1e-6). GET /trajectories: both items have a non-null analysis.
   - test_intersection_perspective: GET /trajectories/T-MER: intersections[0]: other_trajectory_id "T-EQ", time_self 2024-05-01T12:15:00Z, time_other 2024-05-01T12:10:00Z, alt_self_m 2000.0, alt_other_m 1000.0, time_gap_s 300.0 (abs 1e-3).
   - test_zone_detail_passes: GET /zones/Z-0: 2 passes, trajectory_id "T-EQ" then "T-MER"; analysis.pass_count 2 and analysis.trajectory_count 2.
DONE WHEN: uv run pytest -q -> all passed (at least 63)
Agent rules: follow PLAN.md §1 Conventions. Change only the CHANGE ONLY files. Never edit tests to make them pass. Never run git. Reply with the changed files and the last 15 lines of any command you ran.
```

Practice values: none (no placeholders).

Why large: joins, the perspective flip and page-level loading without N+1. Commit message: `P6.5: analysis in the API [AI: large]`.

Then run the gate and log the prompt (top section).

Before sending, apply the cuts taken: cut 1 (decide by minute 143) deletes item 2 (zone analysis stays null) and keeps only the 2-passes assert of `test_zone_detail_passes`; cut 6 deletes the altitude asserts; cut 3 deletes `stale` (from TrajectoryAnalysisOut too); P4.2 skipped deletes the zone parts and `test_zone_detail_passes`. Tripwire 152: finish the trajectory detail first (`analysis`, `zone_passes`, `intersections`; never cut) and drop the unfinished zone part (cut 1's scope).

#### Verify 6

```bash
timeout 120 uv run pytest -q tests/test_geodesy.py tests/test_geodesy_oracle.py   # all passed (the T-table tests, 11 or more, plus 7) in under 20 s
git log --oneline -- tests/test_geodesy.py | wc -l                     # 1 (written by P6.1, never edited since)
uv run python -c "from gisdb.geodesy import distance_km as d; print(round(d(0,0,0,1),6), round(d(52,179,52,-179),6), round(d(85,0,85,180),6))"   # 111.19508 136.912738 1111.950802
grep -nE "acos\(|asin\(" src/gisdb/geodesy.py                          # only item 6's acos(min(1, cos(rho)/cos(xt))) line (a comment quoting "never acos" is fine)
timeout 120 uv run alembic current                                     # 0002 (head)
grep -c "Reviewed:" migrations/versions/0002_analysis_results.py       # 1
uv run gisdb analyze 2>/dev/null                                       # {"analysis_run_id": N, "status": "succeeded", "trajectories": 10, "zones": 10, "zone_passes": 14, "intersections": 9}
uv run gisdb analyze 2>/dev/null                                       # the same counts, analysis_run_id N+1
uv run gisdb stats 2>/dev/null | grep -oE '"(trajectory_intersections|trajectory_metrics|zone_passes)": [0-9]+' | paste -sd' '   # "trajectory_intersections": 9 "trajectory_metrics": 10 "zone_passes": 14 (replaced, not appended)
uv run python scripts/api_get.py "/trajectories/$SAMPLE_TRJ" 2>/dev/null | grep -oE '"distance_inside_km":[0-9.]+|"zone_id":"[^"]+"' | paste -sd' '   # "distance_inside_km":91.466229... "zone_id":"ZN-PITUFFIK" (one pass inside the reporting gap; no ZN-BAFFIN)
# Practice-data ids below; on the day use equivalents or skip them:
uv run python scripts/api_get.py /zones/ZN-BAFFIN 2>/dev/null | grep -oE '"pass_count":[0-9]+'   # "pass_count":0 (the zone only planar interpolation would hit)
uv run python scripts/api_get.py /trajectories/FLT-1008 2>/dev/null | grep -o '"kind":"touch"' | wc -l   # 2 (TFR-101 tangent pass: entry and exit are touch)
uv run python scripts/api_get.py /trajectories/FLT-1009 2>/dev/null | grep -oE '"other_trajectory_id":"[^"]+"|"time_gap_s":[0-9.]+' | paste -sd' '   # "other_trajectory_id":"FLT-1008" "time_gap_s":30.0 (shared waypoint)
timeout 120 uv run pytest -q                                           # 63 or more passed
```

`analysis_run_id` is 1 then 2 only if nobody ran `analyze` on the dev database before; compare the counts and that the id rises by 1. If `trajectories` is 0, the dev database was emptied: run `uv run gisdb ingest "$DATA_DIR"` and repeat. Under cuts: cut 5 runs only `tests/test_geodesy.py` and the suite is ≥ 56; cut 7 makes the `git log` count 2 and `intersections` 7, drops the `"kind":"touch"` line, and the suite is ≥ 62; cut 1 or a skipped P4.2 drops the ZN-BAFFIN line; cut 2 lowers the suite by 1, a skipped P4.2 by 3.

#### If it fails

```text
T2/T6/T7/T10 fail. Do not touch the tests. The implementation must not interpolate or difference raw lat/lon anywhere: use interpolate(a, b, f) = a*cos(f*theta) + u*sin(f*theta) with u = unit(a x b) x a, and convert to lat/lon only for output. In segment_intersections test BOTH candidates x and -x, and require on_arc on BOTH arcs. Show the diff of geodesy.py only.
```

That is the P6.1 follow-up. For the other prompts, paste the failing tail (at most 20 lines) after the text:

- **P6.2** (after minute 120: re-send Prompt 6.2 to a fresh large-model chat with the tail, then use this as the follow-up): "Use the skip rule exactly: for each segment compute the min of the SIGNED sampled g (not min |g|) and skip the case if it lies in (-1 km, +1 km). Keep 1 km steps, segments of 20-600 km and N_ORACLE = 100. Do not change src/."
- **P6.3** (the review found a wrong or missing column, constraint or index; delete the generated 0002 file first): "The 0002 autogenerate does not match the column list of your task; the mismatch is pasted below. Fix only the four new models in src/gisdb/models.py so they match the list exactly; do not touch the 0001 models; do NOT create a migration." Then repeat Human step 6.a.
- **P6.4**: "Running analyze twice duplicates rows or violates UNIQUE. Inside the single analysis transaction, DELETE all rows of trajectory_intersections, zone_passes and trajectory_metrics before inserting, and flush before the inserts. Change analysis.py only."
- **P6.5**: "GET /trajectories/{trajectory_id} returns 500 (ResponseValidationError), or analysis stays null after analyze. Build TrajectoryAnalysisOut from trajectory_metrics joined to analysis_runs (analyzed_at = the run's finished_at), load a page's metrics in one query, and flip the rows where the viewed trajectory is b. Change src/gisdb/api/routes.py and src/gisdb/api/schemas.py only; do not touch tests."

#### Talking points

- Tangency is ill-conditioned: at r = 50 km, a track 1 mm inside has a 20 m chord and one 5 m inside a 1.4 km chord. So "touch" is decided by miss distance within ±1 m, a band tied to the data's 6-decimal quantization (0.11 m).
- I wrote the numbers and the AI wrote the code: the T-table existed before any implementation, and `git log` shows the test file never changed. The oracle uses different math (geographiclib on an exact sphere) and agrees to about 1e-7 m.
- Great circle versus planar, in the practice data: FLT-1003 passes through ZN-PITUFFIK inside a 2,550 km reporting gap with no sample inside the zone, and never enters ZN-BAFFIN, which only a lat/lon interpolation would hit.
- Pruning uses bounding caps, not lat/lon boxes: boxes break at ±180°, at the poles and on poleward bulges.
- 0002 is create-only schema evolution: four new tables, nothing altered in 0001.
- Provenance per run (algorithm version, radius, tolerance) and an idempotent full recompute in one transaction. The incremental path goes through `stale`.

#### Checkpoint 6

```bash
sed -i 's/^- \[ \] Phase 6:/- [x] Phase 6:/' PLAN.md && grep -n '^- \[x\] Phase 6:' PLAN.md   # the line now reads - [x] Phase 6: Geospatial analysis
git add -A && git commit -m "phase 6: geodesy, persisted analysis, API exposure [AI: P6.1 L, P6.2 S, P6.3 S, P6.4 L, P6.5 L; human: expected values, 0002 review]"
```

## Phase 7 — Tests and verification (153–170 min)

**Goal:** a one-command proof from an empty schema, invariants that work on real data, and short docs.   **Model:** small   **Done when:** `bash scripts/verify.sh` ends `VERIFY OK`, and README.md and NOTES.md are committed.

Chats: P7.1 to P7.3 in one fresh small-model chat, opened with the kickoff header; P7.4, if it runs at all, in a fresh large-model chat.

Clock (see Time budget): cut 4 before P7.1 (minute 153); cut 10 before P7.3 (163); tripwire 165, the feature freeze: `bash scripts/verify.sh` ends `VERIFY OK`, and if not, fix only the failing step and cut the README to 20 lines (cut 10's scope); tripwire 177: final commit and push.

#### Prompt 7.1 — Invariants script (model: small)

```text
[P7.1 — Invariants script] (model: small)
READ: PLAN.md §1 and §8; src/gisdb/models.py; in src/gisdb/geodesy.py only the public signatures.
CHANGE ONLY: scripts/check_invariants.py (new)
TASK:
1. A read-only checker of the stored analysis in the current database: open a session with gisdb.db.SessionLocal and query gisdb.models with select(); never write. Use geodesy.distance_km for positions and geographiclib (a dev dependency: from geographiclib.geodesic import Geodesic) for lengths. It needs no answer key, so it works on any data set.
2. Run these 7 checks, counting one assertion per row and rule (N in total, K failed):
   1 Every pass endpoint whose kind is "crossing" or "touch" lies at radius_km ± <TOL_KM=0.001> km from its zone centre.
   2 Every "track_start" entry equals its trajectory's first point and every "track_end" exit its last point, within <TOL_KM=0.001> km, and lies inside the zone (distance ≤ radius_km + <TOL_KM=0.001>).
   3 Per pass: entry_time ≤ exit_time, both within [started_at, ended_at] of its trajectory, and distance_inside_km ≥ 0.
   4 Every intersection point x lies on segment segment_a of trajectory A (the points with seq segment_a and segment_a + 1) and on segment segment_b of B: distance(p_i, x) + distance(x, p_i+1) - distance(p_i, p_i+1) ≤ <TOL_KM=0.001> km.
   5 time_gap_s equals |time_a - time_b| within 0.001 s.
   6 Each metrics length_km equals the sum over consecutive stored points of Geodesic(<EARTH_RADIUS_KM=6371.0088> * 1000, 0.0).Inverse(lat1, lon1, lat2, lon2)["s12"] / 1000, within 1e-6 km.
   7 The trajectory_metrics row count equals the trajectories row count; the latest analysis_runs row (highest id) has status "succeeded"; no metrics row is stale (input_hash equals its trajectory's content_hash).
3. Output: one line per failed assertion (check number, ids, values), then "INVARIANTS OK (N checks)" and exit 0, or "INVARIANTS FAILED (K of N)" and exit 1, with N and K as numbers.
DONE WHEN: uv run python scripts/check_invariants.py -> last line INVARIANTS OK (N checks), exit code 0 (the dev database still holds Phase 6's analyze results)
Agent rules: follow PLAN.md §1 Conventions. Change only the CHANGE ONLY files. Never edit tests to make them pass. Never run git. Reply with the changed files and the last 15 lines of any command you ran.
```

Practice values:

- `TOL_KM=0.001`
- `EARTH_RADIUS_KM=6371.0088`

Why small: a fixed check list over existing tables. Commit message: `P7.1: invariants checker [AI: small]`.

Then run the gate and log the prompt (top section).

Cut 4 (decide by minute 153): skip P7.1; P7.2's `verify.sh` then has no invariants step, and Verify 7 and NOTES drop `INVARIANTS OK`. Cut 3 taken: delete the stale clause of check 7.

#### Prompt 7.2 — Smoke and verify scripts (model: small)

```text
[P7.2 — Smoke and verify scripts] (model: small)
READ: PLAN.md §1 and §9; scripts/api_get.py; src/gisdb/cli.py.
CHANGE ONLY: scripts/smoke.py (new), scripts/verify.sh (new)
TASK:
1. scripts/smoke.py, run as uv run python scripts/smoke.py [--port 8765] (argparse, default 8765). It owns a live server and never leaves it running. cli.py already ends with if __name__ == "__main__": raise SystemExit(main()); if it does not, stop and tell me.
   a. Start [sys.executable, "-m", "gisdb.cli", "serve", "--host", "127.0.0.1", "--port", str(port)] with subprocess.Popen, env={**os.environ, "GISDB_LOG_LEVEL": "INFO"}, stdout=subprocess.DEVNULL and stderr to a temporary file.
   b. Poll GET /health every 0.25 s for up to 20 s (urllib.request, timeout 2 s). Fail if the process exits first or the time runs out.
   c. Run 7 HTTP checks with urllib.request, each sending the header X-Request-ID: smoke-a to smoke-g (the check's letter); read 4xx bodies from urllib.error.HTTPError.
      a /health -> 200 and status "ok".
      b /trajectories?limit=2 -> 200, at most 2 items, total >= 1, response header X-Request-ID equal to "smoke-b".
      c /trajectories/ followed by the first trajectory_id of b -> 200 with the keys analysis, zone_passes and intersections, and analysis not null.
      d /trajectories/DOES-NOT-EXIST -> 404 with a detail key.
      e /trajectories?limit=0 -> 422.
      f /zones?limit=1 -> 200 and total >= 1.
      g /openapi.json -> 200 and every path has only "get" operations.
   d. In finally: terminate(), wait(5), then kill() if the process is still running.
   e. Log check: every non-empty line of the server's stderr file parses as JSON, and one line has "event": "http.request" and "request_id": "smoke-b".
   f. Print "SMOKE OK (8 checks)" and exit 0, or print "SMOKE FAIL: " followed by the check letter (or "start" or "logs"), ": " and the detail, and exit 1.
2. scripts/verify.sh: the first lines are #!/usr/bin/env bash, then set -euo pipefail, then cd "$(dirname "$0")/..", then exactly DATA_DIR="${1:-${DATA_DIR:-<DATA_DIR=data>}}". Then these steps, in this order, one line each, verbatim; add no other step and start no server here:
   1 echo "== lint";     uv run ruff check . && uv run ruff format --check .
   2 echo "== migrate";  uv run alembic downgrade base && uv run alembic upgrade head && uv run alembic check
   3 echo "== ingest 1"; uv run gisdb ingest "$DATA_DIR"
   4 echo "== ingest 2"; uv run gisdb ingest "$DATA_DIR" | uv run python -c 'import json,sys; r=json.loads(sys.stdin.read()); assert r["status"]=="succeeded" and r["inserted"]==0 and r["updated"]==0, r; print("no-op OK", r)'
   5 echo "== analyze";  uv run gisdb analyze && uv run gisdb analyze
   6 echo "== invariants"; uv run python scripts/check_invariants.py
   7 echo "== smoke";    uv run python scripts/smoke.py
   8 echo "== tests";    uv run pytest -q
   9 echo "VERIFY OK"
DONE WHEN: bash scripts/verify.sh -> last line VERIFY OK (about 60 s; it resets the dev database)
Agent rules: follow PLAN.md §1 Conventions. Change only the CHANGE ONLY files. Never edit tests to make them pass. Never run git. Reply with the changed files and the last 15 lines of any command you ran.
```

Practice values: `DATA_DIR=data`

Why small: a fixed step list of exact commands; `verify.sh` calls P7.1's script. Commit message: `P7.2: smoke.py and verify.sh [AI: small]`.

Then run the gate and log the prompt (top section).

The gate's DONE WHEN check for P7.2 is the first line of Human step 7.a; run it before logging and committing P7.2. That run also feeds P7.3, so `verify.sh` runs once instead of twice.

Before sending, apply the cuts taken: cut 4 deletes step 6; a skipped P4.2 deletes smoke check f, and smoke then prints `SMOKE OK (7 checks)`; cut 8 replaces step 4 with this line, which checks that a re-run keeps the entity counts:

`echo "== ingest 2"; s1=$(uv run gisdb stats); uv run gisdb ingest "$DATA_DIR" >/dev/null; s2=$(uv run gisdb stats); uv run python -c 'import json,sys; a,b=(json.loads(s) for s in sys.argv[1:]); k=("trajectories","trajectory_points","zones"); assert [a[x] for x in k]==[b[x] for x in k], (a,b); print("re-run OK", {x: b[x] for x in k})' "$s1" "$s2"`

#### Human step 7.a — Verify run and facts for P7.3 (no AI)

```bash
timeout 300 bash scripts/verify.sh 2>/dev/null | tail -n 15 | tee /tmp/verify_tail.txt   # about 60 s; last line VERIFY OK (P7.2's DONE WHEN; this output feeds P7.3)
uv run gisdb ingest "$DATA_DIR" 2>&1 >/dev/null | grep -oE '"reason_code": "[a-z_]+"' | sort | uniq -c | tee /tmp/rejections.txt   # 4 lines: 1 invalid_timestamp, 1 missing_field, 2 out_of_range, 1 too_few_points
cat /tmp/verify_tail.txt /tmp/rejections.txt                           # paste this under Prompt 7.3
```

The second line reads the reason codes from the JSON logs of a no-op re-ingest, so it works under cut 9 too. If you took any cut, make sure PLAN.md §10 names it before sending P7.3.

#### Prompt 7.3 — README and NOTES (model: small)

```text
[P7.3 — README and NOTES] (model: small)
READ: PLAN.md; AI_LOG.md; pyproject.toml; the output pasted at the end of this prompt (the last 15 lines of bash scripts/verify.sh, then the reason-code counts of the last ingest run).
CHANGE ONLY: README.md, NOTES.md
TASK: use only facts from these inputs. Write every id, path and command literally; never shell variables such as $SAMPLE_TRJ or $DATA_DIR.
1. README.md, at most 120 lines: purpose; quickstart (uv sync; cp .env.example .env; uv run alembic upgrade head; uv run gisdb ingest <DATA_DIR=data>; uv run gisdb analyze; uv run gisdb serve; uv run pytest; bash scripts/verify.sh); a module map (PLAN.md §1 Layout); the data model (PLAN.md §4); the analysis method in 5 lines (sphere radius, n-vectors, pass kinds, intersections and overlaps, 1 m tolerance, constant-speed times; all from PLAN.md §8); an API table (PLAN.md §6); logging (PLAN.md §7); testing layers (analytic table, property and geographiclib oracle tests, DB integration tests, scripts/verify.sh); assumptions, linking to PLAN.md §10.
2. NOTES.md, at most 80 lines, with these sections in this order:
   ## How to evaluate in 10 minutes
   1. bash scripts/verify.sh (about 1 min; it ends VERIFY OK)
   2. Read PLAN.md §2-§3 and §8 (2 min)
   3. Open migrations/versions/0001_core_schema.py and find the Reviewed: line (1 min)
   4. uv run python scripts/api_get.py "/trajectories?limit=2" /trajectories/<SAMPLE_TRJ=FLT-1003> (1 min)
   5. Read src/gisdb/geodesy.py items 6-9 (segment_circle_interval, circle_passes, segment_intersections, bounding_cap and track_intersections) and tests/test_geodesy.py (3 min)
   6. git log --oneline and AI_LOG.md (2 min)
   ## Evidence map
   Copy this table as written:
   | Criterion | Artifact | 60-second proof |
   |---|---|---|
   | Reproducible end to end | `scripts/verify.sh` | `bash scripts/verify.sh` → `VERIFY OK` |
   | Schema: keys, constraints, indexes | `src/gisdb/models.py`, `migrations/versions/0001_core_schema.py` | `grep -cE "CheckConstraint\|UniqueConstraint" migrations/versions/0001_core_schema.py`; `uv run alembic check` → `No new upgrade operations detected.` |
   | Reviewed migrations | `migrations/versions/*.py` | `grep -n "Reviewed:" migrations/versions/*.py` → 2 lines |
   | Idempotent, auditable ingestion | `src/gisdb/ingest.py`, tables `ingest_runs`, `ingest_rejections` | `uv run gisdb ingest <DATA_DIR=data> 2>/dev/null` twice → the second shows `"inserted": 0, "updated": 0`; `uv run gisdb stats` |
   | API models, pagination, errors | `src/gisdb/api/` | `uv run python scripts/api_get.py "/trajectories?limit=2" /trajectories/NOPE "/trajectories?limit=0"` → 200 / 404 / 422 |
   | Structured logs with request IDs | `src/gisdb/logging_config.py`, `src/gisdb/api/app.py` | `uv run pytest -q tests/test_logging.py` → 3 passed |
   | Geo correctness | `src/gisdb/geodesy.py`, `tests/test_geodesy*.py` | `uv run pytest -q tests/test_geodesy.py tests/test_geodesy_oracle.py` |
   | Analysis stored and served | `src/gisdb/analysis.py`, `migrations/versions/0002_analysis_results.py` | `uv run gisdb analyze 2>/dev/null && uv run python scripts/api_get.py /trajectories/<SAMPLE_TRJ=FLT-1003>` |
   | Self-consistency on real data | `scripts/check_invariants.py` | `uv run python scripts/check_invariants.py` → `INVARIANTS OK` |
   | Judicious AI use | `AI_LOG.md`, commit tags | `git log --oneline \| head -20`; `cat AI_LOG.md` |
   ## Decisions and trade-offs (from PLAN.md §10)
   ## Data quality findings (the reason codes and counts pasted below, plus the duplicates count from the verify output)
   ## AI usage (5 lines summarizing AI_LOG.md: prompts per model, escalations, hand fixes; the full log is AI_LOG.md)
   ## Known limitations and next steps (every cut and limitation named in PLAN.md §10; next steps: a PostGIS geography prefilter with ST_DWithin on a GiST index at scale, incremental analysis of stale trajectories, an optional WGS84 distance via geographiclib, keyset pagination for large tables)
DONE WHEN: wc -l README.md NOTES.md -> README.md at most 120 lines, NOTES.md at most 80 lines
Agent rules: follow PLAN.md §1 Conventions. Change only the CHANGE ONLY files. Never edit tests to make them pass. Never run git. Reply with the changed files and the last 15 lines of any command you ran.
```

Practice values:

- `DATA_DIR=data`
- `SAMPLE_TRJ=FLT-1003`

Why small: it summarizes facts it is given and makes no design decision. Commit message: `P7.3: README and NOTES [AI: small]`.

Then run the gate and log the prompt (top section).

Before sending, apply the cuts taken: cut 10 (decide by minute 163) limits README.md to 20 lines and NOTES.md to the evidence map in 20 lines; cut 4 deletes the self-consistency row; cut 5 deletes `tests/test_geodesy_oracle.py` from the geo row; cut 9 deletes `ingest_rejections` from the ingestion row.

After the gate, check the claims yourself (2 minutes, human-only): every command in README.md and NOTES.md exists in PLAN §9 or the evidence map, and every number appears in `/tmp/verify_tail.txt` or `/tmp/rejections.txt`; fix wrong lines by hand.

#### Prompt 7.4 — Review, optional (model: large)

```text
[P7.4 — Review, optional] (model: large)
READ: src/gisdb/ingest.py; src/gisdb/analysis.py; src/gisdb/geodesy.py; src/gisdb/api/routes.py; migrations/versions/*.py.
CHANGE ONLY: nothing. Do not edit any file.
TASK:
1. Review as a strict senior engineer: correctness bugs, data-integrity risks, N+1 queries, missing error handling. No style nits, no praise, no code.
2. List at most 8 concrete defects ranked by severity, each with file:line, the problem in one sentence and a failing input.
DONE WHEN: the ranked list is in your reply and no file changed.
Agent rules: follow PLAN.md §1 Conventions. Change only the CHANGE ONLY files. Never edit tests to make them pass. Never run git. Reply with the changed files and the last 15 lines of any command you ran.
```

Practice values: none (no placeholders).

Why large: it finds defects a small model would miss; the large model works as a reviewer here, not a typist. It is unscheduled: send it only on time saved earlier (see Time budget). Commit message: `P7.4: review, no edits [AI: large]` (the commit holds only its AI_LOG row).

Then run the gate and log the prompt (top section).

Fix 1 to 3 findings: those of ≤ 5 lines by hand, mechanical ones with a small-model prompt, tricky ones with a large-model prompt. Log each in AI_LOG.md.

#### Verify 7

```bash
timeout 300 bash scripts/verify.sh 2>/dev/null | grep -E 'no-op OK|INVARIANTS OK|SMOKE OK|passed|VERIFY OK'   # six lines, as below
#   All checks passed!
#   no-op OK {'ingest_run_id': 2, 'status': 'succeeded', 'seen': 26, 'inserted': 0, 'updated': 0, 'unchanged': 20, 'duplicates': 1, 'rejected': 5}
#   INVARIANTS OK (N checks)
#   SMOKE OK (8 checks)
#   63 passed in ... (63 or more)
#   VERIFY OK
wc -l README.md NOTES.md                                               # README.md at most 120, NOTES.md at most 80
grep -cE '\$(SAMPLE_TRJ|SAMPLE_ZONE|DATA_DIR|BRIEF)' README.md NOTES.md   # README.md:0 and NOTES.md:0 (literal ids only)
git status --short                                                     # no output: verify.sh leaves no stray files
```

Under cuts: cut 4 removes the `INVARIANTS OK` line; a skipped P4.2 shows `SMOKE OK (7 checks)`; cut 8 shows `re-run OK` instead of `no-op OK` (add it to the pattern); cut 10 limits both files to 20 lines; the pass count drops as in Verify 6.

#### If it fails

```text
verify.sh fails in smoke. Start the server with sys.executable -m gisdb.cli serve, poll /health every 0.25 s for at most 20 s, and always terminate (then kill) it in finally. Change scripts/smoke.py only. Failure output (last 20 lines) follows:
```

That is the smoke follow-up for the P7.2 chat. Find the failing step from the last `==` banner; for the other steps:

- `== lint`: run `uv run ruff format . && uv run ruff check --fix .` yourself and re-run (a hand fix).
- `== ingest 2`: the re-run is not a no-op; send Phase 3's "If it fails" prompt (see Phase 3 — JSON ingestion (48–73 min)).
- `== invariants`: paste the failing lines to the large model with `scripts/check_invariants.py` and `src/gisdb/analysis.py` under READ; geometry is never retried on the small model.
- `== tests`: use the "If it fails" prompt of the phase that created the failing test file.

#### Talking points

- One command from an empty schema proves the migrations, idempotency, the analysis, the live API and the JSON logs.
- The invariants need no answer key, so they work on the day's real data; the lengths are re-checked against geographiclib, an independent implementation.
- The README was written from facts (PLAN.md, AI_LOG.md, the verify output), then checked by me.

#### Checkpoint 7

```bash
sed -i 's/^- \[ \] Phase 7:/- [x] Phase 7:/' PLAN.md && grep -n '^- \[x\] Phase 7:' PLAN.md   # the line now reads - [x] Phase 7: Tests and verification
git add -A && git commit -m "phase 7: verify script, invariants, README and NOTES [AI: P7.1 S, P7.2 S, P7.3 S; human: final review]"
```

Then the buffer (170–180 min): a final `bash scripts/verify.sh`, the demo rehearsal and the push (see Time budget and Appendix G — Final 5-minute demo).

## Appendix A — Reference architecture

What the session builds, in one place. Names, paths and contracts are fixed; on the day only the brief's mapping (PLAN §3) and the DELTA lines in PLAN §4–§8 change. The creator of each file is in brackets (H = human step, P = prompt).

### A.1 Layout

```text
INSTRUCTIONS.md  data/*.json                         provided: the brief and its data files
PLAN.md  DATA_PROFILE.md  AI_LOG.md                  [H0.b skeleton, profile run, log header; P0.1 profiler; P0.2 PLAN]
README.md  NOTES.md                                  [P7.3]
pyproject.toml  uv.lock  .python-version             [H1.a uv init/add + tool block; P1.1 sets the gisdb script]
.env.example  .env (git-ignored)  .gitignore         [H1.a]
alembic.ini  migrations/env.py                       [H2.a alembic init; P2.1 rewrites env.py]
migrations/versions/0001_core_schema.py              [H2.b autogenerate, ruff format, review]
migrations/versions/0002_analysis_results.py         [H6.a same steps]
src/gisdb/__init__.py  config.py  db.py              [P1.1]
src/gisdb/logging_config.py                          [P1.1 basic; P5.1 final]
src/gisdb/cli.py                                     [P1.1 serve; P3.2 ingest, stats; P6.4 analyze]
src/gisdb/models.py                                  [P2.1 0001 models; P6.3 0002 models]
src/gisdb/records.py  ingest.py                      [P3.1 pure parsing; P3.2 service]
src/gisdb/geodesy.py  analysis.py                    [P6.1 stdlib math; P6.4 runner]
src/gisdb/api/app.py                                 [P1.1; P4.1 router + CORS; P4.2; P5.1 middleware]
src/gisdb/api/deps.py  schemas.py  routes.py         [P4.1; P4.2 zones router; P6.5 analysis fields]
tests/conftest.py  test_migrations.py                [P2.1]
tests/test_health.py  test_records.py  test_ingest.py              [P1.1, P3.1, P3.2]
tests/test_api.py  test_logging.py                   [P4.1, P4.2, P6.5; P5.1]
tests/test_geodesy.py  test_geodesy_oracle.py  test_analysis.py    [P6.1, P6.2, P6.4]
scripts/profile_data.py  api_get.py                  [P0.1, P1.1]
scripts/check_invariants.py  smoke.py  verify.sh     [P7.1, P7.2]
```

Module rules: `geodesy.py` imports nothing from `gisdb`; `records.py` is pure (no DB); `db.py` owns the only engine and session factory; no repository, service or DI layers.

### A.2 Data flow

```mermaid
flowchart LR
  J["data/*.json"] --> R["records.py<br/>validate, normalize, hash"]
  R --> I["ingest.py<br/>one audited run"]
  I --> C[("0001 tables<br/>runs, rejections,<br/>trajectories, points, zones")]
  C --> A["analysis.py + geodesy.py<br/>full recompute"]
  A --> S[("0002 tables<br/>analysis_runs, metrics,<br/>zone_passes, intersections")]
  C --> P["api/routes.py<br/>GET only"]
  S --> P
  P --> W["web client<br/>JSON + X-Request-ID"]
```

The same flow in words:

1. `records.py` validates each record with Pydantic and normalizes it: UTC, (lat, lon), km, m, sorted and de-duplicated points, SHA-256 of the normalized record.
2. `gisdb ingest` (`ingest.py`) commits one `ingest_runs` row first, then writes all data in one transaction: insert, update or unchanged by natural key, plus rejection rows with reason codes.
3. `gisdb analyze` (`analysis.py` + `geodesy.py`) commits one `analysis_runs` row, then deletes and recomputes every result in one transaction.
4. `api/routes.py` serves both table groups read-only.

Every step logs JSON to stderr; each CLI command writes exactly one JSON result line to stdout.

### A.3 Tables and keys

Key rule: `id` is the internal integer PK and never leaves the service; `<x>_id` is the natural string key (`String(64)`, UNIQUE) used in URLs and JSON; `<x>_pk` is an integer FK to `<x>s.id`. Constraint names follow the `NAMING` convention, so a CHECK named `accounting` on `ingest_runs` becomes `ck_ingest_runs_accounting`.

| Table (migration) | Primary key | Unique | Foreign keys (on delete) | Named CHECKs; indexes |
|---|---|---|---|---|
| `ingest_runs` (0001) | `id` | — | — | `status_valid` (running, succeeded, failed); `accounting`: a succeeded run has seen = inserted + updated + unchanged + duplicates + rejected |
| `ingest_rejections` (0001) | `id` | — | `ingest_run_pk` → `ingest_runs` (CASCADE) | `entity_valid` (trajectory, zone, file); `reason_code_valid` (the 8 codes); ix `ingest_run_pk` |
| `trajectories` (0001) | `id` | `trajectory_id` | `last_ingest_run_pk` → `ingest_runs` (SET NULL) | `min_points` (point_count ≥ 2); `time_order`; ix `started_at`, `last_ingest_run_pk` |
| `trajectory_points` (0001) | (`trajectory_pk`, `seq`) | (`trajectory_pk`, `ts`) | `trajectory_pk` → `trajectories` (CASCADE) | `lat_range`; `lon_range` (−180 ≤ lon < 180); `seq_nonneg` |
| `zones` (0001) | `id` | `zone_id` | `last_ingest_run_pk` → `ingest_runs` (SET NULL) | `lat_range`, `lon_range` (centre); `radius_range` (0 < radius_km < 10000); ix `last_ingest_run_pk` |
| `analysis_runs` (0002) | `id` | — | — | `status_valid` |
| `trajectory_metrics` (0002) | `trajectory_pk` (also the FK, CASCADE) | — | `analysis_run_pk` (CASCADE) | `length_nonneg`, `duration_nonneg`; ix `analysis_run_pk` |
| `zone_passes` (0002) | `id` | (`trajectory_pk`, `zone_pk`, `seq`) | `analysis_run_pk`, `trajectory_pk`, `zone_pk` (all CASCADE) | `entry_kind_valid`, `exit_kind_valid`, `distance_nonneg`, `duration_nonneg`; ix `zone_pk`, `analysis_run_pk` |
| `trajectory_intersections` (0002) | `id` | (`trajectory_a_pk`, `trajectory_b_pk`, `seq`), named `uq_trajectory_intersections_pair_seq` | `analysis_run_pk`, `trajectory_a_pk`, `trajectory_b_pk` (all CASCADE) | `canonical_pair` (a_pk < b_pk), `kind_valid`, `gap_nonneg`; ix `trajectory_b_pk`, `analysis_run_pk` |

Main columns:

- `ingest_runs`: `started_at`, `finished_at`, `status`, `files` (JSON list of `{path, sha256, records}`), the six counters, `error`.
- `ingest_rejections`: `entity`, `source_file` (as given), `record_index` (NULL = whole file), `record_key`, `reason_code`, `detail`, `payload` (the raw record).
- `trajectories`: `trajectory_id`, the descriptive columns (`TRAJECTORY_ATTRS`), `started_at`, `ended_at`, `point_count`, `content_hash`, `source_file`, `created_at`, `updated_at`.
- `trajectory_points`: `seq` (0..n−1 in time order), `ts`, `lat`, `lon`, `alt_m` (nullable).
- `zones`: `zone_id`, `name`, `center_lat`, `center_lon`, `radius_km`, `content_hash`, `source_file`.
- `analysis_runs`: provenance (`algorithm_version` = `sphere-nvector-v1`, `earth_radius_km`, `tol_km`) and counts.
- `trajectory_metrics`: `length_km`, `length_3d_km` (null if any altitude is null), `duration_s`, `zone_pass_count`, `intersection_count`, `input_hash` (stale when it differs from `content_hash`).
- `zone_passes`: `seq`; `entry_*` and `exit_*` (kind, lat, lon, time, alt_m); `distance_inside_km`, `duration_s`.
- `trajectory_intersections`: `seq` (along A), `kind` (crossing, overlap_start, overlap_end), `lat`, `lon`, `segment_a`, `segment_b`, `time_a`, `time_b`, `time_gap_s`, `alt_a_m`, `alt_b_m`.

Portable types: timestamps are `UTCDateTime`; JSON is `JSON().with_variant(JSONB(), "postgresql")`; defaults are `server_default=text("CURRENT_TIMESTAMP")`; enumerations are `String(n)` plus a named CHECK.

### A.4 Endpoints

All routes are GET, with no prefix.

| Path | Query | Response | Errors |
|---|---|---|---|
| `/health` | — | `HealthOut` `{"status": "ok", "database": "ok"}` | 503 `{"status": "degraded", "database": "error"}` |
| `/trajectories` | `limit` 1–500 (default 50), `offset` ≥ 0, `started_after`, `started_before` (timezone-aware) | `Page[TrajectorySummary]`, ordered by `trajectory_id` | 422 (bad paging, naive datetime) |
| `/trajectories/{trajectory_id}` | — | `TrajectoryDetail` | 404 `{"detail": "trajectory 'NOPE' not found"}` |
| `/trajectories/{trajectory_id}/points` | `limit`, `offset` | `Page[PointOut]`, ordered by `seq` | 404, 422 |
| `/zones` | `limit`, `offset` | `Page[ZoneSummary]`, ordered by `zone_id` | 422 |
| `/zones/{zone_id}` | — | `ZoneDetail` | 404 `{"detail": "zone 'NOPE' not found"}` |

- `Page[T]` is `{items, total, limit, offset}`; `total` counts the same filtered query.
- `TrajectorySummary`: `trajectory_id`, the descriptive attributes, `started_at`, `ended_at`, `point_count`, `analysis` (`TrajectoryAnalysisOut`, or null). `TrajectoryDetail` adds `zone_passes` (`ZonePassOut`, with `entry` and `exit` as `PassEndpointOut`) and `intersections` (`IntersectionOut`, seen from the viewed trajectory: `other_trajectory_id`, `time_self`, `time_other`, `alt_self_m`, `alt_other_m`).
- `ZoneSummary`: `zone_id`, `name`, `center {lat, lon}`, `radius_km`, `analysis` (`pass_count`, `trajectory_count`, `analyzed_at`, or null). `ZoneDetail` adds `passes`.
- A null `analysis` means "not analyzed", never zero.
- Every response, errors included, carries `X-Request-ID`. An unhandled error returns 500 `{"detail": "internal server error", "request_id": ...}` with no traceback.
- Datetimes are ISO-8601 UTC ending in `Z`. Internal `id` and `*_pk` values never appear.

### A.5 Log events (PLAN §7)

Every line has `event`, `level`, `logger` (from Phase 5 on) and `timestamp` (UTC, ending `Z`). Request-scoped lines add `request_id`, `method` and `path`. Logs go to stderr and never contain payloads or coordinate arrays.

| Event | Level | Fields |
|---|---|---|
| `app.startup` | info | `version`, `db_dialect` |
| `http.request` | info | `status_code`, `duration_ms` |
| `http.unhandled_error` | error | `exception` |
| `health.check.failed` | warning | `error` |
| `ingest.run.started` | info | `ingest_run_id`, `paths` |
| `ingest.file.read` | info | `ingest_run_id`, `file`, `sha256`, `records` |
| `ingest.record.rejected` | warning | `ingest_run_id`, `file`, `record_index`, `record_key`, `reason_code` |
| `ingest.record.duplicate` | info | `ingest_run_id`, `file`, `record_index`, `record_key` |
| `ingest.run.finished` | info | `ingest_run_id`, `status`, the six counters, `duration_ms` |
| `ingest.run.failed` | error | `ingest_run_id`, `error` |
| `analysis.run.started` | info | `analysis_run_id`, `trajectories`, `zones`, `algorithm_version` |
| `analysis.run.finished` | info | `analysis_run_id`, `status`, `trajectories`, `zone_passes`, `intersections`, `duration_ms` |
| `analysis.run.failed` | error | `analysis_run_id`, `error` |

### A.6 Commands

| Command | What it does | Practice result |
|---|---|---|
| `uv run alembic upgrade head` | applies 0001 and 0002 | `uv run alembic current` → `0002 (head)` |
| `uv run gisdb ingest [PATH ...]` | one audited run; default `data`; a directory expands to its `*.json` files sorted by name; exit 0 only if succeeded | run 1: `{"ingest_run_id": 1, "status": "succeeded", "seen": 26, "inserted": 20, "updated": 0, "unchanged": 0, "duplicates": 1, "rejected": 5}` |
| `uv run gisdb analyze` | full recompute of every result | `{"analysis_run_id": 1, "status": "succeeded", "trajectories": 10, "zones": 10, "zone_passes": 14, "intersections": 9}` |
| `uv run gisdb stats` | row count per table, sorted keys | after two ingests: `{"ingest_rejections": 10, "ingest_runs": 2, "trajectories": 10, "trajectory_points": 184, "zones": 10}` |
| `uv run gisdb serve [--host 127.0.0.1] [--port 8000]` | live server until Ctrl-C; never inside a Verify block | JSON logs on stderr |
| `uv run python scripts/api_get.py [--request-id ID] PATH ...` | in-process GET through TestClient, one line per path | `200 /health {"database":"ok","status":"ok"}` |
| `uv run python scripts/check_invariants.py` | geometry invariants on the stored results, no answer key | `INVARIANTS OK (N checks)` |
| `uv run python scripts/smoke.py [--port 8765]` | owns a live server: 7 HTTP checks plus the JSON-log check | `SMOKE OK (8 checks)` |
| `bash scripts/verify.sh [DATA_DIR]` | lint, migrate from base, ingest twice, analyze twice, invariants, smoke, tests; resets the dev DB | last line `VERIFY OK`, about 60 s |
| `uv run pytest -q` | the whole suite | ≥ 63 passed |
| `python3 scripts/profile_data.py data/*.json > DATA_PROFILE.md` | data profile (stdlib only; runs before uv exists) | one section per file |

## Appendix B — Great-circle math cheat sheet

The reasoning and the numbers behind Prompt 6.1. The executable pseudo-code is the spec inside Prompt 6.1 (see Phase 6 — Geospatial analysis (103–153 min)); keep no second copy here.

Notation:

- φ and λ are latitude and longitude, in radians inside the formulas.
- a, b and c are unit n-vectors; θ = angle(a, b) is a segment's central angle.
- R is the sphere radius; × and · are the cross and dot products.

### B.1 Model and constants

| Name | Value | Note |
|---|---|---|
| `EARTH_RADIUS_KM` | 6371.0088 | IUGG mean radius (2a + b)/3 of WGS84 |
| `TOL_KM` | max(0.001, coordinate step) | 6 decimals = 0.11 m, so 1 m; one tolerance for every boundary, tangency, overlap and de-duplication decision |
| `TOL_RAD` | `TOL_KM` / R = 1.5696e-7 | the same tolerance as an angle |
| `ZERO_RAD` | 1e-12 (about 6 µm) | shorter segments are stationary |
| `NM_TO_KM`, `FT_TO_M` | 1.852, 0.3048 | exact by definition |

### B.2 Building blocks

| Quantity | Formula | Remember |
|---|---|---|
| n-vector | n = (cos φ cos λ, cos φ sin λ, sin φ) | back: φ = atan2(z, hypot(x, y)), λ = atan2(y, x), then wrap λ to [−180, 180) |
| Central angle, distance | θ = atan2(‖a × b‖, a · b); d = R θ | accurate over the whole range 0 to π |
| Haversine (cross-check only) | h = sin²(Δφ/2) + cos φ1 cos φ2 sin²(Δλ/2); clamp h to [0, 1]; θ = 2 atan2(√h, √(1 − h)) | an independent formula; T1 compares it with the n-vector distance on 1,000 random pairs |
| Position at arc fraction f (slerp) | n̂ = unit(a × b), u = n̂ × a; p = a cos(fθ) + u sin(fθ) | never average or interpolate raw lat/lon |
| Time and altitude at f | t = t0 + f (t1 − t0); h = h0 + f (h1 − h0) | f is a fraction of arc length (constant speed); h is null if either end is null |
| Length | L = R Σ θi | |
| 3-D length | Σ hypot(θi (R + h̄i), Δhi), h in km | null if any altitude is null; never the straight ECEF chord |
| Signed cross-track | d_xt = R asin(n̂ · c) | positive when c is left of travel a → b |
| Along-track angle of the closest point | τ = atan2(u · c, a · c) | that point lies on the segment iff 0 ≤ τ ≤ θ |
| Initial bearing | β = atan2(sin Δλ cos φ2, cos φ1 sin φ2 − sin φ1 cos φ2 cos Δλ), wrapped to [0, 360) | `math.atan2(y, x)` takes y first |

### B.3 Arc × circle (zone of radius r, ρ = r/R)

- **Closed form.** On the arc, p(t) = a cos t + u sin t for t in [0, θ]. With A = a · c, B = u · c and C = n̂ · c:
  - p(t) · c = A cos t + B sin t = M cos(t − τ);
  - M = hypot(A, B) = cos xt, and τ = atan2(B, A);
  - xt = atan2(|C|, M) is the angular distance from c to the great circle.
- **Inside test.** A point is inside when p · c ≥ cos ρ, that is |t − τ| ≤ δ, where cos ρ = cos xt · cos δ (spherical Pythagoras).
- **Entry and exit.** Entry is t = τ − δ (p · c rising) and exit is t = τ + δ. Clip to [0, θ], trying τ and τ ± 2π, then f = t/θ.
- **At most one inside interval per segment.** `radius_km` < 10,000 keeps ρ < π/2, so 2δ < π, and a minor arc has θ < π.
- **Touch band.** |xt − ρ| ≤ `TOL_RAD` means the path only grazes the circle: report one point at τ (if 0 ≤ τ ≤ θ), kind `touch`. Decide tangency by this miss distance, never by the computed chord (see the chord table in B.5).
- **Pass assembly.** Join intervals that meet at a vertex within `TOL_KM`, so a vertex on the boundary never splits or duplicates a pass.
- **Kinds.** `track_start` or `track_end` when the track starts or ends inside; `touch` for grazes and for passes no longer than `TOL_KM`; otherwise `crossing`.
- **Check by hand.** Zone (0, 0) with r = 50 km and a track along the equator: xt = 0 and δ = ρ, so entry and exit sit at longitude ∓0.449660, with 100.000000 km inside (T4).

### B.4 Arc × arc

- **Candidates.** The two great circles meet at ±x, with x = unit(n̂1 × n̂2).
  - Keep a candidate only if it lies on BOTH arcs: angle(a, p) + angle(p, b) − angle(a, b) ≤ `TOL_RAD` for each arc.
  - Two minor arcs admit at most one of ±x.
- **Co-linear arcs.** Both ends of arc 2 lie within the tolerance of great circle 1: |n̂1 · a2| ≤ `TOL_RAD` and |n̂1 · b2| ≤ `TOL_RAD`.
  - This is a distance test, not the angle between the two planes.
  - Project arc 2 onto arc 1. An overlap interval gives `overlap_start` + `overlap_end`; one that shrinks to a point gives a `crossing`.
- **Track pairs.**
  - Up to four segment pairs find the same shared vertex, so de-duplicate hits within `TOL_KM` along both tracks.
  - Merge contiguous overlaps along track A and drop crossings inside them.
  - Every row carries both tracks' times and altitudes, and time_gap_s = |time_a − time_b|.
- **Pruning: bounding caps, not lat/lon boxes.**
  - A segment lies within θ/2 of its slerp midpoint.
  - A track lies within maxᵢ(angle(centre, midᵢ) + θᵢ/2) of centre = unit(Σ nᵢ).
  - Skip pairs whose caps cannot meet.
- **Conditioning aside.** (a + b) × (b − a) = 2 a × b gives a better-conditioned normal for very short or nearly parallel segments. The plain a × b passes every test in this playbook.

### B.5 Sanity values

R = 6371.0088 km. Every value below was recomputed for this playbook with an independent n-vector implementation and with geographiclib `Geodesic(6371008.8, 0.0)` (an exact sphere); WGS84 values use `Geodesic.WGS84`.

| Quantity | Value |
|---|---|
| 1° of any great circle (1° of latitude; 1° of longitude on the equator) | 111.195080 km |
| 1 arc-minute | 1.853251 km (1 NM is exactly 1.852 km) |
| Equator to pole | 10,007.557221 km |
| Antipodal points | 20,015.114442 km |
| (60, 0) to (60, 1) | 55.597011 km; 55.597540 km along the parallel |
| (52, 179) to (52, −179) | 136.912738 km; a naive Δλ = 358° along the parallel gives 24,508 km |
| (85, 0) to (85, 180), over the pole | 1,111.950802 km |
| (50, −50) to (50, 50) | 6,560.222 km; great-circle midpoint (61.659226, 0); equirectangular 7,147.482 km; the lat/lon average (50, 0) is 1,296.4 km from the true midpoint |
| LHR (51.47, −0.4543) to JFK (40.6413, −73.7781) | 5,540.019 km on the sphere, 5,554.909 km on WGS84; initial bearing 287.943188° |
| Sphere vs WGS84 | at most 0.561 % (the limit for short north–south hops at the equator, where WGS84's meridian radius is 6,335.439 km); 200,000 random pairs peaked at 0.560 %. WGS84 1° of latitude is 110.574 km at the equator and 111.694 km at the pole; 1° of longitude on the equator is 111.319 km |
| 3-D length, (0, 0) at 0 m to (0, 1) at 10,000 m | 111.730751 km (T3) |
| Cruise altitude effect | 1,000 km of ground track flown at 11 km is 1,001.7266 km (+0.173 %) |
| ECEF chord instead of the arc | 1.411 km short on a 10° leg; 997.590 km short on a 90° leg |
| Cross-track of (0, 0) from the arc (−1, 1) → (1, 1) | +111.195080 km, which is T5's tangent radius |
| `TOL_RAD` | 1.5696e-7 rad |

Chord inside an r = 50 km zone, by how far the path dips inside. Tiny depth changes swing the chord by metres, which is why tangency is decided by miss distance:

| Depth inside | 1 mm | 1 cm | 1 m | 5 m | 100 m |
|---|---|---|---|---|---|
| Chord | 20.0 m | 63.2 m | 632.5 m | 1,414.2 m | 6,321.5 m |

### B.6 Pitfalls

The "measured" figures come from the recomputation runs described in B.5.

| Pitfall | What goes wrong (measured) | Do instead | Guard |
|---|---|---|---|
| `acos(a · b)` | loses up to 14 mm at 1–10 m separations; raises `ValueError` when rounding pushes the dot above 1, which happened for about 1 in 10 identical points (every stationary segment is at risk) | atan2(‖a × b‖, a · b) | spec item 2 (no test reliably catches it) |
| Unclamped haversine | h > 1 for 3.1 % of exact antipodal pairs (3,096 of 100,000), then `math domain error` | clamp h to [0, 1] | spec item 3 |
| Degrees vs radians | `math.sin` and `math.cos` take radians; mixing units gives plausible garbage | convert once, in `to_nvec` | T1 |
| `atan2` argument order | `math.atan2(y, x)`; swapped arguments return 90° minus the angle | lat = atan2(z, hypot(x, y)), lon = atan2(y, x) | T1, T2 |
| Lat/lon interpolation or averaging | the (50, −50) → (50, 50) midpoint lands 1,296.4 km from the true one, so tracks miss zones under the great-circle bulge | slerp; times by arc fraction | T2, T6; oracle test 3 |
| ECEF chord as length | tunnels through the Earth: 1.411 km short on a 10° leg | arc length; 3-D via hypot | T3 |
| Raw longitude comparison | 180 and −180 are one meridian; a pole has every longitude | compare positions by distance ≤ 0.001 km; wrap longitudes to [−180, 180) | T7, T8 |
| One-sided arc test | testing only +x, or only one arc, reports the antipode or a point on an arc's extension | test ±x, each on BOTH arcs | T10 |
| Co-linearity by plane angle | 6-decimal rounding tilts two 100 km segments of the same route by up to 2.1e-6 rad (13 × `TOL_RAD`): fake crossings scattered along shared routes | test endpoint distance to the other great circle | spec item 8; the T-table's identical routes do not catch it, a shared route sampled differently does (practice X1, Verify 6 counts) |
| Tangency noise | 1 mm inside an r = 50 km zone gives a 20 m chord | ±`TOL_KM` touch band on the miss distance | T5 |
| Lat/lon bounding boxes | (50, −50) → (50, 50) peaks at 61.659°N, outside its endpoints' box; boxes split at ±180° and break at the poles | bounding caps | oracle test 7 |
| `hypothesis` | shrinks towards exact antipodes and 1e-16 tangencies; minutes lost | seeded `random.Random` loops with bounded ranges | the P6.2 recipe |

### B.7 Variations: same primitives

If the brief asks for more than circles and crossings, build it from B.2–B.4 and record it as a PLAN §8 DELTA (see Appendix E — Adapting to the real brief, E.5).

| The brief asks for | Build it from |
|---|---|
| Distance to a site, closest approach | per segment, τ from B.2: if 0 ≤ τ ≤ θ, the closest distance is abs(d_xt) at f = τ/θ, else the nearer endpoint; take the minimum over segments; time and altitude from f |
| First time within X km of a site | `circle_passes` with r = X; the first pass's entry (`track_start` if the track starts inside) |
| Zones with a floor and a ceiling (cylinders) | altitude is linear in f within a segment: intersect each inside interval [f0, f1] with the f-range where floor ≤ h(f) ≤ ceiling; decide what a null altitude means |
| Polygon zones | edges are great-circle arcs: `segment_intersections` against every edge gives the boundary crossings, plus a spherical point-in-polygon test for the start state; or PostGIS geography `ST_Intersects` (see Appendix C — PostGIS contingency) |
| Conflicts close in space and time | filter crossings by `time_gap_s` and vertical separation; a true closest point of approach needs both positions at the same instants: slerp both tracks over their shared time window and minimise the distance per window |
| WGS84 accuracy | geographiclib `Geodesic.WGS84.Inverse` for lengths (an app dependency only if the brief demands it), or PostGIS on the spheroid |
| Nautical miles or other output units | store km; convert at the API edge (km / 1.852) |
| Headings, speeds | initial bearing per segment (B.2); speed = segment length / Δt, guarding Δt = 0 |

## Appendix C — PostGIS contingency

**Not verified locally: this environment has no PostGIS.**

- Checked here:
  - the availability and privilege queries in C.2;
  - the Python side of GeoAlchemy2 0.20.0 with SQLAlchemy 2.1.4: helper signatures, column DDL, the GiST index, and the migration that autogenerate renders.
- Everything that needs a PostGIS server is marked unverified.

### C.1 When to switch

| Situation | Decision |
|---|---|
| The brief requires spatial SQL or PostGIS | Switch with migration 0003 once the never-cut core is green (earlier only if the brief makes it the core). Exact events stay in Python |
| The environment ships PostGIS but the brief is silent | Optional: switch only with time in hand once Phase 6 is green, or when polygons or data size make it pay. Otherwise name it as the scale-up path in PLAN §10 and NOTES |
| Polygon zones | Optional: `ST_Intersects` as an indexed yes/no prefilter; exact crossing points stay in Python (see Appendix B — Great-circle math cheat sheet, B.7) |
| Trajectory–zone or trajectory–trajectory pairs in the millions | `ST_DWithin` on GiST indexes as the prefilter |
| Running on SQLite | Not possible: geography columns need Postgres |

Budget about 20–30 minutes.

### C.2 Checks

Use the brief's credentials on the day. Run both queries against the test database too (`-d gis_test`): extensions are per database, and the test fixtures migrate the test database from base.

```bash
PGCONNECT_TIMEOUT=5 PGPASSWORD=gis psql -h localhost -U gis -d gis -tAc "SELECT name, default_version, installed_version FROM pg_available_extensions WHERE name = 'postgis';"   # practice: no output (not installed); a row means installable; a filled installed_version means already created in this database
PGCONNECT_TIMEOUT=5 PGPASSWORD=gis psql -h localhost -U gis -d gis -tAc "SELECT rolsuper FROM pg_roles WHERE rolname = current_user;"   # practice: f (CREATE EXTENSION postgis needs a superuser unless the extension already exists)
```

### C.3 Switch steps

**Step 1 — human.**

- Run `uv add geoalchemy2`.
- Record the decision in PLAN §10 and a PLAN §4 DELTA.
- In PLAN §1, change "no ARRAY, no Geography" to allow `geoalchemy2.Geography` for these columns only. The model obeys the Conventions block.

**Step 2 — prompt (large).** A contingency prompt, outside the 17-prompt inventory of Model routing: send it only after step 1, numbered as the next prompt of the current phase (P6.6 after Phase 6).

```text
[P6.6 — PostGIS geography columns] (model: large)
READ: PLAN.md §1 and §4, src/gisdb/models.py, migrations/env.py
CHANGE ONLY: src/gisdb/models.py, migrations/env.py
TASK:
1. In models.py add TrajectoryPoint.geog and Zone.center_geog as generated columns: Mapped[Any] = mapped_column(Geography(geometry_type="POINT", srid=4326, spatial_index=True), Computed(expression, persisted=True), nullable=True), with Geography from geoalchemy2 and Computed from sqlalchemy. The expression, longitude first, is "ST_SetSRID(ST_MakePoint(lon, lat), 4326)::geography" for points and "ST_SetSRID(ST_MakePoint(center_lon, center_lat), 4326)::geography" for zones. Ingestion code does not change.
2. In migrations/env.py: from geoalchemy2 import alembic_helpers; pass include_object=alembic_helpers.include_object and process_revision_directives=alembic_helpers.writer to both context.configure calls; end render_item with return alembic_helpers.render_item(type_, obj, autogen_context) instead of return False.
3. Do NOT create a migration; when done, tell me to run autogenerate.
DONE WHEN: uv run python -c "import gisdb.models" exits 0
Agent rules: follow PLAN.md §1 Conventions. Change only the CHANGE ONLY files. Never edit tests to make them pass. Never run git. Reply with the changed files and the last 15 lines of any command you ran.
```

Practice values: none (no placeholders).

Then run `gate lint`; log and commit after step 3.

**Step 3 — human, like Human step 6.a.**

- Run `uv run alembic revision --autogenerate -m "postgis columns" --rev-id 0003`, then the `ruff format` / `ruff check --fix` line on `migrations/versions`.
- Add `op.execute("CREATE EXTENSION IF NOT EXISTS postgis")` as the first line of `upgrade()`. Never drop the extension in `downgrade()`.
- Review with the migration checklist. The GiST indexes `idx_trajectory_points_geog` and `idx_zones_center_geog` appear as plain strings, like `uq_trajectory_intersections_pair_seq`. Then run `uv run alembic upgrade head && uv run alembic check`.
- In `tests/test_migrations.py`, give `test_no_drift`'s `opts` the same `include_object`; otherwise `spatial_ref_sys` shows up as drift. This is a human scope edit; no expected value changes.
- Full gate, AI_LOG row, commit `P6.6: PostGIS geography columns; 0003 reviewed [AI: large]`.

**Step 4 — use it** through one more prompt, modelled on P6.4 (an analysis prefilter) or P4.1 (an API filter), with the functions in C.4.

What was checked here, and what was not:

- **Checked.** Step 2's column compiles to `geography(POINT,4326) GENERATED ALWAYS AS (...) STORED` with `CREATE INDEX idx_trajectory_points_geog ... USING gist (geog)`.
- **Checked.** The helper's `render_item` returns False for non-spatial types (safe to chain) and adds `from geoalchemy2 import Geography`; `include_object` hides `spatial_ref_sys`.
- **Checked.** Autogenerate against plain Postgres renders `op.add_geospatial_column(...)` carrying the `sa.Computed(...)`, plus `op.create_geospatial_index(..., postgresql_using='gist')`.
- **Unverified (needs PostGIS).** The extension privilege, the generated-column expression on a real server, the upgrade itself, and every ST_* result.

### C.4 Function map (geography, SRID 4326, metres)

| Need | PostGIS | Caveat |
|---|---|---|
| Point distance | `ST_Distance(g1, g2, false)` | `false` = sphere of radius (2a + b)/3 = 6,371,008.77 m, within 0.03 m of ours; the default (`true`) is the WGS84 spheroid |
| Track length | `ST_Length(line, false)`, with line = `ST_MakeLine(geog::geometry ORDER BY seq)::geography` | expected for `LINESTRING(-50 50, 50 50)`: 6,560.2215 km on the sphere, 6,580.3468 km on the spheroid (computed here with geographiclib) |
| Within r of a zone (prefilter) | `ST_DWithin(track, center, radius_m, false)` | uses the GiST index; the best use of PostGIS here |
| Yes/no intersection | `ST_Intersects(g1, g2)` | native on geography |
| Intersection geometry | `ST_Intersection(g1, g2)` | for geography it projects to a best-fit planar system and back: approximate on long legs. Keep exact events in Python |
| Circle as a polygon | `ST_Buffer(center, radius_m)` | the same planar wrapper, and segmented: not a true small circle |
| Follow great circles in planar work | `ST_Segmentize(geog, max_segment_m)` | densify before casting to geometry |

WKT is `POINT(lon lat)`. Day-of check, once PostGIS exists:

```bash
PGCONNECT_TIMEOUT=5 PGPASSWORD=gis psql -h localhost -U gis -d gis -tAc "SELECT ST_Distance('POINT(0 0)'::geography, 'POINT(1 0)'::geography, false), ST_Distance('POINT(0 0)'::geography, 'POINT(1 0)'::geography);"   # unverified: about 111195.08 (sphere) and 111319.49 (spheroid); practice: ERROR:  type "geography" does not exist
```

Expected values, computed here: 111,195.0797 m on PostGIS's sphere (ours gives 111,195.0802 m) and 111,319.4908 m on the spheroid.

**Interview line:** "PostGIS gives me indexed storage and an `ST_DWithin` prefilter. I keep the exact great-circle entries, exits and crossings in Python, because geography `ST_Intersection` and `ST_Buffer` go through a planar projection."

## Appendix D — No-Postgres fallback (SQLite)

### D.1 Decide, without debugging

| When | Check | Then |
|---|---|---|
| Minute 10 (Human step 0.a) | `pg_isready` and `psql ... select 1` with the brief's credentials | reachable: Postgres. No server but Postgres binaries: D.2 (5-minute cap). Otherwise: SQLite (D.3) |
| Minute 10 | Human step 0.a prints `NO TEST DB` while the server works | `PGPASSWORD=gis createdb -h localhost -U gis gis_test` (the brief's user on the day; the name must contain `test`); if refused, SQLite for both URLs |
| Minute 10 | the environment exports a URL (`env` shows `DATABASE_URL` or `PG*` variables) | reuse its host, user and password in `.env` with the `postgresql+psycopg://` scheme; the settings read only `GISDB_*` |
| Minute 27 (tripwire) | Verify 1: `/health` reports `"database":"ok"` | if not: SQLite now, then rerun Verify 1 |
| The brief requires Postgres-only features | no server and no binaries | `uv add --dev pgserver` for bundled binaries (PostgreSQL 16.2, no PostGIS), then D.2 with the same 5-minute cap; otherwise SQLite, and say so |

The test URL's database name must contain `test`; conftest refuses anything else (`gisdb_test.sqlite3` qualifies).

### D.2 Start your own Postgres (5-minute cap)

Practice: not needed, because the server already runs on 5432. The recipe was exercised on a spare port with the system binaries (initdb took about 1 s) and with pgserver's bundled binaries.

```bash
ls /usr/lib/postgresql/*/bin/initdb 2>/dev/null || command -v initdb || echo "NO PG BINARIES"   # practice: /usr/lib/postgresql/16/bin/initdb
PGBIN=$(dirname "$(ls /usr/lib/postgresql/*/bin/initdb | tail -n 1)")      # no output; if initdb is on PATH instead: PGBIN=$(dirname "$(command -v initdb)")
"$PGBIN/initdb" -D "$HOME/pgdata" -U gis --auth=trust --no-locale -E UTF8 > /dev/null   # no output; it refuses to run as root (then use SQLite)
"$PGBIN/pg_ctl" -D "$HOME/pgdata" -l "$HOME/pgdata/server.log" -o "-p 5432 -k /tmp" -w -t 30 start   # waiting for server to start.... done / server started
"$PGBIN/createdb" -h localhost -U gis gis && "$PGBIN/createdb" -h localhost -U gis gis_test   # no output
PGCONNECT_TIMEOUT=5 PGPASSWORD=gis "$PGBIN/psql" -h localhost -U gis -d gis_test -tAc "select 1"   # 1
```

- `--auth=trust` accepts the `.env` URLs (`gis:gis@localhost:5432`) unchanged, so nothing else changes.
- With pgserver instead, set `PGBIN=$(uv run python -c "import pathlib, pgserver; print(pathlib.Path(pgserver.__file__).parent / 'pginstall' / 'bin')")` and run the same lines. Its data directory must be on a normal Linux filesystem.
- The data directory sits outside the repo (`$HOME/pgdata`), so `git add -A` never sees it. Leave the server running for the session.

### D.3 Switch to SQLite

```bash
printf 'GISDB_DATABASE_URL=sqlite:///./gisdb.sqlite3\nGISDB_TEST_DATABASE_URL=sqlite:///./gisdb_test.sqlite3\nGISDB_LOG_LEVEL=INFO\n' > .env   # no output
grep -c '^GISDB_.*sqlite' .env                         # 2
git check-ignore -q gisdb.sqlite3 && echo ignored      # ignored (once Human step 1.a has added *.sqlite3 to .gitignore)
```

- **Verify again.** Rerun the current Verify block. At minute 27 that is Verify 1, whose `/health` line must print `200 /health {"database":"ok","status":"ok"}`.
- **Record it.** Put the URLs in PLAN §9 and the reason in PLAN §10. If the environment has no Postgres at all, copy the same three lines into `.env.example`, so the README quickstart (`cp .env.example .env`) reproduces your run.
- **Reset at any time.** Run `rm -f gisdb.sqlite3 gisdb_test.sqlite3 && uv run alembic upgrade head`. `verify.sh` resets by itself.

### D.4 Why nothing else changes

| Built in from Phases 1–2 | What it prevents on SQLite |
|---|---|
| `UTCDateTime` (models.py) | SQLite returns naive datetimes; the type re-attaches UTC on read and refuses naive writes |
| `server_default=text("CURRENT_TIMESTAMP")` | `func.now()` in a migration autogenerated on Postgres renders `now()`, which SQLite accepts at CREATE but rejects at every INSERT |
| `PRAGMA foreign_keys=ON` connect listener (db.py) | FKs and `ON DELETE CASCADE` would be silently ignored |
| `check_same_thread=False` (db.py) | explicit; SQLAlchemy 2.1 already defaults to it for file databases (checked), so pooled connections can move between FastAPI's worker threads |
| `render_as_batch` for `sqlite` URLs (env.py) | later ALTER-style migrations fail on SQLite; batch mode rebuilds the table (0001 and 0002 are create-only) |
| `JSON().with_variant(JSONB(), "postgresql")` | JSONB exists only on Postgres |
| `String(n)` + named CHECK; no Enum, ARRAY or Geography | dialect-specific types |
| `make_engine` branches on the URL | Postgres-only options (`-c timezone=UTC`, `pool_pre_ping`) never reach SQLite |

- **Same migrations on both.** The same 0001 and 0002 upgrade, round-trip and pass `alembic check` on both dialects; this was verified when the design was made.
- **Never `create_all`.** The app and the tests always go through Alembic: the session fixture downgrades to base and upgrades to head. That keeps the drift test and `alembic check` proving the migrations.
- **What SQLite costs.** One writer at a time, and no PostGIS. Say so in NOTES, with Postgres as the target.

## Appendix E — Adapting to the real brief

The playbook's names, paths and contracts stay fixed. The brief changes only three things:

- placeholder values;
- the mapping in PLAN §3;
- DELTA lines in PLAN §4–§8.

Decide everything below in Phase 0 and write it into PLAN.md.

### E.1 Checklist

| # | Do | Lands in |
|---|---|---|
| 1 | Read the brief yourself: list requirements R1..Rn, copy the analysis definitions verbatim, and note any required names, paths, fields or units | PLAN §2 |
| 2 | Profile the data (P0.1); no model ever sees the raw files | DATA_PROFILE.md |
| 3 | Landmark check: find a known place (airport, city, port) among the profile's examples; a coordinate beyond ±90 is a longitude | `COORD_ORDER`, PLAN §3 |
| 4 | Map the brief's entities onto the generic tables (E.2) | PLAN §3 names, §4 DELTA |
| 5 | Units, time forms and precision (E.3) | `ALT_UNIT`, `RADIUS_UNITS`, `TIME_FORMATS`, `TOL_KM`, PLAN §3 and §8 |
| 6 | Natural keys: unique and stable across files and days? If not, keep the surrogate `id` and build a composite key string in `records.py` (for example callsign plus UTC date), so URLs and tables stay unchanged | PLAN §3, §10 |
| 7 | Earth model (E.4) | `EARTH_RADIUS_KM`, PLAN §8 |
| 8 | Extra analysis (E.5) | PLAN §8 DELTA |
| 9 | Data size (E.6) | PLAN §10 |
| 10 | Update the placeholder values in every prompt not yet sent, and the shell variables (see Placeholders and PLAN.md; see Session setup) | — |
| 11 | Up to 7 candidate questions (E.7); PLAN §10 keeps the top 5 | PLAN §10 |

### E.2 Mapping the brief onto the generic names

| The brief says | Maps to | Change |
|---|---|---|
| flights, vessels, vehicles, tracks, trips | `trajectories` | none; PLAN §3 records the mapping |
| positions, pings, fixes, reports, samples | `trajectory_points` | `POINT_SOURCE` |
| zones, geofences, airspaces, sites with a radius | `zones` | `ZONE_SOURCE`, `RADIUS_UNITS` |
| polygon areas | a new table | PLAN §4 DELTA; analysis per Appendix B — Great-circle math cheat sheet (B.7), or Appendix C — PostGIS contingency |
| a third entity (airports, ports, stations, a register) | a new table | PLAN §4 DELTA; its record type in P3.1, its ingest branch in P3.2, endpoints through a prompt modelled on P4.2 |
| required URL paths or field names (for example `/flights`) | the same tables | PLAN §6 DELTA: router prefixes and response field names only; the tables keep their generic names |

### E.3 Units, time forms and precision

| Form | Default handling | If the brief differs |
|---|---|---|
| Coordinates | GeoJSON `[lon, lat]`, proven by a landmark | `[lat, lon]` or `{lat, lon}`: set `COORD_ORDER`; never "fix" swapped values silently |
| Altitude | feet × 0.3048 → `alt_m`; null allowed | metres: factor 1; flight levels: FL350 = 35,000 ft |
| Radius | NM × 1.852, km × 1 | statute miles × 1.609344 (exact); metres / 1000 |
| Timestamps | ISO-8601 with `Z` or an offset, or integer epoch seconds. Pydantic's `AwareDatetime` also reads epoch milliseconds (numbers above 2e10) and rejects naive strings (`invalid_timestamp`); checked on Pydantic 2.14 | if the brief says naive times are UTC: a PLAN §3 DELTA, and `records.py` attaches UTC |
| Precision | `TOL_KM` = max(0.001, coordinate step): 6 decimals → 0.11 m → 0.001; 5 decimals → 1.1 m → 0.0011; 4 decimals → 11.1 m → 0.0111 | above 0.004: the T5 rule below |

**T5 rule** (when PLAN §8's `TOL_KM` exceeds 0.004 km). T5's two off-tangent radii sit 5 m either side of the tangent radius 111.195080, and a touch band wider than 4 m swallows them. Before sending Prompt 6.1, edit its T5 line. This is a scope change, not a test edit.

- Keep `r=111.195080 -> one pass touch/touch at (0,1)`.
- Replace the other two radii:
  - 111.195080 − 2·`TOL_KM` expects `[]`;
  - 111.195080 + 2·`TOL_KM` expects exactly one pass, kinds crossing/crossing.
- Drop the `distance_inside 2.109063` value: it holds only for the 5 m case.

| `TOL_KM` | Outside radius → `[]` | Inside radius → one crossing pass |
|---|---|---|
| 0.0111 (4 decimals) | 111.172880 | 111.217280 |

This was checked against a verbatim implementation of the P6.1 spec:

- at `TOL_KM` 0.0111 and 0.111, only T5 fails as written; the edited T5 and every other T-row pass;
- at 0.004 and 0.0045, the original table passes.

### E.4 Earth model

| The brief says | Do |
|---|---|
| "a sphere; state your radius", or nothing | keep 6371.0088 km (IUGG mean radius); state it in PLAN §8 and the README |
| a different radius, for example 6371 km | ask first (question 1 in E.7): 6371.0 differs by 1.4 ppm, about 1.4 m per 1,000 km. If it must change, recompute the radius-dependent expected values before sending each prompt (below) |
| WGS84 (ellipsoidal) distances | lengths via geographiclib `Geodesic.WGS84` (then an app dependency); keep the sphere for zone and crossing geometry unless told otherwise, and say so (sphere error ≤ 0.561 %, Appendix B — Great-circle math cheat sheet) |

**Changing the radius.** Every T-value was computed for R = 6371.0088.

- **What breaks.** With R = 6371.0, T1, T3, T5, T6 and T9 fail as written; with 6378.137, T1 and T3–T9 fail. This was checked with the verbatim spec implementation.
- **Other prompts.** Besides the T-table, edit these before sending:
  - the 222.390160 lengths in P6.4 and P6.5;
  - P6.4's entry times (as T4);
  - `Geodesic(6371008.8, 0.0)` in P6.2, which becomes `Geodesic(R × 1000, 0.0)`; P7.1's check 6 already takes R from its `EARTH_RADIUS_KM` placeholder.
- **What stays.** T2, T10, T11 and the 50.0, 100.0 and 200.0 pass lengths do not depend on R.
- **Recompute.** This tooling reproduces the table at 6371.0088 (run that first); run it while an agent works in Phases 1–5:

```bash
python3 -c '
import math, sys
R = float(sys.argv[1]); deg, rad = math.degrees, math.radians; k = R / 6371.0088
arc = lambda r, xt: 2 * R * math.acos(math.cos(r / R) / math.cos(xt))
rho = deg(50 / R); tan = round(math.pi * R / 180, 6)
rows = [("T1 (0,0)-(0,1)", math.pi * R / 180), ("T1 (60,0)-(60,1)", 55.597011 * k),
        ("T1 (52,179)-(52,-179)", 136.912738 * k), ("T1 (85,0)-(85,180)", 1111.950802 * k),
        ("T1 (0,0)-(0,180)", math.pi * R), ("T3 2-D", 6560.221568 * k),
        ("T3 3-D", math.hypot(rad(1) * (R + 5), 10)), ("T4 lon", rho), ("T4 entry s", 600 * (1 - rho)),
        ("T5 tangent r", tan), ("T5 inside km", arc(round(tan + 0.005, 6), rad(1))),
        ("T6", arc(100, math.atan(math.tan(rad(50)) / math.cos(rad(50))) - rad(61))),
        ("T7", arc(30, math.atan(math.tan(rad(52)) / math.cos(rad(1))) - rad(52))),
        ("T8 lat", 90 - deg(100 / R)), ("T9 second pass", arc(50, math.atan(math.tan(rad(0.4)) / math.cos(rad(1))))),
        ("T9 duration_s", (30 + 20 * rho) * 60), ("P6.4/P6.5 length", 2 * math.pi * R / 180)]
for name, value in rows:
    print(f"{name:22} {value:.6f}")
' 6371.0088   # 111.195080, 55.597011, 136.912738, 1111.950802, 20015.114442, 6560.221568, 111.730751, 0.449660, 330.203891, 111.195080, 2.109063, 136.043038, 59.992612, 89.100680, 45.655685, 2339.592218, 222.390160
```

How to read the output:

- **T4.** The entry is at 12:00 plus "T4 entry s" seconds; the exit is that many seconds before 12:20; the longitudes are ∓"T4 lon".
- **T5.** The radii are "T5 tangent r" and that value ± 0.005, with "T5 inside km" inside.
- **Check.** At R = 6371.0 the script printed values that the spec implementation matched within 5e-7 km.

### E.5 Extra analysis

1. **Define it.** Add a PLAN §8 DELTA line with the definition in the brief's words and the primitive from Appendix B — Great-circle math cheat sheet (B.7).
2. **Plan storage early.** If it stores results, add the columns or the table to P6.3's list before sending it, so migration 0002 carries them. A later 0003 costs a second autogenerate and review.
3. **Write expected values first.** Work out 2–4 hand-checkable cases with `python3` and the formulas of Appendix B — Great-circle math cheat sheet, and put them in the prompt's test list.
4. **Send one large prompt modelled on P6.4.**
   - READ: PLAN §8, the `geodesy.py` signatures, `models.py`.
   - CHANGE ONLY: `analysis.py` (or one new module) and its test file.
   - DONE WHEN: its tests pass.
   - Number it as the next prompt of its phase (P6.6, P6.7 …); gate, AI_LOG row and commit as usual (see AI log and commit tags).
5. **Expose it.** Fold the API fields into P6.5's TASK before sending it, or send a second prompt modelled on P6.5.

### E.6 Data size

- **Measure in Phase 0.** Count records and positions per file from DATA_PROFILE.md.
- **Trajectory pairs grow as n(n − 1)/2:** 10 trajectories give 45 pairs, 1,000 give 499,500.
- **Prefilters.**
  - The bounding-cap prefilter in P6.1 and P6.4 already skips far pairs cheaply.
  - Add a time-window prefilter (skip pairs whose `started_at`–`ended_at` ranges do not overlap) only if the brief's crossings require both trajectories to be present at the same time.
  - For very large sets, use PostGIS `ST_DWithin` (see Appendix C — PostGIS contingency).
- **Already scale-ready.** Ingestion bulk-inserts points with Core, and the API paginates every list.

### E.7 Questions for the interviewer

Up to 7 candidates, each with the default you will take if there is no answer. PLAN §10 keeps the top 5.

| # | Question | Default |
|---|---|---|
| 1 | Sphere or WGS84, and which radius? | sphere, R = 6371.0088 km (IUGG mean) |
| 2 | Does grazing a zone count as a pass, and how should shared route stretches be reported? | ±1 m touch as a zero-length pass; overlaps as start/end rows |
| 3 | Duplicates and conflicts: keep the first copy of an exact duplicate, and reject a different record with the same key? | yes; the conflict is rejected as `duplicate_key_conflict` |
| 4 | Does altitude matter (3-D length, vertical separation at crossings)? | 3-D length as a bonus; altitudes carried on every event |
| 5 | Expected scale: records, points, files per day? | small; pairwise analysis with cap prefilters |
| 6 | Is PostGIS available, or required? | not used; geometry in Python |
| 7 | Anything beyond read-only (authentication, writes, re-ingestion through the API)? | no |

## Appendix F — Prompting patterns and token economy

Why the prompts are built the way they are, plus the recovery library. The rules themselves live in the top section: the contract template, kickoff header and `gate` (see Prompt contract, kickoff header and gate), the model per prompt and the escalation ladder (see Model routing), the token limits and expected spend (see Token rules), and the habits the grader looks for (see AI-use habits the grader wants to see).

### F.1 The contract: what each part buys

| Part | Rule | Prevents |
|---|---|---|
| Title line, for example `[P4.2 — Zone endpoints] (model: small)` | id and model first | the wrong model; an unlogged prompt |
| READ | named files and PLAN.md sections only | repo tours, token burn, guesses from stale files |
| CHANGE ONLY | the exact file list | drift; the gate restores anything else |
| TASK | numbered steps with exact names, signatures, library calls and expected values; never "appropriate", "robust", "handle edge cases" or "etc." | a model filling gaps with plausible inventions, the small model's main failure |
| DONE WHEN | one bounded command and its expected output | "looks done"; it is also the model's own check |
| Agent rules | PLAN.md §1 Conventions; never edit tests; never run git; terse replies | test tampering, commits behind your back, whole files pasted back |

### F.2 Patterns

- **Plan first, cite after.** P0.2 writes PLAN.md once, and later prompts say "per PLAN §n" instead of restating. Edit PLAN.md by hand (seconds); never regenerate it.
- **Pattern, then copy.** The large model writes the first instance (P4.1); the small model copies it ("copy the trajectories pattern exactly", P4.2).
- **Stop at the migration boundary.** P2.1 and P6.3 end at the models ("tell me to run autogenerate"); the human autogenerates, formats, reviews and applies, which is why those two prompts get `gate lint` first.
- **Specs, not code.** Prompts carry formulas, contracts and expected values: with an exact spec the model has nothing to invent, and the tests written from it catch what it gets wrong.
- **Read-only review.** P7.4 lists defects without editing, and you fix 1–3 of them. Run it only on time saved earlier.

### F.3 When a prompt fails

1. Follow gate step 2 (see Prompt contract, kickoff header and gate): stage everything, send the recovery prompt with at most 20 lines of failing tail, then check `git diff --stat -- tests/`.
2. Pick the recovery prompt by symptom: the phase's "If it fails" prompt for the failure it names, otherwise one of R1–R9 below.
3. Climb the escalation ladder in Model routing when the retry fails too: P5.1 escalates at once, and wrong geometry or units from the small model go straight to the large one (R9).
4. Record the outcome in the prompt's AI_LOG.md row (see AI log and commit tags).

### F.4 Token economy

Why the rules in Token rules pay off:

- **A fresh chat per phase:** old context is re-read on every turn and drifts.
- **Only the files in READ, never recursive listings:** the files a prompt names are the whole context it needs.
- **Failing tails only, terse replies:** long pastes and replies cost both tokens and minutes.
- **The 300k-token / 15-tool-call tripwire (R6):** a loop never converges on its own.
- **No "fix everything", no "review the repo", never regenerate PLAN.md:** unbounded asks give unbounded spend and unreviewable diffs.
- **The expected spend leaves room for escalations,** but judicious use is graded, so keep every prompt narrow.

### F.5 Recovery library (R1–R9)

Text in [square brackets] is filled in at the time; it is not a placeholder. Unless noted, send the prompt to the same chat.

| Id | Trigger | First, by hand | Prompt |
|---|---|---|---|
| R1 | Hallucinated or outdated API: ImportError, AttributeError, unknown keyword | — | This fails: [tail, ≤ 15 lines]. [symbol] does not exist in the installed version; check it with `uv run python -c "import [package]; print([package].__version__)"`. Use only APIs allowed by PLAN.md §1 Conventions. Fix only [file]; add no dependency; show the corrected lines. |
| R2 | File drift: files changed outside CHANGE ONLY | `git restore [files]`; delete stray new files | You changed files outside CHANGE ONLY; I reverted them. Redo the task changing only [files]. If another file is truly needed, stop and tell me which and why. |
| R3 | Async creep: `async def` endpoints, `AsyncSession`, `create_async_engine`, `asyncpg`, `aiosqlite` (the gate's grep) | — | This project is sync only (PLAN.md §1). Replace [async constructs] with create_engine, Session and plain def endpoints; keep every other name and signature. Change only [files]. |
| R4 | Scope creep: features, layers, files or dependencies nobody asked for | delete the extras; `uv remove [package]` if one was added | Remove [extra feature, layer or dependency]. Implement exactly the TASK list and nothing more: no new files, layers or dependencies. Change only [files]. |
| R5 | Test tampering: `git diff --stat -- tests/` shows an earlier prompt's test file or a changed expected value | `git restore [test files]` (restores the copy staged before the fix prompt) | You changed tests to make them pass; I reverted that. The expected values are mine: fix the implementation. If you believe an assertion is wrong, stop and explain which one and why. |
| R6 | Loop: 3 failed attempts at the same command, about 15 tool calls or about 300k tokens in one prompt | stop the agent | Stop. In at most 5 lines: what you tried, what the last failure shows, and the one fix you propose. Change nothing until I reply "go". |
| R7 | Context reset: the chat has lost the thread, or work resumes after a break | open a new chat and paste the kickoff header first | PLAN.md §11 has the status. Current step: [prompt id and one line]. Last good: uv run pytest -q gave [n] passed. Continue with this prompt only and read only the files it lists: [the prompt]. |
| R8 | SQLite-only failures: unknown function now(), FKs not enforced, naive datetimes, ALTER errors | — | On SQLite this fails: [tail, ≤ 20 lines]. Rules: server defaults are text("CURRENT_TIMESTAMP"); db.py's SQLite engine runs PRAGMA foreign_keys=ON on connect; env.py uses render_as_batch for sqlite URLs; UTCDateTime attaches UTC to naive values read back. Fix only [file]. If a file in migrations/versions/ is wrong, tell me instead of editing it. |
| R9 | The small model produced wrong geometry or units | no retry on the small model; open a fresh large-model chat with the kickoff header and paste the original prompt | A previous attempt produced wrong geometry or units: [failing assertion, ≤ 20 lines]. Follow the spec and PLAN.md §3 and §8 exactly; the tests are fixed. |

## Appendix G — Final 5-minute demo

Rehearse it once in the buffer (170–180). In a fresh terminal, re-export the shell variables first (see Session setup): with an empty `SAMPLE_TRJ`, the path `/trajectories/` redirects to the list and the demo shows nothing.

| Time | Show | Say |
|---|---|---|
| 0:00 | — | "A uv-managed FastAPI service. A CLI ingests the JSON through validated, normalized records into Postgres, via two reviewed Alembic migrations. A pure-Python n-vector geodesy core computes lengths, zone passes and crossings into result tables with run provenance. Read-only endpoints serve both, with JSON logs and request ids." |
| 0:30 | the `verify.sh` output | From an empty schema: lint, migrations both ways, ingest twice (the second is a no-op), analyze twice, invariants, a live server with JSON logs, the full suite, `VERIFY OK` |
| 1:30 | PLAN §3 and §8 | `[lon, lat]` proven with a landmark; units and UTC at the boundary; whole-record rejection with reason codes; R = 6371.0088 km; a 1 m tolerance derived from the data's decimals |
| 2:15 | `/trajectories/$SAMPLE_TRJ`, then ZN-BAFFIN | Practice: FLT-1003 has no report between 12:00 and 15:00, a 2,550 km gap, yet the great circle between two reports bulges into ZN-PITUFFIK. That gives one crossing pass of 91.466 km, 13:26:53–13:33:21 UTC, with interpolated times. ZN-BAFFIN is the reverse: a planar lat/lon interpolation passes about 0.1 km from its centre, the great circle 476 km, so there is no pass |
| 3:15 | `git log` of `tests/test_geodesy.py`; the geo tests | The analytic table (T1–T11) was in the prompt before any code, written once and never edited; an independent geographiclib oracle agrees with the implementation |
| 4:00 | `AI_LOG.md` and the commit tags | Small model: exact specs, pattern copies, scripts, docs. Large model: plan, schema, ingestion, API pattern, geometry. Name one escalation and why. Every prompt was gated, every migration reviewed by me |
| 4:30 | NOTES "Known limitations and next steps" | PostGIS `ST_DWithin` prefilter for scale; incremental analysis through the `stale` flag; a WGS84 option |

```bash
cat /tmp/verify_tail.txt                                     # saved in Human step 7.a: ... SMOKE OK (8 checks) ... passed ... VERIFY OK
timeout 300 bash scripts/verify.sh 2>/dev/null | tail -n 1   # live alternative, about 60 s, resets the dev DB: VERIFY OK
awk '/^## 8\./,/^## 9\./' PLAN.md | grep -m 2 -E '6371.0088|TOL_KM'   # the Earth-model and tolerance lines of PLAN §8
uv run python scripts/api_get.py "/trajectories/$SAMPLE_TRJ" 2>/dev/null | grep -oE '"zone_id":"[^"]*"|"distance_inside_km":[0-9.]+'   # practice: "distance_inside_km":91.466229... then "zone_id":"ZN-PITUFFIK"; no ZN-BAFFIN
uv run python scripts/api_get.py /zones/ZN-BAFFIN 2>/dev/null | grep -oE '"pass_count":[0-9]+'   # practice only: "pass_count":0
git log --oneline -- tests/test_geodesy.py | wc -l            # 1 (2 after cut 7)
timeout 120 uv run pytest -q tests/test_geodesy.py tests/test_geodesy_oracle.py 2>&1 | tail -n 1   # all passed (at least 18) in under 20 s; after cut 5, drop the oracle file
git log --oneline | grep -cE '\[AI: (small|large)\]'          # 17, one per mandatory prompt; one more per optional or extra prompt sent (P7.4, P6.6); fewer after cut 4 or 5, or a skipped P4.2
grep -A 6 'Known limitations' NOTES.md                        # the limitations and next steps
```
