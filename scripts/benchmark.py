# TODO: review all code in this file imported from part3.
"""Try different numbers of students and save the gas results."""

import csv
import json
import tempfile

from education import EducationDemo, ROOT, DIPLOMA, record_hash, sample_identity, sample_diploma


# TODO: review this imported or added definition.
def main():
    results = ROOT / "results"
    results.mkdir(exist_ok=True)
    all_samples = []
    summary = []
    for student_count in [1, 5, 10]:
        with tempfile.TemporaryDirectory() as directory:
            demo = EducationDemo(directory)
            demo.deploy()
            employer = demo.accounts[19]
            for number in range(1, student_count + 1):
                student = demo.accounts[number]
                identity = sample_identity(number)
                demo.register(student, identity)
                new_identity = sample_identity(number)
                new_hash = record_hash(new_identity)
                function = demo.contract.functions.updateIdentity(new_hash)
                demo.send(function, student, "updateIdentity")
                demo.publish(student, DIPLOMA, sample_diploma(number))
                assert not demo.access(student, employer)["allowed"]
                demo.measurements[-1]["function"] = "requestAccess_denied"
                demo.grant(student, employer)
                for _ in range(10):
                    assert demo.access(student, employer)["allowed"]
                    demo.measurements[-1]["function"] = "requestAccess_allowed"
                demo.revoke(student, employer)
                demo.grant(student, employer)
                demo.measurements[-1]["function"] = "grantConsent_repeat"

            # Put measurements for the same function in one list.
            grouped = {}
            for sample in demo.measurements:
                sample["students"] = student_count
                all_samples.append(sample)
                name = sample["function"]
                if name not in grouped:
                    grouped[name] = []
                grouped[name].append(sample)
            for name, samples in grouped.items():
                total_gas = 0
                total_time = 0
                for sample in samples:
                    total_gas += sample["gas"]
                    total_time += sample["confirmation_ms"]

                row = {
                    "students": student_count,
                    "function": name,
                    "samples": len(samples),
                    "average_gas": round(total_gas / len(samples), 2),
                    "average_confirmation_ms": round(total_time / len(samples), 3),
                }
                summary.append(row)
            print(f"PASS: {student_count} students, {student_count * 10} successful data accesses")

    with (results / "gas-summary.csv").open("w", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=summary[0].keys())
        writer.writeheader()
        writer.writerows(summary)
    (results / "gas-samples.json").write_text(json.dumps(all_samples, indent=2) + "\n")
    print("Saved results/gas-summary.csv and results/gas-samples.json")
    print("Times measure submission + local auto-mining + receipt retrieval, not public-network latency.")


if __name__ == "__main__":
    main()
