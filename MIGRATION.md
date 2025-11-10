# Migration Guide: Real-time Bridge

This document describes the transition from file-based state exchange to the
new socket bridge used by the EmblemMind tactical agent.

## Summary

* The BizHawk Lua scripts now stream state directly to the Python agent via a
  TCP connection on `localhost:17653`.
* The Python side runs `emblem.bridge.server.BridgeServer`, accepting a single
  client and replying with action packets.
* JSON messages are line-delimited and conform to the schema documented in the
  repository README and the `bizhawk/bridge.lua` file.

## Enabling the bridge

1. Install the Lua script `bizhawk/bridge.lua` into your BizHawk scripts
   directory and `require` it from your main memory reader.
2. Ensure the Python process is running before starting BizHawk. Use the
   configuration file `config.yaml` to control connectivity:

```yaml
bridge:
  enabled: true
  timeout_ms: 100
port: 17653
```

3. The old polling loop that read `data/fe_state.txt` and `data/fe_map.txt` is
   now disabled when `bridge.enabled` is true. Set the flag to `false` to fall
   back to the legacy behaviour during debugging.

## Message flow

* **State → Python**: BizHawk sends `{"t":"state", ...}` for every frame (or
  when a watch flag triggers). The payload includes the turn, cursor position,
  unit roster, terrain probes, and chapter objectives.
* **Action ← Python**: The agent responds with
  `{"t":"action","kind":...,"unit_id":...,"path":...}` whenever it is ready
  to commit input.
* **Heartbeat**: Lightweight ping/pong messages keep the connection alive
  during planning windows.

## Determinism hooks

* `bridge.capture_savestate(slot)` and `bridge.load_savestate(slot)` wrap the
  built-in BizHawk savestate API so the Python planner can rewind before a
  rollout.
* Turbo helpers toggle BizHawk speed-up when the planner is searching. You can
  call `bridge.enable_planning_turbo()` or `bridge.enable_enemy_turbo()` based on
  your heuristics.

## Cleaning up legacy scripts

* `fe_memory_reader.lua` and Python utilities such as
  `emblemmind_snapshot.TurnSnapshot.from_files` remain for archival purposes but
  are no longer part of the live control path when the bridge is enabled.
* The new tests in `tests/test_bridge_codec.py` ensure JSON round-trips work and
  the socket server can exchange heartbeat/action messages.

## Next steps

* Update your automation scripts to start the Python process (or CLI command)
  before BizHawk loads the Lua automation script.
* Extend the bridge to send legal-action metadata, RNG seeds, and savestate
  fingerprints as they become available in later milestones.
