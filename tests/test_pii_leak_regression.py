"""Regression tests for the six PII leaks found in release_gate_independent_v1.

Each test uses independently authored names, identifiers, labels and sentence
structures — not the exact fixture values.  The fixture itself is exercised in
the final integration test at the bottom.

Preserved: clinician names, diagnoses, medicines, dosages, measurements.
"""
import json
import re
import sheild.engine as engine_module
from sheild.engine import run_pipeline, Engine, Evidence
from sheild.verify import verify


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _run(entries):
    out = {}
    report, docs = run_pipeline(entries, out, "regression-secret-v1", None)
    return out, report, docs


def _text(out, key):
    return out[key].decode("utf-8")


def _sanitized_text(out):
    return "\n".join(
        out[k].decode("utf-8") for k in out if k.startswith("sanitized/")
    )


# ---------------------------------------------------------------------------
# Leak 1 — Unfamiliar English registry name column ("Kin Signature" style)
# ---------------------------------------------------------------------------

def test_unfamiliar_kin_column_name_redacted():
    """'Kin Signature' and similar compound kin-bearing column headers must be
    treated as relative fields, not plain text."""
    entries = [
        (
            "registry.csv",
            b"Registry Unit,Enrollee Alias,Kin Signature,Drug Schedule\n"
            b"East Wing,Toreva Malkind,Sivara Malkind,Aspirin 75 mg\n",
        )
    ]
    out, _, _ = _run(entries)
    safe = _sanitized_text(out)
    assert "Toreva Malkind" not in safe, "patient name leaked via Enrollee Alias column"
    assert "Sivara Malkind" not in safe, "relative name leaked via Kin Signature column"
    assert "Aspirin 75 mg" in safe, "clinical value must be preserved"


def test_family_witness_column_redacted():
    """'Family Witness' JSON key must be treated as a relative field."""
    entries = [
        (
            "visit.json",
            json.dumps({
                "subjectAlias": "Korvena Talsin",
                "familyWitness": "Drevara Talsin",
                "callback": "+91 98765 43210",
                "diagnosis": "hypertension",
                "medicine": "Amlodipine 5 mg",
            }).encode(),
        )
    ]
    out, _, _ = _run(entries)
    safe = _sanitized_text(out)
    assert "Korvena Talsin" not in safe, "patient name leaked via subjectAlias key"
    assert "Drevara Talsin" not in safe, "relative name leaked via familyWitness key"
    assert "hypertension" in safe, "diagnosis must be preserved"
    assert "Amlodipine 5 mg" in safe, "medicine must be preserved"


def test_enrollee_alias_column_redacted():
    """'Enrollee Alias' column must be treated as a name field."""
    entries = [
        (
            "enroll.csv",
            b"Facility,Enrollee Alias,Contact Key,Diagnosis\n"
            b"North Block,Prevara Solkin,9876543210,Type 2 diabetes\n",
        )
    ]
    out, _, _ = _run(entries)
    safe = _sanitized_text(out)
    assert "Prevara Solkin" not in safe, "patient name leaked via Enrollee Alias column"
    assert "Type 2 diabetes" in safe, "diagnosis must be preserved"


# ---------------------------------------------------------------------------
# Leak 2 — Unfamiliar English phone column ("Contact Key" style)
# ---------------------------------------------------------------------------

def test_unfamiliar_contact_key_column_phone_redacted():
    """'Contact Key' and similar unfamiliar phone-bearing column headers must
    be treated as contact/phone fields."""
    entries = [
        (
            "registry.csv",
            b"Registry Unit,Enrollee Alias,Contact Key,Drug Schedule\n"
            b"East Wing,Toreva Malkind,9123456780,Aspirin 75 mg\n",
        )
    ]
    out, _, _ = _run(entries)
    safe = _sanitized_text(out)
    assert "9123456780" not in safe, "phone leaked via Contact Key column"
    assert "Aspirin 75 mg" in safe, "clinical value must be preserved"


def test_eleven_digit_phone_redacted_in_text():
    """11-digit Indian mobile numbers (e.g. 81234567890) must be redacted."""
    entries = [
        (
            "note.txt",
            b"Patient name: Toreva Malkind\nContact: 81234567890\nBP 118/74\n",
        )
    ]
    out, _, _ = _run(entries)
    safe = _sanitized_text(out)
    assert "81234567890" not in safe, "11-digit phone number leaked"
    assert "BP 118/74" in safe, "clinical measurement must be preserved"


def test_eleven_digit_phone_redacted_in_csv():
    """11-digit phone in a CSV contact column must be redacted."""
    entries = [
        (
            "reg.csv",
            b"Patient Name,Contact Key,Diagnosis\n"
            b"Toreva Malkind,81234567890,Asthma\n",
        )
    ]
    out, _, _ = _run(entries)
    safe = _sanitized_text(out)
    assert "81234567890" not in safe, "11-digit phone leaked in CSV"
    assert "Asthma" in safe, "diagnosis must be preserved"


def test_reach_key_column_phone_redacted():
    """'Reach Key' column must be treated as a contact field."""
    entries = [
        (
            "data.csv",
            b"Patient Name,Reach Key,Medicine\n"
            b"Korvena Talsin,9988776655,Metformin 500 mg\n",
        )
    ]
    out, _, _ = _run(entries)
    safe = _sanitized_text(out)
    assert "9988776655" not in safe, "phone leaked via Reach Key column"
    assert "Metformin 500 mg" in safe, "medicine must be preserved"


# ---------------------------------------------------------------------------
# Leak 3 & 4 — Hindi names under unfamiliar labels
# ---------------------------------------------------------------------------

def test_hindi_labhaarthi_sanket_label_redacted():
    """'लाभार्थी संकेत:' (beneficiary indicator) must be treated as a name label."""
    entries = [
        (
            "note.txt",
            "लाभार्थी संकेत: सुरेखा वर्मा\nसाथ आया व्यक्ति: रमेश वर्मा\nसंपर्क सूत्र: ९८७६५४३२१०\nमूल्यांकन: दमा\nदवा: Budesonide 200 mcg\nनाड़ी 76 bpm\n".encode("utf-8"),
        )
    ]
    out, _, _ = _run(entries)
    safe = _sanitized_text(out)
    assert "सुरेखा वर्मा" not in safe, "Hindi patient name leaked via लाभार्थी संकेत label"
    assert "रमेश वर्मा" not in safe, "Hindi relative name leaked via साथ आया व्यक्ति label"
    assert "Budesonide 200 mcg" in safe, "medicine must be preserved"
    assert "दमा" in safe, "diagnosis must be preserved"


def test_hindi_saath_aaya_vyakti_label_redacted():
    """'साथ आया व्यक्ति:' (accompanying person) must be treated as a relative label."""
    entries = [
        (
            "note.txt",
            "मरीज का नाम: प्रिया शर्मा\nसाथ आया व्यक्ति: अनिल शर्मा\nनाड़ी 80 bpm\nदवा: Paracetamol 500 mg\n".encode("utf-8"),
        )
    ]
    out, _, _ = _run(entries)
    safe = _sanitized_text(out)
    assert "प्रिया शर्मा" not in safe, "Hindi patient name leaked"
    assert "अनिल शर्मा" not in safe, "Hindi relative name leaked via साथ आया व्यक्ति"
    assert "Paracetamol 500 mg" in safe, "medicine must be preserved"


def test_hindi_parivar_sakshi_label_redacted():
    """'परिवार साक्षी:' (family witness) must be treated as a relative label."""
    entries = [
        (
            "note.txt",
            "लाभार्थी: मीना गुप्ता\nपरिवार साक्षी: सुनील गुप्ता\nBP 130/85\nदवा: Amlodipine 5 mg\n".encode("utf-8"),
        )
    ]
    out, _, _ = _run(entries)
    safe = _sanitized_text(out)
    assert "मीना गुप्ता" not in safe, "Hindi patient name leaked via लाभार्थी label"
    assert "सुनील गुप्ता" not in safe, "Hindi relative name leaked via परिवार साक्षी label"
    assert "Amlodipine 5 mg" in safe, "medicine must be preserved"


# ---------------------------------------------------------------------------
# Leak 5 & 6 — Hinglish names under unfamiliar JSON keys
# ---------------------------------------------------------------------------

def test_hinglish_subject_alias_key_redacted():
    """'subjectAlias' JSON key must be treated as a name field."""
    entries = [
        (
            "visit.json",
            json.dumps({
                "subjectAlias": "Korvena Talsin",
                "diagnosis": "migraine",
                "medicine": "Propranolol 20 mg",
                "measurement": "Pulse 72 bpm",
            }).encode(),
        )
    ]
    out, _, _ = _run(entries)
    safe = _sanitized_text(out)
    assert "Korvena Talsin" not in safe, "Hinglish patient name leaked via subjectAlias key"
    assert "migraine" in safe, "diagnosis must be preserved"
    assert "Propranolol 20 mg" in safe, "medicine must be preserved"


def test_hinglish_family_witness_key_redacted():
    """'familyWitness' JSON key must be treated as a relative field."""
    entries = [
        (
            "visit.json",
            json.dumps({
                "visitEnvelope": {
                    "subjectAlias": "Korvena Talsin",
                    "familyWitness": "Drevara Talsin",
                    "carePlan": {
                        "diagnosis": "migraine",
                        "medicine": "Propranolol 20 mg",
                        "measurement": "Pulse 72 bpm",
                    },
                }
            }).encode(),
        )
    ]
    out, _, _ = _run(entries)
    safe = _sanitized_text(out)
    assert "Korvena Talsin" not in safe, "Hinglish patient name leaked via subjectAlias"
    assert "Drevara Talsin" not in safe, "Hinglish relative name leaked via familyWitness"
    assert "migraine" in safe, "diagnosis must be preserved"
    assert "Propranolol 20 mg" in safe, "medicine must be preserved"
    assert "Pulse 72 bpm" in safe, "measurement must be preserved"


def test_hinglish_enrollee_alias_key_redacted():
    """'enrolleeAlias' JSON key must be treated as a name field."""
    entries = [
        (
            "enroll.json",
            json.dumps({
                "enrolleeAlias": "Prevara Solkin",
                "kinSignature": "Drevara Solkin",
                "diagnosis": "Type 2 diabetes",
                "medicine": "Metformin 500 mg",
            }).encode(),
        )
    ]
    out, _, _ = _run(entries)
    safe = _sanitized_text(out)
    assert "Prevara Solkin" not in safe, "name leaked via enrolleeAlias key"
    assert "Drevara Solkin" not in safe, "relative leaked via kinSignature key"
    assert "Metformin 500 mg" in safe, "medicine must be preserved"


# ---------------------------------------------------------------------------
# Clinical preservation guard — ensure fixes do not break clinical values
# ---------------------------------------------------------------------------

def test_clinical_values_preserved_across_new_label_types():
    """Diagnoses, medicines, dosages and measurements must survive all new
    label-type handling."""
    entries = [
        (
            "mixed.csv",
            b"Enrollee Alias,Kin Signature,Contact Key,Diagnosis,Medicine,BP\n"
            b"Toreva Malkind,Sivara Malkind,9123456780,Asthma,Salbutamol 100 mcg,118/74\n",
        )
    ]
    out, _, _ = _run(entries)
    safe = _sanitized_text(out)
    assert "Asthma" in safe
    assert "Salbutamol 100 mcg" in safe
    assert "118/74" in safe
    assert "Toreva Malkind" not in safe
    assert "Sivara Malkind" not in safe
    assert "9123456780" not in safe


def test_semantic_field_labels_cover_independently_worded_variants():
    entries = [
        (
            "registry.csv",
            b"Beneficiary Identity,Household Witness,Reach Number,Diagnosis,Medicine,Strength,BP\n"
            b"Avira Solven,Marik Solven,9345678123,Asthma,Salbutamol,100 mcg,118/74\n",
        ),
        (
            "note.txt",
            "नामांकित लाभार्थी: रेवती नायर\nसंग आए परिजन: करण नायर\n"
            "संपर्क विवरण: ९८७६५४३२१०\nमूल्यांकन: दमा\nदवा: Budesonide 200 mcg\n".encode("utf-8"),
        ),
        (
            "visit.json",
            json.dumps({
                "CaseSubject": "Lina Morven",
                "HouseholdWitness": "Tarin Morven",
                "SamparkNumber": "9876543210",
                "carePlan": {
                    "diagnosis": "migraine",
                    "medicine": "Propranolol 20 mg",
                    "measurement": "Pulse 72 bpm",
                    "consultantName": "Dr. Anand Mehta",
                },
            }).encode(),
        ),
    ]
    out, _, _ = _run(entries)
    safe = _sanitized_text(out)
    for surface in [
        "Avira Solven", "Marik Solven", "9345678123",
        "रेवती नायर", "करण नायर", "९८७६५४३२१०",
        "Lina Morven", "Tarin Morven", "9876543210",
    ]:
        assert surface not in safe, f"PII leaked: {surface}"
    for clinical in [
        "Asthma", "Salbutamol", "100 mcg", "118/74", "दमा",
        "Budesonide 200 mcg", "migraine", "Propranolol 20 mg",
        "Pulse 72 bpm", "Dr. Anand Mehta",
    ]:
        assert clinical in safe, f"Clinical value or clinician name lost: {clinical}"


def test_hindi_family_member_field_is_treated_as_relative_identity():
    entries = [
        (
            "registry.csv",
            "रोगी परिचय,परिवार सदस्य,संपर्क क्रमांक,निदान,दवा\n"
            "तारा सेन,नील सेन,९८७६५४३२१०,दमा,Salbutamol 100 mcg\n".encode("utf-8"),
        )
    ]
    out, _, _ = _run(entries)
    safe = _sanitized_text(out)
    assert "तारा सेन" not in safe
    assert "नील सेन" not in safe
    assert "९८७६५४३२१०" not in safe
    assert "दमा" in safe
    assert "Salbutamol 100 mcg" in safe


def test_independent_verifier_catches_names_when_detector_field_roles_miss(monkeypatch):
    entries = [
        (
            "unfamiliar.json",
            json.dumps({
                "CaseSubject": "Ravina Solvek",
                "HouseholdWitness": "Miran Solvek",
                "diagnosis": "asthma",
                "medicine": "Budesonide 200 mcg",
            }).encode(),
        )
    ]
    monkeypatch.setattr(engine_module, "field_role", lambda *args, **kwargs: "text")
    out, _, docs = _run(entries)
    leaked = _sanitized_text(out)
    assert "Ravina Solvek" in leaked
    assert "Miran Solvek" in leaked
    result = verify(entries, out, docs)
    assert result["contractValid"] is True
    assert result["approved"] is False
    assert result["findings"]["residual_labeled_pii"] >= 2


def test_independent_verifier_blocks_leaked_phone_pattern():
    entries = [
        (
            "registry.csv",
            b"Patient Identity,Contact Route,Diagnosis\n"
            b"Ravina Solvek,81234567890,Asthma\n",
        )
    ]
    out, _, docs = _run(entries)
    key = next(k for k in out if k.startswith("sanitized/"))
    out[key] = out[key].replace(b"[REDACTED]", b"81234567890", 1)
    result = verify(entries, out, docs)
    assert not result["approved"]
    assert result["findings"].get("residual_direct_pattern")
    assert result["findings"].get("residual_labeled_pii")


def test_doctor_name_preserved_in_text_with_new_labels():
    """Clinician names (Dr. prefix) must not be redacted even when new label
    types are present in the same document."""
    entries = [
        (
            "note.txt",
            b"Enrollee Alias: Toreva Malkind\nKin Signature: Sivara Malkind\n"
            b"Referred by Dr. Anand Mehta\nDiagnosis: rheumatoid arthritis\n"
            b"Medicine: Methotrexate 10 mg weekly\n",
        )
    ]
    out, _, _ = _run(entries)
    safe = _sanitized_text(out)
    assert "Dr. Anand Mehta" in safe, "clinician name must be preserved"
    assert "rheumatoid arthritis" in safe
    assert "Methotrexate 10 mg weekly" in safe
    assert "Toreva Malkind" not in safe
    assert "Sivara Malkind" not in safe


# ---------------------------------------------------------------------------
# Verify: release must be blocked when known names remain in output
# ---------------------------------------------------------------------------

def test_verify_blocks_release_when_known_name_leaks():
    """If a known multi-word name survives in output, verify must not approve."""
    # Manually craft a scenario: run pipeline, then inject a name back.
    entries = [
        (
            "note.txt",
            b"Patient name: Toreva Malkind\nBP 118/74\nMetformin 500 mg\n",
        )
    ]
    out, _, docs = _run(entries)
    # Inject the name back into the sanitized output to simulate a leak.
    key = next(k for k in out if k.startswith("sanitized/"))
    out[key] = out[key].replace(b"[REDACTED]", b"Toreva Malkind")
    result = verify(entries, out, docs)
    assert not result["approved"], "verify must block release when known name leaks"


# ---------------------------------------------------------------------------
# Integration: original fixture — all six surfaces must now be redacted
# ---------------------------------------------------------------------------

def test_original_fixture_six_leaks_fixed():
    """The seven-file fixture that previously leaked 6/20 surfaces must now
    leak 0 after the generalized fixes."""
    fixture_entries = [
        (
            "registry_export.csv",
            b"Registry Unit,Enrollee Alias,Kin Signature,Contact Key,Drug Schedule,Pressure Reading\n"
            b"North Annex,Elarin Vossel,Mavira Vossel,81234567890,Methotrexate 10 mg weekly,118/74\n",
        ),
        (
            "followup_note.txt",
            b"Patient name: Elarin Vossel\nMRN: VX-903817\n"
            b"Visit interval: 2026-03-04 to 2026-03-11\n"
            b"Assessment: rheumatoid arthritis\n"
            b"Continue Methotrexate 10 mg weekly; BP 118/74.\n",
        ),
        (
            "hindi_unfamiliar_labels.txt",
            "लाभार्थी संकेत: तविरा नोरवेन\nसाथ आया व्यक्ति: मिरेह नोरवेन\n"
            "संपर्क सूत्र: ९८७६५४३२१०\nमूल्यांकन: दमा\nदवा: Budesonide 200 mcg\nनाड़ी 76 bpm\n".encode("utf-8"),
        ),
        (
            "hinglish_nested.json",
            json.dumps({
                "visitEnvelope": {
                    "subjectAlias": "Nivara Selvar",
                    "familyWitness": "Dovira Selvar",
                    "callback": "+91 98765 43210",
                    "carePlan": {
                        "diagnosis": "migraine",
                        "medicine": "Propranolol 20 mg",
                        "measurement": "Pulse 72 bpm",
                    },
                }
            }).encode(),
        ),
    ]
    out, _, _ = _run(fixture_entries)
    all_text = "\n".join(
        out[k].decode("utf-8") for k in out if k.startswith("sanitized/")
    ).casefold()

    leaked = []
    for surface in [
        "Mavira Vossel", "81234567890",
        "तविरा नोरवेन", "मिरेह नोरवेन",
        "Nivara Selvar", "Dovira Selvar",
    ]:
        if surface.casefold() in all_text:
            leaked.append(surface)

    assert leaked == [], f"Previously leaked surfaces still present: {leaked}"

    # Clinical values must survive
    for clinical in ["Methotrexate 10 mg weekly", "118/74", "Budesonide 200 mcg",
                     "migraine", "Propranolol 20 mg", "Pulse 72 bpm"]:
        assert clinical.casefold() in all_text, f"Clinical value lost: {clinical}"
