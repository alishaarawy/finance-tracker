from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from datetime import datetime, timedelta
from src.models import db, GoldTransaction, GoldSellTransaction, GoldPrice, Income
import csv
from io import StringIO
import logging

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

gold_bp = Blueprint('gold', __name__, url_prefix='/gold', template_folder='templates/gold')

@gold_bp.route('/')
def index():
    return render_template('gold/index.html')

@gold_bp.route('/transactions')
def transactions():
    return render_template('gold/transactions.html')

@gold_bp.route('/transactions/form/<type>', methods=['GET', 'POST'], defaults={'id': None})
@gold_bp.route('/transactions/form/<int:id>/<type>', methods=['GET', 'POST'])
def transaction_form(id, type):
    is_buy = type == 'buy'
    transaction = GoldTransaction.query.get(id) if id and is_buy else GoldSellTransaction.query.get(id) if id else None

    if request.method == 'POST':
        try:
            weight = float(request.form['weight'])
            karat = int(request.form['karat'])
            price = float(request.form['price'])
            date = datetime.strptime(request.form['date'], '%Y-%m-%d').date()
            description = request.form.get('description', '')

            if is_buy:
                if transaction:
                    transaction.weight = weight
                    transaction.karat = karat
                    transaction.purchase_price = price
                    transaction.date = date
                    transaction.description = description
                else:
                    transaction = GoldTransaction(
                        weight=weight,
                        karat=karat,
                        purchase_price=price,
                        date=date,
                        description=description
                    )
                    db.session.add(transaction)
            else:  # Sell transaction
                try:
                    total_weight = get_total_weight_by_karat(exclude_sell_id=id)
                    if total_weight.get(str(karat), 0) < weight:
                        logger.warning(f"Insufficient weight: {weight}g of {karat}K requested, {total_weight.get(str(karat), 0)}g available")
                        flash(f'Cannot sell {weight}g of {karat}K; only {total_weight.get(str(karat), 0)}g available', 'danger')
                        return render_template('gold/transaction_form.html', transaction=transaction, is_buy=False)
                    
                    avg_buy_price = get_avg_purchase_price(karat)
                    sell_value = weight * price
                    return_amount = float(sell_value - (weight * avg_buy_price))
                    logger.debug(f"Sell transaction: sell_value={sell_value}, return_amount={return_amount}")
                    
                    if transaction:  # Update existing
                        logger.debug(f"Updating existing sell transaction: id={transaction.id}")
                        transaction.weight = weight
                        transaction.karat = karat
                        transaction.sell_price = price
                        transaction.date = date
                        transaction.description = description
                        
                        income = Income.query.filter_by(source='gold', sell_transaction_id=transaction.id).first()
                        if income:
                            logger.debug(f"Updating Income record: id={income.id}")
                            income.amount = float(sell_value)
                            income.return_amount = float(return_amount)
                            income.date = date
                            income.description = description
                            income.updated_at = datetime.utcnow()
                        else:
                            logger.debug("No Income record found, creating new")
                            income = Income(
                                amount=float(sell_value),
                                return_amount=float(return_amount),
                                date=date,
                                source='gold',
                                description=description or f"Gold sell: {weight}g {karat}K at EGP {price}/g",
                                sell_transaction_id=transaction.id
                            )
                            db.session.add(income)
                    else:  # New sell transaction
                        logger.debug("Creating new sell transaction")
                        transaction = GoldSellTransaction(
                            weight=weight,
                            karat=karat,
                            sell_price=price,
                            date=date,
                            description=description
                        )
                        db.session.add(transaction)
                        db.session.flush()
                        logger.debug(f"New transaction ID: {transaction.id}")
                        
                        income = Income(
                            amount=float(return_amount),
                            return_amount=float(return_amount),
                            date=date,
                            source='gold',
                            description=description or f"Gold sell: {weight}g {karat}K at EGP {price}/g",
                            sell_transaction_id=transaction.id
                        )
                        db.session.add(income)
                        logger.debug(f"Created Income: amount=float(return_amount), return_amount={return_amount}, sell_transaction_id={transaction.id}")
                    
                    db.session.commit()
                    logger.debug("Transaction committed successfully")
                    flash('Sell transaction saved successfully', 'success')
                
                except Exception as e:
                    logger.error(f"Error processing sell transaction: {str(e)}")
                    db.session.rollback()
                    flash(f'Error saving sell transaction: {str(e)}', 'danger')
                    return render_template('gold/transaction_form.html', transaction=transaction, is_buy=False)
        
            db.session.commit()
            flash('Transaction saved successfully', 'success')
            return redirect(url_for('gold.transactions'))
        except Exception as e:
            logger.error(f"Error processing transaction: {str(e)}")
            db.session.rollback()
            flash(f'Error saving transaction: {str(e)}', 'danger')
            return render_template('gold/transaction_form.html', transaction=transaction, is_buy=is_buy)

    return render_template('gold/transaction_form.html', transaction=transaction, is_buy=is_buy)

@gold_bp.route('/transactions/all')
def all_transactions():
    return render_template('gold/all_transactions.html')

@gold_bp.route('/transactions/details/<int:id>/<type>', methods=['GET'])
def transaction_details(id, type):
    is_buy = type == 'buy'
    transaction = GoldTransaction.query.get_or_404(id) if is_buy else GoldSellTransaction.query.get_or_404(id)
    return_amount = None
    return_percentage = None
    if not is_buy:
        avg_buy_price = get_avg_purchase_price(transaction.karat)
        return_amount = transaction.weight * (transaction.sell_price - avg_buy_price)
        return_percentage = (return_amount / (transaction.weight * avg_buy_price) * 100) if transaction.weight * avg_buy_price > 0 else 0
    return render_template('gold/transaction_details.html', transaction=transaction, is_buy=is_buy, return_amount=return_amount, return_percentage=return_percentage)

@gold_bp.route('/transactions/delete/<int:id>/<type>', methods=['POST'])
def delete_transaction(id, type):
    if type == 'buy':
        transaction = GoldTransaction.query.get_or_404(id)
    else:
        transaction = GoldSellTransaction.query.get_or_404(id)
        income = Income.query.filter_by(source='gold', sell_transaction_id=id).first()
        if income:
            db.session.delete(income)

    db.session.delete(transaction)
    db.session.commit()
    flash('Transaction deleted successfully!', 'success')
    return redirect(url_for('gold.transactions'))

@gold_bp.route('/prices')
def prices():
    return render_template('gold/prices.html')

@gold_bp.route('/prices/add', methods=['GET', 'POST'])
def add_price():
    if request.method == 'POST':
        try:
            price_type = request.form['price_type']
            price_24k = float(request.form['price_24k'])
            date = datetime.strptime(request.form['date'], '%Y-%m-%d').date()

            # Default values for optional fields
            price_21k = (21/24) * price_24k
            price_18k = (18/24) * price_24k
            price_pound = price_21k * 8 if price_type == 'local' else None

            # Handle optional fields for local prices
            if price_type == 'local':
                price_21k = float(request.form.get('price_21k', price_21k)) if request.form.get('price_21k') else price_21k
                price_18k = float(request.form.get('price_18k', price_18k)) if request.form.get('price_18k') else price_18k
                price_pound = float(request.form.get('price_pound', price_pound)) if request.form.get('price_pound') else price_pound

            price = GoldPrice(
                price_type=price_type,
                price_24k=price_24k,
                price_21k=price_21k,
                price_18k=price_18k,
                price_pound=price_pound,
                date=date
            )
            db.session.add(price)
            db.session.commit()
            flash('Price added successfully!', 'success')
            return redirect(url_for('gold.prices'))
        except ValueError as e:
            logger.error(f"Invalid input data: {str(e)}")
            flash(f'Invalid input data: {str(e)}', 'danger')
            return render_template('gold/add_price.html')
        except Exception as e:
            logger.error(f"Error adding price: {str(e)}")
            db.session.rollback()
            flash(f'Error adding price: {str(e)}', 'danger')
            return render_template('gold/add_price.html')
    return render_template('gold/add_price.html')

@gold_bp.route('/prices/edit/<int:id>', methods=['GET', 'POST'])
def edit_price(id):
    price = GoldPrice.query.get_or_404(id)
    if request.method == 'POST':
        try:
            price.price_type = request.form['price_type']
            price.price_24k = float(request.form['price_24k'])
            price.date = datetime.strptime(request.form['date'], '%Y-%m-%d').date()

            # Default values for optional fields
            price.price_21k = (21/24) * price.price_24k
            price.price_18k = (18/24) * price.price_24k
            price.price_pound = price.price_21k * 8 if price.price_type == 'local' else None

            # Handle optional fields for local prices
            if price.price_type == 'local':
                price.price_21k = float(request.form.get('price_21k', price.price_21k)) if request.form.get('price_21k') else price.price_21k
                price.price_18k = float(request.form.get('price_18k', price.price_18k)) if request.form.get('price_18k') else price.price_18k
                price.price_pound = float(request.form.get('price_pound', price.price_pound)) if request.form.get('price_pound') else price.price_pound

            db.session.commit()
            flash('Price updated successfully!', 'success')
            return redirect(url_for('gold.prices'))
        except ValueError as e:
            logger.error(f"Invalid input data: {str(e)}")
            flash(f'Invalid input data: {str(e)}', 'danger')
            return render_template('gold/add_price.html', price=price)
        except Exception as e:
            logger.error(f"Error updating price: {str(e)}")
            db.session.rollback()
            flash(f'Error updating price: {str(e)}', 'danger')
            return render_template('gold/add_price.html', price=price)
    return render_template('gold/add_price.html', price=price)

@gold_bp.route('/prices/delete/<int:id>', methods=['POST'])
def delete_price(id):
    price = GoldPrice.query.get_or_404(id)
    db.session.delete(price)
    db.session.commit()
    flash('Price deleted successfully!', 'success')
    return redirect(url_for('gold.prices'))

@gold_bp.route('/prices/import', methods=['GET', 'POST'])
def import_prices():
    if request.method == 'POST':
        try:
            price_type = request.form['price_type']
            csv_file = request.files['csv_file']
            
            if not csv_file or not csv_file.filename.endswith('.csv'):
                flash('Please upload a valid CSV file.', 'danger')
                return render_template('gold/import_prices.html')

            stream = StringIO(csv_file.stream.read().decode('UTF-8'))
            csv_reader = csv.DictReader(stream)
            
            expected_headers = ['date', 'price_24k']
            if price_type == 'local':
                expected_headers.extend(['price_21k', 'price_18k', 'price_pound'])
            
            if not all(header in csv_reader.fieldnames for header in expected_headers):
                flash('Invalid CSV format. Expected headers: ' + ', '.join(expected_headers), 'danger')
                return render_template('gold/import_prices.html')

            imported_count = 0
            for row in csv_reader:
                try:
                    date = datetime.strptime(row['date'], '%Y-%m-%d').date()
                    price_24k = float(row['price_24k'])
                    
                    price_21k = (21/24) * price_24k
                    price_18k = (18/24) * price_24k
                    price_pound = price_21k * 8 if price_type == 'local' else None
                    
                    if price_type == 'local':
                        price_21k = float(row.get('price_21k', price_21k)) if row.get('price_21k') else price_21k
                        price_18k = float(row.get('price_18k', price_18k)) if row.get('price_18k') else price_18k
                        price_pound = float(row.get('price_pound', price_pound)) if row.get('price_pound') else price_pound
                    
                    price = GoldPrice(
                        price_type=price_type,
                        price_24k=price_24k,
                        price_21k=price_21k,
                        price_18k=price_18k,
                        price_pound=price_pound,
                        date=date
                    )
                    db.session.add(price)
                    imported_count += 1
                except ValueError:
                    continue
            
            db.session.commit()
            flash(f'Successfully imported {imported_count} price records.', 'success')
            return redirect(url_for('gold.prices'))
        except Exception as e:
            logger.error(f"Error importing prices: {str(e)}")
            flash(f'Error: {str(e)}', 'danger')
            return render_template('gold/import_prices.html')
    return render_template('gold/import_prices.html')

@gold_bp.route('/api/transactions')
def api_transactions():
    query = GoldTransaction.query
    if 'start_date' in request.args:
        try:
            start_date = datetime.strptime(request.args.get('start_date'), '%Y-%m-%d').date()
            query = query.filter(GoldTransaction.date >= start_date)
        except ValueError:
            return jsonify({'error': 'Invalid start_date format'}), 400

    if 'end_date' in request.args:
        try:
            end_date = datetime.strptime(request.args.get('end_date'), '%Y-%m-%d').date()
            query = query.filter(GoldTransaction.date <= end_date)
        except ValueError:
            return jsonify({'error': 'Invalid end_date format'}), 400

    limit = int(request.args.get('limit', 0))
    transactions = query.order_by(GoldTransaction.date.desc()).limit(limit).all()
    return jsonify([
        {
            'id': t.id,
            'type': 'Buy',
            'weight': t.weight,
            'karat': t.karat,
            'price': t.purchase_price,
            'total': t.weight * t.purchase_price,
            'date': t.date.strftime('%Y-%m-%d'),
            'description': t.description
        } for t in transactions
    ])

@gold_bp.route('/api/sell_transactions')
def api_sell_transactions():
    query = GoldSellTransaction.query
    if 'start_date' in request.args:
        try:
            start_date = datetime.strptime(request.args.get('start_date'), '%Y-%m-%d').date()
            query = query.filter(GoldSellTransaction.date >= start_date)
        except ValueError:
            return jsonify({'error': 'Invalid start_date format'}), 400

    if 'end_date' in request.args:
        try:
            end_date = datetime.strptime(request.args.get('end_date'), '%Y-%m-%d').date()
            query = query.filter(GoldSellTransaction.date <= end_date)
        except ValueError:
            return jsonify({'error': 'Invalid end_date format'}), 400

    limit = int(request.args.get('limit', 0))
    transactions = query.order_by(GoldSellTransaction.date.desc()).limit(limit).all()
    return jsonify([
        {
            'id': t.id,
            'type': 'Sell',
            'weight': t.weight,
            'karat': t.karat,
            'price': t.sell_price,
            'total': t.weight * t.sell_price,
            'return': t.weight * (t.sell_price - get_avg_purchase_price(t.karat)),
            'date': t.date.strftime('%Y-%m-%d'),
            'description': t.description
        } for t in transactions
    ])

@gold_bp.route('/api/transactions_all')
def api_all_transactions():
    buy_query = GoldTransaction.query
    sell_query = GoldSellTransaction.query
    if 'start_date' in request.args:
        try:
            start_date = datetime.strptime(request.args.get('start_date'), '%Y-%m-%d').date()
            buy_query = buy_query.filter(GoldTransaction.date >= start_date)
            sell_query = sell_query.filter(GoldSellTransaction.date >= start_date)
        except ValueError:
            return jsonify({'error': 'Invalid start_date format'}), 400

    if 'end_date' in request.args:
        try:
            end_date = datetime.strptime(request.args.get('end_date'), '%Y-%m-%d').date()
            buy_query = buy_query.filter(GoldTransaction.date <= end_date)
            sell_query = sell_query.filter(GoldSellTransaction.date <= end_date)
        except ValueError:
            return jsonify({'error': 'Invalid end_date format'}), 400

    buy_transactions = buy_query.order_by(GoldTransaction.date.desc()).all()
    sell_transactions = sell_query.order_by(GoldSellTransaction.date.desc()).all()
    transactions = [
        {
            'id': t.id,
            'type': 'Buy',
            'weight': t.weight,
            'karat': t.karat,
            'price': t.purchase_price,
            'total': t.weight * t.purchase_price,
            'date': t.date.strftime('%Y-%m-%d'),
            'description': t.description
        } for t in buy_transactions
    ] + [
        {
            'id': t.id,
            'type': 'Sell',
            'weight': t.weight,
            'karat': t.karat,
            'price': t.sell_price,
            'total': t.weight * t.sell_price,
            'return': t.weight * (t.sell_price - get_avg_purchase_price(t.karat)),
            'date': t.date.strftime('%Y-%m-%d'),
            'description': t.description
        } for t in sell_transactions
    ]
    return jsonify(transactions)

@gold_bp.route('/api/holdings')
def api_holdings():
    try:
        total_weight = get_total_weight_by_karat()
        latest_price = GoldPrice.query.filter_by(price_type='local').order_by(GoldPrice.date.desc()).first()
        holdings = []
        for karat in ['24', '21', '18']:
            weight = total_weight[karat]
            if weight > 0:
                avg_price = get_avg_purchase_price(int(karat))
                current_price = (
                    latest_price.price_24k if karat == '24' else
                    latest_price.price_21k if karat == '21' else
                    latest_price.price_18k
                ) if latest_price else 0
                return_amount = weight * (current_price - avg_price)
                return_percentage = (return_amount / (weight * avg_price) * 100) if weight * avg_price > 0 else 0
                holdings.append({
                    'karat': int(karat),
                    'weight': weight,
                    'avg_purchase_price': avg_price,
                    'current_price': current_price,
                    'current_value': weight * current_price,
                    'return': return_amount,
                    'return_percentage': return_percentage
                })
        return jsonify(holdings)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@gold_bp.route('/api/investment-summary')
def api_investment_summary():
    try:
        grams_sold = float(request.args.get('grams_sold', 0))
        karat_sold = int(request.args.get('karat_sold', 0))

        transactions = GoldTransaction.query.all()
        sell_transactions = GoldSellTransaction.query.all()

        total_investment = 0
        total_weight = {'24': 0, '21': 0, '18': 0}
        weighted_price = {'24': 0, '21': 0, '18': 0}
        avg_price = {'24': 0, '21': 0, '18': 0}

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

        for k in ['24', '21', '18']:
            k_weight = sum(t.weight for t in transactions if str(t.karat) == k)
            avg_price[k] = weighted_price[k] / k_weight if k_weight > 0 else 0

        latest_price = GoldPrice.query.filter_by(price_type='local').order_by(GoldPrice.date.desc()).first()
        current_value = 0
        if latest_price:
            for k in ['24', '21', '18']:
                price = (
                    latest_price.price_24k if k == '24' else
                    latest_price.price_21k if k == '21' else
                    latest_price.price_18k
                )
                current_value += total_weight[k] * price

        return_amount = current_value - total_investment
        return_percentage = (return_amount / total_investment * 100) if total_investment > 0 else 0

        sale_metrics = {}
        if grams_sold > 0 and karat_sold in [24, 21, 18]:
            k = str(karat_sold)
            if total_weight[k] < grams_sold:
                return jsonify({'error': f'Only {total_weight[k]}g of {k}K available'}), 400

            current_price = (
                latest_price.price_24k if karat_sold == 24 else
                latest_price.price_21k if karat_sold == 21 else
                latest_price.price_18k
            )
            sell_value = grams_sold * current_price
            sale_return = sell_value - (grams_sold * avg_price[k])
            sale_return_pct = (sale_return / (grams_sold * avg_price[k]) * 100) if grams_sold * avg_price[k] > 0 else 0
            sale_metrics = {
                'sell_value': sell_value,
                'sale_return': {'amount': sale_return, 'percentage': sale_return_pct}
            }

        return jsonify({
            'total_investment': total_investment,
            'current_value': current_value,
            'return': {'amount': return_amount, 'percentage': return_percentage},
            'total_weight': total_weight,
            'sale_metrics': sale_metrics
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@gold_bp.route('/api/daily-returns')
def daily_returns():
    try:
        first_tx = GoldTransaction.query.order_by(GoldTransaction.date.asc()).first()
        if not first_tx:
            return jsonify({'dates': [], 'returns': []})

        start = request.args.get('start_date')
        start_date = datetime.strptime(start, '%Y-%m-%d').date() if start else first_tx.date
        end_date = datetime.strptime(request.args.get('end_date', datetime.now().strftime('%Y-%m-%d')).date()) if request.args.get('end_date') else datetime.now().date()

        transactions = GoldTransaction.query.filter(GoldTransaction.date <= end_date).all()
        sales = GoldSellTransaction.query.filter(GoldSellTransaction.date <= end_date).all()
        prices = GoldPrice.query.filter_by(price_type='local').filter(GoldPrice.date >= start_date, GoldPrice.date <= end_date).order_by(GoldPrice.date.asc()).all()

        dates = []
        returns = []
        current_date = start_date

        while current_date <= end_date:
            total_investment = 0
            total_weight = {'24': 0, '21': 0, '18': 0}
            weighted_price = {'24': 0, '21': 0, '18': 0}

            for t in transactions:
                if t.date <= current_date:
                    k = str(t.karat)
                    total_weight[k] += t.weight
                    total_investment += t.weight * t.purchase_price
                    weighted_price[k] += t.weight * t.purchase_price

            for s in sales:
                if s.date <= current_date:
                    k = str(s.karat)
                    total_weight[k] = max(0, total_weight[k] - s.weight)
                    k_weight = sum(t.weight for t in transactions if str(t.karat) == k)
                    k_price = weighted_price[k] / k_weight if k_weight > 0 else 0
                    total_investment -= s.weight * k_price

            latest_price = next((p for p in prices if p.date <= current_date), None)
            current_value = 0
            if latest_price:
                for k in ['24', '21', '18']:
                    price = (
                        latest_price.price_24k if k == '24' else
                        latest_price.price_21k if k == '21' else
                        latest_price.price_18k
                    )
                    current_value += total_weight[k] * price

            return_pct = ((current_value - total_investment) / total_investment * 100) if total_investment > 0 else 0
            dates.append(current_date.strftime('%Y-%m-%d'))
            returns.append(return_pct)
            current_date += timedelta(days=1)

        return jsonify({'dates': dates, 'returns': returns})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@gold_bp.route('/api/latest-prices')
def latest_prices():
    try:
        local = GoldPrice.query.filter_by(price_type='local').order_by(GoldPrice.date.desc()).first()
        global_ = GoldPrice.query.filter_by(price_type='global').order_by(GoldPrice.date.desc()).first()
        return jsonify({
            'local': {
                'price_24k': local.price_24k if local else 0,
                'price_21k': local.price_21k if local else 0,
                'price_18k': local.price_18k if local else 0,
                'price_pound': local.price_pound if local else 0,
                'date': local.date.strftime('%Y-%m-%d') if local else None
            },
            'global': {
                'price_24k': global_.price_24k if global_ else 0,
                'price_21k': global_.price_21k if global_ else 0,
                'price_18k': global_.price_18k if global_ else 0,
                'date': global_.date.strftime('%Y-%m-%d') if global_ else None
            }
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@gold_bp.route('/api/prices')
def api_prices():
    query = GoldPrice.query
    if 'start_date' in request.args:
        try:
            start_date = datetime.strptime(request.args.get('start_date'), '%Y-%m-%d').date()
            query = query.filter(GoldPrice.date >= start_date)
        except ValueError:
            return jsonify({'error': 'Invalid start_date format'}), 400

    if 'end_date' in request.args:
        try:
            end_date = datetime.strptime(request.args.get('end_date'), '%Y-%m-%d').date()
            query = query.filter(GoldPrice.date <= end_date)
        except ValueError:
            return jsonify({'error': 'Invalid end_date format'}), 400

    prices = query.order_by(GoldPrice.date.desc()).all()
    return jsonify([
        {
            'id': p.id,
            'price_type': p.price_type,
            'price_24k': p.price_24k,
            'price_21k': p.price_21k,
            'price_18k': p.price_18k,
            'price_pound': p.price_pound,
            'date': p.date.strftime('%Y-%m-%d')
        } for p in prices
    ])

@gold_bp.route('/api/price-returns')
def price_returns():
    try:
        today = datetime.now().date()
        periods = [
            {'name': '1d', 'days': 1},
            {'name': '5d', 'days': 5},
            {'name': '1m', 'days': 30},
            {'name': '1y', 'days': 365},
            {'name': '5y', 'days': 365 * 5}
        ]
        
        result = {'local': {}, 'global': {}}
        
        for price_type in ['local', 'global']:
            # Get latest price
            latest_price = GoldPrice.query.filter_by(price_type=price_type).order_by(GoldPrice.date.desc()).first()
            current_price = latest_price.price_24k if latest_price else 0
            latest_date = latest_price.date if latest_price else None
            
            # Initialize returns
            returns = {period['name']: 0 for period in periods}
            
            # Calculate returns for each period
            for period in periods:
                past_date = today - timedelta(days=period['days'])
                past_price_record = GoldPrice.query.filter_by(price_type=price_type).filter(GoldPrice.date <= past_date).order_by(GoldPrice.date.desc()).first()
                if past_price_record and current_price > 0:
                    past_price = past_price_record.price_24k
                    returns[period['name']] = ((current_price - past_price) / past_price * 100) if past_price > 0 else 0
            
            # Get all-time max and min
            max_price_record = GoldPrice.query.filter_by(price_type=price_type).order_by(GoldPrice.price_24k.desc()).first()
            min_price_record = GoldPrice.query.filter_by(price_type=price_type).order_by(GoldPrice.price_24k.asc()).first()
            
            result[price_type] = {
                'current_price': current_price,
                'date': latest_date.strftime('%Y-%m-%d') if latest_date else None,
                'returns': returns,
                'all_time_max': {
                    'price': max_price_record.price_24k if max_price_record else 0,
                    'date': max_price_record.date.strftime('%Y-%m-%d') if max_price_record else None
                },
                'all_time_min': {
                    'price': min_price_record.price_24k if min_price_record else 0,
                    'date': min_price_record.date.strftime('%Y-%m-%d') if min_price_record else None
                }
            }
        
        return jsonify(result)
    except Exception as e:
        logger.error(f"Error calculating price returns: {str(e)}")
        return jsonify({'error': str(e)}), 500

def get_total_weight_by_karat(exclude_sell_id=None):
    transactions = GoldTransaction.query.all()
    sales = GoldSellTransaction.query.filter(GoldSellTransaction.id != exclude_sell_id if exclude_sell_id else True).all()
    total_weight = {'24': 0, '21': 0, '18': 0}
    for t in transactions:
        total_weight[str(t.karat)] += t.weight
    for s in sales:
        total_weight[str(s.karat)] = max(0, total_weight[str(s.karat)] - s.weight)
    return total_weight

def get_avg_purchase_price(karat):
    transactions = GoldTransaction.query.filter_by(karat=karat).all()
    total_weight = sum(t.weight for t in transactions)
    weighted_price = sum(t.weight * t.purchase_price for t in transactions)
    return weighted_price / total_weight if total_weight > 0 else 0
