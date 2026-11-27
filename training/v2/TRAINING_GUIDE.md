# Sheild V2 training add-on

Extract the ZIP at the existing project root. It adds `training/v2/` only; the root files, `raksha.toml`, toolkit, frontend, backend and V1 `training/` and `models/` files remain unchanged. This is training material, not a finished privacy engine. Run during the event if required by its original-work rules.

## Colab
1. Upload `training/v2/Sheild_Model_Training_V2.ipynb` to Colab.
2. Select CPU runtime and Run all. When prompted upload the original `Sheild_Training_V2.zip`.
3. Three regularization candidates are compared on 8,000 training / 2,000 validation examples. The selection criterion weights F2 and Hindi recall and penalizes clinical/doctor overlap. The selected model trains on all 45,000 training rows. Full validation/test metrics are reported. Training can be resource-intensive; no completion time is guaranteed.
4. Linkage calibration chooses a threshold on validation at >=99.5% measured precision, or abstains if no qualifying threshold. Missing evidence is neutral; normalize phones and common DOB formats; retain authoritative conflict vetoes and independent-support eligibility. Scores are candidate-pair evidence, not cluster approval.
5. The frozen V1 models are evaluated on the same V2 test rows, using their original feature code. Test metrics are for reporting, not tuning.
6. Extract the exported `Sheild_Trained_Models_V2.zip` into the existing root. It writes `models/v2/`, not V1. Add `python-crfsuite==0.9.12` to root requirements if absent. Do not replace root requirements. Use `models/v2/model_runtime.py` with its matching V2 artifacts only; do not mix feature versions.

## Data and limitations
57,000 NER rows and 41,000 candidate pairs: 45k/6k/6k NER and 30k/5k/6k pairs. Synthetic name roots/surnames and clause wording are separated across splits; clause combinations and annotation offsets are reproducibly generated. A fixed seed and manifest hashes allow reproduction. No official practice input, truth, or attacker records used. Clinical phrase banks are shared across splits; names are compositional and can sound artificial. Identifiers include reserved-looking phone numbers and synthetic ID shapes, not realistic coverage of all identifier formats. The same synthetic number can recur across splits; pair scorer uses comparisons rather than memorized phone values. The authored evaluation is not equivalent to independent external data. Hard negatives are deliberately constructed and do not represent all real-world collisions. Do not infer 100% real-world precision from zero false positives here.

Local checks: all dataset hashes/counts, all NER token annotation round trips, family IDs, feature smoke checks, linkage calibration and frozen V1 linkage comparison were executed. CRF dependency not available locally, so V2 CRF training, inference and V1 CRF comparison remain unverified until Colab runs. No V2 CRF binary is supplied. The notebook is syntax checked. More independent adversarial examples and official practice pipeline evaluation are still required. No runtime use of training datasets, V1 benchmark files or official truth. Keep training materials out of public-facing frontend assets.
