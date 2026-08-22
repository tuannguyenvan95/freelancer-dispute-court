# v0.2.16
# { "Depends": "py-genlayer:1jb45aa8ynh2a9c9xn3b7qqh8sm5q93hwfp7jqmwsfhh8jpz09h6" }
from genlayer import *
from dataclasses import dataclass
import json


@allow_storage
@dataclass
class Milestone:
    id: bigint
    job_id: bigint
    description: str
    amount: bigint
    evidence_url_1: str
    evidence_url_2: str
    evidence_count: bigint
    state: str
    verdict: str
    reason: str


@allow_storage
@dataclass
class Job:
    id: bigint
    client: str
    freelancer: str
    milestones_count: bigint


class Contract(gl.Contract):
    jobs: TreeMap[str, Job]
    milestones: TreeMap[str, Milestone]
    job_counter: bigint
    treasury_address: str

    def __init__(self, treasury_addr: str):
        self.job_counter = bigint(0)
        self.treasury_address = treasury_addr.strip() if treasury_addr else ""

    def _addr_str(self, addr: Address) -> str:
        try:
            return addr.as_hex
        except Exception:
            return str(addr)

    def _get_treasury_addr(self) -> Address:
        if not self.treasury_address:
            raise UserError("Treasury address not set")
        return Address(self.treasury_address)

    @gl.public.write
    def create_job(self, freelancer_addr: str) -> None:
        self.job_counter += bigint(1)
        job_id = self.job_counter

        self.jobs[str(job_id)] = Job(
            id=job_id,
            client=self._addr_str(gl.message.sender_address),
            freelancer=freelancer_addr.strip(),
            milestones_count=bigint(0),
        )

    @gl.public.view
    def get_job_counter(self) -> bigint:
        return self.job_counter

    @gl.public.write.payable
    def add_milestone(self, job_id: str, description: str) -> None:
        amount = gl.message.value
        if amount == bigint(0):
            raise UserError("Milestone amount cannot be zero")

        if job_id not in self.jobs:
            raise UserError("Job not found")

        job = self.jobs[job_id]
        if self._addr_str(gl.message.sender_address) != job.client:
            raise UserError("Only client can add milestones")

        job.milestones_count += bigint(1)
        m_id = job.milestones_count

        m_key = str(job_id) + "_" + str(m_id)

        self.milestones[m_key] = Milestone(
            id=m_id,
            job_id=bigint(int(job_id)),
            description=description,
            amount=amount,
            evidence_url_1="",
            evidence_url_2="",
            evidence_count=bigint(0),
            state="OPEN",
            verdict="",
            reason="",
        )

        self.jobs[job_id] = job

    @gl.public.write
    def accept_milestone(self, job_id: str, milestone_id: str) -> None:
        """Client accepts completed milestone work directly without dispute, releasing funds to freelancer."""
        if job_id not in self.jobs:
            raise UserError("Job not found")

        job = self.jobs[job_id]
        if self._addr_str(gl.message.sender_address) != job.client:
            raise UserError("Only client can accept milestone")

        m_key = str(job_id) + "_" + str(milestone_id)
        if m_key not in self.milestones:
            raise UserError("Milestone not found")

        milestone = self.milestones[m_key]
        if milestone.state != "OPEN":
            raise UserError("Milestone is not open for acceptance")

        ms_amount = milestone.amount
        freelancer_addr = Address(job.freelancer)

        fee = (ms_amount * bigint(2)) // bigint(100)
        payout = ms_amount - fee

        if fee > bigint(0):
            gl.get_contract_at(self._get_treasury_addr()).emit_transfer(value=fee)
        if payout > bigint(0):
            gl.get_contract_at(freelancer_addr).emit_transfer(value=payout)

        milestone.state = "CLOSED"
        milestone.verdict = "ACCEPTED_BY_CLIENT"
        milestone.reason = "Client directly accepted deliverable work."
        self.milestones[m_key] = milestone

    @gl.public.write
    def cancel_milestone(self, job_id: str, milestone_id: str) -> None:
        """Client cancels an open milestone if no evidence has been submitted, refunding deposit to client."""
        if job_id not in self.jobs:
            raise UserError("Job not found")

        job = self.jobs[job_id]
        if self._addr_str(gl.message.sender_address) != job.client:
            raise UserError("Only client can cancel milestone")

        m_key = str(job_id) + "_" + str(milestone_id)
        if m_key not in self.milestones:
            raise UserError("Milestone not found")

        milestone = self.milestones[m_key]
        if milestone.state != "OPEN":
            raise UserError("Milestone is not open for cancellation")
        if milestone.evidence_count > bigint(0):
            raise UserError("Cannot cancel milestone after freelancer submitted evidence; use open_dispute instead")

        ms_amount = milestone.amount
        client_addr = Address(job.client)

        if ms_amount > bigint(0):
            gl.get_contract_at(client_addr).emit_transfer(value=ms_amount)

        milestone.state = "CLOSED"
        milestone.verdict = "CANCELLED_BY_CLIENT"
        milestone.reason = "Client cancelled milestone before evidence submission."
        self.milestones[m_key] = milestone

    @gl.public.write
    def submit_evidence(self, job_id: str, milestone_id: str, url: str) -> None:
        if job_id not in self.jobs:
            raise UserError("Job not found")

        job = self.jobs[job_id]
        if self._addr_str(gl.message.sender_address) != job.freelancer:
            raise UserError("Only the freelancer can submit evidence")

        m_key = str(job_id) + "_" + str(milestone_id)
        if m_key not in self.milestones:
            raise UserError("Milestone not found")

        milestone = self.milestones[m_key]
        if milestone.state != "OPEN":
            raise UserError("Milestone is not open")
        if milestone.evidence_count >= bigint(2):
            raise UserError("Max 2 evidence URLs allowed per milestone")

        if milestone.evidence_count == bigint(0):
            milestone.evidence_url_1 = url
        else:
            milestone.evidence_url_2 = url

        milestone.evidence_count += bigint(1)
        self.milestones[m_key] = milestone

    @gl.public.write
    def open_dispute(self, job_id: str, milestone_id: str) -> None:
        if job_id not in self.jobs:
            raise UserError("Job not found")

        job = self.jobs[job_id]
        sender = self._addr_str(gl.message.sender_address)
        if sender != job.client and sender != job.freelancer:
            raise UserError("Only client or freelancer can open dispute")

        m_key = str(job_id) + "_" + str(milestone_id)
        if m_key not in self.milestones:
            raise UserError("Milestone not found")

        milestone = self.milestones[m_key]
        if milestone.state != "OPEN":
            raise UserError("Milestone is not open for dispute")
        if milestone.evidence_count == bigint(0):
            raise UserError("Cannot dispute before any evidence is submitted")

        milestone.state = "DISPUTED"
        self.milestones[m_key] = milestone

    @gl.public.write
    def resolve_escalated(self, job_id: str, milestone_id: str, freelancer_percentage: int) -> None:
        """Authorized completion path for ESCALATED milestones by client agreement or treasury authority."""
        if job_id not in self.jobs:
            raise UserError("Job not found")

        job = self.jobs[job_id]
        sender = self._addr_str(gl.message.sender_address)
        treasury_addr_str = self.treasury_address.lower() if self.treasury_address else ""
        
        if sender != job.client and sender.lower() != treasury_addr_str:
            raise UserError("Only client or treasury authority can resolve escalated milestone")

        if not (0 <= freelancer_percentage <= 100):
            raise UserError("Percentage must be between 0 and 100")

        m_key = str(job_id) + "_" + str(milestone_id)
        if m_key not in self.milestones:
            raise UserError("Milestone not found")

        milestone = self.milestones[m_key]
        if milestone.state != "ESCALATED":
            raise UserError("Milestone is not in ESCALATED state")

        ms_amount = milestone.amount
        freelancer_addr = Address(job.freelancer)
        client_addr = Address(job.client)

        if freelancer_percentage == 100:
            fee = (ms_amount * bigint(2)) // bigint(100)
            payout = ms_amount - fee
            if fee > bigint(0):
                gl.get_contract_at(self._get_treasury_addr()).emit_transfer(value=fee)
            if payout > bigint(0):
                gl.get_contract_at(freelancer_addr).emit_transfer(value=payout)
        elif freelancer_percentage == 0:
            if ms_amount > bigint(0):
                gl.get_contract_at(client_addr).emit_transfer(value=ms_amount)
        else:
            freelancer_share = (ms_amount * bigint(freelancer_percentage)) // bigint(100)
            client_share = ms_amount - freelancer_share
            f_fee = (freelancer_share * bigint(2)) // bigint(100)
            f_payout = freelancer_share - f_fee
            if f_fee > bigint(0):
                gl.get_contract_at(self._get_treasury_addr()).emit_transfer(value=f_fee)
            if f_payout > bigint(0):
                gl.get_contract_at(freelancer_addr).emit_transfer(value=f_payout)
            if client_share > bigint(0):
                gl.get_contract_at(client_addr).emit_transfer(value=client_share)

        milestone.state = "CLOSED"
        milestone.verdict = f"RESOLVED_ESCALATION_{freelancer_percentage}_PERCENT"
        milestone.reason = f"Escalated dispute settled by authorized party ({sender}) with {freelancer_percentage}% freelancer payout."
        self.milestones[m_key] = milestone

    @gl.public.write
    def adjudicate(self, job_id: str, milestone_id: str) -> None:
        m_key = str(job_id) + "_" + str(milestone_id)
        if m_key not in self.milestones:
            raise UserError("Milestone not found")

        milestone = self.milestones[m_key]
        job = self.jobs[str(job_id)]

        if milestone.state != "DISPUTED":
            raise UserError("Milestone is not disputed")

        ms_description = milestone.description
        ev_url_1 = milestone.evidence_url_1
        ev_url_2 = milestone.evidence_url_2
        ev_count = int(milestone.evidence_count)

        def _safe_parse(raw):
            try:
                if isinstance(raw, dict):
                    data = raw
                elif hasattr(raw, "calldata") and isinstance(raw.calldata, dict):
                    data = raw.calldata
                elif hasattr(raw, "content"):
                    return _safe_parse(raw.content)
                elif isinstance(raw, str):
                    text = raw.strip()
                    if text.startswith("```json"):
                        text = text[7:]
                    elif text.startswith("```"):
                        text = text[3:]
                    if text.endswith("```"):
                        text = text[:-3]
                    data = json.loads(text.strip())
                else:
                    return None

                verdict = str(data.get("verdict", "")).strip().upper()
                if verdict not in ("RELEASE", "REFUND", "PARTIAL", "ESCALATE"):
                    return None

                percentage = data.get("percentage", 0)
                if isinstance(percentage, float):
                    percentage = int(percentage)
                if not isinstance(percentage, int) or not (0 <= percentage <= 100):
                    return None

                if verdict == "RELEASE":
                    percentage = 100
                elif verdict == "REFUND":
                    percentage = 0
                elif verdict == "PARTIAL" and not (1 <= percentage <= 99):
                    return None

                confidence = data.get("confidence", 0)
                if isinstance(confidence, float):
                    confidence = int(confidence)
                if not isinstance(confidence, int) or not (0 <= confidence <= 100):
                    return None

                reason = str(data.get("reason", ""))

                # Bind confidence directly to verdict: Low confidence falls back to ESCALATE
                if confidence < 60 and verdict != "ESCALATE":
                    verdict = "ESCALATE"
                    percentage = 0
                    reason = f"[low_confidence: {confidence}%] " + reason

                return {
                    "verdict": verdict,
                    "percentage": percentage,
                    "confidence": confidence,
                    "reason": reason[:1000],
                }
            except Exception:
                return None

        def leader_fn():
            evidence_texts = []

            if ev_count >= 1 and ev_url_1 != "":
                try:
                    res = gl.nondet.web.render(ev_url_1, mode="text")
                    text = res.content if hasattr(res, "content") else str(res)
                    if not text or len(text.strip()) < 10:
                        evidence_texts.append(f"Evidence 1 ({ev_url_1}): [EMPTY_OR_FETCH_FAILED]")
                    else:
                        evidence_texts.append(f"Evidence 1 ({ev_url_1}):\n{text[:3000]}")
                except Exception as e:
                    evidence_texts.append(f"Evidence 1 ({ev_url_1}) error: {str(e)}")

            if ev_count >= 2 and ev_url_2 != "":
                try:
                    res = gl.nondet.web.render(ev_url_2, mode="text")
                    text = res.content if hasattr(res, "content") else str(res)
                    if not text or len(text.strip()) < 10:
                        evidence_texts.append(f"Evidence 2 ({ev_url_2}): [EMPTY_OR_FETCH_FAILED]")
                    else:
                        evidence_texts.append(f"Evidence 2 ({ev_url_2}):\n{text[:3000]}")
                except Exception as e:
                    evidence_texts.append(f"Evidence 2 ({ev_url_2}) error: {str(e)}")

            combined_evidence = "\n\n".join(evidence_texts)

            prompt = f"""
SYSTEM: You are an impartial dispute resolution AI for a freelancer platform.
Milestone Description: {ms_description}

Evidence Submitted:
{combined_evidence}

Rules:
- RELEASE (percentage=100): Evidence fully satisfies the milestone requirements.
- REFUND (percentage=0): Evidence is invalid, empty, irrelevant, or fails completely.
- PARTIAL (percentage=1-99): Evidence partially satisfies requirements.
- If confidence < 60 or evidence is unverifiable, set verdict to ESCALATE.

OUTPUT ONLY RAW JSON:
{{
  "verdict": "RELEASE" | "REFUND" | "PARTIAL" | "ESCALATE",
  "percentage": 0-100,
  "confidence": 0-100,
  "reason": "explanation string"
}}
"""
            try:
                raw = gl.nondet.exec_prompt(prompt, response_format="json")
                parsed = _safe_parse(raw)
                if parsed is None:
                    return {"verdict": "ESCALATE", "percentage": 0, "confidence": 0, "reason": "parse_failed"}
                return parsed
            except Exception as e:
                return {"verdict": "ESCALATE", "percentage": 0, "confidence": 0, "reason": f"LLM error: {str(e)}"}

        def validator_fn(leader_res) -> bool:
            if not isinstance(leader_res, gl.vm.Return):
                return False

            leader_data = leader_res.calldata if hasattr(leader_res, "calldata") else leader_res
            leader = _safe_parse(leader_data)
            if leader is None:
                return False

            mine = _safe_parse(leader_fn())
            if mine is None:
                return False

            # Semantic agreement on verified payout fields
            return (
                mine["verdict"] == leader["verdict"]
                and mine["percentage"] == leader["percentage"]
            )

        result_raw = gl.vm.run_nondet(leader_fn, validator_fn)
        result = _safe_parse(result_raw)

        if result is None:
            result = {"verdict": "ESCALATE", "percentage": 0, "confidence": 0, "reason": "adjudication_failed"}

        verdict = result["verdict"]
        percentage = result["percentage"]
        confidence = result["confidence"]
        reason = result["reason"]

        ms_amount = milestone.amount
        freelancer_addr = Address(job.freelancer)
        client_addr = Address(job.client)

        if verdict == "ESCALATE":
            milestone.state = "ESCALATED"
            milestone.verdict = "ESCALATE"
            milestone.reason = reason
            self.milestones[m_key] = milestone
            return

        fee = (ms_amount * bigint(2)) // bigint(100)

        if verdict == "RELEASE":
            payout = ms_amount - fee
            if fee > bigint(0):
                gl.get_contract_at(self._get_treasury_addr()).emit_transfer(value=fee)
            if payout > bigint(0):
                gl.get_contract_at(freelancer_addr).emit_transfer(value=payout)

        elif verdict == "REFUND":
            if ms_amount > bigint(0):
                gl.get_contract_at(client_addr).emit_transfer(value=ms_amount)

        elif verdict == "PARTIAL":
            freelancer_share = (ms_amount * bigint(percentage)) // bigint(100)
            client_share = ms_amount - freelancer_share
            f_fee = (freelancer_share * bigint(2)) // bigint(100)
            f_payout = freelancer_share - f_fee
            if f_fee > bigint(0):
                gl.get_contract_at(self._get_treasury_addr()).emit_transfer(value=f_fee)
            if f_payout > bigint(0):
                gl.get_contract_at(freelancer_addr).emit_transfer(value=f_payout)
            if client_share > bigint(0):
                gl.get_contract_at(client_addr).emit_transfer(value=client_share)

        milestone.state = "CLOSED"
        milestone.verdict = verdict
        milestone.reason = reason
        self.milestones[m_key] = milestone

    @gl.public.view
    def get_job(self, job_id: str) -> str:
        if job_id not in self.jobs:
            raise UserError("Job not found")
        job = self.jobs[job_id]
        return json.dumps({
            "id": str(job.id),
            "client": job.client,
            "freelancer": job.freelancer,
            "milestones_count": str(job.milestones_count),
        })

    @gl.public.view
    def get_milestone(self, job_id: str, milestone_id: str) -> str:
        m_key = str(job_id) + "_" + str(milestone_id)
        if m_key not in self.milestones:
            raise UserError("Milestone not found")
        m = self.milestones[m_key]
        return json.dumps({
            "id": str(m.id),
            "job_id": str(m.job_id),
            "description": m.description,
            "amount": str(m.amount),
            "evidence_url_1": m.evidence_url_1,
            "evidence_url_2": m.evidence_url_2,
            "evidence_count": str(m.evidence_count),
            "state": m.state,
            "verdict": m.verdict,
            "reason": m.reason,
        })
