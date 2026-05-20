"""STL file sanity checks for assertions in tests.

`is_valid_stl(path)` and `summarize_stl(path)` are deliberately lenient — they
verify that the file PARSES and contains a non-trivial mesh. Mechanical
correctness of the geometry is the developer's responsibility, not QA's.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass
class StlSummary:
    path: Path
    size_bytes: int
    triangle_count: int
    is_binary: bool
    bbox_min: tuple
    bbox_max: tuple


def _read_binary_header_triangle_count(path: Path) -> int | None:
    """ASCII STL has 'solid' header (mostly). Binary has 80-byte header + uint32 count.
    Returns the binary triangle count, or None if the file is ASCII."""
    with path.open("rb") as fh:
        header = fh.read(80)
        if header.lstrip().startswith(b"solid"):
            # Could still be a binary file labelled 'solid' — let numpy-stl decide.
            return None
        import struct
        count_bytes = fh.read(4)
        if len(count_bytes) < 4:
            return None
        (count,) = struct.unpack("<I", count_bytes)
        return count


def is_valid_stl(path: Path) -> bool:
    """Quick smoke check — file exists, has size, has triangles, parses."""
    try:
        summary = summarize_stl(path)
    except Exception:
        return False
    return (
        summary.size_bytes > 84
        and summary.triangle_count > 0
        # Sanity on bounding box: must have non-zero extent in at least one axis
        and any(mx > mn for mn, mx in zip(summary.bbox_min, summary.bbox_max))
    )


def summarize_stl(path: Path) -> StlSummary:
    """Parse the STL via numpy-stl and return summary stats.

    numpy-stl handles both ASCII and binary formats transparently.
    """
    from stl import mesh  # numpy-stl

    p = Path(path)
    size = p.stat().st_size
    binary_count = _read_binary_header_triangle_count(p)
    m = mesh.Mesh.from_file(str(p))

    min_xyz = (
        float(m.vectors[:, :, 0].min()),
        float(m.vectors[:, :, 1].min()),
        float(m.vectors[:, :, 2].min()),
    )
    max_xyz = (
        float(m.vectors[:, :, 0].max()),
        float(m.vectors[:, :, 1].max()),
        float(m.vectors[:, :, 2].max()),
    )

    return StlSummary(
        path=p,
        size_bytes=size,
        triangle_count=len(m.vectors),
        is_binary=binary_count is not None,
        bbox_min=min_xyz,
        bbox_max=max_xyz,
    )
