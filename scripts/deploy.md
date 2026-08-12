# Deploying on GenLayer studionet

This guide outlines how to deploy and test the **Freelancer Dispute Court** contract using GenLayer Studio.

## 1. Prerequisites

1. Head to [Studio.genlayer.com](https://studio.genlayer.com).
2. Connect your MetaMask wallet. Ensure it is connected to the **GenLayer studionet** (Chain ID: `61999` or `0xF1EF`).
3. You will need some Testnet GEN tokens on `studionet`. 
   - Open the **Accounts** panel in GenLayer Studio.
   - Click **Fund** to receive GEN tokens. 

> **Important:** Do not refer to this as a generic testnet in external communications. It is exclusively the **studionet**.

## 2. Deploying the Contract

1. In GenLayer Studio, create a new file named `dispute_court.py`.
2. Paste the exact contents of `contracts/dispute_court.py` into this file.
3. Make sure the header `v0.2.16` and the dependency `py-genlayer` exactly match what the Studio currently provides for templates.
4. Click **Deploy**.
5. Your MetaMask will prompt you to sign the transaction.
6. Once deployed, note the **Contract Address**. You will need to copy this into the frontend application.

## 3. Testing in Studio

Before using the frontend, you can test the contract directly in the Studio panel:

1. **Create a Job:**
   - Call `create_job(freelancer_address, "description of work")`
   - Specify a `Value` (e.g., `1000` wei/GEN) in the transaction settings before clicking run.
2. **Submit Evidence:**
   - Switch your active wallet to the freelancer's address.
   - Call `submit_evidence(job_id, "https://github.com/my/pr")`.
3. **Open Dispute:**
   - Call `open_dispute(job_id)`.
4. **Adjudicate (The AI Judge):**
   - Call `adjudicate(job_id)`.
   - This transaction will be non-deterministic. GenLayer validators will fetch the URLs and run the prompt. Wait for the transaction to reach consensus (it might take 10-20 seconds).
   - Once completed, check the transaction result. The result will be `SUCCESS`.

## 4. Hooking up the Frontend

1. Open `frontend/src/App.tsx` (or your configuration file).
2. Update the `CONTRACT_ADDRESS` constant to the deployed address from step 2.
3. Run the frontend (`npm run dev`) and interact with it!
