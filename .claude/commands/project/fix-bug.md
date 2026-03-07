---
description: Diagnose, fix, test, and review a bug
---

# Fix Bug: $ARGUMENTS

Execute the bug fix workflow chain:

## Step 1: Diagnose (planner agent)
Delegate to the `planner` agent:
- Analyze the bug report: "$ARGUMENTS"
- Search codebase for relevant code paths
- Identify root cause and affected modules
- Produce a fix plan

## Step 2: Fix (implementer agent)
Delegate to the `implementer` agent:
- Follow the planner's fix plan
- Make minimal, targeted changes
- Use the `smart-build` skill to verify build

## Step 3: Test (test-engineer agent)
Delegate to the `test-engineer` agent:
- Write a regression test that reproduces the bug
- Run existing tests to ensure no regressions
- Use the `test-coverage` skill

## Step 4: Review (reviewer agent)
Delegate to the `reviewer` agent:
- Review the fix using the `code-review` skill
- Verify the fix is minimal and correct
- Produce structured verdict

## Post-Review Decision Gate

After the reviewer produces its verdict:

- **APPROVE**: Report completion to user
- **REQUEST_CHANGES**: Check `max_review_remediate_cycles` (default: 2)
  - If cycles remaining > 0: route findings back to `implementer`, then `test-engineer`, then `reviewer`
  - If cycles remaining == 0: report remaining findings to user
