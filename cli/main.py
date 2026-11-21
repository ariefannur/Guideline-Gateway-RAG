"""Command-line interface for Guideline Gateway and kpack tooling."""

import os
import shutil
from typing import Optional

import typer
import logging
import os

# Configure logger for CLI operations
log_dir = os.path.join(os.path.dirname(__file__), "..", "logs")
os.makedirs(log_dir, exist_ok=True)
logging.basicConfig(
    filename=os.path.join(log_dir, "cli.log"),
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)

from rich import print as rprint
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt
from rich.table import Table

from engine.models import ChatMessage, QueryRequest
from kpack.evaluator import EvaluationHarness
from kpack.manifest import load_manifest, load_pack_config
from kpack.packager import Packager
from server.manager import PackManager

app = typer.Typer(
    name="guideline",
    help="Offline-first Domain-Agnostic Guideline Q&A System",
    no_args_is_help=True,
)

kpack_app = typer.Typer(
    name="kpack",
    help="Knowledge Pack build, validate, and evaluation tooling",
    no_args_is_help=True,
)

console = Console()


# ==========================================
# Guideline CLI Commands
# ==========================================


@app.command("ask")
def ask_command(
    query: str = typer.Argument(..., help="Question to ask based on the active guideline"),
    pack: Optional[str] = typer.Option(None, "--pack", "-p", help="Target knowledge pack ID"),
    lang: Optional[str] = typer.Option(None, "--language", "-l", help="Language code (en, id)"),
    top_k: int = typer.Option(5, "--top-k", "-k", help="Number of evidence chunks to retrieve"),
):
    """Ask a question against the active Knowledge Pack."""
    packs_dir = os.getenv("PACKS_DIR", "packs")
    manager = PackManager(packs_dir=packs_dir, active_pack_id=pack)

    if not manager.pipeline:
        rprint("[bold red]Error:[/bold red] Failed to initialize guideline pipeline.")
        raise typer.Exit(1)

    rprint(f"[dim]Active Pack: [bold cyan]{manager.active_pack_id}[/bold cyan][/dim]")
    req = QueryRequest(query=query, language=lang, top_k=top_k)
    logging.info("Ask command received: query='%s', pack='%s', lang='%s', top_k=%d", query, pack, lang, top_k)

    with console.status("[bold blue]Retrieving evidence and generating answer..."):
        response = manager.pipeline.run(req)
        logging.info("Pipeline completed: status=%s, total_ms=%d, retrieval_ms=%d, generation_ms=%d", response.status, response.latencies.total_ms, response.latencies.retrieval_ms, response.latencies.generation_ms)

    # Status badge
    status_color = "green" if response.status == "answered" else "yellow"
    rprint(f"\n[bold {status_color}]Status: {response.status.upper()}[/bold {status_color}]")

    # Main Answer Panel
    console.print(
        Panel(
            response.answer,
            title="[bold green]Answer[/bold green]",
            subtitle=(
                f"[dim]Total: {response.latencies.total_ms}ms | "
                f"Retrieval: {response.latencies.retrieval_ms}ms | "
                f"Generation: {response.latencies.generation_ms}ms[/dim]"
            ),
            border_style="blue",
        )
    )

    # Citations Table
    if response.citations:
        table = Table(title="Verifiable Citations", border_style="dim")
        table.add_column("Marker", style="cyan", width=8)
        table.add_column("Chunk ID", style="magenta", width=18)
        table.add_column("Title / Law", style="green")
        table.add_column("Snippet", style="dim", overflow="fold")

        for c in response.citations:
            snippet = (
                (c.text_snippet or "")[:80] + "..."
                if c.text_snippet and len(c.text_snippet) > 80
                else (c.text_snippet or "")
            )
            table.add_row(c.marker, c.chunk_id, c.law_title or "-", snippet)
        console.print(table)


@app.command("chat")
def chat_command(
    pack: Optional[str] = typer.Option(None, "--pack", "-p", help="Target knowledge pack ID"),
):
    """Interactive multi-turn terminal chat session."""
    packs_dir = os.getenv("PACKS_DIR", "packs")
    manager = PackManager(packs_dir=packs_dir, active_pack_id=pack)

    if not manager.pipeline:
        rprint("[bold red]Error:[/bold red] Failed to initialize guideline pipeline.")
        raise typer.Exit(1)

    console.print(
        Panel(
            f"Active Pack: [bold cyan]{manager.active_pack_id}[/bold cyan]\n"
            "Type your questions below. Type [bold red]exit[/bold red] or [bold red]quit[/bold red] to stop.",
            title="[bold]Guideline Gateway Chat[/bold]",
            border_style="cyan",
        )
    )

    history = []

    while True:
        try:
            user_input = Prompt.ask("\n[bold blue]You[/bold blue]")
            if not user_input or user_input.strip().lower() in ("exit", "quit", "q"):
                rprint("[yellow]Exiting chat session. Goodbye![/yellow]")
                break

            req = QueryRequest(query=user_input, history=history)
            with console.status("[dim]Processing..."):
                response = manager.pipeline.run(req)
            logging.info("Pipeline completed: status=%s, total_ms=%d, retrieval_ms=%d, generation_ms=%d", response.status, response.latencies.total_ms, response.latencies.retrieval_ms, response.latencies.generation_ms)

            console.print(f"\n[bold green]Assistant[/bold green]: {response.answer}")

            if response.citations:
                c_markers = " ".join([f"[{c.marker} -> {c.chunk_id}]" for c in response.citations])
                console.print(f"[dim cyan]Citations: {c_markers}[/dim cyan]")

            history.append(ChatMessage(role="user", content=user_input))
            history.append(ChatMessage(role="assistant", content=response.answer))
        except (KeyboardInterrupt, EOFError):
            rprint("\n[yellow]Session ended.[/yellow]")
            break


@app.command("serve")
def serve_command(
    host: str = typer.Option("127.0.0.1", "--host", "-h", help="Bind host"),
    port: int = typer.Option(8000, "--port", "-p", help="Bind port"),
    reload: bool = typer.Option(False, "--reload", "-r", help="Auto reload"),
):
    """Start the local FastAPI server."""
    import uvicorn

    rprint(f"[bold green]Starting Guideline Gateway server at http://{host}:{port}[/bold green]")
    uvicorn.run("server.app:app", host=host, port=port, reload=reload)


packs_app = typer.Typer(name="packs", help="Manage Knowledge Packs", no_args_is_help=True)
app.add_typer(packs_app)


@packs_app.command("list")
def list_packs_command():
    """List all installed knowledge packs."""
    packs_dir = os.getenv("PACKS_DIR", "packs")
    manager = PackManager(packs_dir=packs_dir)
    packs = manager.discover_packs()

    table = Table(title="Installed Knowledge Packs")
    table.add_column("Status", width=10)
    table.add_column("ID", style="cyan")
    table.add_column("Name", style="green")
    table.add_column("Edition", style="magenta")
    table.add_column("Domain")

    for pid, pdata in packs.items():
        is_active = pid == manager.active_pack_id
        status = "[bold green]ACTIVE[/bold green]" if is_active else "installed"
        table.add_row(
            status, pid, pdata.get("name", pid), pdata.get("edition", "-"), pdata.get("domain", "-")
        )

    console.print(table)


# ==========================================
# kpack CLI Commands
# ==========================================


@kpack_app.command("init")
def kpack_init(
    domain: str = typer.Argument(..., help="Domain identifier (e.g. safety-sops, legal-code)"),
    template_dir: str = typer.Option(
        "packs/_template", "--template", "-t", help="Path to pack template"
    ),
):
    """Create a new knowledge pack skeleton from template."""
    target_dir = os.path.join("packs", domain)
    if os.path.exists(target_dir):
        rprint(f"[bold red]Error:[/bold red] Pack directory already exists: {target_dir}")
        raise typer.Exit(1)

    if not os.path.exists(template_dir):
        rprint(f"[bold red]Error:[/bold red] Template directory not found: {template_dir}")
        raise typer.Exit(1)

    shutil.copytree(template_dir, target_dir)
    rprint(f"[bold green]Successfully initialized new pack at:[/bold green] {target_dir}")
    rprint("[dim]Next: update pack.yaml, glossary.yaml, and add source documents.[/dim]")


@kpack_app.command("validate")
def kpack_validate(
    pack_dir: str = typer.Argument(..., help="Path to knowledge pack directory"),
):
    """Validate knowledge pack integrity, manifests, and schema."""
    if not os.path.exists(pack_dir):
        rprint(f"[bold red]Error:[/bold red] Directory not found: {pack_dir}")
        raise typer.Exit(1)

    try:
        Packager.validate_pack_dir(pack_dir)
        load_manifest(pack_dir)
        load_pack_config(pack_dir)
        rprint(
            f"[bold green]Validation SUCCESS:[/bold green] Pack '{pack_dir}' contains all required artifacts."
        )
    except Exception as exc:
        rprint(f"[bold red]Validation FAILED:[/bold red] {exc}")
        raise typer.Exit(1)


@kpack_app.command("build")
def kpack_build(
    pack_dir: str = typer.Argument(..., help="Path to knowledge pack directory"),
    output: Optional[str] = typer.Option(None, "--output", "-o", help="Output .kpack file path"),
):
    """Package a verified pack directory into a .kpack archive."""
    if not os.path.exists(pack_dir):
        rprint(f"[bold red]Error:[/bold red] Directory not found: {pack_dir}")
        raise typer.Exit(1)

    out_file = output or f"{pack_dir.rstrip('/')}.kpack"
    try:
        pack_hash = Packager.build_kpack(pack_dir, out_file)
        rprint(f"[bold green]Successfully built knowledge pack archive:[/bold green] {out_file}")
        rprint(f"[dim]SHA-256: [cyan]{pack_hash}[/cyan][/dim]")
    except Exception as exc:
        rprint(f"[bold red]Build FAILED:[/bold red] {exc}")
        raise typer.Exit(1)


@kpack_app.command("eval")
def kpack_eval(
    pack_dir: str = typer.Argument(..., help="Path to knowledge pack directory"),
    golden: Optional[str] = typer.Option(None, "--golden", "-g", help="Custom golden.jsonl path"),
    top_k: int = typer.Option(5, "--top-k", "-k", help="Top-k evaluation threshold"),
):
    """Run regression evaluation harness on a knowledge pack."""
    manager = PackManager(packs_dir=os.path.dirname(os.path.abspath(pack_dir)))
    pack_id = os.path.basename(os.path.abspath(pack_dir))
    manager.activate_pack(pack_id)

    golden_file = golden or os.path.join(pack_dir, "eval", "golden.jsonl")
    if not os.path.exists(golden_file):
        rprint(f"[bold red]Error:[/bold red] Golden set not found: {golden_file}")
        raise typer.Exit(1)

    harness = EvaluationHarness(pipeline=manager.pipeline, golden_path=golden_file)
    with console.status("[bold blue]Executing golden regression suite..."):
        results = harness.run_eval(top_k=top_k)

    # Print summary table
    table = Table(title=f"Evaluation Results for {pack_id}")
    table.add_column("Metric", style="cyan")
    table.add_column("Value", style="green")

    table.add_row("Total Questions", str(results["total_questions"]))
    table.add_row("Factual Questions", str(results["factual_questions"]))
    table.add_row("Trap / Abstain Questions", str(results["trap_questions"]))
    table.add_row(f"Recall@{top_k}", f"{results[f'recall@{top_k}']}%")
    table.add_row("MRR", f"{results['mrr']}")
    table.add_row("Abstain Accuracy", f"{results['abstain_accuracy']}%")
    table.add_row(
        "Passes Gate",
        "[bold green]YES[/bold green]" if results["passes_gate"] else "[bold red]NO[/bold red]",
    )

    console.print(table)


if __name__ == "__main__":
    app()
