import os
import logging
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from flask import Flask, render_template, request, jsonify
from flask_wtf.csrf import CSRFProtect, generate_csrf
from datetime import datetime
from src.models import (db,RecurringExpense, Income, Expense, ExpenseCategory, StockPrice, GoldSellTransaction,
                        GoldTransaction, GoldPrice, ExchangeRate, Inflation, Savings, SavingsGoal,
                        StockTransaction, StockSellTransaction, MutualFundTransaction, MutualFundSellTransaction, MutualFundNAV)
from src.routes import income_routes, expense_routes, gold_routes, exchange_routes, inflation_routes, savings_routes, import_routes
from src.routes.investment_routes import investment_bp, calculate_fees
from src.routes.expense_routes import expense_bp

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__, instance_relative_config=True)
app.config['SECRET_KEY'] = os.getenv('FLASK_SECRET_KEY', '23e92c9b4346ebb0f5040e0a53d90dde')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db_folder = os.path.abspath(os.path.join(app.instance_path, 'db'))
db_file = os.path.join(db_folder, 'finance_tracker.db')
try:
    if not os.path.exists(db_folder):
        os.makedirs(db_folder)
        logger.info(f"Created database directory: {db_folder}")
    db_uri = f"sqlite:///{db_file}"
    logger.info(f"Database URI: {db_uri}")
    app.config['SQLALCHEMY_DATABASE_URI'] = db_uri
except Exception as e:
    logger.error(f"Error setting up database path: {str(e)}")
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'

csrf = CSRFProtect(app)
db.init_app(app)

@app.context_processor
def inject_csrf_token():
    return dict(csrf_token=generate_csrf)

app.register_blueprint(income_routes.income_bp)
app.register_blueprint(expense_routes.expense_bp, url_prefix='/expense')
app.register_blueprint(gold_routes.gold_bp)
app.register_blueprint(exchange_routes.exchange_bp)
app.register_blueprint(inflation_routes.inflation_bp)
app.register_blueprint(savings_routes.savings_bp)
app.register_blueprint(import_routes.import_bp)
app.register_blueprint(investment_bp)

@app.route('/')
def index():
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    
    income_query = Income.query
    expense_query = Expense.query
    exchange_query = ExchangeRate.query
    gold_query = GoldPrice.query
    inflation_query = Inflation.query
    
    if start_date and end_date:
        try:
            start_date = datetime.strptime(start_date, '%Y-%m-%d').date()
            end_date = datetime.strptime(end_date, '%Y-%m-%d').date()
            income_query = income_query.filter(Income.date >= start_date, Income.date <= end_date)
            expense_query = expense_query.filter(Expense.date >= start_date, Expense.date <= end_date)
            exchange_query = exchange_query.filter(ExchangeRate.date >= start_date, ExchangeRate.date <= end_date)
            gold_query = gold_query.filter(GoldPrice.date >= start_date, GoldPrice.date <= end_date)
            inflation_query = inflation_query.filter(Inflation.date >= start_date, Inflation.date <= end_date)
        except ValueError:
            pass

    total_income = income_query.with_entities(db.func.sum(Income.amount)).scalar() or 0.0
    total_expenses = expense_query.with_entities(db.func.sum(Expense.amount)).scalar() or 0.0
    latest_exchange_rate = exchange_query.order_by(ExchangeRate.date.desc()).first()
    latest_gold_price = gold_query.filter(GoldPrice.price_24k.isnot(None)).order_by(GoldPrice.date.desc()).first()
    latest_inflation = inflation_query.filter_by(category='all', country='EGY').order_by(Inflation.date.desc()).first()

    # Investment summary
    gold_query = GoldTransaction.query
    gold_sell_query = GoldSellTransaction.query
    stock_query = StockTransaction.query
    stock_sell_query = StockSellTransaction.query
    fund_query = MutualFundTransaction.query
    fund_sell_query = MutualFundSellTransaction.query
    if start_date:
        gold_query = gold_query.filter(GoldTransaction.date >= start_date)
        gold_sell_query = gold_sell_query.filter(GoldSellTransaction.date >= start_date)
        stock_query = stock_query.filter(StockTransaction.date >= start_date)
        stock_sell_query = stock_sell_query.filter(StockSellTransaction.date >= start_date)
        fund_query = fund_query.filter(MutualFundTransaction.date >= start_date)
        fund_sell_query = fund_sell_query.filter(MutualFundSellTransaction.date >= start_date)
    if end_date:
        gold_query = gold_query.filter(GoldTransaction.date <= end_date)
        gold_sell_query = gold_sell_query.filter(GoldSellTransaction.date <= end_date)
        stock_query = stock_query.filter(StockTransaction.date <= end_date)
        stock_sell_query = stock_sell_query.filter(StockSellTransaction.date <= end_date)
        fund_query = fund_query.filter(MutualFundTransaction.date <= end_date)
        fund_sell_query = fund_sell_query.filter(MutualFundSellTransaction.date <= end_date)

    # Gold investment
    transactions = gold_query.all()
    sell_transactions = gold_sell_query.all()
    total_weight = {'24': 0, '21': 0, '18': 0}
    weighted_price = {'24': 0, '21': 0, '18': 0}
    for t in transactions:
        k = str(t.karat)
        total_weight[k] += t.weight
        weighted_price[k] += t.weight * t.purchase_price
    for s in sell_transactions:
        k = str(s.karat)
        total_weight[k] = max(0, total_weight[k] - s.weight)
    latest_gold_price = GoldPrice.query.filter_by(price_type='local').order_by(GoldPrice.date.desc()).first()
    gold_value = 0.0
    if latest_gold_price:
        for k in ['24', '21', '18']:
            price = (
                latest_gold_price.price_24k if k == '24' else
                latest_gold_price.price_21k if k == '21' else
                latest_gold_price.price_18k
            )
            gold_value += total_weight[k] * price

    # Stock investment
    stock_remaining = {}  # ticker: {buy_id: remaining_qty}
    for t in stock_query.order_by(StockTransaction.date.asc()).all():
        if t.ticker not in stock_remaining:
            stock_remaining[t.ticker] = {}
        stock_remaining[t.ticker][t.id] = t.quantity
    for s in stock_sell_query.order_by(StockSellTransaction.date.asc()).all():
        sold_qty = s.quantity
        for t in stock_query.filter_by(ticker=s.ticker).order_by(StockTransaction.date.asc()).all():
            if sold_qty <= 0:
                break
            if t.id in stock_remaining[s.ticker] and stock_remaining[s.ticker][t.id] > 0:
                qty_to_use = min(sold_qty, stock_remaining[s.ticker][t.id])
                stock_remaining[s.ticker][t.id] -= qty_to_use
                sold_qty -= qty_to_use

    stock_value = 0.0
    total_stock_investment = 0.0
    for t in stock_query.all():
        if t.ticker in stock_remaining and t.id in stock_remaining[t.ticker]:
            remaining_qty = stock_remaining[t.ticker][t.id]
            if remaining_qty > 0:
                total_stock_investment += remaining_qty * t.purchase_price
                latest_price = StockPrice.query.filter_by(ticker=t.ticker).order_by(StockPrice.date.desc()).first()
                stock_value += remaining_qty * (latest_price.price if latest_price else t.purchase_price)

    # Mutual Fund investment
    fund_remaining = {}  # fund_name: {buy_id: remaining_units}
    for t in fund_query.order_by(MutualFundTransaction.date.asc()).all():
        if t.fund_name not in fund_remaining:
            fund_remaining[t.fund_name] = {}
        fund_remaining[t.fund_name][t.id] = t.units
    for s in fund_sell_query.order_by(MutualFundSellTransaction.date.asc()).all():
        sold_qty = s.units
        for t in fund_query.filter_by(fund_name=s.fund_name).order_by(MutualFundTransaction.date.asc()).all():
            if sold_qty <= 0:
                break
            if t.id in fund_remaining[s.fund_name] and fund_remaining[s.fund_name][t.id] > 0:
                qty_to_use = min(sold_qty, fund_remaining[s.fund_name][t.id])
                fund_remaining[s.fund_name][t.id] -= qty_to_use
                sold_qty -= qty_to_use

    fund_value = 0.0
    total_fund_investment = 0.0
    for t in fund_query.all():
        if t.fund_name in fund_remaining and t.id in fund_remaining[t.fund_name]:
            remaining_units = fund_remaining[t.fund_name][t.id]
            if remaining_units > 0:
                total_fund_investment += remaining_units * t.purchase_nav
                latest_nav = MutualFundNAV.query.filter_by(fund_name=t.fund_name).order_by(MutualFundNAV.date.desc()).first()
                fund_value += remaining_units * (latest_nav.nav if latest_nav else t.purchase_nav)

    total_investment = weighted_price['24'] + weighted_price['21'] + weighted_price['18'] + total_stock_investment + total_fund_investment
    investment_value = gold_value + stock_value + fund_value

    return render_template('index.html',
                         total_income=total_income,
                         total_expenses=total_expenses,
                         latest_exchange_rate=latest_exchange_rate.rate if latest_exchange_rate else None,
                         latest_gold_price=latest_gold_price.price_24k if latest_gold_price else None,
                         latest_inflation=latest_inflation.rate if latest_inflation else None,
                         investment_value=investment_value)

@app.template_filter('format_currency')
def format_currency(value):
    try:
        if value is None or value == '':
            return 'EGP 0.00'
        return f"EGP {float(value):,.2f}"
    except (ValueError, TypeError):
        return 'EGP 0.00'

@app.template_filter('format_percentage')
def format_percentage(value):
    return f"{value:.2f}%" if value else "N/A"

@app.route('/api/dashboard')
def api_dashboard():
    try:
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')
        
        income_query = Income.query
        expense_query = Expense.query
        gold_query = GoldTransaction.query
        gold_sell_query = GoldSellTransaction.query
        stock_query = StockTransaction.query
        stock_sell_query = StockSellTransaction.query
        fund_query = MutualFundTransaction.query
        fund_sell_query = MutualFundSellTransaction.query
        
        if start_date:
            try:
                start_date = datetime.strptime(start_date, '%Y-%m-%d').date()
                income_query = income_query.filter(Income.date >= start_date)
                expense_query = expense_query.filter(Expense.date >= start_date)
                gold_query = gold_query.filter(GoldTransaction.date >= start_date)
                gold_sell_query = gold_sell_query.filter(GoldSellTransaction.date >= start_date)
                stock_query = stock_query.filter(StockTransaction.date >= start_date)
                stock_sell_query = stock_sell_query.filter(StockSellTransaction.date >= start_date)
                fund_query = fund_query.filter(MutualFundTransaction.date >= start_date)
                fund_sell_query = fund_sell_query.filter(MutualFundSellTransaction.date >= start_date)
            except ValueError:
                logger.warning(f"Invalid start_date: {start_date}")
                return jsonify({'error': 'Invalid start_date format'}), 400
        
        if end_date:
            try:
                end_date = datetime.strptime(end_date, '%Y-%m-%d').date()
                income_query = income_query.filter(Income.date <= end_date)
                expense_query = expense_query.filter(Expense.date <= end_date)
                gold_query = gold_query.filter(GoldTransaction.date <= end_date)
                gold_sell_query = gold_sell_query.filter(GoldSellTransaction.date <= end_date)
                stock_query = stock_query.filter(StockTransaction.date <= end_date)
                stock_sell_query = stock_sell_query.filter(StockSellTransaction.date <= end_date)
                fund_query = fund_query.filter(MutualFundTransaction.date <= end_date)
                fund_sell_query = fund_sell_query.filter(MutualFundSellTransaction.date <= end_date)
            except ValueError:
                logger.warning(f"Invalid end_date: {end_date}")
                return jsonify({'error': 'Invalid end_date format'}), 400
        
        total_income = sum(float(i.amount) for i in income_query.all())
        total_expenses = sum(float(e.amount) for e in expense_query.all())
        latest_exchange_rate = ExchangeRate.query.order_by(ExchangeRate.date.desc()).first()
        latest_gold_price = GoldPrice.query.filter(GoldPrice.price_24k.isnot(None)).order_by(GoldPrice.date.desc()).first()
        latest_inflation = Inflation.query.filter(Inflation.yearly_rate.isnot(None)).filter_by(category='all', country='EGY').order_by(Inflation.date.desc()).first()
        
        # Investment summary
        total_investment = 0.0
        investment_value = 0.0
        gold_value = 0.0
        stock_value = 0.0
        fund_value = 0.0

        # Gold
        transactions = gold_query.all()
        sell_transactions = gold_sell_query.all()
        total_weight = {'24': 0, '21': 0, '18': 0}
        weighted_price = {'24': 0, '21': 0, '18': 0}
        for t in transactions:
            k = str(t.karat)
            total_weight[k] += t.weight
            weighted_price[k] += t.weight * t.purchase_price
            total_investment += t.weight * t.purchase_price
        for s in sell_transactions:
            k = str(s.karat)
            total_weight[k] = max(0, total_weight[k] - s.weight)
            k_weight = sum(t.weight for t in transactions if str(t.karat) == k)
            k_price = weighted_price[k] / k_weight if k_weight > 0 else 0
            total_investment -= s.weight * k_price
        latest_gold_price = GoldPrice.query.filter_by(price_type='local').order_by(GoldPrice.date.desc()).first()
        if latest_gold_price:
            for k in ['24', '21', '18']:
                price = (
                    latest_gold_price.price_24k if k == '24' else
                    latest_gold_price.price_21k if k == '21' else
                    latest_gold_price.price_18k
                )
                gold_value += total_weight[k] * price
        
        # Stocks
        stock_remaining = {}  # ticker: {buy_id: remaining_qty}
        for t in stock_query.order_by(StockTransaction.date.asc()).all():
            if t.ticker not in stock_remaining:
                stock_remaining[t.ticker] = {}
            stock_remaining[t.ticker][t.id] = t.quantity
        for s in stock_sell_query.order_by(StockSellTransaction.date.asc()).all():
            sold_qty = s.quantity
            for t in stock_query.filter_by(ticker=s.ticker).order_by(StockTransaction.date.asc()).all():
                if sold_qty <= 0:
                    break
                if t.id in stock_remaining[s.ticker] and stock_remaining[s.ticker][t.id] > 0:
                    qty_to_use = min(sold_qty, stock_remaining[s.ticker][t.id])
                    stock_remaining[s.ticker][t.id] -= qty_to_use
                    sold_qty -= qty_to_use

        stock_value = 0.0
        total_stock_investment = 0.0
        for t in stock_query.all():
            if t.ticker in stock_remaining and t.id in stock_remaining[t.ticker]:
                remaining_qty = stock_remaining[t.ticker][t.id]
                if remaining_qty > 0:
                    total_stock_investment += remaining_qty * t.purchase_price
                    latest_price = StockPrice.query.filter_by(ticker=t.ticker).order_by(StockPrice.date.desc()).first()
                    stock_value += remaining_qty * (latest_price.price if latest_price else t.purchase_price)

        # Mutual Funds
        fund_remaining = {}  # fund_name: {buy_id: remaining_units}
        for t in fund_query.order_by(MutualFundTransaction.date.asc()).all():
            if t.fund_name not in fund_remaining:
                fund_remaining[t.fund_name] = {}
            fund_remaining[t.fund_name][t.id] = t.units
        for s in fund_sell_query.order_by(MutualFundSellTransaction.date.asc()).all():
            sold_qty = s.units
            for t in fund_query.filter_by(fund_name=s.fund_name).order_by(MutualFundTransaction.date.asc()).all():
                if sold_qty <= 0:
                    break
                if t.id in fund_remaining[s.fund_name] and fund_remaining[s.fund_name][t.id] > 0:
                    qty_to_use = min(sold_qty, fund_remaining[s.fund_name][t.id])
                    fund_remaining[s.fund_name][t.id] -= qty_to_use
                    sold_qty -= qty_to_use

        fund_value = 0.0
        total_fund_investment = 0.0
        for t in fund_query.all():
            if t.fund_name in fund_remaining and t.id in fund_remaining[t.fund_name]:
                remaining_units = fund_remaining[t.fund_name][t.id]
                if remaining_units > 0:
                    total_fund_investment += remaining_units * t.purchase_nav
                    latest_nav = MutualFundNAV.query.filter_by(fund_name=t.fund_name).order_by(MutualFundNAV.date.desc()).first()
                    fund_value += remaining_units * (latest_nav.nav if latest_nav else t.purchase_nav)

        total_investment = total_investment + total_stock_investment + total_fund_investment
        investment_value = gold_value + stock_value + fund_value
        total_savings = ((total_income - total_expenses) - total_investment) + investment_value
        net_balance = (total_income - total_expenses) - total_investment
        investment_return = ((investment_value - total_investment) / total_investment * 100) if total_investment > 0 else 0.0
        
        cash_percentage = (net_balance / total_savings * 100) if total_savings > 0 else 0.0
        investment_percentage = (investment_value / total_savings * 100) if total_savings > 0 else 0.0
        gold_percentage = (gold_value / investment_value * 100) if investment_value > 0 else 0.0
        stock_percentage = (stock_value / investment_value * 100) if investment_value > 0 else 0.0
        fund_percentage = (fund_value / investment_value * 100) if investment_value > 0 else 0.0
        
        return jsonify({
            'total_income': float(total_income),
            'total_expenses': float(total_expenses),
            'latest_exchange_rate': float(latest_exchange_rate.rate) if latest_exchange_rate else 0.0,
            'latest_gold_price': float(latest_gold_price.price_24k) if latest_gold_price else 0.0,
            'latest_inflation': float(latest_inflation.rate) if latest_inflation else 0.0,
            'total_investment': float(total_investment),
            'investment_value': float(investment_value),
            'cash_percentage': float(cash_percentage),
            'investment_percentage': float(investment_percentage),
            'investment_return': float(investment_return),
            'gold_percentage': float(gold_percentage),
            'stock_percentage': float(stock_percentage),
            'fund_percentage': float(fund_percentage)
        })
    except Exception as e:
        logger.error(f"Error in api_dashboard: {str(e)}")
        return jsonify({'error': str(e)}), 500
@app.route('/debug/endpoints')
def debug_endpoints():
    return jsonify([rule.endpoint for rule in app.url_map.iter_rules()])

with app.app_context():
    db.create_all()
    print("Database setup complete.")
if __name__ == '__main__':
    
    app.run(host='0.0.0.0', port=5000, debug=True)

