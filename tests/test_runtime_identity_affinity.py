from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]

PROJECT_MANAGER_FILES = [
    ROOT / ".context" / "ENTRYPOINT.md",
    ROOT / ".context" / "manager" / "CONTRACT.md",
    ROOT / ".context" / "manager" / "PROTOCOL.md",
    ROOT / "templates" / ".context" / "ENTRYPOINT.md",
    ROOT / "templates" / ".context" / "manager" / "CONTRACT.md",
    ROOT / "templates" / ".context" / "manager" / "PROTOCOL.md",
]

SERVICE_AGENT_FILES = [
    ROOT / "service-agent-templates" / ".context" / "ENTRYPOINT.md",
    ROOT / "service-agent-templates" / ".context" / "service-agent" / "CONTRACT.md",
    ROOT / "service-agent-templates" / ".context" / "service-agent" / "PROTOCOL.md",
]

ALL_RUNTIME_CONTRACTS = PROJECT_MANAGER_FILES + SERVICE_AGENT_FILES


class RuntimeIdentityAffinityTests(unittest.TestCase):
    def contents(self):
        return "\n".join(p.read_text(encoding="utf-8") for p in ALL_RUNTIME_CONTRACTS)

    def test_no_current_same_runtime_cross_agent_reinstantiation(self):
        text = self.contents().lower()
        forbidden = [
            "reinstate the next persistent agent directly in the same live runtime",
            "reinstantiates that caller in the same live runtime",
            "reinstate that caller in the same live runtime",
        ]
        for phrase in forbidden:
            self.assertNotIn(phrase, text)

    def test_project_manager_contract_requires_fixed_runtime_identity(self):
        text = (ROOT / "templates" / ".context" / "manager" / "CONTRACT.md").read_text(encoding="utf-8")
        self.assertIn("A runtime may carry at most one persistent Agent identity", text)
        self.assertIn("A different persistent target requires a separate runtime", text)

    def test_service_agent_contract_requires_fixed_runtime_identity(self):
        text = (ROOT / "service-agent-templates" / ".context" / "service-agent" / "CONTRACT.md").read_text(encoding="utf-8")
        self.assertIn("identity-affine", text)
        self.assertIn("MUST NOT reinstate a different persistent Agent", text)

    def test_manual_pull_and_new_runtime_continuation_are_normative(self):
        text = self.contents()
        self.assertIn("continuation:manual-pull", text)
        self.assertIn("continuation:automatic-new-runtime", text)
        self.assertIn("runtime:caller-continuation", text)

    def test_user_visible_header_contract_is_installed(self):
        text = self.contents()
        self.assertIn("DD.MM.YYYY · HH:MM MSK · <source_id>", text)
        self.assertIn("Europe/Moscow", text)

    def test_responsibility_semantics_are_not_replaced_by_runtime_routing(self):
        contract = (ROOT / "templates" / ".context" / "manager" / "CONTRACT.md").read_text(encoding="utf-8")
        self.assertIn(
            "Responsibility, authority, and execution ownership are separate dimensions",
            contract,
        )
        self.assertIn("responsibility semantics", contract.lower())


if __name__ == "__main__":
    unittest.main()
