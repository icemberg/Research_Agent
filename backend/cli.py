"""
CLI entry point using Typer.

Uses the same Orchestrator as the FastAPI layer — no duplicated logic (DRY).
"""

from __future__ import annotations

import asyncio
import logging
import sys
from pathlib import Path

import typer
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.table import Table
from rich.progress import Progress, SpinnerColumn, TextColumn

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler()],
)

app = typer.Typer(
    name="research-agent",
    help="Research Agent with Citations — ask questions, get cited answers.",
    rich_markup_mode="rich",
)
console = Console()


def _get_orchestrator():
    """Lazy-load the orchestrator to avoid import-time model loading."""
    from backend.pipeline.orchestrator import Orchestrator
    return Orchestrator()


def _get_database():
    """Lazy-load the database."""
    from backend.storage.database import Database
    return Database()


@app.command()
def ingest(
    path: str = typer.Argument(..., help="File or directory to ingest"),
):
    """Ingest documents into the research corpus."""
    file_path = Path(path)
    if not file_path.exists():
        console.print(f"[red]Error:[/red] Path not found: {path}")
        raise typer.Exit(1)

    orchestrator = _get_orchestrator()
    db = _get_database()

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        if file_path.is_file():
            task = progress.add_task(f"Ingesting {file_path.name}...", total=None)
            result = orchestrator.ingest_file(file_path)
            results = [result]
        elif file_path.is_dir():
            task = progress.add_task(f"Ingesting directory {file_path.name}/...", total=None)
            results = orchestrator.ingest_directory(file_path)
        else:
            console.print(f"[red]Error:[/red] Invalid path: {path}")
            raise typer.Exit(1)

    # Display results
    table = Table(title="Ingestion Results")
    table.add_column("Document", style="cyan")
    table.add_column("Chunks", style="green", justify="right")
    table.add_column("Status", style="bold")

    for r in results:
        status_style = "green" if r["status"] == "indexed" else "red"
        table.add_row(
            r["name"],
            str(r["chunk_count"]),
            f"[{status_style}]{r['status']}[/{status_style}]",
        )

        # Save to database
        from backend.models.passage import DocumentInfo
        db.save_document(DocumentInfo(
            document_id=r["document_id"],
            name=r["name"],
            chunk_count=r["chunk_count"],
            status=r["status"],
        ))

    console.print(table)
    total_chunks = sum(r["chunk_count"] for r in results)
    console.print(f"\n[green]✓[/green] Ingested {len(results)} files, {total_chunks} total chunks")


@app.command()
def ask(
    question: str = typer.Argument(..., help="Your research question"),
    web_search: bool = typer.Option(False, "--web", "-w", help="Allow web search"),
):
    """Ask a question and get a cited answer."""
    orchestrator = _get_orchestrator()
    db = _get_database()

    console.print(f"\n[bold cyan]Question:[/bold cyan] {question}\n")

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        task = progress.add_task("Thinking...", total=None)

        # Run the async orchestrator
        response = asyncio.run(
            orchestrator.ask(
                question=question,
                allow_web_search=web_search,
            )
        )

    # Display the answer
    if response.abstained:
        console.print(Panel(
            response.answer_text,
            title="[yellow]⚠ Abstained[/yellow]",
            border_style="yellow",
        ))
    else:
        console.print(Panel(
            Markdown(response.answer_text),
            title="[green]✓ Answer[/green]",
            border_style="green",
        ))

    # Display citations
    if response.citations:
        console.print("\n[bold]Citations:[/bold]")
        for citation in response.citations:
            console.print(
                f"  [{citation.marker}] [cyan]{citation.source}[/cyan] "
                f"({citation.location})"
            )
            console.print(f"      [dim]{citation.snippet[:100]}...[/dim]")

    # Display metadata
    console.print(
        f"\n[dim]Latency: {response.latency_ms:.0f}ms | "
        f"ID: {response.question_id} | "
        f"{response.confidence_note}[/dim]"
    )

    # Save to history
    db.save_question(response)


@app.command()
def documents():
    """List all ingested documents."""
    orchestrator = _get_orchestrator()
    docs = orchestrator.get_document_list()

    if not docs:
        console.print("[yellow]No documents ingested yet.[/yellow]")
        console.print("Use [bold]research-agent ingest <path>[/bold] to add documents.")
        return

    table = Table(title="Ingested Documents")
    table.add_column("Document", style="cyan")
    table.add_column("Chunks", style="green", justify="right")

    for doc in docs:
        table.add_row(doc["name"], str(doc["chunk_count"]))

    console.print(table)
    console.print(f"\n[dim]Total: {len(docs)} documents[/dim]")


@app.command()
def history(
    limit: int = typer.Option(10, "--limit", "-n", help="Number of recent questions"),
):
    """Show past questions and answers."""
    db = _get_database()
    questions = db.get_questions(limit=limit)

    if not questions:
        console.print("[yellow]No question history yet.[/yellow]")
        return

    for q in questions:
        status = "[yellow]⚠ Abstained[/yellow]" if q.abstained else "[green]✓ Answered[/green]"
        console.print(f"\n{status} [bold]{q.question}[/bold]")
        console.print(f"  [dim]{q.answer_text[:150]}...[/dim]")
        console.print(f"  [dim]Citations: {len(q.citations)} | {q.created_at}[/dim]")


if __name__ == "__main__":
    app()
