import contextlib
from decimal import Decimal
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from Cli_based_bank_management import Bank, CurrentAccount, SavingsAccount, main


class AccountTests(unittest.TestCase):
    def test_overdraft_is_allowed_until_exact_limit(self):
        account = CurrentAccount('Demo', 100, 500)
        account.withdraw(200)
        self.assertEqual(account.check_balance(), Decimal('-100.00'))
        account.withdraw(400)
        self.assertEqual(account.check_balance(), Decimal('-500.00'))
        with self.assertRaises(ValueError):
            account.withdraw('0.01')
        self.assertEqual(account.check_balance(), Decimal('-500.00'))

    def test_savings_cannot_overdraw(self):
        account = SavingsAccount('Demo', 100, 12)
        with self.assertRaises(ValueError):
            account.withdraw(101)
        self.assertEqual(account.check_balance(), Decimal('100.00'))

    def test_decimal_money_and_interest_rounding(self):
        account = SavingsAccount('Demo', '0.10', 5)
        account.deposit('0.20')
        self.assertEqual(account.check_balance(), Decimal('0.30'))
        self.assertEqual(account.add_interest(), Decimal('0.02'))
        self.assertEqual(account.check_balance(), Decimal('0.32'))

    def test_invalid_amounts_do_not_change_balance(self):
        account = SavingsAccount('Demo', 100, 4)
        for value in ['bad', 'NaN', 'Infinity', '-1', '0', '0.001', '1e1000']:
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    account.deposit(value)
        self.assertEqual(account.check_balance(), Decimal('100.00'))
        self.assertEqual(account.get_transaction_history(), [])

    def test_invalid_account_fields(self):
        for name, balance, rate in [('', 0, 4), ('Demo\nOther', 0, 4), ('Demo', -1, 4),
                                     ('Demo', 0, -1), ('Demo', 0, 101)]:
            with self.subTest(name=name, balance=balance, rate=rate), self.assertRaises(ValueError):
                SavingsAccount(name, balance, rate)
        with self.assertRaises(ValueError):
            CurrentAccount('Demo', 0, -1)

    def test_history_cannot_mutate_account(self):
        account = SavingsAccount('Demo', 0, 4)
        account.deposit(1)
        account.get_transaction_history().clear()
        self.assertEqual(len(account.get_transaction_history()), 1)


class PersistenceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / 'bank.json'
        self.legacy = Path(self.temp.name) / 'bank.txt'
        self.bank = Bank(self.path, self.legacy)

    def test_roundtrip_preserves_settings_unicode_and_separators(self):
        savings_id = self.bank.create_account('Demo | comma, Unicode नाम', 100, 'savings', 12)
        current_id = self.bank.create_account('Current', 100, 'current', 750)
        self.bank.find_account(current_id).withdraw(300)
        self.bank.save_to_file()
        restored = Bank(self.path, self.legacy)
        restored.load_from_file()
        savings = restored.find_account(savings_id)
        self.assertEqual(savings.get_owner_name(), 'Demo | comma, Unicode नाम')
        self.assertEqual(savings.add_interest(), Decimal('12.00'))
        self.assertEqual(savings.check_balance(), Decimal('112.00'))
        current = restored.find_account(current_id)
        self.assertEqual(current.overdraft_limit, Decimal('750.00'))
        self.assertEqual(current.check_balance(), Decimal('-200.00'))
        self.assertEqual(current.get_transaction_history(), ['Withdrew 300.00'])
        self.assertEqual(restored.create_account('Next', 0, 'savings', 0), 'ACC1002')

    def test_failed_replace_preserves_saved_file_and_cleans_temp(self):
        account_id = self.bank.create_account('Demo', 100, 'savings', 4)
        self.bank.save_to_file()
        original = self.path.read_bytes()
        self.bank.find_account(account_id).deposit(5)
        with patch('Cli_based_bank_management.os.replace', side_effect=OSError('disk error')):
            with self.assertRaises(OSError):
                self.bank.save_to_file()
        self.assertEqual(self.path.read_bytes(), original)
        self.assertEqual(list(self.path.parent.glob('.bank-*.tmp')), [])

    def test_malformed_data_is_not_silently_overwritten(self):
        self.path.write_text('{ broken', encoding='utf-8')
        with self.assertRaises(ValueError):
            self.bank.load_from_file()
        self.assertEqual(self.path.read_text(), '{ broken')

    def test_unknown_schema_and_bad_balance_are_rejected(self):
        self.path.write_text(json.dumps({'schema_version': 99, 'accounts': {}}))
        with self.assertRaises(ValueError):
            self.bank.load_from_file()
        self.bank.create_account('Demo', 0, 'savings', 4)
        self.bank.save_to_file()
        payload = json.loads(self.path.read_text())
        payload['accounts']['ACC1000']['balance'] = '-1'
        self.path.write_text(json.dumps(payload))
        with self.assertRaises(ValueError):
            Bank(self.path, self.legacy).load_from_file()

    def test_existing_legacy_records_require_explicit_recovery(self):
        self.legacy.write_text('ACC1000|Demo|100|savings|\n')
        with self.assertRaisesRegex(ValueError, 'Legacy'):
            self.bank.load_from_file()
        self.assertFalse(self.path.exists())

    def test_empty_legacy_placeholder_is_harmless(self):
        self.legacy.write_text('')
        self.bank.load_from_file()
        self.assertIsNone(self.bank.find_account('ACC1000'))

    def test_cli_recovers_after_invalid_numeric_input(self):
        output = io.StringIO()
        answers = ['1', 'Demo', 'not a number', 'savings', '4', '6']
        with patch('Cli_based_bank_management.Bank', return_value=self.bank), \
                patch('builtins.input', side_effect=answers), contextlib.redirect_stdout(output):
            self.assertEqual(main(), 0)
        self.assertIn('Invalid input:', output.getvalue())
        self.assertIn('Goodbye!', output.getvalue())
        self.assertIsNone(self.bank.find_account('ACC1000'))


if __name__ == '__main__':
    unittest.main()
