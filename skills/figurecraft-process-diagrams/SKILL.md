---
name: figurecraft-process-diagrams
description: Creates Gantt charts, swimlane diagrams, algorithm flowcharts, decision trees, state machines, and role-based process diagrams. Use for 甘特图, 泳道图, 算法图, 流程图, project plan, workflow, handoff, milestone, decision flow, or lifecycle visualization. Do not use for statistical data charts, software landscapes, or neural networks.
license: MIT
compatibility: Requires the sibling figurecraft core skill; Gantt rendering requires matplotlib.
metadata:
  author: figurecraft
  version: "0.26.0"
---

# FigureCraft Process Diagrams

Choose the grammar that carries the process meaning.

## Selection

- Dates, durations, milestones, dependencies: `project.gantt`.
- Accountable actors and handoffs: `diagram.swimlane`.
- Branching computation or decisions: `diagram.algorithm`.
- Simple directed procedure: `diagram.flowchart`.

## Workflow

1. Validate actors, task IDs, dates, ordering, decisions, and dependencies.
2. Keep one progression direction.
3. Build FigureSpec with stable node/task IDs.
4. Locate sibling `figurecraft/scripts/figure.py`, validate, render, and lint.
5. Deliver SVG/source/manifest; add Draw.io for manual workflow editing.

## Rules

- A swimlane node belongs to exactly one accountable lane.
- Cross-lane edges represent handoffs, not decorative relationships.
- Gantt completion appears only when provided.
- Task end cannot precede start; dependencies must reference existing tasks.
- Decision diamonds use explicit outcomes on outgoing edges.
- Do not duplicate one event in several lanes.
- Use explicit action labels and final-size output constraints. A role inventory
  is not a task sequence; provide a separate scenario view when needed.
