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
        
        self.gl_instance.message.sender_address = client
        self.contract.create_job(freelancer)
        
        self.gl_instance.message.value = MockBigInt(1000)
        self.contract.add_milestone("1", "Frontend UI")
        
        self.gl_instance.message.sender_address = MockAddress(freelancer)
        self.contract.submit_evidence("1", "1", "https://github.com/pr/1")
        
        self.gl_instance.message.sender_address = client
        self.contract.open_dispute("1", "1")
        
        self.gl_instance.nondet.web.render = lambda url, mode="text": "Evidence UI loaded successfully."
        self.gl_instance.nondet.exec_prompt = lambda prompt, response_format="json": {
            "verdict": "RELEASE",
            "percentage": 100,
            "confidence": 95,
            "reason": "Milestone delivered completely."
        }
        
        self.contract.adjudicate("1", "1")
        
        ms = json.loads(self.contract.get_milestone("1", "1"))
        self.assertEqual(ms["state"], "CLOSED")
        self.assertEqual(ms["verdict"], "RELEASE")
        
        transfers = self.gl_instance.transfers
        self.assertEqual(len(transfers), 2)
        self.assertEqual(transfers[0]["to"], "0xTreasury_123")
        self.assertEqual(transfers[0]["value"], 20)
        self.assertEqual(transfers[1]["to"], "0xFreelancer_222")
        self.assertEqual(transfers[1]["value"], 980)

    def test_02_open_milestone_acceptance_route(self):
        """NEW ROUTE TEST: Client directly accepts OPEN milestone without dispute."""
        client = MockAddress("0xClient_111")
        freelancer = "0xFreelancer_222"
        
        self.gl_instance.message.sender_address = client
        self.contract.create_job(freelancer)
        self.gl_instance.message.value = MockBigInt(1000)
        self.contract.add_milestone("1", "Acceptance Test")
        
        # Client accepts directly
        self.contract.accept_milestone("1", "1")
        
        ms = json.loads(self.contract.get_milestone("1", "1"))
        self.assertEqual(ms["state"], "CLOSED")
        self.assertEqual(ms["verdict"], "ACCEPTED_BY_CLIENT")
        
        transfers = self.gl_instance.transfers
        self.assertEqual(len(transfers), 2)
        self.assertEqual(transfers[0]["to"], "0xTreasury_123")
        self.assertEqual(transfers[0]["value"], 20)
        self.assertEqual(transfers[1]["to"], "0xFreelancer_222")
        self.assertEqual(transfers[1]["value"], 980)

    def test_03_open_milestone_cancellation_route(self):
        """NEW ROUTE TEST: Client cancels OPEN milestone before evidence submission."""
        client = MockAddress("0xClient_111")
        freelancer = "0xFreelancer_222"
        
        self.gl_instance.message.sender_address = client
        self.contract.create_job(freelancer)
        self.gl_instance.message.value = MockBigInt(500)
        self.contract.add_milestone("1", "Cancellation Test")
        
        # Client cancels
        self.contract.cancel_milestone("1", "1")
        
        ms = json.loads(self.contract.get_milestone("1", "1"))
        self.assertEqual(ms["state"], "CLOSED")
        self.assertEqual(ms["verdict"], "CANCELLED_BY_CLIENT")
        
        transfers = self.gl_instance.transfers
        self.assertEqual(len(transfers), 1)
        self.assertEqual(transfers[0]["to"], "0xClient_111")
        self.assertEqual(transfers[0]["value"], 500)

    def test_04_escalated_milestone_resolution_route(self):
        """NEW ROUTE TEST: Escalated milestone resolved by authorized party."""
        client = MockAddress("0xClient_111")
        freelancer = "0xFreelancer_222"
        
        self.gl_instance.message.sender_address = client
        self.contract.create_job(freelancer)
        self.gl_instance.message.value = MockBigInt(1000)
        self.contract.add_milestone("1", "Escalation Resolution Test")
        
        self.gl_instance.message.sender_address = MockAddress(freelancer)
        self.contract.submit_evidence("1", "1", "https://demo.com")
        
        self.gl_instance.message.sender_address = client
        self.contract.open_dispute("1", "1")
        
        # AI returns low confidence (50% < 60%)
        self.gl_instance.nondet.web.render = lambda url, mode="text": "Ambiguous evidence"
        self.gl_instance.nondet.exec_prompt = lambda prompt, response_format="json": {
            "verdict": "RELEASE",
            "percentage": 100,
            "confidence": 50,
            "reason": "Low confidence"
        }
        
        self.contract.adjudicate("1", "1")
        ms = json.loads(self.contract.get_milestone("1", "1"))
        self.assertEqual(ms["state"], "ESCALATED")
        
        # Client settles escalated dispute 50/50
        self.gl_instance.transfers = []
        self.contract.resolve_escalated("1", "1", freelancer_percentage=50)
        
        ms_after = json.loads(self.contract.get_milestone("1", "1"))
        self.assertEqual(ms_after["state"], "CLOSED")
        self.assertIn("RESOLVED_ESCALATION_50_PERCENT", ms_after["verdict"])
        
        transfers = self.gl_instance.transfers
        self.assertEqual(len(transfers), 3)
        self.assertEqual(transfers[0]["to"], "0xTreasury_123")
        self.assertEqual(transfers[0]["value"], 10)
        self.assertEqual(transfers[1]["to"], "0xFreelancer_222")
        self.assertEqual(transfers[1]["value"], 490)
        self.assertEqual(transfers[2]["to"], "0xClient_111")
        self.assertEqual(transfers[2]["value"], 500)

if __name__ == "__main__":
    unittest.main(verbosity=2)
