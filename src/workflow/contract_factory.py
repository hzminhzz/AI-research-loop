"""Versioned, provenance-preserving Warden research contract compiler.

Scientific policy lives here, not in an LLM prompt. This factory may derive a
NEW contract from an existing pinned exploratory dataset for a genuinely
different evaluation horizon. It never rewrites a registered contract, fabricates
market data, changes a split to improve results, lowers costs, or opens a holdout.

A proposal is not an activated Warden contract. To activate, an operator with
explicit delegated authority must write the files and use Warden's independent
manifest approval/signing process. The factory never signs its own manifest.
"""
from __future__ import annotations

import hashlib
import json
import math
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import pyarrow.parquet as pq
import yaml
from pydantic import BaseModel, ConfigDict, Field, HttpUrl, field_validator

ALLOWED_PARENT_IDS = frozenset({
    "CRYPTO_PERPS_TOP100_1H_V1",
    "CRYPTO_PERPS_1H_V2",
    "CRYPTO_PERPS_5M_V1",
    "CRYPTO_PERPS_4H_V1",
    "CRYPTO_PERPS_1D_V1",
    "INDICES_5M_V1",
    "INDICES_1H_V2",
    "INDICES_30M_V1",
    "FX_MAJORS_1H_V1",
    "FX_MAJORS_5M_V1",
    "FX_MAJORS_1D_V1",
})
REQUIRED_COLUMNS = ("timestamp", "asset", "open", "high", "low", "close", "volume")
MANDATORY_COST_KEYS = ("taker_fee_bps", "slippage_bps")
APPROVED_CURRENCIES = ("crypto_perps", "indices", "fx")


class ContractBlocked(ValueError):
    """A contract cannot be proposed or activated without bypassing governance."""


class ContractRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    parent_contract_id: str = Field(min_length=8, max_length=80)
    research_family: str = Field(pattern=r"^[a-z][a-z0-9_]{2,43}$")
    label_horizon_bars: int = Field(ge=1, le=1440)
    expected_holding_bars: int = Field(ge=1, le=1440)
    source_url: HttpUrl
    source_published_at: datetime
    source_captured_at: datetime
    source_revision_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    reason_for_new_contract: str = Field(min_length=50, max_length=500)
    min_taker_fee_bps: float = Field(ge=0, le=100)
    min_slippage_bps: float = Field(ge=0, le=100)
    requires_quote_data: bool = False
    requires_open_interest: bool = False
    requires_funding: bool = False

    @field_validator("source_published_at", "source_captured_at")
    @classmethod
    def require_tz(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            raise ValueError("source timestamps must be explicitly timezone aware")
        return value

    @field_validator("parent_contract_id")
    @classmethod
    def allow_parent(cls, value: str) -> str:
        if value not in ALLOWED_PARENT_IDS:
            raise ValueError("parent must be an approved existing Warden contract")
        return value


@dataclass(frozen=True)
class ContractProposal:
    contract_id: str
    contract_yaml: str
    manifest_json: str
    provenance_json: str
    parent_contract_id: str
    snapshot_sha256: str
    selection_group: str
    requires_manifest_approval: bool
    source_after_validation: bool
    parent_selection_attempts: int

    def as_dict(self) -> dict:
        return {
            "contract_id": self.contract_id,
            "contract": yaml.safe_load(self.contract_yaml),
            "manifest": json.loads(self.manifest_json),
            "provenance": json.loads(self.provenance_json),
            "parent_contract_id": self.parent_contract_id,
            "snapshot_sha256": self.snapshot_sha256,
            "selection_group": self.selection_group,
            "requires_manifest_approval": self.requires_manifest_approval,
            "source_after_validation": self.source_after_validation,
            "parent_selection_attempts": self.parent_selection_attempts,
        }


def _file_hash(file: Path) -> str:
    digest = hashlib.sha256()
    with file.open("rb") as stream:
        for block in iter(lambda: stream.read(8 * 1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _relative_path(root: Path, raw: str) -> Path:
    rel = Path(raw)
    if rel.is_absolute() or ".." in rel.parts or not rel.parts:
        raise ContractBlocked("dataset must have a safe repository-relative path")
    file = (root / rel).resolve()
    if not file.is_relative_to(root.resolve()):
        raise ContractBlocked("dataset escapes the authorized research repository")
    return file


def assert_existing_manifest_unchanged(repo: Path) -> dict:
    """Pin *all* previously governed files, not just the selected parent.

    Existing protected files might be Git-dirty for legitimate reasons.
    They must match the already approved Warden hashes: an agent cannot
    opportunistically re-sign unrelated edits while adding a contract.
    """
    root = repo.resolve()
    manifest = root / ".warden_manifest.sha256"
    if not manifest.is_file():
        raise ContractBlocked("Missing approved Warden manifest")
    old = {}
    for line in manifest.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        expected, rel = line.split(maxsplit=1)
        path = _relative_path(root, rel)
        if not path.is_file() or _file_hash(path) != expected:
            raise ContractBlocked(f"Previously approved file changed: {rel}")
        if rel in old:
            raise ContractBlocked("Duplicate Warden manifest entry")
        old[rel] = expected
    return old


def _market_schema_ok(path: Path, expect_funding: bool) -> dict:
    meta = pq.read_metadata(path)
    names = set(meta.schema.names)
    missing = set(REQUIRED_COLUMNS) - names
    if missing:
        raise ContractBlocked(f"Market snapshot missing required columns: {sorted(missing)}")
    if expect_funding and "funding_rate" not in names:
        raise ContractBlocked("Perpetual contract missing settlement funding observations")
    if meta.num_rows <= 0:
        raise ContractBlocked("Empty research dataset")
    return {"columns": sorted(names), "rows": meta.num_rows}


def _parse_time(value: Any) -> datetime:
    dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    if dt.tzinfo is None:
        raise ContractBlocked("Naive Warden split timestamp")
    return dt


def _selection_history(repo: Path, parent: dict, snapshot_sha: str) -> int:
    """Count related historical selection attempts across *all* contract IDs.

    This is a non-qualification informational floor. Warden still owns the
    authoritative registry and contract-wide DSR; new contracts may NOT
    independently claim to reset selection statistics.
    """
    import sqlite3

    db = repo / "registry/registry.db"
    if not db.exists():
        return 0
    connection = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    try:
        # Same snapshot, market, frequency, and evaluation interval share a
        # research family even if their label horizon and contract ID differ.
        ids = {parent["contract_id"]}
        for path in (repo / "contracts").glob("*.yaml"):
            try:
                item = yaml.safe_load(path.read_text(encoding="utf-8"))
                if (item.get("data_snapshot_sha256") == snapshot_sha
                        and item.get("asset_class") == parent["asset_class"]
                        and item.get("frequency") == parent["frequency"]
                        and item.get("val_start") == parent["val_start"]
                        and item.get("val_end") == parent["val_end"]):
                    ids.add(item["contract_id"])
            except (OSError, ValueError, yaml.YAMLError, AttributeError):
                continue
        args = ",".join("?" for _ in ids)
        return int(connection.execute(
            f"SELECT COUNT(*) FROM selection_attempts WHERE contract_id IN ({args})",
            sorted(ids),
        ).fetchone()[0])
    finally:
        connection.close()


def propose_contract(repo: Path, request: ContractRequest) -> ContractProposal:
    root = repo.resolve()
    old = assert_existing_manifest_unchanged(root)
    path = root / "contracts" / f"{request.parent_contract_id.lower()}.yaml"
    if not path.is_file():
        raise ContractBlocked("Exact parent Warden YAML unavailable")
    parent = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(parent, dict) or parent.get("contract_id") != request.parent_contract_id:
        raise ContractBlocked("Parent contract identity mismatch")
    if parent.get("asset_class") not in APPROVED_CURRENCIES:
        raise ContractBlocked("Parent market not approved for autonomous research")
    if parent.get("execution_mode") != "NEXT_BAR" or parent.get("execution_delay_bars", 0) < 1:
        raise ContractBlocked("Automated contract creation requires next-bar execution lag")
    manifest_file = root / "contracts/datasets" / f"{request.parent_contract_id}.json"
    if not manifest_file.is_file():
        raise ContractBlocked("Missing source dataset manifest")
    manifest = json.loads(manifest_file.read_text(encoding="utf-8"))
    if parent.get("data_provenance") != "verified_market" or manifest.get("provenance") != "verified_market":
        raise ContractBlocked("Dataset origin must be verified_market")
    dataset = parent.get("exploratory_data_path")
    if dataset != manifest.get("path"):
        raise ContractBlocked("Dataset path does not match pinned manifest")
    if not str(dataset).startswith("data/exploratory/"):
        raise ContractBlocked("Exploratory path must stay in data/exploratory")
    file = _relative_path(root, dataset)
    if not file.is_file():
        raise ContractBlocked("Exploratory data snapshot unavailable")
    digest = _file_hash(file)
    if parent.get("data_snapshot_sha256") != digest or manifest.get("sha256") != digest:
        raise ContractBlocked("Dataset hash drift from parent contract")
    if request.requires_quote_data:
        raise ContractBlocked("No verified bid/ask or order-book evidence")
    if request.requires_open_interest:
        raise ContractBlocked("No historical open interest in pinned data")
    _market_schema_ok(file, request.requires_funding or parent["asset_class"] == "crypto_perps")

    val_start = _parse_time(parent["val_start"])
    val_end = _parse_time(parent["val_end"])
    days = (val_end - val_start).total_seconds() / 86400
    bars_per_day = {"1m": 1440, "5m": 288, "15m": 96, "30m": 48,
                    "1h": 24, "4h": 6, "1d": 1}.get(parent["frequency"])
    if bars_per_day is None:
        raise ContractBlocked("Unrecognized parent frequency")
    validation_bars = days * bars_per_day
    # An entire fold must have enough observations for several label spans,
    # otherwise alleged OOS folds are nearly all overlapping horizon.
    if validation_bars / int(parent["n_folds"]) < 3 * request.label_horizon_bars:
        raise ContractBlocked(
            "Validation fold too short for strategy label horizon; "
            "requires new, approved PIT dataset/split rather than shortening labels"
        )
    if request.expected_holding_bars > request.label_horizon_bars * 3:
        raise ContractBlocked("Label horizon materially shorter than intended holding period")

    old_label = int(parent["label_horizon_bars"])
    old_embargo = int(parent["embargo_bars"])
    new_label = max(old_label, request.label_horizon_bars)
    new_embargo = max(old_embargo, new_label)
    new_fee = max(float(parent["taker_fee_bps"]), request.min_taker_fee_bps)
    new_slip = max(float(parent["slippage_bps"]), request.min_slippage_bps)
    if (new_label, new_embargo, new_fee, new_slip) == (
        old_label, old_embargo, float(parent["taker_fee_bps"]),
        float(parent["slippage_bps"]),
    ):
        raise ContractBlocked("Existing approved contract already provides required semantics")

    suffix = (f"H{new_label}_E{new_embargo}"
              f"_F{int(new_fee * 10)}_S{int(new_slip * 10)}")
    new_id = f"AUTO_{request.parent_contract_id}_{suffix}_V1"
    if len(new_id) > 116 or not re.fullmatch(r"[A-Z0-9_]+", new_id):
        raise ContractBlocked("Derived Warden contract ID invalid")
    target_contract = root / "contracts" / f"{new_id.lower()}.yaml"
    target_manifest = root / "contracts/datasets" / f"{new_id}.json"
    if target_contract.exists() or target_manifest.exists():
        raise ContractBlocked("Derived contract already exists; immutable records cannot be rewritten")

    item = dict(parent)
    item.update({
        "contract_id": new_id,
        "label_horizon_bars": new_label,
        "embargo_bars": new_embargo,
        "taker_fee_bps": new_fee,
        "slippage_bps": new_slip,
    })
    # Preserve exact source dataset/splits and never open or copy holdout.
    assert item["train_start"] == parent["train_start"]
    assert item["val_start"] == parent["val_start"]
    assert item["val_end"] == parent["val_end"]
    assert item["holdout_start"] == parent["holdout_start"]
    assert item["holdout_data_path"] == parent["holdout_data_path"]

    selection_group = hashlib.sha256(json.dumps({
        "snapshot": digest,
        "asset_class": parent["asset_class"],
        "frequency": parent["frequency"],
        "validation_start": str(parent["val_start"]),
        "validation_end": str(parent["val_end"]),
    }, sort_keys=True).encode()).hexdigest()
    historical = _selection_history(root, parent, digest)
    meta = {
        "contract_id": new_id,
        "path": dataset,
        "sha256": digest,
        "provenance": "verified_market",
        "source": manifest.get("source"),
        "pipeline": manifest.get("pipeline"),
        "parent_contract_id": request.parent_contract_id,
        "parent_dataset_manifest_sha256": _file_hash(manifest_file),
        "derivation": "no new data; same original independently pinned exploratory bytes",
        "selection_group": selection_group,
        "prior_related_selection_attempts_at_proposal": historical,
        "bias_notice": "Research contracts sharing a dataset/validation period are NOT independent trials",
    }
    evidence = {
        "parent_contract_id": request.parent_contract_id,
        "contract_id": new_id,
        "market_data_sha256": digest,
        "selection_group": selection_group,
        "source_url": str(request.source_url),
        "source_text_sha256": request.source_revision_sha256,
        "source_published_at": request.source_published_at.isoformat(),
        "source_captured_at": request.source_captured_at.isoformat(),
        "strategy_family": request.research_family,
        "expected_holding_bars": request.expected_holding_bars,
        "label_horizon_bars": new_label,
        "embargo_bars": new_embargo,
        "old_label_horizon_bars": old_label,
        "old_embargo_bars": old_embargo,
        "old_costs_bps": {
            k: float(parent[k]) for k in MANDATORY_COST_KEYS
        },
        "new_costs_bps": {
            k: float(item[k]) for k in MANDATORY_COST_KEYS
        },
        "reason": request.reason_for_new_contract,
        "retrospective_source": request.source_published_at >= val_end,
        "prior_related_selection_attempts": historical,
        "existing_manifest_entries_checked": len(old),
        "holdout_accessed": False,
        "state": "PROPOSED_REQUIRES_WARDEN_MANIFEST_APPROVAL",
    }
    return ContractProposal(
        contract_id=new_id,
        contract_yaml=yaml.safe_dump(item, sort_keys=False),
        manifest_json=json.dumps(meta, indent=2, sort_keys=True) + "\n",
        provenance_json=json.dumps(evidence, indent=2, sort_keys=True) + "\n",
        parent_contract_id=request.parent_contract_id,
        snapshot_sha256=digest,
        selection_group=selection_group,
        requires_manifest_approval=True,
        source_after_validation=bool(evidence["retrospective_source"]),
        parent_selection_attempts=historical,
    )

def activate_contract(
    repo: Path, request: ContractRequest, *,
    delegated_approval: str | None = None,
    max_auto_contracts: int = 8,
) -> dict:
    """Activate ONE new, semantically necessary research contract under a
    principal's explicitly delegated, bounded approval.

    Never used for arbitrary agent-authored YAML. The compiler verifies the
    original market snapshot and *all* previously pinned Warden files first.
    A manifest with an independent HMAC signature cannot be re-signed by
    this unsigned flow. Existing contract and registered trials are immutable.
    """
    import fcntl
    import os
    from datetime import timezone

    if delegated_approval != "principal-approved-2026-10-30-research-contracts":
        raise ContractBlocked("Missing explicit principal contract-creation delegation")
    if max_auto_contracts < 1 or max_auto_contracts > 8:
        raise ContractBlocked("Unbounded contract creation quota")
    root = repo.resolve()
    if (root / ".warden_manifest.sha256.sig").exists():
        raise ContractBlocked("Independent Warden signature exists: require human-held key signing path")
    audit_dir = root / ".workspace" / "research_contracts"
    audit_dir.mkdir(parents=True, exist_ok=True)
    fd = os.open(audit_dir / "activation.lock", os.O_RDWR | os.O_CREAT, 0o600)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX)
        existing = list((root / "contracts").glob("auto_*.yaml"))
        if len(existing) >= max_auto_contracts:
            raise ContractBlocked("Autonomous contract cap reached; new research must use prior contracts")
        # The prior manifest must not have drifted since its last approval.
        previous_entries = assert_existing_manifest_unchanged(root)
        proposal = propose_contract(root, request)
        contract_path = root / "contracts" / f"{proposal.contract_id.lower()}.yaml"
        manifest_path = root / "contracts/datasets" / f"{proposal.contract_id}.json"
        evidence_path = audit_dir / f"{proposal.contract_id}.json"
        if evidence_path.exists():
            raise ContractBlocked("Previous activation evidence already exists")
        old_manifest = (root / ".warden_manifest.sha256").read_bytes()
        meta_path = root / ".warden_manifest.sha256.meta.json"
        old_meta = meta_path.read_bytes() if meta_path.exists() else None
        created = []
        changed_manifest = False
        try:
            for path, content in (
                (contract_path, proposal.contract_yaml),
                (manifest_path, proposal.manifest_json),
            ):
                # Exclusive file creation prevents silent overwrite of a
                # concurrent agent's legitimate work.
                with path.open("x", encoding="utf-8") as handle:
                    handle.write(content)
                created.append(path)
            lines = [
                f"{_file_hash(path)}  {path.relative_to(root)}"
                for path in created
            ]
            new_manifest = old_manifest + ("\n".join(lines) + "\n").encode("utf-8")
            temp = (root / ".warden_manifest.sha256.pending")
            temp.write_bytes(new_manifest)
            temp.replace(root / ".warden_manifest.sha256")
            changed_manifest = True
            approval = {
                "mode": "bounded_principal_delegation_unsigned",
                "approver": "principal explicit 2026-10-30 authorization",
                "approved_at": datetime.now(timezone.utc).isoformat(),
                "manifest_sha256": hashlib.sha256(new_manifest).hexdigest(),
                "previous_manifest_sha256": hashlib.sha256(old_manifest).hexdigest(),
                "added_paths": [str(path.relative_to(root)) for path in created],
                "previous_manifest_entries_verified": len(previous_entries),
                "independent_signature": "none",
                "note": "Research contract creation delegated, never protected holdout unsealing or live execution",
            }
            meta_path.write_text(json.dumps(approval, indent=2) + "\n", encoding="utf-8")
            # All original hashes must remain unchanged; new files must be
            # explicitly pinned in the new manifest.
            latest = assert_existing_manifest_unchanged(root)
            if len(latest) != len(previous_entries) + 2:
                raise ContractBlocked("Manifest did not add exactly two research contract files")
            evidence = proposal.as_dict()
            evidence["activation"] = approval
            evidence["activation_status"] = "ENABLED_FOR_EXPLORATORY_WARDEN_USE"
            evidence_path.write_text(json.dumps(evidence, indent=2) + "\n", encoding="utf-8")
            return {
                "status": "ACTIVATED_DELEGATED_RESEARCH_CONTRACT",
                "contract_id": proposal.contract_id,
                "parent_contract_id": proposal.parent_contract_id,
                "selection_group": proposal.selection_group,
                "prior_related_selection_attempts": proposal.parent_selection_attempts,
                "holdout_accessed": False,
                "manifest_approval_mode": approval["mode"],
                "independent_signature": "none",
                "evidence_path": str(evidence_path.relative_to(root)),
            }
        except Exception:
            # Restore exactly the pre-read manifest and metadata only when
            # this invocation changed them; other dirty files are untouched.
            if changed_manifest:
                (root / ".warden_manifest.sha256").write_bytes(old_manifest)
                if old_meta is not None:
                    meta_path.write_bytes(old_meta)
                elif meta_path.exists():
                    meta_path.unlink()
            for path in created:
                path.unlink(missing_ok=True)
            raise
    finally:
        fcntl.flock(fd, fcntl.LOCK_UN)
        os.close(fd)





def find_compatible_contract(repo: Path, request: ContractRequest) -> str | None:
    """Reuse a governed contract rather than minting a fresh ID per hypothesis.

    Same immutable parent dataset, market, frequency and validation window.
    Never substitute a shorter purge, lower cost or different snapshot.
    """
    root = repo.resolve()
    assert_existing_manifest_unchanged(root)
    if request.requires_quote_data or request.requires_open_interest:
        raise ContractBlocked("Available data contracts do not provide order-book or open-interest fields")
    parent_file = root / "contracts" / (request.parent_contract_id.lower() + ".yaml")
    if not parent_file.is_file():
        raise ContractBlocked("Parent contract unavailable")
    parent = yaml.safe_load(parent_file.read_text(encoding="utf-8"))
    if request.requires_funding:
        source_file = _relative_path(root, parent["exploratory_data_path"])
        if "funding_rate" not in pq.read_metadata(source_file).schema.names:
            raise ContractBlocked("Required historical funding column missing")
    candidates = []
    for path in (root / "contracts").glob("*.yaml"):
        try:
            item = yaml.safe_load(path.read_text(encoding="utf-8"))
        except (yaml.YAMLError, OSError):
            continue
        if not isinstance(item, dict):
            continue
        if any(item.get(key) != parent.get(key) for key in (
            "asset_class", "frequency", "exploratory_data_path", "data_snapshot_sha256",
            "data_provenance", "val_start", "val_end", "holdout_start", "holdout_end",
            "execution_mode", "execution_delay_bars",
        )):
            continue
        if int(item.get("label_horizon_bars", 0)) < request.label_horizon_bars:
            continue
        if int(item.get("embargo_bars", 0)) < request.label_horizon_bars:
            continue
        if float(item.get("taker_fee_bps", 0)) < request.min_taker_fee_bps:
            continue
        if float(item.get("slippage_bps", 0)) < request.min_slippage_bps:
            continue
        # Match a corresponding, pinned source dataset manifest.
        manifest = root / "contracts/datasets" / f"{item['contract_id']}.json"
        if not manifest.is_file():
            continue
        m = json.loads(manifest.read_text(encoding="utf-8"))
        if m.get("sha256") != parent["data_snapshot_sha256"] or m.get("provenance") != "verified_market":
            continue
        candidates.append((
            int(item["label_horizon_bars"]) - request.label_horizon_bars,
            float(item["taker_fee_bps"]) - request.min_taker_fee_bps,
            item["contract_id"],
        ))
    if not candidates:
        return None
    return min(candidates)[2]


def main() -> None:
    """Safe CLI for the research supervisor; default is a dry-run proposal."""
    import argparse
    import os

    parser = argparse.ArgumentParser(
        description="Propose or, with bounded principal delegation, activate a Warden research contract"
    )
    parser.add_argument("--quant-lab", default="/home/quant/dev/quant-lab")
    parser.add_argument("--request-json", required=True, type=Path)
    parser.add_argument("--activate", action="store_true")
    options = parser.parse_args()
    try:
        req = ContractRequest.model_validate_json(options.request_json.read_text(encoding="utf-8"))
        if options.activate:
            out = activate_contract(
                Path(options.quant_lab), req,
                delegated_approval=os.environ.get("RESEARCH_CONTRACT_DELEGATION"),
            )
        else:
            out = {"status": "DRY_RUN_PROPOSAL", **propose_contract(
                Path(options.quant_lab), req,
            ).as_dict()}
        print(json.dumps(out, indent=2, allow_nan=False, default=str))
    except (ContractBlocked, OSError, ValueError) as exc:
        print(json.dumps({
            "status": "BLOCKED_CONTRACT_FACTORY",
            "reason": str(exc),
        }, indent=2))
        raise SystemExit(2)


if __name__ == "__main__":
    main()
