# PetEVA Runtime Process Lifecycle

## Initial Contract

Lifecycle source: local switch file.

Default path:

```text
runtime/peteva-runtime/state/pet-enabled.json
```

The runtime treats missing, empty, invalid, or disabled switch files as a stop
signal. This is deliberate: local-only desktop helpers should fail closed.

## States

| Switch State | Runtime Behavior |
| --- | --- |
| Missing file | Exit with a clear message |
| `{"enabled": false}` | Exit or close the pet window |
| `{"enabled": true, "unit": "eva-01"}` | Show Unit-01 using the local Codex pet spritesheet |
| Invalid JSON/text | Exit with a clear message |

## Future Extension Point

`peteva_runtime.lifecycle.PetStateProvider` is the only lifecycle interface the
window needs. `LocalSwitchFileProvider` implements the initial local switch
behavior. `CodexDesktopStateProvider` is a placeholder for a later confirmed
Codex Desktop state reader.

Do not implement `CodexDesktopStateProvider` until the real Codex Desktop state
location and schema are verified.
