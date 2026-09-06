# Gantt and swimlane diagrams

## Gantt

- Use ISO dates in the FigureSpec.
- Reject tasks whose end precedes start.
- Group tasks by workstream only when the grouping has operational meaning.
- Show completion only when supplied by the user.
- Dependencies must reference existing task IDs.

## Swimlanes

- Each lane represents one accountable actor, team, or system.
- A node belongs to exactly one lane.
- Use edges across lanes to show handoffs.
- Keep time or process progression left-to-right.
- Avoid duplicating one event in multiple lanes; use a handoff edge instead.
