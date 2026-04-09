from aiogram.fsm.state import StatesGroup, State
class SearchStates(StatesGroup): waiting_for_query = State()
class BroadcastStates(StatesGroup): waiting_for_message = State()
class GiveCreditsStates(StatesGroup): waiting_for_target = State(); waiting_for_amount = State()
class AddBalanceStates(StatesGroup): waiting_for_target = State(); waiting_for_amount = State()
class CryptoTopUpStates(StatesGroup): waiting_for_coin = State(); waiting_for_amount = State()
