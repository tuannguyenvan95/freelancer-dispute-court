# Freelancer Dispute Court

**Freelancer Dispute Court** is a standalone Intelligent Contract primitive on **GenLayer** that provides decentralized escrow and autonomous AI dispute arbitration for freelance contracts, bounties, and service agreements.

## The Problem & The GenLayer Solution

Traditional escrow smart contracts suffer from a fundamental flaw: if a client and freelancer disagree on deliverables, funds are locked indefinitely, or they must rely on a centralized, trusted third-party human arbitrator (slow, expensive, and biased).

**Why this primitive requires GenLayer:**
Blockchains traditionally cannot read off-chain evidence or evaluate subjective deliverables (like design files, PRs, codebases, or deployed websites). Without GenLayer, escrow contracts are unable to autonomously resolve real-world disputes.

With GenLayer's non-deterministic Intelligent Contracts:
1. The contract fetches live web evidence directly using `gl.nondet.web.render`.
2. The contract prompts an LLM via `gl.nondet.exec_prompt` to adjudicate the milestone against submitted evidence.
3. GenLayer nodes execute non-deterministic verification and reach decentralized consensus on the dispute verdict.

## Public API & Lifecycle

- **`create_job(freelancer_addr: str)`**: Initializes a new job counter and records client and freelancer addresses.
- **`add_milestone(job_id: str, description: str)` [Payable]**: Adds a funded milestone in state `OPEN`, locking deposit in escrow.
- **`submit_evidence(job_id: str, milestone_id: str, url: str)`**: Freelancer submits up to 2 web evidence URLs.
- **`open_dispute(job_id: str, milestone_id: str)`**: Either party transitions milestone from `OPEN` to `DISPUTED`.
- **`adjudicate(job_id: str, milestone_id: str)`**: Triggers AI evaluation of submitted evidence against description.
  - `RELEASE`: Transfers milestone amount (minus 2% protocol fee) to freelancer. State becomes `CLOSED`.
  - `REFUND`: Refunds 100% of milestone deposit back to client. State becomes `CLOSED`.
  - `PARTIAL`: Splits funds proportionally based on `percentage` (e.g. 60% freelancer / 40% client). State becomes `CLOSED`.
  - `ESCALATE`: If AI confidence < 60% or evidence is unverifiable, escrow remains 100% preserved in contract. State becomes `ESCALATED`.
- **`get_job(job_id: str) -> str`**: Returns JSON serialized job details.
- **`get_milestone(job_id: str, milestone_id: str) -> str`**: Returns JSON serialized milestone details.

## How Consensus & Validator Work (Agreement on MEANING)

GenLayer validators run non-deterministic operations (`leader_fn`) and verify proposals using `validator_fn(leader_res)`.

A naive check would verify string equality of LLM outputs, which inevitably fails due to non-deterministic wording. The Freelancer Dispute Court implements **semantic agreement on MEANING**:
- The validator parses and validates the structured output via `_safe_parse`.
- If confidence < 60%, the verdict is automatically mapped to `ESCALATE` with `percentage = 0`.
- The validator strictly compares:
  1. `mine["verdict"] == leader["verdict"]`
  2. `mine["percentage"] == leader["percentage"]`
- Subjective natural language explanations (`reason`) are excluded from consensus comparison, while **all payout-affecting fields are strictly bound**.
- Any divergence in payout intent or low-confidence escalation causes validators to reject the proposal, preventing erroneous state transitions.

## Deployment

- **CONTRACT_ADDRESS:** `0x692B254E7B7904e34D2C0840240182157972041C`
- **NETWORK:** `studionet`
- **Studio URL:** https://studio.genlayer.com/contracts/0x692B254E7B7904e34D2C0840240182157972041C
- **Explorer URL:** https://explorer-studio.genlayer.com/address/0x692B254E7B7904e34D2C0840240182157972041C

## Illustrative Worked Example

### 1. Job Creation & Funded Milestone
```python
# Client creates job with Freelancer 0xFreelancer...
contract.create_job(freelancer_addr="0xFreelancer_222")

# Client funds Milestone 1 with 1,000 GEN tokens
contract.add_milestone(job_id="1", description="Implement Responsive Navbar & Auth Flow", value=1000)
```

### 2. Evidence Submission & Dispute
```python
# Freelancer submits GitHub PR URL as evidence
contract.submit_evidence(job_id="1", milestone_id="1", url="https://github.com/example/repo/pull/12")

# Dispute opened due to disagreement on responsiveness
contract.open_dispute(job_id="1", milestone_id="1")
```

### 3. AI Adjudication & Payout
```python
# Anyone calls adjudicate
contract.adjudicate(job_id="1", milestone_id="1")
```

**Expected Outcome (Illustrative):**
- **AI Verdict:** `RELEASE` (Confidence: 95%, Percentage: 100%)
- **Treasury Payout:** 20 GEN (2% protocol fee)
- **Freelancer Payout:** 980 GEN
- **Milestone Final State:** `CLOSED`
