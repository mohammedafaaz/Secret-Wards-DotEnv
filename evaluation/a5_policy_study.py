"""Compare privacy-only policy candidates against the unchanged practice proxy."""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from evaluation import attack_arena
from sheild import engine
from sheild.verify import verify

KIT = ROOT / "Secret-Wards-ToolKit-main"
POLICIES = {
    "adaptive_baseline": {"age_width": None, "suppress_geography": False},
    "adaptive_and_suppress_geography": {"age_width": None, "suppress_geography": True},
    "age_width_40": {"age_width": 40, "suppress_geography": False},
    "age_width_80": {"age_width": 80, "suppress_geography": False},
    "age_width_40_and_suppress_geography": {"age_width": 40, "suppress_geography": True},
    "age_width_80_and_suppress_geography": {"age_width": 80, "suppress_geography": True},
    "selective_institutional_geography": {
        "age_width": None,
        "suppress_geography": False,
        "selective_geography_fields": ["state", "hospital", "hospitalname", "facility", "facilityname"],
    },
}
SUPPRESSED_GEOGRAPHY = {"district", "jila", "tehsil", "city", "state", "pin", "pincode", "hospital", "hospitalname", "facility", "facilityname", "village", "mohalla"}
NEW_GEOGRAPHY_FIELDS = {"district", "jila", "state", "hospital", "hospitalname", "facility", "facilityname"}


def _write_output(root: Path, artifacts: dict[str, bytes]) -> None:
    for name, contents in artifacts.items():
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(contents)


def _run_candidate(policy: dict, secret: str, root: Path, model) -> dict:
    old_linker_run = engine.Linker.run
    old_field_role = engine.field_role
    old_location_fields = engine.LOC
    widened_profiles = 0

    def candidate_linker_run(linker):
        nonlocal widened_profiles
        old_linker_run(linker)
        width = policy["age_width"]
        if width is not None:
            for record in linker.records:
                if record.evidence.ages:
                    record.width = width
                    widened_profiles += 1

    def candidate_field_role(key, parents=(), resource=""):
        normalized_key = engine.nk(key)
        if normalized_key in policy.get("selective_geography_fields", set()):
            return "location"
        if policy["suppress_geography"] and normalized_key in SUPPRESSED_GEOGRAPHY:
            if resource in ("Practitioner", "Organization") and engine.nk(key) == "name":
                return "clinical"
            return "location"
        return old_field_role(key, parents, resource)

    try:
        if not policy["suppress_geography"]:
            engine.LOC = old_location_fields - NEW_GEOGRAPHY_FIELDS
        engine.Linker.run = candidate_linker_run
        engine.field_role = candidate_field_role
        entries = list(engine.directory_entries(KIT / "dev" / "input"))
        artifacts: dict[str, bytes] = {}
        report, documents = engine.run_pipeline(entries, artifacts, secret, model)
        verification = verify(entries, artifacts, documents)
        if verification.get("contractValid") is not True:
            raise RuntimeError("candidate_output_contract_failed")
        _write_output(root, artifacts)
        return {
            "verification_approved": verification.get("approved"),
            "verification_findings": verification.get("findings"),
            "counts": report["counts"],
            "entities": report["entities"],
            "timing": report["timing"],
            "resources": report["resources"],
            "risk_proxy": report["risk_proxy"],
            "age_profiles_widened": widened_profiles,
            "artifacts": artifacts,
        }
    finally:
        engine.Linker.run = old_linker_run
        engine.field_role = old_field_role
        engine.LOC = old_location_fields


def _practice_metrics(output: Path) -> dict:
    completed = subprocess.run(
        [sys.executable, str(KIT / "check_dev.py"), "--output", str(output)],
        cwd=KIT,
        capture_output=True,
        text=True,
        check=True,
    )
    patterns = {
        "personal_data": r"PERSONAL DATA: (\d+) of (\d+) pieces still visible",
        "canaries": r"CANARIES: (\d+) of (\d+) planted canaries found",
        "medical": r"MEDICAL DATA KEPT: (\d+) of (\d+) medical values survived",
        "linkage": r"PATIENT LINKING: precision ([\d.]+), recall ([\d.]+).*?wrongly merge different people: (\d+)",
        "raw_copies": r"RAW COPIES: (\d+) broken/unsupported files were copied out unchanged",
    }
    values = {}
    for key, pattern in patterns.items():
        match = re.search(pattern, completed.stdout)
        if not match:
            raise RuntimeError(f"practice_metric_missing:{key}")
        values[key] = list(match.groups())
    return {
        "personal_data_leaks": int(values["personal_data"][0]),
        "personal_data_tested": int(values["personal_data"][1]),
        "canary_leaks": int(values["canaries"][0]),
        "canaries_tested": int(values["canaries"][1]),
        "medical_preserved": int(values["medical"][0]),
        "medical_tested": int(values["medical"][1]),
        "linkage_precision": float(values["linkage"][0]),
        "linkage_recall": float(values["linkage"][1]),
        "false_merges": int(values["linkage"][2]),
        "raw_copies": int(values["raw_copies"][0]),
    }


def study() -> dict:
    if not (KIT / "dev" / "truth" / "truth.json").is_file():
        raise FileNotFoundError("organizer_practice_truth_unavailable")
    model = engine.load_model(required=True)
    results = {}
    with tempfile.TemporaryDirectory(prefix="shield-a5-study-") as work:
        root = Path(work)
        for name, policy in POLICIES.items():
            primary = root / name / "primary"
            rotated = root / name / "rotated"
            primary.mkdir(parents=True)
            rotated.mkdir(parents=True)
            first = _run_candidate(policy, "synthetic-a5-study-primary", primary, model)
            second = _run_candidate(policy, "synthetic-a5-study-rotated", rotated, model)
            attacks = attack_arena.run(KIT, primary, rotated)
            results[name] = {
                "policy": policy,
                "primary_contract": first["verification_approved"],
                "primary_findings": first["verification_findings"],
                "input_files": first["counts"]["files_total"],
                "files_sanitized": first["counts"]["files_sanitized"],
                "files_quarantined": first["counts"]["files_quarantined"],
                "practice_utility": _practice_metrics(primary),
                "age_profiles_widened": first["age_profiles_widened"],
                "privacy_transform_counts": first["entities"],
                "timing": first["timing"],
                "resources": first["resources"],
                "normalized_attack_proxy": attacks["normalized"],
                "targeted_attack_proxy": attacks["sanitized"]["A5_targeted_mean_probability"],
                "date_shift_stability": attacks["sanitized"]["A7_stable_date_position_share"],
                "pseudonym_stability": attacks["sanitized"]["A7_stable_record_pseudonym_share"],
                "rotated_secret_changes_pseudonyms": attacks["sanitized"]["A7_stable_record_pseudonym_share"] < 1.0,
                "attack_metrics": attacks["sanitized"],
                "secondary_contract": second["verification_approved"],
            }
    return {
        "scope": "unchanged synthetic practice set and unchanged local A1-A7 approximation; not organizer hidden-attack scores",
        "policy_utility": "internal release verification and output accounting; widening/suppressing age and geography changes quasi-identifiers only; this study does not establish full clinical utility",
        "results": results,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = json.dumps(study(), indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(result + "\n", encoding="utf-8")
        print(f"wrote {args.output}")
    else:
        sys.stdout.reconfigure(encoding="utf-8")
        print(result)


if __name__ == "__main__":
    main()
