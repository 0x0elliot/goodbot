// contractService.js
class ContractService {
  constructor(contractAddress, contractAbi, wallet) {
    this.contractAddress = contractAddress;
    this.contractAbi = contractAbi;
    this.wallet = wallet; // BrianCoinbaseSDK wallet instance
  }

  async executeAction({ method, args }) {
    try {
      // Use the initialized SDK wallet to invoke contract
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

export default ContractService;
