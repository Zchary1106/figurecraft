# View selection

Choose the view before choosing the renderer.

| Reader question | View | Default scope |
|---|---|---|
| What is this product and who interacts with it? | System context / README overview | 3–8 elements |
| What deployable services and stores exist? | Container architecture | 5–15 elements |
| How is one service internally structured? | Component view | One boundary |
| Where do processes, pods, nodes, and regions run? | Deployment view | Physical runtime boundaries |
| What happens to one request or event? | Data path / sequence | One scenario |
| How does an entity change over time? | State machine / lifecycle | One entity |
| How do many domains and shared platforms relate? | System landscape | Macro domains plus summarized sections |
| How does a real model compute? | Computation graph | Fact view, then collapsed publication view |

## Splitting rule

Create an overview plus detail views when any condition is true:

- more than 15 visible elements;
- more than three nested boundary levels;
- both deployment and logical relationships are required;
- both read and write paths need explanation;
- edge crossings remain after stable layered layout;
- the smallest required text would fall below the output minimum.

The overview should link to details by stable IDs or matching titles. Do not
shrink one overloaded figure until it technically fits.

## Architecture text hierarchy

Use:

1. primary name;
2. technology or protocol;
3. one short responsibility description.

README overviews usually need only levels 1–2. Engineering component views may
use all three.

## Relationship text hierarchy

Use an action phrase as the primary label and a protocol or transport as
secondary metadata:

```text
submits experiment
HTTPS/JSON
```

Avoid labels that merely repeat the target node name.
