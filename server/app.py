"""FastAPI local REST API server for Guideline Gateway."""

import json
import os
import time
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from engine.models import ChatMessage, QueryRequest, QueryResponse
from server.manager import PackManager

app = FastAPI(
    title="Guideline Gateway API",
    description="Offline-first domain-agnostic guideline Q&A engine",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

PACKS_DIR = os.getenv("PACKS_DIR", "packs")
ACTIVE_PACK = os.getenv("ACTIVE_PACK", "football-laws")
FEEDBACK_FILE = os.path.join(os.getenv("DATA_DIR", "data"), "feedback.jsonl")

pack_manager = PackManager(packs_dir=PACKS_DIR, active_pack_id=ACTIVE_PACK)


class AskRequestPayload(BaseModel):
    pack_id: Optional[str] = None
    question: str
    history: List[ChatMessage] = Field(default_factory=list)
    mode: str = "answer"  # "answer" | "search_only"
    stream: bool = False
    language: Optional[str] = None


class FeedbackPayload(BaseModel):
    query: str
    answer: str
    rating: int  # 1 (positive) or -1 (negative)
    comment: Optional[str] = None
    session_id: Optional[str] = None
    citations: List[Dict[str, Any]] = Field(default_factory=list)


@app.get("/healthz")
async def health_check() -> Dict[str, Any]:
    """Return health and readiness status."""
    return {
        "status": "ok",
        "active_pack": pack_manager.active_pack_id,
        "installed_packs": list(pack_manager.installed_packs.keys()),
        "slm_available": (
            pack_manager.pipeline.generator.is_available
            if pack_manager.pipeline and pack_manager.pipeline.generator
            else False
        ),
        "timestamp": time.time(),
    }


@app.get("/v1/packs")
async def list_packs() -> Dict[str, Any]:
    """List all installed knowledge packs."""
    packs = pack_manager.discover_packs()
    return {
        "active_pack": pack_manager.active_pack_id,
        "packs": list(packs.values()),
    }


@app.post("/v1/packs/{pack_id}/activate")
async def activate_pack(pack_id: str) -> Dict[str, Any]:
    """Activate a specific knowledge pack."""
    try:
        pack_manager.activate_pack(pack_id)
        return {
            "status": "success",
            "message": f"Pack '{pack_id}' activated successfully.",
            "active_pack": pack_id,
        }
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@app.post("/v1/packs/{pack_id}/rollback")
async def rollback_pack(pack_id: Optional[str] = None) -> Dict[str, Any]:
    """Roll back to previous knowledge pack."""
    try:
        target = pack_manager.rollback_pack()
        return {
            "status": "success",
            "message": f"Rolled back to pack '{target}'.",
            "active_pack": target,
        }
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@app.post("/v1/packs/install")
async def install_pack(file: UploadFile = File(...)) -> Dict[str, Any]:
    """Install a new Knowledge Pack (.kpack archive)."""
    if not file.filename.endswith(".kpack"):
        raise HTTPException(status_code=400, detail="Only .kpack files are supported.")

    temp_path = os.path.join(PACKS_DIR, file.filename)
    try:
        with open(temp_path, "wb") as f:
            content = await file.read()
            f.write(content)

        installed_id = pack_manager.install_kpack(temp_path)
        return {
            "status": "success",
            "installed_pack": installed_id,
            "message": f"Successfully installed knowledge pack '{installed_id}'.",
        }
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Installation failed: {exc}")
    finally:
        if os.path.exists(temp_path):
            os.remove(temp_path)


@app.get("/v1/chunks/{chunk_id}")
async def get_chunk(chunk_id: str) -> Dict[str, Any]:
    """Retrieve full text and metadata for a specific citation chunk ID."""
    if not pack_manager.pipeline or not pack_manager.pipeline.retriever:
        raise HTTPException(status_code=503, detail="Retriever not initialized.")

    chunk = pack_manager.pipeline.retriever.get_chunk(chunk_id)
    if not chunk:
        raise HTTPException(status_code=404, detail=f"Chunk '{chunk_id}' not found.")
    return chunk.model_dump()


@app.post("/v1/feedback")
async def submit_feedback(payload: FeedbackPayload) -> Dict[str, Any]:
    """Record user feedback locally in JSONL format."""
    os.makedirs(os.path.dirname(FEEDBACK_FILE), exist_ok=True)
    entry = payload.model_dump()
    entry["timestamp"] = time.time()
    entry["pack_id"] = pack_manager.active_pack_id

    with open(FEEDBACK_FILE, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")

    return {"status": "success", "message": "Feedback recorded."}


@app.post("/v1/ask", response_model=QueryResponse)
async def ask_question(payload: AskRequestPayload):
    """Answer question with verifiable citations from active guideline document."""
    if payload.pack_id and payload.pack_id != pack_manager.active_pack_id:
        if payload.pack_id in pack_manager.installed_packs:
            pack_manager.activate_pack(payload.pack_id)
        else:
            raise HTTPException(status_code=404, detail=f"Pack '{payload.pack_id}' not found.")

    if not pack_manager.pipeline:
        raise HTTPException(status_code=503, detail="Pipeline is not ready or no pack is active.")

    req = QueryRequest(
        query=payload.question,
        history=payload.history,
        language=payload.language,
        stream=payload.stream,
    )

    if payload.stream and pack_manager.pipeline.generator.is_available:

        def stream_generator():
            # Process query and retrieve evidence
            proc_q = pack_manager.pipeline.query_processor.process(
                query=req.query, history=req.history, forced_lang=req.language
            )
            ev_list = pack_manager.pipeline.retriever.retrieve(proc_q, top_k=req.top_k)

            if pack_manager.pipeline.guardrails.should_abstain_on_retrieval(ev_list):
                abstain_resp = pack_manager.pipeline.guardrails.create_abstain_response(
                    lang=proc_q.detected_lang, evidence_list=ev_list
                )
                yield f"data: {json.dumps({'type': 'content', 'delta': abstain_resp.answer})}\n\n"
                yield f"data: {json.dumps({'type': 'done', 'citations': []})}\n\n"
                return

            built_ctx = pack_manager.pipeline.context_builder.build(
                evidence_list=ev_list,
                system_prompt_template=pack_manager.pipeline.system_prompt,
                history=req.history,
                query=proc_q.standalone_query,
            )

            token_stream = pack_manager.pipeline.generator.generate_stream(
                system_prompt=built_ctx.system_prompt,
                context_text=built_ctx.formatted_context_text,
                user_query=proc_q.standalone_query,
                history_text=built_ctx.history_text,
            )
            full_text = []
            for token in token_stream:
                full_text.append(token)
                yield f"data: {json.dumps({'type': 'content', 'delta': token})}\n\n"

            accumulated = "".join(full_text)
            clean_answer, citations = pack_manager.pipeline.guardrails.extract_citations(
                accumulated, built_ctx.citation_map
            )
            citation_dicts = [c.model_dump() for c in citations]
            yield f"data: {json.dumps({'type': 'done', 'citations': citation_dicts})}\n\n"

        return StreamingResponse(stream_generator(), media_type="text/event-stream")

    response = pack_manager.pipeline.run(req)
    return response


# UI Static Files & SPA fallback
ui_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "ui", "dist")
if os.path.exists(ui_dir):
    app.mount("/static", StaticFiles(directory=ui_dir), name="static")

    @app.get("/", response_class=HTMLResponse)
    async def serve_index():
        index_file = os.path.join(ui_dir, "index.html")
        if os.path.exists(index_file):
            with open(index_file, "r", encoding="utf-8") as f:
                return HTMLResponse(content=f.read())
        return HTMLResponse(content="<h1>Guideline Gateway</h1><p>UI build not found.</p>")
else:

    @app.get("/", response_class=HTMLResponse)
    async def serve_default_ui():
        return HTMLResponse(
            """<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>Guideline Gateway</title>
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <script src="https://cdn.tailwindcss.com"></script>
</head>
<body class="bg-slate-900 text-slate-100 min-h-screen flex flex-col font-sans">
    <header class="border-b border-slate-800 bg-slate-950 px-6 py-4 flex items-center justify-between shadow">
        <div class="flex items-center space-x-3">
            <span class="text-2xl">📘</span>
            <div>
                <h1 class="text-lg font-bold text-white tracking-wide">Guideline Gateway</h1>
                <p class="text-xs text-slate-400">Offline-First RAG & SLM</p>
            </div>
        </div>
        <div id="pack-badge" class="px-3 py-1 bg-emerald-950 text-emerald-400 border border-emerald-800 rounded-full text-xs font-semibold">
            Loading...
        </div>
    </header>

    <main class="flex-1 max-w-4xl w-full mx-auto p-4 flex flex-col">
        <div id="messages" class="flex-1 overflow-y-auto space-y-4 mb-4 p-2">
            <div class="bg-slate-800/80 p-4 rounded-xl border border-slate-700/60 shadow-sm max-w-2xl">
                <p class="text-sm text-slate-300">
                    Welcome to <strong>Guideline Gateway</strong>. Ask any question regarding the active guideline rules.
                    Every answer is strictly grounded in the document with verifiable citations.
                </p>
            </div>
        </div>

        <div class="border-t border-slate-800 pt-3">
            <form id="chat-form" class="flex gap-2">
                <input id="query-input" type="text" placeholder="Ask a question (e.g. Can a player be offside from a throw-in?)"
                    class="flex-1 bg-slate-800 border border-slate-700 rounded-xl px-4 py-3 text-sm text-white focus:outline-none focus:ring-2 focus:ring-blue-500">
                <button type="submit" class="bg-blue-600 hover:bg-blue-500 text-white font-medium px-5 py-3 rounded-xl text-sm transition">
                    Send
                </button>
            </form>
        </div>
    </main>

    <script>
        async function loadStatus() {
            try {
                const res = await fetch('/healthz');
                const data = await res.json();
                document.getElementById('pack-badge').innerText = 'Pack: ' + (data.active_pack || 'None');
            } catch (e) {
                document.getElementById('pack-badge').innerText = 'Offline';
            }
        }
        loadStatus();

        const messages = document.getElementById('messages');
        const form = document.getElementById('chat-form');
        const input = document.getElementById('query-input');
        const history = [];

        form.onsubmit = async (e) => {
            e.preventDefault();
            const text = input.value.trim();
            if (!text) return;
            input.value = '';

            const uMsg = document.createElement('div');
            uMsg.className = 'ml-auto bg-blue-600 text-white p-3.5 rounded-2xl rounded-tr-sm max-w-xl text-sm shadow';
            uMsg.innerText = text;
            messages.appendChild(uMsg);
            messages.scrollTop = messages.scrollHeight;

            const aMsg = document.createElement('div');
            aMsg.className = 'bg-slate-800/90 text-slate-200 p-4 rounded-2xl rounded-tl-sm max-w-2xl text-sm border border-slate-700/60 shadow space-y-2';
            aMsg.innerHTML = '<span class="text-slate-400 italic">Thinking and retrieving evidence...</span>';
            messages.appendChild(aMsg);
            messages.scrollTop = messages.scrollHeight;

            try {
                const res = await fetch('/v1/ask', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({question: text, history: history})
                });
                const data = await res.json();
                let html = '<div class="whitespace-pre-wrap leading-relaxed">' + data.answer + '</div>';
                if (data.citations && data.citations.length > 0) {
                    html += '<div class="mt-3 pt-3 border-t border-slate-700/80 flex flex-wrap gap-2 text-xs">';
                    data.citations.forEach(c => {
                        html += '<span class="bg-slate-700/80 text-blue-300 px-2 py-1 rounded border border-slate-600 font-mono" title="' + (c.text_snippet || '') + '">' + c.marker + ' ' + (c.law_title || c.chunk_id) + '</span>';
                    });
                    html += '</div>';
                }
                if (data.latencies) {
                    html += '<div class="text-[11px] text-slate-500 pt-1">Total: ' + data.latencies.total_ms + 'ms | Retrieval: ' + data.latencies.retrieval_ms + 'ms</div>';
                }
                aMsg.innerHTML = html;
                history.push({role: 'user', content: text});
                history.push({role: 'assistant', content: data.answer});
            } catch (err) {
                aMsg.innerHTML = '<span class="text-red-400">Error: ' + err.message + '</span>';
            }
            messages.scrollTop = messages.scrollHeight;
        };
    </script>
</body>
</html>"""
        )
