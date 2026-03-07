---
description: Plan and execute a refactoring with tests and review
---

# Refactor: $ARGUMENTS

Execute the refactoring workflow chain:

## Step 1: Plan (planner agent)
Delegate to the `planner` agent:
- Analyze the refactoring request: "$ARGUMENTS"
- Use the `dependency-impact` skill to assess blast radius
- Produce a refactoring plan that preserves behavior

## Step 2: Implement (implementer agent)
Delegate to the `implementer` agent:
- Follow the refactoring plan
- Ensure behavior is preserved
- Use the `smart-build` skill to verify build

## Step 3: Test (test-engineer agent)
Delegate to the `test-engineer` agent:
- Run all existing tests to verify no regressions
- Update tests if interfaces changed
- Use the `test-coverage` skill

## Step 4: Review (reviewer agent)
Delegate to the `reviewer` agent:
- Verify refactoring preserves behavior
- Check for missed references
- Produce structured verdict

## Post-Review Decision Gate

After the reviewer produces its verdict:

- **APPROVE**: Report completion to user
- **REQUEST_CHANGES**: Check `max_review_remediate_cycles` (default: 2)
  - If cycles remaining > 0: route findings back to `implementer`, then `test-engineer`, then `reviewer`
  - If cycles remaining == 0: report remaining findings to user
