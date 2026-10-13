# CLI Bank Management System

A small Python application for practicing classes, inheritance, input validation, and persistent storage. Create savings/current accounts, deposit or withdraw decimal amounts, and inspect balances and transaction history.

**Educational only:** no login, access control, encryption, or real payment processing. Use fictional names and amounts.

## Run

Python 3.11+; no third-party packages are required.

```bash
git clone https://github.com/MohitMahato-1/CLI_based_bank_management_system.git
cd CLI_based_bank_management_system
python Cli_based_bank_management.py
```

The menu provides creation, deposit, withdrawal, balance, transaction history, and exit options. Successful changes are saved after each operation.

Example inputs for a current account:

```text
Enter choice: 1
Enter name: Demo User
Enter initial balance: 100
Enter type (savings/current): current
Enter interest rate or overdraft limit: 500
Account created: ACC1000

Enter choice: 3
Enter account number: ACC1000
Enter amount: 200
Balance: -100.00
```

A further withdrawal of 400 reaches the -500 limit; a withdrawal beyond that limit is rejected. Savings accounts cannot have negative balances. Invalid numbers, non-finite values, negative amounts, and amounts with more than two decimal places produce a validation message and return to the menu.

## How it works

- `Account` implements shared balance and transaction operations.
- `SavingsAccount` stores an interest rate. `add_interest()` is available in Python; the menu does not apply interest automatically.
- `CurrentAccount` supplies an overdraft minimum to the shared withdrawal logic.
- `Bank` assigns account numbers and loads/saves a versioned JSON document.
- `Decimal` represents money in cents. Interest uses half-up rounding to the nearest cent.

## Storage

`bank_data.json` is created in the current working directory and is ignored by Git. It preserves account type, owner, balance, interest rate or overdraft limit, and transaction history. JSON safely handles names containing pipes, commas, or Unicode characters.

Saving writes a temporary file and then replaces the previous file, reducing the chance of leaving a partial document. Malformed saved data is rejected instead of silently discarded. This is still a single-user local file: there is no concurrent-writer support, backup service, or secure audit trail.

Earlier versions used `bank_data.txt`, which did not preserve custom account settings. An empty old file is harmless. If a nonempty legacy file exists and no JSON file exists, startup stops with an explanation so records are not silently replaced. Keep a backup and recreate fictional demo accounts with the intended settings; lost settings cannot be inferred reliably.

## Checks

```bash
python -m unittest discover -s tests -v
```

Tests cover overdraft boundaries, exact decimal arithmetic, invalid input, persistence of custom settings, names containing separators, corrupted files, failed file replacement, and recovery from an invalid CLI input. A GitHub Actions workflow runs the suite on Python 3.11 and 3.12 when enabled on the remote repository.

## Current limits

This is a learning exercise, not a production banking system. Transaction history is a list of messages, not an immutable financial ledger. There are no transfers, scheduled interest calculations, authentication, or database transactions.
