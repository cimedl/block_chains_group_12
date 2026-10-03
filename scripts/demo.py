# TODO: review all code in this file imported from part3.
"""Run with: .venv/bin/python scripts/demo.py"""

import json
from education import EducationDemo, ROOT, DIPLOMA, sample_identity, sample_diploma


# TODO: review this imported or added definition.
def main():
    demo = EducationDemo(ROOT / ".local/records")
    address = demo.deploy()
    student = demo.accounts[1]
    employer = demo.accounts[2]
    print("EduConsent: fictional education-record sharing")
    print(f"Local contract: {address}")
    demo.register(student, sample_identity())
    demo.publish(student, DIPLOMA, sample_diploma())
    print("1. Student registered; diploma saved locally; hashes stored on-chain.")

    denied = demo.access(student, employer)
    assert not denied["allowed"]
    print("2. Before consent: DENIED (attempt logged).")

    demo.grant(student, employer)
    allowed = demo.access(student, employer)
    assert allowed["allowed"]
    print("3. After one-day consent: ALLOWED.")
    print(json.dumps(allowed["record"], indent=2))
    assert demo.contract.functions.rewardBalance(student).call() == 10
    print("4. Student earned 10 reward points; access transferred no tokens.")

    demo.revoke(student, employer)
    assert not demo.access(student, employer)["allowed"]
    print("5. After revocation: DENIED (attempt logged).")

    demo.grant(student, employer)
    demo.advance_time(86400)
    assert not demo.access(student, employer)["allowed"]
    print("6. After expiry: DENIED (attempt logged).")
    assert demo.contract.functions.rewardBalance(student).call() == 10
    print("7. Re-granting the same permission did not generate extra rewards.")

    logs = demo.contract.events.AccessLogged().get_logs(from_block=0)
    decisions = []
    for log in logs:
        decisions.append(log["args"]["allowed"])
    print(f"Access log: {decisions}")
    results = ROOT / "results"
    results.mkdir(exist_ok=True)
    (results / "demo-transactions.json").write_text(json.dumps(demo.measurements, indent=2) + "\n")
    print("PASS: complete registration -> grant -> access -> revoke -> expiry workflow")


if __name__ == "__main__":
    main()
