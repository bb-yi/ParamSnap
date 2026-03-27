# ParamSnap

ParamSnap is a Blender add-on for saving, restoring, and swapping parameter snapshots.

It is designed for workflows where you repeatedly jump between different settings on the same scene, object, modifier, material, or animation datablock. Instead of manually rewriting values, you can store them as snapshots and bring them back with one click.

## What It Does

ParamSnap lets you:

- Save any supported Blender property into a snapshot
- Group multiple properties into reusable snapshot sets
- Restore stored values back to the target properties
- Update stored values from the current scene state
- Swap current values and stored values
- Import and export snapshots as JSON
- Copy and paste snapshots through the clipboard

## Why It Is Useful

ParamSnap is especially helpful for:

- Geometry Nodes parameter presets
- Animation setup switching
- Material and shader state variations
- Shape key and action assignment snapshots
- Scene setup comparisons during look-dev or iteration

## Key Features

### Property Snapshot Workflow

Right-click a property anywhere Blender exposes a data path for it, then add it to the active snapshot. ParamSnap stores both the value and the property target.

### Multi-Parameter Snapshots

Each snapshot can contain multiple parameters, so a single click can restore a coordinated setup instead of one property at a time.

### Update, Sync, and Swap

- `Sync` applies stored values to the current targets
- `Update` captures the current values as the new stored values
- `Swap` exchanges the current values and stored values

### JSON Import and Export

Snapshots can be exported to a JSON file, copied to the clipboard, imported from JSON, or pasted from the clipboard.

### More Robust Target Resolution

ParamSnap does not rely only on a raw full data path anymore. It also stores the root datablock reference and a relative property path, which helps snapshots survive datablock renames such as:

- object renaming
- material renaming
- collection renaming
- action renaming

## Where To Find It

Open:

`3D View` -> `Sidebar` -> `ParamSnap`

The panel also adds `Add to Active Snapshot` actions to supported property context menus and animation panels.

## Quick Start

1. Create or select a snapshot in the ParamSnap panel.
2. Right-click a property and choose `Add to Active Snapshot`.
3. Repeat for any other properties you want in the same snapshot.
4. Use `Sync`, `Update`, or `Swap` on a single parameter or the full snapshot.

## Compatibility

- Blender `4.2+`
- Extension manifest included
- Clipboard and file permissions declared for JSON import/export

## Current Limitations

ParamSnap is much more resilient to datablock renames, but some links can still break if the property structure itself changes, for example:

- a modifier is removed or renamed
- a node group interface socket key changes
- the target datablock is deleted

In those cases, the snapshot entry will remain visible, but the target may need to be re-linked manually.
