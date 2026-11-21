import { useEffect, useState } from "react";
import { api, courseId } from "../api";
import type { Course } from "../types";

function openCourse(id: number) {
  const url = new URL(location.href);
  if (id) url.searchParams.set("course", String(id));
  else url.searchParams.delete("course");
  url.hash = "/documents";
  location.assign(url.href);
}

export default function CoursePicker() {
  const [courses, setCourses] = useState<Course[]>([]);
  const [creating, setCreating] = useState(false);
  const [busy, setBusy] = useState(false);
  const [name, setName] = useState("");
  const [error, setError] = useState("");
  useEffect(() => { api.courses().then(setCourses).catch(e => setError(e.message)); }, []);
  return <section className="course-picker">
    <label>Course tutor
      <select value={courseId} onChange={e => openCourse(Number(e.target.value))}>
        {!courses.some(c => String(c.id) === courseId) && <option value={courseId}>{courses.length ? "Choose a course" : "Loading…"}</option>}
        {courses.map(c => <option key={c.id} value={c.id}>{c.name}</option>)}
      </select>
    </label>
    {creating ? <form onSubmit={async e => {
      e.preventDefault();
      if (!name.trim() || busy) return;
      setBusy(true); setError("");
      try { openCourse((await api.createCourse(name.trim())).id); }
      catch (err) { setError(String(err)); setBusy(false); }
    }}>
      <label>Course name<input autoFocus required maxLength={100} value={name} onChange={e => setName(e.target.value)} /></label>
      <button className="btn" disabled={busy}>Create</button>{" "}
      <button className="item-link" disabled={busy} type="button" onClick={() => setCreating(false)}>Cancel</button>
    </form> : <button className="item-link" onClick={() => setCreating(true)}>+ New course</button>}
    {error && <p role="alert">{error}</p>}
  </section>;
}
