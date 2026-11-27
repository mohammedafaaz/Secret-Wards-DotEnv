import json
from datetime import datetime
from functools import lru_cache
from pathlib import Path

import jsonschema

from sheild.engine import run_pipeline
from sheild.verify import verify

FHIR_R4_SCHEMA = Path(__file__).parent / "fixtures" / "fhir-r4.schema.json"


@lru_cache(maxsize=1)
def _bundle_validator():
    schema = json.loads(FHIR_R4_SCHEMA.read_text(encoding="utf-8"))
    jsonschema.Draft6Validator.check_schema(schema)
    return jsonschema.Draft6Validator({**schema, "$ref": "#/definitions/Bundle"})


def _assert_fhir_r4(bundle):
    errors = list(_bundle_validator().iter_errors(bundle))
    assert not errors, "\n".join(f"{error.json_path}: {error.message}" for error in errors)


def _entry(index, resource):
    return {
        "fullUrl": f"urn:uuid:00000000-0000-4000-8000-{index:012d}",
        "resource": resource,
    }


def _bundle():
    entries = [
        _entry(1, {"resourceType": "Patient", "id": "p1", "name": [{"text": "Synthetic Alpha"}], "birthDate": "1980-01-02"}),
        _entry(2, {"resourceType": "Patient", "id": "p2", "name": [{"text": "Synthetic Beta"}], "birthDate": "1970-02-03"}),
        _entry(3, {"resourceType": "Organization", "id": "org", "name": "Synthetic Hospital"}),
        _entry(4, {"resourceType": "Practitioner", "id": "prac", "name": [{"text": "Dr. Synthetic Clinician"}]}),
    ]
    for patient, suffix, start, end, value in (
        ("p1", "1", "2026-03-01T10:00:00Z", "2026-03-01T14:00:00Z", 72),
        ("p2", "2", "2026-04-02T11:00:00Z", "2026-04-02T17:00:00Z", 81),
    ):
        encounter_id = f"e{suffix}"
        observation_id = f"o{suffix}"
        entries.extend([
            _entry(10 + int(suffix), {
                "resourceType": "Encounter",
                "id": encounter_id,
                "status": "finished",
                "class": {"system": "http://terminology.hl7.org/CodeSystem/v3-ActCode", "code": "AMB"},
                "subject": {"reference": f"Patient/{patient}"},
                "serviceProvider": {"reference": "Organization/org"},
                "participant": [{"individual": {"reference": "Practitioner/prac"}}],
                "period": {"start": start, "end": end},
            }),
            _entry(20 + int(suffix), {
                "resourceType": "Observation",
                "id": observation_id,
                "status": "final",
                "code": {"text": "Pulse"},
                "subject": {"reference": f"Patient/{patient}"},
                "encounter": {"reference": f"Encounter/{encounter_id}"},
                "performer": [{"reference": "#lab"}],
                "contained": [{"resourceType": "Organization", "id": "lab", "name": "Synthetic Lab"}],
                "valueQuantity": {"value": value, "unit": "beats/min"},
            }),
            _entry(30 + int(suffix), {
                "resourceType": "MedicationRequest",
                "id": f"m{suffix}",
                "status": "active",
                "intent": "order",
                "medicationCodeableConcept": {"text": "Metformin 500 mg"},
                "subject": {"reference": f"Patient/{patient}"},
                "encounter": {"reference": f"Encounter/{encounter_id}"},
                "requester": {"reference": "Practitioner/prac"},
                "dosageInstruction": [{"text": "500 mg twice daily"}],
            }),
            _entry(40 + int(suffix), {
                "resourceType": "DiagnosticReport",
                "id": f"d{suffix}",
                "status": "final",
                "code": {"text": "Routine panel"},
                "subject": {"reference": f"Patient/{patient}"},
                "encounter": {"reference": f"Encounter/{encounter_id}"},
                "performer": [{"reference": "Practitioner/prac"}],
                "result": [{"reference": f"Observation/{observation_id}"}],
            }),
        ])
    entries.append(_entry(50, {
        "resourceType": "RelatedPerson",
        "id": "rp1",
        "patient": {"reference": "Patient/p1"},
        "name": [{"text": "Synthetic Relative"}],
    }))
    return {"resourceType": "Bundle", "type": "collection", "entry": entries}


def test_multi_patient_bundle_is_independently_validated_and_references_stay_owned():
    source = _bundle()
    _assert_fhir_r4(source)
    raw = json.dumps(source).encode()
    output = {}
    report, documents = run_pipeline([("multi.fhir.json", raw)], output, "fhir-r4-validator-secret", None)
    result = verify([("multi.fhir.json", raw)], output, documents)
    assert result["contractValid"] is True
    sanitized = json.loads(output[documents[0].output])
    _assert_fhir_r4(sanitized)

    resources = {
        (entry["resource"]["resourceType"], entry["resource"]["id"]): entry["resource"]
        for entry in sanitized["entry"]
    }
    patient_ids = {
        resource["id"]
        for (resource_type, _), resource in resources.items()
        if resource_type == "Patient"
    }
    assert len(patient_ids) == 2
    ids_by_type = {
        resource_type: {resource_id for kind, resource_id in resources if kind == resource_type}
        for resource_type in {kind for kind, _ in resources}
    }
    observations = [resource for (resource_type, _), resource in resources.items() if resource_type == "Observation"]
    reports = [resource for (resource_type, _), resource in resources.items() if resource_type == "DiagnosticReport"]
    assert {resource["valueQuantity"]["value"] for resource in observations} == {72, 81}
    assert len(reports) == 2
    for report_resource in reports:
        observation_id = report_resource["result"][0]["reference"].split("/")[-1]
        observation = resources[("Observation", observation_id)]
        assert observation["subject"]["reference"] == report_resource["subject"]["reference"]
    for (resource_type, _), resource in resources.items():
        if resource_type in {"Encounter", "Observation", "MedicationRequest", "DiagnosticReport", "RelatedPerson"}:
            subject = resource.get("subject") or resource.get("patient")
            assert subject["reference"].split("/")[-1] in patient_ids
        if resource.get("encounter"):
            assert resource["encounter"]["reference"].split("/")[-1] in ids_by_type["Encounter"]
    for resource in (value for (kind, _), value in resources.items() if kind == "Encounter"):
        assert resource["serviceProvider"]["reference"].split("/")[-1] in ids_by_type["Organization"]
        assert resource["participant"][0]["individual"]["reference"].split("/")[-1] in ids_by_type["Practitioner"]
    for resource in (value for (kind, _), value in resources.items() if kind == "MedicationRequest"):
        assert resource["requester"]["reference"].split("/")[-1] in ids_by_type["Practitioner"]
        assert resource["medicationCodeableConcept"]["text"] == "Metformin 500 mg"
        assert resource["dosageInstruction"][0]["text"] == "500 mg twice daily"
    for resource in reports:
        assert resource["performer"][0]["reference"].split("/")[-1] in ids_by_type["Practitioner"]
        assert resource["result"][0]["reference"].split("/")[-1] in ids_by_type["Observation"]
    organizations = [resource for (resource_type, _), resource in resources.items() if resource_type == "Organization"]
    practitioners = [resource for (resource_type, _), resource in resources.items() if resource_type == "Practitioner"]
    assert len(organizations) == 1 and organizations[0]["name"] == "Synthetic Hospital"
    assert len(practitioners) == 1 and practitioners[0]["name"][0]["text"] == "Dr. Synthetic Clinician"
    assert all(resource["performer"][0]["reference"] == "#" + resource["contained"][0]["id"] for resource in observations)
    assert all(resource["contained"][0]["name"] == "Synthetic Lab" for resource in observations)

    source_intervals = [(datetime.fromisoformat(item[0]), datetime.fromisoformat(item[1])) for item in (
        ("2026-03-01T10:00:00+00:00", "2026-03-01T14:00:00+00:00"),
        ("2026-04-02T11:00:00+00:00", "2026-04-02T17:00:00+00:00"),
    )]
    output_intervals = []
    for (resource_type, _), resource in resources.items():
        if resource_type == "Encounter":
            period = resource["period"]
            output_intervals.append((datetime.fromisoformat(period["start"].replace("Z", "+00:00")), datetime.fromisoformat(period["end"].replace("Z", "+00:00"))))
    assert sorted((end - start for start, end in output_intervals)) == sorted((end - start for start, end in source_intervals))
    rows = [json.loads(line) for line in output["records.jsonl"].decode().splitlines()]
    patient_locs = {row["loc"] for row in rows}
    assert patient_locs == {f"/entry/{index}/resource" for index in (0, 1)}
    assert report["counts"]["records_processed"] == 2
