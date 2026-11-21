import type { Graph, GraphEdge } from "../types";

export type Position = { x: number; y: number };
const PAGE_SIZE = 3;

export function startingConcept(graph: Graph): number | null {
  const counts = new Map<number, number>();
  for (const e of graph.edges) {
    counts.set(e.target, (counts.get(e.target) ?? 0) + (e.type === "PREREQUISITE_OF" ? 2 : 1));
    counts.set(e.source, (counts.get(e.source) ?? 0) + 1);
  }
  return [...graph.nodes].sort((a, b) => (counts.get(b.id) ?? 0) - (counts.get(a.id) ?? 0) || a.id - b.id)[0]?.id ?? null;
}

function neighbors(graph: Graph, id: number, positions: Map<number, Position>) {
  const priority = (e: GraphEdge) => e.type === "PREREQUISITE_OF" ? (e.target === id ? 0 : 1) : 2;
  const seen = new Set(positions.keys());
  return graph.edges.filter(e => e.source === id || e.target === id)
    .sort((a, b) => priority(a) - priority(b) || b.confidence - a.confidence || a.source - b.source || a.target - b.target)
    .flatMap(edge => {
      const other = edge.target === id ? edge.source : edge.target;
      if (seen.has(other)) return [];
      seen.add(other);
      return [{ other, edge }];
    });
}

export function focusGraph(graph: Graph, root: number, expanded: number[]) {
  const positions = new Map<number, Position>([[root, { x: 0, y: 0 }]]);
  const occupied = new Set(["0,0"]);
  for (const id of [root, ...expanded]) {
    const anchor = positions.get(id);
    if (!anchor) continue;
    const next = neighbors(graph, id, positions).slice(0, PAGE_SIZE);
    for (const [index, { other, edge }] of next.entries()) {
      const x = anchor.x + (edge.target === id ? -280 : 280);
      let y = anchor.y + (index - Math.floor(next.length / 2)) * 112;
      while (occupied.has(`${x},${y}`)) y += 112;
      occupied.add(`${x},${y}`);
      positions.set(other, { x, y });
    }
  }
  return {
    positions,
    remaining: (id: number) => neighbors(graph, id, positions).length,
    graph: {
      nodes: graph.nodes.filter(n => positions.has(n.id)),
      edges: graph.edges.filter(e => positions.has(e.source) && positions.has(e.target)),
    },
  };
}
