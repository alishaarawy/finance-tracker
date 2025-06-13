
from src.models import db
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

class RecurringExpense(db.Model):
    __tablename__ = 'recurring_expenses'
    id = db.Column(db.Integer, primary_key=True)
    item = db.Column(db.String(100), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    category_id = db.Column(db.Integer, db.ForeignKey('expense_category.id'), nullable=False)  # Add ForeignKey
    recurrence_day = db.Column(db.Integer, nullable=False)  # Day of the month (1-31)
    spontaneous = db.Column(db.Boolean, default=False)
    description = db.Column(db.Text)
    category = db.relationship('ExpenseCategory', backref='recurring_expenses', lazy=True)
class Income(db.Model):
    __tablename__ = 'income'
    id = db.Column(db.Integer, primary_key=True)
    amount = db.Column(db.Float, nullable=False)
    return_amount = db.Column(db.Float, nullable=False)
    date = db.Column(db.Date, nullable=False)
    source = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    sell_transaction_id = db.Column(db.Integer)  # Links to sell transactions (e.g., gold, stocks)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class Expense(db.Model):
    __tablename__ = 'expense'
    id = db.Column(db.Integer, primary_key=True)
    amount = db.Column(db.Float, nullable=False)
    date = db.Column(db.Date, nullable=False)
    category_id = db.Column(db.Integer, db.ForeignKey('expense_category.id'), nullable=False)
    description = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    category = db.relationship('ExpenseCategory', backref='expenses')
    quantity=db.Column(db.Float, nullable=False)
    item=db.Column(db.Text)
    subcategory=db.Column(db.Text)
    unit=db.Column(db.Text)
class ExpenseCategory(db.Model):
    __tablename__ = 'expense_category'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False, unique=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class GoldTransaction(db.Model):
    __tablename__ = 'gold_transaction'
    id = db.Column(db.Integer, primary_key=True)
    karat = db.Column(db.Integer, nullable=False)
    weight = db.Column(db.Float, nullable=False)
    purchase_price = db.Column(db.Float, nullable=False)
    date = db.Column(db.Date, nullable=False)
    description = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class GoldSellTransaction(db.Model):
    __tablename__ = 'gold_sell_transaction'
    id = db.Column(db.Integer, primary_key=True)
    karat = db.Column(db.Integer, nullable=False)
    weight = db.Column(db.Float, nullable=False)
    sell_price = db.Column(db.Float, nullable=False)
    date = db.Column(db.Date, nullable=False)
    description = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class GoldPrice(db.Model):
    __tablename__ = 'gold_price'
    id = db.Column(db.Integer, primary_key=True)
    price_type = db.Column(db.String)
    price_24k = db.Column(db.Float)
    price_21k = db.Column(db.Float)
    price_18k = db.Column(db.Float)
    price_pound = db.Column(db.Float)
    date = db.Column(db.Date, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class ExchangeRate(db.Model):
    __tablename__ = 'exchange_rate'
    id = db.Column(db.Integer, primary_key=True)
    currency = db.Column(db.String(3), nullable=False)
    rate = db.Column(db.Float, nullable=False)
    date = db.Column(db.Date, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class Inflation(db.Model):
    __tablename__ = 'inflation'
    id = db.Column(db.Integer, primary_key=True)
    country = db.Column(db.String(3), nullable=False)
    category = db.Column(db.String(100), nullable=False)
    rate = db.Column(db.Float)
    yearly_rate = db.Column(db.Float)
    date = db.Column(db.Date, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class Savings(db.Model):
    __tablename__ = 'saving'
    id = db.Column(db.Integer, primary_key=True)
    amount = db.Column(db.Float, nullable=False)
    date = db.Column(db.Date, nullable=False)
    goal_id = db.Column(db.Integer, db.ForeignKey('savings_goal.id'))
    description = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    goal = db.relationship('SavingsGoal', back_populates='savings_entries', lazy=True)

class SavingsGoal(db.Model):
    __tablename__ = 'savings_goal'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    target_amount = db.Column(db.Float, nullable=False)
    duration = db.Column(db.Integer, nullable=False)  # Duration in months
    savings_percentage = db.Column(db.Float, nullable=False)  # Percentage of last income
    monthly_savings = db.Column(db.Float, nullable=False)
    description = db.Column(db.Text)
    target_date = db.Column(db.Date)  # Optional target date
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    savings_entries = db.relationship('Savings', back_populates='goal', lazy=True)

class StockTransaction(db.Model):
    __tablename__ = 'stock_transaction'
    id = db.Column(db.Integer, primary_key=True)
    ticker = db.Column(db.String(10), nullable=False)
    quantity = db.Column(db.Float, nullable=False)
    purchase_price = db.Column(db.Float, nullable=False)
    date = db.Column(db.Date, nullable=False)
    description = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class StockSellTransaction(db.Model):
    __tablename__ = 'stock_sell_transaction'
    id = db.Column(db.Integer, primary_key=True)
    ticker = db.Column(db.String(10), nullable=False)
    quantity = db.Column(db.Float, nullable=False)
    sell_price = db.Column(db.Float, nullable=False)
    date = db.Column(db.Date, nullable=False)
    description = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class MutualFundTransaction(db.Model):
    __tablename__ = 'mutual_fund_transaction'
    id = db.Column(db.Integer, primary_key=True)
    fund_name = db.Column(db.String(100), nullable=False)
    units = db.Column(db.Float, nullable=False)
    purchase_nav = db.Column(db.Float, nullable=False)
    date = db.Column(db.Date, nullable=False)
    description = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class MutualFundSellTransaction(db.Model):
    __tablename__ = 'mutual_fund_sell_transaction'
    id = db.Column(db.Integer, primary_key=True)
    fund_name = db.Column(db.String(100), nullable=False)
    units = db.Column(db.Float, nullable=False)
    sell_nav = db.Column(db.Float, nullable=False)
    date = db.Column(db.Date, nullable=False)
    description = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class StockPrice(db.Model):
    __tablename__ = 'stock_price'
    id = db.Column(db.Integer, primary_key=True)
    ticker = db.Column(db.String(10), nullable=False)
    price = db.Column(db.Float, nullable=False)
    date = db.Column(db.Date, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class MutualFundNAV(db.Model):
    __tablename__ = 'mutual_fund_nav'
    id = db.Column(db.Integer, primary_key=True)
    fund_name = db.Column(db.String(100), nullable=False)
    nav = db.Column(db.Float, nullable=False)
    date = db.Column(db.Date, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
