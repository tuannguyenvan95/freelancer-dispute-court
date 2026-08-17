import sys
import os
import unittest
from unittest.mock import MagicMock
import json

# --- GenLayer SDK Mock Infrastructure for Offline Regression Testing ---
class MockAddress(str):
    @property
    def as_hex(self):
        return str(self)

class MockBigInt(int):
    pass

class MockUserError(Exception):
    pass

class MockReturn:
    def __init__(self, calldata):
        self.calldata = calldata

class MockContractStub:
    def __init__(self, address, transfer_tracker):
        self.address = str(address)
        self.transfer_tracker = transfer_tracker

    def emit_transfer(self, value):
        self.transfer_tracker.append({"to": self.address, "value": int(value)})

class MockGL:
    class Contract:
        pass

    class public:
        @staticmethod
        def view(fn): return fn
        @staticmethod
        def write(fn): return fn

    class message:
        value = MockBigInt(100)
        sender_address = MockAddress("0xClient_111")

    class nondet:
        class web:
            @staticmethod
            def render(url, mode="text"):
                pass
        @staticmethod
        def exec_prompt(prompt, response_format="json"):
            pass

    class vm:
        Return = MockReturn
        @staticmethod
        def run_nondet(leader_fn, validator_fn):
            res = leader_fn()
            ret = MockReturn(calldata=res)
            valid = validator_fn(ret)
            if not valid:
                raise Exception("Validator rejected leader payload")
            return res

    def __init__(self):
        self.transfers = []

    def get_contract_at(self, address):
        return MockContractStub(address, self.transfers)

# Setup decorator mocking
MockGL.public.write.payable = lambda fn: fn

# Inject mocks into sys.modules
mock_genlayer_mod = MagicMock()
mock_genlayer_mod.gl = MockGL()
mock_genlayer_mod.allow_storage = lambda cls: cls
mock_genlayer_mod.Address = MockAddress
mock_genlayer_mod.bigint = MockBigInt
mock_genlayer_mod.u256 = MockBigInt
mock_genlayer_mod.UserError = MockUserError
mock_genlayer_mod.TreeMap = dict

sys.modules["genlayer"] = mock_genlayer_mod

# Import contract
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from contracts import dispute_court

class TestOfflineDisputeCourt(unittest.TestCase):

    def setUp(self):
        self.gl_instance = mock_genlayer_mod.gl
        self.gl_instance.transfers = []
        
        self.contract = dispute_court.Contract("0xTreasury_123")
        self.contract.jobs = {}
        self.contract.milestones = {}

    def test_01_happy_path_release(self):
        client = MockAddress("0xClient_111")
        freelancer = "0xFreelancer_222"
        
        # Create Job
        self.gl_instance.message.sender_address = client
        self.contract.create_job(freelancer)
        
        # Add Milestone (1000 wei)
        self.gl_instance.message.value = MockBigInt(1000)
        self.contract.add_milestone("1", "Frontend UI")
        
        # Submit Evidence
        self.gl_instance.message.sender_address = MockAddress(freelancer)
        self.contract.submit_evidence("1", "1", "https://github.com/pr/1")
        
        # Open Dispute
        self.gl_instance.message.sender_address = client
        self.contract.open_dispute("1", "1")
        
        # Mock Web & LLM
        self.gl_instance.nondet.web.render = lambda url, mode="text": "Evidence UI loaded successfully."
        self.gl_instance.nondet.exec_prompt = lambda prompt, response_format="json": {
            "verdict": "RELEASE",
            "percentage": 100,
            "confidence": 95,
            "reason": "Milestone delivered completely."
        }
        
        # Adjudicate
        self.contract.adjudicate("1", "1")
        
        # Assertions
        ms = json.loads(self.contract.get_milestone("1", "1"))
        self.assertEqual(ms["state"], "CLOSED")
        self.assertEqual(ms["verdict"], "RELEASE")
        
        # Protocol fee: 2% (20) to treasury, 980 to freelancer
        transfers = self.gl_instance.transfers
        self.assertEqual(len(transfers), 2)
        self.assertEqual(transfers[0]["to"], "0xTreasury_123")
        self.assertEqual(transfers[0]["value"], 20)
        self.assertEqual(transfers[1]["to"], "0xFreelancer_222")
        self.assertEqual(transfers[1]["value"], 980)

    def test_02_low_confidence_escalates_and_preserves_escrow(self):
        client = MockAddress("0xClient_111")
        freelancer = "0xFreelancer_222"
        
        self.gl_instance.message.sender_address = client
        self.contract.create_job(freelancer)
        self.gl_instance.message.value = MockBigInt(1000)
        self.contract.add_milestone("1", "Backend API")
        
        self.gl_instance.message.sender_address = MockAddress(freelancer)
        self.contract.submit_evidence("1", "1", "https://api-demo.com")
        
        self.gl_instance.message.sender_address = client
        self.contract.open_dispute("1", "1")
        
        # LLM returns low confidence (50% < 60%)
        self.gl_instance.nondet.web.render = lambda url, mode="text": "Ambiguous API output."
        self.gl_instance.nondet.exec_prompt = lambda prompt, response_format="json": {
            "verdict": "RELEASE",
            "percentage": 100,
            "confidence": 50,
            "reason": "Unsure about database schema."
        }
        
        # Adjudicate
        self.contract.adjudicate("1", "1")
        
        ms = json.loads(self.contract.get_milestone("1", "1"))
        self.assertEqual(ms["state"], "ESCALATED")
        self.assertEqual(ms["verdict"], "ESCALATE")
        self.assertEqual(len(self.gl_instance.transfers), 0, "No funds should move on ESCALATE")

    def test_03_partial_settlement(self):
        client = MockAddress("0xClient_111")
        freelancer = "0xFreelancer_222"
        
        self.gl_instance.message.sender_address = client
        self.contract.create_job(freelancer)
        self.gl_instance.message.value = MockBigInt(1000)
        self.contract.add_milestone("1", "Design Assets")
        
        self.gl_instance.message.sender_address = MockAddress(freelancer)
        self.contract.submit_evidence("1", "1", "https://figma.com/file")
        
        self.gl_instance.message.sender_address = client
        self.contract.open_dispute("1", "1")
        
        # LLM returns 60% partial payout
        self.gl_instance.nondet.web.render = lambda url, mode="text": "Partial designs available."
        self.gl_instance.nondet.exec_prompt = lambda prompt, response_format="json": {
            "verdict": "PARTIAL",
            "percentage": 60,
            "confidence": 85,
            "reason": "60% completed."
        }
        
        self.contract.adjudicate("1", "1")
        
        ms = json.loads(self.contract.get_milestone("1", "1"))
        self.assertEqual(ms["state"], "CLOSED")
        self.assertEqual(ms["verdict"], "PARTIAL")
        
        # 1000 total: freelancer share = 600 (fee 2% = 12, payout = 588), client share = 400
        transfers = self.gl_instance.transfers
        self.assertEqual(len(transfers), 3)
        self.assertEqual(transfers[0]["to"], "0xTreasury_123")
        self.assertEqual(transfers[0]["value"], 12)
        self.assertEqual(transfers[1]["to"], "0xFreelancer_222")
        self.assertEqual(transfers[1]["value"], 588)
        self.assertEqual(transfers[2]["to"], "0xClient_111")
        self.assertEqual(transfers[2]["value"], 400)

if __name__ == "__main__":
    unittest.main(verbosity=2)
