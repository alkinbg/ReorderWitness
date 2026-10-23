"""Reference implementation: union-find with path compression.

Each input edge links two vertices in an undirected graph. The partition into
connected components is invariant to the order in which edges are processed.
"""

from __future__ import annotations

import json
import sys

parent: dict[str, str] = {}


def find(vertex: str) -> str:
    parent.setdefault(vertex, vertex)
    if parent[vertex] != vertex:
        parent[vertex] = find(parent[vertex])
    return parent[vertex]


def union(a: str, b: str) -> None:
    ra, rb = find(a), find(b)
    if ra != rb:
        parent[max(ra, rb)] = min(ra, rb)


for line in sys.stdin:
    if line.strip():
        edge = json.loads(line)
        union(edge["u"], edge["v"])

components: dict[str, list[str]] = {}
for vertex in sorted(parent):
    components.setdefault(find(vertex), []).append(vertex)
for component in sorted(components.values()):
    print(json.dumps({"members": component}))
