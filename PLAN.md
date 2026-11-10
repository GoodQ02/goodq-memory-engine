<!-- DOC_BADGE: CANONICAL -->
<!-- DOC_STATUS: AUTHORITATIVE -->
<!-- DOC_LAST_VERIFIED: 2026-11-06 -->
<!-- INSTRUCTION_REVIEW: documentation only; no runtime qualification -->

# Execution plans

Use a written plan when requested or when multi-step work needs durable decisions,
dependencies or recovery. Routine fixes need no new plan document. A plan
implements an authorized outcome; it does not override `AGENTS.md`, current
user instructions, `PROJECT.md` holds or subsystem contracts.

Keep one maintained plan for the task. Link existing contracts and evidence
instead of copying their contents. Include enough local context to resume
without the conversation, but do not build another repository manual.

## Useful plan content

- **Outcome and scope:** what the user will be able to do, the current failure
  or approved requirement, exclusions and the acceptance boundary.
- **Relevant context:** source owners, baseline revision, existing changes,
  dependencies and contract links needed for this task.
- **Work:** coherent steps with observable results. Specify commands, inputs,
  working directory and expected results where precision affects correctness;
  leave routine implementation choices to the executor.
- **Validation:** original-failure evidence, the production caller and relevant
  positive/negative cases. Use existing checks. Separate source tests, isolated
  integration, live behavior and release qualification.
- **Recovery:** authorization gates, exact-target backup and rollback for risky
  steps. Label rollback **UNDO ONLY - not a verification step.**
- **Progress and decisions:** completed scope, evidence locations, meaningful
  changes of direction, unresolved risks and the next bounded step.

Keep these details proportional to the task; headings, prose and checklists are
tools rather than a mandatory template. Update the plan at meaningful decision
or handoff points, not after every command. Do not duplicate the roadmap backlog
or the current checkpoint. A prototype needs a purpose and a disposition;
parallel implementations need a justified transition and retirement boundary.

Execute authorized steps through their verification gates. Stop only at an
actual missing decision/approval, conflicting local work or an unresolved safety
boundary. A plan is not authorization to commit, publish, deploy, migrate data
or proceed into later milestones. Record actual results and remaining limits;
do not infer completion from code existence or historical test counts.
