import { useCallback, useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../api";
import MathText from "../components/MathText";
import { ErrorBox, Loading, MasteryBar, Panel, StatusBadge } from "../components/ui";
import type { Concept, CourseProgress, GapReport, LogEntry, RecommendedTopic } from "../types";
import { STATUS_MASTERED, STATUS_UNKNOWN, STATUS_WEAK, masteryStatus } from "../types";

interface Stats {
  documents: number;
  concepts: number;
  relationships: number;
  mastered: number;
  weak: number;
  unknown: number;
}

export default function DashboardPage() {
  const navigate = useNavigate();
  const [stats, setStats] = useState<Stats | null>(null);
  const [topics, setTopics] = useState<RecommendedTopic[] | null>(null);
  const [concepts, setConcepts] = useState<Concept[]>([]);
  const [gapReport, setGapReport] = useState<GapReport | null>(null);
  const [log, setLog] = useState<LogEntry[] | null>(null);
  const [progress, setProgress] = useState<CourseProgress | null>(null);
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    setError("");
    try {
      const [graph, documents, recommendation, conceptList, logEntries, evidence] = await Promise.all([
        api.getGraph(),
        api.listDocuments(),
        api.getRecommendations(),
        api.listConcepts(),
        api.getLog(200),
        api.progress(),
      ]);
      const byStatus = (status: string) =>
        graph.nodes.filter((node) => masteryStatus(node.mastery) === status).length;
      setStats({
        documents: documents.length,
        concepts: graph.nodes.length,
        relationships: graph.edges.length,
        mastered: byStatus(STATUS_MASTERED),
        weak: byStatus(STATUS_WEAK),
        unknown: byStatus(STATUS_UNKNOWN),
      });
      setTopics(recommendation.topics);
      setConcepts(conceptList);
      setLog(logEntries);
      setProgress(evidence);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  async function loadGaps(conceptId: number) {
    if (conceptId === 0) {
      setGapReport(null);
      return;
    }
    try {
      setGapReport(await api.getGaps(conceptId));
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  }

  return (
    <div className="page">
      <header className="page-header">
        <div>
          <h1>Dashboard</h1>
          <p className="page-subtitle">Learning progress, recommendations and agent activity.</p>
        </div>
        <button className="btn" onClick={() => void load()}>
          Refresh
        </button>
      </header>

      {error ? <ErrorBox error={error} /> : null}

      {progress && <Panel title="Your learning so far">
        {progress.total === 0 ? <p>There are no submitted answers in this course yet. Study a lecture and try a practice question to start your progress record.</p> :
          <p>You answered <strong>{progress.correct} of {progress.total}</strong> practice questions correctly. {progress.untested === 1 ? "One concept still has" : `${progress.untested} concepts still have`} no assessment evidence.</p>}
        {progress.recent.map(item => <details key={item.id} className="practice-evidence">
          <summary>{item.concept} · {item.correct ? "Correct" : "Needs practice"} · {item.hints} {item.hints === 1 ? "clue" : "clues"}</summary>
          <h3>Question</h3><MathText text={item.question} />
          <h3>Your answer</h3><MathText text={item.answer} />
        </details>)}
      </Panel>}

      {stats === null ? (
        <Loading />
      ) : (
        <>
          <div className="stats-row">
            <div className="stat-card"><strong>{stats.documents}</strong><span>Documents</span></div>
            <div className="stat-card"><strong>{stats.concepts}</strong><span>Concepts</span></div>
            <div className="stat-card"><strong>{stats.relationships}</strong><span>Relationships</span></div>
            <div className="stat-card"><strong>{stats.mastered}</strong><span>Mastered</span></div>
            <div className="stat-card"><strong>{stats.weak}</strong><span>Needs practice</span></div>
            <div className="stat-card"><strong>{stats.unknown}</strong><span>Unknown</span></div>
          </div>

          {stats.concepts > 0 ? (
            <div className="distribution">
              <span className="dist-mastered" style={{ width: `${(stats.mastered / stats.concepts) * 100}%` }} />
              <span className="dist-weak" style={{ width: `${(stats.weak / stats.concepts) * 100}%` }} />
              <span className="dist-unknown" style={{ width: `${(stats.unknown / stats.concepts) * 100}%` }} />
            </div>
          ) : null}
        </>
      )}

      <div className="dashboard-grid">
        <Panel title="Recommended topics">
          {topics === null ? (
            <Loading />
          ) : topics.length === 0 ? (
            <p className="empty">No recommendations yet — upload material or choose a learning goal to see recommendations.</p>
          ) : (
            <ul className="topic-list">
              {topics.map((topic, index) => (
                <li key={topic.concept.id} className="topic-row">
                  <span className="topic-rank">{index + 1}</span>
                  <div className="topic-main">
                    <div className="topic-name">
                      {topic.concept.name}
                      <StatusBadge status={topic.status} />
                      <MasteryBar mastery={topic.mastery} />
                    </div>
                    <p className="hint">{topic.reason}</p>
                  </div>
                  <button className="btn btn-small" onClick={() => navigate(`/chat?topic=${encodeURIComponent(topic.concept.name)}`)}>
                    Study
                  </button>
                </li>
              ))}
            </ul>
          )}
        </Panel>

        <Panel title="Prerequisite gaps">
          <label className="concept-picker">
            Choose a target concept: 
            <select onChange={(e) => void loadGaps(Number(e.target.value))} defaultValue="0">
              <option value="0">— Choose a concept —</option>
              {concepts.map((concept) => (
                <option key={concept.id} value={concept.id}>{concept.name} · Concept #{concept.id}</option>
              ))}
            </select>
          </label>
          {gapReport === null ? (
            <p className="empty">Choose a concept to see its prerequisites and learning gaps.</p>
          ) : (
            <div className="gap-report">
              <h3>Goal: {gapReport.target.name}</h3>
              <table className="table">
                <thead>
                  <tr><th>Prerequisites</th><th>Distance</th><th>Status</th><th>Estimated mastery</th><th>Evidence count</th></tr>
                </thead>
                <tbody>
                  {gapReport.prerequisites.length === 0 ? (
                    <tr><td colSpan={5} className="empty">No prerequisites recorded.</td></tr>
                  ) : (
                    gapReport.prerequisites.map((entry) => (
                      <tr key={entry.concept.id}>
                        <td>{entry.concept.name}</td>
                        <td>{entry.distance}</td>
                        <td><StatusBadge status={entry.status} /></td>
                        <td>
                          {entry.mastery === null ? "—" : `${Math.round(entry.mastery * 100)}%`}
                        </td>
                        <td>{entry.evidence_count}</td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
              {gapReport.gaps.length > 0 ? (
                <p className="gap-hint">
                  Study first: {gapReport.gaps.map((g) => g.concept.name).join(", ")}
                </p>
              ) : (
                <p className="gap-hint ok">{gapReport.prerequisites.length ? "No prerequisite gaps found in the available evidence." : "There are no recorded prerequisites to assess."}</p>
              )}
            </div>
          )}
        </Panel>
      </div>

      <Panel title="Agent activity log" extra={<button className="btn btn-small" onClick={() => void load()}>Refresh</button>}>
        {log === null ? (
          <Loading />
        ) : log.length === 0 ? (
          <p className="empty">No activity yet — start a learning chat to see the actions here.</p>
        ) : (
          <table className="table log-table">
            <thead>
              <tr><th>Time</th><th>Tool</th><th>Details</th></tr>
            </thead>
            <tbody>
              {log.map((entry, index) => (
                <tr key={index}>
                  <td className="log-time">{entry.timestamp.replace("T", " ")}</td>
                  <td><code>{entry.tool}</code></td>
                  <td>{entry.detail}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </Panel>
    </div>
  );
}
