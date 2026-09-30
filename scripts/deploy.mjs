// Local Hardhat deployment. Uses Node's built-in modules only.
import { readFile, mkdir, writeFile, rename } from "node:fs/promises";
import { fileURLToPath } from "node:url";
import path from "node:path";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const rpcUrl = process.argv[2] ?? "http://127.0.0.1:8545";
let rpcId = 1;

async function rpc(method, params = []) {
  const response = await fetch(rpcUrl, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ jsonrpc: "2.0", id: rpcId++, method, params }),
    signal: AbortSignal.timeout(10000),
  });
  if (!response.ok) throw new Error(`RPC HTTP status ${response.status}`);
  const result = await response.json();
  if (result.error) throw new Error(`${method}: ${result.error.message}`);
  return result.result;
}

function addressWord(address) {
  if (!/^0x[0-9a-fA-F]{40}$/.test(address)) throw new Error("Invalid address");
  return address.slice(2).toLowerCase().padStart(64, "0");
}

async function callData(signature, addresses = []) {
  const hash = await rpc("web3_sha3", ["0x" + Buffer.from(signature).toString("hex")]);
  return hash.slice(0, 10) + addresses.map(addressWord).join("");
}

async function send(from, data, to) {
  const transaction = { from, data };
  if (to) transaction.to = to;
  transaction.gas = await rpc("eth_estimateGas", [transaction]);
  const hash = await rpc("eth_sendTransaction", [transaction]);
  for (let attempt = 0; attempt < 100; attempt++) {
    const receipt = await rpc("eth_getTransactionReceipt", [hash]);
    if (receipt) {
      if (receipt.status !== "0x1") throw new Error(`Transaction failed: ${hash}`);
      return receipt;
    }
    await new Promise((resolve) => setTimeout(resolve, 100));
  }
  throw new Error(`Receipt timeout: ${hash}`);
}

async function deploy(name, constructorAddresses, admin) {
  const artifactPath = path.join(root, "artifacts", "contracts", `${name}.sol`, `${name}.json`);
  const artifact = JSON.parse(await readFile(artifactPath, "utf8"));
  const receipt = await send(admin, artifact.bytecode + constructorAddresses.map(addressWord).join(""));
  const address = receipt.contractAddress;
  if (!address || await rpc("eth_getCode", [address, "latest"]) === "0x") {
    throw new Error(`${name} was not deployed`);
  }
  return { address, abi: artifact.abi, receipt };
}

const accounts = await rpc("eth_accounts");
if (accounts.length === 0) throw new Error("No unlocked local deployment account");
const admin = accounts[0];
const registry = await deploy("HealthRegistry", [admin], admin);
const reward = await deploy("ConsentReward", [registry.address, admin], admin);
const manager = await deploy("ConsentManager", [registry.address, reward.address], admin);
const wiring = await send(admin, await callData("setConsentManager(address)", [manager.address]), reward.address);

// Verify the actual deployed wiring before publishing the local manifest.
for (const [contract, getter, expected] of [
  [reward.address, "registry()", registry.address],
  [reward.address, "consentManager()", manager.address],
  [manager.address, "healthRegistry()", registry.address],
  [manager.address, "consentReward()", reward.address],
]) {
  const encoded = await rpc("eth_call", [{ to: contract, data: await callData(getter) }, "latest"]);
  if (encoded.toLowerCase() !== "0x" + addressWord(expected)) throw new Error(`Incorrect wiring: ${getter}`);
}

const manifest = {
  chainId: Number(BigInt(await rpc("eth_chainId"))),
  rpcUrl,
  admin,
  deployedAt: new Date().toISOString(),
  contracts: { HealthRegistry: registry, ConsentReward: reward, ConsentManager: manager },
  wiringReceipt: wiring,
};
const output = path.join(root, ".local", "deployment.json");
await mkdir(path.dirname(output), { recursive: true });
await writeFile(output + ".tmp", JSON.stringify(manifest, null, 2) + "\n");
await rename(output + ".tmp", output);
console.log(JSON.stringify({
  chainId: manifest.chainId,
  HealthRegistry: registry.address,
  ConsentReward: reward.address,
  ConsentManager: manager.address,
  manifest: output,
}, null, 2));
