from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from urllib.error import HTTPError
from contextlib import redirect_stderr
from io import StringIO
from unittest.mock import patch

from installer.pmctl import require_product_freshness
from installer.runtime_guard import LifecycleGuardError

from installer.state_health import (
    BASELINE_PATH,
    FreshnessError,
    ProductEvidence,
    compare_product,
    inspect,
    load_baseline,
    observe_product,
    main as freshness_main,
    write_baseline,
)

REPOSITORY = "owner/sample"
HEAD = "a" * 40
NEW_HEAD = "b" * 40
RELEASE_SHA = "c" * 40
NEW_RELEASE_SHA = "d" * 40


def fake_fetch(url, token):
    assert url.startswith("https://api.github.com/repos/owner/sample/")
    if "/branches/" in url:
        return {"commit": {"sha": HEAD}}
    if url.endswith("/releases/latest"):
        return {"tag_name": "v1.0.0", "target_commitish": "main"}
    if url.endswith("/commits/v1.0.0"):
        return {"sha": RELEASE_SHA}
    raise AssertionError("unexpected GitHub resource: " + url)


def evidence(head=HEAD, tag="v1.0.0", release=RELEASE_SHA, branch="main"):
    return ProductEvidence(REPOSITORY, branch, head, tag, release)


class ProductFreshnessTests(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.dir.cleanup)
        self.root = Path(self.dir.name)
        (self.root / ".context").mkdir()
        (self.root / ".context/manifest.json").write_text(
            json.dumps({
                "repository": REPOSITORY,
                "authority": {"manager_state_branch": "context", "product_branch": "main"},
            }), encoding="utf-8"
        )

    def test_live_release_tag_must_resolve_to_commit_not_target_branch(self):
        actual = observe_product(REPOSITORY, "main", fetch=fake_fetch)
        self.assertEqual(actual, evidence())

    def test_no_baseline_is_unknown_not_fresh(self):
        status, reasons, live = inspect(self.root, fetch=fake_fetch)
        self.assertEqual(status, "UNKNOWN")
        self.assertEqual(live, evidence())
        self.assertIn("baseline", " ".join(reasons))

    def test_exact_match_is_fresh(self):
        write_baseline(self.root, evidence())
        status, reasons, _ = inspect(self.root, fetch=fake_fetch)
        self.assertEqual((status, reasons), ("FRESH", []))
        self.assertEqual(load_baseline(self.root), evidence())

    def test_new_release_is_stale_even_when_head_unchanged(self):
        actual = evidence(tag="v1.1.0", release=NEW_RELEASE_SHA)
        status, reasons = compare_product(REPOSITORY, "main", evidence(), actual)
        self.assertEqual(status, "STALE")
        self.assertIn("release", " ".join(reasons))

    def test_branch_head_drift_must_be_reconciled_not_claimed_as_code_change(self):
        status, reasons = compare_product(REPOSITORY, "main", evidence(), evidence(head=NEW_HEAD))
        self.assertEqual(status, "DRIFT")
        self.assertIn("context-only", " ".join(reasons))

    def test_mismatched_authority_is_unknown(self):
        status, reasons = compare_product(REPOSITORY, "main", evidence(branch="context"), evidence())
        self.assertEqual(status, "UNKNOWN")

    def test_missing_release_is_supported_but_not_other_404(self):
        def no_releases(url, token):
            if url.endswith("/releases/latest"):
                raise HTTPError(url, 404, "no release", None, None)
            return fake_fetch(url, token)

        actual = observe_product(REPOSITORY, "main", fetch=no_releases)
        self.assertIsNone(actual.release_tag)
        self.assertIsNone(actual.release_sha)

        def missing_branch(url, token):
            raise HTTPError(url, 404, "missing branch", None, None)

        with self.assertRaises(FreshnessError):
            observe_product(REPOSITORY, "main", fetch=missing_branch)

    def test_network_failure_does_not_claim_fresh(self):
        def disconnected(url, token):
            raise TimeoutError("offline")

        write_baseline(self.root, evidence())
        status, reasons, live = inspect(self.root, fetch=disconnected)
        self.assertEqual(status, "UNKNOWN")
        self.assertIsNone(live)

    def test_rejects_corrupt_baseline_instead_of_ignoring(self):
        path = self.root / BASELINE_PATH
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text('{"schema":"pm-product-baseline-v1","product":{}}', encoding="utf-8")
        with self.assertRaises(FreshnessError):
            inspect(self.root, fetch=fake_fetch)

    def test_baseline_does_not_mutate_manager_integrity_or_bdi(self):
        before = sorted(p.relative_to(self.root).as_posix() for p in self.root.rglob("*") if p.is_file())
        write_baseline(self.root, evidence())
        after = sorted(p.relative_to(self.root).as_posix() for p in self.root.rglob("*") if p.is_file())
        self.assertEqual(after, sorted(before + [BASELINE_PATH]))
        data = json.loads((self.root / BASELINE_PATH).read_text(encoding="utf-8"))
        self.assertEqual(data["reconciliation"], "operator-confirmed")

    def test_release_pair_and_sha_are_validated(self):
        data = {
            "repository": REPOSITORY, "branch": "main", "head_sha": HEAD,
            "release_tag": "v1.0", "release_sha": None,
        }
        with self.assertRaises(FreshnessError):
            ProductEvidence.parse(data)
        data["release_sha"] = "not-a-sha"
        with self.assertRaises(FreshnessError):
            ProductEvidence.parse(data)

    def test_capture_refuses_without_explicit_reconciliation(self):
        with redirect_stderr(StringIO()):
            result = freshness_main(["capture", "--target", str(self.root)])
        self.assertEqual(result, 2)
        self.assertFalse((self.root / BASELINE_PATH).exists())

    def test_ready_strict_gate_cannot_reinstate_stale_product(self):
        with patch("installer.pmctl.inspect_product_freshness",
                   return_value=("STALE", ["new release published"], evidence())):
            with self.assertRaises(LifecycleGuardError):
                require_product_freshness(self.root)
        with patch("installer.pmctl.inspect_product_freshness",
                   return_value=("FRESH", [], evidence())):
            self.assertIsNone(require_product_freshness(self.root))

    def test_att51_regression_known_release_mismatch(self):
        # Regression for Oct 26: structural seal generation 33 was coherent
        # while the manager described v0.1.20 and GitHub published v0.1.23.
        old = evidence(tag="v0.1.20")
        live = evidence(tag="v0.1.23", release=NEW_RELEASE_SHA)
        status, _ = compare_product(REPOSITORY, "main", old, live)
        self.assertEqual(status, "STALE")


if __name__ == "__main__":
    unittest.main()
