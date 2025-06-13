from alembic import op
import sqlalchemy as sa
from datetime import datetime
from src.models import db, Income

def upgrade():
    # Create a new table with the updated schema
    op.create_table(
        'savings_goal_new',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('name', sa.String(length=100), nullable=False),
        sa.Column('target_amount', sa.Float(), nullable=False),
        sa.Column('duration', sa.Integer(), nullable=False, default=12),
        sa.Column('savings_percentage', sa.Float(), nullable=False, default=0.0),
        sa.Column('monthly_savings', sa.Float(), nullable=False, default=0.0),
        sa.Column('target_date', sa.Date(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, default=datetime.utcnow),
        sa.Column('updated_at', sa.DateTime(), nullable=False, default=datetime.utcnow)
    )

    # Copy data from old table to new table, calculating new fields
    op.execute('''
        INSERT INTO savings_goal_new (id, name, target_amount, target_date, created_at, updated_at, duration, savings_percentage, monthly_savings)
        SELECT id, name, target_amount, target_date, created_at, updated_at, 12, 0.0, 
               CASE 
                   WHEN target_amount > 0 THEN target_amount / 12
                   ELSE 0.0 
               END
        FROM savings_goal
    ''')

    # Drop the old table
    op.drop_table('savings_goal')

    # Rename the new table to savings_goal
    op.rename_table('savings_goal_new', 'savings_goal')

    # Update monthly_savings based on last income
    bind = op.get_bind()
    session = sa.orm.Session(bind=bind)
    last_income = session.query(Income).order_by(Income.date.desc()).first()
    income_amount = last_income.amount if last_income else 0.0
    goals = session.execute(sa.text('SELECT id, savings_percentage, target_amount, duration FROM savings_goal')).fetchall()
    for goal in goals:
        goal_id, savings_percentage, target_amount, duration = goal
        monthly_savings = income_amount * (savings_percentage / 100) if savings_percentage > 0 else target_amount / duration
        op.execute(
            sa.text('UPDATE savings_goal SET monthly_savings = :monthly_savings WHERE id = :id')
            .params(monthly_savings=monthly_savings, id=goal_id)
        )
    session.commit()

def downgrade():
    # Create the old table schema
    op.create_table(
        'savings_goal_old',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('name', sa.String(length=100), nullable=False),
        sa.Column('target_amount', sa.Float(), nullable=False),
        sa.Column('current_amount', sa.Float(), nullable=False, default=0.0),
        sa.Column('target_date', sa.Date(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, default=datetime.utcnow),
        sa.Column('updated_at', sa.DateTime(), nullable=False, default=datetime.utcnow)
    )

    # Copy data back, recalculating current_amount from savings
    op.execute('''
        INSERT INTO savings_goal_old (id, name, target_amount, current_amount, target_date, created_at, updated_at)
        SELECT sg.id, sg.name, sg.target_amount, 
               COALESCE((SELECT SUM(s.amount) FROM saving s WHERE s.goal_id = sg.id), 0.0),
               sg.target_date, sg.created_at, sg.updated_at
        FROM savings_goal sg
    ''')

    # Drop the new table
    op.drop_table('savings_goal')

    # Rename the old table to savings_goal
    op.rename_table('savings_goal_old', 'savings_goal')