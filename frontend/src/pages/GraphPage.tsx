import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import type { FormEvent } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { Network } from "vis-network";
import { api } from "../api";
import { ErrorBox, Loading, MasteryBadge, MasteryBar, Panel } from "../components/ui";
import type {
  ConceptDetail,
  Graph,
  GraphEdge,
  GraphNode,
  Prerequisite,
  RelatedConcept,
} from "../types";
import { masteryStatus } from "../types";
import { focusGraph, startingConcept, type Position } from "./focusedGraph";
import MathText from "../components/MathText";

const STATUS_COLORS: Record<string, { background: string; border: string }> = {
  MASTERED: { background: "#1f6f43", border: "#3fb950" },
  WEAK: { background: "#6b5216", border: "#e3b341" },
  UNKNOWN: { background: "#2c3140", border: "#8b95a5" },
};

function nodeColor(node: GraphNode) {
  return STATUS_COLORS[masteryStatus(node.mastery)];
}

const EDGE_LABELS: Record<string, string> = {
  PREREQUISITE_OF: "Prerequisite", RELATED_TO: "Related", PART_OF: "Part of",
  EXAMPLE_OF: "Example of", DERIVED_FROM: "Derived from", CONTRADICTS: "Contradicts",
};
const EDGE_COLORS: Record<string, string> = {
  PREREQUISITE_OF: "#7aa2f7", RELATED_TO: "#c6a5f4", PART_OF: "#55c7c2",
  EXAMPLE_OF: "#f5be67", DERIVED_FROM: "#ee92b8", CONTRADICTS: "#ff797a",
};
const edgeKey = (e: GraphEdge) => `${e.source}-${e.type}-${e.target}`;

const EDGE_VERBS: Record<string, string> = {
  PREREQUISITE_OF: "is a prerequisite for", RELATED_TO: "is related to", PART_OF: "is part of",
  EXAMPLE_OF: "is an example of", DERIVED_FROM: "is derived from", CONTRADICTS: "contradicts",
};
function EdgeDetail({ edge, source, target }: { edge: GraphEdge; source: string; target: string }) {
  const [passage, setPassage] = useState<Awaited<ReturnType<typeof api.getPassage>>>();
  const [error, setError] = useState("");
  useEffect(() => {
    let active = true;
    if (edge.evidence_source_id) api.getPassage(edge.evidence_source_id).then(result => {
      if (active) setPassage(result);
    }).catch(err => { if (active) setError(err.message); });
    return () => { active = false; };
  }, [edge.evidence_source_id]);
  return <Panel title="Selected relationship">
    <p><strong>{source}</strong> {EDGE_VERBS[edge.type]} <strong>{target}</strong>.</p>
    {error ? <ErrorBox error={error} /> : passage ? <details open>
      <summary>{passage.title}{passage.page != null && ` · page ${passage.page}`}</summary>
      <MathText text={passage.text} /><Link to={`/chat?lecture=${passage.document_id}`}>Study this lecture</Link>
    </details> : <p className="hint">{edge.evidence_source_id ? "Loading passage…" : "No source passage recorded for this connection."}</p>}
  </Panel>;
}

export default function GraphPage() {
  const [params, setParams] = useSearchParams();
  const requested = Number(params.get("concept"));
  return <ConceptGraph key={requested} requested={requested}
    centerOn={id => setParams({ concept: String(id) })} />;
}

function ConceptGraph({ requested, centerOn }: { requested: number; centerOn: (id: number) => void }) {
  const containerRef = useRef<HTMLDivElement>(null);
  const networkRef = useRef<Network | null>(null);
  const view = useRef<{ key: string; scale: number; position: Position; nodes: Record<string, Position> } | null>(null);
  const [graph, setGraph] = useState<Graph | null>(null);
  const [error, setError] = useState("");
  const [selection, setSelectedId] = useState<number | null>(null);
  const [full, setFull] = useState(false);
  const [expanded, setExpanded] = useState<number[]>([]);
  const [selectedEdge, setSelectedEdge] = useState<GraphEdge | null>(null);
  const [detail, setDetail] = useState<ConceptDetail | null>(null);
  const [prereqs, setPrereqs] = useState<Prerequisite[]>([]);
  const [related, setRelated] = useState<RelatedConcept[]>([]);
  const [formError, setFormError] = useState("");
  const [detailError, setDetailError] = useState("");

  const load = useCallback(async () => {
    try {
      const data = await api.getGraph();
      setGraph(data);
      setError("");
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  const choices = useMemo(
    () => [...(graph?.nodes ?? [])].sort((a, b) => a.name.localeCompare(b.name) || a.id - b.id),
    [graph],
  );
  const focus = useMemo(() => graph && (graph.nodes.some(n => n.id === requested)
    ? requested : startingConcept(graph)), [graph, requested]);
  const selectedId = selection ?? focus;
  const focused = useMemo(() => graph && !full && focus !== null
    ? focusGraph(graph, focus, expanded) : null, [graph, full, focus, expanded]);
  const visibleGraph = focused?.graph ?? graph;
  const viewKey = full ? "full" : String(focus);
  const remaining = selectedId !== null ? focused?.remaining(selectedId) ?? 0 : 0;
  const nameOf = (id: number) => graph?.nodes.find(n => n.id === id)?.name ?? String(id);
  function zoom(factor: number) {
    const network = networkRef.current;
    if (network) network.moveTo({ scale: Math.max(0.08, Math.min(4, network.getScale() * factor)) });
  }

  useEffect(() => {
    const container = containerRef.current;
    if (!container || !visibleGraph?.nodes.length) return;

    const saved = view.current?.key === viewKey ? view.current : null;
    const nodes = visibleGraph.nodes.map((node) => {
      const color = nodeColor(node);
      const mastery =
        node.mastery === null ? "No mastery evidence yet" : `Estimated mastery ${Math.round(node.mastery * 100)}%`;
      return {
        id: node.id,
        label: node.name,
        title: `Concept #${node.id} · ${mastery}`,
        ...(saved?.nodes[node.id] ?? focused?.positions.get(node.id)),
        shape: "box",
        margin: { top: 10, right: 14, bottom: 10, left: 14 },
        borderWidth: 1.5,
        widthConstraint: { maximum: 190 },
        font: { size: 15, face: "Segoe UI, sans-serif", color: "#e6e9f0" },
        color: {
          ...color,
          highlight: { background: "#253757", border: "#a9c6ff" },
          hover: { background: "#293343", border: "#aab6c9" },
        },
      };
    });
    const edges = visibleGraph.edges.map((edge) => ({
      id: edgeKey(edge),
      from: edge.source,
      to: edge.target,
      title: `${EDGE_LABELS[edge.type] ?? edge.type} (Confidence ${Math.round(edge.confidence * 100)}%)`,
      arrows: !["RELATED_TO", "CONTRADICTS"].includes(edge.type) ? "to" : undefined,
      dashes: edge.type === "RELATED_TO" ? [6, 4] : undefined,
      color: { color: EDGE_COLORS[edge.type], highlight: "#fff" },
      width: edge.type === "PREREQUISITE_OF" ? 2 : 1.2,
      smooth: { enabled: true, type: "cubicBezier", forceDirection: "horizontal", roundness: 0.4 },
      font: { size: 11, color: "#9aa3b5", strokeWidth: 0 },
    }));

    const network = new Network(
      container,
      { nodes, edges },
      {
        layout: { randomSeed: 7, improvedLayout: !focused },
        physics: focused ? false : {
          barnesHut: { gravitationalConstant: -4500, springLength: 170 },
          stabilization: { iterations: 200 },
        },
        interaction: { hover: true, tooltipDelay: 100 },
        edges: {
          smooth: { enabled: true, type: "cubicBezier", forceDirection: "horizontal", roundness: 0.4 },
        },
      },
    );
    network.on("click", (params) => {
      const id = params.nodes[0];
      if (typeof id === "number") {
        setSelectedId(id);
        setSelectedEdge(null);
      } else {
        setSelectedEdge(visibleGraph.edges.find(e => edgeKey(e) === params.edges[0]) ?? null);
      }
    });
    if (saved) network.moveTo({ position: saved.position, scale: saved.scale });
    else if (focused) network.fit({ animation: false, maxZoomLevel: 1.1 });
    networkRef.current = network;
    return () => {
      view.current = { key: viewKey, scale: network.getScale(), position: network.getViewPosition(), nodes: network.getPositions() };
      network.destroy();
      networkRef.current = null;
    };
  }, [visibleGraph, focused, viewKey]);

  useEffect(() => {
    if (selectedId !== null && visibleGraph?.nodes.some((node) => node.id === selectedId)) {
      networkRef.current?.selectNodes([selectedId]);
    } else {
      networkRef.current?.unselectAll();
    }
  }, [selectedId, visibleGraph]);

  // Load the side-panel detail when a node is selected.
  useEffect(() => {
    let active = true;
    setDetail(null);
    setDetailError("");
    setFormError("");
    if (selectedId === null) return;
    void (async () => {
      try {
        const [detailRes, prereqRes, relatedRes] = await Promise.all([
          api.getConcept(selectedId),
          api.getPrerequisites(selectedId),
          api.getRelated(selectedId),
        ]);
        if (!active) return;
        setDetail(detailRes);
        setPrereqs(prereqRes);
        setRelated(relatedRes);
      } catch (e) {
        if (active) setDetailError(e instanceof Error ? e.message : String(e));
      }
    })();
    return () => { active = false; };
  }, [selectedId, graph]);

  async function submitRelationship(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    if (selectedId === null || !detail) return;
    const element = e.currentTarget;
    const form = new FormData(element);
    const target = String(form.get("target") ?? "").trim();
    const relationType = String(form.get("relation_type") ?? "PREREQUISITE_OF");
    const confidence = Number(form.get("confidence") ?? 0.7);
    if (!target) return;
    setFormError("");
    try {
      await api.createRelationship(detail.name, target, relationType, confidence);
      element.reset();
      await load();
    } catch (err) {
      setFormError(err instanceof Error ? err.message : String(err));
    }
  }

  return (
    <div className="page graph-page">
      <header className="page-header">
        <div>
          <h1>Knowledge graph</h1>
          <p className="page-subtitle">Select a concept to explore its connections. Drag to pan and scroll to zoom.</p>
        </div>
        <div className="toolbar">
          <span className="legend">
            <i className="legend-dot legend-mastered" /> Mastered
            <i className="legend-dot legend-weak" /> Needs practice
            <i className="legend-dot legend-unknown" /> Unknown
          </span>
          <button className="btn" onClick={() => void load()}>
            Refresh
          </button>
        </div>
      </header>

      {error ? <ErrorBox error={error} /> : null}

      <div className="graph-controls">
        <label>Choose a concept
          <select value={focus ?? ""} disabled={!choices.length} onChange={event => centerOn(Number(event.target.value))}>
            {!choices.length && <option value="">No concepts yet</option>}
            {choices.map((node) => <option key={node.id} value={node.id}>{node.name} · Concept #{node.id}</option>)}
          </select>
        </label>
        <button className="btn" disabled={focus === null} onClick={() => { setFull(!full); setSelectedEdge(null); setSelectedId(null); }}>
          {full ? "Return to focus" : "Show full graph"}
        </button>
        <button className="btn" disabled={!visibleGraph?.nodes.length} onClick={() => networkRef.current?.fit()}>
          Fit to view
        </button>
        <button className="btn" aria-label="Zoom out" disabled={!choices.length} onClick={() => zoom(1 / 1.3)}>−</button>
        <button className="btn" aria-label="Zoom in" disabled={!choices.length} onClick={() => zoom(1.3)}>+</button>
        {visibleGraph && <span className="hint">Showing {visibleGraph.nodes.length} of {choices.length} concepts</span>}
      </div>
      {!!visibleGraph?.edges.length && <div className="edge-legend" aria-label="Relationship colors">
        {Object.entries(EDGE_LABELS).filter(([type]) => visibleGraph.edges.some(e => e.type === type)).map(([type, label]) =>
          <span key={type}><i style={{ borderColor: EDGE_COLORS[type], borderTopStyle: type === "RELATED_TO" ? "dashed" : "solid" }} />{label}</span>)}
      </div>}

      <div className="graph-layout">
        <div className="graph-stage">
          <div className="graph-canvas" ref={containerRef} aria-label="Concepts and relationships" />
          {!visibleGraph && !error && !detailError && <div className="graph-message"><Loading text="Loading graph…" /></div>}
          {visibleGraph?.nodes.length === 0 && <p className="graph-message">Upload learning material to see your graph here.</p>}
        </div>

        <aside className="graph-sidebar">
          {selectedEdge && <EdgeDetail key={edgeKey(selectedEdge)} edge={selectedEdge} source={nameOf(selectedEdge.source)} target={nameOf(selectedEdge.target)} />}
          {detailError ? <ErrorBox error={detailError} /> : selectedId === null || detail?.id !== selectedId ? (
            <Panel title="Concept details">
              <p className="empty">{selectedId === null ? "Choose a concept by name, or click a node." : "Loading concept…"}</p>
            </Panel>
          ) : (
            <>
              <Panel title={`${detail.name} · Concept #${detail.id}`} extra={<MasteryBadge mastery={graph?.nodes.find((n) => n.id === detail.id)?.mastery} />}>
                <MasteryBar mastery={graph?.nodes.find((n) => n.id === detail.id)?.mastery} />
                <MathText text={detail.description || "No description available."} />
                {focused && <button className="btn btn-primary expand-connections" disabled={!remaining}
                  onClick={() => setExpanded(prev => [...prev, detail.id])}>
                  {remaining ? `Show ${Math.min(3, remaining)} more connection${remaining === 1 ? "" : "s"}` : "All connections shown"}
                </button>}
                {detail.id !== focus && <button className="btn" onClick={() => centerOn(detail.id)}>Focus on this concept</button>}
                <details><summary>Prerequisites ({prereqs.length})</summary>
                {prereqs.length === 0 ? (
                  <p className="empty">No prerequisites recorded.</p>
                ) : (
                  <ul className="link-list">
                    {prereqs.map((item) => (
                      <li key={item.concept.id}>
                        <button className="item-link" onClick={() => centerOn(item.concept.id)}>{item.concept.name}</button>
                        {item.distance > 1 ? <span className="hint"> (Distance {item.distance})</span> : null}
                      </li>
                    ))}
                  </ul>
                )}
                </details><details><summary>Related concepts ({related.length})</summary>
                {related.length === 0 ? (
                  <p className="empty">No related concepts recorded.</p>
                ) : (
                  <ul className="link-list">
                    {related.map((item) => (
                      <li key={`${item.concept.id}-${item.relation_type}`}>
                        <button className="item-link" onClick={() => centerOn(item.concept.id)}>{item.concept.name}</button>
                        <span className="hint"> ({EDGE_LABELS[item.relation_type]})</span>
                      </li>
                    ))}
                  </ul>
                )}
                </details>
                {detail.source_chunks.length > 0 ? (
                  <>
                    <h3>Sources ({detail.source_chunks.length})</h3>
                    <div className="chunk-list">
                      {detail.source_chunks.slice(0, 3).map((chunk) => (
                        <p key={chunk.id} className="chunk-preview">{chunk.text.slice(0, 220)}…</p>
                      ))}
                    </div>
                  </>
                ) : null}
              </Panel>
              <Panel title="Add relationship">
                <form className="form" onSubmit={submitRelationship}>
                  <label>
                    Relationship type
                    <select name="relation_type" defaultValue="PREREQUISITE_OF">
                      {Object.entries(EDGE_LABELS).map(([type, label]) => (
                        <option key={type} value={type}>{label}</option>
                      ))}
                    </select>
                  </label>
                  <label>
                    Target concept
                    <input name="target" list="relation-targets" placeholder="Choose or enter a concept name" />
                    <datalist id="relation-targets">
                      {choices.filter((node) => node.id !== detail.id).map((node) =>
                        <option key={node.id} value={node.name}>Concept #{node.id}</option>)}
                    </datalist>
                  </label>
                  <label>
                    Confidence: <span className="hint">0.7</span>
                    <input name="confidence" type="range" min={0} max={1} step={0.1} defaultValue={0.7} />
                  </label>
                  <p className="hint">From {detail.name} to the target concept.</p>
                  {formError ? <ErrorBox error={formError} /> : null}
                  <button className="btn btn-primary" type="submit">Save relationship</button>
                </form>
              </Panel>
            </>
          )}
        </aside>
      </div>
    </div>
  );
}
