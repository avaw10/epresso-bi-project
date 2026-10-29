"""Tests use a tiny made-up table so you can check every answer by hand."""
import os
import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
import agent  # noqa: E402
import analytics  # noqa: E402


@pytest.fixture
def df():
    return pd.DataFrame({
        'store': ['A', 'A', 'B', 'B', 'B'],
        'channel': ['web', 'shop', 'web', 'shop', 'shop'],
        'amount': [100, 200, 50, None, 150],
    })


def test_survey_workbook_uses_its_header_row():
    survey_path = (
        Path(__file__).resolve().parents[1]
        / 'data'
        / 'Support_EX_B_Survey (1).xlsx'
    )
    survey = analytics.load_table(
        survey_path.read_bytes(), survey_path.name, 'Survey Results'
    )
    assert list(survey.columns) == [
        'Survey ID', 'Store ID', 'Year', 'Satisfaction', 'Interest'
    ]


def test_total_all_rows(df):
    r = analytics.get_total(df, 'amount')
    assert r.value == 500 and r.rows_used == 4
    assert any('missing' in c for c in r.caveats)


def test_total_filtered(df):
    assert analytics.get_total(df, 'amount', {'store': 'A'}).value == 300


def test_unknown_filter_value_returns_error_not_zero(df):
    r = analytics.get_total(df, 'amount', {'store': 'Z'})
    assert r.error and r.value is None


def test_group_total(df):
    assert analytics.group_total(df, 'amount', 'store').value == {'A': 300.0, 'B': 200.0}


def test_data_quality(df):
    r = analytics.data_quality_report(df)
    assert r.value['columns_with_missing'] == {'amount': 1}


def test_merge_without_fan_out(df):
    stores = pd.DataFrame({'store': ['A', 'B'], 'city': ['X', 'Y']})
    _, rep = analytics.check_merge(df, stores, on='store', value_col='amount')
    assert not rep['changed']


def test_merge_fan_out_is_detected(df):
    dup = pd.DataFrame({'store': ['A', 'A', 'B'], 'city': ['X', 'X2', 'Y']})
    _, rep = analytics.check_merge(df, dup, on='store', value_col='amount')
    assert rep['changed'] and rep['sum_after'] > rep['sum_before']


def test_merge_detects_dropped_rows_even_when_revenue_is_unchanged():
    left = pd.DataFrame({'id': ['A', 'B'], 'Revenue': [10, 0]})
    right = pd.DataFrame({'id': ['A']})
    _, report = analytics.check_merge(
        left, right, on='id', value_col='Revenue', how='inner'
    )
    assert report['rows_after'] < report['rows_before']
    assert report['sum_after'] == report['sum_before']
    assert report['changed']


def test_merge_with_different_key_names(df):
    stores = pd.DataFrame({'id': ['A', 'B'], 'city': ['X', 'Y']})
    merged, report = analytics.check_merge(
        df, stores, left_on='store', right_on='id', value_col='amount'
    )
    assert len(merged) == len(df)
    assert not report['changed']


def test_merge_ignores_blank_lookup_keys_without_fanning_out():
    left = pd.DataFrame({'id': [None, 'A'], 'Revenue': [10, 20]})
    right = pd.DataFrame({'id': [None, None, 'A'], 'name': ['x', 'y', 'a']})
    merged, report = analytics.merge_sales_products(
        left.rename(columns={'id': 'Product ID'}),
        right.rename(columns={'id': 'Product ID', 'name': 'Product'}),
    )
    assert len(merged) == len(left)
    assert merged['Product'].isna().sum() == 1
    assert not report['changed']


def test_merge_reports_clear_missing_required_column():
    left = pd.DataFrame({'id': ['A'], 'amount': [10]})
    right = pd.DataFrame({'id': ['A']})
    with pytest.raises(ValueError, match="Left table is missing required column\\(s\\): 'Revenue'"):
        analytics.check_merge(left, right, on='id', value_col='Revenue')


def test_dimension_merge_rejects_duplicate_lookup_keys():
    sales = pd.DataFrame({'Product ID': ['A'], 'Revenue': [10]})
    products = pd.DataFrame({'Product ID': ['A', 'A'], 'Product': ['one', 'two']})
    with pytest.raises(ValueError, match='duplicate merge-key values'):
        analytics.merge_sales_products(sales, products)


def test_revenue_blanks_are_skipped_and_counted():
    sales = pd.DataFrame({'Revenue': [100, None, 'not a number']})
    assert analytics.calculate_total_revenue(sales) == 100
    assert analytics.count_missing_or_non_numeric(sales, 'Revenue') == 2


def test_dispatcher_rejects_unknown_tool_and_arguments(df):
    log = []
    assert agent.run_tool('run_python', {}, df, log).error
    assert agent.run_tool('get_total', {'value_col': 'amount', 'code': 'x'}, df, log).error


def test_unsupported_question(df):
    out = agent.answer_question('What is the meaning of life?', df)
    assert 'cannot answer' in out['findings']
