from flask import Blueprint, render_template, request, redirect, url_for, flash
from werkzeug.utils import secure_filename
import os
import pandas as pd
from datetime import datetime, timedelta
import tempfile
import shutil
from src.models import db, Income, ExpenseCategory, Expense, GoldTransaction, GoldPrice, ExchangeRate, Inflation, SavingsGoal, Savings

import_bp = Blueprint('import', __name__, url_prefix='/import')

@import_bp.route('/')
def index():
    return render_template('import.html')

@import_bp.route('/excel', methods=['POST'])
def import_excel():
    if 'file' not in request.files:
        flash('No file part in the request', 'error')
        return redirect(url_for('import.index'))

    file = request.files['file']
    if file.filename == '':
        flash('No file selected', 'error')
        return redirect(url_for('import.index'))

    if not file.filename.endswith('.xlsx'):
        flash('File must be an Excel (.xlsx) file', 'error')
        return redirect(url_for('import.index'))

    temp_dir = tempfile.mkdtemp()
    temp_path = os.path.join(temp_dir, secure_filename('temp_excel.xlsx'))

    try:
        file.save(temp_path)
        result = process_excel_file(temp_path)
        flash(f"Imported: {result['imported']}", 'success')
        if result['errors']:
            for error in result['errors']:
                flash(error, 'error')
        return redirect(url_for('import.index'))
    except Exception as e:
        flash(f'Error processing file: {str(e)}', 'error')
        return redirect(url_for('import.index'))
    finally:
        try:
            if os.path.exists(temp_path):
                os.remove(temp_path)
            if os.path.exists(temp_dir):
                shutil.rmtree(temp_dir)
        except Exception as e:
            print(f"Error cleaning up temporary files: {str(e)}")

def process_excel_file(file_path):
    result = {'imported': {}, 'errors': []}
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"File not found: {file_path}")

    try:
        df_dict = pd.read_excel(file_path, sheet_name=None)
        sheet_names = df_dict.keys()
    except Exception as e:
        raise Exception(f"Error reading Excel file: {str(e)}")

    for sheet_name in sheet_names:
        sheet_name_lower = sheet_name.lower()
        df = df_dict[sheet_name]
        try:
            if df.empty:
                result['errors'].append(f"Sheet '{sheet_name}' is empty")
                continue
            if 'income' in sheet_name_lower:
                count = import_income(df)
                result['imported']['income'] = count
            elif 'expense' in sheet_name_lower:
                count = import_expenses(df)
                result['imported']['expenses'] = count
            elif 'gold_prices' in sheet_name_lower:
                count = import_gold_prices(df)
                result['imported']['gold_prices'] = count
            elif 'gold' in sheet_name_lower:
                count = import_gold(df)
                result['imported']['gold'] = count
            elif 'exchange' in sheet_name_lower:
                count = import_exchange_rates(df)
                result['imported']['exchange_rates'] = count
            elif 'inflation' in sheet_name_lower:
                count = import_inflation(df)
                result['imported']['inflation'] = count
            elif 'saving' in sheet_name_lower:
                count = import_savings(df)
                result['imported']['savings'] = count
            else:
                result['errors'].append(f"Unknown sheet '{sheet_name}'")
        except Exception as e:
            result['errors'].append(f"Error processing sheet '{sheet_name}': {str(e)}")
    return result

def parse_date(date_val):
    if pd.isna(date_val):
        return None
    if isinstance(date_val, datetime):
        return date_val.date()
    formats = [
        '%Y-%m-%d', '%m-%d-%Y', '%m/%d/%Y', '%d-%m-%Y', '%d/%m/%Y',
        '%Y/%m/%d', '%d.%m.%Y', '%m.%d.%Y', '%Y%m%d'
    ]
    date_str = str(date_val)
    for fmt in formats:
        try:
            return datetime.strptime(date_str, fmt).date()
        except ValueError:
            continue
    raise ValueError(f"Could not parse date: {date_str}")

def import_income(df):
    required_columns = ['amount', 'date', 'source']
    for col in required_columns:
        if col not in df.columns:
            raise ValueError(f"Missing required column: {col}")
    count = 0
    for index, row in df.iterrows():
        try:
            if pd.isna(row['amount']) or pd.isna(row['date']) or pd.isna(row['source']):
                continue
            date = parse_date(row['date'])
            income = Income(
                amount=float(row['amount']),
                return_amount=float(row['return_amount']) if 'return_amount' in row and not pd.isna(row['return_amount']) else 0.0,  # Provide default value
                date=date,
                source=str(row['source']),
                description=str(row['description']) if 'description' in row and not pd.isna(row['description']) else None
            )
            db.session.add(income)
            count += 1
        except Exception as e:
            print(f"Error importing income row {index + 2}: {str(e)}")
    db.session.commit()
    return count

def import_expenses(df):
    required_columns = ['amount', 'date', 'category']
    for col in required_columns:
        if col.lower() not in [c.lower() for c in df.columns]:
            raise ValueError(f"Missing required column: {col}")
    count = 0
    batch_size = 1000
    batch = []
    for index, row in df.iterrows():
        try:
            if pd.isna(row['amount']) or pd.isna(row['date']) or pd.isna(row['category']):
                continue
            date = parse_date(row['date'])
            amount = float(row['amount'])
            category_name = str(row['category']).strip()
            category = ExpenseCategory.query.filter_by(name=category_name).first()
            if not category:
                category = ExpenseCategory(name=category_name)
                db.session.add(category)
                db.session.flush()
            quantity = row.get('quantity', None)
            if pd.isna(quantity) or quantity == '':
                quantity = None
            else:
                quantity = float(quantity)
            unit = None
            
            expense = Expense(
                date=date,
                amount=amount,
                category_id=category.id,
                description=str(row.get('description', '')),
                item=str(row.get('item', '')) if pd.notna(row.get('item', '')) else None,
                quantity=quantity,
                unit=unit,
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow()
            )
            batch.append(expense)
            count += 1
            if len(batch) >= batch_size:
                db.session.bulk_save_objects(batch)
                db.session.commit()
                batch = []
        except Exception as e:
            print(f"Error importing expense row {index + 2}: {str(e)}")
    if batch:
        db.session.bulk_save_objects(batch)
        db.session.commit()
    return count

def import_gold(df):
    required_columns = ['weight', 'karat', 'purchase_price', 'date']
    for col in required_columns:
        if col not in df.columns:
            raise ValueError(f"Missing required column: {col}")
    count = 0
    for index, row in df.iterrows():
        try:
            if pd.isna(row['weight']) or pd.isna(row['karat']) or pd.isna(row['purchase_price']) or pd.isna(row['date']):
                continue
            date = parse_date(row['date'])
            transaction = GoldTransaction(
                weight=float(row['weight']),
                karat=int(row['karat']),
                purchase_price=float(row['purchase_price']),
                date=date,
                description=str(row['description']) if 'description' in row and not pd.isna(row['description']) else None
            )
            db.session.add(transaction)
            count += 1
        except Exception as e:
            print(f"Error importing gold transaction row {index + 2}: {str(e)}")
    db.session.commit()
    return count

def import_gold_prices(df):
    required_columns = ['date', 'price_type', 'price_24k']
    for col in required_columns:
        if col not in df.columns:
            raise ValueError(f"Missing required column: {col}")
    count = 0
    for index, row in df.iterrows():
        try:
            if pd.isna(row['date']) or pd.isna(row['price_type']) or pd.isna(row['price_24k']):
                continue
            date = parse_date(row['date'])
            price_type = str(row['price_type']).lower()
            if price_type not in ['local', 'global']:
                raise ValueError(f"Invalid price_type: {price_type}. Must be 'local' or 'global'")
            price_24k = float(row['price_24k'])
            price_21k = (21/24) * price_24k
            price_18k = (18/24) * price_24k
            price_pound = price_21k * 8 if price_type == 'local' else None
            
            if price_type == 'local':
                price_21k = float(row.get('price_21k', price_21k)) if pd.notna(row.get('price_21k')) else price_21k
                price_18k = float(row.get('price_18k', price_18k)) if pd.notna(row.get('price_18k')) else price_18k
                price_pound = float(row.get('price_pound', price_pound)) if pd.notna(row.get('price_pound')) else price_pound
            
            price = GoldPrice(
                price_type=price_type,
                price_24k=price_24k,
                price_21k=price_21k,
                price_18k=price_18k,
                price_pound=price_pound,
                date=date
            )
            db.session.add(price)
            count += 1
        except Exception as e:
            print(f"Error importing gold price row {index + 2}: {str(e)}")
    db.session.commit()
    return count

def import_exchange_rates(df):
    required_columns = ['date', 'rate']
    for col in required_columns:
        if col not in df.columns:
            raise ValueError(f"Missing required column: {col}")
    count = 0
    for index, row in df.iterrows():
        try:
            if pd.isna(row['date']) or pd.isna(row['rate']):
                continue
            date = parse_date(row['date'])
            exchange_rate = ExchangeRate(
                rate=float(row['rate']),
                date=date
            )
            db.session.add(exchange_rate)
            count += 1
        except Exception as e:
            print(f"Error importing exchange rate row {index + 2}: {str(e)}")
    db.session.commit()
    return count

def import_inflation(df):
    required_columns = ['date', 'cpi_value', 'category']
    for col in required_columns:
        if col not in df.columns:
            raise ValueError(f"Missing required column: {col}")
    df = df.sort_values(by='date')
    count = 0
    for index, row in df.iterrows():
        try:
            if pd.isna(row['date']) or pd.isna(row['cpi_value']) or pd.isna(row['category']):
                continue
            date = parse_date(row['date'])
            cpi_value = float(row['cpi_value'])
            category = str(row['category']).lower()
            country = str(row['country']) if 'country' in row and not pd.isna(row['country']) else None
            month_to_month_rate = 0.0
            yearly_rate = 0.0
            prev_inflation_month = Inflation.query.filter(
                Inflation.category == category,
                Inflation.country == country,
                Inflation.date < date
            ).order_by(Inflation.date.desc()).first()
            if prev_inflation_month and prev_inflation_month.cpi_value is not None and prev_inflation_month.cpi_value > 0:
                month_to_month_rate = ((cpi_value - prev_inflation_month.cpi_value) / prev_inflation_month.cpi_value) * 100
            one_year_prior = date - timedelta(days=365)
            prev_inflation_year = Inflation.query.filter(
                Inflation.category == category,
                Inflation.country == country,
                Inflation.date <= one_year_prior
            ).order_by(Inflation.date.desc()).first()
            if prev_inflation_year and prev_inflation_year.cpi_value is not None and prev_inflation_year.cpi_value > 0:
                yearly_rate = ((cpi_value - prev_inflation_year.cpi_value) / prev_inflation_year.cpi_value) * 100
            inflation = Inflation(
                rate=month_to_month_rate,
                yearly_rate=yearly_rate,
                category=category,
                date=date,
                cpi_value=cpi_value,
                country=country
            )
            db.session.add(inflation)
            count += 1
        except Exception as e:
            print(f"Error importing inflation row {index + 2}: {str(e)}")
    db.session.commit()
    return count

