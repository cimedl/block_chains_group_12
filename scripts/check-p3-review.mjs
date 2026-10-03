//TODO: review this added pre-push review guard before approving it.
import { readFileSync } from "node:fs";
import { spawnSync } from "node:child_process";
import { resolve } from "node:path";
import { fileURLToPath } from "node:url";

const root = fileURLToPath(new URL("../", import.meta.url));
const checklistPath = "docs/p3-merge-todo.md";
const reviewedFiles = [
  ".gitignore", ".gitattributes", "README.md", "package.json", "requirements.txt", checklistPath,
  "contracts/EduConsent.sol",
  "offchain/crypto_utils.py", "offchain/encrypt_record.py",
  "offchain/offchain_service.py", "offchain/storage_db.py",
  "scripts/education.py", "scripts/demo.py", "scripts/benchmark.py",
  "results/benchmark-output.txt", "results/demo-output.txt",
  "results/demo-transactions.json", "results/gas-samples.json",
  "results/gas-summary.csv", "results/integration-tests.txt",
  ".githooks/pre-push", "scripts/check-p3-review.mjs",
];

//TODO: review all conditions required to permit a normal local Git push.
export function reviewProblems(checklist, changedFiles = []) {
  const problems = [];
  const pending = checklist.match(/^- \[ \].+$/gm) ?? [];
  if (pending.length) problems.push(...pending);
  if (!/^- \[[xX]\] Final review sign-off:/m.test(checklist)) {
    problems.push("Missing checked final review sign-off.");
  }
  for (const file of reviewedFiles) {
    if (!checklist.includes(file)) problems.push("Checklist omits reviewed file: " + file);
  }
  if (changedFiles.length) {
    problems.push("Commit the reviewed changes first: " + changedFiles.join(", "));
  }
  return problems;
}

//TODO: review Git execution and fail-closed error handling.
function git(args) {
  const result = spawnSync("git", ["-c", "safe.directory=" + root, ...args], {
    cwd: root, encoding: "utf8", stdio: ["ignore", "pipe", "pipe"],
  });
  if (result.error) throw result.error;
  if (result.status !== 0) throw new Error(result.stderr.trim() || "Git check failed.");
  return result.stdout;
}

//TODO: review that approval comes from the committed checklist, not unchecked working edits.
function main() {
  try {
    const committed = git(["show", "HEAD:" + checklistPath]);
    const working = readFileSync(resolve(root, checklistPath), "utf8");
    const changed = git(["diff", "--name-only", "HEAD", "--", ...reviewedFiles])
      .trim().split(/\r?\n/).filter(Boolean);
    const problems = reviewProblems(committed, changed);
    if (working.replace(/\r\n/g, "\n") !== committed.replace(/\r\n/g, "\n")) {
      problems.push("Checklist changes must be committed before pushing.");
    }
    if (problems.length) {
      console.error("PUSH BLOCKED: P3 review is incomplete.");
      console.error("Review " + checklistPath + ", check every item and final sign-off, then commit.");
      console.error(problems.join("\n"));
      process.exitCode = 1;
      return;
    }
    console.log("P3 review checklist and final sign-off are complete.");
  } catch (error) {
    console.error("PUSH BLOCKED: review could not be verified. " + error.message);
    process.exitCode = 1;
  }
}

//TODO: review this command-line entry point.
if (process.argv[1] && resolve(process.argv[1]) === fileURLToPath(import.meta.url)) main();
