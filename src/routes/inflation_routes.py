from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from src.models import db, Inflation
from datetime import datetime
from sqlalchemy import func

inflation_bp = Blueprint('inflation', __name__, url_prefix='/inflation', template_folder='../../templates/inflation')

@inflation_bp.route('/')
def index():
    return render_template('inflation/index.html')

@inflation_bp.route('/add', methods=['GET', 'POST'])
def add():
    if request.method == 'POST':
        try:
            date = datetime.strptime(request.form['date'], '%Y-%m-%d').date()
            category = request.form['category'].strip().lower()
            cpi_value = float(request.form['cpi_value'])
            country = request.form.get('country', 'Egypt').strip().upper()  # Standardize to 'EGY'
            rate = float(request.form.get('rate', 0))
            yearly_rate = float(request.form.get('yearly_rate', 0))

            # Check for duplicates
            existing = Inflation.query.filter_by(date=date, category=category, country=country).first()
            if existing:
                flash('Duplicate inflation data for this date, category, and country.', 'error')
                return redirect(url_for('inflation.add'))

            inflation = Inflation(
                date=date,
                category=category,
                cpi_value=cpi_value,
                country=country,
                rate=rate,
                yearly_rate=yearly_rate
            )
            db.session.add(inflation)
            db.session.commit()
            flash('Inflation data added successfully!', 'success')
            return redirect(url_for('inflation.index'))
        except Exception as e:
            flash(f'Error adding inflation data: {str(e)}', 'error')
    return render_template('add.html')

@inflation_bp.route('/edit/<int:id>', methods=['GET', 'POST'])
def edit(id):
    inflation = Inflation.query.get_or_404(id)
    if request.method == 'POST':
        try:
            date = datetime.strptime(request.form['date'], '%Y-%m-%d').date()
            category = request.form['category'].strip().lower()
            cpi_value = float(request.form['cpi_value'])
            country = request.form.get('country', 'Egypt').strip().upper()  # Standardize to 'EGY'
            rate = float(request.form.get('rate', 0))
            yearly_rate = float(request.form.get('yearly_rate', 0))

            # Check for duplicates (excluding current record)
            existing = Inflation.query.filter_by(date=date, category=category, country=country).filter(Inflation.id != id).first()
            if existing:
                flash('Duplicate inflation data for this date, category, and country.', 'error')
                return redirect(url_for('inflation.edit', id=id))

            inflation.date = date
            inflation.category = category
            inflation.cpi_value = cpi_value
            inflation.country = country
            inflation.rate = rate
            inflation.yearly_rate = yearly_rate
            db.session.commit()
            flash('Inflation data updated successfully!', 'success')
            return redirect(url_for('inflation.index'))
        except Exception as e:
            flash(f'Error updating inflation data: {str(e)}', 'error')
    return render_template('edit.html', inflation=inflation)

@inflation_bp.route('/delete/<int:id>', methods=['POST'])
def delete(id):
    inflation = Inflation.query.get_or_404(id)
    try:
        db.session.delete(inflation)
        db.session.commit()
        flash('Inflation data deleted successfully!', 'success')
    except Exception as e:
        flash(f'Error deleting inflation data: {str(e)}', 'error')
    return redirect(url_for('inflation.index'))

@inflation_bp.route('/api/list', methods=['GET'])
def api_list():
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    query = Inflation.query
    
    if start_date and end_date:
        try:
            start_date = datetime.strptime(start_date, '%Y-%m-%d').date()
            end_date = datetime.strptime(end_date, '%Y-%m-%d').date()
            query = query.filter(Inflation.date >= start_date, Inflation.date <= end_date)
        except ValueError:
            pass

    inflations = query.order_by(Inflation.date.desc()).distinct().all()
    return jsonify([{
        'id': i.id,
        'date': i.date.strftime('%Y-%m-%d'),
        'category': i.category,
        'rate': float(i.rate) if i.rate is not None else None,
        'yearly_rate': float(i.yearly_rate) if i.yearly_rate is not None else None,
        'cpi_value': float(i.cpi_value) if i.cpi_value is not None else None,
        'country': i.country or 'N/A'
    } for i in inflations])

@inflation_bp.route('/api/summary', methods=['GET'])
def api_summary():
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    
    query = Inflation.query.filter(func.lower(Inflation.country).in_(['egypt', 'egy']))
    if start_date and end_date:
        try:
            start_date = datetime.strptime(start_date, '%Y-%m-%d').date()
            end_date = datetime.strptime(end_date, '%Y-%m-%d').date()
            query = query.filter(Inflation.date >= start_date, Inflation.date <= end_date)
        except ValueError:
            start_date = None
            end_date = None
    
    latest_egypt_all = query.filter(Inflation.category == 'all').order_by(Inflation.date.desc()).distinct().first()
    latest_egypt_food = query.filter(Inflation.category == 'food').order_by(Inflation.date.desc()).distinct().first()
    
    # Calculate cumulative inflation using CPI
    cpi_query = query.filter(Inflation.category.in_(['all', 'food']), Inflation.cpi_value.isnot(None))
    cpi_data = cpi_query.order_by(Inflation.date).distinct().all()
    
    cumulative_egypt_all = None
    cumulative_egypt_food = None
    
    all_cpi = [r for r in cpi_data if r.category == 'all']
    food_cpi = [r for r in cpi_data if r.category == 'food']
    
    if all_cpi and len(all_cpi) >= 2:
        cpi_start = all_cpi[0].cpi_value
        cpi_end = all_cpi[-1].cpi_value
        cumulative_egypt_all = ((cpi_end - cpi_start) / cpi_start * 100) if cpi_start != 0 else 0.0
    
    if food_cpi and len(food_cpi) >= 2:
        cpi_start = food_cpi[0].cpi_value
        cpi_end = food_cpi[-1].cpi_value
        cumulative_egypt_food = ((cpi_end - cpi_start) / cpi_start * 100) if cpi_start != 0 else 0.0
    
    chart_data = {
        'egypt_all': [],
        'egypt_food': []
    }
    yearly_changes = {
        'egypt_all': [],
        'egypt_food': []
    }
    
    all_inflations = query.filter(Inflation.category.in_(['all', 'food'])).order_by(Inflation.date).distinct().all()
    
    for record in all_inflations:
        entry = {
            'date': record.date.strftime('%Y-%m-%d'),
            'rate': float(record.rate) if record.rate is not None else None,
            'cpi_value': float(record.cpi_value) if record.cpi_value is not None else None
        }
        if record.category == 'all':
            chart_data['egypt_all'].append(entry)
            if record.yearly_rate is not None:
                yearly_changes['egypt_all'].append({
                    'date': record.date.strftime('%Y-%m-%d'),
                    'yearly_rate': float(record.yearly_rate)
                })
        elif record.category == 'food':
            chart_data['egypt_food'].append(entry)
            if record.yearly_rate is not None:
                yearly_changes['egypt_food'].append({
                    'date': record.date.strftime('%Y-%m-%d'),
                    'yearly_rate': float(record.yearly_rate)
                })
    
    response = {
        'latest': {
            'egypt_all': {
                'month_to_month_rate': float(latest_egypt_all.rate) if latest_egypt_all and latest_egypt_all.rate is not None else None,
                'year_to_year_rate': float(latest_egypt_all.yearly_rate) if latest_egypt_all and latest_egypt_all.yearly_rate is not None else None,
                'date': latest_egypt_all.date.strftime('%Y-%m-%d') if latest_egypt_all else None,
                'cpi_value': float(latest_egypt_all.cpi_value) if latest_egypt_all and latest_egypt_all.cpi_value is not None else None
            },
            'egypt_food': {
                'month_to_month_rate': None,
                'year_to_year_rate': None,
                'date': None,
                'cpi_value': None,
                'message': 'No data available for food category'
            } if not latest_egypt_food else {
                'month_to_month_rate': float(latest_egypt_food.rate) if latest_egypt_food.rate is not None else None,
                'year_to_year_rate': float(latest_egypt_food.yearly_rate) if latest_egypt_food.yearly_rate is not None else None,
                'date': latest_egypt_food.date.strftime('%Y-%m-%d') if latest_egypt_food else None,
                'cpi_value': float(latest_egypt_food.cpi_value) if latest_egypt_food.cpi_value is not None else None
            }
        },
        'cumulative': {
            'egypt_all': float(cumulative_egypt_all) if cumulative_egypt_all is not None else None,
            'egypt_food': None if not food_cpi else float(cumulative_egypt_food)
        },
        'chart_data': chart_data,
        'yearly_changes': yearly_changes,
        'start_date': start_date.strftime('%Y-%m-%d') if start_date else None,
        'end_date': end_date.strftime('%Y-%m-%d') if end_date else None
    }
    
    return jsonify(response)
