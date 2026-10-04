"""Interactive credential prompts; secrets never appear in terminal output."""

import getpass
from typing import Callable

from rich.console import Console


console = Console(stderr=True)


class AeroTerminalUI:
    @staticmethod
    def prompt_missing_credential(key_id: str, kind: str = "credential") -> str:
        console.print(f"Required {kind}: {key_id}", markup=False)
        return getpass.getpass(f"Enter value for {key_id}: ").strip()

    @staticmethod
    def prompt_credential_approval(
        key_id: str,
        existing_val: str,
        kind: str = "credential",
        input_fn: Callable[[str], str] | None = None,
    ) -> tuple[str, bool]:
        console.print(
            f"A configured {kind} is available for {key_id}.\n"
            "[1] Use configured value\n[2] Enter a replacement\n[3] Reject and abort",
            markup=False,
        )
        choice = (input_fn or input)("Select option [1/2/3] (default 1): ").strip()
        if choice in ("", "1"):
            return existing_val, True
        if choice == "2":
            value = AeroTerminalUI.prompt_missing_credential(key_id, kind)
            return value, bool(value)
        return "", False
