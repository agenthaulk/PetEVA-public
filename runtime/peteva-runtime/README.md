# PetEVA Lightweight Runtime

This is the Phase 3 lightweight runtime. It is a normal local process, not a
macOS App bundle.

Initial lifecycle mode: local switch file.

Future lifecycle mode: a separate provider can read Codex Desktop state after
that storage location is confirmed. The current version intentionally does not
guess or inspect Codex Desktop internals.

## Run

Use the project wrapper from the repository root. On macOS it auto-builds and
runs the lightweight Swift/AppKit backend so the pet is a real transparent,
borderless process window. The Tk backend remains available as a fallback with
`--backend tk`.

```bash
scripts/peteva-runtime enable
scripts/peteva-runtime run
```

The default active unit is configured in `config/default.yaml`:

```yaml
runtime:
  pet:
    activeUnit: eva-02
```

Override it for a single switch-file update:

```bash
scripts/peteva-runtime enable --unit eva-01
scripts/peteva-runtime enable --unit eva-02
```

Useful movement tuning options:

```bash
scripts/peteva-runtime run --move-ms 120 --step-pixels 8
scripts/peteva-runtime run --backend macos
scripts/peteva-runtime run --backend tk
```

Default movement and reminder values live in `config/default.yaml` under
`runtime.window`, `runtime.motion`, and `runtime.reminders`. The CLI flags above
are short-term overrides; the config file is the normal place to edit behavior.

Reminder timing, text, and optional display duration are configured per reminder:

```yaml
runtime:
  reminders:
    defaultDisplaySeconds: 55
    water:
      enabled: true
      intervalMinutes: 20
      message: 该喝水了。
      displaySeconds: 55
    activity:
      enabled: true
      intervalMinutes: 30
      message: 起来活动一下。
```

`displaySeconds` can be omitted on an individual reminder. In that case the
runtime uses `defaultDisplaySeconds`. Display time is capped at 60 seconds.

Disable and stop the runtime:

```bash
scripts/peteva-runtime disable
```

Default switch file:

```text
runtime/peteva-runtime/state/pet-enabled.json
```

Supported switch content:

```json
{
  "enabled": true,
  "unit": "eva-02"
}
```

Text values also work: `enabled`, `disabled`, `true`, `false`, `1`, `0`.

## Behavior

- If the switch file is missing or disabled, the runtime exits clearly.
- If enabled, the runtime opens a small always-on-top window for the configured unit.
- The initial window position is chosen uniformly inside the visible screen area, rather than always starting in the lower-right corner.
- The macOS backend reads transparent PNG frames from `assets/codex-pets/<unit>/source/frames`.
- The macOS backend uses a borderless transparent `NSWindow`, not a normal title-bar window.
- The close/shrink/grow controls are hidden by default and appear only while the pointer is over the pet.
- The pet stays still for about 70% of movement segments.
- Moving segments use `runtime.motion.directionStrategy: uniform`: choose a direction axis from `horizontalPercent` / `verticalPercent`, then choose the sign within that axis uniformly.
- The default direction mix is vertical:horizontal = 9:1. Vertical segments use jump frames and split uniformly between up and down.
- Horizontal segments choose among enabled ground forms (`walk`, `run`, `crawl`) using config weights, then split uniformly between left and right.
- Jump segments apply a real height arc; the default apex is about 1.2x the pet window height.
- The movement rows use twelve-frame loops from `source/frames/2026-05-13-<unitPrefix>-motion-12frame/runtime-12frame-clean/`: walking, running, crawling, vertical-jump, diagonal-jump, and diagonal-jump-right.
- Rebuild Unit-01 with `scripts/peteva-python scripts/build_unit01_12frame_motion_pack.py` after replacing the source strips. Build the initial Unit-02 fallback pack with `scripts/peteva-python scripts/build_unit02_motion_pack.py`.
- Reminder interval, text, enabled state, and optional display duration are read
  from `config/default.yaml`.
- The default config reminds the user to drink water every 20 minutes and to
  stand up and move every 30 minutes.
- Reminder text is displayed for at most 60 seconds; the default config uses 55
  seconds.
- Movement renders like a small marquee: each frame clears the previous sprite before drawing the next one, avoiding stacked/ghosted frames.
- Movement reuses local transparent motion-pack rows and falls back to existing spritesheet rows if the pack is missing.
- The runtime polls the switch file and exits when it becomes disabled.
- No network access is used.
