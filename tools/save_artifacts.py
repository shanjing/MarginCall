"""
This tool is used to save artifacts to session.state.
TODO: will dive more to find ouf if session.state is the best place to save artifacts.
"""
from google.adk.tools.tool_context import ToolContext
from google.genai import types

from tools.logging_utils import logger

# Map file extension -> MIME type for correct UI rendering (e.g. HTML/image display)
EXTENSION_TO_MIME = {
    ".html": "text/html",
    ".htm": "text/html",
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".gif": "image/gif",
    ".webp": "image/webp",
    ".svg": "image/svg+xml",
    ".json": "application/json",
    ".xml": "application/xml",
    ".csv": "text/csv",
}


def _mime_for_filename(filename: str) -> str:
    """Infer MIME type from filename extension; default to text/plain."""
    ext = "." + filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    return EXTENSION_TO_MIME.get(ext, "text/plain")


async def save_artifacts(tool_context: ToolContext, artifact: str, filename: str) -> str:
    data_bytes = artifact.encode("utf-8")
    mime_type = _mime_for_filename(filename)

    artifact_part = types.Part(
        inline_data=types.Blob(mime_type=mime_type, data=data_bytes),
    )
    try:
        await tool_context.save_artifact(filename, artifact_part)
    except Exception as e:
        logger.error(f"Error saving artifact: {e}")
        raise e
    return f"Artifact saved: {filename}"