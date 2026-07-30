"""Rich Terminal UI Layout & Event Presentation Renderer for Aero Mesh."""

import sys
import getpass
from typing import Dict, Any, List, Tuple
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

# Force UTF-8 encoding on Windows console streams to handle Rich emojis seamlessly
if sys.platform == "win32":
    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8")
        except Exception:
            pass
    if hasattr(sys.stderr, "reconfigure"):
        try:
            sys.stderr.reconfigure(encoding="utf-8")
        except Exception:
            pass

console = Console()

class AeroTerminalUI:
    """Renders formatted Rich terminal banners, SLA summaries, and interactive prompts."""

    @staticmethod
    def render_agent_banner(manifest: Any) -> None:
        table = Table.grid(expand=True)
        table.add_column(style="bold cyan", justify="left")
        table.add_column(style="white", justify="left")

        table.add_row("Agent Identifier  ", f"{manifest.identity.id} (v{manifest.identity.version})")
        table.add_row("Domain            ", manifest.capabilities.domain)
        table.add_row("CDI Driver        ", manifest.cognitive_runtime.driver)

        panel = Panel(
            table,
            title="[bold green]🚀 Aero Agent Engine (aero / amx)[/bold green]",
            border_style="cyan",
            expand=False
        )
        console.print(panel)

    @staticmethod
    def prompt_credential_approval(key_id: str, existing_val: str, kind: str = "credential", input_fn=None) -> Tuple[str, bool]:
        """Asks human user for explicit approval to use an existing key or input a new key."""
        masked_val = existing_val[:4] + "****" + existing_val[-4:] if len(existing_val) > 8 else "****"
        panel = Panel(
            f"[bold yellow]🔑 Found Environment Credential:[/bold yellow] [bold white]{key_id}[/bold white] (Value: [cyan]{masked_val}[/cyan])\n\n"
            f"[bold white]Options:[/bold white]\n"
            f"  [bold green][1][/bold green] Approve using existing environment key\n"
            f"  [bold yellow][2][/bold yellow] Enter a new secret key\n"
            f"  [bold red][3][/bold red] Reject and abort\n",
            title="[bold yellow]Explicit User Key Approval[/bold yellow]",
            border_style="yellow",
            expand=False
        )
        console.print(panel)

        if input_fn:
            choice = input_fn(f"Select option [1-3] (Default 1): ")
        else:
            choice = input("Select option [1-3] (Default 1): ")

        choice = choice.strip() or "1"

        if choice == "1":
            console.print(f"[bold green]✅ Approved using existing key '{key_id}'.[/bold green]")
            return (existing_val, True)
        elif choice == "2":
            if input_fn:
                new_val = input_fn(f"Enter new secret value for '{key_id}': ")
            else:
                try:
                    new_val = getpass.getpass(f"Enter new secret value for '{key_id}': ")
                except Exception:
                    new_val = input(f"Enter new secret value for '{key_id}': ")
            if new_val and new_val.strip():
                console.print(f"[bold green]✅ Set new key for '{key_id}'.[/bold green]")
                return (new_val.strip(), True)
            return ("", False)
        else:
            console.print(f"[bold red]❌ Key '{key_id}' rejected by user.[/bold red]")
            return ("", False)

    @staticmethod
    def prompt_missing_credential(key_id: str, kind: str = "credential", prompt_fn=None) -> str:
        """Prompts human user interactively for a missing vault requirement."""
        panel = Panel(
            f"[bold yellow]🔑 Missing Required Credential:[/bold yellow] [bold white]{key_id}[/bold white] (Kind: {kind})\n"
            f"[dim]Please enter the value to continue execution and save securely to ~/.aeromesh/credentials.json.[/dim]",
            title="[bold yellow]Interactive Vault Resolution[/bold yellow]",
            border_style="yellow",
            expand=False
        )
        console.print(panel)

        if prompt_fn:
            val = prompt_fn(f"Enter secret for '{key_id}': ")
        else:
            try:
                val = getpass.getpass(f"Enter secret for '{key_id}': ")
            except Exception:
                val = input(f"Enter secret for '{key_id}': ")

        if val and val.strip():
            console.print(f"[bold green]✅ Credential '{key_id}' acquired and saved to vault.[/bold green]")
            return val.strip()

        return ""

    @staticmethod
    def render_diagnostics(diagnostics: Any) -> None:
        table = Table(title="🔍 Real-Time OTel Diagnostic Traces & Performance Metrics", header_style="bold magenta")
        table.add_column("Span ID", style="dim")
        table.add_column("Event Type", style="cyan")
        table.add_column("Component", style="green")
        table.add_column("Duration", style="yellow")
        table.add_column("Memory (MB)", style="blue")

        spans = []
        summary = {}

        if isinstance(diagnostics, dict):
            spans = diagnostics.get("spans", [])
            summary = {
                "total_spans": diagnostics.get("total_spans", len(spans)),
                "total_duration_ms": diagnostics.get("total_duration_ms", 0.0),
                "peak_memory_mb": diagnostics.get("peak_memory_mb", 0.0),
            }
            for span in spans:
                table.add_row(
                    str(span.get("span_id", "")),
                    str(span.get("event_type", "")),
                    str(span.get("component", "")),
                    f"{span.get('duration_ms', 0.0)} ms",
                    f"{span.get('memory_mb', 0.0)} MB"
                )
        else:
            spans = getattr(diagnostics, "spans", [])
            summary = diagnostics.get_summary()
            for span in spans:
                table.add_row(
                    span.span_id,
                    span.event_type,
                    span.component,
                    f"{span.duration_ms} ms",
                    f"{span.memory_mb} MB"
                )

        console.print(table)
        summary_panel = Panel(
            f"[bold white]Total Spans:[/bold white] {summary['total_spans']} | "
            f"[bold white]Total Latency:[/bold white] {summary['total_duration_ms']} ms | "
            f"[bold white]Peak Memory:[/bold white] {summary['peak_memory_mb']} MB",
            title="[bold green]📊 Performance SLA Summary[/bold green]",
            border_style="green",
            expand=False
        )
        console.print(summary_panel)

    @staticmethod
    def render_result(result_text: str) -> None:
        panel = Panel(
            result_text,
            title="[bold cyan]✨ Verified Execution Result[/bold cyan]",
            border_style="bright_blue",
            expand=False
        )
        console.print(panel)

    @staticmethod
    def render_error(error_text: str) -> None:
        panel = Panel(
            f"[bold red]{error_text}[/bold red]",
            title="[bold red]❌ AMX Execution Error[/bold red]",
            border_style="red",
            expand=False
        )
        console.print(panel)
