from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from src.models import db, Savings, SavingsGoal, Income
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta
from sqlalchemy import func
import logging
from src.models import db,Expense, StockTransaction, StockSellTransaction, MutualFundTransaction, MutualFundSellTransaction, StockPrice, MutualFundNAV, Income


logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

savings_bp = Blueprint('savings', __name__, url_prefix='/savings', template_folder='../../templates/savings')

@savings_bp.route('/')
def index():
    return render_template('savings/index.html')

@savings_bp.route('/goals')
def goals():
    goals = SavingsGoal.query.options(db.joinedload(SavingsGoal.savings_entries)).all()
    return render_template('savings/goals.html', goals=goals)

@savings_bp.route('/add', methods=['GET', 'POST'])
def add():
    goals = SavingsGoal.query.all()
    if request.method == 'POST':
        try:
            date = datetime.strptime(request.form['date'], '%Y-%m-%d').date()
            amount = float(request.form['amount'])
            goal_id = int(request.form['goal_id'])
            description = request.form.get('description', '')

            saving = Savings(
                date=date,
                amount=amount,
                goal_id=goal_id,
                description=description or None
            )
            db.session.add(saving)
            db.session.commit()
            flash('Saving added successfully!', 'success')
            return redirect(url_for('savings.index'))
        except Exception as e:
            logger.error(f"Error adding saving: {str(e)}")
            flash(f'Error adding saving: {str(e)}', 'error')
    return render_template('savings/add.html', goals=goals)

@savings_bp.route('/goals/add', methods=['GET', 'POST'])
def add_goal():
    if request.method == 'POST':
        try:
            name = request.form['name'].strip()
            target_amount = float(request.form['target_amount'])
            duration = int(request.form['duration'])
            savings_percentage = float(request.form['savings_percentage'])
            target_date = request.form.get('target_date')
            description = request.form.get('description', '')

            if duration <= 0:
                raise ValueError("Duration must be positive")
            if not (0 <= savings_percentage <= 100):
                raise ValueError("Savings percentage must be between 0 and 100")

            # Calculate monthly savings based on last income
            last_income = Income.query.order_by(Income.date.desc()).first()
            monthly_savings = (last_income.amount * (savings_percentage / 100) if last_income and savings_percentage > 0
                             else target_amount / duration)

            goal = SavingsGoal(
                name=name,
                target_amount=target_amount,
                duration=duration,
                savings_percentage=savings_percentage,
                monthly_savings=monthly_savings,
                target_date=datetime.strptime(target_date, '%Y-%m-%d').date() if target_date else None,
                description=description or None
            )
            db.session.add(goal)
            db.session.commit()
            flash(f'Goal added successfully! Monthly savings required: {format_currency(monthly_savings)}', 'success')
            return redirect(url_for('savings.goals'))
        except Exception as e:
            logger.error(f"Error adding savings goal: {str(e)}")
            flash(f'Error adding savings goal: {str(e)}', 'error')
    return render_template('savings/add_goal.html')

@savings_bp.route('/edit/<int:id>', methods=['GET', 'POST'])
def edit(id):
    saving = Savings.query.get_or_404(id)
    goals = SavingsGoal.query.all()
    if request.method == 'POST':
        try:
            saving.date = datetime.strptime(request.form['date'], '%Y-%m-%d').date()
            saving.amount = float(request.form['amount'])
            saving.goal_id = int(request.form['goal_id'])
            description = request.form.get('description', '')
            saving.description = description if description else None
            db.session.commit()
            flash('Saving updated successfully!', 'success')
            return redirect(url_for('savings.index'))
        except Exception as e:
            logger.error(f"Error updating saving: {str(e)}")
            flash(f'Error updating saving: {str(e)}', 'error')
    return render_template('savings/edit.html', saving=saving, goals=goals)

@savings_bp.route('/goals/edit/<int:id>', methods=['GET', 'POST'])
def edit_goal(id):
    goal = SavingsGoal.query.get_or_404(id)
    if request.method == 'POST':
        try:
            goal.name = request.form['name'].strip()
            goal.target_amount = float(request.form['target_amount'])
            goal.duration = int(request.form['duration'])
            goal.savings_percentage = float(request.form['savings_percentage'])
            target_date = request.form.get('target_date')
            description = request.form.get('description', '')
            goal.description = description if description else None
            goal.target_date = datetime.strptime(target_date, '%Y-%m-%d').date() if target_date else None

            if goal.duration <= 0:
                raise ValueError("Duration must be positive")
            if not (0 <= goal.savings_percentage <= 100):
                raise ValueError("Savings percentage must be between 0 and 100")

            # Recalculate monthly savings
            last_income = Income.query.order_by(Income.date.desc()).first()
            goal.monthly_savings = (last_income.amount * (goal.savings_percentage / 100) if last_income and goal.savings_percentage > 0
                                   else goal.target_amount / goal.duration)

            db.session.commit()
            flash('Goal updated successfully!', 'success')
            return redirect(url_for('savings.goals'))
        except Exception as e:
            logger.error(f"Error updating savings goal: {str(e)}")
            flash(f'Error updating savings goal: {str(e)}', 'error')
    return render_template('savings/edit_goal.html', goal=goal)

@savings_bp.route('/delete/<int:id>', methods=['POST'])
def delete(id):
    saving = Savings.query.get_or_404(id)
    try:
        db.session.delete(saving)
        db.session.commit()
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({'status': 'success', 'message': 'Saving deleted successfully!'})
        flash('Saving deleted successfully!', 'success')
    except Exception as e:
        logger.error(f"Error deleting saving: {str(e)}")
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({'status': 'error', 'message': str(e)}), 500
        flash(f'Error deleting saving: {str(e)}', 'error')
    referrer = request.referrer or url_for('savings.index')
    return redirect(referrer)

@savings_bp.route('/goals/delete/<int:id>', methods=['POST'])
def delete_goal(id):
    goal = SavingsGoal.query.get_or_404(id)
    try:
        if goal.savings:
            raise ValueError('Cannot delete goal with associated savings')
        db.session.delete(goal)
        db.session.commit()
        flash('Goal deleted successfully!', 'success')
        return redirect(url_for('savings.goals'))
    except Exception as e:
        logger.error(f"Error deleting goal: {str(e)}")
        flash(f'Error deleting goal: {str(e)}', 'error')
        return redirect(url_for('savings.goals'))

@savings_bp.route('/api/savings')
def api_savings():
    try:
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')

        query = Savings.query

        if start_date:
            try:
                start_date = datetime.strptime(start_date, '%Y-%m-%d').date()
                query = query.filter(Savings.date >= start_date)
            except ValueError:
                logger.error(f"Invalid start_date format: {start_date}")
                return jsonify({'error': 'Invalid start_date format'}), 400

        if end_date:
            try:
                end_date = datetime.strptime(end_date, '%Y-%m-%d').date()
                query = query.filter(Savings.date <= end_date)
            except ValueError:
                logger.error(f"Invalid end_date format: {end_date}")
                return jsonify({'error': 'Invalid end_date format'}), 400

        savings = query.order_by(Savings.date.desc()).all()

        result = [{
            'id': saving.id,
            'date': saving.date.strftime('%Y-%m-%d'),
            'goal_name': saving.goal.name if saving.goal else 'Unknown',
            'amount': float(saving.amount),
            'description': saving.description or '-'
        } for saving in savings]

        logger.debug(f"Fetched {len(result)} savings records")
        return jsonify(result)
    except Exception as e:
        logger.error(f"Error in api_savings: {str(e)}")
        return jsonify({'error': str(e)}), 500

@savings_bp.route('/api/goals')
def api_goals():
    try:
        goals = SavingsGoal.query.options(db.joinedload(SavingsGoal.savings_entries)).all()
        result = [{
            'id': goal.id,
            'name': goal.name,
            'target_amount': float(goal.target_amount),
            'total_saved': float(sum(saving.amount for saving in goal.savings_entries)),
            'progress': (sum(saving.amount for saving in goal.savings_entries) / goal.target_amount * 100) if goal.target_amount > 0 else 0.0,
            'target_date': goal.target_date.strftime('%Y-%m-%d') if goal.target_date else None,
            'duration': goal.duration,
            'savings_percentage': float(goal.savings_percentage),
            'monthly_savings': float(goal.monthly_savings)
        } for goal in goals]
        logger.debug(f"Fetched {len(result)} savings goals")
        return jsonify({'goals': result})  # Wrap the array in an object with a 'goals' key
    except Exception as e:
        logger.error(f"Error in api_goals: {str(e)}")
        return jsonify({'goals': [], 'error': str(e)})  # Return empty array on error



@savings_bp.route('/api/summary', methods=['GET'])
def savings_summary():
    try:
        # Get query parameters
        start_date_str = request.args.get('start_date')
        end_date_str = request.args.get('end_date')

        # Default to last 12 months if no dates provided
        end_date = datetime.utcnow().date()
        start_date = end_date - timedelta(days=365)

        # Parse provided dates
        if start_date_str:
            try:
                start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
            except ValueError:
                logger.warning(f"Invalid start_date format: {start_date_str}")
                return jsonify({'error': 'Invalid start_date format. Use YYYY-MM-DD.'}), 400
        if end_date_str:
            try:
                end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date()
            except ValueError:
                logger.warning(f"Invalid end_date format: {end_date_str}")
                return jsonify({'error': 'Invalid end_date format. Use YYYY-MM-DD.'}), 400

        # Ensure start_date is before end_date
        if start_date > end_date:
            logger.warning(f"start_date {start_date} is after end_date {end_date}")
            return jsonify({'error': 'start_date must be before end_date.'}), 400

        # Query income, expenses, and savings
        income_query = Income.query.filter(Income.date >= start_date, Income.date <= end_date)
        expense_query = Expense.query.filter(Expense.date >= start_date, Expense.date <= end_date)
        savings_query = Savings.query.filter(Savings.date >= start_date, Savings.date <= end_date)

        # Calculate total income and expenses
        total_income = sum(float(i.amount or 0) for i in income_query.all())
        total_expenses = sum(float(e.amount or 0) for e in expense_query.all())
        total_savings = total_income - total_expenses

        # By goal breakdown
        by_goal = {}
        savings_records = savings_query.all()
        logger.debug(f"Fetched {len(savings_records)} savings records")
        for saving in savings_records:
            goal_name = saving.goal.name if saving.goal else "No Goal"
            by_goal[goal_name] = by_goal.get(goal_name, 0.0) + float(saving.amount or 0)

        # By month breakdown
        by_month = {}
        income_by_month = {}
        expense_by_month = {}
        for income in income_query.all():
            month_key = income.date.strftime('%Y-%m')
            income_by_month[month_key] = income_by_month.get(month_key, 0.0) + float(income.amount or 0)
        for expense in expense_query.all():
            month_key = expense.date.strftime('%Y-%m')
            expense_by_month[month_key] = expense_by_month.get(month_key, 0.0) + float(expense.amount or 0)
        for month in set(list(income_by_month.keys()) + list(expense_by_month.keys())):
            by_month[month] = income_by_month.get(month, 0.0) - expense_by_month.get(month, 0.0)

        # By year breakdown
        by_year = {}
        income_by_year = {}
        expense_by_year = {}
        for income in income_query.all():
            year_key = income.date.strftime('%Y')
            income_by_year[year_key] = income_by_year.get(year_key, 0.0) + float(income.amount or 0)
        for expense in expense_query.all():
            year_key = expense.date.strftime('%Y')
            expense_by_year[year_key] = expense_by_year.get(year_key, 0.0) + float(expense.amount or 0)
        for year in set(list(income_by_year.keys()) + list(expense_by_year.keys())):
            by_year[year] = income_by_year.get(year, 0.0) - expense_by_year.get(year, 0.0)

        # Average daily savings
        days_diff = (end_date - start_date).days + 1
        average_daily = total_savings / days_diff if days_diff > 0 else 0.0

        # Average monthly savings
        months_diff = (end_date.year - start_date.year) * 12 + end_date.month - start_date.month + 1
        average_monthly = total_savings / months_diff if months_diff > 0 else 0.0

        # Average yearly savings
        years_diff = end_date.year - start_date.year + 1
        average_yearly = total_savings / years_diff if years_diff > 0 else 0.0

        # Daily max/min
        by_day = {}
        for income in income_query.all():
            day_key = income.date.strftime('%Y-%m-%d')
            by_day[day_key] = by_day.get(day_key, 0.0) + float(income.amount or 0)
        for expense in expense_query.all():
            day_key = expense.date.strftime('%Y-%m-%d')
            by_day[day_key] = by_day.get(day_key, 0.0) - float(expense.amount or 0)
        max_daily = max(by_day.items(), key=lambda x: x[1], default=(None, 0.0))
        min_daily = min(by_day.items(), key=lambda x: x[1], default=(None, 0.0))

        # Monthly max/min
        max_monthly = max(by_month.items(), key=lambda x: x[1], default=(None, 0.0))
        min_monthly = min(by_month.items(), key=lambda x: x[1], default=(None, 0.0))

        # Yearly max/min
        max_yearly = max(by_year.items(), key=lambda x: x[1], default=(None, 0.0))
        min_yearly = min(by_year.items(), key=lambda x: x[1], default=(None, 0.0))

        # Year-over-year and month-over-month growth
        sorted_years = sorted(by_year.keys())
        yoy_growth = 0.0
        if len(sorted_years) >= 2:
            current_year = by_year[sorted_years[-1]]
            prev_year = by_year[sorted_years[-2]]
            yoy_growth = ((current_year - prev_year) / prev_year * 100) if prev_year != 0 else 0.0

        sorted_months = sorted(by_month.keys())
        mom_growth = 0.0
        if len(sorted_months) >= 2:
            current_month = by_month[sorted_months[-1]]
            prev_month = by_month[sorted_months[-2]]
            mom_growth = ((current_month - prev_month) / prev_month * 100) if prev_month != 0 else 0.0

        return jsonify({
            'total': float(total_savings),
            'by_goal': by_goal,
            'by_month': by_month,
            'by_year': by_year,
            'average_daily': float(average_daily),
            'average_monthly': float(average_monthly),
            'average_yearly': float(average_yearly),
            'max_daily': {'amount': float(max_daily[1]), 'date': max_daily[0] or ''},
            'min_daily': {'amount': float(min_daily[1]), 'date': min_daily[0] or ''},
            'max_monthly': {'amount': float(max_monthly[1]), 'month': max_monthly[0] or ''},
            'min_monthly': {'amount': float(min_monthly[1]), 'month': min_monthly[0] or ''},
            'max_yearly': {'amount': float(max_yearly[1]), 'year': max_yearly[0] or ''},
            'min_yearly': {'amount': float(min_yearly[1]), 'year': min_yearly[0] or ''},
            'yoy_growth': float(yoy_growth),
            'mom_growth': float(mom_growth)
        })
    except Exception as e:
        logger.error(f"Error in savings_summary: {str(e)}", exc_info=True)
        return jsonify({'error': str(e)}), 500
