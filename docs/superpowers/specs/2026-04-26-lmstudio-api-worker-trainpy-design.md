# LM Studio API-Only Worker Design (train.py Core)

Date: 2026-04-26  
Status: Draft for review  
Scope: Refactor current FastAPI research app so FastAPI is the only control plane, while `train.py` runs the research loop out-of-process with resumability.

## 1. Goals

1. Enforce a fixed, explicit research-loop protocol (`SEARCH`, `THINK`, `ANSWER`) with clear stop rules.
2. Make `train.py` the mutable loop-policy core, with strong module boundaries around transport/control concerns.
3. Keep FastAPI as the only method to start/control runs.
4. Ensure resumability after failure using durable checkpoints.
5. Preserve current API/UI behavior as much as possible during migration.

## 2. Non-Goals (Phase 1)

1. Rebuilding frontend UX from scratch.
2. Changing LM Studio model-management endpoints beyond compatibility needs.
3. Implementing distributed workers or multi-host scheduling.

## 3. Architecture

### 3.1 Control and Runtime Split

- **FastAPI control plane** (`app/main.py` + control services):
  - Accepts run commands (`start`, `status`, `resume`, `pause`, `cancel`).
  - Persists and serves durable run state.
  - Spawns and monitors worker processes.
- **Worker runtime zone** (`train.py`, out-of-process):
  - Owns the research loop policy and turn execution.
  - Talks to LM Studio through adapter/service code.
  - Writes checkpoints/events/status to DB.

### 3.2 Module Responsibilities

- `train.py`
  - Research loop policy owner (protocol parsing, turn boundaries, stop rules).
  - No HTTP serving responsibilities.
- `app/services/lm_studio_client.py`
  - LM Studio transport adapter only (chat/stream/model API integration).
  - No loop policy.
- `app/services/run_manager.py` (new)
  - Worker lifecycle: spawn, heartbeat monitor, terminate, restart on resume.
- `app/services/state_store.py` (new)
  - DB-backed read/write contract for sessions, checkpoints, processes, events.
- `app/main.py`
  - API contract surface only.

### 3.3 Boundary Rule

Loop behavior should be changeable primarily through `train.py`; API control and transport layers remain stable unless loop contract intentionally changes.

## 4. Durable Data Model

Existing tables are retained and reused:

- `sessions`
- `history_entries`

New tables:

### 4.1 `run_checkpoints`

- `task_id` (PK, FK to sessions)
- `last_completed_turn` (int)
- `summary_snapshot` (text)
- `worker_state_json` (text/json)
- `updated_at` (timestamp)

Purpose: resume from deterministic turn boundary.

### 4.2 `run_processes`

- `id` (PK)
- `task_id` (FK)
- `pid` (int)
- `started_at` (timestamp)
- `heartbeat_at` (timestamp)
- `exit_code` (nullable int)
- `failure_reason` (nullable text)
- `restart_count` (int default 0)

Purpose: operational lifecycle/audit of worker attempts.

### 4.3 `run_events` (recommended)

- `id` (PK)
- `task_id` (FK)
- `event_type` (text)
- `payload_json` (text/json)
- `created_at` (timestamp)

Purpose: append-only operational trail for replay/debug/streaming.

## 5. Resume and Consistency Contract

### 5.1 Status Model

`queued -> running -> paused -> completed | failed | canceled`

### 5.2 Turn Commit Atomicity

Each completed turn is committed in one DB transaction:

1. insert `history_entries` row
2. update `sessions` (`current_turn`, status fields as needed)
3. update `run_checkpoints` (`last_completed_turn`, snapshots)
4. optional append to `run_events`

### 5.3 Resume Rules

1. Resume starts at `last_completed_turn + 1`.
2. Mid-turn crash resumes at same turn (idempotent boundary behavior).
3. `resume` allowed only for `failed` or `paused`.
4. Every resume attempt increments `restart_count`.
5. Prior failures remain auditable via `run_processes`/`run_events`.

## 6. Execution Flow

### 6.1 Start

1. `POST /api/research`
2. API creates session (`queued`) and initial checkpoint (`turn=0`).
3. `run_manager` spawns worker (`train.py --task-id <id>`).
4. API marks session `running` on successful spawn.

### 6.2 Worker Boot

1. Load session + checkpoint by `task_id`.
2. Reconstruct context (topic, summary snapshot, next turn, max turns).
3. Begin periodic heartbeat updates.

### 6.3 Per Turn

1. Build state prompt.
2. Invoke LM Studio adapter.
3. Parse one action (`SEARCH`, `THINK`, `ANSWER`).
4. Execute tool/search when needed.
5. Atomically commit turn + checkpoint.

### 6.4 Complete / Fail / Pause / Cancel

- `ANSWER` -> `completed` + `final_answer`.
- Exception/timeout -> `failed` + reason + exit non-zero.
- Pause request -> checkpoint boundary stop -> `paused`.
- Cancel request -> terminate process -> `canceled`.

## 7. API Contract (Phase 1)

Keep current endpoints where possible, add lifecycle controls:

- `POST /api/research` (start run)
- `GET /api/status/{task_id}` (durable status)
- `POST /api/research/{task_id}/resume`
- `POST /api/research/{task_id}/pause`
- `POST /api/research/{task_id}/cancel`

History/model endpoints remain available for compatibility.

## 8. Refactor Plan

### Phase 1: Durable Run Control Foundation

1. Add `run_manager` and `state_store`.
2. Add DB migrations for new tables.
3. Keep existing API endpoints stable while introducing internal control primitives; do not add any non-API user-facing run path.

### Phase 2: Move Loop Policy to `train.py` Worker

1. Implement out-of-process worker entry (`task_id` driven).
2. Move protocol loop logic out of `app/orchestrator.py`.
3. Wire checkpoint/heartbeat/failure writes.

### Phase 3: API Switch-Over

1. `/api/research` launches worker only.
2. `/api/status` and websocket read durable DB-backed state.
3. Add resume/pause/cancel endpoints.

### Phase 4: Cleanup and Hardening

1. Remove in-memory `StateManager` as source of truth.
2. Remove `app/orchestrator.py` loop ownership (delete or minimize).
3. Expand tests for crash/recovery and idempotent turn commits.

## 9. Testing Strategy

1. Unit tests
   - action parsing and protocol enforcement in worker loop
   - checkpoint read/write semantics
   - run manager state transitions
2. Integration tests
   - start -> running -> completed
   - forced crash -> failed -> resume -> completed
   - pause/cancel at turn boundaries
3. Regression checks
   - existing API history endpoints still function
   - model list/load/unload endpoints unaffected

## 10. Risks and Mitigations

1. **Duplicate writes or skipped turns**  
   Mitigation: strict transactional turn commits and deterministic resume cursor.
2. **Worker orphaning**  
   Mitigation: heartbeat timeout + stale process detection and cleanup.
3. **API/worker drift**  
   Mitigation: single state-store contract and typed payload schemas.
4. **Migration regressions**  
   Mitigation: phased rollout with compatibility checks before removing old paths.

## 11. Acceptance Criteria (Phase 1)

1. FastAPI remains the only external control method.
2. Worker runs out-of-process and is visible in process tracking.
3. A failed run can resume from last completed turn and finish.
4. Fixed protocol loop remains enforced in worker policy.
5. Existing UI/API status/history behaviors still function against durable state.

## 12. Implementation Handoff

Next step after this spec is an implementation plan that maps each phase into concrete code tasks, file ownership, and verification commands.
