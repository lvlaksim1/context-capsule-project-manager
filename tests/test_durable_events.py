from __future__ import annotations

import copy
import json
import unittest
from urllib.error import HTTPError

from installer.durable_events import plan_durable_event
from installer.event_evidence import verify_event
from installer.github_atomic import ConcurrentBranchUpdate, publish_single_commit
from installer.model import CapsuleModelError, clean_install_changes, readiness_snapshot
from installer.working_index import (
    INDEX_PATH, LEDGER_PATH, EVENTS_PATH,
    index_document, read_active_commitments, validate_index,
)
from test_capsulectl import TEMPLATES, CORE_SHA, FakeBackend, apply, ready_overrides


def initial():
    return apply({}, clean_install_changes(
        {}, TEMPLATES, "owner/repo", "main", CORE_SHA, semantic_overrides=ready_overrides()
    ))


def event(event_id="evt-001", kind="merge", transitions=None):
    return {
        "id": event_id, "kind": kind, "summary": "Verified change of test behavior.",
        "product_repository": "owner/repo", "product_branch": "main",
        "evidence_url": "https://github.com/owner/repo/pull/17",
        "commitments": transitions or [],
    }


class DurableEventTests(unittest.TestCase):
    def test_atomic_plan_updates_bdi_ledger_seal_and_index(self):
        start = initial()
        baseline_ready, errors = readiness_snapshot(start)
        self.assertTrue(baseline_ready, errors)
        tx = plan_durable_event(start, event(transitions=[{
            "id": "work-001", "action": "open",
            "statement": "Check live desktop behavior with the owner.",
            "requires_owner_acceptance": True,
        }]), expected_head="a" * 40, evidence_verified=True)
        self.assertEqual(tx.branch, "main")
        self.assertEqual(tx.repository, "owner/repo")
        self.assertEqual(tx.expected_head, "a" * 40)
        self.assertIn(INDEX_PATH, tx.changes)
        self.assertIn(LEDGER_PATH, tx.changes)
        self.assertIn(EVENTS_PATH, tx.changes)
        self.assertIn(".context/manager/state-integrity.json", tx.changes)
        done = apply(start, tx.changes)
        ready, errors = readiness_snapshot(done)
        self.assertTrue(ready, errors)
        self.assertEqual(validate_index(done), [])
        from installer.model import _durable_entries, _entry_provenance_errors
        beliefs = ".context/manager/beliefs.md"
        self.assertEqual(len(_durable_entries(done[beliefs])), len(_durable_entries(start[beliefs])) + 1)
        self.assertEqual(_entry_provenance_errors(done[beliefs], "manager.beliefs"), [])
        self.assertEqual(read_active_commitments(done)[0]["statement"],
                         "Check live desktop behavior with the owner.")
        manifest = json.loads(done[".context/manifest.json"])
        self.assertEqual(manifest["manager"]["commitments"], LEDGER_PATH)
        self.assertEqual(manifest["manager"]["events"], EVENTS_PATH)
        self.assertIn(LEDGER_PATH, json.loads(done[".context/manager/state-integrity.json"])["coupled_paths"])
        self.assertEqual(start[".context/current/state.md"],
                         done[".context/current/state.md"][:len(start[".context/current/state.md"])].strip("\n") + "\n")

    def test_owner_acceptance_is_not_inferred_from_release_or_merge(self):
        open_event = event(transitions=[{
            "id": "owner-check", "action": "open",
            "statement": "Require explicit owner acceptance.", "requires_owner_acceptance": True,
        }])
        with_open = apply(initial(), plan_durable_event(initial(), open_event,
            expected_head="a" * 40, evidence_verified=True).changes)
        fake_done = event("evt-002", transitions=[{
            "id": "owner-check", "action": "complete", "reason": "Code merged.",
        }])
        with self.assertRaisesRegex(CapsuleModelError, "owner acceptance"):
            plan_durable_event(with_open, fake_done, expected_head="b" * 40, evidence_verified=True)
        accepted = event("evt-002", kind="owner-acceptance", transitions=[{
            "id": "owner-check", "action": "complete", "reason": "Owner confirmed behavior.",
        }])
        accepted["evidence_url"] = "https://example.org/owner-acceptance/2"
        accepted["owner_confirmed"] = True
        done = apply(with_open, plan_durable_event(with_open, accepted,
            expected_head="b" * 40, evidence_verified=True).changes)
        self.assertEqual(read_active_commitments(done), [])
        self.assertEqual(json.loads(done[LEDGER_PATH])["items"]["owner-check"]["status"], "completed")

    def test_incoherent_seal_blocks_event_even_with_verified_evidence(self):
        x = initial()
        x[".context/current/state.md"] += "Unsealed mutation\n"
        with self.assertRaisesRegex(CapsuleModelError, "incoherent"):
            plan_durable_event(x, event(), expected_head="a" * 40, evidence_verified=True)

    def test_replay_and_ghost_completion_are_rejected(self):
        x = initial()
        once = plan_durable_event(x, event(), expected_head="a" * 40, evidence_verified=True)
        x = apply(x, once.changes)
        with self.assertRaisesRegex(CapsuleModelError, "already published"):
            plan_durable_event(x, event(), expected_head="b" * 40, evidence_verified=True)
        with self.assertRaisesRegex(CapsuleModelError, "missing/inactive"):
            plan_durable_event(x, event("evt-002", transitions=[{
                "id": "missing", "action": "complete", "reason": "Assumed complete"
            }]), expected_head="b" * 40, evidence_verified=True)

    def test_refuses_unverified_and_cross_product_events(self):
        x = initial()
        with self.assertRaisesRegex(CapsuleModelError, "not verified"):
            plan_durable_event(x, event(), expected_head="a" * 40, evidence_verified=False)
        foreign = event()
        foreign["product_branch"] = "context"
        with self.assertRaisesRegex(CapsuleModelError, "authority"):
            plan_durable_event(x, foreign, expected_head="a" * 40, evidence_verified=True)

    def test_large_canonical_history_still_has_bounded_index(self):
        x = initial()
        # All legacy text remains authoritative; the index never copies it.
        x[".context/current/state.md"] += "\n" + ("Previous verified change.\n" * 1000)
        from installer.model import build_manager_state_integrity, canonical_json
        manifest = json.loads(x[".context/manifest.json"])
        prev = json.loads(x[".context/manager/state-integrity.json"])
        x[".context/manager/state-integrity.json"] = canonical_json(
            build_manager_state_integrity(x, manifest, existing=prev)
        )
        many = [{
            "id": f"work-{n:03}", "action": "open",
            "statement": "Preserve complete statement for task " + str(n),
        } for n in range(30)]
        done = apply(x, plan_durable_event(x, event(transitions=many),
            expected_head="a" * 40, evidence_verified=True).changes)
        self.assertLess(len(done[INDEX_PATH]), 8192)
        self.assertEqual(len(read_active_commitments(done)), 30)
        self.assertIn("Previous verified change.", done[".context/current/state.md"])
        self.assertEqual(validate_index(done), [])

    def test_index_budget_is_fail_closed(self):
        x = initial()
        with self.assertRaisesRegex(CapsuleModelError, "budget"):
            index_document(x, max_chars=260)

    def test_source_conflict_and_tamper_detected(self):
        x = initial()
        done = apply(x, plan_durable_event(x, event(transitions=[{
            "id": "required-one", "action": "open", "statement": "Open obligation.",
        }]), expected_head="a" * 40, evidence_verified=True).changes)
        altered = dict(done)
        altered[INDEX_PATH] = done[INDEX_PATH].replace("required-one", "forged-name")
        self.assertTrue(validate_index(altered))
        altered = dict(done)
        ledger = json.loads(done[LEDGER_PATH])
        ledger["items"]["required-one"]["status"] = "completed"
        altered[LEDGER_PATH] = json.dumps(ledger)
        ready, errors = readiness_snapshot(altered)
        self.assertFalse(ready)
        self.assertIn("integrity", " ".join(errors))

    def test_atomic_backend_aborts_on_race(self):
        x = initial()
        plan = plan_durable_event(x, event(), expected_head="1" * 40, evidence_verified=True)
        ok = FakeBackend()
        self.assertEqual(publish_single_commit(ok, plan), "4" * 40)
        race = FakeBackend()
        race.move_after_tree = True
        with self.assertRaises(ConcurrentBranchUpdate):
            publish_single_commit(race, plan)
        self.assertEqual(race.moves, [])

    def test_opt_in_hook_is_disabled_by_default_and_cannot_infer_approval(self):
        from pathlib import Path
        template = (Path(__file__).resolve().parents[1] /
                    "templates/workflows/pm-durable-events.yml").read_text(encoding="utf-8")
        self.assertIn("vars.PM_SOURCE_COMMIT", template)
        self.assertIn("vars.PM_MANAGER_BRANCH", template)
        self.assertIn("types: [published]", template)
        self.assertIn("types: [closed]", template)
        self.assertIn("pull_request.merged == true", template)
        self.assertIn('event_kind = "release"', template)
        self.assertIn('event_kind = "merge"', template)
        self.assertNotIn('event_kind = "owner-acceptance"', template)
        self.assertIn("--publish", template)
        self.assertIn("--expected-head", template)

    def test_verified_evidence_is_read_from_github(self):
        x = event()
        verify_event(x, fetch=lambda url, token: {"state": "closed", "merged_at": "2026-10-26", "base": {"ref": "main"}})
        with self.assertRaisesRegex(CapsuleModelError, "not merged"):
            verify_event(x, fetch=lambda url, token: {"state": "open", "merged_at": None})
        with self.assertRaisesRegex(CapsuleModelError, "product branch"):
            verify_event(x, fetch=lambda url, token: {"state": "closed", "merged_at": "date", "base": {"ref": "other"}})
        release = event(kind="release")
        release["evidence_url"] = "https://github.com/owner/repo/releases/tag/v1.2.3"
        verify_event(release, fetch=lambda url, token: {"tag_name": "v1.2.3", "draft": False})
        with self.assertRaisesRegex(CapsuleModelError, "not a published"):
            verify_event(release, fetch=lambda url, token: {"tag_name": "v1.2.3", "draft": True})
        ci = event(kind="verified-regression")
        ci["evidence_url"] = "https://github.com/owner/repo/actions/runs/123"
        verify_event(ci, fetch=lambda url, token: {"status": "completed", "conclusion": "success"})
        with self.assertRaisesRegex(CapsuleModelError, "not succeeded"):
            verify_event(ci, fetch=lambda url, token: {"status": "in_progress"})
        owner = event(kind="owner-acceptance")
        owner["owner_confirmed"] = True
        owner["evidence_url"] = "https://example.org/approval"
        with self.assertRaisesRegex(CapsuleModelError, "direct"):
            verify_event(owner, confirm_owner=False)
        verify_event(owner, confirm_owner=True)


if __name__ == "__main__":
    unittest.main()
