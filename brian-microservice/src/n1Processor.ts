// nlProcessor.ts
import Instructor from "@instructor-ai/instructor";
// import OpenAI from "openai";
import Groq from 'groq-sdk';

import { ContractActionSchema } from "./schemas";

export class NLProcessor {
  private client: ReturnType<typeof Instructor>;
  private contractAbi: any[];

  constructor(apiKey: string, contractAbi: any[]) {
    const oai = new Groq({ apiKey: process.env.GROQ });
    this.client = Instructor({
      client: oai,
      mode: "FUNCTIONS"
    });
    this.contractAbi = contractAbi;
  }

  async processUserInput(message: string): Promise<any> {
    const systemContext = `Given this contract ABI: ${JSON.stringify(this.contractAbi)}`;
    
    const action = await this.client.chat.completions.create({
      messages: [
        { role: "system", content: systemContext },
        { role: "user", content: message }
      ],
      model: "llama-3.3-70b-versatile",
      response_model: {
        schema: ContractActionSchema,
        name: "ContractAction"
      }
    });

    return action;
  }
}
