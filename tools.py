def calculate_new_regime_tax(income):
    # Standard Deduction
    income = max(0, income - 75000)
    
    # 87A Rebate check (Income <= 12L is tax free)
    if income <= 1200000:
        return 0

    tax = 0
    # Slabs
    # 0 - 4L: 0%
    
    # 4L - 8L: 5%
    if income > 400000:
        taxable = min(income, 800000) - 400000
        tax += taxable * 0.05
        
    # 8L - 12L: 10%
    if income > 800000:
        taxable = min(income, 1200000) - 800000
        tax += taxable * 0.10
        
    # 12L - 16L: 15%
    if income > 1200000:
        taxable = min(income, 1600000) - 1200000
        tax += taxable * 0.15
        
    # 16L - 20L: 20%
    if income > 1600000:
        taxable = min(income, 2000000) - 1600000
        tax += taxable * 0.20
        
    # 20L - 24L: 25%
    if income > 2000000:
        taxable = min(income, 2400000) - 2000000
        tax += taxable * 0.25
        
    # Above 24L: 30%
    if income > 2400000:
        tax += (income - 2400000) * 0.30
        
    return tax

def calculate_old_regime_tax(income):
    # Standard Deduction
    income = max(0, income - 50000)
    
    # Rebate check (Income <= 5L is tax free)
    if income <= 500000:
        return 0
        
    tax = 0
    # 0 - 2.5L: 0%
    
    # 2.5L - 5L: 5%
    if income > 250000:
        taxable = min(income, 500000) - 250000
        tax += taxable * 0.05
        
    # 5L - 10L: 20%
    if income > 500000:
        taxable = min(income, 1000000) - 500000
        tax += taxable * 0.20
        
    # Above 10L: 30%
    if income > 1000000:
        tax += (income - 1000000) * 0.30
        
    return tax