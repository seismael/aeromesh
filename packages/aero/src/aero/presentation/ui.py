"""Rich Terminal UI Layout & Event Presentation Renderer for Aero Mesh."""

import sys
import getpass
from typing import Dict, Any, List, Tuple, Optional
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

        fn = input_fn or input
        choice = fn("Select option [1/2/3] (default 1): ").strip()
        if choice in ("", "1"):
            return existing_val, True
        elif choice == "2":
            new_key = fn(f"Enter secret key for {key_id}: ").strip()
            return new_key, bool(new_key)
        else:
            return "", False

    @staticmethod
    def prompt_provider_selection(providers: List[Dict[str, str]], input_fn=None) -> Tuple[str, str]:
        """Prompts human user to select default LLM model provider and enter API key."""
        lines = ["[bold yellow]⚙️ No Default Model Provider Configured.[/bold yellow]\n", "Select a Model Provider:"]
        for idx, prov in enumerate(providers, 1):
            lines.append(f"  [bold green][{idx}][/bold green] {prov['name']} ({prov['env_var']})")

        panel = Panel("\n".join(lines), title="[bold cyan]LLM Model Provider Selection[/bold cyan]", border_style="cyan", expand=False)
        console.print(panel)

        fn = input_fn or input
        choice_str = fn("Select provider number (default 1): ").strip()
        choice_idx = int(choice_str) - 1 if choice_str.isdigit() and 1 <= int(choice_str) <= len(providers) else 0

        selected_prov = providers[choice_idx]
        console.print(f"[bold green]Selected Provider:[/bold green] {selected_prov['name']}")
        api_key = fn(f"Enter API Key for {selected_prov['name']}: ").strip()

        return selected_prov["id"], api_key

    @staticmethod
    def render_diagnostics_summary(summary: Any) -> None:
        """Renders diagnostic spans from either an AeroDiagnosticTracer or a summary dict."""
        # Support both tracer objects and raw summary dicts from get_summary()
        if isinstance(summary, dict):
            spans = summary.get("spans", [])
        elif hasattr(summary, "get_spans"):
            spans = summary.get_spans()
        elif hasattr(summary, "spans"):
            spans = [s if isinstance(s, dict) else {"event_type": str(s)} for s in summary.spans]
        else:
            spans = []

        table = Table(title="📊 Aero Engine Diagnostic Tracing Spans", show_header=True, header_style="bold magenta")
        table.add_column("Span ID", style="cyan")
        table.add_column("Component", style="green")
        table.add_column("Latency (ms)", justify="right", style="yellow")
        table.add_column("RAM (MB)", justify="right", style="magenta")

        for s in spans:
            table.add_row(
                s.get("event_type", "SPAN"),
                s.get("component", "Core"),
                f"{s.get('duration_ms', 0):.2f}",
                f"{s.get('memory_mb', 0):.2f}"
            )
        console.print(table)
        console.print(f"[bold cyan]Total Spans: {len(spans)}[/bold cyan]")

    @staticmethod
    def render_result(result: str) -> None:
        """Renders a verified execution result."""
        console.print(f"[bold green]✅ Result:[/bold green] {result}")

    @staticmethod
    def render_error(error: str) -> None:
        """Renders a domain error message."""
        console.print(f"[bold red]❌ Error:[/bold red] {error}")

    @staticmethod
    def render_diagnostics(diagnostics: Any) -> None:
        """Renders diagnostic spans. Accepts tracer object or summary dict."""
        AeroTerminalUI.render_diagnostics_summary(diagnostics)

    @staticmethod
    def render_requirements_checklist(checklist: Any) -> None:
        """Renders an upfront requirement checklist table for a decomposed user goal."""
        table = Table(
            title=f"🎯 Goal Requirement Checklist & Capability Plan\n[dim]{checklist.goal}[/dim]",
            show_header=True,
            header_style="bold cyan",
        )
        table.add_column("Category", style="yellow")
        table.add_column("Details", style="green")

        mode_str = "JIT Synthesized Agent" if checklist.is_jit_synthesized else "Discovered Registry Swarm"
        table.add_row("Execution Mode", mode_str)
        table.add_row("Agents", ", ".join(checklist.matched_agent_ids))

        req_keys = [r.id for r in checklist.required_credentials]
        table.add_row("Required Credentials", ", ".join(req_keys) if req_keys else "None (Public API / Offline)")

        console.print(table)

    @staticmethod
    def render_search_results(results: List[Any]) -> None:
        """Renders 2-Tier Search Index results in a Rich table layout."""
        table = Table(title="🔍 AeroMesh 2-Tier Agent Search Index", show_header=True, header_style="bold cyan")
        table.add_column("Agent ID", style="bold green")
        table.add_column("Score", justify="right", style="yellow")
        table.add_column("Tier", style="magenta")
        table.add_column("Domain", style="blue")
        table.add_column("Match Rationale", style="white")

        for res in results:
            table.add_row(
                res.record.id,
                f"{res.match_score:.2f}",
                res.search_tier,
                res.record.domain,
                res.rationale,
            )

        console.print(table)

    @staticmethod
    def render_security_audit(audit_res: Dict[str, Any]) -> None:
        """Renders static security scanner results and Sigstore cryptographic attestations."""
        is_sec = audit_res.get("is_secure", False)
        status_str = "[bold green]SECURE ✅[/bold green]" if is_sec else "[bold red]VULNERABLE ❌[/bold red]"

        lines = [
            f"[bold cyan]Agent ID:[/bold cyan] {audit_res.get('agent_id')} (v{audit_res.get('version')})",
            f"[bold cyan]Security Status:[/bold cyan] {status_str}",
            f"[bold cyan]SHA-256 Sigstore Hash:[/bold cyan] [yellow]{audit_res.get('sha256_attestation')}[/yellow]\n",
        ]

        issues = audit_res.get("issues", [])
        if issues:
            lines.append("[bold red]Detected Issues:[/bold red]")
            for issue in issues:
                lines.append(f"  • {issue}")
        else:
            lines.append("[bold green]Zero security vulnerabilities detected.[/bold green]")

        panel = Panel("\n".join(lines), title="[bold magenta]🛡️ Guardian Security Attestation Audit[/bold magenta]", border_style="magenta", expand=False)
        console.print(panel)


