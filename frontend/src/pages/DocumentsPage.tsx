import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api";
import MathText from "../components/MathText";
import { ErrorBox, Loading, Panel } from "../components/ui";
import type { DocumentDetail, DocumentMeta, KnowledgeSummary, UploadResult } from "../types";

const ACCEPTED = ".md,.markdown,.txt,.pdf";

function StudyLink({ id }: { id: number }) {
  return <Link className="btn btn-primary" to={`/chat?lecture=${id}`}>Study this lecture</Link>;
}

function DocumentDrawer({ doc, onClose }: { doc: DocumentMeta; onClose: () => void }) {
  const [detail, setDetail] = useState<DocumentDetail | null>(null);
  const [summary, setSummary] = useState<KnowledgeSummary | null>(null);
  const [sourceError, setSourceError] = useState("");
  const [summaryError, setSummaryError] = useState("");

  useEffect(() => {
    let active = true;
    api.summarizeDocument(doc.id).then(
      (value) => { if (active) setSummary(value); },
      (error) => { if (active) setSummaryError(String(error)); },
    );
    api.getDocument(doc.id).then(
      (value) => { if (active) setDetail(value); },
      (error) => { if (active) setSourceError(String(error)); },
    );
    return () => { active = false; };
  }, [doc.id]);

  return (
    <div className="drawer-backdrop" onClick={onClose} onKeyDown={(e) => { if (e.key === "Escape") onClose(); }}>
      <aside role="dialog" aria-labelledby="document-title" className="drawer" onClick={(e) => e.stopPropagation()}>
        <header>
          <h2 id="document-title">{doc.title} <small className="hint">Document #{doc.id}</small></h2>
          <button autoFocus className="btn" onClick={onClose}>Close</button>
        </header>
        <div className="drawer-body">
          <StudyLink id={doc.id} />
          <Panel title="Knowledge summary">
            {summaryError ? <ErrorBox error={summaryError} /> : !summary ? <Loading /> : (
              <>
                <MathText text={summary.overview} />
                {summary.key_concepts.length > 0 && <p>{summary.key_concepts.join(" · ")}</p>}
                {summary.claims.length > 0 && (
                  <details>
                    <summary>Summary sources ({summary.claims.length})</summary>
                    {summary.claims.map((claim, index) => {
                      const chunk = detail?.chunks.find((item) => item.id === claim.source_chunk_id);
                      return (
                        <blockquote key={index}>
                          <MathText text={claim.text} />
                          <footer className="hint">Source passage #{claim.source_chunk_id}
                            {chunk?.page_number != null && ` · page ${chunk.page_number}`}
                          </footer>
                        </blockquote>
                      );
                    })}
                  </details>
                )}
              </>
            )}
          </Panel>
          {sourceError ? <ErrorBox error={sourceError} /> : !detail ? <Loading /> : (
            <details>
              <summary>Source passages ({detail.chunks.length})</summary>
              {detail.chunks.map((chunk) => (
                <section key={chunk.id} className="chunk">
                  <header>Passage #{chunk.id}{chunk.page_number !== null && ` · page ${chunk.page_number}`}</header>
                  <p>{chunk.text}</p>
                </section>
              ))}
            </details>
          )}
        </div>
      </aside>
    </div>
  );
}

export default function DocumentsPage() {
  const [documents, setDocuments] = useState<DocumentMeta[] | null>(null);
  const [error, setError] = useState("");
  const [uploading, setUploading] = useState(false);
  const [result, setResult] = useState<UploadResult | null>(null);
  const [selected, setSelected] = useState<DocumentMeta | null>(null);
  const [dragging, setDragging] = useState(false);

  const load = useCallback(async () => {
    try {
      setDocuments(await api.listDocuments());
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  async function upload(file: File) {
    setUploading(true);
    setError("");
    try {
      const res = await api.uploadDocument(file);
      setResult(res);
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setUploading(false);
    }
  }

  return (
    <div className="page">
      <h1>Documents</h1>
      <p className="page-subtitle">Choose a lecture to study or add material to this course.</p>

      {error ? <ErrorBox error={error} /> : null}

      <div
        className={`drop-zone${dragging ? " dragging" : ""}`}
        onDragOver={(e) => {
          e.preventDefault();
          setDragging(true);
        }}
        onDragLeave={() => setDragging(false)}
        onDrop={(e) => {
          e.preventDefault();
          setDragging(false);
          const file = e.dataTransfer.files[0];
          if (file) void upload(file);
        }}
      >
        <p>{uploading ? "Processing your file…" : "Drop a file here or choose one below"}</p>
        <label className="btn btn-primary">
          Choose file
          <input
            type="file"
            accept={ACCEPTED}
            hidden
            disabled={uploading}
            onChange={(e) => {
              const file = e.target.files?.[0];
              if (file) void upload(file);
            }}
          />
        </label>
        <p className="hint">Supported formats: Markdown / TXT / PDF</p>
      </div>

      {result ? (
        <div className="upload-result">
          <strong>✓ Uploaded: {result.document.title} · Document #{result.document.id}</strong>
          <StudyLink id={result.document.id} />
          <button className="btn btn-small" onClick={() => setSelected(result.document)}>View summary</button>
          <span>
            {result.chunk_count} passages · {result.extracted_mentions} concept mentions ·{" "}
            {result.new_concept_count} new concepts · {result.new_relationship_count} new relationships
          </span>
          {result.llm_fallback_chunks > 0 ? (
            <span className="warn"> ({result.llm_fallback_chunks} passages processed with the local extractor)</span>
          ) : null}
        </div>
      ) : null}

      <Panel title="Uploaded documents">
        {documents === null ? (
          <Loading />
        ) : documents.length === 0 ? (
          <p className="empty">No documents yet — Upload a file to get started.</p>
        ) : (
          <table className="table">
            <thead>
              <tr>
                <th>Lecture</th>
                <th>Study</th>
                <th>Type</th>
                <th>Uploaded</th>
              </tr>
            </thead>
            <tbody>
              {documents.map((doc) => (
                <tr key={doc.id}>
                  <td><button className="item-link" onClick={() => setSelected(doc)}>
                    {doc.title} <small>#{doc.id} · View summary</small>
                  </button></td>
                  <td><StudyLink id={doc.id} /></td>
                  <td>{doc.file_type}</td>
                  <td>{new Date(doc.created_at).toLocaleString("en-GB")}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </Panel>

      {selected && <DocumentDrawer key={selected.id} doc={selected} onClose={() => setSelected(null)} />}
    </div>
  );
}
