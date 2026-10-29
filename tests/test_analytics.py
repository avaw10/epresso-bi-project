"""Tests use a tiny made-up table so you can check every answer by hand."""
import os
import sys
from io import BytesIO

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


def test_profile_key_reports_missing_and_duplicate_keys():
    table = pd.DataFrame({'store': ['A', 'A', None], 'year': [2025, 2025, 2026]})
    result = analytics.profile_key(table, ['store', 'year'])
    assert result == {
        'columns': ['store', 'year'],
        'missing_rows': 1,
        'duplicate_rows': 1,
        'unique_values': 1,
    }


def test_load_epresso_sources_reads_separate_tables_and_survey_header():
    sales_workbook = BytesIO()
    with pd.ExcelWriter(sales_workbook, engine='openpyxl') as writer:
        pd.DataFrame({
            'Sales ID': ['S1'], 'Date': ['2025-01-31'], 'Store ID': ['SH01'],
            'StoreYear': ['SH01_25'], 'Category ID': ['C1'], 'Product ID': ['P01'],
            'Revenue': [1000],
        }).to_excel(writer, sheet_name='Sales', index=False)
        pd.DataFrame({'Product ID': ['P01'], 'Product': ['Coffee']}).to_excel(
            writer, sheet_name='Products', index=False,
        )
        pd.DataFrame({'Category ID': ['C1'], 'Category': ['Beans']}).to_excel(
            writer, sheet_name='Categories', index=False,
        )

    survey_workbook = BytesIO()
    with pd.ExcelWriter(survey_workbook, engine='openpyxl') as writer:
        pd.DataFrame([
            ['Survey title', None, None, None, None],
            [None, None, None, None, None],
            ['Survey ID', 'Store ID', 'Year', 'Satisfaction', 'Interest'],
            ['SH01_25', 'SH01', 'Y2025', 4, 5],
        ]).to_excel(writer, sheet_name='Survey Results', index=False, header=False)

    stores = (
        'ID\tCity\tState\tPostalCode\tPhone\tStoreType\tMarket\tLocation\tManager\n'
        'SH01\tTown\tCA\t01234\t555-0100\tRetail\t1-Small\tWest\t"Doe, Jane"\n'
    ).encode()

    tables = analytics.load_epresso_sources(
        sales_workbook.getvalue(),
        stores,
        survey_workbook.getvalue(),
    )

    assert set(tables) == {'Sales', 'Products', 'Categories', 'Stores', 'Survey Results'}
    assert tables['Sales'].loc[0, 'Revenue'] == 1000
    assert tables['Stores'].loc[0, 'PostalCode'] == '01234'
    assert tables['Survey Results'].columns.tolist() == [
        'Survey ID', 'Store ID', 'Year', 'Satisfaction', 'Interest',
    ]
    assert tables['Survey Results'].loc[0, 'Survey ID'] == 'SH01_25'
    total = analytics.get_total(tables['Sales'], 'Revenue')
    assert total.value == 1000 and total.rows_used == 1


def test_merge_without_fan_out(df):
    stores = pd.DataFrame({'store': ['A', 'B'], 'city': ['X', 'Y']})
    _, rep = analytics.check_merge(df, stores, on='store', value_col='amount')
    assert not rep['changed']


def test_merge_fan_out_is_detected(df):
    dup = pd.DataFrame({'store': ['A', 'A', 'B'], 'city': ['X', 'X2', 'Y']})
    _, rep = analytics.check_merge(df, dup, on='store', value_col='amount')
    assert rep['changed'] and rep['sum_after'] > rep['sum_before']


def test_dispatcher_rejects_unknown_tool_and_arguments(df):
    log = []
    assert agent.run_tool('run_python', {}, df, log).error
    assert agent.run_tool('get_total', {'value_col': 'amount', 'code': 'x'}, df, log).error


def test_unsupported_question(df):
    out = agent.answer_question('What is the meaning of life?', df)
    assert 'cannot answer' in out['findings']
