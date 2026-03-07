---
description: Plan, implement, test, and review a new feature end-to-end
---

# New Feature: $ARGUMENTS

Execute the full feature workflow chain:

## Step 1: Plan (planner agent)
Delegate to the `planner` agent:
- Analyze the feature request: "$ARGUMENTS"
- Read relevant design docs in `docs/`
- Produce an implementation plan with file paths, changes, and impact analysis
- Use the `dependency-impact` skill to trace affected modules

## Step 2: Implement (implementer agent)
Delegate to the `implementer` agent:
- Follow the planner's implementation plan
- Write code following MAOS async/Pydantic/Protocol conventions
- Use the `feature-scaffold` skill for new modules
- Use the `smart-build` skill to verify the build

## Step 3: Integration Check (integration-specialist agent)
Delegate to the `integration-specialist` agent:
- Verify cross-module wiring using the `integration-verify` skill
- Run integration tests: `pytest tests/integration/ -v`
- Fix any integration issues

## Step 4: Test (test-engineer agent)
Delegate to the `test-engineer` agent:
- Write unit tests for all new code
- Run full test suite using the `test-coverage` skill
- Ensure coverage meets standards

## Step 5: Review (reviewer agent)
Delegate to the `reviewer` agent:
- Review all changes using the `code-review` skill
- Run linters and type checkers
- Produce structured verdict (APPROVE or REQUEST_CHANGES)

## Post-Review Decision Gate

After the reviewer produces its verdict:

- **APPROVE**: Report completion to user with summary of changes
- **REQUEST_CHANGES**: Check `max_review_remediate_cycles` in `.claude/workflow-config.yml` (default: 2)
  - If cycles remaining > 0: route critical findings back to `implementer`, then `test-engineer`, then `reviewer` again
  - If cycles remaining == 0: stop auto-remediation and report remaining findings to user
