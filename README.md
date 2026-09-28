# CLI Bank Management System

A small Python CLI project for practicing classes, inheritance, and file-based persistence. It is an educational exercise and is not suitable for handling real money or personal financial information.

## Features

- Create savings or current accounts.
- Deposit and withdraw funds.
- Check an account balance and view its transaction history.
- Load account records from `bank_data.txt` at startup and save them when you choose **Exit**.

New account numbers are generated in the form `ACC1000`, `ACC1001`, and so on.

## Run

Requires Python 3. No third-party packages are needed.

```bash
python Cli_based_bank_management.py
```

Use the numbered menu to create an account, then enter its account number for deposits, withdrawals, balance checks, or transaction history. Choose **Exit** to save the current account records.

## Project files

```text
.
├── Cli_based_bank_management.py
├── bank_data.txt
└── README.md
```

## Storage and limitations

- Account names, balances, and transaction histories are stored as plain text in `bank_data.txt`.
- Data is saved when the **Exit** menu option is selected; an abrupt close may lose changes made during that run.
- There is no login, authentication, database, or encryption. Do not use real account details or balances.
- The current-account overdraft path is not complete, so overdrafts should be treated as unsupported.
- This is a learning project, not a secure or production banking system.
