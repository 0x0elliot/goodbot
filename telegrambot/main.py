import os
import json
import requests
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, ConversationHandler
from cdp import Cdp, Wallet, WalletData, hash_message
from eth_account.messages import encode_defunct
from eth_account import Account
from datetime import datetime
import time
import uuid
from dotenv import load_dotenv

load_dotenv()

API_KEY_NAME = os.getenv('CDP_API_KEY_NAME')
API_KEY_PRIVATE_KEY = os.getenv('CDP_API_PRIVATE_KEY')
TELEGRAM_AUTH_TOKEN = os.getenv('TELEGRAM_AUTH_TOKEN')

print("API_KEY_NAME: ", API_KEY_NAME)
print("API_KEY_PRIVATE_KEY: ", API_KEY_PRIVATE_KEY)

Cdp.configure(API_KEY_NAME, API_KEY_PRIVATE_KEY)

# Constants for conversation states
WAITING_ADDRESS, WAITING_ABI = range(2)
API_URL = "http://localhost:5002"

def check_first_time_cache():
    if os.path.isfile("./.cache"):
        return False
    else:
        with open("./.cache", "w") as file:
            file.write("1")
        return True

def get_wallet_data():
    read_from_file = "../brian-microservice/src/demo_coinbase_wallet.json"
    with open(read_from_file, "r") as file:
        data = file.read()
        return json.loads(data)

def talk_to_brian(prompt):
    wallet = get_wallet_data()
    walletId = wallet.get("walletId")
    walletSeed = wallet.get("walletSeed")
    walletAddress = wallet.get("walletAddress")
    
    url = "http://localhost:5002/transaction"
    r = requests.post(url, json = {
        "prompt": prompt,
        "walletId": walletId,
        "walletSeed": walletSeed,
        "walletAddress": walletAddress
    }) 
    
    return r

async def respond_to_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    message = update.message.text
    
    wallet = get_wallet_data()

    if check_first_time_cache():
        await update.message.reply_text("Hey! I see you are new here. Creating a wallet for you")
        time.sleep(1.2)
        
        message = "Hey! Anything you would like to do one your generated wallet?: " + str(wallet.get("walletAddress"))        
        await update.message.reply_text(message)
    else:
        response = talk_to_brian(message)
        print(response.json())
        if response.json()['status']!='error':
            await update.message.reply_text("Transaction Hash: " + str(response.json()['transaction_hash']['model']['transaction']['transaction_link']))
        else:
            await update.message.reply_text("Error: " + str(response.json()['message']))

async def send_bot_address(update: Update, context: ContextTypes.DEFAULT_TYPE):
    wallet = get_wallet_data()
    Account.enable_unaudited_hdwallet_features()
    await update.message.reply_text("Your wallet address is: " + str(wallet.get("walletAddress")))

def setup_contract(contract_address, contract_abi):
    response = requests.post(f"{API_URL}/setup", json={
        "contractAddress": contract_address,
        "contractAbi": contract_abi
    })
    return response.json()

async def start_setup(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Please enter the contract address (starting with 0x):")
    return WAITING_ADDRESS

async def handle_address(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['contract_address'] = update.message.text
    response = requests.get(f"https://api.basescan.org/api?module=contract&action=getabi&address={context.user_data['contract_address']}&apikey=2Z3EFNIJ9U3BSBDTMM2ABUWIYMTW7IINQQ")
    print(response.json()['result'])
    if response.status_code == 200:
        await update.message.reply_text("Contract found.")
        context.user_data['contract_abi'] = response.json()['result']
        return WAITING_ABI
    else:
        await update.message.reply_text("Contract not found. Please enter a valid contract address.")
        return WAITING_ADDRESS


async def handle_abi(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        abi = json.loads(update.message.text)
        context.user_data['contract_abi'] = abi

        response = setup_contract(context.user_data['contract_address'], abi)
        if 'sessionId' in response:
            context.user_data['session_id'] = response['sessionId']
            await update.message.reply_text("Contract setup successful! You can now use /interact <command> to interact.")
        else:
            await update.message.reply_text(f"Setup failed: {response.get('error', 'Unknown error')}")
            return WAITING_ABI
    except json.JSONDecodeError:
        await update.message.reply_text("Invalid ABI format. Please send valid JSON.")
        return WAITING_ABI

    return ConversationHandler.END

async def add_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Gave @notnotrachit access to your wallet")

async def interact_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Please provide a command. Usage: /interact <command>")
        return

    if 'session_id' not in context.user_data:
        await update.message.reply_text("No active contract session. Please use /setup first.")
        return

    command = ' '.join(context.args)
    try:
        response = requests.post(
            f"{API_URL}/interact",
            headers={"session-id": context.user_data['session_id']},
            json={"command": command}
        )
        result = response.json()
        print(result)
        if 'transactionHash' in result:
            await update.message.reply_text(f"Transaction successful! Hash: {result['transactionHash']}")
        else:
            output = "Successfully executed function: "
            output += result['action']['method']
            output +="\n"
            for args in result['action']['args'].keys():
                output += f" {args}: {result['action']['args'][args]}\n"
            await update.message.reply_text(output)
    except Exception as e:
        await update.message.reply_text(f"Error: {str(e)}")

def main():
    bot = Application.builder().token(TELEGRAM_AUTH_TOKEN).build()

    setup_handler = ConversationHandler(
        entry_points=[CommandHandler('setup', start_setup)],
        states={
            WAITING_ADDRESS: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_address)],
            WAITING_ABI: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_abi)]
        },
        fallbacks=[]
    )

    bot.add_handler(setup_handler)
    bot.add_handler(CommandHandler("interact", interact_command))
    bot.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, respond_to_message))
    bot.add_handler(CommandHandler("wallet", send_bot_address))

    print('Bot is running...')
    bot.run_polling()

if __name__ == '__main__':
    main()