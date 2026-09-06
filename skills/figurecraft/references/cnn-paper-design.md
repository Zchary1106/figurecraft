# CNN paper figure design

This playbook distills recurring visual grammar from public paper figures. It
does not reproduce their artwork or exact composition.

## Sources

- ResNet, Figure 2: residual branch and explicit add operator  
  https://ar5iv.labs.arxiv.org/html/1512.03385#S1.F2
- U-Net, Figure 1: spatially scaled feature maps and long skip paths  
  https://ar5iv.labs.arxiv.org/html/1505.04597#S1.F1
- DenseNet, Figures 1–2: dense connectivity plus block-level compression  
  https://ar5iv.labs.arxiv.org/html/1608.06993#S1.F1
- Inception, Figure 2: one input, aligned parallel branches, one concat output  
  https://ar5iv.labs.arxiv.org/html/1409.4842#S4.F2
- MobileNetV2, Figures 2–3: channel thickness, expand/project, and inverted skip  
  https://ar5iv.labs.arxiv.org/html/1801.04381#S3.F2
- EfficientNet, Figure 2: comparable panels for width, depth, and resolution  
  https://ar5iv.labs.arxiv.org/html/1905.11946#S0.F2
- ConvNeXt, Figure 4: aligned block comparison and explicit residual operators  
  https://ar5iv.labs.arxiv.org/html/2201.03545#S2.F4
- MaxViT, Figure 2: stage-level main path plus a representative block inset  
  https://ar5iv.labs.arxiv.org/html/2204.01697#S3.F2
- EfficientViT, Figure 6: coordinated network, block, and attention detail  
  https://arxiv.org/html/2305.07027v1#S2.F6
- RT-DETR, Figures 4–5: multiscale feature pyramid and separate fusion detail  
  https://arxiv.org/html/2304.08069v3#S4.F4
- UniRepLKNet, Figure 2: training-to-inference reparameterization and kernel grid  
  https://arxiv.org/html/2311.15599v2#S3.F2
- MobileMamba, Figures 3–4: macro network, multi-branch module, and compact table  
  https://arxiv.org/html/2411.15941v1#S3.F4

## Required information layers

1. **Main architecture:** input, stem, stages, head, prediction.
2. **Stage facts:** output spatial size, channels, repeat count, and transition.
3. **Block detail:** expand one representative innovation instead of every
   repeated block.
4. **Visual grammar:** explain tensor, transition, residual, merge, and repeat
   glyphs.
5. **Optional evidence panel:** a small configuration table, kernel grid, or
   quantitative inset only when it directly supports the architectural claim.

## Tensor grammar

- Tensor face area encodes spatial resolution using a bounded logarithmic scale.
- Prism depth encodes channels using a separate bounded logarithmic scale.
- Exact `H×W×C` remains visible; visual scale never replaces numeric labels.
- Use the multiplication symbol `×`, not the letter `x`.
- Align tensor centers along the main data path.

## Topology grammar

- Solid arrow: forward data flow.
- Outer orthogonal path: identity or residual.
- Circle `+`: element-wise addition.
- Wide merge node: concatenation, with the concatenation axis labeled.
- Explicit `↓2`, stride, or pooling marker: downsampling.
- `×N` badge: repeated block; explain whether the first repetition changes
  shape or stride.
- Grid glyph: kernel, window, or token grouping with actual spatial geometry.
- Transformation arrow: parameter fusion or train-to-inference conversion,
  visually distinct from forward data flow.
- Parallel lanes: channel or feature branches with one explicit fusion node.

## Composition

- Use a wide main plate for the macro network.
- Keep one inset below the main path for block detail.
- Place the legend outside the main topology.
- Use low-saturation stage bands, but keep arrows and exact dimensions darker.
- Use one semantic color per operation family, not one random color per layer.
- For comparison figures, lock common node positions and highlight only changed
  operators or routes.
- At paper size, stage titles, dimensions, and operators must remain readable.

## Failure patterns

- identical rectangles for every tensor;
- a residual block with no visible shortcut and add node;
- dimension changes implied only by a smaller box;
- dozens of repeated blocks drawn individually;
- arbitrary stage colors with no legend;
- a raw framework computation graph presented as a publication figure;
- block internals repeated in every stage instead of one inset.
