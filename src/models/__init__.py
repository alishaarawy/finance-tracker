from flask import Flask
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()

def create_app():
    app = Flask(__name__)
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///finance_tracker.db'
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    db.init_app(app)

    # Register blueprints
    from src.routes import import_routes, inflation_routes
    app.register_blueprint(import_routes.import_bp)
    app.register_blueprint(inflation_routes.inflation_bp)


    # Register format_currency with Jinja2
    app.jinja_env.globals['format_currency'] = format_currency



    return app
# Import all models to make them available when importing from src.models
from src.models.models import (
    Income, ExpenseCategory, Expense, GoldTransaction, GoldSellTransaction, 
    GoldPrice, ExchangeRate, Inflation, SavingsGoal, Savings, StockTransaction, 
    StockSellTransaction, MutualFundTransaction, MutualFundSellTransaction,RecurringExpense, 
    StockPrice, MutualFundNAV
)

# Re-export all models
__all__ = [
    'db', 'create_app', 'Income', 'ExpenseCategory', 'Expense', 'GoldTransaction', 
    'GoldPrice', 'ExchangeRate', 'Inflation', 'SavingsGoal', 'Savings', 
    'StockTransaction', 'StockSellTransaction', 'MutualFundTransaction', 
    'MutualFundSellTransaction', 'StockPrice', 'MutualFundNAV'
]
