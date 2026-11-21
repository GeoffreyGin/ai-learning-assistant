import { useEffect, useRef, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { api } from "../api";
import MathText from "../components/MathText";
import { ErrorBox, Loading } from "../components/ui";
import type { AgentAction, ChatTurn, PendingQuestion, TutorOptions } from "../types";

interface Message {
  role: "user" | "agent";
  text: string;
  actions?: AgentAction[];
  error?: boolean;
}
type Topic = { id: number; name: string };

function messagesFromTurn(turn: ChatTurn): Message[] {
  return [{ role: "user", text: turn.message }, { role: "agent", text: turn.reply, actions: turn.actions }];
}

function LectureTopics({ id, disabled, start }: {
  id: number; disabled: boolean; start: (topic: Topic, title: string) => void;
}) {
  const [lecture, setLecture] = useState<{ title: string; topics: Topic[] }>();
  const [topicId, setTopicId] = useState("");
  const [error, setError] = useState("");
  useEffect(() => {
    let active = true;
    Promise.all([api.listDocuments(), api.lectureTopics(id)]).then(([docs, topics]) => {
      if (active) setLecture({ title: docs.find(d => d.id === id)?.title ?? "Lecture", topics });
    }).catch(e => { if (active) setError(e.message); });
    return () => { active = false; };
  }, [id]);
  if (error) return <ErrorBox error={error} />;
  if (!lecture) return <Loading text="Finding topics in this lecture…" />;
  const { title, topics } = lecture;
  return <section className="lecture-picker" aria-label="Lecture topics">
    <div className="study-heading"><h2>{title}</h2><Link to="/documents">Change lecture</Link></div>
    {topics.length ? <>
      <p>Which topic would you like to work through?</p>
      <div className="toolbar">{topics.slice(0, 3).map(t =>
        <button key={t.id} className="btn" disabled={disabled} onClick={() => start(t, title)}>{t.name}</button>)}</div>
      {topics.length > 3 && <form className="topic-chooser" onSubmit={e => {
        e.preventDefault();
        const chosen = topics.find(t => String(t.id) === topicId);
        if (chosen) start(chosen, title);
      }}>
        <label>All lecture topics<select value={topicId} onChange={e => setTopicId(e.target.value)}>
          <option value="">Choose a topic</option>
          {topics.map(t => <option key={t.id} value={t.id}>{t.name}</option>)}
        </select></label>
        <button className="btn btn-primary" disabled={disabled || !topicId}>Study topic</button>
      </form>}
    </> : <p>This lecture has no extracted topics. <Link to="/documents">Choose another lecture</Link>.</p>}
  </section>;
}

export default function ChatPage() {
  const [search, setSearch] = useSearchParams();
  const lecture = search.get("lecture");
  const topic = search.get("topic");
  const [messages, setMessages] = useState<Message[]>([]);
  const [pending, setPending] = useState<PendingQuestion | null>(null);
  const [input, setInput] = useState("");
  const [step, setStep] = useState("");
  const [busy, setBusy] = useState(false);
  const [loading, setLoading] = useState(true);
  const [historyError, setHistoryError] = useState("");
  const scrollRef = useRef<HTMLDivElement>(null);
  const sending = useRef(false);

  useEffect(() => {
    let active = true;
    api.history().then(turns => {
      if (!active) return;
      setMessages(turns.flatMap(messagesFromTurn));
      setPending(turns.at(-1)?.pending ?? null);
    }).catch(e => { if (active) setHistoryError(e.message); })
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, []);
  useEffect(() => {
    const pane = scrollRef.current;
    if (pane) pane.scrollTop = pane.scrollHeight;
  }, [messages, busy, lecture]);
  useEffect(() => { setStep(""); }, [pending?.attempt_id]);

  async function send(text: string, options: TutorOptions = {}, keepDraft = false) {
    const message = text.trim();
    if (!message || sending.current || loading) return;
    sending.current = true;
    setBusy(true);
    try {
      const turn = await api.chat(message, options);
      setMessages(prev => [...prev, ...messagesFromTurn({ message, ...turn })]);
      setPending(turn.pending);
      if (!keepDraft) setInput("");
      if ((lecture && options.document_id) || topic) setSearch({}, { replace: true });
    } catch (err) {
      setMessages(prev => [...prev, { role: "agent", text: err instanceof Error ? err.message : String(err), error: true }]);
    } finally {
      sending.current = false;
      setBusy(false);
    }
  }
  const disabled = loading || busy;
  return <div className="page chat-page">
    <header className="page-header">
      <div><h1>Learning chat</h1><p className="page-subtitle">Work through a lecture with your course tutor.</p></div>
      <div className="toolbar"><Link className="btn" to="/documents">Choose a lecture</Link>
        {pending ? <Link className="btn" to={`/graph?concept=${pending.concept_id}`}>Open concept graph</Link> :
          <button className="btn" disabled={disabled} onClick={() => void send("What should I study next?")}>Suggest a topic</button>}
      </div>
    </header>
    {historyError && <ErrorBox error={historyError} />}
    {topic && !lecture && <section className="lecture-picker"><h2>{topic}</h2>
      <button className="btn btn-primary" disabled={disabled} onClick={() => void send(`Help me learn ${topic}`)}>Study this topic</button>
    </section>}
    {lecture && <LectureTopics key={lecture} id={Number(lecture)} disabled={disabled} start={(t, title) =>
      void send(`Study ${t.name} from ${title}.`, { document_id: Number(lecture), concept_id: t.id })} />}
    <div className="chat-window" ref={scrollRef} role="log" aria-label="Tutor conversation">
      {loading ? <Loading /> : !lecture && !topic && messages.length === 0 ? <div className="chat-empty">
        <h2>What would you like to study?</h2>
        <Link className="btn btn-primary" to="/documents">Choose a lecture</Link>
        <button className="btn" onClick={() => void send("Test me")}>Test my understanding</button>
      </div> : null}
      {messages.map((msg, i) => <div key={i} className={`msg-row ${msg.role}`}>
        <div className={`bubble ${msg.role}${msg.error ? " error" : ""}`}>
          <MathText text={msg.text} />
          {!!msg.actions?.length && <details className="actions-log"><summary>Activity log ({msg.actions.length})</summary>
            <ul>{msg.actions.map((act, j) => <li key={j}><code>{act.tool}</code> {act.detail}</li>)}</ul></details>}
        </div>
      </div>)}
      {busy && <div className="msg-row agent" role="status"><div className="bubble agent">Tutor is thinking…</div></div>}
    </div>
    {pending && !lecture && <section className="practice-panel">
      <div className="study-heading"><h2>{pending.concept_name}</h2><small>Practice question</small></div>
      <MathText text={pending.question} />
      <div className="toolbar">
        {!!pending.worked_steps?.length && <label>Clue for
          <select value={step} onChange={e => setStep(e.target.value)}>
            <option value="">Practice question</option>
            {pending.worked_steps.map((_s, i) => <option key={i} value={i + 1}>Worked step {i + 1}</option>)}
          </select>
        </label>}
        <button className="btn" disabled={disabled} onClick={() => void send(
          input.trim() || (step ? `Give me one clue for worked step ${step}.` : "Give me one clue."),
          { attempt_id: pending.attempt_id, hint: true, step: step ? Number(step) : undefined }, true,
        )}>Give me one clue</button>
        {!!pending.hint_count && <span className="hint">{pending.hint_count} {pending.hint_count === 1 ? "clue" : "clues"} used</span>}
      </div>
    </section>}
    {!lecture && <form className="chat-input" onSubmit={e => {
      e.preventDefault();
      void send(input, pending ? { attempt_id: pending.attempt_id, step: step ? Number(step) : undefined } : {});
    }}>
      <textarea aria-label={pending ? "Your working or answer" : "Message to your tutor"}
        placeholder={pending ? "Write your working for a clue, or submit your answer…" : "Ask your tutor a question…"}
        value={input} rows={2} disabled={disabled} onChange={e => setInput(e.target.value)} />
      <button className="btn btn-primary" disabled={disabled || !input.trim()}>{pending ? "Submit answer" : "Send"}</button>
    </form>}
  </div>;
}
