from mcp.server.fastmcp.exceptions import ToolError


def unwrap_data(envelope: dict) -> list:
    """Items of a ``{code, data, message}`` envelope (schedule API)."""
    return envelope.get("data") or []


def unwrap_result(envelope: dict) -> list:
    """Items of a ``{error_code, error_message, result}`` envelope (record book, booking APIs)."""
    return envelope.get("result") or []


def checked_result(envelope: dict):
    """Raw ``result`` of an ``{error_code, error_message, result}`` envelope; a non-zero code raises."""
    if envelope.get("error_code"):
        raise ToolError(envelope.get("error_message") or f"API error {envelope['error_code']}")
    return envelope.get("result")
