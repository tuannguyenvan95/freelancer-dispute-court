# Freelancer Dispute Court

**Freelancer Dispute Court** is an intelligent escrow system designed to securely hold funds for freelance jobs and resolve disputes using autonomous AI arbitration on **GenLayer**.

## The Problem & The GenLayer Solution

Traditional escrow smart contracts suffer from a critical flaw: if the client and freelancer disagree, funds are locked indefinitely, or they rely on a centralized, trusted third-party human arbitrator (which is slow, expensive, and biased).

**Why this project dies without GenLayer:**
Without GenLayer, this project is just a dumb escrow that permanently locks funds when clients and freelancers disagree, because blockchains cannot read off-chain evidence or make subjective judgments. 

With GenLayer's non-deterministic Intelligent Contracts, the contract itself browses the web (e.g., GitHub PRs, live demo sites) and acts as an impartial, automated judge. By leveraging `gl.nondet.web.render` and `gl.nondet.exec_prompt`, the contract securely and transparently adjudicates disputes on-chain, unlocking a completely decentralized freelance economy.

## Features

- **Decentralized Escrow:** Securely locks GEN tokens until the job is completed or disputed.
- **Multi-Source Web Evidence:** Freelancers can submit multiple URLs (e.g., GitHub, Live Demo). The Intelligent Contract reads them directly from the web.
- **Autonomous AI Arbitration:** If disputed, the contract's `adjudicate` function cross-checks the job description against the web evidence and outputs a verdict (`RELEASE`, `REFUND`, or `PARTIAL` with a percentage split).
- **Robust Consensus:** The validator function strictly compares the mathematical/categorical outcomes (the verdict and percentage), explicitly ignoring the subjective language of the AI's "reasoning". This ensures consensus is reliably reached on the studionet.
- **Premium User Experience:** A beautiful, responsive web app built with React, Vite, and GenLayer JS.

## Architecture

1. **Client** creates a job and deposits GEN into the escrow contract.
2. **Freelancer** completes the work and submits up to two evidence URLs.
3. Either party can trigger **Open Dispute** if there is a disagreement.
4. Anyone can call **Adjudicate**. The contract fetches the URLs, prompts the LLM, and reaches a non-deterministic consensus on the verdict, automatically transferring the funds based on the result.

## Example Usage

**Setup Mocks & Run (Expected Verdict: REFUND):**
```python
contract.connect(freelancer).submit_evidence(
    args=["1", "1", "https://freelancer-evidence.com/deliverable"]
).transact()

# Mocking the AI adjudication: The evidence does not meet the milestone requirements.
client.provider.make_request(
    method="sim_installMocks",
    params={
        "llm_mocks": {
            ".*": json.dumps({
                "verdict": "REFUND",
                "percentage": 0,
                "confidence": 95,
                "reason": "The submitted evidence is entirely unrelated to the requested milestone."
            })
        },
        "web_mocks": {
            ".*": {"status": 200, "body": "Placeholder content"}
        }
    }
)

# Adjudicate milestone #1 for job #1
result = contract.connect(client_addr).adjudicate(args=["1", "1"]).transact()

# Expected state
milestone = contract.get_milestone(args=["1", "1"]).call()
assert milestone.verdict == "REFUND"
assert milestone.state == "CLOSED"
```

## Deployment

This intelligent contract has been deployed on GenLayer.
- **CONTRACT_ADDRESS:** `0x9D57c04be517DEd5ab290A004B8e7F246147e170`
- **NETWORK:** `studionet`

See [scripts/deploy.md](scripts/deploy.md) for step-by-step instructions on how to deploy this intelligent contract on GenLayer Studio.
