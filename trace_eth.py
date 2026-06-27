"""trace_eth.py — Trace ETH spend per transaction across all UCI-HAR sessions."""
from web3 import Web3
from dotenv import load_dotenv
import os, re, glob

load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), '.env'))

w3 = Web3(Web3.HTTPProvider(os.getenv('BASE_SEPOLIA_RPC_URL')))
addr = w3.eth.account.from_key(os.getenv('PRIVATE_KEY')).address
print(f"Wallet: {addr}\n")

TX_RE = re.compile(r'Transaction sent: ([0-9a-f]{64})')
entries = []
for log in sorted(glob.glob('outputs_ucihar/*/fl_server.log')):
    session = log.split('/')[1]
    with open(log) as f:
        for line in f:
            m = TX_RE.search(line)
            if m:
                entries.append((session, '0x' + m.group(1)))

print(f"Found {len(entries)} transactions across {len(set(e[0] for e in entries))} sessions\n")
print(f"{'Session':<45} {'TxHash[:10]':>12}  {'Fee ETH':>12}  {'Total spent':>14}")
print('-' * 90)

total_spent = 0.0
for session, txhash in entries:
    try:
        tx   = w3.eth.get_transaction(txhash)
        rcpt = w3.eth.get_transaction_receipt(txhash)
        fee  = float(w3.from_wei(rcpt['gasUsed'] * tx['gasPrice'], 'ether'))
        total_spent += fee
        print(f"{session:<45} {txhash[:12]}  {fee:>12.8f}  {total_spent:>14.8f}")
    except Exception as e:
        print(f"{session:<45} {txhash[:12]}  ERROR: {e}")

print(f"\nTotal spent: {total_spent:.8f} ETH  (~${total_spent * 1573.35:.4f} USD)")
