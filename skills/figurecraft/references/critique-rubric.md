# Critique rubric

Evaluate in this order:

1. **Data and logic**: values, units, uncertainty, nodes, edges, and direction.
2. **Representation**: whether the selected figure family serves the stated
   intent without misleading encodings.
3. **Completeness**: labels, legends, caption alignment, dependencies, and
   groups.
4. **Geometry**: overlap, clipping, edge crossings, whitespace, and alignment.
5. **Typography and accessibility**: final size, contrast, color redundancy,
   and grayscale behavior.
6. **Reproducibility**: editable source, manifest, engine version, and input
   hash.

Data or relationship errors, clipping, unreadable text, missing required units,
and invalid outputs are blocking. Subjective style preferences are not.

Automated checks are not a substitute for a final-size visual review. Prefer
rendered text bounds, connector geometry, and semantic export inventories over
file-exists assertions. Include dense graphs, long labels, Chinese glyphs,
custom dark fills, feedback loops, and portable source re-renders in regression
cases. Inspect a fresh output directory so old exports cannot mask a failure.
