# Improve LM Studio Client

## 1. System Prompt Update
Update the `LMStudioClient` to support passing a `system_prompt` correctly to all API requests, not just during initialization.

## 2. Research Output Enhancement
Update `chat_v1` or `chat_v1_stream` to output event progress (e.g., `prompt_processing.progress`) so the user can see model activity.

## 3. API Integration
Adopt the `chat_v1` method from `.worktrees/fix-lmstudio-integration` which properly handles tool calls and provides debugging logs, merging it into the main codebase.
