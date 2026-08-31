from __future__ import annotations

from typing import Any

from .types import RawVisualCandidate


def extract_raw_features(
    frames: list[Any],
    vision_client: Any | None = None,
) -> list[RawVisualCandidate]:
    """
    Extract raw visual features from a list of frames using the provided vision client.

    Args:
        frames (list[Any]): A list of frames (images) to process.
        vision_client (Any | None): An optional vision client for processing the frames.

    Returns:
        list[RawVisualCandidate]: A list of RawVisualCandidate objects representing
        the extracted visual features.
        
    yang dikembalikan adalah list dari RawVisualCandidate yang berisi kandidat visual mentah yang dihasilkan dari VLM.
    Tidak bisa langsung map ke canonical term disini.
    """
    if not frames:
        return []

    if vision_client is None:
        raise ValueError("vision_client must be provided for feature extraction.")

    raw_candidates: list[RawVisualCandidate] = []

    for frame in frames:
        result = vision_client.analyze(frame)
        for item in result.get("detections", []):
            source_frame = getattr(frame, "name", None)
            if source_frame is None and isinstance(frame, str):
                source_frame = frame

            raw_candidates.append(
                RawVisualCandidate(
                    label=str(item["label"]).strip(),
                    confidence=float(item.get("confidence", 0.0)),
                    source_frame=source_frame,
                )
            )

    return raw_candidates
