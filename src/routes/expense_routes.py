from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from src.models import db, Expense, ExpenseCategory, RecurringExpense
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta
from sqlalchemy import func
import logging

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

expense_bp = Blueprint('expense', __name__, url_prefix='/expense', template_folder='../../templates/expense')

@expense_bp.route('/')
def index():
    view_all = request.args.get('view_all', 'false').lower() == 'true'
    if view_all:
        return render_template('expense/view_all.html')
    return render_template('expense/index.html')

@expense_bp.route('/add', methods=['GET', 'POST'])
def add():
    categories = ExpenseCategory.query.all()
    if request.method == 'POST':
        try:
            date = datetime.strptime(request.form['date'], '%Y-%m-%d').date()
            amount = float(request.form['amount'])
            category_id = int(request.form['category_id'])
            item = request.form['item']
            if item == 'other':
                item = request.form.get('new_item', '').strip()
                if not item:
                    raise ValueError('New item is required when "Other" is selected')
            quantity = float(request.form['quantity']) if request.form.get('quantity') else None
            unit = request.form.get('unit', '')
            description = request.form.get('description', '')
            recurring = request.form.get('recurring') == 'on'
            recurrence_day = int(request.form['recurrence_day']) if recurring else None

            expense = Expense(
                date=date,
                amount=amount,
                category_id=category_id,
                item=item or None,
                quantity=quantity,
                unit=unit or None,
                description=description or None
            )
            db.session.add(expense)

            if recurring:
                recurring_expense = RecurringExpense(
                    item=item,
                    amount=amount,
                    category_id=category_id,
                    recurrence_day=recurrence_day,
                    spontaneous=False,
                    description=description or None
                )
                db.session.add(recurring_expense)

            db.session.commit()
            flash('Expense added successfully!', 'success')
            return redirect(url_for('expense.index'))
        except Exception as e:
            logger.error(f"Error adding expense: {str(e)}")
            flash(f'Error adding expense: {str(e)}', 'error')
    return render_template('expense/add.html', categories=categories)

@expense_bp.route('/edit/<int:id>', methods=['GET', 'POST'])
def edit(id):
    expense = Expense.query.get_or_404(id)
    categories = ExpenseCategory.query.all()
    if request.method == 'POST':
        try:
            expense.date = datetime.strptime(request.form['date'], '%Y-%m-%d').date()
            expense.amount = float(request.form['amount'])
            expense.category_id = int(request.form['category_id'])
            expense.item = request.form.get('item', '')
            expense.quantity = float(request.form['quantity']) if request.form.get('quantity') else None
            expense.unit = request.form.get('unit', '')
            description = request.form.get('description', '')
            expense.description = description if description else None
            db.session.commit()
            flash('Expense updated successfully!', 'success')
            return redirect(url_for('expense.index'))
        except Exception as e:
            logger.error(f"Error updating expense: {str(e)}")
            flash(f'Error updating expense: {str(e)}', 'error')
    return render_template('expense/edit.html', expense=expense, categories=categories)

@expense_bp.route('/delete/<int:id>', methods=['POST'])
def delete(id):
    expense = Expense.query.get_or_404(id)
    try:
        db.session.delete(expense)
        db.session.commit()
        if request.is_xhr:
            return jsonify({'status': 'success', 'message': 'Expense deleted successfully!'})
        flash('Expense deleted successfully!', 'success')
    except Exception as e:
        logger.error(f"Error deleting expense: {str(e)}")
        if request.is_xhr:
            return jsonify({'status': 'error', 'message': str(e)}), 500
        flash(f'Error deleting expense: {str(e)}', 'error')
    referrer = request.referrer or url_for('expense.index')
    return redirect(referrer)

@expense_bp.route('/delete_multiple', methods=['POST'])
def delete_multiple():
    try:
        data = request.get_json()
        ids = data.get('ids', [])
        if not ids:
            return jsonify({'status': 'error', 'message': 'No expenses selected'}), 400

        deleted_count = 0
        for id in ids:
            expense = Expense.query.get(id)
            if expense:
                db.session.delete(expense)
                deleted_count += 1
        db.session.commit()

        return jsonify({
            'status': 'success',
            'message': f'{deleted_count} expense(s) deleted successfully!'
        })
    except Exception as e:
        logger.error(f"Error deleting multiple expenses: {str(e)}")
        db.session.rollback()
        return jsonify({'status': 'error', 'message': str(e)}), 500

@expense_bp.route('/categories')
def categories():
    categories = ExpenseCategory.query.all()
    return render_template('expense/categories.html', categories=categories)

@expense_bp.route('/categories/add', methods=['GET', 'POST'])
def add_category():
    if request.method == 'POST':
        try:
            name = request.form['name'].strip().lower()
            if not name:
                raise ValueError('Category name is required')
            if ExpenseCategory.query.filter_by(name=name).first():
                raise ValueError(f'Category {name} already exists')
            category = ExpenseCategory(name=name)
            db.session.add(category)
            db.session.commit()
            flash('Category added successfully!', 'success')
            return redirect(url_for('expense.categories'))
        except Exception as e:
            logger.error(f"Error adding category: {str(e)}")
            flash(f'Error adding category: {str(e)}', 'error')
    return render_template('expense/add_category.html')

@expense_bp.route('/categories/edit/<int:id>', methods=['GET', 'POST'])
def edit_category(id):
    category = ExpenseCategory.query.get_or_404(id)
    if request.method == 'POST':
        try:
            name = request.form['name'].strip()
            if not name:
                raise ValueError('Category name is required')
            if ExpenseCategory.query.filter_by(name=name).filter(ExpenseCategory.id != id).first():
                raise ValueError(f'Category {name} already exists')
            category.name = name
            db.session.commit()
            flash('Category updated successfully!', 'success')
            return redirect(url_for('expense.categories'))
        except Exception as e:
            logger.error(f"Error updating category: {str(e)}")
            flash(f'Error updating category: {str(e)}', 'error')
    return render_template('expense/edit_category.html', category=category)

@expense_bp.route('/categories/delete/<int:id>', methods=['POST'])
def delete_category(id):
    category = ExpenseCategory.query.get_or_404(id)
    try:
        if Expense.query.filter_by(category_id=category.id).first():
            raise ValueError('Cannot delete category with associated expenses')
        db.session.delete(category)
        db.session.commit()
        flash('Category deleted successfully!', 'success')
        return redirect(url_for('expense.categories'))
    except Exception as e:
        logger.error(f"Error deleting category: {str(e)}")
        flash(f'Error deleting category: {str(e)}', 'error')
        return redirect(url_for('expense.categories'))

@expense_bp.route('/api/list')
def api_list():
    try:
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')

        query = Expense.query

        if start_date:
            try:
                start_date = datetime.strptime(start_date, '%Y-%m-%d').date()
                query = query.filter(Expense.date >= start_date)
            except ValueError:
                logger.error(f"Invalid start_date format: {start_date}")
                return jsonify({'error': 'Invalid start_date format'}), 400

        if end_date:
            try:
                end_date = datetime.strptime(end_date, '%Y-%m-%d').date()
                query = query.filter(Expense.date <= end_date)
            except ValueError:
                logger.error(f"Invalid end_date format: {end_date}")
                return jsonify({'error': 'Invalid end_date format'}), 400

        expenses = query.order_by(Expense.date.desc()).all()

        result = [{
            'id': expense.id,
            'date': expense.date.strftime('%Y-%m-%d'),
            'item': expense.item or '-',
            'category': expense.category.name if expense.category else 'Unknown',
            'amount': float(expense.amount),
            'description': expense.description or '-'
        } for expense in expenses]

        logger.debug(f"Fetched {len(result)} expense records")
        return jsonify(result)
    except Exception as e:
        logger.error(f"Error in api_list: {str(e)}")
        return jsonify({'error': str(e)}), 500

@expense_bp.route('/api/summary')
def api_summary():
    try:
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')

        query = Expense.query

        if start_date:
            try:
                start_date = datetime.strptime(start_date, '%Y-%m-%d').date()
                query = query.filter(Expense.date >= start_date)
            except ValueError:
                logger.error(f"Invalid start_date format: {start_date}")
                return jsonify({'error': 'Invalid start_date format'}), 400

        if end_date:
            try:
                end_date = datetime.strptime(end_date, '%Y-%m-%d').date()
                query = query.filter(Expense.date <= end_date)
            except ValueError:
                logger.error(f"Invalid end_date format: {end_date}")
                return jsonify({'error': 'Invalid end_date format'}), 400

        expenses = query.all()

        response = {
            'total': 0.0,
            'max_monthly': {'amount': 0.0, 'month': ''},
            'min_monthly': {'amount': 0.0, 'month': ''},
            'average_monthly': 0.0,
            'yoy_change': 0.0,
            'mom_change': 0.0,
            'by_category': {},
            'by_month': {},
            'by_year': {},
            'top_5_expensive': [],
            'top_5_cheapest': [],
            'top_5_frequent': [],
            'start_date': start_date.strftime('%Y-%m-%d') if start_date else None,
            'end_date': end_date.strftime('%Y-%m-%d') if end_date else None
        }

        if expenses:
            total = sum(float(expense.amount) for expense in expenses)
            response['total'] = float(total)

            months = set(expense.date.strftime('%Y-%m') for expense in expenses)
            if months:
                response['average_monthly'] = float(total / len(months))

            # Calculate average daily expense
            if start_date and end_date:
                # Calculate total days in the period (inclusive)
                delta = (end_date - start_date).days + 1
                response['avg_daily_expense'] = float(total / delta)
            else:
                # Calculate period based on min and max dates in the data
                dates = [expense.date for expense in expenses]
                if dates:
                    min_date = min(dates)
                    max_date = max(dates)
                    delta = (max_date - min_date).days + 1
                    response['avg_daily_expense'] = float(total / delta)
                    
            yearly_totals = {}
            for expense in expenses:
                year_key = expense.date.strftime('%Y')
                yearly_totals[year_key] = yearly_totals.get(year_key, 0.0) + float(expense.amount)
            response['by_year'] = {k: float(v) for k, v in yearly_totals.items()}

            by_category = {}
            for expense in expenses:
                category = expense.category.name if expense.category else 'Unknown'
                by_category[category] = by_category.get(category, 0.0) + float(expense.amount)
            response['by_category'] = {k: float(v) for k, v in by_category.items()}

            by_month = {}
            for expense in expenses:
                month_key = expense.date.strftime('%Y-%m')
                by_month[month_key] = by_month.get(month_key, 0.0) + float(expense.amount)
            response['by_month'] = {k: float(v) for k, v in by_month.items()}

            if by_month:
                max_month = max(by_month.items(), key=lambda x: x[1])
                min_month = min(by_month.items(), key=lambda x: x[1])
                response['max_monthly'] = {'amount': float(max_month[1]), 'month': max_month[0]}
                response['min_monthly'] = {'amount': float(min_month[1]), 'month': min_month[0]}

            if start_date and end_date:
                prev_year_start = start_date - relativedelta(years=1)
                prev_year_end = end_date - relativedelta(years=1)
                prev_year_expenses = Expense.query.filter(
                    Expense.date >= prev_year_start,
                    Expense.date <= prev_year_end
                ).all()
                prev_year_total = sum(float(expense.amount) for expense in prev_year_expenses)
                if prev_year_total > 0:
                    response['yoy_change'] = float(((total - prev_year_total) / prev_year_total) * 100)

            if by_month:
                sorted_months = sorted(by_month.keys())
                latest_month = sorted_months[-1]
                latest_month_total = by_month[latest_month]
                if len(sorted_months) > 1:
                    prev_month = sorted_months[-2]
                    prev_month_total = by_month[prev_month]
                    if prev_month_total > 0:
                        response['mom_change'] = float(((latest_month_total - prev_month_total) / prev_month_total) * 100)

            sorted_expenses = sorted(expenses, key=lambda x: x.amount, reverse=True)
            response['top_5_expensive'] = [{
                'item': expense.item or 'Unknown',
                'amount': float(expense.amount),
                'date': expense.date.strftime('%Y-%m-%d')
            } for expense in sorted_expenses[:5]]

            response['top_5_cheapest'] = [{
                'item': expense.item or 'Unknown',
                'amount': float(expense.amount),
                'date': expense.date.strftime('%Y-%m-%d')
            } for expense in sorted(expenses, key=lambda x: x.amount)[:5]]

            item_counts = {}
            for expense in expenses:
                item = expense.item or 'Unknown'
                item_counts[item] = item_counts.get(item, 0) + 1
            response['top_5_frequent'] = [{
                'item': item,
                'count': count,
                'total_cost': sum(float(e.amount) for e in expenses if (e.item or 'Unknown') == item)
            } for item, count in sorted(item_counts.items(), key=lambda x: x[1], reverse=True)[:5]]

            item_totals = {}
            for expense in expenses:
                item = expense.item or 'Unknown'
                item_totals[item] = item_totals.get(item, 0.0) + float(expense.amount)
            top_5_items_by_spend = sorted(
                [{'item': item, 'total': total} for item, total in item_totals.items()],
                key=lambda x: x['total'],
                reverse=True
            )[:5]
            response['top_5_items_by_spend'] = top_5_items_by_spend
            
        logger.debug(f"Expense summary: {response}")
        return jsonify(response)
    except Exception as e:
        logger.error(f"Error in api_summary: {str(e)}", exc_info=True)
        return jsonify({'error': str(e)}), 500

@expense_bp.route('/item_analysis')
def analysis():
    try:
        categories = ExpenseCategory.query.all()
        return render_template('expense/item_analysis.html', categories=categories)
    except Exception as e:
        logger.error(f"Error loading item analysis page: {str(e)}")
        flash('Error loading analysis page. Please try again.', 'error')
        return redirect(url_for('expense.index'))

@expense_bp.route('/api/category_trends')
def api_category_trends():
    try:
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')

        query = Expense.query

        if start_date:
            try:
                start_date = datetime.strptime(start_date, '%Y-%m-%d').date()
                query = query.filter(Expense.date >= start_date)
            except ValueError:
                logger.error(f"Invalid start_date format: {start_date}")
                return jsonify({'error': 'Invalid start_date format'}), 400

        if end_date:
            try:
                end_date = datetime.strptime(end_date, '%Y-%m-%d').date()
                query = query.filter(Expense.date <= end_date)
            except ValueError:
                logger.error(f"Invalid end_date format: {end_date}")
                return jsonify({'error': 'Invalid end_date format'}), 400

        expenses = query.all()

        category_trends = {}
        for expense in expenses:
            category = expense.category.name if expense.category else 'Unknown'
            if category not in category_trends:
                category_trends[category] = {}
            month_key = expense.date.strftime('%Y-%m')
            category_trends[category][month_key] = category_trends[category].get(month_key, 0.0) + float(expense.amount)

        logger.debug(f"Category trends: categories={len(category_trends)}")
        return jsonify(category_trends)
    except Exception as e:
        logger.error(f"Error in api_category_trends: {str(e)}")
        return jsonify({'error': str(e)}), 500

@expense_bp.route('/api/items')
def get_items():
    try:
        category_id = request.args.get('category_id')
        query = db.session.query(func.lower(Expense.item).label('item')).distinct()
        if category_id and category_id.isdigit():
            query = query.filter(Expense.category_id == int(category_id))
        query = query.filter(Expense.item != None).order_by(func.lower(Expense.item))
        items = [item.item for item in query.all() if item.item]
        return jsonify({'items': items})
    except Exception as e:
        logger.error(f"Error fetching items: {str(e)}")
        return jsonify({'error': str(e)}), 500

@expense_bp.route('/api/item_analysis/<item_name>')
def item_analysis(item_name):
    try:
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')
        
        logger.info(f"Analyzing item: {item_name} from {start_date} to {end_date}")
        
        query = Expense.query.filter(func.lower(Expense.item) == item_name.strip().lower())
        
        if start_date:
            try:
                start_date = datetime.strptime(start_date, '%Y-%m-%d').date()
                query = query.filter(Expense.date >= start_date)
            except ValueError:
                logger.error(f"Invalid start_date format: {start_date}")
                return jsonify({'error': 'Invalid start_date format'}), 400

        if end_date:
            try:
                end_date = datetime.strptime(end_date, '%Y-%m-%d').date()
                query = query.filter(Expense.date <= end_date)
            except ValueError:
                logger.error(f"Invalid end_date format: {end_date}")
                return jsonify({'error': 'Invalid end_date format'}), 400
            
        transactions = query.order_by(Expense.date).all()
        
        if not transactions:
            logger.warning(f"No transactions found for item: {item_name}")
            return jsonify({
                'status': 'error',
                'message': f'No transactions found for item "{item_name}"'
            }), 404
            
        logger.debug(f"Found {len(transactions)} transactions for item: {item_name}")
        
        unit_prices = []
        total_quantity = 0.0
        amounts = []
        for t in transactions:
            quantity = t.quantity if t.quantity and t.quantity > 0 else 1.0
            total_quantity += quantity
            unit_price = float(t.amount) / quantity
            unit_prices.append(unit_price)
            amounts.append(float(t.amount))
        
        if not amounts or not unit_prices:
            logger.warning(f"No valid amounts or unit prices for item: {item_name}")
            return jsonify({
                'status': 'error',
                'message': 'No valid price data available'
            }), 404

        max_price = max(amounts)
        min_price = min(amounts)
        max_unit_price = max(unit_prices)
        min_unit_price = min(unit_prices)
        total_spent = sum(amounts)
    
        max_trans = next(t for t in transactions if float(t.amount) == max_price)
        min_trans = next(t for t in transactions if float(t.amount) == min_price)
        max_unit_trans = next(t for t in transactions if float(t.amount) / (t.quantity or 1.0) == max_unit_price)
        min_unit_trans = next(t for t in transactions if float(t.amount) / (t.quantity or 1.0) == min_unit_price)
    
        monthly_data = {}
        for t in transactions:
            month_key = t.date.strftime('%Y-%m')
            if month_key not in monthly_data:
                monthly_data[month_key] = []
            monthly_data[month_key].append(float(t.amount) / (t.quantity or 1.0))
    
        avg_monthly = total_spent / len(monthly_data) if monthly_data else 0
        
        price_trend = [{
            'date': t.date.isoformat(),
            'amount': float(t.amount) / (t.quantity or 1.0)
        } for t in transactions]
    
        inflation_data = calculate_item_inflation(transactions, unit_price=True)
    
        response = {
            'status': 'success',
            'max_price': {
                'amount': float(max_price),
                'date': max_trans.date.isoformat()
            },
            'min_price': {
                'amount': float(min_price),
                'date': min_trans.date.isoformat()
            },
            'max_unit_price': {
                'amount': float(max_unit_price),
                'date': max_unit_trans.date.isoformat()
            },
            'min_unit_price': {
                'amount': float(min_unit_price),
                'date': min_unit_trans.date.isoformat()
            },
            'total_spent': float(total_spent),
            'total_quantity': float(total_quantity),
            'avg_monthly': float(avg_monthly),
            'price_trend': price_trend,
            'inflation': inflation_data
        }
        
        logger.debug(f"Item analysis response: {response}")
        return jsonify(response)
    except Exception as e:
        logger.error(f"Error in item analysis for {item_name}: {str(e)}", exc_info=True)
        return jsonify({'status': 'error', 'message': str(e)}), 500

def calculate_item_inflation(transactions, unit_price=False):
    monthly = {}
    for t in transactions:
        key = t.date.strftime('%Y-%m')
        if key not in monthly:
            monthly[key] = []
        amount = float(t.amount) / (t.quantity or 1.0) if unit_price else float(t.amount)
        monthly[key].append(amount)
    
    monthly_avg = {k: sum(v)/len(v) for k, v in monthly.items()}
    sorted_months = sorted(monthly_avg.keys())
    
    inflation = []
    
    for i in range(1, len(sorted_months)):
        prev_month = sorted_months[i-1]
        curr_month = sorted_months[i]
        prev_price = monthly_avg[prev_month]
        curr_price = monthly_avg[curr_month]
        
        if prev_price == 0:
            continue
            
        change = ((curr_price - prev_price) / prev_price) * 100
        inflation.append({
            'period': f"{prev_month} to {curr_month}",
            'inflation': round(change, 2),
            'type': 'monthly'
        })
    
    if len(sorted_months) >= 13:
        for i in range(12, len(sorted_months)):
            year_ago_month = sorted_months[i-12]
            curr_month = sorted_months[i]
            year_ago_price = monthly_avg[year_ago_month]
            curr_price = monthly_avg[curr_month]
            
            if year_ago_price == 0:
                continue
                
            change = ((curr_price - year_ago_price) / year_ago_price) * 100
            inflation.append({
                'period': f"{year_ago_month} to {curr_month} (YoY)",
                'inflation': round(change, 2),
                'type': 'yearly'
            })
    
    if not inflation:
        for i in range(1, len(transactions)):
            prev = transactions[i-1]
            curr = transactions[i]
            prev_amount = float(prev.amount) / (prev.quantity or 1.0) if unit_price else float(prev.amount)
            curr_amount = float(curr.amount) / (curr.quantity or 1.0) if unit_price else float(curr.amount)
            if prev_amount == 0:
                continue
            change = ((curr_amount - prev_amount) / prev_amount) * 100
            inflation.append({
                'period': f"{prev.date.strftime('%Y-%m-%d')} to {curr.date.strftime('%Y-%m-%d')}",
                'inflation': round(change, 2),
                'type': 'transaction'
            })
    
    return inflation

@expense_bp.route('/recurring', methods=['GET', 'POST'])
def recurring():
    categories = ExpenseCategory.query.all()
    if request.method == 'POST':
        try:
            item = request.form['item']
            amount = float(request.form['amount'])
            category_id = int(request.form['category_id'])
            recurrence_day = int(request.form['recurrence_day'])
            spontaneous = request.form.get('spontaneous') == 'on'
            description = request.form.get('description', '')

            recurring_expense = RecurringExpense(
                item=item,
                amount=amount,
                category_id=category_id,
                recurrence_day=recurrence_day,
                spontaneous=spontaneous,
                description=description or None
            )
            db.session.add(recurring_expense)
            db.session.commit()
            flash('Recurring expense added successfully!', 'success')
            return redirect(url_for('expense.recurring'))
        except Exception as e:
            logger.error(f"Error adding recurring expense: {str(e)}")
            flash(f'Error adding recurring expense: {str(e)}', 'error')

    recurring_expenses = RecurringExpense.query.all()
    return render_template('expense/recurring.html', recurring_expenses=recurring_expenses, categories=categories)

@expense_bp.route('/recurring/edit/<int:id>', methods=['GET', 'POST'])
def edit_recurring(id):
    recurring_expense = RecurringExpense.query.get_or_404(id)
    categories = ExpenseCategory.query.all()
    if request.method == 'POST':
        try:
            recurring_expense.item = request.form['item']
            recurring_expense.amount = float(request.form['amount'])
            recurring_expense.category_id = int(request.form['category_id'])
            recurring_expense.recurrence_day = int(request.form['recurrence_day'])
            recurring_expense.spontaneous = request.form.get('spontaneous') == 'on'
            description = request.form.get('description', '')
            recurring_expense.description = description if description else None
            db.session.commit()
            flash('Recurring expense updated successfully!', 'success')
            return redirect(url_for('expense.recurring'))
        except Exception as e:
            logger.error(f"Error updating recurring expense: {str(e)}")
            flash(f'Error updating recurring expense: {str(e)}', 'error')
    return render_template('expense/edit_recurring.html', recurring_expense=recurring_expense, categories=categories)

@expense_bp.route('/recurring/delete/<int:id>', methods=['POST'])
def delete_recurring(id):
    recurring_expense = RecurringExpense.query.get_or_404(id)
    try:
        db.session.delete(recurring_expense)
        db.session.commit()
        flash('Recurring expense deleted successfully!', 'success')
    except Exception as e:
        logger.error(f"Error deleting recurring expense: {str(e)}")
        flash(f'Error deleting recurring expense: {str(e)}', 'error')
    return redirect(url_for('expense.recurring'))

@expense_bp.route('/api/recurring', methods=['GET'])
def get_recurring_expenses():
    try:
        recurring_expenses = RecurringExpense.query.all()
        result = [
            {
                'id': expense.id,
                'item': expense.item,
                'amount': expense.amount,
                'category': expense.category.name if expense.category else 'Uncategorized',
                'recurrence_day': expense.recurrence_day,
                'spontaneous': expense.spontaneous,
                'description': expense.description
            } for expense in recurring_expenses
        ]
        return jsonify(result), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500
