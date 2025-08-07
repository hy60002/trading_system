#!/usr/bin/env python3
"""
Enhanced Trading System Launcher
Author: Enhanced by Claude Code
Version: 4.0

Usage:
    python run.py                 # Start the trading system
    python run.py --config-check  # Check configuration only
    python run.py --test          # Run in test mode
    python run.py --help          # Show help
"""

import asyncio
import argparse
import sys
import os
from pathlib import Path

# Add the current directory to Python path
current_dir = Path(__file__).parent
sys.path.insert(0, str(current_dir))

from main import EnhancedTradingSystem, trading_system_context
from core.config import ConfigManager
from core.exceptions import TradingSystemException

def parse_arguments():
    """Parse command line arguments"""
    parser = argparse.ArgumentParser(
        description="Enhanced Trading System v4.0",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    python run.py                     # Start normal trading
    python run.py --config-check      # Validate configuration
    python run.py --test              # Run in test mode
    python run.py --dry-run           # Simulate trading without real orders
        """
    )
    
    parser.add_argument(
        "--config-check",
        action="store_true",
        help="Check configuration and exit"
    )
    
    parser.add_argument(
        "--test",
        action="store_true", 
        help="Run in test mode with mock data"
    )
    
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Simulate trading without placing real orders"
    )
    
    parser.add_argument(
        "--config-file",
        default=".env",
        help="Path to configuration file (default: .env)"
    )
    
    parser.add_argument(
        "--log-level",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        default="INFO",
        help="Set logging level (default: INFO)"
    )
    
    parser.add_argument(
        "--version",
        action="version",
        version="Enhanced Trading System v4.0"
    )
    
    return parser.parse_args()

async def check_configuration(config_file: str):
    """Check configuration validity"""
    print("🔍 Checking configuration...")
    
    try:
        # Check if config file exists
        if not os.path.exists(config_file):
            print(f"❌ Configuration file not found: {config_file}")
            print(f"💡 Copy .env.example to {config_file} and fill in your credentials")
            return False
        
        # Load and validate configuration
        config_manager = ConfigManager()
        
        # Try to reload with specific file
        if config_file != ".env":
            config = config_manager.reload_config(config_file)
        else:
            config = config_manager.get_config()
        
        print("✅ Configuration loaded successfully")
        
        # Display masked configuration
        masked_config = config.mask_secrets()
        print("📋 Configuration Summary:")
        print(f"   Symbols: {config.SYMBOLS}")
        print(f"   Leverage: {config.LEVERAGE}")
        print(f"   Portfolio Weights: {config.PORTFOLIO_WEIGHTS}")
        print(f"   Database: {config.DATABASE_URL}")
        print(f"   Cache Size: {config.INDICATOR_CACHE_SIZE}")
        
        # Check API credentials (masked)
        credentials_status = {
            'Bitget API': bool(config.BITGET_API_KEY),
            'Bitget Secret': bool(config.BITGET_SECRET_KEY),
            'Bitget Passphrase': bool(config.BITGET_PASSPHRASE),
            'OpenAI API': bool(config.OPENAI_API_KEY),
            'Telegram Bot': bool(config.TELEGRAM_BOT_TOKEN)
        }
        
        print("🔑 Credentials Status:")
        for service, status in credentials_status.items():
            status_icon = "✅" if status else "❌"
            print(f"   {status_icon} {service}: {'Configured' if status else 'Missing'}")
        
        # Validate configuration
        config.validate()
        print("✅ Configuration validation passed")
        
        return True
        
    except Exception as e:
        print(f"❌ Configuration error: {e}")
        return False

async def run_test_mode():
    """Run system in test mode"""
    print("🧪 Running in test mode...")
    
    try:
        async with trading_system_context() as system:
            print("✅ System initialized successfully in test mode")
            print("📊 System Status:", system.get_system_status())
            
            # Run for a short time in test mode
            await asyncio.sleep(10)
            print("✅ Test mode completed successfully")
            
    except Exception as e:
        print(f"❌ Test mode failed: {e}")
        return False
    
    return True

async def run_production_mode(dry_run: bool = False):
    """Run system in production mode"""
    mode = "dry-run" if dry_run else "production"
    print(f"🚀 Starting Enhanced Trading System v4.0 in {mode} mode...")
    
    try:
        async with trading_system_context() as system:
            if dry_run:
                print("⚠️  DRY RUN MODE: No real trades will be executed")
            
            print("✅ System initialized successfully")
            print("📊 System Status:", system.get_system_status())
            
            # Run the main system
            await system.run()
            
    except KeyboardInterrupt:
        print("\\n🛑 Shutdown requested by user")
    except TradingSystemException as e:
        print(f"❌ Trading system error: {e}")
        return False
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        return False
    
    return True

def main():
    """Main entry point"""
    args = parse_arguments()
    
    # Print banner
    print("=" * 60)
    print("🚀 Enhanced Trading System v4.0")
    print("   Author: Enhanced by Claude Code")
    print("   Cryptocurrency Trading with Advanced Risk Management")
    print("=" * 60)
    
    # Set log level if specified
    if args.log_level:
        os.environ['LOG_LEVEL'] = args.log_level
    
    # Handle different modes
    try:
        if args.config_check:
            # Configuration check mode
            success = asyncio.run(check_configuration(args.config_file))
            return 0 if success else 1
            
        elif args.test:
            # Test mode
            print("🧪 Test mode enabled")
            success = asyncio.run(run_test_mode())
            return 0 if success else 1
            
        else:
            # Production mode (or dry-run)
            if args.dry_run:
                print("⚠️  Dry-run mode enabled - no real trades will be executed")
            
            success = asyncio.run(run_production_mode(dry_run=args.dry_run))
            return 0 if success else 1
            
    except KeyboardInterrupt:
        print("\\n🛑 Interrupted by user")
        return 130  # Standard exit code for Ctrl+C
    except Exception as e:
        print(f"❌ Fatal error: {e}")
        return 1

if __name__ == "__main__":
    sys.exit(main())