from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from datetime import datetime, timedelta
from src.models import db, StockTransaction, StockSellTransaction, MutualFundTransaction, MutualFundSellTransaction, StockPrice, MutualFundNAV, Income
import csv
from io import StringIO
import logging
from ..forms import TransactionForm

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

investment_bp = Blueprint('investment', __name__, url_prefix='/investment', template_folder='templates/investment')

# Fee constants for stock transactions
EGX_FEE_RATE = 0.0001  # 0.01%
MCDR_FEE_RATE = 0.0001  # 0.01%
FRA_FEE_RATE = 0.00005  # 0.005%, max 1 EGP
RISK_INSURANCE_RATE = 0.00005  # 0.005%
BROKERAGE_ORDER_FEE = 2  # Flat 2 EGP
BROKERAGE_CUSTODY_RATE = 0.001  # 0.1%
def calculate_fees(total_value, is_stock=True):
    """Calculate fees for stock or mutual fund transactions based on total value."""
    if is_stock:
        egx_fee = total_value * EGX_FEE_RATE
        mcdr_fee = total_value * MCDR_FEE_RATE
        fra_fee = max(total_value * FRA_FEE_RATE, 1)  # Max 1 EGP
        risk_insurance_fee = total_value * RISK_INSURANCE_RATE
        brokerage_custody_fee = total_value * BROKERAGE_CUSTODY_RATE
        total_fees = egx_fee + mcdr_fee + fra_fee + risk_insurance_fee + BROKERAGE_ORDER_FEE + brokerage_custody_fee
    else:
        # Mutual fund: only brokerage fees
        egx_fee = 0
        mcdr_fee = 0
        fra_fee = 0
        risk_insurance_fee = 0
        brokerage_custody_fee = total_value * BROKERAGE_CUSTODY_RATE
        total_fees = BROKERAGE_ORDER_FEE + brokerage_custody_fee

    return {
        'egx_fee': round(egx_fee, 4),
        'mcdr_fee': round(mcdr_fee, 4),
        'fra_fee': round(fra_fee, 4),
        'risk_insurance_fee': round(risk_insurance_fee, 4),
        'brokerage_order_fee': round(BROKERAGE_ORDER_FEE, 4),
        'brokerage_custody_fee': round(brokerage_custody_fee, 4),
        'total_fees': round(total_fees, 4)
    }

@investment_bp.route('/')
def index():
    return render_template('investment/index.html')

@investment_bp.route('/transactions')
def transactions():
    return render_template('investment/transactions.html')

@investment_bp.route('/transaction/<type>', methods=['GET', 'POST'])
@investment_bp.route('/transaction/<type>/<int:id>', methods=['GET', 'POST'])
def transaction_form(type, id=None):
    # Initial type determination from URL
    is_buy = 'buy' in type.lower()
    is_stock = 'stock' in type.lower()
    security_type = 'stock' if is_stock else 'mutual_fund'
    logger.debug(f"Initial: type={type}, is_buy={is_buy}, is_stock={is_stock}, id={id}")

    if id:
        # Load existing transaction
        model = None
        if is_stock:
            model = StockTransaction if is_buy else StockSellTransaction
        else:
            model = MutualFundTransaction if is_buy else MutualFundSellTransaction
        transaction = model.query.get_or_404(id)
        # Confirm transaction type
        is_buy = isinstance(transaction, (StockTransaction, MutualFundTransaction))
        is_stock = isinstance(transaction, (StockTransaction, StockSellTransaction))
        security_type = 'stock' if is_stock else 'mutual_fund'
        logger.debug(f"After loading transaction: is_buy={is_buy}, is_stock={is_stock}, transaction_type={type(transaction).__name__}")
    else:
        transaction = None

    form = TransactionForm()

    if request.method == 'POST':
        security_type = request.form.get('security_type')
        is_stock = security_type == 'stock'
        logger.debug(f"POST: security_type={security_type}, is_stock={is_stock}")

        # For existing transactions, use transaction type
        if transaction:
            is_buy = isinstance(transaction, (StockTransaction, MutualFundTransaction))
            logger.debug(f"Editing transaction: is_buy={is_buy}, transaction_type={type(transaction).__name__}")
        else:
            is_buy = 'buy' in type.lower()

        model = (StockTransaction if is_buy and is_stock else
                 StockSellTransaction if not is_buy and is_stock else
                 MutualFundTransaction if is_buy and not is_stock else
                 MutualFundSellTransaction)

        try:
            quantity = float(request.form.get('quantity'))
            price = float(request.form.get('price'))
            date = request.form.get('date')
            identifier = request.form.get('ticker' if is_stock else 'fund_name')
            description = request.form.get('description', '')
            logger.debug(f"Form data: quantity=%s, price=%s, identifier=%s", quantity, price, identifier)

            if transaction:
                # Update existing transaction
                if isinstance(transaction, StockTransaction):
                    transaction.ticker = identifier
                    transaction.quantity = quantity
                    transaction.purchase_price = price
                elif isinstance(transaction, StockSellTransaction):
                    transaction.ticker = identifier
                    transaction.quantity = quantity
                    transaction.sell_price = price
                elif isinstance(transaction, MutualFundTransaction):
                    transaction.fund_name = identifier
                    transaction.units = quantity
                    transaction.purchase_nav = price
                elif isinstance(transaction, MutualFundSellTransaction):
                    transaction.fund_name = identifier
                    transaction.units = quantity
                    transaction.sell_nav = price

                transaction.date = date
                transaction.description = description
            else:
                # Create new transaction
                kwargs = {
                    ('ticker' if is_stock else 'fund_name'): identifier,
                    ('quantity' if is_stock else 'units'): quantity,
                    ('purchase_price' if is_buy and is_stock else
                     'sell_price' if not is_buy and is_stock else
                     'purchase_nav' if is_buy and not is_stock else
                     'sell_nav'): price,
                    'date': date,
                    'description': description
                }
                new_transaction = model(**kwargs)
                db.session.add(new_transaction)

            db.session.commit()
            flash('Transaction updated successfully.', 'success')
            return redirect(url_for('investment.transactions'))
        except Exception as e:
            db.session.rollback()
            flash(f'Error saving transaction: {str(e)}', 'danger')
            logger.error(f"Error saving transaction: {str(e)}")
            return render_template('investment/transaction_form.html',
                                 transaction=transaction,
                                 is_stock=is_stock,
                                 is_buy=is_buy,
                                 security_type=security_type,
                                 fees=calculate_fees(0, is_stock))

    fees = calculate_fees(0, is_stock)
    return render_template('investment/transaction_form.html',
                         transaction=transaction,
                         is_stock=is_stock,
                         is_buy=is_buy,
                         security_type=security_type,
                         fees=fees)

@investment_bp.route('/api/calculate-fees', methods=['POST'])
def calculate_fees_api():
    try:
        data = request.get_json()
        total_value = float(data.get('total_value', 0))
        security_type = data.get('security_type', 'stock')
        is_stock = security_type == 'stock'
        fees = calculate_fees(total_value, is_stock)
        return jsonify(fees)
    except Exception as e:
        logger.error(f"Error calculating fees: {str(e)}")
        return jsonify({'error': str(e)}), 400

@investment_bp.route('/transactions/delete/<int:id>/<type>', methods=['POST'])
def delete_transaction(id, type):
    is_stock = type.startswith('stock')
    model = StockSellTransaction if is_stock and type.endswith('sell') else StockTransaction if is_stock else MutualFundSellTransaction if type.endswith('sell') else MutualFundTransaction
    transaction = model.query.get_or_404(id)
    if type.endswith('sell'):
        income = Income.query.filter_by(source='stock' if is_stock else 'mutual_fund', sell_transaction_id=id).first()
        if income:
            db.session.delete(income)
    db.session.delete(transaction)
    db.session.commit()
    flash('Transaction deleted successfully!', 'success')
    return redirect(url_for('investment.transactions'))

@investment_bp.route('/prices')
def prices():
    return render_template('investment/prices.html')

@investment_bp.route('/prices/add', methods=['GET', 'POST'])
def add_price():
    if request.method == 'POST':
        try:
            investment_type = request.form['investment_type']
            identifier = request.form['ticker' if investment_type == 'stock' else 'fund_name']
            price = float(request.form['price'])
            date = datetime.strptime(request.form['date'], '%Y-%m-%d').date()
            model = StockPrice if investment_type == 'stock' else MutualFundNAV
            if investment_type == 'stock':
                price_entry = model(
                    ticker=identifier,
                    price=price,
                    date=date
                )
            else:
                price_entry = model(
                    fund_name=identifier,
                    nav=price,
                    date=date
                )
            db.session.add(price_entry)
            db.session.commit()
            flash('Price/NAV added successfully!', 'success')
            return redirect(url_for('investment.prices'))
        except ValueError:
            flash('Invalid input data.', 'danger')
            return render_template('investment/add_price.html')
    return render_template('investment/add_price.html')

@investment_bp.route('/prices/edit/<int:id>/<investment_type>', methods=['GET', 'POST'])
def edit_price(id, investment_type):
    model = StockPrice if investment_type == 'stock' else MutualFundNAV
    price = model.query.get_or_404(id)
    if request.method == 'POST':
        try:
            identifier = request.form['ticker' if investment_type == 'stock' else 'fund_name']
            price_value = float(request.form['price'])
            date = datetime.strptime(request.form['date'], '%Y-%m-%d').date()
            if investment_type == 'stock':
                price.ticker = identifier
                price.price = price_value
            else:
                price.fund_name = identifier
                price.nav = price_value
            price.date = date
            db.session.commit()
            flash('Price/NAV updated successfully!', 'success')
            return redirect(url_for('investment.prices'))
        except ValueError:
            flash('Invalid transaction data.', 'error')
            return render_template('investment/add_price.html', price=price, investment_type=investment_type)
    return render_template('investment/add_price.html', price=price, investment_type=investment_type)

@investment_bp.route('/prices/delete/<int:id>/<investment_type>', methods=['POST'])
def delete_price(id, investment_type):
    model = StockPrice  if investment_type == 'stock' else MutualFundNAV
    price = model.query.get_or_404(id)
    db.session.delete(price)
    db.session.commit()
    flash('Price/NAV deleted successfully!', 'success')
    return redirect(url_for('investment.prices'))

@investment_bp.route('/api/transactions_all')
def api_all_transactions():
    buy_stock = StockTransaction.query.all()
    sell_stock = StockSellTransaction.query.all()
    buy_fund = MutualFundTransaction.query.all()
    sell_fund = MutualFundSellTransaction.query.all()
    transactions = (
        [{'id': t.id, 'type': 'Stock Buy', 'identifier': t.ticker, 'quantity': t.quantity, 'price': t.purchase_price, 'total': t.quantity * t.purchase_price, 'date': t.date.strftime('%Y-%m-%d'), 'description': t.description} for t in buy_stock] +
        [{'id': t.id, 'type': 'Stock Sell', 'identifier': t.ticker, 'quantity': t.quantity, 'price': t.sell_price, 'total': t.quantity * t.sell_price, 'date': t.date.strftime('%Y-%m-%d'), 'description': t.description} for t in sell_stock] +
        [{'id': t.id, 'type': 'Fund Buy', 'identifier': t.fund_name, 'quantity': t.units, 'price': t.purchase_nav, 'total': t.units * t.purchase_nav, 'date': t.date.strftime('%Y-%m-%d'), 'description': t.description} for t in buy_fund] +
        [{'id': t.id, 'type': 'Fund Sell', 'identifier': t.fund_name, 'quantity': t.units, 'price': t.sell_nav, 'total': t.units * t.sell_nav, 'date': t.date.strftime('%Y-%m-%d'), 'description': t.description} for t in sell_fund]
    )
    return jsonify(transactions)

@investment_bp.route('/api/investment-summary')
def api_investment_summary():
    try:
        identifier = request.args.get('identifier')
        quantity_sold = float(request.args.get('quantity_sold', 0))
        is_stock = request.args.get('investment_type') == 'stock'

        total_investment = 0
        current_value = 0
        total_quantity = {'stocks': 0, 'funds': 0}
        sale_metrics = {}

        if identifier:
            # Handle specific identifier case
            buy_model = StockTransaction if is_stock else MutualFundTransaction
            sell_model = StockSellTransaction if is_stock else MutualFundSellTransaction
            price_model = StockPrice if is_stock else MutualFundNAV

            transactions = buy_model.query.filter_by(ticker=identifier if is_stock else None, fund_name=identifier if not is_stock else None).all()
            sell_transactions = sell_model.query.filter_by(ticker=identifier if is_stock else None, fund_name=identifier if not is_stock else None).all()

            total_quantity_specific = 0
            weighted_price = 0
            for t in transactions:
                qty = t.quantity if is_stock else t.units
                price = t.purchase_price if is_stock else t.purchase_nav
                total_quantity_specific += qty
                total_investment += qty * price
                weighted_price += qty * price

            for s in sell_transactions:
                qty = s.quantity if is_stock else s.units
                total_quantity_specific -= qty
                avg_price = weighted_price / total_quantity_specific if total_quantity_specific > 0 else 0
                total_investment -= qty * avg_price

            avg_price = weighted_price / total_quantity_specific if total_quantity_specific > 0 else 0
            latest_price = price_model.query.filter_by(**{'ticker': identifier} if is_stock else {'fund_name': identifier}).order_by(price_model.date.desc()).first()
            current_value = total_quantity_specific * (latest_price.price if is_stock and latest_price else latest_price.nav if not is_stock and latest_price else 0)

            if quantity_sold > 0:
                if total_quantity_specific < quantity_sold:
                    return jsonify({'error': f'Only {total_quantity_specific} {"shares" if is_stock else "units"} of {identifier} available'}), 400
                current_price = latest_price.price if is_stock and latest_price else latest_price.nav if not is_stock and latest_price else 0
                sell_value = quantity_sold * current_price
                if is_stock:
                    fees = calculate_fees(sell_value)
                    sell_value -= fees['total_fees']
                sale_return = sell_value - (quantity_sold * avg_price)
                sale_return_pct = (sale_return / (quantity_sold * avg_price) * 100) if quantity_sold * avg_price > 0 else 0
                sale_metrics = {
                    'sell_value': sell_value,
                    'sale_return': {'amount': sale_return, 'percentage': sale_return_pct}
                }

            total_quantity['stocks' if is_stock else 'funds'] = total_quantity_specific
        else:
            # Aggregate all stocks and mutual funds
            for is_stock in [True, False]:
                buy_model = StockTransaction if is_stock else MutualFundTransaction
                sell_model = StockSellTransaction if is_stock else MutualFundSellTransaction
                price_model = StockPrice if is_stock else MutualFundNAV

                transactions = buy_model.query.all()
                sell_transactions = sell_model.query.all()
                identifiers = list(set(t.ticker if is_stock else t.fund_name for t in transactions))

                for ident in identifiers:
                    ident_transactions = [t for t in transactions if (t.ticker if is_stock else t.fund_name) == ident]
                    ident_sell_transactions = [s for s in sell_transactions if (s.ticker if is_stock else s.fund_name) == ident]

                    qty = 0
                    weighted_price = 0
                    for t in ident_transactions:
                        q = t.quantity if is_stock else t.units
                        p = t.purchase_price if is_stock else t.purchase_nav
                        qty += q
                        total_investment += q * p
                        weighted_price += q * p

                    for s in ident_sell_transactions:
                        q = s.quantity if is_stock else s.units
                        qty -= q
                        avg_price = weighted_price / qty if qty > 0 else 0
                        total_investment -= q * avg_price

                    latest_price = price_model.query.filter_by(**{'ticker': ident} if is_stock else {'fund_name': ident}).order_by(price_model.date.desc()).first()
                    current_value += qty * (latest_price.price if is_stock and latest_price else latest_price.nav if not is_stock and latest_price else 0)

                    total_quantity['stocks' if is_stock else 'funds'] += qty

        return_amount = current_value - total_investment
        return_percentage = (return_amount / total_investment * 100) if total_investment > 0 else 0

        return jsonify({
            'total_investment': total_investment,
            'current_value': current_value,
            'return': {'amount': return_amount, 'percentage': return_percentage},
            'total_quantity': total_quantity,
            'sale_metrics': sale_metrics
        })
    except Exception as e:
        logger.error(f"Error in api_investment_summary: {str(e)}")
        return jsonify({'error': str(e)}), 500

@investment_bp.route('/api/latest-prices')
def api_latest_prices():
    try:
        stocks = StockPrice.query.group_by(StockPrice.ticker).having(db.func.max(StockPrice.date)).all()
        funds = MutualFundNAV.query.group_by(MutualFundNAV.fund_name).having(db.func.max(MutualFundNAV.date)).all()
        return jsonify({
            'stocks': [{'ticker': s.ticker, 'price': s.price, 'date': s.date.strftime('%Y-%m-%d')} for s in stocks],
            'funds': [{'fund_name': f.fund_name, 'nav': f.nav, 'date': f.date.strftime('%Y-%m-%d')} for f in funds]
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@investment_bp.route('/api/prices')
def api_prices():
    stock_prices = StockPrice.query.all()
    fund_navs = MutualFundNAV.query.all()
    prices = (
        [{'id': p.id, 'type': 'stock', 'identifier': p.ticker, 'price': p.price, 'date': p.date.strftime('%Y-%m-%d')} for p in stock_prices] +
        [{'id': p.id, 'type': 'fund', 'identifier': p.fund_name, 'price': p.nav, 'date': p.date.strftime('%Y-%m-%d')} for p in fund_navs]
    )
    return jsonify(prices)

def get_total_quantity_by_identifier(identifier, is_stock, exclude_sell_id=None):
    buy_model = StockTransaction if is_stock else MutualFundTransaction
    sell_model = StockSellTransaction if is_stock else MutualFundSellTransaction
    transactions = buy_model.query.filter_by(ticker=identifier if is_stock else None, fund_name=identifier if not is_stock else None).all()
    sales = sell_model.query.filter((sell_model.ticker == identifier if is_stock else sell_model.fund_name == identifier) & (sell_model.id != exclude_sell_id if exclude_sell_id else True)).all()
    total_quantity = sum(t.quantity if is_stock else t.units for t in transactions)
    for s in sales:
        total_quantity -= s.quantity if is_stock else s.units
    return max(0, total_quantity)

def get_avg_purchase_price(identifier, is_stock):
    buy_model = StockTransaction if is_stock else MutualFundTransaction
    transactions = buy_model.query.filter_by(ticker=identifier if is_stock else None, fund_name=identifier if not is_stock else None).all()
    total_quantity = sum(t.quantity if is_stock else t.units for t in transactions)
    weighted_price = sum((t.quantity if is_stock else t.units) * (t.purchase_price if is_stock else t.purchase_nav) for t in transactions)
    return weighted_price / total_quantity if total_quantity > 0 else 0
