from __future__ import annotations

from contextlib import asynccontextmanager
from dataclasses import dataclass
import os

from mcp.server.fastmcp import Context, FastMCP

from .bridge import PdUdpBridge
from .docs import get_object_doc, list_object_names, search_objects
from .model import BoxType, PatchModel


DEFAULT_PD_HOST = os.environ.get("PD_MCP_HOST", "127.0.0.1")
DEFAULT_PD_PORT = int(os.environ.get("PD_MCP_PORT", "5000"))


@dataclass(slots=True)
class ServerState:
    bridge: PdUdpBridge
    model: PatchModel


_fallback_state: ServerState | None = None


def _new_state() -> ServerState:
    return ServerState(
        bridge=PdUdpBridge(host=DEFAULT_PD_HOST, port=DEFAULT_PD_PORT),
        model=PatchModel(),
    )


@asynccontextmanager
async def lifespan(_: FastMCP):
    state = _new_state()
    try:
        yield {"state": state}
    finally:
        state.bridge.close()


def _build_mcp() -> FastMCP:
    # FastMCP's constructor changed across releases. Try the richer signature
    # first, then fall back to older variants used by earlier packages.
    variants = [
        {"name": "PureDataMCP", "description": "Basic MCP server for vanilla Pure Data", "lifespan": lifespan},
        {"name": "PureDataMCP", "lifespan": lifespan},
        {"name": "PureDataMCP"},
        {},
    ]

    last_error: TypeError | None = None
    for kwargs in variants:
        try:
            return FastMCP(**kwargs)
        except TypeError as exc:
            last_error = exc

    assert last_error is not None
    raise last_error


mcp = _build_mcp()


def _state(ctx: Context) -> ServerState:
    request_context = getattr(ctx, "request_context", None)
    lifespan_context = getattr(request_context, "lifespan_context", None)
    if isinstance(lifespan_context, dict):
        state = lifespan_context.get("state")
        if state is not None:
            return state

    global _fallback_state
    if _fallback_state is None:
        _fallback_state = _new_state()
    return _fallback_state


@mcp.tool()
def list_pd_objects(ctx: Context) -> list[str]:
    """Return known vanilla Pd object names from the bundled docs set."""
    return list_object_names()


@mcp.tool()
def search_pd_objects(query: str, ctx: Context) -> list[dict]:
    """Search the bundled vanilla Pd docs by name or description."""
    return search_objects(query)[:20]


@mcp.tool()
def get_pd_object_doc(object_name: str, ctx: Context) -> dict:
    """Return documentation for a single bundled vanilla Pd object."""
    doc = get_object_doc(object_name)
    if doc is None:
        return {
            "success": False,
            "error": "Unknown object name.",
            "suggestion": "Call list_pd_objects or search_pd_objects first.",
        }
    return doc


@mcp.tool()
def get_patch_state(ctx: Context) -> dict:
    """Return the server-side patch graph that is mirrored into Pd."""
    return _state(ctx).model.snapshot()


@mcp.tool()
def add_pd_object(
    ctx: Context,
    position: list[int],
    box_type: BoxType,
    text: str = "",
) -> dict:
    """Add an object, message, comment, or atom box to the managed Pd canvas.

    Args:
        position: Two integers [x, y].
        box_type: One of obj, msg, text, floatatom, symbolatom.
        text: Raw Pd box text, for example "osc~ 440" or "0.2".
    """
    if len(position) != 2:
        raise ValueError("position must be [x, y].")
    state = _state(ctx)
    obj = state.model.add_object(
        box_type=box_type,
        x=int(position[0]),
        y=int(position[1]),
        text=text,
    )
    sync = state.bridge.sync_model(state.model)
    return {
        "status": "success",
        "object": {
            "id": obj.object_id,
            "box_type": obj.box_type,
            "text": obj.describe(),
            "position": [obj.x, obj.y],
            "receive_symbol": obj.receive_symbol,
        },
        "sync": sync,
    }


@mcp.tool()
def remove_pd_object(ctx: Context, object_id: str) -> dict:
    """Remove an object from the managed canvas and rebuild the patch."""
    state = _state(ctx)
    removed = state.model.remove_object(object_id)
    sync = state.bridge.sync_model(state.model)
    return {
        "status": "success",
        "removed": {
            "id": removed.object_id,
            "box_type": removed.box_type,
            "text": removed.describe(),
        },
        "sync": sync,
    }


@mcp.tool()
def connect_pd_objects(
    ctx: Context,
    source_id: str,
    outlet_index: int,
    destination_id: str,
    inlet_index: int,
) -> dict:
    """Connect two managed objects and rebuild the patch."""
    state = _state(ctx)
    conn = state.model.connect(source_id, outlet_index, destination_id, inlet_index)
    sync = state.bridge.sync_model(state.model)
    return {
        "status": "success",
        "connection": {
            "source_id": conn.source_id,
            "outlet_index": conn.outlet_index,
            "destination_id": conn.destination_id,
            "inlet_index": conn.inlet_index,
        },
        "sync": sync,
    }


@mcp.tool()
def disconnect_pd_objects(
    ctx: Context,
    source_id: str,
    outlet_index: int,
    destination_id: str,
    inlet_index: int,
) -> dict:
    """Disconnect two managed objects and rebuild the patch."""
    state = _state(ctx)
    removed = state.model.disconnect(source_id, outlet_index, destination_id, inlet_index)
    sync = state.bridge.sync_model(state.model)
    return {"status": "success", "connection_removed": removed, "sync": sync}


@mcp.tool()
def set_object_text(ctx: Context, object_id: str, text: str) -> dict:
    """Update the text for an obj, msg, or text box and rebuild the patch."""
    state = _state(ctx)
    obj = state.model.get_object(object_id)
    obj.text = text
    sync = state.bridge.sync_model(state.model)
    return {
        "status": "success",
        "object": {
            "id": obj.object_id,
            "box_type": obj.box_type,
            "text": obj.describe(),
        },
        "sync": sync,
    }


@mcp.tool()
def move_pd_object(ctx: Context, object_id: str, position: list[int]) -> dict:
    """Move an object and rebuild the patch."""
    if len(position) != 2:
        raise ValueError("position must be [x, y].")
    state = _state(ctx)
    obj = state.model.get_object(object_id)
    obj.x = int(position[0])
    obj.y = int(position[1])
    sync = state.bridge.sync_model(state.model)
    return {
        "status": "success",
        "object": {
            "id": obj.object_id,
            "position": [obj.x, obj.y],
        },
        "sync": sync,
    }


@mcp.tool()
def clear_patch(ctx: Context) -> dict:
    """Delete all managed objects and connections."""
    state = _state(ctx)
    state.model.clear()
    sync = state.bridge.sync_model(state.model)
    return {"status": "success", "sync": sync}


@mcp.tool()
def sync_patch(ctx: Context) -> dict:
    """Re-send the current server-side patch model to Pd."""
    state = _state(ctx)
    return state.bridge.sync_model(state.model)


@mcp.tool()
def set_dsp(ctx: Context, enabled: bool) -> dict:
    """Turn Pd DSP on or off in the bridge patch."""
    state = _state(ctx)
    state.bridge.set_dsp(enabled)
    return {"status": "success", "dsp_enabled": enabled}


@mcp.tool()
def send_bang_to_object(ctx: Context, object_id: str) -> dict:
    """Send a bang into the left inlet of a managed object."""
    state = _state(ctx)
    obj = state.model.get_object(object_id)
    if not obj.receive_symbol:
        raise ValueError(f"Object {object_id} cannot receive messages.")
    state.bridge.send_to_receive(obj.receive_symbol, "bang")
    return {"status": "success", "object_id": object_id, "message": ["bang"]}


@mcp.tool()
def send_message_to_object(ctx: Context, object_id: str, message: list[str | int | float]) -> dict:
    """Send a Pd message into the left inlet of a managed object."""
    state = _state(ctx)
    obj = state.model.get_object(object_id)
    if not obj.receive_symbol:
        raise ValueError(f"Object {object_id} cannot receive messages.")
    state.bridge.send_to_receive(obj.receive_symbol, *message)
    return {"status": "success", "object_id": object_id, "message": list(message)}


@mcp.tool()
def set_number(ctx: Context, object_id: str, value: float) -> dict:
    """Set a floatatom or any float-accepting object by sending it a float."""
    state = _state(ctx)
    obj = state.model.get_object(object_id)
    if not obj.receive_symbol:
        raise ValueError(f"Object {object_id} cannot receive messages.")
    state.bridge.send_to_receive(obj.receive_symbol, value)
    return {"status": "success", "object_id": object_id, "value": value}


def run() -> None:
    mcp.run()


if __name__ == "__main__":
    run()
