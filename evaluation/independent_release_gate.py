"""Measure a frozen, hand-authored synthetic fixture against normal model processing."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from sheild.engine import load_model, run_pipeline
from sheild.verify import verify

FIXTURE = ROOT / "evaluation" / "data" / "release_gate_independent_v1.json"
FHIR_SCHEMA = ROOT / "tests" / "fixtures" / "fhir-r4.schema.json"


def _fhir_validation(bundle: dict) -> dict:
    import jsonschema

    schema = json.loads(FHIR_SCHEMA.read_text(encoding="utf-8"))
    validator = jsonschema.Draft6Validator({**schema, "$ref": "#/definitions/Bundle"})
    errors = list(validator.iter_errors(bundle))
    resources = {
        (entry["resource"]["resourceType"], entry["resource"]["id"]): entry["resource"]
        for entry in bundle.get("entry", [])
    }
    patient_ids = {key[1] for key in resources if key[0] == "Patient"}
    references_checked = 0
    references_consistent = True
    for (resource_type, _), resource in resources.items():
        if resource_type in {"Encounter", "Observation", "MedicationRequest", "RelatedPerson"}:
            owner = resource.get("subject") or resource.get("patient")
            references_checked += 1
            references_consistent &= bool(
                owner and owner.get("reference", "").split("/")[-1] in patient_ids
            )
        if resource.get("encounter"):
            encounter_id = resource["encounter"]["reference"].split("/")[-1]
            references_checked += 1
            references_consistent &= ("Encounter", encounter_id) in resources
    durations = []
    for (resource_type, _), resource in resources.items():
        if resource_type == "Encounter":
            period = resource["period"]
            start = datetime.fromisoformat(period["start"].replace("Z", "+00:00"))
            end = datetime.fromisoformat(period["end"].replace("Z", "+00:00"))
            durations.append((end - start).total_seconds())
    return {
        "schema_errors": len(errors),
        "patient_resources": len(patient_ids),
        "shared_practitioners": sum(key[0] == "Practitioner" for key in resources),
        "references_checked": references_checked,
        "references_consistent": bool(references_consistent),
        "encounter_duration_seconds": sorted(durations),
        "valid": not errors and bool(references_consistent),
    }


def _clinical_probe_preserved(surface: str, text: str) -> bool:
    interval = re.fullmatch(r"(\d{4}-\d{2}-\d{2}) to (\d{4}-\d{2}-\d{2})", surface)
    if interval:
        expected_days = (
            datetime.fromisoformat(interval.group(2)) - datetime.fromisoformat(interval.group(1))
        ).days
        dates = [
            datetime.fromisoformat(value)
            for value in re.findall(r"\d{4}-\d{2}-\d{2}", text)
        ]
        return any((end - start).days == expected_days for start, end in zip(dates, dates[1:]))
    return surface.casefold() in text.casefold()


def evaluate(fixture_path: Path = FIXTURE) -> dict:
    fixture_bytes = fixture_path.read_bytes()
    fixture = json.loads(fixture_bytes)
    records = fixture["records"]
    entries = [(item["file"], item["content"].encode("utf-8")) for item in records]
    model = load_model(required=True)
    artifacts: dict[str, bytes] = {}
    report, documents = run_pipeline(
        entries, artifacts, "independent-release-gate-v1-synthetic", model
    )
    verification = verify(entries, artifacts, documents)

    files_by_hash = {
        item["input_sha256"]: item.get("output")
        for item in report.get("files", [])
    }
    output_for_input = {
        item["file"]: files_by_hash.get(hashlib.sha256(item["content"].encode("utf-8")).hexdigest())
        for item in records
    }
    output_by_name = {
        path: artifacts[path].decode("utf-8", errors="replace")
        for path in output_for_input.values()
        if path and path in artifacts
    }
    all_artifacts = b"\n".join(artifacts.values()) + "\n".join(artifacts).encode("utf-8")
    all_text = all_artifacts.decode("utf-8", errors="replace").casefold()

    pii_total = pii_leaked = clinical_total = clinical_preserved = 0
    interval_total = interval_preserved = 0
    per_file = []
    for item in records:
        output_path = output_for_input[item["file"]]
        text = output_by_name.get(output_path or "", "")
        leaked = [surface for surface in item["pii"] if surface.casefold() in all_text]
        lost = [surface for surface in item["clinical"] if not _clinical_probe_preserved(surface, text)]
        intervals = [
            surface for surface in item["clinical"]
            if re.fullmatch(r"\d{4}-\d{2}-\d{2} to \d{4}-\d{2}-\d{2}", surface)
        ]
        pii_total += len(item["pii"])
        pii_leaked += len(leaked)
        clinical_total += len(item["clinical"])
        clinical_preserved += len(item["clinical"]) - len(lost)
        interval_total += len(intervals)
        interval_preserved += sum(
            _clinical_probe_preserved(surface, text) for surface in intervals
        )
        per_file.append({
            "file": item["file"],
            "status": "sanitized" if output_path else "quarantined",
            "pii_surfaces": len(item["pii"]),
            "pii_leaked": len(leaked),
            "leaked_surfaces": leaked,
            "clinical_probes": len(item["clinical"]),
            "clinical_preserved": len(item["clinical"]) - len(lost),
            "clinical_misses": lost,
        })

    output_rows = [
        json.loads(line)
        for line in artifacts.get("records.jsonl", b"").decode("utf-8").splitlines()
        if line.strip()
    ]
    expected_specs = []
    for item in records:
        output_path = output_for_input[item["file"]]
        if item.get("expected_patient"):
            expected_specs.append((output_path, None, item["expected_patient"]))
        for location, patient in item.get("expected_patients_by_loc", {}).items():
            expected_specs.append((output_path, location, patient))
    linkage = []
    for output_path, location, expected in expected_specs:
        matches = [
            row for row in output_rows
            if output_path and row["file"] == output_path
            and (location is None or row["loc"] == location)
        ]
        if matches:
            linkage.extend((expected, row.get("patient")) for row in matches)
        else:
            linkage.append((expected, None))
    true_positive = false_positive = false_negative = 0
    for index, (expected_a, actual_a) in enumerate(linkage):
        for expected_b, actual_b in linkage[index + 1:]:
            if expected_a == expected_b:
                if actual_a and actual_a == actual_b:
                    true_positive += 1
                else:
                    false_negative += 1
            elif actual_a and actual_a == actual_b:
                false_positive += 1
    fhir_input = next(
        (item for item in records if item["file"] == "two_patient_bundle.json"), None
    )
    fhir_output = output_for_input[fhir_input["file"]] if fhir_input else None
    if fhir_input and fhir_output:
        fhir = _fhir_validation(json.loads(artifacts[fhir_output]))
        source_fhir = _fhir_validation(json.loads(fhir_input["content"]))
        fhir["applicable"] = True
        fhir["source_encounter_duration_seconds"] = source_fhir["encounter_duration_seconds"]
        fhir["encounter_durations_preserved"] = (
            fhir["encounter_duration_seconds"] == source_fhir["encounter_duration_seconds"]
        )
        fhir["valid"] &= fhir["encounter_durations_preserved"]
    else:
        fhir = {"applicable": fhir_input is not None, "valid": False if fhir_input else None,
                "reason": "FHIR fixture was quarantined" if fhir_input else "not included"}
    input_count = len(entries)
    sanitized_count = report["counts"]["files_sanitized"]
    quarantined_count = report["counts"]["files_quarantined"]
    return {
        "scope": fixture["scope"],
        "fixture_sha256": hashlib.sha256(fixture_bytes).hexdigest(),
        "model_active": model is not None,
        "contract_valid": verification.get("contractValid") is True,
        "release_approved": verification.get("approved") is True,
        "verification_checks": verification.get("checks", {}),
        "verification_findings": verification.get("findings", {}),
        "file_accounting": {
            "input": input_count,
            "sanitized": sanitized_count,
            "quarantined": quarantined_count,
            "balanced": input_count == sanitized_count + quarantined_count,
        },
        "pii": {
            "leaked": pii_leaked,
            "tested": pii_total,
            "recall": (pii_total - pii_leaked) / pii_total if pii_total else None,
        },
        "clinical": {
            "preserved": clinical_preserved,
            "tested": clinical_total,
            "preservation": clinical_preserved / clinical_total if clinical_total else None,
            "intervals_preserved": interval_preserved,
            "intervals_tested": interval_total,
        },
        "linkage": {
            "evaluable_records": len(linkage),
            "expected_records": len(expected_specs),
            "mapping_coverage": len(linkage) / len(expected_specs) if expected_specs else None,
            "true_positive_pairs": true_positive,
            "false_positive_pairs": false_positive,
            "false_negative_pairs": false_negative,
            "precision": true_positive / (true_positive + false_positive)
            if true_positive + false_positive else None,
            "recall": true_positive / (true_positive + false_negative)
            if true_positive + false_negative else None,
        },
        "fhir": fhir,
        "per_file": per_file,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--fixture", type=Path, default=FIXTURE)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = json.dumps(evaluate(args.fixture), ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(result, encoding="utf-8")
    sys.stdout.reconfigure(encoding="utf-8")
    print(result, end="")


if __name__ == "__main__":
    main()
