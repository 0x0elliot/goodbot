import express from "express";
import dotenv from "dotenv";
import { ethers } from "ethers";
import { BrianCoinbaseSDK } from "@brian-ai/cdp-sdk";

// import { NLProcessor } from "./nlProcessor";

import Instructor from "@instructor-ai/instructor";
// import OpenAI from "openai";
import Groq from "groq-sdk";

// import { ContractActionSchema } from "./schemas";
import { z } from "zod";

import { Coinbase, Wallet } from "@coinbase/coinbase-sdk";

const ContractActionSchema = z.object({
  method: z.string().describe("The smart contract method to call"),
  args: z.record(z.any()).describe("Arguments for the contract method call"),
});

dotenv.config();

const app = express();
app.use(express.json());

class ContractService {
  constructor(contractAddress, contractAbi, wallet) {
    this.contractAddress = contractAddress;
    this.contractAbi = contractAbi;
    this.wallet = wallet; // BrianCoinbaseSDK wallet instance
  }

  async executeAction({ method, args }) {
    try {
      // Use the initialized SDK wallet to invoke contract
      console.log(this.wallet);
      const contractInvocation = await this.wallet.invokeContract({
        contractAddress: this.contractAddress,
        method: method,
        args: args,
        abi: this.contractAbi,
      });

      // Wait for transaction confirmation
      const result = await contractInvocation.wait();
      return result;
    } catch (error) {
      throw new Error(`Contract execution failed: ${error.message}`);
    }
  }
}

class NLProcessor {
  client;
  contractAbi;

  constructor(apiKey, contractAbi) {
    const oai = new Groq({
      apiKey: "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",
    });
    this.client = Instructor({
      client: oai,
      mode: "FUNCTIONS",
    });
    this.contractAbi = contractAbi;
  }

  async processUserInput(message) {
    const systemContext = `Given this contract ABI: ${JSON.stringify(
      this.contractAbi
    )}`;

    const action = await this.client.chat.completions.create({
      messages: [
        { role: "system", content: systemContext },
        { role: "user", content: message },
      ],
      model: "llama-3.3-70b-versatile",
      response_model: {
        schema: ContractActionSchema,
        name: "ContractAction",
      },
    });

    return action;
  }
}

// Initialize base SDK once
const brianCDPSDK = new BrianCoinbaseSDK({
  brianApiKey: process.env.BRIAN_API_KEY,
  coinbaseApiKeyName: process.env.CDP_SDK_API_KEY_NAME,
  coinbaseApiKeySecret: process.env.CDP_SDK_API_KEY_SECRET,
});
await brianCDPSDK.importWallet({
  walletId: "85becdbc-69ab-4f57-9bd7-2024b5a3d826",
  seed: "347f5892c4cf26584cb2b91d5395ed504ee9b37a5ef5258f2a868c8c0cad3ecd",
});
const sessions = new Map();
// Coinbase.configure({
//     apiKey: "organizations/121088c5-a046-4203-aaa8-2f1d91ae6fb7/apiKeys/0789b180-24a0-4708-a091-749f8ab4d045",
//     apiSecret: "-----BEGIN EC PRIVATE KEY-----\nMHcCAQEEIDx7EY9nNSKS1u4XiJTMmqB9QixDoJZJe3rf5hFlJqnOoAoGCCqGSM49\nAwEHoUQDQgAEaBupEMEUMVYjEhUU9o9iKX0fQWXaeGhvGitoRZd2SJx7NeSJJBdi\noGzSGNYIGllBIgFDcZC5aCqSf1JPO5AYVA==\n-----END EC PRIVATE KEY-----\n"
// });
const validateContractSetup = (req, res, next) => {
  const sessionId = req.headers["session-id"];
  if (!sessionId || !sessions.has(sessionId)) {
    return res
      .status(400)
      .json({ error: "Contract not setup. Please setup contract first." });
  }
  next();
};

app.get("/wallet", async (req, res) => {
  // try {
  const wallet = await Wallet.create();

  const data = wallet.export();

  const address = await wallet.listAddresses();

  console.log(address);

  return res.json({
    status: "success",
    data,
    wallet_address: address,
  });
});

app.post("/transaction", async (req, res) => {
  try {
    const {
      prompt,
      walletId, // Get wallet ID from request
      walletSeed, // Get wallet seed from request
      walletAddress, // Get wallet address from request
    } = req.body;

    if (!walletId || !walletSeed || !walletAddress) {
      console.log(walletId, walletSeed, walletAddress);
      return res.status(400).json({ error: "Missing required credentials" });
    }

    const cleanPrompt = prompt.replace(/"/g, "");
    console.log(walletId);
    // Import wallet with request credentials
    const w = await brianCDPSDK.importWallet({
      walletId: walletId,
      seed: walletSeed,
    });
    // console.log(w);
    // w.addresses[0].networkId = "base-mainnet";
    // w.addresses[0].model.networkId = "base-mainnet";

    // console.log(w);
    // change wallet chain
    // await w.changeChain("ethereum");

    // console.log("Wallet: ", w);

    // Process initial transaction
    // const response = await brianCDPSDK.brianSDK.transact({
    //     prompt: cleanPrompt,
    //     address: walletAddress,
    //     chainId: '8453'
    // });

    // Execute transaction immediately
    // await brianCDPSDK.fundWallet(w, 0.1);
    const result = await brianCDPSDK.transact(cleanPrompt);
    console.log(result);
    const transaction_hash = result[0];

    // const transactionLink = result[0].getTransactionLink();

    res.json({
      status: "success",
      transaction_hash,
    });
  } catch (error) {
    res.status(500).json({
      status: "error",
      message: error.message,
    });
  }
});

app.post("/setup", async (req, res) => {
  //   try {
  const { contractAddress, contractAbi } = req.body;

  // Validate contract address
  if (!contractAddress?.match(/0x[a-fA-F0-9]{40}/)) {
    return res.status(400).json({ error: "Invalid contract address" });
  }

  // Validate ABI
  if (!Array.isArray(contractAbi)) {
    return res.status(400).json({ error: "Invalid ABI format" });
  }

  // Generate unique session ID
  const sessionId = Math.random().toString(36).substring(7);

  // Store contract details
  sessions.set(sessionId, {
    contractAddress,
    contractAbi,
  });

  res.json({
    message: "Contract setup successful",
    sessionId,
  });
  //   } catch (error) {
  //     res.status(500).json({ error: error.message });
  //   }
});

app.post("/interact", validateContractSetup, async (req, res) => {
  try {
    const { command } = req.body;
    const sessionId = req.headers["session-id"];
    const session = sessions.get(sessionId);

    const nlProcessor = new NLProcessor(process.env.groq, session.contractAbi);

    const contractService = new ContractService(
      session.contractAddress,
      session.contractAbi,
      brianCDPSDK.getCurrentWallet() // Use the SDK instance initialized at the top
    );

    const action = await nlProcessor.processUserInput(command);
    const result = await contractService.executeAction(action);

    res.json({
      transactionHash: result.hash,
      action,
    });
  } catch (error) {
    res.status(500).json({ error: error.message });
  }
});

const PORT = process.env.PORT || 5002;
app.listen(PORT, () => {
  console.log(`Server running on port ${PORT}`);
});
