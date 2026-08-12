import json
import pytest

def test_happy_path(gl_client):
    treasury_addr = "0x9999999999999999999999999999999999999999"
    client_addr = gl_client.default_account
    freelancer_addr = "0x2222222222222222222222222222222222222222"
    
    contract = gl_client.deploy_contract("contracts/dispute_court.py", args=[treasury_addr])
    
    contract.connect(client_addr).create_job(args=[freelancer_addr]).transact()
    assert contract.get_job_counter().call() == 1
    
    contract.connect(client_addr).add_milestone(args=["1", "Build frontend"]).transact(value=1000)
    
    contract.connect(freelancer_addr).submit_evidence(args=["1", "1", "https://github.com/demo/pr/1"]).transact()
    contract.connect(freelancer_addr).submit_evidence(args=["1", "1", "https://demo.app"]).transact()
    
    milestone = contract.get_milestone(args=["1", "1"]).call()
    assert milestone.state == "OPEN"
    
    contract.connect(client_addr).open_dispute(args=["1", "1"]).transact()
    
    milestone = contract.get_milestone(args=["1", "1"]).call()
    assert milestone.state == "DISPUTED"
    
    gl_client.provider.make_request(
        method="sim_installMocks",
        params={
            "llm_mocks": {
                ".*": json.dumps({
                    "verdict": "RELEASE",
                    "percentage": 100,
                    "confidence": 95,
                    "reason": "Evidence looks perfect."
                })
            },
            "web_mocks": {
                ".*": {"status": 200, "body": "Looks good!"}
            }
        }
    )
    
    contract.connect(client_addr).adjudicate(args=["1", "1"]).transact()
    
    milestone = contract.get_milestone(args=["1", "1"]).call()
    assert milestone.state == "CLOSED"
    assert milestone.verdict == "RELEASE"

def test_edge_cases(gl_client):
    treasury_addr = "0x9999999999999999999999999999999999999999"
    client_addr = gl_client.default_account
    freelancer_addr = "0x2222222222222222222222222222222222222222"
    
    contract = gl_client.deploy_contract("contracts/dispute_court.py", args=[treasury_addr])
    contract.connect(client_addr).create_job(args=[freelancer_addr]).transact()
    
    # 1. 0 amount milestone
    try:
        contract.connect(client_addr).add_milestone(args=["1", "Test"]).transact(value=0)
        assert False, "Should have raised UserError"
    except Exception as e:
        assert "zero" in str(e).lower()

    contract.connect(client_addr).add_milestone(args=["1", "Test2"]).transact(value=500)
    
    # 2. dispute without evidence
    try:
        contract.connect(client_addr).open_dispute(args=["1", "1"]).transact()
        assert False, "Should have raised UserError"
    except Exception as e:
        assert "evidence" in str(e).lower()
