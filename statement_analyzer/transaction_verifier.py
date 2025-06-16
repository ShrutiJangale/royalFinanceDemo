# statement_analyzer/transaction_verifier.py
# def verify_transactions(transactions_list):
#     """
#     Verifies the integrity of transactions based on running balances.
#     Args:
#         transactions_list: A list of transaction dictionaries, presumably sorted.
#                            Each dict should have 'withdrawal', 'deposit', and 'balance' keys.
#     Returns:
#         A tuple: (all_good, flagged_entries)
#     """
#     if not transactions_list:
#         print("Verifier: No transactions provided.")
#         return True, []

#     flagged_entries = []
#     previous_running_balance = None

#     for i, entry in enumerate(transactions_list):
#         try:
#             current_running_balance = float(entry.get('balance', 0.0))
#             credit_amount = float(entry.get('credit', 0.0)) if entry.get('credit') not in [None, 'nan', ''] else 0.0
#             debit_amount = float(entry.get('debit', 0.0)) if entry.get('debit') not in [None, 'nan', ''] else 0.0
#             description = entry.get('details', 'N/A')
#             date = entry.get('date', 'N/A')

#             if i == 0:
#                 previous_running_balance = current_running_balance
#                 continue

#             expected_balance = previous_running_balance + credit_amount - debit_amount
#             tolerance = 0.015

#             if abs(expected_balance - current_running_balance) > tolerance:
#                 flagged_entries.append(
#                     f"Mismatch at Entry #{i+1} (Date: {date}, Desc: {description}): "
#                     f"Expected Balance = {expected_balance:.2f}, Actual Balance = {current_running_balance:.2f}, "
#                     f"Prev Balance = {previous_running_balance:.2f}, +Deposit = {credit_amount:.2f}, -Withdrawal = {debit_amount:.2f}"
#                 )

#             previous_running_balance = current_running_balance

#         except Exception as e:
#             flagged_entries.append(f"Error at Entry #{i+1} (Date: {entry.get('date', 'N/A')}): {str(e)}")
#             previous_running_balance = current_running_balance  # Try to recover and continue

#     return (len(flagged_entries) == 0), flagged_entries


def verify_transactions(transactions_list):
    """
    Verifies the integrity of transactions based on running balances.
    Args:
        transactions_list: A list of transaction dictionaries.
                           Each dict may have 'credit', 'debit', and optionally 'balance' keys.
    Returns:
        A tuple: (all_good, flagged_entries)
    """
    if not transactions_list:
        print("Verifier: No transactions provided.")
        return True, []

    flagged_entries = []
    previous_running_balance = None

    for i, entry in enumerate(transactions_list):
        try:
            entry['mismatch'] = False
            balance_raw = entry.get('balance')
            if balance_raw is not None:
                if isinstance(balance_raw, (int, float)):
                    current_running_balance = float(balance_raw)
                else:
                    balance_str = str(balance_raw).replace('Cr', '').replace('Dr', '').replace(',', '').strip()
                    current_running_balance = float(balance_str)
            else:
                current_running_balance = None

            amount = float(entry.get('amount', 0.0)) if entry.get('amount') not in [None, 'nan', ''] else 0.0
            # debit_amount = float(entry.get('debit', 0.0)) if entry.get('debit') not in [None, 'nan', ''] else 0.0
            description = entry.get('details', 'N/A')
            date = entry.get('date', 'N/A')

            if current_running_balance is None:
                # Can't validate balance if not present
                previous_running_balance = previous_running_balance + amount if previous_running_balance is not None else None
                continue

            if i == 0:
                previous_running_balance = current_running_balance
                continue
            print(entry.get("id"))
            
            expected_balance = previous_running_balance + amount
            tolerance = 0.015
            print(f"previous_running_balance: {previous_running_balance}")
            print(f"current_running_balance: {current_running_balance}")
            print(f"expected_balance: {expected_balance}")
            print(f"amount: {amount}")

            if abs(expected_balance - current_running_balance) > tolerance:
                flagged_entries.append(
                    f"Mismatch at Entry #{i + 1} (Date: {date}, Desc: {description}): "
                    f"Expected Balance = {expected_balance:.2f}, Actual Balance = {current_running_balance:.2f}, "
                    f"Prev Balance = {previous_running_balance:.2f}, +Amount = {amount:.2f}"
                )
                entry['mismatch'] = True

            previous_running_balance = current_running_balance

        except Exception as e:
            flagged_entries.append(f"Error at Entry #{i + 1} (Date: {entry.get('date', 'N/A')}): {str(e)}")
            # Fallback: don't update previous_running_balance unless safely defined
            entry['mismatch'] = True
            if 'current_running_balance' in locals():
                previous_running_balance = current_running_balance

    return flagged_entries, transactions_list


