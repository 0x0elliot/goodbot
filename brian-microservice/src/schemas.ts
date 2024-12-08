// schemas.ts
import { z } from "zod";

export const ContractActionSchema = z.object({
  method: z.string().describe("The smart contract method to call"),
  args: z.record(z.any()).describe("Arguments for the contract method call")
});

type ContractAction = z.infer<typeof ContractActionSchema>;