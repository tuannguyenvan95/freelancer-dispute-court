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
    client: Address
    freelancer: Address
    milestones_count: bigint


class Contract(gl.Contract):
    jobs: TreeMap[str, Job]
    milestones: TreeMap[str, Milestone]
    job_counter: bigint
    treasury_address: str

    def __init__(self, treasury_addr: str):
        self.job_counter = bigint(0)
        self.treasury_address = treasury_addr

    @gl.public.write
    def create_job(self, freelancer_addr: str) -> None:
        self.job_counter += bigint(1)
        job_id = self.job_counter

        self.jobs[str(job_id)] = Job(
            id=job_id,
            client=gl.message.sender,
            freelancer=Address(freelancer_addr),
            milestones_count=bigint(0)
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
        if gl.message.sender != job.client:
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
            reason=""
        )

        self.jobs[job_id] = job

    @gl.public.write
    def submit_evidence(self, job_id: str, milestone_id: str, url: str) -> None:
        if job_id not in self.jobs:
            raise UserError("Job not found")

        job = self.jobs[job_id]
        if gl.message.sender != job.freelancer:
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
        if gl.message.sender != job.client and gl.message.sender != job.freelancer:
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
    def adjudicate(self, job_id: str, milestone_id: str) -> None:
        m_key = str(job_id) + "_" + str(milestone_id)
        if m_key not in self.milestones:
            raise UserError("Milestone not found")

        milestone = self.milestones[m_key]
        job = self.jobs[str(job_id)]

        if milestone.state != "DISPUTED":
            raise UserError("Milestone is not disputed")
        if milestone.state == "CLOSED":
            raise UserError("Milestone is already closed")

        # Capture data BEFORE entering nondet block
        ms_description = milestone.description
        ev_url_1 = milestone.evidence_url_1
        ev_url_2 = milestone.evidence_url_2
        ev_count = int(milestone.evidence_count)

        def _safe_parse(raw):
            """Nhận cả dict lẫn string. Trả về dict sạch hoặc None."""
            try:
                if isinstance(raw, dict):
                    data = raw
                elif isinstance(raw, str):
                    raw = raw.strip()
                    if raw.startswith("```"):
                        parts = raw.split("```")
                        if len(parts) >= 2:
                            raw = parts[1]
                            if raw.startswith("json"):
                                raw = raw[4:]
                    data = json.loads(raw)
                else:
                    return None

                verdict = data.get("verdict")
                if verdict not in ("RELEASE", "REFUND", "PARTIAL"):
                    return None

                percentage = data.get("percentage", 0)
                if not isinstance(percentage, (int, float)) or not (0 <= percentage <= 100):
                    return None

                confidence = data.get("confidence", 0)
                if not isinstance(confidence, (int, float)) or not (0 <= confidence <= 100):
                    return None

                reason = data.get("reason", "")
                if not isinstance(reason, str):
                    return None

                return {
                    "verdict": str(verdict),
                    "percentage": int(percentage),
                    "confidence": int(confidence),
                    "reason": reason[:2000]
                }
            except Exception:
                return None

        def leader_fn():
            evidence_texts = []

            if ev_count >= 1 and ev_url_1 != "":
                try:
                    text = gl.nondet.web.render(ev_url_1, mode="text")
                    evidence_texts.append("Evidence from " + ev_url_1 + ":\n" + text)
                except Exception as e:
                    evidence_texts.append("Evidence from " + ev_url_1 + " could not be loaded: " + str(e))

            if ev_count >= 2 and ev_url_2 != "":
                try:
                    text = gl.nondet.web.render(ev_url_2, mode="text")
                    evidence_texts.append("Evidence from " + ev_url_2 + ":\n" + text)
                except Exception as e:
                    evidence_texts.append("Evidence from " + ev_url_2 + " could not be loaded: " + str(e))

            combined_evidence = "\n\n".join(evidence_texts)

            prompt = (
                "You are an impartial dispute resolution AI for a freelancer platform.\n\n"
                "Milestone Description: " + ms_description + "\n\n"
                "Evidence Submitted by Freelancer:\n" + combined_evidence + "\n\n"
                "Based on the evidence, determine the outcome of the dispute for this milestone.\n"
                "You must return ONLY a raw JSON object with no markdown wrappers or backticks.\n\n"
                "Schema:\n"
                '{"verdict": "RELEASE" or "REFUND" or "PARTIAL", '
                '"percentage": int 0-100, '
                '"confidence": int 0-100, '
                '"reason": "string explaining your reasoning"}'
            )

            raw = gl.nondet.exec_prompt(prompt, response_format="json")
            parsed = _safe_parse(raw)
            if parsed is None:
                # Trả về object đặc biệt để validator reject
                return {
                    "verdict": "INVALID",
                    "percentage": 0,
                    "confidence": 0,
                    "reason": "parse_failed"
                }
            return parsed

        def validator_fn(leader_res) -> bool:
            if not isinstance(leader_res, gl.vm.Return):
                return False

            leader = _safe_parse(leader_res.calldata)
            if leader is None or leader.get("verdict") == "INVALID":
                return False

            mine = _safe_parse(leader_fn())
            if mine is None or mine.get("verdict") == "INVALID":
                return False

            # === BIND MỌI FIELD ẢNH HƯỞNG ĐẾN PAYOUT ===
            # verdict + percentage + confidence đều được so khớp chặt
            return (
                mine["verdict"] == leader["verdict"]
                and mine["percentage"] == leader["percentage"]
                and mine["confidence"] == leader["confidence"]
            )

        result_raw = gl.vm.run_nondet(leader_fn, validator_fn)
        result = _safe_parse(result_raw)

        if result is None or result.get("verdict") == "INVALID":
            raise UserError("AI returned invalid or unparseable result")

        verdict = result["verdict"]
        confidence = result["confidence"]
        percentage = result["percentage"]
        reason = result["reason"]

        if confidence < 60:
            raise UserError("AI confidence too low to adjudicate autonomously")

        ms_amount = milestone.amount
        freelancer_addr = job.freelancer
        client_addr = job.client

        # Protocol fee: 2%
        fee = (ms_amount * bigint(2)) // bigint(100)

        if verdict == "RELEASE":
            payout = ms_amount - fee
            if fee > bigint(0):
                gl.get_contract_at(Address(self.treasury_address)).emit_transfer(value=fee)
            if payout > bigint(0):
                gl.get_contract_at(freelancer_addr).emit_transfer(value=payout)

        elif verdict == "REFUND":
            gl.get_contract_at(client_addr).emit_transfer(value=ms_amount)

        elif verdict == "PARTIAL":
            freelancer_share = (ms_amount * bigint(percentage)) // bigint(100)
            client_share = ms_amount - freelancer_share
            f_fee = (freelancer_share * bigint(2)) // bigint(100)
            f_payout = freelancer_share - f_fee
            if f_fee > bigint(0):
                gl.get_contract_at(Address(self.treasury_address)).emit_transfer(value=f_fee)
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
            "client": str(job.client),
            "freelancer": str(job.freelancer),
            "milestones_count": str(job.milestones_count)
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
            "reason": m.reason
        })
