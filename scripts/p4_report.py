"""Generate report tables from matching verification and benchmark evidence."""
import csv
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read_csv(path):
    with path.open(encoding="utf-8", newline="") as source:
        return list(csv.DictReader(source))


def write_csv(path, rows):
    with path.open("w", encoding="utf-8", newline="") as output:
        writer = csv.DictWriter(output, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def table(headers, rows):
    lines = ["| " + " | ".join(headers) + " |", "| " + " | ".join("---" for _ in headers) + " |"]
    lines += ["| " + " | ".join(str(value).replace("|", "/").replace("\n", " ") for value in row) + " |" for row in rows]
    return "\n".join(lines)


def main():
    verification = json.loads((ROOT / "results/p4-current/latest.json").read_text())
    evaluation = json.loads((ROOT / "results/p4-evaluation/latest.json").read_text())
    verified = ROOT / verification["folder"]
    measured = ROOT / evaluation["folder"]
    run = json.loads((verified / "run.json").read_text())
    benchmark = json.loads((measured / "run.json").read_text())
    for path, digest in run["source_sha256"].items():
        if path.startswith(("contracts/", "offchain/")) or path == "hardhat.config.ts":
            if benchmark["source_sha256"].get(path) != digest:
                raise RuntimeError("Verification/evaluation application source differs: " + path)

    reasons = {row["test"]: row["why_critical"] for row in read_csv(ROOT / "results/test-results-all-tests-with-why-critical.csv")}
    locations = {}
    for path in (ROOT / "test").glob("*.sol"):
        for name in re.findall(r"function\s+(test\w+)\s*\(", path.read_text()):
            locations[name] = path.relative_to(ROOT).as_posix()
    tests = [{"test": name, "status": "Passed" if run["solidity"]["returncode"] == 0 else "Not confirmed", "source": locations[name]} for name in run["solidity"]["tests"]]
    for result in run["python_tests"]:
        tests.append({"test": result["test"].rsplit(".", 1)[-1], "status": result["status"], "source": "test/" + result["test"].split(".", 1)[0] + ".py"})
    if not tests:
        raise RuntimeError("No test outcomes recorded; run scripts/p4_verify.py first.")
    for test in tests:
        if test["test"] not in reasons:
            raise RuntimeError("Add a criticality explanation for test: " + test["test"])
        test["why_critical"] = reasons[test["test"]]

    gas = read_csv(measured / "gas-summary.csv")
    scaling = read_csv(measured / "scaling-summary.csv")
    output = ROOT / "results/p4-generated" / verified.name
    output.mkdir(parents=True, exist_ok=True)
    write_csv(output / "test-results-all-tests-with-why-critical.csv", tests)
    write_csv(output / "gas-deployment-and-function-costs.csv", gas)
    write_csv(output / "scaling-time-and-cost-by-number-of-users.csv", scaling)
    number = lambda value: f"{float(value):,.2f}"
    summary = []
    for component, suffix in (("Solidity", ".sol"), ("Python hashing", "test_hash_data.py"), ("Delivery integration", "test_offchain_service.py")):
        rows = [test for test in tests if test["source"].endswith(suffix)]
        summary.append([component, len(rows), sum(row["status"] == "Passed" for row in rows)])
    report = "\n\n".join([
        "# Verification and evaluation results",
        f"Verification revision: `{run['head']}`. Source SHA-256 hashes, dependency versions and raw outcomes are recorded in `{verification['folder']}/run.json`. Benchmark metadata is in `{evaluation['folder']}/run.json`.",
        "## Test outcomes",
        table(["Component", "Executed", "Passed"], summary),
        table(["Test", "Result", "Why critical"], [[test["test"], test["status"], test["why_critical"]] for test in tests]),
        "Passing outcomes establish only the listed scenarios. Compile/test failures and skipped tests remain in the verification evidence; this report does not establish complete coverage.",
        "## Deployment and operation gas",
        table(["Operation", "Samples", "Average gas", "Confirmation ms", "Event decode ms"], [[row["operation"], row["samples"], number(row["average_gas"]), number(row["average_confirmation_ms"]), number(row["average_event_decode_ms"])] for row in gas]),
        "Gas means use successful transaction receipts. Denied requests are successful transactions that record a denial. Confirmation includes submission and receipt retrieval; zero event-decoding time means that operation was not separately measured.",
        "## Scaling",
        table(["Patients", "Runs", "Transactions/run", "Average total gas", "Elapsed s", "Delivery ms", "Failures"], [[row["patients"], row["repetitions"], row["transactions_per_run"], number(row["average_total_gas"]), number(row["average_elapsed_s"]), number(row["average_delivery_total_ms"]), row["failures"]] for row in scaling]),
        f"Workloads use {benchmark['patients']} patients with {benchmark['repetitions']} repetitions each, two doctors and one administrator. Each run resets the temporary chain and uses fresh private files and a database. Total gas includes deployment and setup.",
        "Timings describe sequential synthetic workloads on a local auto-mining Hardhat node. They do not establish public-network throughput or real monetary costs. Authentication and permission probes must not be added to total delivery time, which already includes those checks. Permission decisions are on-chain; local delivery records do not prove a person received or read a file. Revocation cannot erase previously delivered copies.",
    ])
    (output / "report.md").write_text(report + "\n", encoding="utf-8")
    print("Generated report and CSV tables:", output)


if __name__ == "__main__":
    main()
