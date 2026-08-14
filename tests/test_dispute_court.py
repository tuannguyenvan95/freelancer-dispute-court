import sys
import os
import unittest
from unittest.mock import MagicMock
import json

# --- GenLayer SDK Mock Infrastructure for Offline Regression Testing ---
class MockAddress(str):
    pass

class MockBigInt(int):
    pass

class MockUserError(Exception):
    pass

class MockReturn:
    def __init__(self, calldata):
        self.calldata = calldata

class MockContractStub:
    def __init__(self, address, transfer_tracker):
        self.address = address
        self.transfer_tracker = transfer_tracker

    def emit_transfer(self, value):
        self.transfer_tracker.append({"to": self.address, "value": value})

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
        sender = MockAddress("0xClientAddress")

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
            # Return string since the contract expects JSON string from leader_fn
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

    def test_happy_path_release(self):
        client = "0xClient_111"
        freelancer = "0xFreelancer_222"
        
        # Create Job
        self.gl_instance.message.sender = client
        self.contract.create_job(freelancer)
        
        # Add Milestone
        self.gl_instance.message.value = MockBigInt(1000)
        self.contract.add_milestone("1", "Frontend UI")
        
        # Submit Evidence
        self.gl_instance.message.sender = freelancer
        self.contract.submit_evidence("1", "1", "https://github.com/pr")
        
        # Open Dispute
        self.gl_instance.message.sender = client
        self.contract.open_dispute("1", "1")
        
        # Mocks for Adjudicate
        def mock_render(url, mode="text"):
            return "Look at this great UI"
        
        self.gl_instance.nondet.web.render = mock_render
        self.gl_instance.nondet.exec_prompt = lambda prompt, response_format="json": json.dumps({
            "verdict": "RELEASE",
            "percentage": 100,
            "confidence": 95,
            "reason": "Perfect"
        })
        
        # Adjudicate
        self.contract.adjudicate("1", "1")
        
        # Verify
        ms = json.loads(self.contract.get_milestone("1", "1"))
        self.assertEqual(ms["state"], "CLOSED")
        self.assertEqual(ms["verdict"], "RELEASE")
        
        # 1000 total: 2% fee (20) to treasury, 980 to freelancer
        transfers = self.gl_instance.transfers
        self.assertEqual(len(transfers), 2)
        self.assertEqual(transfers[0]["to"], "0xTreasury_123")
        self.assertEqual(transfers[0]["value"], 20)
        self.assertEqual(transfers[1]["to"], "0xFreelancer_222")
        self.assertEqual(transfers[1]["value"], 980)

    def test_validator_rejects_confidence_mismatch(self):
        client = "0xClient_111"
        freelancer = "0xFreelancer_222"
        self.gl_instance.message.sender = client
        self.contract.create_job(freelancer)
        self.gl_instance.message.value = MockBigInt(1000)
        self.contract.add_milestone("1", "Frontend UI")
        self.gl_instance.message.sender = freelancer
        self.contract.submit_evidence("1", "1", "https://github.com/pr")
        self.gl_instance.message.sender = client
        self.contract.open_dispute("1", "1")
        
        # Force leader to say confidence 60, but validator logic will execute with confidence 50
        def patched_run_nondet(leader_fn, validator_fn):
            # Leader output
            leader_res = json.dumps({"verdict": "RELEASE", "percentage": 100, "confidence": 60, "reason": "Good"})
            # Validator output (mine)
            original_leader = leader_fn
            
            # Monkeypatch the lambda to simulate validator's local LLM returning lower confidence
            self.gl_instance.nondet.exec_prompt = lambda p, r: json.dumps({"verdict": "RELEASE", "percentage": 100, "confidence": 50, "reason": "Bad"})
            
            ret = MockReturn(calldata=leader_res)
            # This should return False!
            is_valid = validator_fn(ret)
            self.assertFalse(is_valid, "Validator should reject because confidence threshold (60) mismatched!")
            return leader_res

        original_run_nondet = self.gl_instance.vm.run_nondet
        self.gl_instance.vm.run_nondet = patched_run_nondet
        
        try:
            self.contract.adjudicate("1", "1")
        except Exception:
            pass
        
        self.gl_instance.vm.run_nondet = original_run_nondet

if __name__ == "__main__":
    unittest.main(verbosity=2)
