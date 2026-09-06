---
name: figurecraft-neural-networks
description: Creates publication-style neural-network and deep-learning architecture figures, including CNN plates, residual networks, encoder-decoder models, tensor flows, repeated blocks, skip connections, projection shortcuts, stage schedules, and block-detail insets. Use for neural network diagrams, CNN, ResNet, U-Net, Transformer blocks, 模型结构图, 神经网络图, 卷积网络, 残差网络, or academic method figures. Do not use for ordinary software architecture or statistical charts.
license: MIT
compatibility: Requires the sibling figurecraft core skill and Python 3.11.
metadata:
  author: figurecraft
  version: "0.26.0"
---

# FigureCraft Neural Networks

Create an architecture plate, not a generic sequence of equal rectangles.

## Required information layers

1. Macro path: input, stem, stages, head, prediction.
2. Stage facts: spatial size, channels, repeat count, transition, and stride.
3. Representative block inset: expand only the key block once.
4. Visual grammar or stage schedule: explain glyphs and exact configuration.

## Workflow

1. Establish the factual topology from model code, configuration, or explicit
   user input. Never infer hidden layer sizes.
2. Use `diagram.cnn-architecture` for professional CNN/residual plates.
   Use explicit `diagram.neural-network` nodes/edges for U-Net, Transformer, or
   arbitrary branching. The CNN plate does not reconstruct an executable model.
3. Encode spatial size in bounded tensor face area and channels in bounded prism
   depth, while always printing exact `H×W×C`.
4. Use explicit glyphs for add, concat, downsample, projection, residual,
   repeated blocks, and training-only paths.
5. Reserve separate lanes before routing skip connections.
6. Locate sibling `figurecraft/scripts/figure.py`, validate, render, and lint.
7. Inspect the image at final paper size and deliver SVG, source, manifest, and
   editable Draw.io when requested.

## Publication rules

- Residual paths terminate at a visible add node.
- Repeated blocks use `×N`; do not draw all copies.
- Downsampling shows stride or `↓2`, not only a smaller tensor.
- Use one inset for block detail and a separate table/legend.
- Color encodes operation family, not arbitrary stage decoration.
- Distinguish conceptual scale from exact executable structure.
- Declare visible provenance and final output medium. Use core `render-set`
  for a compact stage overview and separate block details when the complete
  plate fails final-size readability. Do not solve it by shrinking annotations.

## Blocking failures

Invalid topology, inconsistent dimension order, overlapping block/shortcut
cards, skip lines through nodes, missing merge semantics, or unreadable paper
scale.
