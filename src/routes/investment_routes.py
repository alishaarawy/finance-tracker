from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from datetime import datetime
from src.models import db, StockTransaction, StockSellTransaction, MutualFundTransaction, MutualFundSellTransaction, StockPrice, MutualFundNAV, Income
import logging

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

def calculate_fees(total_value, investment_type='stock'):
    """Calculate fees for stock or mutual fund transactions based on total value."""
    if total_value <= 0:
        return {
            'egx_fee': 0.0,
            'mcdr_fee': 0.0,
            'fra_fee': 0.0,
            'risk_insurance_fee': 0.0,
            'brokerage_order_fee': 0.0,
            'brokerage_custody_fee': 0.0,
            'total_fees': 0.0
        }
    if investment_type == 'fund':
        brokerage_custody_fee = total_value * BROKERAGE_CUSTODY_RATE
        total_fees = brokerage_custody_fee + BROKERAGE_ORDER_FEE
        return {
            'egx_fee': 0.0,
            'mcdr_fee': 0.0,
            'fra_fee': 0.0,
            'risk_insurance_fee': 0.0,
            'brokerage_order_fee': BROKERAGE_ORDER_FEE,
            'brokerage_custody_fee': round(brokerage_custody_fee, 2),
            'total_fees': round(total_fees, 2)
        }
    else:  # investment_type == 'stock'
        egx_fee = total_value * EGX_FEE_RATE
        mcdr_fee = total_value * MCDR_FEE_RATE
        fra_fee = max(total_value * FRA_FEE_RATE, 1.0)
        risk_insurance_fee = total_value * RISK_INSURANCE_RATE
        brokerage_custody_fee = total_value * BROKERAGE_CUSTODY_RATE
        total_fees = egx_fee + mcdr_fee + fra_fee + risk_insurance_fee + BROKERAGE_ORDER_FEE + brokerage_custody_fee
        return {
            'egx_fee': round(egx_fee, 2),
            'mcdr_fee': round(mcdr_fee, 2),
            'fra_fee': round(fra_fee, 2),
            'risk_insurance_fee': round(risk_insurance_fee, 2),
            'brokerage_order_fee': BROKERAGE_ORDER_FEE,
            'brokerage_custody_fee': round(brokerage_custody_fee, 2),
            'total_fees': round(total_fees, 2)
        }


def get_total_quantity_by_identifier(identifier, is_stock, exclude_sell_id=None):
    """Get total available quantity of a security by identifier."""
    buy_model = StockTransaction if is_stock else MutualFundTransaction
    sell_model = StockSellTransaction if is_stock else MutualFundSellTransaction
    
    total_bought = db.session.query(
        db.func.sum(buy_model.quantity if is_stock else buy_model.units)
    ).filter(
        buy_model.ticker == identifier if is_stock else buy_model.fund_name == identifier
    ).scalar() or 0.0
    
    query = db.session.query(
        db.func.sum(sell_model.quantity if is_stock else sell_model.units)
    ).filter(
        sell_model.ticker == identifier if is_stock else sell_model.fund_name == identifier
    )
    
    if exclude_sell_id:
        query = query.filter(sell_model.id != exclude_sell_id)
    
    total_sold = query.scalar() or 0.0
    
    return max(0, total_bought - total_sold)



@investment_bp.route('/')
def index():
    return render_template('investment/index.html')

@investment_bp.route('/transactions')
def transactions():
    return render_template('investment/transactions.html')



@investment_bp.route('/api/calculate-fees', methods=['POST'])
def calculate_fees_api():
    try:
        data = request.get_json()
        total_value = float(data.get('total_value', 0))
        fees = calculate_fees(total_value)
        return jsonify(fees)
    except ValueError:
        return jsonify({'error': 'Invalid total value'}), 400
    except Exception as e:
        logger.error(f"Error in calculate_fees_api: {str(e)}")
        return jsonify({'error': str(e)}), 500

@investment_bp.route('/transactions/delete/<int:id>/<type>', methods=['POST'])
def delete_transaction(id, type):
    try:
        is_stock = type.startswith('stock')
        model = (
            StockSellTransaction if is_stock and type.endswith('sell') else 
            StockTransaction if is_stock else 
            MutualFundSellTransaction if type.endswith('sell') else 
            MutualFundTransaction
        )
        transaction = model.query.get_or_404(id)
        if type.endswith('sell'):
            income = Income.query.filter_by(
                source='stock' if is_stock else 'fund', 
                sell_transaction_id=id
            ).first()
            if income:
                db.session.delete(income)
        db.session.delete(transaction)
        db.session.commit()
        flash('Transaction deleted successfully!', 'success')
        return redirect(url_for('investment.transactions'))
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error deleting transaction: {str(e)}")
        flash(f'Error deleting transaction: {str(e)}', 'danger')
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
            
            if price <= 0:
                flash('Price/NAV must be a positive number.', 'danger')
                return render_template('investment/add_price.html')
            
            model = StockPrice if investment_type == 'stock' else MutualFundNAV
            price_entry_data = {
                'date': date
            }
            if investment_type == 'stock':
                price_entry_data['ticker'] = identifier
                price_entry_data['price'] = price
            else:
                price_entry_data['fund_name'] = identifier
                price_entry_data['nav'] = price
            
            price_entry = model(**price_entry_data)
            db.session.add(price_entry)
            db.session.commit()
            flash('Price/NAV added successfully!', 'success')
            return redirect(url_for('investment.prices'))
        except ValueError as e:
            flash(f'Invalid input data: {str(e)}', 'danger')
            return render_template('investment/add_price.html')
        except Exception as e:
            logger.error(f"Error saving transaction: {str(e)}")
            flash(f'Error adding price: {str(e)}', 'danger')
            return render_template('investment/add_price.html')
    return render_template('investment/add_price.html')

@investment_bp.route('/prices/edit/<int:id>/<investment_type>', methods=['GET', 'POST'])
def edit_price(id, investment_type):
    model = StockPrice if investment_type == 'stock' else MutualFundNAV
    price = model.query.get_or_404(id)
    
    if request.method == 'POST':
        try:
            identifier = request.form.get('ticker' if investment_type == 'stock' else 'fund_name')
            price_value = float(request.form.get('price'))
            date = datetime.strptime(request.form.get('date'), '%Y-%m-%d').date()
            
            if price_value <= 0:
                flash('Price/NAV must be a positive number.', 'danger')
                return render_template('investment/add_price.html', price=price, investment_type=investment_type)
            
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
        except ValueError as e:
            flash(f'Invalid input data: {str(e)}', 'danger')
            return render_template('investment/add_price.html', price=price, investment_type=investment_type)
        except Exception as e:
            logger.error(f"Error saving transaction: {str(e)}")
            flash(f'Error editing price: {str(e)}', 'danger')
            return render_template('investment/add_price.html', price=price, investment_type=investment_type)
    
    return render_template('investment/add_price.html', price=price, investment_type=investment_type)

@investment_bp.route('/prices/delete/<int:id>/<investment_type>', methods=['POST'])
def delete_price(id, investment_type):
    try:
        model = StockPrice if investment_type == 'stock' else MutualFundNAV
        price = model.query.get_or_404(id)
        db.session.delete(price)
        db.session.commit()
        flash('Price/NAV deleted successfully!', 'success')
        return redirect(url_for('investment.prices'))
    except Exception as e:
        logger.error(f"Error deleting transaction: {str(e)}")
        flash(f'Error deleting price: {str(e)}', 'danger')
        return redirect(url_for('investment.prices'))

@investment_bp.route('/api/transactions/all')
def api_transactions_all():
    try:
        logger.debug("Fetching all transactions")
        limit = request.args.get('limit', type=int)  # Get limit from query params
        transactions = []

        # Stock Buy Transactions
        for t in StockTransaction.query.all():
            total_value = t.quantity * t.purchase_price
            fees = calculate_fees(total_value, 'stock')
            transactions.append({
                'id': t.id,
                'type': 'Stock Buy',
                'identifier': t.ticker,
                'quantity': t.quantity,
                'price': t.purchase_price,
                'total': round(total_value, 2),
                'date': t.date.strftime('%Y-%m-%d'),
                'description': t.description or '',
                'fees': fees,
                'return_amount': None,
                'return_percentage': None,
                'matched_buys': None
            })

        # Stock Sell Transactions
        # Track remaining buy quantities globally
        buy_remaining = {}  # ticker: {buy_id: remaining_qty}
        buys_all = StockTransaction.query.order_by(StockTransaction.date.asc()).all()
        for t in buys_all:
            if t.ticker not in buy_remaining:
                buy_remaining[t.ticker] = {}
            buy_remaining[t.ticker][t.id] = t.quantity

        # Process sells in date order
        stock_sells = StockSellTransaction.query.order_by(StockSellTransaction.date.asc()).all()
        for t in stock_sells:
            total_value = t.quantity * t.sell_price
            fees = calculate_fees(total_value, 'stock')
            # Match buys using FIFO
            sold_qty = t.quantity
            matched_buys = []
            total_cost = 0.0
            buys = [b for b in buys_all if b.ticker == t.ticker]
            for buy in buys:
                if sold_qty <= 0:
                    break
                if buy.id not in buy_remaining[t.ticker] or buy_remaining[t.ticker][buy.id] <= 0:
                    continue
                qty_to_use = min(sold_qty, buy_remaining[t.ticker][buy.id])
                if qty_to_use > 0:
                    cost = qty_to_use * buy.purchase_price
                    total_cost += cost
                    matched_buys.append({
                        'buy_id': buy.id,
                        'date': buy.date.strftime('%Y-%m-%d'),
                        'quantity': qty_to_use,
                        'purchase_price': buy.purchase_price,
                        'cost': round(cost, 2)
                    })
                    buy_remaining[t.ticker][buy.id] -= qty_to_use
                    logger.debug(f"Sell id={t.id}: Matched buy id={buy.id}, date={buy.date}, qty={qty_to_use}, price={buy.purchase_price}, cost={cost}, remaining={buy_remaining[t.ticker][buy.id]}")
                    sold_qty -= qty_to_use
            sell_value = total_value - fees['total_fees']
            return_amount = round(sell_value - total_cost, 2)
            return_percentage = (
                round((return_amount / total_cost) * 100, 2)
                if total_cost > 0 else 0.0
            )
            logger.debug(f"Sell id={t.id}: sell_value={sell_value}, total_cost={total_cost}, return_amount={return_amount}, return_percentage={return_percentage}")
            transactions.append({
                'id': t.id,
                'type': 'Stock Sell',
                'identifier': t.ticker,
                'quantity': t.quantity,
                'price': t.sell_price,
                'total': round(total_value, 2),
                'date': t.date.strftime('%Y-%m-%d'),
                'description': t.description or '',
                'fees': fees,
                'return_amount': return_amount,
                'return_percentage': return_percentage,
                'matched_buys': matched_buys
            })

        # Fund Buy Transactions
        for t in MutualFundTransaction.query.all():
            total_value = t.units * t.purchase_nav
            fees = calculate_fees(total_value, 'fund')
            transactions.append({
                'id': t.id,
                'type': 'Fund Buy',
                'identifier': t.fund_name,
                'quantity': t.units,
                'price': t.purchase_nav,
                'total': round(total_value, 2),
                'date': t.date.strftime('%Y-%m-%d'),
                'description': t.description or '',
                'fees': fees,
                'return_amount': None,
                'return_percentage': None,
                'matched_buys': None
            })

        # Fund Sell Transactions
        fund_buy_remaining = {}  # fund_name: {buy_id: remaining_units}
        fund_buys_all = MutualFundTransaction.query.order_by(MutualFundTransaction.date.asc()).all()
        for t in fund_buys_all:
            if t.fund_name not in fund_buy_remaining:
                fund_buy_remaining[t.fund_name] = {}
            fund_buy_remaining[t.fund_name][t.id] = t.units

        fund_sells = MutualFundSellTransaction.query.order_by(MutualFundSellTransaction.date.asc()).all()
        for t in fund_sells:
            total_value = t.units * t.sell_nav
            fees = calculate_fees(total_value, 'fund')
            sold_qty = t.units
            matched_buys = []
            total_cost = 0.0
            buys = [b for b in fund_buys_all if b.fund_name == t.fund_name]
            for buy in buys:
                if sold_qty <= 0:
                    break
                if buy.id not in fund_buy_remaining[t.fund_name] or fund_buy_remaining[t.fund_name][buy.id] <= 0:
                    continue
                qty_to_use = min(sold_qty, fund_buy_remaining[t.fund_name][buy.id])
                if qty_to_use > 0:
                    cost = qty_to_use * buy.purchase_nav
                    buy_fees = calculate_fees(qty_to_use * buy.purchase_nav, 'fund')['total_fees']
                    effective_cost = cost + buy_fees
                    total_cost += effective_cost
                    matched_buys.append({
                        'buy_id': buy.id,
                        'date': buy.date.strftime('%Y-%m-%d'),
                        'quantity': qty_to_use,
                        'purchase_price': buy.purchase_nav,
                        'cost': round(effective_cost, 2)
                    })
                    fund_buy_remaining[t.fund_name][buy.id] -= qty_to_use
                    logger.debug(f"Sell id={t.id}: Matched buy id={buy.id}, date={buy.date}, qty={qty_to_use}, price={buy.purchase_nav}, cost={effective_cost}, remaining={fund_buy_remaining[t.fund_name][buy.id]}")
                    sold_qty -= qty_to_use
            sell_value = total_value - fees['total_fees']
            return_amount = round(sell_value - total_cost, 2)
            return_percentage = (
                round((return_amount / total_cost) * 100, 2)
                if total_cost > 0 else 0.0
            )
            logger.debug(f"Sell id={t.id}: sell_value={sell_value}, total_cost={total_cost}, return_amount={return_amount}, return_percentage={return_percentage}")
            transactions.append({
                'id': t.id,
                'type': 'Fund Sell',
                'identifier': t.fund_name,
                'quantity': t.units,
                'price': t.sell_nav,
                'total': round(total_value, 2),
                'date': t.date.strftime('%Y-%m-%d'),
                'description': t.description or '',
                'fees': fees,
                'return_amount': return_amount,
                'return_percentage': return_percentage,
                'matched_buys': matched_buys
            })
        # Sort transactions by date descending and apply limit
        transactions.sort(key=lambda x: x['date'], reverse=True)
        if limit:
            transactions = transactions[:limit]
        logger.debug(f"Fetched {len(transactions)} transactions")
        return jsonify(transactions)
    except Exception as e:
        logger.error(f"Error fetching all transactions: {str(e)}")
        return jsonify({'error': f'Internal server error: {str(e)}'}), 500

@investment_bp.route('/api/transactions/<int:id>/<type>')
def api_transaction_details(id, type):
    try:
        logger.debug(f"Fetching transaction details for id={id}, type={type}")
        valid_types = ['stock_buy', 'stock_sell', 'fund_buy', 'fund_sell']
        if type not in valid_types:
            logger.error(f"Invalid transaction type: {type}")
            return jsonify({'error': f'Invalid transaction type: {type}. Must be one of {valid_types}'}), 400

        is_stock = type.startswith('stock')
        model = (
            StockTransaction if type == 'stock_buy' else
            StockSellTransaction if type == 'stock_sell' else
            MutualFundTransaction if type == 'fund_buy' else
            MutualFundSellTransaction
        )
        transaction = model.query.get(id)
        if not transaction:
            logger.error(f"No transaction found for id={id}, type={type}")
            return jsonify({'error': f'No transaction found for id={id} with type={type}'}), 404

        is_buy = type.endswith('buy')
        total_value = (
            transaction.quantity * ((transaction.purchase_price if is_buy else transaction.sell_price))
            if is_stock else
            transaction.units * ((transaction.purchase_nav if is_buy else transaction.sell_nav))
        )
        fees = calculate_fees(total_value, 'stock' if is_stock else 'fund')

        details = {
            'id': transaction.id,
            'type': type.replace('_', ' ').title(),
            'identifier': transaction.ticker if is_stock else transaction.fund_name,
            'quantity': transaction.quantity if is_stock else transaction.units,
            'price': (
                transaction.purchase_price if is_stock and is_buy else
                transaction.sell_price if is_stock and not is_buy else
                transaction.purchase_nav if not is_stock and is_buy else
                transaction.sell_nav
            ),
            'total': round(total_value, 2),
            'date': transaction.date.strftime('%Y-%m-%d'),
            'description': transaction.description or '',
            'fees': fees
        }

        if not is_buy:
            avg_buy_price = get_avg_purchase_price(details['identifier'], is_stock)
            sell_value = total_value - fees['total_fees']
            details['return_amount'] = round(sell_value - (details['quantity'] * avg_buy_price), 2)
            details['return_percentage'] = (
                round((details['return_amount'] / (details['quantity'] * avg_buy_price) * 100), 2)
                if details['quantity'] * avg_buy_price > 0 else 0.0
            )
        else:
            details['return_amount'] = None
            details['return_percentage'] = None

        logger.debug(f"Transaction details fetched successfully: {details}")
        return jsonify(details)

    except AttributeError as e:
        logger.error(f"Attribute error in transaction details: id={id}, type={type}, error={str(e)}")
        return jsonify({'error': f'Invalid transaction data for id={id}, type={type}: {str(e)}'}), 500

    except Exception as e:
        logger.error(f"Error in transaction details: id={id}, type={type}, error={str(e)}")
        return jsonify({'error': f'Internal server error: {str(e)}'}), 500
    




def get_avg_purchase_price(identifier, is_stock, for_sold_quantity=False, sold_quantity=0):
    try:
        logger.debug(f"Calculating avg purchase price for {identifier}, is_stock={is_stock}, for_sold={for_sold_quantity}")
        buy_model = StockTransaction if is_stock else MutualFundTransaction
        sell_model = StockSellTransaction if is_stock else MutualFundSellTransaction
        qty_field = 'quantity' if is_stock else 'units'
        price_field = 'purchase_price' if is_stock else 'purchase_nav'

        buys = buy_model.query.filter_by(
            ticker=identifier if is_stock else None,
            fund_name=identifier if not is_stock else None
        ).order_by(buy_model.date).all()
        sells = sell_model.query.filter_by(
            ticker=identifier if is_stock else None,
            fund_name=identifier if not is_stock else None
        ).all()

        total_qty = 0
        total_cost = 0
        sold_qty = sum(getattr(s, qty_field) for s in sells) if not for_sold_quantity else sold_quantity

        for buy in buys:
            buy_qty = getattr(buy, qty_field)
            buy_price = getattr(buy, price_field)
            effective_price = buy_price if is_stock else (
                (buy_qty * buy_price + calculate_fees(buy_qty * buy_price, 'fund')['total_fees']) / buy_qty if buy_qty > 0 else buy_price
            )
            logger.debug(f"Buy transaction: id={buy.id}, qty={buy_qty}, price={buy_price}")

            if for_sold_quantity:
                qty_to_use = min(sold_qty, buy_qty)
                total_qty += qty_to_use
                total_cost += qty_to_use * effective_price
                sold_qty -= qty_to_use
                if sold_qty <= 0:
                    break
            else:
                remaining_qty = buy_qty - max(0, sold_qty)
                if remaining_qty > 0:
                    total_qty += remaining_qty
                    total_cost += remaining_qty * effective_price
                sold_qty = max(0, sold_qty - buy_qty)

        avg_price = total_cost / total_qty if total_qty > 0 else 0.0
        logger.debug(f"Avg purchase price for {identifier}: {avg_price}")
        return avg_price
    except Exception as e:
        logger.error(f"Error calculating avg purchase price for {identifier}: {str(e)}")
        return 0.0

@investment_bp.route('/api/holdings')
def api_holdings():
    try:
        identifier = request.args.get('identifier')
        investment_type = request.args.get('type')
        logger.debug(f"Fetching holdings: identifier={identifier}, type={investment_type}")
        holdings = []

        is_stock_values = [True] if investment_type == 'stock' else [False] if investment_type == 'fund' else [True, False]

        for is_stock in is_stock_values:
            buy_model = StockTransaction if is_stock else MutualFundTransaction
            sell_model = StockSellTransaction if is_stock else MutualFundSellTransaction
            price_model = StockPrice if is_stock else MutualFundNAV

            if identifier:
                transactions = (
                    buy_model.query.filter_by(ticker=identifier).order_by(buy_model.date.asc()).all()
                    if is_stock else
                    buy_model.query.filter_by(fund_name=identifier).order_by(buy_model.date.asc()).all()
                )
                sell_transactions = (
                    sell_model.query.filter_by(ticker=identifier).all()
                    if is_stock else
                    sell_model.query.filter_by(fund_name=identifier).all()
                )
                identifiers = {identifier}
            else:
                transactions = buy_model.query.order_by(buy_model.date.asc()).all()
                sell_transactions = sell_model.query.all()
                identifiers = set(t.ticker if is_stock else t.fund_name for t in transactions)

            for ident in identifiers:
                ident_transactions = [t for t in transactions if (is_stock and t.ticker == ident) or (not is_stock and t.fund_name == ident)]
                ident_sell_transactions = [s for s in sell_transactions if (is_stock and s.ticker == ident) or (not is_stock and s.fund_name == ident)]

                total_sold_quantity = sum(s.quantity if is_stock else s.units for s in ident_sell_transactions)
                total_buy_quantity = sum(t.quantity if is_stock else t.units for t in ident_transactions)
                logger.debug(f"{ident}: total_sold_quantity={total_sold_quantity}, total_buy_quantity={total_buy_quantity}")

                remaining_quantity = total_buy_quantity - total_sold_quantity
                if remaining_quantity <= 0:
                    logger.debug(f"{ident}: remaining_quantity={remaining_quantity}, skipping")
                    continue

                # FIFO: Calculate avg_price for remaining shares
                weighted_price = 0.0
                total_fees = 0.0
                qty_to_allocate = total_sold_quantity
                for t in ident_transactions:
                    qty = t.quantity if is_stock else t.units
                    price = t.purchase_price if is_stock else t.purchase_nav
                    logger.debug(f"{ident}: transaction id={t.id}, date={t.date}, qty={qty}, price={price}")
                    if qty_to_allocate >= qty:
                        qty_to_allocate -= qty
                        continue
                    else:
                        remaining_qty = qty - qty_to_allocate
                        if remaining_qty > 0:
                            weighted_price += remaining_qty * price
                            if not is_stock:
                                fees = calculate_fees(remaining_qty * price, 'fund')
                                total_fees += fees['total_fees']
                        qty_to_allocate = 0

                avg_price = (weighted_price + total_fees) / remaining_quantity if remaining_quantity > 0 else 0.0
                logger.debug(f"{ident}: avg_price={avg_price}, remaining_quantity={remaining_quantity}")

                latest_price = (
                    price_model.query.filter_by(ticker=ident).order_by(price_model.date.desc()).first()
                    if is_stock else
                    price_model.query.filter_by(fund_name=ident).order_by(price_model.date.desc()).first()
                )
                current_price = (
                    latest_price.price if latest_price and is_stock else
                    latest_price.nav if latest_price and not is_stock else
                    0.0
                )
                current_value = remaining_quantity * current_price
                if is_stock:
                    fees = calculate_fees(current_value, 'stock')
                    current_value -= fees['total_fees']
                return_amount = current_value - (remaining_quantity * avg_price)
                return_percentage = (
                    (return_amount / (remaining_quantity * avg_price)) * 100
                    if remaining_quantity * avg_price > 0 else 0.0
                )

                holdings.append({
                    'type': 'stock' if is_stock else 'fund',
                    'identifier': ident,
                    'total_quantity': round(remaining_quantity, 2),
                    'avg_price': round(avg_price, 2),
                    'current_price': round(current_price, 2),
                    'current_value': round(current_value, 2),
                    'return_amount': round(return_amount, 2),
                    'return_percentage': round(return_percentage, 2)
                })

        logger.debug(f"Fetched {len(holdings)} holdings")
        return jsonify(holdings)
    except Exception as e:
        logger.error(f"Error in holdings: {str(e)}")
        return jsonify({'error': str(e)}), 500




@investment_bp.route('/api/past-investments')
def api_past_investments():
    try:
        past_investments = []
        
        for is_stock in [True, False]:
            buy_model = StockTransaction if is_stock else MutualFundTransaction
            sell_model = StockSellTransaction if is_stock else MutualFundSellTransaction
            
            transactions = buy_model.query.order_by(buy_model.date.asc()).all()
            sell_transactions = sell_model.query.all()

            identifiers = set(s.ticker if is_stock else s.fund_name for s in sell_transactions)

            for ident in identifiers:
                ident_transactions = [t for t in transactions if (is_stock and t.ticker == ident) or (not is_stock and t.fund_name == ident)]
                ident_sell_transactions = [s for s in sell_transactions if (is_stock and s.ticker == ident) or (not is_stock and s.fund_name == ident)]
                
                total_sold_quantity = sum(s.quantity if is_stock else s.units for s in ident_sell_transactions)
                if total_sold_quantity == 0:
                    continue
                
                # FIFO: Calculate sold portion
                sold_quantity = 0.0
                purchase_value = 0.0
                sell_value = 0.0
                total_buy_fees = 0.0
                total_sell_fees = 0.0
                
                remaining_sold_quantity = total_sold_quantity
                for t in ident_transactions:
                    qty = t.quantity if is_stock else t.units
                    price = t.purchase_price if is_stock else t.purchase_nav
                    qty_to_sell = min(remaining_sold_quantity, qty)
                    if qty_to_sell > 0:
                        sold_quantity += qty_to_sell
                        purchase_value += qty_to_sell * price
                        if not is_stock:
                            fees = calculate_fees(qty_to_sell * price, 'fund')
                            total_buy_fees += fees['total_fees']
                        remaining_sold_quantity -= qty_to_sell
                        if remaining_sold_quantity <= 0:
                            break
                
                for s in ident_sell_transactions:
                    qty = s.quantity if is_stock else s.units
                    price = s.sell_price if is_stock else s.sell_nav
                    sell_value += qty * price
                    fees = calculate_fees(qty * price, 'stock' if is_stock else 'fund')
                    total_sell_fees += fees['total_fees']

                buy_cost = purchase_value + total_buy_fees
                return_amount = (sell_value - total_sell_fees) - buy_cost
                return_percentage = (
                    (return_amount / buy_cost) * 100 if buy_cost > 0 else 0.0
                )

                logger.debug(f"Past investment {ident}: sell_value={sell_value}, buy_cost={buy_cost}, return_amount={return_amount}, return_percentage={return_percentage}")

                past_investments.append({
                    'type': 'stock' if is_stock else 'fund',
                    'identifier': ident,
                    'purchase_value': round(buy_cost, 2),
                    'sell_value': round(sell_value - total_sell_fees, 2),
                    'return_amount': round(return_amount, 2),
                    'return_percentage': round(return_percentage, 2)
                })

        logger.debug(f"Fetched {len(past_investments)} past investments")
        return jsonify(past_investments)
    except Exception as e:
        logger.error(f"Error in past investments: {str(e)}")
        return jsonify({'error': str(e)}), 500

@investment_bp.route('/transactions/form/<type>', methods=['GET', 'POST'], defaults={'id': None}, endpoint='transaction_form')
@investment_bp.route('/transactions/form/<int:id>/<type>', methods=['GET', 'POST'], endpoint='transaction_form_with_id')
def transaction_form(id, type):
    try:
        is_buy = type.endswith('buy')
        transaction = None
        fees = None
        security_type = 'fund' if type.startswith('fund') else 'stock'
        
        if id:
            model = (
                StockTransaction if type == 'stock_buy' else
                StockSellTransaction if type == 'stock_sell' else
                MutualFundTransaction if type == 'fund_buy' else
                MutualFundSellTransaction
            )
            logger.debug(f"Fetching transaction: model={model.__name__}, id={id}")
            transaction = model.query.get(id)
            if not transaction:
                logger.warning(f"Transaction not found: model={model.__name__}, id={id}")
                flash('Transaction not found.', 'danger')
                return render_template('investment/transaction_form.html', 
                                      transaction=None, 
                                      is_stock=security_type == 'stock', 
                                      is_buy=is_buy, 
                                      security_type=security_type, 
                                      fees=None), 404
            security_type = 'stock' if hasattr(transaction, 'ticker') else 'fund'
            logger.debug(f"Transaction found: security_type={security_type}, type={type}")

        if request.method == 'POST':
            logger.debug(f"Form data: {request.form}")
            security_type = request.form.get('security_type')
            if security_type not in ['stock', 'fund']:
                logger.error(f"Invalid security type received: {security_type}")
                flash(f'Invalid security type: {security_type or "None"}.', 'danger')
                return render_template('investment/transaction_form.html', 
                                      transaction=transaction, 
                                      is_stock=security_type == 'stock', 
                                      is_buy=is_buy, 
                                      security_type=security_type, 
                                      fees=fees)
            
            is_stock = security_type == 'stock'
            identifier_key = 'ticker' if is_stock else 'fund_name'
            if identifier_key not in request.form or not request.form[identifier_key]:
                flash(f'{identifier_key.replace("_", " ").title()} is required.', 'danger')
                return render_template('investment/transaction_form.html', 
                                      transaction=transaction, 
                                      is_stock=is_stock, 
                                      is_buy=is_buy, 
                                      security_type=security_type, 
                                      fees=fees)
            
            identifier = request.form[identifier_key]
            quantity = float(request.form.get('quantity', 0))
            price = float(request.form.get('price', 0))
            date_str = request.form.get('date')
            description = request.form.get('description', '')

            if quantity <= 0 or price <= 0:
                flash('Quantity and price must be positive numbers.', 'danger')
                return render_template('investment/transaction_form.html', 
                                      transaction=transaction, 
                                      is_stock=is_stock, 
                                      is_buy=is_buy, 
                                      security_type=security_type, 
                                      fees=fees)
            
            if not date_str:
                flash('Date is required.', 'danger')
                return render_template('investment/transaction_form.html', 
                                      transaction=transaction, 
                                      is_stock=is_stock, 
                                      is_buy=is_buy, 
                                      security_type=security_type, 
                                      fees=fees)
            
            date = datetime.strptime(date_str, '%Y-%m-%d').date()

            model = (
                StockTransaction if is_stock and is_buy else
                StockSellTransaction if is_stock else
                MutualFundTransaction if not is_stock and is_buy else
                MutualFundSellTransaction
            )

            total_value = quantity * price
            fees = calculate_fees(total_value, 'stock' if is_stock else 'fund')
            
            if is_buy:
                total_cost = total_value + fees['total_fees']
                price = total_cost / quantity
            else:
                total_quantity = get_total_quantity_by_identifier(identifier, is_stock, exclude_sell_id=id)
                if quantity > total_quantity:
                    flash(f'Cannot sell {quantity} {"shares" if is_stock else "units"} of {identifier}; only {total_quantity} available', 'danger')
                    return render_template('investment/transaction_form.html', 
                                          transaction=transaction, 
                                          is_stock=is_stock, 
                                          is_buy=is_buy, 
                                          security_type=security_type, 
                                          fees=fees)

                # Calculate return_amount using FIFO
                sell_value = total_value - fees['total_fees']
                total_cost = 0.0
                sold_qty = quantity
                buys = StockTransaction.query.filter_by(ticker=identifier).order_by(StockTransaction.date.asc()).all() if is_stock else \
                       MutualFundTransaction.query.filter_by(fund_name=identifier).order_by(MutualFundTransaction.date.asc()).all()
                sells = StockSellTransaction.query.filter_by(ticker=identifier).all() if is_stock else \
                        MutualFundSellTransaction.query.filter_by(fund_name=identifier).all()
                
                # Include current sell in FIFO processing if updating
                current_sell = None
                if id and transaction:
                    current_sell = transaction
                    current_sell.quantity = quantity if is_stock else None
                    current_sell.units = quantity if not is_stock else None
                    current_sell.date = date
                    current_sell.sell_price = price if is_stock else None
                    current_sell.sell_nav = price if not is_stock else None
                    sells = [s for s in sells if s.id != id] + [current_sell]
                elif not id:
                    # New sell, append to sells
                    transaction_data = {
                        'date': date,
                        'description': description
                    }
                    if is_stock:
                        transaction_data['ticker'] = identifier
                        transaction_data['quantity'] = quantity
                        transaction_data['sell_price'] = price
                    else:
                        transaction_data['fund_name'] = identifier
                        transaction_data['units'] = quantity
                        transaction_data['sell_nav'] = price
                    logger.debug(f"Creating new sell: model={model.__name__}, data={transaction_data}")
                    current_sell = model(**transaction_data)
                    sells.append(current_sell)
                
                buy_remaining = {b.id: b.quantity if is_stock else b.units for b in buys}
                sells = sorted(sells, key=lambda x: x.date)
                logger.debug(f"Sell order for {identifier}: {[s.id if s.id else 'new' for s in sells]}")

                for s in sells:
                    s_qty = s.quantity if is_stock else s.units
                    if s == current_sell:
                        # Calculate cost for current sell
                        for b in sorted(buys, key=lambda x: x.date):
                            if sold_qty <= 0:
                                break
                            if buy_remaining[b.id] <= 0:
                                continue
                            qty_to_use = min(sold_qty, buy_remaining[b.id])
                            buy_price = b.purchase_price if is_stock else b.purchase_nav
                            effective_price = buy_price if is_stock else (
                                (qty_to_use * buy_price + calculate_fees(qty_to_use * buy_price, 'fund')['total_fees']) / qty_to_use if qty_to_use > 0 else buy_price
                            )
                            total_cost += qty_to_use * effective_price
                            buy_remaining[b.id] -= qty_to_use
                            sold_qty -= qty_to_use
                            logger.debug(f"Sell {identifier} {'id=' + str(s.id) if s.id else 'new'}: Matched buy id={b.id}, qty={qty_to_use}, price={buy_price}, cost={qty_to_use * effective_price}")
                        break  # Stop after processing current sell
                    else:
                        # Process prior sell
                        for b in sorted(buys, key=lambda x: x.date):
                            if s_qty <= 0:
                                break
                            if buy_remaining[b.id] <= 0:
                                continue
                            qty_to_use = min(s_qty, buy_remaining[b.id])
                            buy_remaining[b.id] -= qty_to_use
                            s_qty -= qty_to_use
                            logger.debug(f"Prior sell {s.id}: Matched buy id={b.id}, qty={qty_to_use}")

                return_amount = float(sell_value - total_cost)
                return_percentage = (return_amount / total_cost * 100) if total_cost > 0 else 0.0
                logger.debug(f"Sell {identifier} {'id=' + str(id) if id else 'new'}: sell_value={sell_value}, total_cost={total_cost}, return_amount={return_amount}, return_percentage={return_percentage}")

            with db.session.no_autoflush:
                if transaction:
                    # Update existing transaction
                    if is_stock:
                        transaction.ticker = identifier
                        transaction.quantity = quantity
                        if is_buy:
                            transaction.purchase_price = price
                        else:
                            transaction.sell_price = price
                    else:
                        transaction.fund_name = identifier
                        transaction.units = quantity
                        if is_buy:
                            transaction.purchase_nav = price
                        else:
                            transaction.sell_nav = price
                    transaction.date = date
                    transaction.description = description

                    if not is_buy:
                        income = Income.query.filter_by(
                            source='stock' if is_stock else 'fund', 
                            sell_transaction_id=id
                        ).first()
                        if income:
                            income.amount = return_amount
                            income.return_amount = return_amount
                            income.date = date
                            income.description = description or f"{'Stock' if is_stock else 'Mutual Fund'} sell: {quantity} {'shares' if is_stock else 'units'} {identifier} at EGP {price:.2f}"
                            income.updated_at = datetime.utcnow()
                        else:
                            income = Income(
                                amount=return_amount,
                                return_amount=return_amount,
                                date=date,
                                source='stock' if is_stock else 'fund',
                                description=description or f"{'Stock' if is_stock else 'Mutual Fund'} sell: {quantity} {'shares' if is_stock else 'units'} {identifier} at EGP {price:.2f}",
                                sell_transaction_id=id
                            )
                            db.session.add(income)
                else:
                    # Create new transaction
                    transaction_data = {
                        'date': date,
                        'description': description
                    }
                    if is_stock:
                        transaction_data['ticker'] = identifier
                        transaction_data['quantity'] = quantity
                        if is_buy:
                            transaction_data['purchase_price'] = price
                        else:
                            transaction_data['sell_price'] = price
                    else:
                        transaction_data['fund_name'] = identifier
                        transaction_data['units'] = quantity
                        if is_buy:
                            transaction_data['purchase_nav'] = price
                        else:
                            transaction_data['sell_nav'] = price
                    logger.debug(f"Creating new transaction: model={model.__name__}, data={transaction_data}")
                    transaction = model(**transaction_data)
                    db.session.add(transaction)
                    if not is_buy:
                        db.session.flush()
                        income = Income(
                            amount=return_amount,
                            return_amount=return_amount,
                            date=date,
                            source='stock' if is_stock else 'fund',
                            description=description or f"{'Stock' if is_stock else 'Mutual Fund'} sell: {quantity} {'shares' if is_stock else 'units'} {identifier} at EGP {price:.2f}",
                            sell_transaction_id=transaction.id
                        )
                        db.session.add(income)

            db.session.commit()
            flash(f"{'Stock' if is_stock else 'Mutual Fund'} transaction saved successfully", 'success')
            return redirect(url_for('investment.transactions'))
    except ValueError as e:
            db.session.rollback()
            flash(f'Invalid input data: {str(e)}', 'danger')
            return render_template('investment/transaction_form.html', 
                                  transaction=transaction, 
                                  is_stock=is_stock, 
                                  is_buy=is_buy, 
                                  security_type=security_type, 
                                  fees=fees)
    except Exception as e:
            db.session.rollback()
            logger.error(f"Error saving transaction: {str(e)}")
            flash(f'Error saving transaction: {str(e)}', 'danger')
            return render_template('investment/transaction_form.html', 
                                  transaction=transaction, 
                                  is_stock=is_stock, 
                                  is_buy=is_buy, 
                                  security_type=security_type, 
                                  fees=fees)

    return render_template('investment/transaction_form.html', 
                          transaction=transaction, 
                          is_stock=security_type == 'stock', 
                          is_buy=is_buy, 
                          security_type=security_type, 
                          fees=fees)


@investment_bp.route('/api/prices')
def api_prices():
    try:
        stock_prices = StockPrice.query.order_by(StockPrice.ticker).all()
        prices = [{
            'id': s.id,
            'type': 'stock',
            'name': s.ticker,
            'price': s.price,
            'date': s.date.strftime('%Y-%m-%d')
        } for s in stock_prices]
        
        return jsonify(prices)
    except Exception as e:
        logger.error(f'Error in prices: {e}')
        return jsonify({'error': str(e)}), 500

@investment_bp.route('/get_total_quantity_by_identifier')
def get_total_quantity_by_ident():
    try:
        id = request.args.get('id')
        is_stock = request.args.get('is_stock', '').lower() == 'true'
        exclude = request.args.get('exclude')
        
        buy_model = StockTransaction if is_stock else MutualFundTransaction
        transactions = (buy_model.query.filter_by(ticker=id).all() 
                      if is_stock 
                      else buy_model.query.filter_by(fund_name=id).all())
        
        sell_transactions = (StockSellTransaction.query.filter_by(ticker=id).all() 
                           if is_stock 
                           else MutualFundSellTransaction.query.filter_by(fund_name=id).all())
        
        if exclude:
            sell_transactions = [s for s in sell_transactions if s.transaction_id != exclude]
        
        total_quantity = sum(t.quantity for t in transactions)
        total_sold = sum(s.quantity for s in sell_transactions)
        
        logger.debug(f"Total quantity for {id} (stock={is_stock}): {total_quantity - total_sold}")
        return jsonify({'total_quantity': max(0, total_quantity - total_sold)})
    except Exception as e:
        logger.error(f"Error in total_quantity: {e}")
        return jsonify({'error': str(e)}), 500

@investment_bp.route('/api/purchase_price/<id>')
def api_purchase_price(id):
    try:
        is_stock = request.args.get('is_stock', '').lower() == 'true'
        buy_model = StockTransaction if is_stock else MutualFundTransaction
        
        transactions = (buy_model.query.filter_by(ticker=id).all() 
                      if is_stock 
                      else buy_model.query.filter_by(fund_name=id).all())
        
        total_quantity = sum(t.quantity for t in transactions)
        weighted_price = sum(t.quantity * (t.purchase_price if is_stock else t.purchase_nav) for t in transactions)
        total_fees = sum(calculate_fees(t.quantity * (t.purchase_price if is_stock else t.purchase_nav))['total_fees'] 
                    for t in transactions) 
        
        avg_price = (weighted_price + total_fees) / total_quantity if total_quantity > 0 else 0
        logger.debug(f"Average price for {id}: {avg_price}")
        return jsonify({'avg_price': round(avg_price, 2)})
    except Exception as e:
        logger.error(f"Error in price for {id}: {str(e)}")
        return jsonify({'error': str(e)}), 500
@investment_bp.route('/api/investment-summary')
def api_investment_summary():
    try:
        identifier = request.args.get('identifier')
        quantity_sold = float(request.args.get('quantity_sold', 0))
        investment_type = request.args.get('investment_type')
        is_stock = investment_type == 'stock' if investment_type else None

        logger.debug(f"Received request - identifier: {identifier}, quantity_sold: {quantity_sold}, is_stock: {is_stock}")

        total_investment = 0.0
        logger.debug(f"Initialized total_investment: {total_investment}")
        current_value = 0.0
        total_quantity = {'stocks': 0.0, 'funds': 0.0}
        sale_metrics = {}

        if identifier:
            logger.debug("Handling single investment summary")
            if is_stock is None:
                return jsonify({'error': 'investment_type is required when identifier is provided'}), 400

            buy_model = StockTransaction if is_stock else MutualFundTransaction
            sell_model = StockSellTransaction if is_stock else MutualFundSellTransaction
            price_model = StockPrice if is_stock else MutualFundNAV
            logger.debug(f"Models selected - buy_model: {buy_model.__name__}, sell_model: {sell_model.__name__}, price_model: {price_model.__name__}")

            # Fetch buy and sell transactions, sorted by date
            buy_transactions = (
                buy_model.query.filter_by(ticker=identifier).order_by(buy_model.date.asc()).all() if is_stock
                else buy_model.query.filter_by(fund_name=identifier).order_by(buy_model.date.asc()).all()
            )
            sell_transactions = (
                sell_model.query.filter_by(ticker=identifier).order_by(sell_model.date.asc()).all() if is_stock
                else sell_model.query.filter_by(fund_name=identifier).order_by(sell_model.date.asc()).all()
            )
            logger.debug(f"Found {len(buy_transactions)} buy transactions and {len(sell_transactions)} sell transactions for {identifier}")

            # Calculate remaining quantity and weighted purchase price
            remaining_quantity = 0.0
            weighted_purchase_price = 0.0
            buy_remaining = {t.id: t.quantity if is_stock else t.units for t in buy_transactions}

            # Process buys
            for t in buy_transactions:
                qty = t.quantity if is_stock else t.units
                remaining_quantity += qty
                logger.debug(f"Buy txn id={t.id}: qty={qty}, price={t.purchase_price if is_stock else t.purchase_nav}")

            # Process sells with FIFO matching
            for s in sell_transactions:
                qty = s.quantity if is_stock else s.units
                remaining_quantity -= qty
                logger.debug(f"Sell txn id={s.id}: qty={qty}, remaining_quantity={remaining_quantity}")
                temp_qty = qty
                for buy_id, buy_qty in list(buy_remaining.items()):
                    if temp_qty <= 0:
                        break
                    if buy_qty > 0:
                        matched_qty = min(temp_qty, buy_qty)
                        buy_remaining[buy_id] -= matched_qty
                        temp_qty -= matched_qty
                        logger.debug(f"Matched sell id={s.id} to buy id={buy_id}, matched_qty={matched_qty}, remaining_buy_qty={buy_remaining[buy_id]}")

            if remaining_quantity < 0:
                logger.warning(f"Negative quantity for {identifier}: {remaining_quantity}")
                return jsonify({'error': f'Negative quantity for {identifier}'}), 400

            # Calculate average purchase price for remaining shares
            for t in buy_transactions:
                qty = buy_remaining.get(t.id, 0.0)
                if qty > 0:
                    price = t.purchase_price if is_stock else t.purchase_nav
                    weighted_purchase_price += qty * price
                    logger.debug(f"Remaining buy id={t.id}: qty={qty}, price={price}, weighted_price={qty * price}")

            avg_purchase_price = weighted_purchase_price / remaining_quantity if remaining_quantity > 0 else 0.0
            total_investment = remaining_quantity * avg_purchase_price
            logger.debug(f"{identifier} - avg_purchase_price: {avg_purchase_price}, remaining_quantity: {remaining_quantity}, total_investment: {total_investment}")

            # Calculate current value
            latest_price = (
                price_model.query.filter_by(ticker=identifier).order_by(price_model.date.desc()).first() if is_stock
                else price_model.query.filter_by(fund_name=identifier).order_by(price_model.date.desc()).first()
            )
            current_price = (
                latest_price.price if is_stock and latest_price else
                latest_price.nav if not is_stock and latest_price else 0.0
            )
            current_value = remaining_quantity * current_price
            logger.debug(f"{identifier} - current_price: {current_price}, current_value: {current_value}")

            # Handle hypothetical sale
            if quantity_sold > 0:
                logger.debug(f"Processing hypothetical sale for {quantity_sold} units/shares")
                if remaining_quantity < quantity_sold:
                    error_msg = f"Only {remaining_quantity} {'shares' if is_stock else 'units'} of {identifier} available"
                    logger.warning(error_msg)
                    return jsonify({'error': error_msg}), 400

                sell_value = quantity_sold * current_price
                fees = calculate_fees(sell_value, 'stock' if is_stock else 'fund')
                sell_value_after_fees = sell_value - fees['total_fees']
                sale_return = sell_value_after_fees - (quantity_sold * avg_purchase_price)
                sale_return_pct = (sale_return / (quantity_sold * avg_purchase_price) * 100) if quantity_sold * avg_purchase_price > 0 else 0.0
                logger.debug(f"Hypothetical sale - sell_value: {sell_value}, fees: {fees['total_fees']}, sell_value_after_fees: {sell_value_after_fees}, sale_return: {sale_return}, sale_return_pct: {sale_return_pct}")

                sale_metrics = {
                    'buy_cost': round(quantity_sold * avg_purchase_price, 2),
                    'sell_value': round(sell_value_after_fees, 2),
                    'sale_return': {
                        'amount': round(sale_return, 2),
                        'percentage': round(sale_return_pct, 2)
                    }
                }

            total_quantity['stocks' if is_stock else 'funds'] = remaining_quantity
        else:
            logger.debug("Handling full portfolio summary")
            holdings_count = 0
            for is_stock in [True, False]:
                buy_model = StockTransaction if is_stock else MutualFundTransaction
                sell_model = StockSellTransaction if is_stock else MutualFundSellTransaction
                price_model = StockPrice if is_stock else MutualFundNAV

                buy_transactions = buy_model.query.all()
                sell_transactions = sell_model.query.all()
                identifiers = list(set(t.ticker if is_stock else t.fund_name for t in buy_transactions))
                logger.debug(f"{'Stock' if is_stock else 'Fund'} identifiers found: {identifiers}")

                for ident in identifiers:
                    ident_buy_transactions = [t for t in buy_transactions if (t.ticker if is_stock else t.fund_name) == ident]
                    ident_sell_transactions = [s for s in sell_transactions if (s.ticker if is_stock else s.fund_name) == ident]

                    # Sort buys by date for FIFO
                    ident_buy_transactions.sort(key=lambda x: x.date)
                    remaining_quantity = 0.0
                    weighted_purchase_price = 0.0
                    buy_remaining = {t.id: t.quantity if is_stock else t.units for t in ident_buy_transactions}

                    # Process buys
                    for t in ident_buy_transactions:
                        qty = t.quantity if is_stock else t.units
                        remaining_quantity += qty
                        logger.debug(f"Buy txn for {ident} id={t.id}: qty={qty}, price={t.purchase_price if is_stock else t.purchase_nav}")

                    # Process sells with FIFO matching
                    for s in ident_sell_transactions:
                        qty = s.quantity if is_stock else s.units
                        remaining_quantity -= qty
                        logger.debug(f"Sell txn for {ident} id={s.id}: qty={qty}, remaining_quantity={remaining_quantity}")
                        temp_qty = qty
                        for buy_id, buy_qty in list(buy_remaining.items()):
                            if temp_qty <= 0:
                                break
                            if buy_qty > 0:
                                matched_qty = min(temp_qty, buy_qty)
                                buy_remaining[buy_id] -= matched_qty
                                temp_qty -= matched_qty
                                logger.debug(f"Matched sell id={s.id} to buy id={buy_id}, matched_qty={matched_qty}, remaining_buy_qty={buy_remaining[buy_id]}")

                    if remaining_quantity < 0:
                        logger.warning(f"Negative quantity for {ident}: {remaining_quantity}")
                        continue

                    # Calculate average purchase price for remaining shares
                    for t in ident_buy_transactions:
                        qty = buy_remaining.get(t.id, 0.0)
                        if qty > 0:
                            price = t.purchase_price if is_stock else t.purchase_nav
                            weighted_purchase_price += qty * price
                            logger.debug(f"Remaining buy for {ident} id={t.id}: qty={qty}, price={price}, weighted_price={qty * price}")

                    if remaining_quantity > 0:
                        avg_purchase_price = weighted_purchase_price / remaining_quantity
                        total_investment += remaining_quantity * avg_purchase_price
                        logger.debug(f"{'Stock' if is_stock else 'Fund'} {ident} - avg_purchase_price: {avg_purchase_price}, remaining_quantity: {remaining_quantity}, investment: {remaining_quantity * avg_purchase_price}, total_investment: {total_investment}")

                        # Calculate current value
                        latest_price = (
                            price_model.query.filter_by(ticker=ident).order_by(price_model.date.desc()).first() if is_stock
                            else price_model.query.filter_by(fund_name=ident).order_by(price_model.date.desc()).first()
                        )
                        current_price = (
                            latest_price.price if is_stock and latest_price else
                            latest_price.nav if not is_stock and latest_price else 0.0
                        )
                        current_value += remaining_quantity * current_price
                        logger.debug(f"{'Stock' if is_stock else 'Fund'} {ident} - qty: {remaining_quantity}, current_price: {current_price}, current_value: {current_value}")
                        holdings_count += 1

            logger.debug(f"Fetched {holdings_count} holdings")

        return_amount = current_value - total_investment
        return_percentage = (return_amount / total_investment * 100) if total_investment > 0 else 0.0
        logger.debug(f"Return - amount: {return_amount}, percentage: {return_percentage}")

        result = {
            'total_investment': round(total_investment, 2),
            'current_value': round(current_value, 2),
            'return': {
                'amount': round(return_amount, 2),
                'percentage': round(return_percentage, 2)
            },
            'total_quantity': {
                'stocks': round(total_quantity['stocks'], 2),
                'funds': round(total_quantity['funds'], 2)
            },
            'sale_metrics': sale_metrics
        }

        logger.debug(f"Final result: {result}")
        return jsonify(result)

    except ValueError as e:
        logger.error(f"Value error in api_investment_summary: {str(e)}")
        return jsonify({'error': f'Invalid input data: {str(e)}'}), 400
    except ZeroDivisionError as e:
        logger.error(f"Zero division error in api_investment_summary: {str(e)}")
        return jsonify({'error': 'Cannot calculate metrics due to zero quantity or investment'}), 400
    except Exception as e:
        logger.error(f"Unexpected error in api_investment_summary: {str(e)}")
        return jsonify({'error': f'Internal server error: {str(e)}'}), 500
