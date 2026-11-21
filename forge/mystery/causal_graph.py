"""Causal graph of a case (docs/MYSTERY_DESIGN.md §9): what the reader must have solved before a
page can be used. Nodes carry `requires`; the graph must be a DAG in page order and the final
answer must depend on every puzzle and every evidence node (no orphan work, no shortcut).

Pattern after the requires/unlocks state graphs listed in docs/REFERENCES.md (ideas only)."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Node:
    id: str
    kind: str  # story | puzzle | evidence | final
    order: int  # position in the book (page order)
    requires: tuple[str, ...] = ()


@dataclass
class CausalGraph:
    nodes: dict[str, Node] = field(default_factory=dict)

    def add(self, id: str, kind: str, requires: tuple[str, ...] = ()) -> Node:
        if id in self.nodes:
            raise ValueError(f"duplicate node {id!r}")
        node = Node(id, kind, len(self.nodes), requires)
        self.nodes[id] = node
        return node

    def closure(self, id: str) -> set[str]:
        """Everything that must be done before `id` (transitive requirements)."""
        seen: set[str] = set()
        todo = [r for r in self.nodes[id].requires if r in self.nodes]
        while todo:
            n = todo.pop()
            if n not in seen:
                seen.add(n)
                todo += [r for r in self.nodes[n].requires if r in self.nodes]
        return seen

    def available(self, done: set[str]) -> list[str]:
        """Nodes the reader can do now (state filtering)."""
        return [n.id for n in self.nodes.values() if n.id not in done and set(n.requires) <= done]

    def problems(self, final: str = "final", min_inputs: int = 2) -> list[str]:
        out: list[str] = []
        if final not in self.nodes:
            return [f"graph has no {final!r} node"]
        for n in self.nodes.values():
            for r in n.requires:
                if r not in self.nodes:
                    out.append(f"{n.id} requires unknown node {r!r}")
                elif self.nodes[r].order >= n.order:
                    out.append(f"{n.id} needs {r}, which comes later in the book")
            if n.kind == "evidence":
                inputs = [
                    r for r in n.requires if r in self.nodes and self.nodes[r].kind == "puzzle"
                ]
                if len(inputs) < min_inputs:
                    out.append(f"{n.id} must depend on at least {min_inputs} puzzles")
        if out:
            return out
        need = self.closure(final)
        for n in self.nodes.values():
            if n.kind in ("puzzle", "evidence") and n.id not in need:
                out.append(f"{n.id} is not needed for the final answer")
        done: set[str] = set()  # walk: everything must become available, final last
        while True:
            nxt = [i for i in self.available(done) if i != final]
            if not nxt:
                break
            done.update(nxt)
        if set(self.nodes) - done != {final} or final not in self.available(done):
            out.append(f"unreachable nodes: {sorted(set(self.nodes) - done - {final})}")
        return out
