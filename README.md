# Personal Finance Tracker

A comprehensive web-based application for tracking and analyzing your personal finances, including income, expenses, gold investments, exchange rates, inflation, and savings goals.

## Features

- **Income Tracking**: Monitor your salary and income from various sources
- **Expense Tracking**: Track expenses across multiple categories
- **Gold Investment Analysis**: Track gold purchases and calculate returns based on current prices
- **Exchange Rate Monitoring**: Track EGP/USD exchange rates over time
- **Inflation Analysis**: Monitor monthly inflation rates for food and all items
- **Savings Goals**: Set and track progress toward savings targets
- **Date Range Filtering**: Filter all analyses by custom date ranges
- **Excel Data Import**: Import your existing financial data from Excel spreadsheets

## Getting Started

### Prerequisites

- Python 3.11+
- Virtual environment (venv)
- Required Python packages (installed automatically)

### Installation

1. Clone the repository or download the source code
2. Navigate to the project directory
3. Set up a virtual environment:
   ```
   python3.11 -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```
4. Install dependencies:
   ```
   pip install flask flask-sqlalchemy pandas matplotlib plotly openpyxl
   ```

### Running the Application

1. Activate the virtual environment if not already activated:
   ```
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```
2. Start the application:
   ```
   cd src
   python -m main
   ```
3. Open your web browser and navigate to:
   ```
   http://localhost:5000
   ```

## Importing Your Data

You can import your existing financial data from an Excel file. The Excel file should contain separate sheets for each data type:

1. **Income**: Columns should include `amount`, `date`, `source`, and optionally `description`
2. **Expenses**: Columns should include `amount`, `date`, `category`, and optionally `description`
3. **Gold**: Columns should include `weight`, `karat`, `purchase_price`, `date`, and optionally `description`
4. **Exchange Rates**: Columns should include `date` and `rate`
5. **Inflation**: Columns should include `date`, `rate`, and `category` (either 'food' or 'all')
6. **Savings**: Columns should include `amount`, `date`, `goal`, and optionally `description`, `target_amount`, and `target_date`

To import your data:
1. Navigate to the "Import Data" page from the navigation menu
2. Upload your Excel file
3. Review the import summary

## Usage Guide

### Dashboard

The dashboard provides an overview of your financial situation, including:
- Total income and expenses
- Income by source and expenses by category
- Income and expense trends over time
- Gold investment summary
- Inflation rates
- Savings goals progress

### Date Range Filtering

All analyses can be filtered by date range:
1. Use the date range filter at the top of each page
2. Select start and end dates
3. Click "Apply Filter" to update the data

### Income Management

- View income summary and details
- Add new income entries
- Edit or delete existing entries

### Expense Management

- View expense summary by category
- Add new expense entries
- Manage expense categories
- Edit or delete existing entries

### Gold Investment Tracking

- Record gold purchases with weight, karat, and price
- Track local and global gold prices
- View investment returns based on current prices

### Exchange Rate Monitoring

- Record daily EGP/USD exchange rates
- View exchange rate trends over time

### Inflation Tracking

- Record monthly inflation rates for food and all items
- View inflation trends over time

### Savings Goals

- Create savings goals with target amounts and dates
- Track progress toward goals
- Record savings contributions

## Project Structure

- `src/main.py`: Main application entry point
- `src/models/`: Database models
- `src/routes/`: Route handlers for each feature
- `src/static/`: Static assets (CSS, JavaScript)
- `src/templates/`: HTML templates
