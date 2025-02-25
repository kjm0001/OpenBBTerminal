# IMPORTATION STANDARD

# IMPORTATION THIRDPARTY
import pytest
import numpy as np
import pandas as pd

# IMPORTATION INTERNAL
from openbb_terminal.stocks.fundamental_analysis import fmp_model


@pytest.fixture(scope="module")
def vcr_config():
    return {
        "filter_headers": [("User-Agent", None)],
        "filter_query_parameters": [
            ("apikey", "MOCK_API_KEY"),
        ],
    }


@pytest.mark.vcr
@pytest.mark.record_stdout
def test_get_score():
    result = fmp_model.get_score(symbol="PM")
    if result:
        assert isinstance(result, np.number)


@pytest.mark.vcr
@pytest.mark.parametrize(
    "func, kwargs_dict",
    [
        (
            "get_profile",
            {"symbol": "PM"},
        ),
        (
            "get_quote",
            {"symbol": "PM"},
        ),
        (
            "get_enterprise",
            {"symbol": "PM", "limit": 5, "quarterly": False},
        ),
        (
            "get_dcf",
            {"symbol": "PM", "limit": 5, "quarterly": False},
        ),
        (
            "get_income",
            {"symbol": "PM", "limit": 5, "quarterly": False},
        ),
        (
            "get_balance",
            {"symbol": "PM", "limit": 5, "quarterly": False},
        ),
        (
            "get_cash",
            {"symbol": "PM", "limit": 5, "quarterly": False},
        ),
        (
            "get_key_metrics",
            {"symbol": "PM", "limit": 5, "quarterly": False},
        ),
        (
            "get_key_ratios",
            {"symbol": "PM", "limit": 5, "quarterly": False},
        ),
        (
            "get_financial_growth",
            {"symbol": "PM", "limit": 5, "quarterly": False},
        ),
        (
            "get_filings",
            {},
        ),
    ],
)
@pytest.mark.record_stdout
def test_valid_df(func, kwargs_dict):
    result_df = getattr(fmp_model, func)(**kwargs_dict)
    assert isinstance(result_df, pd.DataFrame)
