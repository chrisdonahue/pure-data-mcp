# `pd-mcp`

Basic MCP server for agentic interaction with vanilla Pure Data.

This project is intentionally shaped after the Max/MSP MCP workflow described in the ISMIR 2025 late-breaking demo paper and the associated Max reference implementation, but adapted to what is practical in plain vanilla Pd:

- bundled object docs for in-context lookup
- live patch creation and rewiring
- direct object/message/atom creation
- patch-state inspection
- runtime bang/message/number injection
- DSP on/off control

## Architecture

The system has two parts:

1. A Python MCP server that owns an authoritative graph model of the patch.
2. A vanilla Pd bridge patch that listens on UDP port `5000` and forwards dynamic patching messages into a managed subpatch canvas.

Instead of trying to delete or mutate arbitrary objects inside Pd one-at-a-time, the server updates its graph model and resynchronizes the target canvas by sending:

1. `clear`
2. object creation messages
3. optional hidden control receivers for explicitly controllable objects
4. connection messages

That tradeoff is deliberate. It is simpler and more reliable in vanilla Pd, while still feeling agentic from the MCP client side.

## Included Tools

- `list_pd_objects`
- `search_pd_objects`
- `get_pd_object_doc`
- `get_patch_state`
- `add_pd_object`
- `remove_pd_object`
- `connect_pd_objects`
- `disconnect_pd_objects`
- `set_object_text`
- `move_pd_object`
- `clear_patch`
- `sync_patch`
- `set_dsp`
- `send_bang_to_object`
- `send_message_to_object`
- `set_number`

## Project Layout

- `src/pd_mcp/server.py`: MCP tool definitions
- `src/pd_mcp/model.py`: in-memory patch graph and Pd index layout
- `src/pd_mcp/bridge.py`: UDP FUDI bridge to Pd
- `src/pd_mcp/pd_docs.json`: small bundled docs set for common vanilla objects
- `pd/pd_mcp_bridge.pd`: bridge patch to open in Pure Data

## Install

Using `uv`:

```bash
uv venv
source .venv/bin/activate
uv pip install -e .
```

Or with `pip`:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .
```

## Run

1. Open `pd/pd_mcp_bridge.pd` in vanilla Pure Data.
2. Keep the bridge patch open.
3. Start the MCP server:

```bash
python main.py
```

Environment variables:

- `PD_MCP_HOST` defaults to `127.0.0.1`
- `PD_MCP_PORT` defaults to `5000`

## Cursor MCP Config

Add something like this to your MCP config:

```json
{
  "mcpServers": {
    "pd-mcp": {
      "command": "/bin/zsh",
      "args": [
        "-lc",
        "cd /Users/chrisdonahue/Code/pd-mcp && source .venv/bin/activate && python main.py"
      ]
    }
  }
}
```

## Typical Workflow

1. Call `add_pd_object` a few times to create `obj`, `msg`, `text`, or atom boxes.
2. Use `connect_pd_objects` to wire them.
3. Only set `controllable=true` on `add_pd_object` when you want runtime tools like `send_message_to_object`, `send_bang_to_object`, or `set_number`.
4. Call `get_patch_state` whenever the agent needs a reliable snapshot.

Example object boxes:

- `box_type="obj", text="osc~ 440"`
- `box_type="obj", text="*~ 0.1"`
- `box_type="obj", text="dac~"`
- `box_type="msg", text="440"`
- `box_type="floatatom"`
- `box_type="obj", text="line~", controllable=true`

## Limitations

- The bundled docs are intentionally small, not a full export of the Pd manual.
- The server manages only the objects it created in the bridge patch's target subpatch.
- Selection introspection is not implemented in this first cut.
- Object attributes in the Max sense do not map cleanly onto vanilla Pd, so the API is text-centric instead.
- Because sync is graph-based, manual edits inside the managed target subpatch can be overwritten.

## Why This Shape

The Max paper emphasizes two ideas:

- documentation retrieval for in-context learning
- tool-based direct manipulation instead of raw patch-file generation

This server keeps those properties while using a safer Pd backend than the nascent Pd MCP implementations that mutate Pd more directly.
