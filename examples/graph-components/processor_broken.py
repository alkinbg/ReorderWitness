"""Intentionally broken: one-pass label propagation does not merge entire components.

The connected components of an undirected graph must not depend on edge order.
This processor changes labels only for the endpoints of each input edge.
"""

from __future__ import annotations

import json
import sys

edges = []
for line in sys.stdin:
    if line.strip():
        edge = json.loads(line)
        edges.append((edge["u"], edge["v"]))

labels = {vertex: vertex for edge in edges for vertex in edge}
for u, v in edges:
    representative = min(labels[u], labels[v])
    labels[u] = labels[v] = representative

components: dict[str, list[str]] = {}
for vertex in sorted(labels):
    components.setdefault(labels[vertex], []).append(vertex)
for component in sorted(components.values()):
    print(json.dumps({"members": component}))
