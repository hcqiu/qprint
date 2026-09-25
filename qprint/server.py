from concurrent.futures import ThreadPoolExecutor
from contextlib import asynccontextmanager
from pathlib import Path
import secrets
from threading import Lock
from typing import Literal
from urllib.parse import urlparse
import uuid
import time

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse, PlainTextResponse
import json
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from starlette.middleware.trustedhost import TrustedHostMiddleware

from .importers import import_code, import_paper
from .paths import WorkspaceError, read_text
from .formal_report_access import report_file, report_links, recent_reports, report_text
from .workspace import ConflictError, Workspace
from .verification import verify_bindings
from .knowledge.navigator import KnowledgeNavigator
from .knowledge.index import KnowledgeIndexer
from .knowledge.runtime import publish_runtime, query_target
from .agent_paths import relative_output


class DocumentUpdate(BaseModel):
    path: str
    text: str = Field(max_length=5 * 1024 * 1024)
    revision: str


class ImportRequest(BaseModel):
    kind: str
    source: str = Field(max_length=2048)
    dest: str = Field(max_length=512)
    language: str = "lean"
    name: str = ""
    ref: str | None = None
    verify_after_download: bool = True
    timeout: float = Field(default=600, ge=1, le=3600, allow_inf_nan=False)


class VerificationRequest(BaseModel):
    node_id: str | None = Field(default=None, max_length=2048)
    language: Literal["lean", "agda", "coq"] | None = None
    timeout: float = Field(default=120, ge=1, le=3600, allow_inf_nan=False)


class NavigatorFocus(BaseModel):
    session: str = Field(default="default", min_length=1, max_length=200)
    node_id: str | None = Field(default=None, max_length=2048)
    view: Literal["rendered", "tex", "edit", "graph", "references", "paper"] = "rendered"
    selection: str = Field(default="", max_length=2000)
    document: str | None = Field(default=None, max_length=2048)


def create_app(root: Path, *, allow_verification: bool = False, toolchain_home: Path | None = None,
               allow_system_toolchains: bool = False, runtime_root: Path | None = None) -> FastAPI:
    workspace = Workspace(root)
    runtime_root = Path(runtime_root).resolve() if runtime_root is not None else workspace.root
    if not workspace.root.is_relative_to(runtime_root):
        raise WorkspaceError("workspace must stay inside the Qprint folder")
    token = secrets.token_urlsafe(32)
    executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="qprint-import")
    verification_executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="qprint-verify")
    jobs, job_lock = {}, Lock()
    static = Path(__file__).parent / "static"

    @asynccontextmanager
    async def lifespan(app):
        # Bootstrap belongs to the host, never to agent query processes. Publish
        # before any browser click so a fresh shell can discover the workspace.
        KnowledgeIndexer(workspace.root).update()
        publish_runtime(runtime_root, workspace.root, "host-" + uuid.uuid4().hex)
        yield
        executor.shutdown(wait=False, cancel_futures=True)
        verification_executor.shutdown(wait=False, cancel_futures=True)

    app = FastAPI(title="Qprint", lifespan=lifespan, docs_url=None, redoc_url=None)
    app.state.workspace = workspace
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=["127.0.0.1", "localhost", "[::1]", "testserver"])

    @app.middleware("http")
    async def guard(request: Request, call_next):
        if request.method not in {"GET", "HEAD", "OPTIONS"}:
            origin = request.headers.get("origin")
            if origin and origin != str(request.base_url).rstrip("/"):
                return JSONResponse({"detail": "仅允许同源写入"}, status_code=403)
            if not secrets.compare_digest(request.headers.get("x-qprint-token", ""), token):
                return JSONResponse({"detail": "写入 token 无效，请刷新页面"}, status_code=403)
            if int(request.headers.get("content-length", "0")) > 6 * 1024 * 1024:
                return JSONResponse({"detail": "请求过大"}, status_code=413)
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["Content-Security-Policy"] = "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; font-src 'self'; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'"
        if request.url.path.startswith("/api/"):
            response.headers["Cache-Control"] = "no-store"
        return response

    @app.exception_handler(WorkspaceError)
    async def invalid(request, exc):
        return JSONResponse({"detail": relative_output(str(exc), runtime_root)}, status_code=409 if isinstance(exc, ConflictError) else 400)

    @app.exception_handler(FileNotFoundError)
    async def missing(request, exc):
        return JSONResponse({"detail": "文件不存在"}, status_code=404)

    @app.get("/api/project")
    def project():
        return {**workspace.project(), "token": token, "verification_enabled": allow_verification,
                "navigator_available": (workspace.root / ".qprint/index/knowledge.sqlite").is_file()}

    @app.get("/api/navigator/state")
    def navigator_state(session: str | None = None, limit: int = 8):
        _, session = query_target(runtime_root, workspace.root.relative_to(runtime_root).as_posix(), session)
        with KnowledgeNavigator(workspace.root, session=session, runtime_root=runtime_root) as nav:
            return relative_output(nav.kb_state(limit), runtime_root)

    @app.post("/api/navigator/focus")
    def navigator_focus(payload: NavigatorFocus):
        # Validate against the visible workspace as well as the canonical index.
        if payload.node_id is not None and payload.node_id not in workspace.nodes:
            raise HTTPException(404, "节点不存在")
        with KnowledgeNavigator(workspace.root, session=payload.session, runtime_root=runtime_root) as nav:
            state = nav.set_focus(payload.node_id, view=payload.view, selection=payload.selection, origin="browser", document=payload.document)
            publish_runtime(runtime_root, workspace.root, payload.session)
            return relative_output(state, runtime_root)

    @app.get("/api/formal-reports")
    def reports():
        return {"reports": recent_reports(workspace.root)}

    @app.get("/api/formal-report")
    def report(path: str, download: bool = False):
        target = report_file(workspace.root, path)
        data = json.loads(read_text(target))
        if not isinstance(data, dict) or not isinstance(data.get("status"), str):
            raise WorkspaceError("无效的验证报告")
        if download:
            return JSONResponse(data, headers={"Content-Disposition": f'attachment; filename="{target.name}"'})
        return PlainTextResponse(report_text(data))

    @app.get("/api/node")
    def node(id: str):
        try:
            return workspace.detail(id)
        except KeyError:
            raise HTTPException(404, "节点不存在")

    @app.get("/api/document")
    def document(path: str):
        return workspace.document(path)

    @app.put("/api/document")
    def save_document(update: DocumentUpdate):
        return workspace.save_document(update.path, update.text, update.revision)

    @app.get("/api/tex")
    def tex_document(path: str):
        with workspace.lock:
            if path not in workspace.tex:
                raise HTTPException(404, "TeX 文件不存在")
            doc = workspace.tex[path]
            return {"path": path, "source": doc.source, "sections": doc.sections}

    @app.get("/api/references")
    def references(path: str):
        try:
            return {key: value for key, value in workspace.bibliography(path).items() if key != "citations"}
        except KeyError:
            raise HTTPException(404, "TeX 文件不存在")

    @app.post("/api/reload")
    def reload():
        workspace.reload()
        return workspace.project()

    def run_import(job_id, payload):
        with job_lock:
            jobs[job_id].update(status="running", started_at=time.time())
        try:
            if payload.kind == "code":
                def phase(value):
                    with job_lock:
                        jobs[job_id]["phase"] = value
                def progress(value):
                    with job_lock:
                        jobs[job_id].update(progress=value, updated_at=time.time())
                result = import_code(workspace.root, payload.source, payload.language, payload.dest, payload.ref,
                                     verify_after_download=payload.verify_after_download, timeout=payload.timeout,
                                     toolchain_home=toolchain_home, on_phase=phase, on_progress=progress)
            else:
                result = import_paper(workspace.root, payload.source, payload.dest, payload.name)
            workspace.reload()
            with job_lock:
                jobs[job_id].update(status="succeeded", phase="complete", result=result, finished_at=time.time())
        except Exception as exc:
            with job_lock:
                jobs[job_id].update(status="failed", error=str(exc), finished_at=time.time())

    @app.post("/api/import", status_code=202)
    def start_import(payload: ImportRequest):
        if payload.kind not in {"code", "paper"}:
            raise WorkspaceError("导入类型必须是 code 或 paper")
        job_id = uuid.uuid4().hex
        with job_lock:
            if sum(j.get("kind") == "import" and j["status"] in {"queued", "running"} for j in jobs.values()) >= 5:
                raise HTTPException(429, "导入队列已满")
            jobs[job_id] = {"id": job_id, "kind": "import", "status": "queued", "result": None, "error": None}
        executor.submit(run_import, job_id, payload)
        return {"id": job_id, "status": "queued"}

    def run_verification(job_id, bindings, timeout, diagnostics):
        with job_lock:
            jobs[job_id]["status"] = "running"
        try:
            result = verify_bindings(workspace.root, bindings, timeout=timeout,
                                     toolchain_home=toolchain_home, allow_system=allow_system_toolchains)
            result["diagnostics"] = diagnostics
            if any(d["severity"] == "error" for d in diagnostics):
                result["status"] = "incomplete"
            with job_lock:
                # Job success means a report was produced; inspect result.status.
                jobs[job_id].update(status="succeeded", result=result)
        except Exception as exc:
            with job_lock:
                jobs[job_id].update(status="failed", error=str(exc))

    @app.post("/api/verify", status_code=202)
    def start_verification(payload: VerificationRequest):
        if not allow_verification:
            raise HTTPException(403, "验证执行未启用；可信工作区可使用 serve --allow-verification")
        try:
            with workspace.lock:
                bindings = workspace.verification_bindings(payload.node_id, payload.language)
                diagnostics = list(workspace.diagnostics)
        except KeyError:
            raise HTTPException(404, "节点不存在")
        job_id = uuid.uuid4().hex
        with job_lock:
            if sum(j.get("kind") == "verification" and j["status"] in {"queued", "running"} for j in jobs.values()) >= 5:
                raise HTTPException(429, "验证队列已满")
            jobs[job_id] = {"id": job_id, "kind": "verification", "status": "queued", "result": None, "error": None}
        verification_executor.submit(run_verification, job_id, bindings, payload.timeout, diagnostics)
        return {"id": job_id, "status": "queued"}

    @app.get("/api/jobs/{job_id}")
    def job(job_id: str):
        with job_lock:
            if job_id not in jobs:
                raise HTTPException(404, "任务不存在（重启后任务记录会清空）")
            result = dict(jobs[job_id])
            if (result.get("result") or {}).get("verification"):
                payload = dict(result["result"])
                verification = dict(payload["verification"])
                verification["reports"] = [report_links(workspace.root, r) for r in verification.get("reports", [])]
                payload["verification"] = verification
                result["result"] = payload
            if "started_at" in result:
                result["elapsed_seconds"] = round(result.get("finished_at", time.time()) - result["started_at"], 1)
            return result

    @app.get("/")
    def home():
        return FileResponse(static / "index.html")

    app.mount("/static", StaticFiles(directory=static), name="static")
    return app
