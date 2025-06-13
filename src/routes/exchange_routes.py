from flask import Blueprint, render_template, request, redirect, url_for, jsonify
from src.models import db
from src.models.models import ExchangeRate
from datetime import datetime

exchange_bp = Blueprint('exchange', __name__, url_prefix='/exchange')

@exchange_bp.route('/', methods=['GET'])
def index():
    return render_template('exchange/index.html')

@exchange_bp.route('/add', methods=['GET', 'POST'])
def add():
    if request.method == 'POST':
        rate = float(request.form['rate'])
        date_str = request.form['date']
        
        date = datetime.strptime(date_str, '%Y-%m-%d').date()
        
        # Check if there's already a rate for this date
        existing = ExchangeRate.query.filter_by(date=date).first()
        if existing:
            existing.rate = rate
        else:
            exchange_rate = ExchangeRate(
                rate=rate,
                date=date
            )
            db.session.add(exchange_rate)
        
        db.session.commit()
        
        return redirect(url_for('exchange.index'))
    
    return render_template('exchange/add.html')

@exchange_bp.route('/edit/<int:id>', methods=['GET', 'POST'])
def edit(id):
    exchange_rate = ExchangeRate.query.get_or_404(id)
    
    if request.method == 'POST':
        exchange_rate.rate = float(request.form['rate'])
        exchange_rate.date = datetime.strptime(request.form['date'], '%Y-%m-%d').date()
        
        db.session.commit()
        
        return redirect(url_for('exchange.index'))
    
    return render_template('exchange/edit.html', exchange_rate=exchange_rate)

@exchange_bp.route('/delete/<int:id>', methods=['POST'])
def delete(id):
    exchange_rate = ExchangeRate.query.get_or_404(id)
    db.session.delete(exchange_rate)
    db.session.commit()
    
    return redirect(url_for('exchange.index'))

@exchange_bp.route('/api/list')
def api_list():
    # Get date range filter
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    
    if start_date:
        start_date = datetime.strptime(start_date, '%Y-%m-%d').date()
    else:
        # Default to beginning of current year
        start_date = datetime(datetime.now().year, 1, 1).date()
    
    if end_date:
        end_date = datetime.strptime(end_date, '%Y-%m-%d').date()
    else:
        # Default to today
        end_date = datetime.now().date()
    
    rates = ExchangeRate.query.filter(
        ExchangeRate.date >= start_date,
        ExchangeRate.date <= end_date
    ).order_by(ExchangeRate.date).all()
    
    result = []
    for rate in rates:
        result.append({
            'id': rate.id,
            'rate': rate.rate,
            'date': rate.date.strftime('%Y-%m-%d')
        })
    
    return jsonify(result)

@exchange_bp.route('/api/latest')
def api_latest():
    # Get latest exchange rate
    latest = ExchangeRate.query.order_by(ExchangeRate.date.desc()).first()
    
    if latest:
        result = {
            'id': latest.id,
            'rate': latest.rate,
            'date': latest.date.strftime('%Y-%m-%d')
        }
    else:
        result = {
            'rate': 0,
            'date': None
        }
    
    return jsonify(result)

@exchange_bp.route('/api/summary')
def api_summary():
    # Get date range filter
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    
    if start_date:
        start_date = datetime.strptime(start_date, '%Y-%m-%d').date()
    else:
        # Default to beginning of current year
        start_date = datetime(datetime.now().year, 1, 1).date()
    
    if end_date:
        end_date = datetime.strptime(end_date, '%Y-%m-%d').date()
    else:
        # Default to today
        end_date = datetime.now().date()
    
    rates = ExchangeRate.query.filter(
        ExchangeRate.date >= start_date,
        ExchangeRate.date <= end_date
    ).order_by(ExchangeRate.date).all()
    
    # Get latest exchange rate
    latest = ExchangeRate.query.order_by(ExchangeRate.date.desc()).first()
    
    # Calculate statistics
    if rates:
        avg_rate = sum(r.rate for r in rates) / len(rates)
        min_rate = min(r.rate for r in rates)
        max_rate = max(r.rate for r in rates)
        
        # Calculate volatility (standard deviation)
        mean = avg_rate
        variance = sum((r.rate - mean) ** 2 for r in rates) / len(rates)
        volatility = variance ** 0.5
        
        # Calculate change over period
        first_rate = rates[0].rate
        last_rate = rates[-1].rate
        change = last_rate - first_rate
        change_percent = (change / first_rate) * 100 if first_rate > 0 else 0
    else:
        avg_rate = 0
        min_rate = 0
        max_rate = 0
        volatility = 0
        change = 0
        change_percent = 0
    
    # Format data for charts
    chart_data = [{'date': r.date.strftime('%Y-%m-%d'), 'rate': r.rate} for r in rates]
    
    return jsonify({
        'latest': {
            'rate': latest.rate if latest else 0,
            'date': latest.date.strftime('%Y-%m-%d') if latest else None
        },
        'statistics': {
            'average': avg_rate,
            'minimum': min_rate,
            'maximum': max_rate,
            'volatility': volatility,
            'change': change,
            'change_percent': change_percent
        },
        'chart_data': chart_data
    })
