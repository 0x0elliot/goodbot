from web3 import Web3
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes
from typing import Dict, List, Any
import json
import asyncio

ITEMS_PER_PAGE = 5

class ContractInterface:
    def __init__(self, node_url: str):
        self.w3 = Web3(Web3.HTTPProvider(node_url))
        self.contracts: Dict[str, Any] = {}
        self.event_listeners: Dict[str, asyncio.Task] = {}

    def load_contract(self, address: str, abi: str, name: str) -> bool:
        # try:
            contract_address = Web3.to_checksum_address(address)
            contract_abi = json.loads(abi)
            contract = self.w3.eth.contract(address=contract_address, abi=contract_abi)
            print(contract)
            self.contracts[name] = {
                'contract': contract,
                'functions': self._get_contract_functions(contract),
                'events': self._get_contract_events(contract)
            }
            return True
        # except Exception as e:
        #     raise Exception(f"Contract loading error: {e}")

    def _get_contract_functions(self, contract):
        return [fn for fn in contract.all_functions()]

    def _get_contract_events(self, contract):
        return [event for event in contract.events]

    async def estimate_gas(self, contract_name: str, function_name: str, params: List[Any]) -> int:
        contract = self.contracts[contract_name]['contract']
        fn = getattr(contract.functions, function_name)
        return await fn(*params).estimate_gas()

    async def send_transaction(self, contract_name: str, function_name: str, params: List[Any], 
                             private_key: str):
        contract = self.contracts[contract_name]['contract']
        fn = getattr(contract.functions, function_name)
        
        account = self.w3.eth.account.from_key(private_key)
        transaction = fn(*params).build_transaction({
            'from': account.address,
            'nonce': self.w3.eth.get_transaction_count(account.address),
            'gas': await self.estimate_gas(contract_name, function_name, params),
            'gasPrice': self.w3.eth.gas_price
        })
        
        signed_txn = self.w3.eth.account.sign_transaction(transaction, private_key)
        tx_hash = self.w3.eth.send_raw_transaction(signed_txn.rawTransaction)
        return self.w3.eth.wait_for_transaction_receipt(tx_hash)

class TelegramBot:
    def __init__(self, token: str, node_url: str):
        self.contract_interface = ContractInterface(node_url)
        self.app = ApplicationBuilder().token(token).build()
        self.user_states: Dict[int, Dict] = {}
        self.setup_handlers()

    def setup_handlers(self):
        self.app.add_handler(CommandHandler("start", self.start_command))
        self.app.add_handler(CommandHandler("load_contract", self.load_contract_command))
        self.app.add_handler(CallbackQueryHandler(self.button_callback))
        self.app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_text_input))

    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        keyboard = [
            [InlineKeyboardButton("Load Contract", callback_data='load_contract')],
            [InlineKeyboardButton("View Contracts", callback_data='view_contracts')]
        ]
        await update.message.reply_text('Welcome!', reply_markup=InlineKeyboardMarkup(keyboard))

    async def load_contract_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        self.user_states[user_id] = {'state': 'awaiting_contract_name'}
        await update.message.reply_text("Please enter the contract name:")

    async def handle_text_input(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        if user_id not in self.user_states:
            return

        state = self.user_states[user_id]['state']
        if state == 'awaiting_contract_name':
            self.user_states[user_id].update({
                'contract_name': update.message.text,
                'state': 'awaiting_address'
            })
            await update.message.reply_text("Please enter the contract address:")
        
        elif state == 'awaiting_address':
            self.user_states[user_id].update({
                'address': update.message.text,
                'state': 'awaiting_abi'
            })
            await update.message.reply_text("Please enter the contract ABI:")
        
        elif state == 'awaiting_abi':
            # try:
                contract_name = self.user_states[user_id]['contract_name']
                address = self.user_states[user_id]['address']
                x=update.message.text
                self.contract_interface.load_contract(address, x, contract_name)
                await update.message.reply_text(f"Contract {contract_name} loaded successfully!")
            # except Exception as e:
            #     await update.message.reply_text(f"Error loading contract: {e}")
            # finally:
            #     del self.user_states[user_id]

    async def button_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        data = query.data
        page = 0

        if 'page' in data:
            action, contract_name, page = data.split('_')
            page = int(page)

        if data == 'view_contracts':
            await self.show_contracts_list(query)
        
        elif data.startswith('contract_'):
            contract_name = data.split('_')[1]
            await self.show_contract_actions(query, contract_name)
        
        elif data.startswith('functions_'):
            contract_name = data.split('_')[1]
            await self.show_contract_functions(query, contract_name, page)
        
        elif data.startswith('events_'):
            contract_name = data.split('_')[1]
            await self.show_contract_events(query, contract_name, page)
        
        elif data.startswith('call_'):
            _, contract_name, function_name = data.split('_')
            await self.prepare_function_call(query, contract_name, function_name)

    async def show_contracts_list(self, query):
        contracts = list(self.contract_interface.contracts.keys())
        if not contracts:
            await query.message.reply_text("No contracts loaded!")
            return

        keyboard = [[InlineKeyboardButton(name, callback_data=f'contract_{name}')] 
                   for name in contracts]
        await query.message.reply_text("Loaded contracts:", 
                                     reply_markup=InlineKeyboardMarkup(keyboard))

    async def show_contract_actions(self, query, contract_name):
        keyboard = [
            [InlineKeyboardButton("View Functions", 
                                callback_data=f'functions_{contract_name}_0')],
            [InlineKeyboardButton("View Events", 
                                callback_data=f'events_{contract_name}_0')],
            [InlineKeyboardButton("Back", callback_data='view_contracts')]
        ]
        await query.message.reply_text(f"Contract: {contract_name}", 
                                     reply_markup=InlineKeyboardMarkup(keyboard))

    async def show_contract_functions(self, query, contract_name, page):
        functions = self.contract_interface.contracts[contract_name]['functions']
        start_idx = page * ITEMS_PER_PAGE
        end_idx = start_idx + ITEMS_PER_PAGE
        current_page_fns = functions[start_idx:end_idx]

        keyboard = [[InlineKeyboardButton(str(fn), 
                    callback_data=f'call_{contract_name}_{fn.fn_name}')] 
                   for fn in current_page_fns]

        if page > 0:
            keyboard.append([InlineKeyboardButton("Previous", 
                          callback_data=f'functions_{contract_name}_{page-1}')])
        if end_idx < len(functions):
            keyboard.append([InlineKeyboardButton("Next", 
                          callback_data=f'functions_{contract_name}_{page+1}')])

        keyboard.append([InlineKeyboardButton("Back", 
                       callback_data=f'contract_{contract_name}')])
        
        await query.message.reply_text(f"Functions (Page {page + 1}):", 
                                     reply_markup=InlineKeyboardMarkup(keyboard))

    def run(self):
        self.app.run_polling()

def main():
    bot = TelegramBot(os.getenv("TELEGRAM_BOT"), os.getenv("ALCHEMY_PROVIDER_URL"))
    bot.run()

if __name__ == "__main__":
    main()
