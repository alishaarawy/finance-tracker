from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from src.models import db, Income
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta
from sqlalchemy import func
import logging

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

income_bp = Blueprint('income', __name__, url_prefix='/income', template_folder='../../templates/income')

@income_bp.route('/')
def index():
    view_all = request.args.get('view_all', 'false').lower() == 'true'
    if view_all:
        return render_template('income/view_all.html')
    return render_template('income/index.html')

@income_bp.route('/add', methods=['GET', 'POST'])
def add():
    sources = db.session.query(Income.source).distinct().order_by(Income.source).all()
    sources = [source[0] for source in sources if source[0]]
    
    if request.method == 'POST':
        try:
            date = datetime.strptime(request.form['date'], '%Y-%m-%d').date()
            amount = float(request.form['amount'])
            source = request.form['source']
            if source == 'other':
                source = request.form.get('new_source', '').strip()
                if not source:
                    raise ValueError('New source is required when "Other" is selected')
            description = request.form.get('description', '')

            income = Income(
                date=date,
                amount=amount,
                source=source,
                description=description or None
            )
            db.session.add(income)
            db.session.commit()
            flash('Income added successfully!', 'success')
            return redirect(url_for('income.add'))  # Stay on add page
        except Exception as e:
            logger.error(f"Error adding income: {str(e)}")
            flash(f'Error adding income: {str(e)}', 'error')
    
    return render_template('income/add.html', sources=sources)

@income_bp.route('/edit/<int:id>', methods=['GET', 'POST'])
def edit(id):
    income = Income.query.get_or_404(id)
    
    if request.method == 'POST':
        try:
            income.date = datetime.strptime(request.form['date'], '%Y-%m-%d').date()
            income.amount = float(request.form['amount'])
            income.source = request.form['source']
            description = request.form.get('description', '')
            income.description = description if description else None
            db.session.commit()
            flash('Income updated successfully!', 'success')
            return redirect(url_for('income.index'))
        except Exception as e:
            logger.error(f"Error updating income: {str(e)}")
            flash(f'Error updating income: {str(e)}', 'error')
    
    # For GET request, just render the template with income data
    return render_template('income/edit.html', income=income)

@income_bp.route('/delete/<int:id>', methods=['POST'])
def delete(id):
    income = Income.query.get_or_404(id)
    try:
        db.session.delete(income)
        db.session.commit()
        
        # Check if request is AJAX by looking for the X-Requested-With header
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({'status': 'success', 'message': 'Income deleted successfully!'})
        
        flash('Income deleted successfully!', 'success')
    except Exception as e:
        logger.error(f"Error deleting income: {str(e)}")
        
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({'status': 'error', 'message': str(e)}), 500
        
        flash(f'Error deleting income: {str(e)}', 'error')
    
    referrer = request.referrer or url_for('income.index')
    return redirect(referrer)

@income_bp.route('/delete_multiple', methods=['POST'])
def delete_multiple():
    try:
        # Check for AJAX first
        if request.headers.get('X-Requested-With') != 'XMLHttpRequest':
            return jsonify({'status': 'error', 'message': 'Invalid request'}), 400
            
        data = request.get_json()
        ids = data.get('ids', [])
        if not ids:
            return jsonify({'status': 'error', 'message': 'No incomes selected'}), 400

        deleted_count = 0
        for id in ids:
            income = Income.query.get(id)
            if income:
                db.session.delete(income)
                deleted_count += 1
        db.session.commit()

        return jsonify({
            'status': 'success',
            'message': f'{deleted_count} income(s) deleted successfully!'
        })
    except Exception as e:
        logger.error(f"Error deleting multiple incomes: {str(e)}")
        db.session.rollback()
        return jsonify({'status': 'error', 'message': str(e)}), 500

@income_bp.route('/api/list')
def api_list():
    try:
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')

        query = Income.query

        if start_date:
            try:
                start_date = datetime.strptime(start_date, '%Y-%m-%d').date()
                query = query.filter(Income.date >= start_date)
            except ValueError:
                logger.error(f"Invalid start_date format: {start_date}")
                return jsonify({'error': 'Invalid start_date format'}), 400

        if end_date:
            try:
                end_date = datetime.strptime(end_date, '%Y-%m-%d').date()
                query = query.filter(Income.date <= end_date)
            except ValueError:
                logger.error(f"Invalid end_date format: {end_date}")
                return jsonify({'error': 'Invalid end_date format'}), 400

        incomes = query.order_by(Income.date.desc()).all()

        result = [{
            'id': income.id,
            'date': income.date.strftime('%Y-%m-%d'),
            'source': income.source or '-',
            'amount': float(income.amount),
            'description': income.description or '-'
        } for income in incomes]

        logger.debug(f"Fetched {len(result)} income records")
        return jsonify(result)
    except Exception as e:
        logger.error(f"Error in api_list: {str(e)}")
        return jsonify({'error': str(e)}), 500

@income_bp.route('/api/summary')
def api_summary():
    try:
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')

        query = Income.query

        # Date parsing and filtering (existing code)
        if start_date:
            try:
                start_date = datetime.strptime(start_date, '%Y-%m-%d').date()
                query = query.filter(Income.date >= start_date)
            except ValueError:
                logger.error(f"Invalid start_date format: {start_date}")
                return jsonify({'error': 'Invalid start_date format'}), 400

        if end_date:
            try:
                end_date = datetime.strptime(end_date, '%Y-%m-%d').date()
                query = query.filter(Income.date <= end_date)
            except ValueError:
                logger.error(f"Invalid end_date format: {end_date}")
                return jsonify({'error': 'Invalid end_date format'}), 400

        incomes = query.all()

        # Calculate duration in Y M D format
        duration_str = "0D"
        if start_date and end_date:
            delta = relativedelta(end_date, start_date)
            duration_str = f"{delta.years}Y {delta.months}M {delta.days}D"
        elif incomes:
            dates = [income.date for income in incomes]
            if dates:
                min_date = min(dates)
                max_date = max(dates)
                delta = relativedelta(max_date, min_date)
                duration_str = f"{delta.years}Y {delta.months}M {delta.days}D"

        # Calculate total and basic stats
        total = sum(float(income.amount) for income in incomes)
        months = set(income.date.strftime('%Y-%m') for income in incomes)
        avg_income = float(total / len(months)) if months else 0.0

        # Calculate average daily income and total days
        total_days = 0
        avg_daily_income = 0.0
        
        if start_date and end_date:
            # Calculate total days in the period (inclusive)
            total_days = (end_date - start_date).days + 1
            avg_daily_income = float(total / total_days) if total_days > 0 else 0.0
        elif incomes:
            # Calculate period based on min and max dates in the data
            dates = [income.date for income in incomes]
            min_date = min(dates)
            max_date = max(dates)
            total_days = (max_date - min_date).days + 1
            avg_daily_income = float(total / total_days) if total_days > 0 else 0.0

        # Calculate yearly totals
        yearly_totals = {}
        for income in incomes:
            year_key = income.date.strftime('%Y')
            yearly_totals[year_key] = yearly_totals.get(year_key, 0.0) + float(income.amount)

        # Group by month and calculate monthly totals
        monthly_totals = {}
        for income in incomes:
            month_key = income.date.strftime('%Y-%m')
            monthly_totals[month_key] = monthly_totals.get(month_key, 0.0) + float(income.amount)

        # Find month with highest and lowest totals
        max_month = None
        min_month = None
        max_amount = 0.0
        min_amount = float('inf')
        
        for month, amount in monthly_totals.items():
            if amount > max_amount:
                max_amount = amount
                max_month = month
            if amount < min_amount:
                min_amount = amount
                min_month = month

        # Format month names for display
        max_month_name = datetime.strptime(max_month, '%Y-%m').strftime('%B %Y') if max_month else 'N/A'
        min_month_name = datetime.strptime(min_month, '%Y-%m').strftime('%B %Y') if min_month else 'N/A'

        # Group by source
        by_source = {}
        for income in incomes:
            source = income.source or 'Unknown'
            by_source[source] = by_source.get(source, 0.0) + float(income.amount)

        # YoY Growth
        yoy_growth = 0.0
        if start_date and end_date:
            prev_year_start = start_date - relativedelta(years=1)
            prev_year_end = end_date - relativedelta(years=1)
            prev_year_incomes = Income.query.filter(
                Income.date >= prev_year_start,
                Income.date <= prev_year_end
            ).all()
            prev_year_total = sum(float(income.amount) for income in prev_year_incomes)
            yoy_growth = ((total - prev_year_total) / prev_year_total * 100) if prev_year_total > 0 else 0.0

        # MoM Growth
        mom_growth = 0.0
        if monthly_totals and len(monthly_totals) > 1:
            sorted_months = sorted(monthly_totals.keys())
            current_month = sorted_months[-1]
            previous_month = sorted_months[-2]
            current_amount = monthly_totals[current_month]
            previous_amount = monthly_totals[previous_month]
            mom_growth = ((current_amount - previous_amount) / previous_amount * 100) if previous_amount > 0 else 0.0

        response = {
            'total': float(total),
            'months': len(months),
            'days': total_days,  # Added total_days to response
            'max': {
                'amount': float(max_amount) if max_month else 0.0,
                'month': max_month_name
            },
            'min': {
                'amount': float(min_amount) if min_month else 0.0,
                'month': min_month_name
            },
            'average': avg_income,
            'avg_daily': avg_daily_income,
            'yoy_growth': float(yoy_growth),
            'mom_growth': float(mom_growth),
            'by_source': {k: float(v) for k, v in by_source.items()},
            'by_month': {k: float(v) for k, v in monthly_totals.items()},
            'by_year': {k: float(v) for k, v in yearly_totals.items()}
        }

        logger.debug(f"Income summary:duration={duration_str}, total={total}, months={len(months)}, days={total_days}, max_month={max_month_name}, min_month={min_month_name}, avg_daily={avg_daily_income}")
        return jsonify(response)
    except Exception as e:
        logger.error(f"Error in api_summary: {str(e)}")
        return jsonify({'error': str(e)}), 500
