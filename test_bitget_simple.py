#!/usr/bin/env python3
"""
Simple Bitget API Test
"""
import os
import sys
import ccxt
from dotenv import load_dotenv

load_dotenv()

def test_bitget():
    print("=== Bitget API Test ===")
    
    api_key = os.getenv('BITGET_API_KEY')
    secret_key = os.getenv('BITGET_SECRET_KEY')
    passphrase = os.getenv('BITGET_PASSPHRASE')
    
    print(f"API Key: {api_key[:15]}..." if api_key else "API Key: Missing")
    print(f"Secret: {secret_key[:15]}..." if secret_key else "Secret: Missing")
    print(f"Passphrase: {passphrase[:8]}..." if passphrase else "Passphrase: Missing")
    
    if not all([api_key, secret_key, passphrase]):
        print("ERROR: Missing API credentials")
        return False
    
    try:
        exchange = ccxt.bitget({
            'apiKey': api_key,
            'secret': secret_key,
            'password': passphrase,
            'enableRateLimit': True,
            'options': {
                'defaultType': 'swap',
                'adjustForTimeDifference': True
            }
        })
        
        print("\nTesting connection...")
        
        # Test balance
        balance = exchange.fetch_balance()
        print("SUCCESS: Balance fetched")
        
        usdt_balance = balance.get('USDT', {})
        print(f"USDT Balance:")
        print(f"  Free: ${usdt_balance.get('free', 0):.2f}")
        print(f"  Used: ${usdt_balance.get('used', 0):.2f}")
        print(f"  Total: ${usdt_balance.get('total', 0):.2f}")
        
        return True
        
    except Exception as e:
        print(f"ERROR: {e}")
        print(f"Error Type: {type(e).__name__}")
        return False

if __name__ == "__main__":
    success = test_bitget()
    if success:
        print("\n✓ Bitget API working correctly!")
    else:
        print("\n✗ Bitget API connection failed")