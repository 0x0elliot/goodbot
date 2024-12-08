import { Telegraf, Context } from "telegraf";
import { NLProcessor } from "./nlProcessor";
import { ContractService } from "./contractService";
import { SmartContractBot } from "./telegramBot";

interface BotContext extends Context {
  session?: {
    contractAddress?: string;
    contractAbi?: any[];
  }
}

const bot = new Telegraf<BotContext>(process.env.TELEGRAM_TOKEN!);

// Add session middleware
bot.use(Telegraf.session());

// Command to start contract interaction setup
bot.command('setup', async (ctx) => {
  await ctx.reply('Please enter the contract address:');
  ctx.session = {};
});

// Handle contract address input
bot.hears(/0x[a-fA-F0-9]{40}/, async (ctx) => {
  if (!ctx.session) return;
  
  ctx.session.contractAddress = ctx.message.text;
  await ctx.reply('Please paste the contract ABI (as JSON):');
});

// Handle ABI input
bot.on('text', async (ctx) => {
  if (!ctx.session?.contractAddress) return;
  if (ctx.session.contractAbi) {
    // ABI is already set, process natural language command
    const nlProcessor = new NLProcessor(
      process.env.OPENAI_API_KEY!,
      ctx.session.contractAbi
    );
    
    const contractService = new ContractService(
      ctx.session.contractAddress,
      ctx.session.contractAbi
    );

    try {
      const action = await nlProcessor.processUserInput(ctx.message.text);
      const result = await contractService.executeAction(action);
      await ctx.reply(`Transaction completed: ${result.hash}`);
    } catch (error) {
      await ctx.reply(`Error: ${error.message}`);
    }
    return;
  }

  try {
    // Try to parse ABI JSON
    const abi = JSON.parse(ctx.message.text);
    ctx.session.contractAbi = abi;
    await ctx.reply('Setup complete! You can now interact with the contract using natural language.');
  } catch (error) {
    await ctx.reply('Invalid ABI format. Please send valid JSON.');
  }
});

bot.launch();

// Enable graceful stop
process.once('SIGINT', () => bot.stop('SIGINT'));
process.once('SIGTERM', () => bot.stop('SIGTERM'));