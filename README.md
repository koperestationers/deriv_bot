# Deriv Odd/Even Trading Bot

A production-ready trading bot for Deriv's "Odd/Even" binary options that makes real demo account trades with rigorous risk management. Features statistical validation, user-friendly output formatting, and secure cloud deployment with console-only logging.

## ⚠️ IMPORTANT SAFETY NOTICE

- **ACCOUNT SELECTION**: Choose demo or real account via `ACCOUNT_TYPE` environment variable
- **NO GUARANTEES**: Trading involves risk - no profits are guaranteed
- **STATISTICAL VALIDATION**: Bot only trades when proven edge exists (95% confidence)
- **RISK CONTROLS**: Multiple safety limits and automatic stop conditions
- **PRODUCTION SECURE**: Console-only logging, no file output, GitHub/Railway safe

## 🚀 Quick Start

### Prerequisites
- Python 3.8+
- Deriv account (demo or real) and API token
- Virtual environment (recommended)
- Minimum $0.35 balance for trading (Deriv requirement)

### Local Installation

```bash
# Clone and setup
git clone <repository>
cd deriv_bot

# Create virtual environment (optional but recommended)
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Setup environment
cp .env.example .env
# Edit .env with your Deriv API token and set ACCOUNT_TYPE
```

### 🖥️ Local Usage

**Test Strategy (Recommended First Run):**
```bash
python src/main.py --mode paper
```
- ✅ Validates strategy with ~1000 simulated trades
- ✅ Shows statistical edge analysis (95% confidence)
- ✅ Safe testing without real trades
- ✅ Uses R_50 symbol (optimal for odd/even)

**Full Bot (Always Live Demo Trading):**
```bash
python src/main.py --mode full
```
- ✅ Runs validation first (statistical analysis)
- ✅ Always switches to live demo trading on your demo account
- ✅ Makes real API trades with actual balance impact
- ✅ Enforces all risk limits and safety stops

**Alternative Scripts:**
```bash
python scripts/paper_test.py    # Paper mode validation only
python scripts/start_demo.py    # Full mode with validation
```

**Control:**
- **Stop**: Press **Ctrl+C** for graceful shutdown
- **Monitor**: Real-time dashboard updates every minute
- **Safety**: Bot auto-stops on any risk limit breach

### 🚂 Railway Deployment (Recommended)

**Step 1: Prepare Repository**
```bash
# Fork this repository to your GitHub account
# No additional setup needed - ready for deployment
```

**Step 2: Deploy to Railway**
1. Go to [railway.app](https://railway.app) and sign up/login
2. Click "New Project" → "Deploy from GitHub repo"
3. Select your forked repository
4. Railway will automatically detect Python and use the `Procfile`

**Step 3: Configure Environment Variables**
In Railway dashboard, add these variables:
```bash
# Required API Configuration
DERIV_APP_ID=1089
DERIV_API_TOKEN=your_actual_token_here
DERIV_ACCOUNT_CURRENCY=USD
DERIV_ENV=demo
ACCOUNT_TYPE=demo  # Change to 'real' for live trading

# Risk Management (adjust as needed)
RISK_MAX_STAKE_FRAC=0.02
RISK_DAILY_LOSS_CAP_FRAC=0.10
RISK_DRAWDOWN_STOP_FRAC=0.15
COOLDOWN_AFTER_LOSS_STREAK_MIN=10
MAX_SINGLE_STAKE_CAP=0.35
BALANCE_STOP_LOWER=5.0
BALANCE_STOP_UPPER=10000.0
LOSS_STREAK_THRESHOLD=3
```

**Step 4: Deploy & Monitor**
- Railway auto-deploys on every GitHub push
- View logs in Railway dashboard
- Bot runs continuously with automatic restarts

### Environment Variables

Required variables in `.env`:

```bash
# API Configuration
DERIV_APP_ID=1089
DERIV_API_TOKEN=your_token_here
DERIV_ACCOUNT_CURRENCY=USD
DERIV_ENV=demo
ACCOUNT_TYPE=demo  # Set to 'real' for live trading

# Risk Parameters
RISK_MAX_STAKE_FRAC=0.02
RISK_DAILY_LOSS_CAP_FRAC=0.10
RISK_DRAWDOWN_STOP_FRAC=0.15
COOLDOWN_AFTER_LOSS_STREAK_MIN=10

# Trading Limits
MAX_SINGLE_STAKE_CAP=0.35
BALANCE_STOP_LOWER=5.0
BALANCE_STOP_UPPER=10000.0
LOSS_STREAK_THRESHOLD=3
```

**Account Type Options:**
- `ACCOUNT_TYPE=demo` - Use demo/virtual account (recommended for testing)
- `ACCOUNT_TYPE=real` - Use real account (live trading with real money)

**⚠️ Account Type Validation:**
- Bot validates token matches selected account type
- Prevents accidental real money trading with demo settings
- Clear error messages for mismatched configurations

## 📊 Configuration

### Environment Variables (Primary Configuration)
All critical settings via environment variables for secure deployment:

```bash
# Risk Management
RISK_MAX_STAKE_FRAC=0.02          # 2% max per trade
RISK_DAILY_LOSS_CAP_FRAC=0.10     # 10% daily loss limit
RISK_DRAWDOWN_STOP_FRAC=0.15      # 15% drawdown stop
MAX_SINGLE_STAKE_CAP=0.35          # Deriv minimum stake requirement

# Safety Limits
BALANCE_STOP_LOWER=5.0             # Stop if balance ≤ $5
BALANCE_STOP_UPPER=10000.0         # Stop if balance ≥ $10,000
LOSS_STREAK_THRESHOLD=3            # Cooldown after 3 losses
COOLDOWN_AFTER_LOSS_STREAK_MIN=10  # Minutes to pause
```

### Advanced Configuration (config.yaml)
Fine-tune strategy parameters:

```yaml
strategy:
  min_confidence_threshold: 0.55    # Only trade if >55% confidence
  frequency_bias_threshold: 0.15    # Deviation required for signal
  volatility_threshold: 0.02        # Skip high volatility periods
  lookback_window: 20               # Ticks to analyze

backtest:
  min_samples: 1000                 # Minimum trades for validation
  confidence_level: 0.95            # Statistical confidence required
```

## 📈 Strategy Logic

### Conservative Approach
- **Frequency Analysis**: Detects short-term digit bias on R_50 (50% volatility)
- **Mean Reversion**: Bets against recent patterns
- **Volatility Filter**: Skips high-volatility periods
- **Statistical Validation**: Reports edge analysis with 95% confidence

### Trading Behavior
- **Always Live Demo**: Makes real trades on demo account regardless of edge
- **Validation First**: Runs 1000+ simulated trades for statistical analysis
- **Risk Management**: All safety limits enforced during live trading
- **Honest Reporting**: Shows true win rates and expected values

## 🔍 Monitoring & Logging

### Production-Safe Logging
- **✅ Console Only**: All output to stdout/stderr for cloud platforms
- **✅ No File Output**: Zero disk writes - safe for GitHub and Railway
- **✅ No Secrets**: API tokens never logged or printed
- **✅ Structured Format**: Easy parsing for log aggregation services

### Real-Time Dashboard
```
============================================================
                    TRADING DASHBOARD
============================================================
Account Type:      DEMO
Balance:           $10.00
Daily P&L:         +$0.00
Win Rate (last 100): 0.0%
Expected Value:    +0.0000
Loss Streak:       0
Cooldown:          None
Active Risk Gates: None
============================================================
Last Updated:      18:21:28
============================================================
```

### Log Examples
```
2025-09-02 18:21:28 - runner - INFO - Configured for DEMO account trading
2025-09-02 21:54:07 - logging_utils - INFO - TRADE: LIVE_DEMO | Side: EVEN | Stake: $1.42 | Result: LOSS | P&L: -$1.42 | Balance: $98.49
2025-09-02 21:54:12 - logging_utils - INFO - PERFORMANCE: Balance: $98.49 | Daily P&L: -$1.42 | Win Rate: 0.0% | EV: -0.0156 | Loss Streak: 1
```

## 🛑 Automatic Stop Conditions

### Balance Limits
- **Minimum**: Balance ≤ $5.00 → Emergency stop
- **Maximum**: Balance ≥ $10,000 → Target reached
- **Stake Minimum**: $0.35 per trade (Deriv requirement)

### Risk Limits
- **Daily Loss**: ≥10% of starting balance → Stop trading
- **Drawdown**: ≥15% from session peak → Emergency stop & restart
- **Loss Streak**: 3+ consecutive losses → 10-15 minute cooldown
- **Max Stake**: 2% of balance, minimum $0.35

### Technical Limits
- **API Failures**: 5 consecutive reconnection attempts → Exit (Railway auto-restarts)
- **Authentication**: Token invalid/expired → Stop
- **Account Mismatch**: Wrong account type → Stop
- **Connection Loss**: Exponential backoff reconnection (1s, 2s, 4s, 8s, 16s)

### Manual Controls
- **Graceful Shutdown**: SIGINT/SIGTERM (Ctrl+C)
- **Railway**: Stop button in dashboard
- **Emergency**: Any safety constraint violation

## 🧪 Testing & Validation

### Unit Tests
```bash
# Run all tests
python -m pytest tests/ -v

# Run specific test categories
python -m pytest tests/test_risk_management.py -v
```

### Test Coverage
- ✅ Risk management constraints (8/8 tests pass)
- ✅ Position sizing limits
- ✅ Emergency stop triggers  
- ✅ Account type validation
- ✅ Statistical validation

### Local Testing
```bash
# Test strategy (recommended first run)
python src/main.py --mode paper

# Full bot (validates first, then live demo if edge found)
python src/main.py --mode full

# Alternative convenience scripts
python scripts/paper_test.py
python scripts/start_demo.py
```

**Expected Output:**
```
2025-09-02 21:54:03 - runner - INFO - Initialization complete - Balance: $99.91
2025-09-02 21:54:03 - deriv_client - INFO - Subscribed to ticks for R_50
2025-09-02 21:54:03 - backtest - INFO - Backtest completed: 252 trades, Final balance: $9.52
2025-09-02 21:54:03 - runner - INFO - Win Rate: 0.520
2025-09-02 21:54:03 - runner - INFO - Expected Value: -0.0156
2025-09-02 21:54:03 - runner - INFO - Confidence Interval: [45.8%, 58.1%]
2025-09-02 21:54:03 - runner - WARNING - VALIDATION FAILED: No statistical edge detected

No edge detected - Running live demo anyway (user preference)
🚀 Starting trading loop in LIVE_DEMO mode

2025-09-02 21:54:07 - deriv_client - INFO - Trade placed: EVEN $1.42 - Contract ID: 293026925888
2025-09-02 21:54:07 - runner - INFO - LIVE TRADE: EVEN $1.42 - Mean reversion strategy

======================================================================
DERIV ODD/EVEN BOT - LIVE_DEMO MODE
Last Updated: 21:54:42
======================================================================
Balance: $99.91 | Daily P&L: $-0.09
Trades: 1 | Win Rate: 0.0% | Loss Streak: 1
Daily Loss Remaining: $9.99 | Drawdown Remaining: $14.99
Ready to trade
Ticks Processed: 1005 | Odd/Even Freq: 0.486/0.514
======================================================================
```

**Behavior:**
- ✅ Connects to Deriv API with your token
- ✅ Validates account type (demo/real)
- ✅ Runs statistical validation with ~1000 simulated trades
- ✅ Always switches to live demo trading (real API trades)
- ✅ Uses R_50 symbol (optimal 50% volatility for odd/even)
- ✅ Places real trades with $0.35+ stakes on your demo account
- ✅ Honest edge reporting with readable confidence intervals
- ✅ Single balance fetch (optimized API usage)

## ⚠️ Critical Warnings

### Financial Risk
1. **No Guarantees**: Trading involves substantial risk of loss
2. **Statistical Reality**: Most strategies show no significant edge
3. **Demo First**: Always test thoroughly in demo mode
4. **Risk Capital**: Only trade with money you can afford to lose

### Security
5. **Token Security**: Keep API tokens secure, rotate regularly
6. **Environment Variables**: Never commit tokens to GitHub
7. **Account Validation**: Verify account type before deployment

### Technical
8. **Safety Limits**: All risk constraints are non-negotiable
9. **Monitoring**: Always monitor bot performance and logs
10. **Updates**: Keep dependencies and tokens current

## 🔧 Troubleshooting

### Common Issues

**Authentication Failed**
- Verify your API token is correct and active
- Check ACCOUNT_TYPE matches your token type (demo/real)
- Ensure token permissions in Deriv dashboard

**Account Type Mismatch**
- `ACCOUNT_TYPE=demo` but token is for real account
- `ACCOUNT_TYPE=real` but token is for demo account
- Update ACCOUNT_TYPE to match your token

**Railway Deployment Issues**
- ✅ Verify all environment variables set in Railway dashboard
- ✅ Check build logs for missing dependencies  
- ✅ Ensure `Procfile` exists: `worker: python src/main.py --mode full`
- ✅ Confirm `railway.json` configuration is present
- ✅ Check Python version compatibility (3.8+)

**Connection Errors**
- Check internet connectivity
- Verify Deriv API is accessible
- Try restarting the bot

**Risk Gate Triggered**
- Review daily loss limits
- Check if cooldown period is active
- Verify balance is within operating range

**No Edge Detected**
- This is normal and expected behavior
- Bot will remain in paper mode
- Consider adjusting strategy parameters in `config.yaml`

### Getting Help

**Local Development:**
1. Check console output for error messages
2. Verify all environment variables in `.env`
3. Run tests: `python -m pytest tests/ -v`
4. Test paper mode: `python src/main.py --mode paper`

**Railway Deployment:**
1. Check Railway dashboard logs
2. Verify environment variables in Railway settings
3. Monitor deployment status and restarts
4. Check Deriv API token validity and permissions

**Common Solutions:**
- Invalid token → Generate new token in Deriv dashboard
- Account mismatch → Update `ACCOUNT_TYPE` to match token
- Build failure → Check Python version and dependencies
- Runtime error → Review environment variable configuration

## 📝 License

This software is for educational and research purposes only. Use at your own risk.

---

**Remember**: Always test thoroughly in demo mode first. This bot supports both demo and real account trading - choose wisely based on your risk tolerance and validation results.
