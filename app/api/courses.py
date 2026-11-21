"""Each personal course reuses the learning API against its own SQLite workspace."""

from dataclasses import replace
from functools import lru_cache
from threading import Lock

from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from starlette.concurrency import run_in_threadpool

from app.db.models import Course

STARTER = "My first course"


class CourseName(BaseModel):
    name: str = Field(min_length=1, max_length=100)


def install_courses(app, settings, session_factory, install_workspace):
    @app.get("/courses", tags=["courses"])
    def list_courses():
        with session_factory() as session:
            rows = session.scalars(select(Course).order_by(Course.name))
            return [{"id": 0, "name": STARTER}, *({"id": c.id, "name": c.name} for c in rows)]

    @app.post("/courses", status_code=201, tags=["courses"])
    def create_course(body: CourseName):
        name = body.name.strip()
        if not name:
            raise HTTPException(422, "Enter a course name.")
        if name.casefold() == STARTER.casefold():
            raise HTTPException(409, "A course with that name already exists.")
        with session_factory() as session:
            course = Course(name=name, name_key=name.casefold())
            session.add(course)
            try:
                session.commit()
            except IntegrityError as error:
                raise HTTPException(409, "A course with that name already exists.") from error
            return {"id": course.id, "name": course.name}

    lock = Lock()

    @lru_cache(maxsize=32)
    def course_app(course_id):
        with session_factory() as session:
            if not session.get(Course, course_id):
                raise LookupError("Course not found.")
        folder = settings.data_dir / "courses" / str(course_id)
        scoped = replace(settings, data_dir=folder, upload_dir=folder / "uploads",
                         database_url=f"sqlite:///{folder / 'knowledge.db'}")
        child = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)
        install_workspace(child, scoped)
        return child

    def lookup(course_id):
        with lock:
            return course_app(course_id)

    class Workspace:
        async def __call__(self, scope, receive, send):
            try:
                child = await run_in_threadpool(lookup, scope["path_params"]["course_id"])
            except LookupError:
                await JSONResponse({"detail": "Course not found."}, 404)(scope, receive, send)
            else:
                await child(scope, receive, send)

    app.mount("/courses/{course_id:int}/workspace", Workspace())
