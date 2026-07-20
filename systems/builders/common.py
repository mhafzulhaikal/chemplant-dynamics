from __future__ import annotations

import control as ct


def build_interconnected_system(
    *,
    syslist,
    connections,
    inplist,
    outlist,
    name: str,
):
    """Create an interconnected system with consistent list normalization."""
    return ct.InterconnectedSystem(
        syslist=list(syslist),
        connections=list(connections),
        inplist=list(inplist),
        outlist=list(outlist),
        name=name,
    )
