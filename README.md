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

## Complete Escrow Lifecycle & Authorized State Transitions

The smart contract implements a complete, safe escrow lifecycle ensuring funds have explicit, authorized exit paths for every state:

```
[OPEN] ---> accept_milestone() -------------> [CLOSED] (Payout to Freelancer)
  | --------> cancel_milestone() -------------> [CLOSED] (100% Refund to Client)
  | --------> submit_evidence() -> open_dispute()
  v
[DISPUTED] -> adjudicate() (Consensus > 60%) --> [CLOSED] (Payout / Refund / Partial)
  |
  +---------> adjudicate() (Confidence < 60%) -> [ESCALATED] (Preserve Funds)
                                                    |
                                                    v
                                            resolve_escalated() -> [CLOSED] (Settlement Payout)
```

### Public API Methods:
- **`create_job(freelancer_addr: str)`**: Initializes a new job counter and records client and freelancer addresses.
- **`add_milestone(job_id: str, description: str)` [Payable]**: Adds a funded milestone in state `OPEN`, locking deposit in escrow.
- **`accept_milestone(job_id: str, milestone_id: str)`**: Authorized path for Client to directly accept an `OPEN` milestone deliverable, releasing funds (minus 2% fee) to freelancer. State becomes `CLOSED`.
- **`cancel_milestone(job_id: str, milestone_id: str)`**: Authorized path for Client to cancel an `OPEN` milestone before evidence submission, refunding deposit 100% back to client. State becomes `CLOSED`.
- **`submit_evidence(job_id: str, milestone_id: str, url: str)`**: Freelancer submits up to 2 web evidence URLs.
- **`open_dispute(job_id: str, milestone_id: str)`**: Either party transitions milestone from `OPEN` to `DISPUTED`.
- **`adjudicate(job_id: str, milestone_id: str)`**: Triggers AI evaluation of submitted evidence against description.
  - `RELEASE`: Transfers milestone amount (minus 2% protocol fee) to freelancer. State becomes `CLOSED`.
  - `REFUND`: Refunds 100% of milestone deposit back to client. State becomes `CLOSED`.
  - `PARTIAL`: Splits funds proportionally based on `percentage` (e.g. 60% freelancer / 40% client). State becomes `CLOSED`.
  - `ESCALATE`: If AI confidence < 60% or evidence is unverifiable, escrow remains 100% preserved in contract. State becomes `ESCALATED`.
- **`resolve_escalated(job_id: str, milestone_id: str, freelancer_percentage: int)`**: Authorized completion path for `ESCALATED` state. Callable by Client or Treasury Authority to safely resolve escalated funds with custom percentage split. State becomes `CLOSED`.
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

## Deployment

- **CONTRACT_ADDRESS:** `0xaa1E4A195005eE07206fd9C5d93401Ec8A5c7964`
- **NETWORK:** `studionet`
- **Studio URL:** https://studio.genlayer.com/contracts/0xaa1E4A195005eE07206fd9C5d93401Ec8A5c7964
- **Explorer URL:** https://explorer-studio.genlayer.com/address/0xaa1E4A195005eE07206fd9C5d93401Ec8A5c7964

## Illustrative Worked Example

```python
# 1. Client creates job & funds milestone
contract.create_job(freelancer_addr="0xFreelancer_222")
contract.add_milestone(job_id="1", description="Implement Responsive Navbar", value=1000)

# Option A: Client directly accepts OPEN milestone
contract.accept_milestone(job_id="1", milestone_id="1") # Funds -> Freelancer

# Option B: Dispute & Escalate -> Resolution
contract.submit_evidence(job_id="1", milestone_id="1", url="https://github.com/example/pr")
contract.open_dispute(job_id="1", milestone_id="1")
contract.adjudicate(job_id="1", milestone_id="1") # AI low confidence -> ESCALATED state
contract.resolve_escalated(job_id="1", milestone_id="1", freelancer_percentage=50) # Safe exit -> 50/50 split
```
