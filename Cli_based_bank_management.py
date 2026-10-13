"""Educational CLI accounts with Decimal balances and versioned JSON persistence.

No authentication or encryption is provided. Never use real financial data.
"""
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
import json
import os
from pathlib import Path
import tempfile


CENT = Decimal('0.01')


def number(value, field='value'):
    try:
        result = Decimal(str(value))
    except (InvalidOperation, ValueError):
        raise ValueError(f'{field} must be a number.') from None
    if not result.is_finite():
        raise ValueError(f'{field} must be finite.')
    return result


def money(value, field='amount', *, allow_negative=False):
    result = number(value, field)
    try:
        rounded = result.quantize(CENT)
    except InvalidOperation:
        raise ValueError(f'{field} is too large.') from None
    if result != rounded:
        raise ValueError(f'{field} must have at most two decimal places.')
    if not allow_negative and result < 0:
        raise ValueError(f'{field} cannot be negative.')
    return rounded


class Account:
    account_type = 'savings'

    def __init__(self, owner_name, initial_balance):
        if not isinstance(owner_name, str) or not owner_name.strip():
            raise ValueError('Owner name cannot be empty.')
        if len(owner_name) > 100 or any(ord(char) < 32 for char in owner_name):
            raise ValueError('Owner name must be under 101 characters with no control characters.')
        self.owner_name = owner_name.strip()
        self._balance = money(initial_balance, 'Initial balance')
        self._transactions = []

    def deposit(self, amount):
        amount = money(amount)
        if amount <= 0:
            raise ValueError('Deposit must be greater than zero.')
        self._balance += amount
        self._transactions.append(f'Deposited {amount:.2f}')

    def withdraw(self, amount):
        amount = money(amount)
        if amount <= 0:
            raise ValueError('Withdrawal must be greater than zero.')
        if self._balance - amount < self.minimum_balance:
            raise ValueError('Withdrawal exceeds available funds or the overdraft limit.')
        self._balance -= amount
        self._transactions.append(f'Withdrew {amount:.2f}')

    @property
    def minimum_balance(self):
        return Decimal('0')

    def check_balance(self):
        return self._balance

    def get_transaction_history(self):
        return self._transactions.copy()

    def get_owner_name(self):
        return self.owner_name

    def to_record(self):
        record = {'type': self.account_type, 'owner': self.owner_name,
                  'balance': str(self._balance), 'transactions': self._transactions.copy()}
        if isinstance(self, SavingsAccount):
            record['interest_rate'] = str(self.interest_rate)
        else:
            record['overdraft_limit'] = str(self.overdraft_limit)
        return record


class SavingsAccount(Account):
    account_type = 'savings'

    def __init__(self, owner_name, initial_balance, interest_rate):
        super().__init__(owner_name, initial_balance)
        self.interest_rate = number(interest_rate, 'Interest rate')
        if not 0 <= self.interest_rate <= 100:
            raise ValueError('Interest rate must be between 0 and 100 percent.')

    def add_interest(self):
        interest = (self._balance * self.interest_rate / 100).quantize(CENT, rounding=ROUND_HALF_UP)
        if interest > 0:
            self._balance += interest
            self._transactions.append(f'Interest {interest:.2f}')
        return interest


class CurrentAccount(Account):
    account_type = 'current'

    def __init__(self, owner_name, initial_balance, overdraft_limit):
        super().__init__(owner_name, initial_balance)
        self.overdraft_limit = money(overdraft_limit, 'Overdraft limit')

    @property
    def minimum_balance(self):
        return -self.overdraft_limit


def account_from_record(record):
    if not isinstance(record, dict):
        raise ValueError('Account record must be an object.')
    try:
        if record['type'] == 'savings':
            account = SavingsAccount(record['owner'], 0, record['interest_rate'])
        elif record['type'] == 'current':
            account = CurrentAccount(record['owner'], 0, record['overdraft_limit'])
        else:
            raise ValueError('Unknown account type in saved data.')
        balance = money(record['balance'], 'Saved balance', allow_negative=True)
        if balance < account.minimum_balance:
            raise ValueError('Saved balance is below this account\'s allowed minimum.')
        transactions = record['transactions']
    except KeyError as error:
        raise ValueError(f'Missing saved account field: {error.args[0]}.') from None
    if not isinstance(transactions, list) or any(not isinstance(item, str) for item in transactions):
        raise ValueError('Saved transactions must be a list of strings.')
    account._balance = balance
    account._transactions = transactions.copy()
    return account


class Bank:
    def __init__(self, data_path='bank_data.json', legacy_path='bank_data.txt'):
        self.data_path = Path(data_path)
        self.legacy_path = Path(legacy_path)
        self._accounts = {}

    def create_account(self, owner_name, initial_balance, account_type, extra):
        account_type = account_type.lower().strip()
        if account_type == 'savings':
            account = SavingsAccount(owner_name, initial_balance, extra)
        elif account_type == 'current':
            account = CurrentAccount(owner_name, initial_balance, extra)
        else:
            raise ValueError('Account type must be savings or current.')
        next_number = max((int(key[3:]) for key in self._accounts), default=999) + 1
        account_number = f'ACC{next_number}'
        self._accounts[account_number] = account
        return account_number

    def find_account(self, account_number):
        return self._accounts.get(account_number.strip().upper())

    def save_to_file(self):
        """Replace the saved file only after a complete JSON write succeeds."""
        payload = {'schema_version': 1,
                   'accounts': {key: account.to_record() for key, account in self._accounts.items()}}
        self.data_path.parent.mkdir(parents=True, exist_ok=True)
        temp_path = None
        try:
            with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', dir=self.data_path.parent,
                                             prefix='.bank-', suffix='.tmp', delete=False) as handle:
                temp_path = Path(handle.name)
                json.dump(payload, handle, indent=2, ensure_ascii=False)
                handle.write('\n')
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temp_path, self.data_path)
        finally:
            if temp_path is not None and temp_path.exists():
                temp_path.unlink()

    def load_from_file(self):
        """Load validated data without replacing existing state on a malformed file."""
        if not self.data_path.exists():
            if self.legacy_path.exists() and self.legacy_path.read_text(encoding='utf-8').strip():
                raise ValueError('Legacy bank_data.txt has records. Keep a backup and recreate demo accounts; '
                                 'the old format did not preserve account settings, so automatic migration '
                                 'cannot recover them safely.')
            return
        try:
            payload = json.loads(self.data_path.read_text(encoding='utf-8'))
        except json.JSONDecodeError as error:
            raise ValueError(f'Invalid JSON in {self.data_path}: {error.msg}.') from None
        if not isinstance(payload, dict) or payload.get('schema_version') != 1:
            raise ValueError('Unsupported bank data format.')
        records = payload.get('accounts')
        if not isinstance(records, dict):
            raise ValueError('Saved accounts must be an object.')
        loaded = {}
        for key, record in records.items():
            if (not isinstance(key, str) or not key.startswith('ACC') or not key[3:].isdigit()
                    or str(int(key[3:])) != key[3:] or int(key[3:]) < 1000):
                raise ValueError('Invalid saved account number.')
            loaded[key] = account_from_record(record)
        self._accounts = loaded


def main():
    bank = Bank()
    try:
        bank.load_from_file()
    except (OSError, ValueError) as error:
        print(f'Cannot load accounts: {error} Existing files were not changed.')
        return 1
    menu = '\n1. Create Account\n2. Deposit\n3. Withdraw\n4. Check Balance\n5. View Transaction History\n6. Exit\n'
    while True:
        try:
            print(menu)
            choice = input('Enter choice: ').strip()
            if choice == '1':
                name = input('Enter name: ')
                balance = input('Enter initial balance: ')
                account_type = input('Enter type (savings/current): ')
                extra = input('Enter interest rate or overdraft limit: ')
                account_number = bank.create_account(name, balance, account_type, extra)
                bank.save_to_file()
                print(f'Account created: {account_number}')
            elif choice in {'2', '3', '4', '5'}:
                account = bank.find_account(input('Enter account number: '))
                if account is None:
                    raise ValueError('Account not found.')
                if choice in {'2', '3'}:
                    amount = input('Enter amount: ')
                    (account.deposit if choice == '2' else account.withdraw)(amount)
                    bank.save_to_file()
                    print(f'Balance: {account.check_balance():.2f}')
                elif choice == '4':
                    print(f'Balance: {account.check_balance():.2f}')
                else:
                    print('History:', account.get_transaction_history())
            elif choice == '6':
                bank.save_to_file()
                print('Goodbye!')
                return 0
            else:
                print('Choose a menu option from 1 to 6.')
        except ValueError as error:
            print(f'Invalid input: {error}')
        except OSError as error:
            print(f'Could not save accounts: {error}. Changes are in memory; retry saving with Exit.')
        except (EOFError, KeyboardInterrupt):
            print('\nClosed. Successful changes were saved after each operation.')
            return 0


if __name__ == '__main__':
    raise SystemExit(main())
