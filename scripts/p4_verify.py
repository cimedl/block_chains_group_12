import contextlib
import hashlib
import io
import json
import re
import shutil
import subprocess
import sys
import unittest
from datetime import datetime, timezone
from importlib.metadata import version
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class RecordedResult(unittest.TextTestResult):
    def __init__(self, *args):
        super().__init__(*args)
        self.records = []

    def addSuccess(self, test):
        super().addSuccess(test)
        self.records.append({"test": test.id(), "status": "Passed"})

    def addFailure(self, test, error):
        super().addFailure(test,error)
        self.records.append({"test": test.id(), "status": "Failed", "detail": self._exc_info_to_string(error,test)})

    def addError(self, test, error):
        super().addError(test,error)
        self.records.append({"test": test.id(), "status": "Error", "detail": self._exc_info_to_string(error,test)})

    def addSkip(self, test, reason):
        super().addSkip(test,reason)
        self.records.append({"test": test.id(), "status": "Skipped", "detail": reason})

    def addSubTest(self, test, subtest, error):
        super().addSubTest(test,subtest,error)
        if error is not None:
            self.records.append({"test": subtest.id(), "status": "Failed", "detail": self._exc_info_to_string(error,test)})


def environment():
    try:
        revision = subprocess.run(["git", "-c", "safe.directory=" + str(ROOT), "rev-parse", "--show-toplevel", "HEAD"],
            cwd=ROOT, capture_output=True, text=True)
    except FileNotFoundError:
        head = "unversioned source archive (Git unavailable)"
    else:
        lines = revision.stdout.splitlines()
        if revision.returncode == 0 and len(lines) == 2 and Path(lines[0]).resolve() == ROOT.resolve():
            head = lines[1]
        else:
            head = "unversioned source archive"
    paths = list((ROOT / "test").glob("*.sol")) + list((ROOT / "test").glob("*.py"))
    paths += list((ROOT / "contracts").rglob("*.sol")) + list((ROOT / "offchain").glob("*.py"))
    paths += [ROOT / "hardhat.config.ts", ROOT / "package-lock.json", ROOT / "requirements.txt"]
    paths += list((ROOT / "scripts").glob("p4_*.py"))
    paths += [ROOT / "scripts/healthcare_demo.py"]
    return {"started_utc": datetime.now(timezone.utc).isoformat(), "head": head,
        "source": "current working tree; SHA-256 hashes identify uncommitted content",
        "python": sys.version, "node": subprocess.check_output([shutil.which("node"), "--version"],text=True).strip(),
        "hardhat": json.loads((ROOT / "node_modules/hardhat/package.json").read_text())["version"],
        "web3": version("web3"), "eth-account": version("eth-account"), "cryptography": version("cryptography"),
        "solidity_compiler": "0.8.28", "optimizer": {"enabled": True, "runs": 200},
        "source_sha256": {str(path.relative_to(ROOT)).replace("\\","/"): hashlib.sha256(path.read_bytes()).hexdigest() for path in sorted(paths)}}


def runCommand(args, path):
    run = subprocess.run(args, cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding="utf-8")
    path.write_text(run.stdout, encoding="utf-8")
    return run


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    runId = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    folder = ROOT / "results/p4-current" / runId
    folder.mkdir(parents=True)
    metadata = environment()
    cli = [shutil.which("node"), str(ROOT / "node_modules/hardhat/dist/src/cli.js")]
    compiled = runCommand(cli + ["compile"], folder / "compile.txt")
    solidity = runCommand(cli + ["test", "solidity"], folder / "solidity-tests.txt")
    names = re.findall(r"\b(test\w+)\(\)", solidity.stdout)
    metadata["solidity"] = {"returncode": solidity.returncode, "tests": names, "output": "solidity-tests.txt"}
    metadata["compile_returncode"] = compiled.returncode

    sys.path.insert(0, str(ROOT / "test"))
    stream = io.StringIO()
    suite = unittest.defaultTestLoader.discover(str(ROOT / "test"), pattern="test_*.py")
    with contextlib.redirect_stdout(stream), contextlib.redirect_stderr(stream):
        result = unittest.TextTestRunner(stream=stream, verbosity=2, resultclass=RecordedResult).run(suite)
    (folder / "python-tests.txt").write_text(stream.getvalue(),encoding="utf-8")
    metadata["python_tests"] = result.records
    metadata["python_summary"] = {"run": result.testsRun, "failures": len(result.failures), "errors": len(result.errors), "skipped": len(result.skipped)}
    metadata["commands"] = ["npx hardhat compile", "npx hardhat test solidity", ".venv/Scripts/python.exe -m unittest discover -s test -p test_*.py -v"]
    (folder / "run.json").write_text(json.dumps(metadata,indent=2) + "\n",encoding="utf-8")
    latest = {"folder": str(folder.relative_to(ROOT)).replace("\\","/"), "solidity_returncode": solidity.returncode, "python_summary": metadata["python_summary"]}
    (folder.parent / "latest.json").write_text(json.dumps(latest,indent=2) + "\n",encoding="utf-8")
    print("Solidity test command exit code:", solidity.returncode, "| test functions:", len(names))
    print("Python:", json.dumps(metadata["python_summary"]))
    for record in result.records:
        if record["status"] != "Passed":
            print(record["status"] + ": " + record["test"])
    print("Evidence:", folder)
    return 0 if compiled.returncode == 0 and solidity.returncode == 0 and result.wasSuccessful() else 1


if __name__ == "__main__":
    raise SystemExit(main())
