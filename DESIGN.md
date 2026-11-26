---
name: InnovaTransport
description: Dark control room for video based traffic analysis.
colors:
  ground: "#09090b"
  card: "rgba(24,24,27,.5)"
  inset: "#111114"
  field: "#18181b"
  raised: "#27272a"
  border: "rgba(255,255,255,.055)"
  border-strong: "rgba(255,255,255,.13)"
  ink: "#f4f4f5"
  muted: "#a1a1aa"
  dim: "#a1a1aa"
  action: "#4f46e5"
  action-hover: "#6366f1"
  action-soft: "#a5b4fc"
  success: "#86efac"
  danger: "#fca5a5"
typography:
  headline:
    fontFamily: "Avenir Next, -apple-system, BlinkMacSystemFont, Segoe UI, sans-serif"
    fontSize: "22px"
    fontWeight: 650
    lineHeight: 1.2
    letterSpacing: "-.03em"
  title:
    fontFamily: "Avenir Next, -apple-system, BlinkMacSystemFont, Segoe UI, sans-serif"
    fontSize: "14px"
    fontWeight: 620
    letterSpacing: "-.015em"
  body:
    fontFamily: "Avenir Next, -apple-system, BlinkMacSystemFont, Segoe UI, sans-serif"
    fontSize: "12px"
    lineHeight: 1.5
  label:
    fontFamily: "ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace"
    fontSize: "12px"
    fontWeight: 500
  metric:
    fontFamily: "ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace"
    fontSize: "32px"
    fontWeight: 600
    lineHeight: 1
    letterSpacing: "-.04em"
rounded:
  surface: "16px"
  viewer: "12px"
  inset: "9px"
  button: "8px"
  field: "7px"
  chip: "6px"
spacing:
  xs: "4px"
  sm: "8px"
  md: "12px"
  gutter: "16px"
  panel: "18px"
  section: "22px"
components:
  card:
    backgroundColor: "{colors.card}"
    textColor: "{colors.ink}"
    rounded: "{rounded.surface}"
    padding: "{spacing.panel}"
  button-primary:
    backgroundColor: "{colors.action}"
    textColor: "{colors.ink}"
    rounded: "{rounded.button}"
    padding: "8px 14px"
    height: "36px"
  button-primary-hover:
    backgroundColor: "{colors.action-hover}"
  button-secondary:
    backgroundColor: "{colors.raised}"
    textColor: "{colors.ink}"
    rounded: "{rounded.field}"
    padding: "7px 10px"
  input:
    backgroundColor: "{colors.field}"
    textColor: "{colors.ink}"
    rounded: "{rounded.field}"
    height: "34px"
---

# Design System: InnovaTransport

## Overview

**Creative North Star: "The Control Room"**

A dense, calm workspace for reading video, configuring count zones, and checking traffic results. The interface uses nearly black ground, translucent zinc cards, fine borders, and compact technical data. Indigo marks available actions; status colors carry specific meaning.

**Key Characteristics:**
- Dark zinc ground and lightly raised bento surfaces.
- Compact sans serif labels with monospace, tabular telemetry.
- The calibration grid appears inside the video viewer only.

## Colors

The palette is mostly neutral: `ground`, `card`, `inset`, and `field` establish depth; `ink`, `muted`, and `dim` establish hierarchy. `action` and `action-hover` are reserved for primary controls and selected tools. `action-soft` supports focus, range controls, and data bars. Green `success` and red `danger` indicate state.

**The Local Grid Rule.** Keep the 26px calibration grid inside the video viewer; the page ground and cards stay unpatterned.

## Typography

Avenir Next with system sans fallbacks carries headings and prose. Monospace is reserved for counts, time, telemetry, metadata, table headers, and compact workflow labels. Secondary technical labels use 12px type. Use tabular numerals so changing metrics do not shift.

## Layout

At wide widths, a 240–268px sidebar sits beside a two column workspace; video and metrics occupy the larger column, configuration the smaller. The analysis panel spans both. The shell caps at 1900px with 16px main gaps. At 1050px the sidebar moves above the workspace. At 760px the content stacks in this order: video, configuration, metrics, report. At 560px metric cards stack individually. Preserve the 16:9 video area.

## Elevation & Depth

Cards use a translucent `#18181b` surface, a `border` hairline, and the structural shadow `0 22px 44px rgba(0,0,0,.22), 0 5px 12px rgba(0,0,0,.16)`. Inset sections use darker solid zinc without another large shadow. Controls may lift 1px on hover; the modal uses a deeper shadow and blurred backdrop.

## Shapes

Primary panels and metric cards use 16px corners; the video uses 12px. Buttons, fields, chips, and nested sections use smaller 6–9px corners. Borders remain thin and low contrast. The video frame clips overlays and grid to its rounded boundary.

## Components

Primary buttons use `action`, a 1px `action-hover` border, white text, and 8px 14px padding. Hover changes the fill to `action-hover` and lifts 1px. Secondary controls use raised zinc and a stronger neutral border. Fields use the solid `field` fill, 34px height, and a visible indigo focus outline. Mode switches and toolbar buttons use a dark inset track and a filled selected state. Metric cards keep figures monospace and supporting labels subdued. Archive rows use a compact hover and active fill.

## Do's and Don'ts

### Do:
- **Do** use indigo for actions, selection, focus, and measured progress.
- **Do** set technical values and changing counts in tabular monospace.
- **Do** keep status colors tied to actual success, review, or danger states.

### Don't:
- **Don't** extend the calibration grid beyond the video viewer.
- **Don't** add bright decoration to the ground or card surfaces.
- **Don't** use accent color for routine body copy or neutral metadata.
