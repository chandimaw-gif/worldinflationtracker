"""
CPI Calculation Engine

Implements:
- Laspeyres fixed-basket CPI
- Year-on-Year, Month-on-Month, and 12-Month Moving Average inflation
- Core CPI (exclusion method)
- Elementary Jevons index (geometric mean)
"""

import math
from decimal import Decimal
from django.db.models import Avg, Sum
from core.models import BasketItem, PriceObservation, CPIIndex, ProductGroup


def jevons_index(prices):
    """
    Calculate Jevons (geometric mean) elementary index.
    P_jevons = (Π P_i)^(1/n)
    """
    if not prices:
        return Decimal('0')
    product = Decimal('1')
    for p in prices:
        product *= p
    n = len(prices)
    return Decimal(product) ** (Decimal('1') / Decimal(n))


def laspeyres_cpi(current_prices, base_prices, weights):
    """
    Calculate Laspeyres CPI.
    CPI_t = (Σ (P_i,t × Q_i,0)) / (Σ (P_i,0 × Q_i,0)) × 100

    Here weights represent the expenditure shares (P_i,0 × Q_i,0).
    We use item.weight as the proportion within its group.
    """
    numerator = Decimal('0')
    denominator = Decimal('0')

    for item_id in current_prices:
        p_t = current_prices[item_id]
        p_0 = base_prices.get(item_id)
        w = weights.get(item_id, Decimal('0'))

        if p_0 and p_0 > 0:
            numerator += p_t * w
            denominator += p_0 * w

    if denominator == 0:
        return Decimal('0')

    return (numerator / denominator) * Decimal('100')


def compute_group_index(country, group, period_date, base_period):
    """
    Compute index for a single product group.
    """
    items = BasketItem.objects.filter(
        country=country,
        group=group,
        is_active=True
    )

    current_prices = {}
    base_prices = {}
    weights = {}

    for item in items:
        # Get latest price before or on period_date
        latest = PriceObservation.objects.filter(
            item=item,
            observation_date__lte=period_date
        ).order_by('-observation_date').first()

        base = PriceObservation.objects.filter(
            item=item,
            observation_date__lte=base_period
        ).order_by('-observation_date').first()

        if latest and base:
            current_prices[item.id] = latest.price
            base_prices[item.id] = base.price
            weights[item.id] = item.weight

    if not current_prices:
        return None

    return laspeyres_cpi(current_prices, base_prices, weights)


def compute_cpi(country, period_date, index_type='headline', base_period=None):
    """
    Compute CPI for a country and period.

    index_type options: 'headline', 'core', 'food', 'non_food'
    """
    if base_period is None:
        base_period = country.base_period

    groups = ProductGroup.objects.filter(country=country, is_active=True)

    if index_type == 'core':
        # Exclude non-core groups
        groups = groups.filter(is_core=True)
    elif index_type == 'food':
        # Filter to food group only (COICOP 01)
        groups = groups.filter(coicop_code__startswith='01')
    elif index_type == 'non_food':
        groups = groups.exclude(coicop_code__startswith='01')

    total_weight = Decimal('0')
    weighted_sum = Decimal('0')

    for group in groups:
        group_index = compute_group_index(country, group, period_date, base_period)
        if group_index is not None:
            weighted_sum += group_index * group.weight
            total_weight += group.weight

    if total_weight == 0:
        return None

    return weighted_sum / total_weight


def compute_inflation_rates(country, period_date, index_type='headline'):
    """
    Compute YoY, MoM, and 12-month MA inflation.
    """
    from datetime import timedelta
    from dateutil.relativedelta import relativedelta

    # Current CPI
    current_cpi = compute_cpi(country, period_date, index_type)
    if current_cpi is None:
        return None, None, None

    # YoY: compare with same month last year
    yoy_date = period_date - relativedelta(months=12)
    yoy_cpi = compute_cpi(country, yoy_date, index_type)
    yoy = ((current_cpi - yoy_cpi) / yoy_cpi * 100) if yoy_cpi else None

    # MoM: compare with previous month
    mom_date = period_date - relativedelta(months=1)
    mom_cpi = compute_cpi(country, mom_date, index_type)
    mom = ((current_cpi - mom_cpi) / mom_cpi * 100) if mom_cpi else None

    # 12-month MA
    last_12 = []
    prev_12 = []
    for i in range(12):
        d1 = period_date - relativedelta(months=i)
        v1 = compute_cpi(country, d1, index_type)
        if v1:
            last_12.append(v1)

        d2 = period_date - relativedelta(months=(i + 12))
        v2 = compute_cpi(country, d2, index_type)
        if v2:
            prev_12.append(v2)

    ma12 = None
    if last_12 and prev_12:
        avg_last = sum(last_12) / len(last_12)
        avg_prev = sum(prev_12) / len(prev_12)
        if avg_prev > 0:
            ma12 = ((avg_last - avg_prev) / avg_prev) * 100

    return yoy, mom, ma12
