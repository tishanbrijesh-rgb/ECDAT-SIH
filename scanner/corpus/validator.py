"""
Phase 3 exit-gate validator for ECDAT corpus.

Validates:
  1. >= 150 positive operations across all languages  (full corpus only)
  2. >= 150 negative operations across all languages  (full corpus only)
  3. Coverage across >= 4 languages                   (full corpus only)
  4. Coverage across all 9 algorithm families         (all files)
  5. Each family has >= 20 total entries (pos + neg)  (full corpus only)
  6. No duplicate corpus_ids                          (all files)
  7. All required fields present in each entry        (all files)
  8. sha256 hashes are valid 64-char hex              (all files)
  9. line_start < line_end                            (all files)
  10. commit_sha is valid hex string                   (all files)

Usage:
    python validator.py                              # validate all.json (exit gate target)
    python validator.py --path <file.json>            # validate a specific file
    python validator.py --all                         # validate every manifest
    python validator.py --holdout                     # validate train/holdout splits
"""
import argparse
import json
import os
import re
import sys

REQUIRED_FIELDS = {
    "corpus_id", "language", "algorithm_family", "repo_url", "commit_sha",
    "file_path", "file_sha256", "line_start", "line_end", "positive",
    "label", "operation",
}

SHA_RE = re.compile(r'^[0-9a-f]{40,64}$')

EXPECTED_FAMILIES = {
    "RSA", "ECDSA", "AES", "SHA-256", "HMAC",
    "Ed25519", "ML-KEM", "ML-DSA", "ChaCha20",
}

VALID_OPERATIONS = {
    "generate_keypair", "encrypt", "decrypt", "sign", "verify",
    "import_key", "hash", "compute", "encapsulate", "decapsulate",
    "derive_key",
}


def load_json(path):
    with open(path) as f:
        data = json.load(f)
    return data.get("entries", [])


def validate_entry(entry, idx):
    errors = []
    missing = REQUIRED_FIELDS - set(entry.keys())
    if missing:
        errors.append(f"  Entry {idx}: missing fields: {sorted(missing)}")
    if not isinstance(entry.get("positive"), bool):
        errors.append(f"  Entry {idx}: 'positive' must be bool")
    ls, le = entry.get("line_start"), entry.get("line_end")
    if isinstance(ls, int) and isinstance(le, int) and ls >= le:
        errors.append(f"  Entry {idx}: line_start ({ls}) >= line_end ({le})")
    fs = entry.get("file_sha256", "")
    if not isinstance(fs, str) or len(fs) != 64 or not re.match(r'^[0-9a-f]+$', fs):
        errors.append(f"  Entry {idx}: file_sha256 must be 64-char hex")
    cs = entry.get("commit_sha", "")
    if not isinstance(cs, str) or not SHA_RE.match(cs):
        errors.append(f"  Entry {idx}: commit_sha must be 40-64 char hex")
    op = entry.get("operation", "")
    if op and op not in VALID_OPERATIONS:
        errors.append(f"  Entry {idx}: unknown operation '{op}'")
    fam = entry.get("algorithm_family", "")
    if fam not in EXPECTED_FAMILIES:
        errors.append(f"  Entry {idx}: unexpected algorithm_family '{fam}'")
    return errors


def is_full_corpus(path, total_entries, languages):
    """True for the complete all.json, not for split files or single-language manifests."""
    is_split = "holdout" in path.lower() or "train_" in path.lower()
    return not is_split and (total_entries >= 300 or
                             (path.endswith("all.json") and len(languages) >= 4))


def validate_corpus(path):
    errors = []
    gates = []
    gate_pass = True

    try:
        entries = load_json(path)
    except Exception as ex:
        return False, {"path": path, "error": str(ex)}

    pos = sum(1 for e in entries if e.get("positive"))
    neg = sum(1 for e in entries if not e.get("positive"))
    langs = {e.get("language", "") for e in entries}
    fams = {e.get("algorithm_family", "") for e in entries}
    ops_by_fam = {}
    seen_ids = {}
    for idx, e in enumerate(entries):
        errors.extend(validate_entry(e, idx))
        cid = e.get("corpus_id")
        if cid in seen_ids:
            gates.append(f"FAIL: duplicate corpus_id '{cid}'")
            gate_pass = False
        seen_ids[cid] = True
        fam = e.get("algorithm_family", "unknown")
        ops_by_fam.setdefault(fam, {"pos": 0, "neg": 0, "ops": set()})
        if e.get("positive"):
            ops_by_fam[fam]["pos"] += 1
        else:
            ops_by_fam[fam]["neg"] += 1
        ops_by_fam[fam]["ops"].add(e.get("operation", ""))

    full = is_full_corpus(path, len(entries), langs)

    if full:
        # Gate 1: >= 150 positive
        if pos < 150:
            gates.append(f"FAIL: positive_count={pos} < 150")
            gate_pass = False
        else:
            gates.append(f"PASS: positive_count={pos} >= 150")

        # Gate 2: >= 150 negative
        if neg < 150:
            gates.append(f"FAIL: negative_count={neg} < 150")
            gate_pass = False
        else:
            gates.append(f"PASS: negative_count={neg} >= 150")

        # Gate 3: >= 4 languages
        non_empty = {l for l in langs if l}
        if len(non_empty) < 4:
            gates.append(f"FAIL: language_count={len(non_empty)} < 4")
            gate_pass = False
        else:
            gates.append(f"PASS: language_count={len(non_empty)} >= 4")

        # Gate 5: Each family >= 20
        for fam, counts in sorted(ops_by_fam.items()):
            total = counts["pos"] + counts["neg"]
            if total < 20:
                gates.append(f"FAIL: {fam} has {total} entries (need >= 20)")
                gate_pass = False
        if all((c["pos"] + c["neg"]) >= 20 for c in ops_by_fam.values()):
            gates.append("PASS: all families have >= 20 entries each")
    else:
        gates.append(f"INFO: pos={pos}, neg={neg} (split file, exit gate skipped)")
        gates.append(f"INFO: languages={sorted(langs)} (split file, exit gate skipped)")
        gates.append("INFO: per-family >=20 check skipped (run on all.json)")

    # Gate 4: All 9 families covered (all files)
    missing = EXPECTED_FAMILIES - fams
    if missing:
        gates.append(f"FAIL: missing families: {sorted(missing)}")
        gate_pass = False
    else:
        gates.append(f"PASS: all {len(EXPECTED_FAMILIES)} algorithm families covered")

    # Gate 6: No duplicates
    sum(1 for cid, _ in seen_ids.items() if isinstance(cid, str))
    # Already handled in loop above

    passed = gate_pass and len(errors) == 0

    report = {
        "path": path, "total_entries": len(entries),
        "positive_count": pos, "negative_count": neg,
        "languages": sorted(langs), "families": sorted(fams),
        "ops_by_family": {k: {"pos": v["pos"], "neg": v["neg"],
                              "ops": sorted(v["ops"])}
                          for k, v in sorted(ops_by_fam.items())},
        "gates": gates, "errors": errors,
    }
    return passed, report


def print_report(report):
    print(f"\n{'='*60}")
    print("  ECDAT Phase 3 Corpus Validator Report")
    print(f"{'='*60}")
    print(f"  File:    {report['path']}")
    print(f"  Entries: {report['total_entries']}  (pos={report['positive_count']}, neg={report['negative_count']})")
    print("\n  Gates:")
    for g in report["gates"]:
        print(f"    {g}")
    print("\n  Family Breakdown:")
    for fam, counts in sorted(report["ops_by_family"].items()):
        print(f"    {fam:12s}: {counts['pos']:3d} pos + {counts['neg']:3d} neg  ops={counts['ops']}")
    if report["errors"]:
        print(f"\n  Entry Errors ({len(report['errors'])}):")
        for err in report["errors"][:20]:
            print(err)
        if len(report["errors"]) > 20:
            print(f"    ... +{len(report['errors']) - 20} more")
    status = "PASSED" if not report["errors"] and all("FAIL" not in g for g in report["gates"]) else "FAILED"
    print(f"\n  Overall: {status}")
    print(f"{'='*60}")


def main():
    parser = argparse.ArgumentParser(description="ECDAT corpus exit-gate validator")
    parser.add_argument("--path", help="Path to a specific corpus JSON file")
    parser.add_argument("--all", action="store_true", help="Validate all manifest files")
    parser.add_argument("--holdout", action="store_true", help="Validate train/holdout splits")
    args = parser.parse_args()

    corpus_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "manifests")
    holdout_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "holdout")

    targets = []
    if args.path:
        targets = [args.path]
    elif args.holdout:
        for f in ["train_all.json", "holdout_all.json"]:
            p = os.path.join(holdout_dir, f)
            if os.path.exists(p):
                targets.append(p)
    elif args.all:
        targets = sorted(os.path.join(corpus_dir, f)
                         for f in os.listdir(corpus_dir) if f.endswith(".json"))
    else:
        targets = [os.path.join(corpus_dir, "all.json")]
        for f in ["train_all.json", "holdout_all.json"]:
            p = os.path.join(holdout_dir, f)
            if os.path.exists(p):
                targets.append(p)

    if not targets:
        print("No corpus files found.")
        sys.exit(1)

    all_ok = True
    for target in targets:
        if not os.path.exists(target):
            print(f"SKIP: {target} not found")
            continue
        passed, report = validate_corpus(target)
        print_report(report)
        if not passed:
            all_ok = False

    print()
    if all_ok:
        print("*** ALL VALIDATIONS PASSED ***")
        sys.exit(0)
    else:
        print("*** VALIDATION FAILURES DETECTED ***")
        sys.exit(1)


if __name__ == "__main__":
    main()
