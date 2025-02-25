# pylint: disable=too-many-arguments,E1101
"""Automatic Statistical Forecast"""
__docformat__ = "numpy"

import logging
from typing import Union, Optional, List, Tuple

import warnings
from darts import TimeSeries
import pandas as pd
from statsforecast.core import StatsForecast

from openbb_terminal.decorators import log_start_end
from openbb_terminal.rich_config import console, USE_COLOR
from openbb_terminal.forecast import helpers


warnings.simplefilter("ignore")

logger = logging.getLogger(__name__)

# pylint: disable=E1123,E1137


def precision_format(best_model: str, index: str, val: float) -> str:
    if index == best_model and USE_COLOR:
        return f"[#00AAFF]{val:.2f}% [/#00AAFF]"
    return f"{val:.2f}%"


@log_start_end(log=logger)
def get_autoselect_data(
    data: Union[pd.Series, pd.DataFrame],
    target_column: str = "close",
    seasonal_periods: int = 7,
    n_predict: int = 5,
    start_window: float = 0.85,
    forecast_horizon: int = 5,
) -> Tuple[
    Optional[List[type[TimeSeries]]],
    Optional[List[type[TimeSeries]]],
    Optional[List[type[TimeSeries]]],
    Optional[float],
    Optional[StatsForecast],
    Optional[Union[int, str]],
]:
    """Performs Automatic Statistical forecasting
    This is a wrapper around StatsForecast models;
    we refer to this link for the original and more complete documentation of the parameters.


        https://nixtla.github.io/statsforecast/models.html

    Parameters
    ----------
    data : Union[pd.Series, np.ndarray]
        Input data.
    target_column: Optional[str]:
        Target column to forecast. Defaults to "close".
    seasonal_periods: int
        Number of seasonal periods in a year (7 for daily data)
        If not set, inferred from frequency of the series.
    n_predict: int
        Number of days to forecast
    start_window: float
        Size of sliding window from start of timeseries and onwards
    forecast_horizon: int
        Number of days to forecast when backtesting and retraining historical

    Returns
    -------
    Tuple[List[TimeSeries], List[TimeSeries], List[TimeSeries], Optional[float], StatsForecast, Union[int, str]]
        list[np.ndarray] - Adjusted Data series
        list[np.ndarray] - List of historical fcast values
        list[np.ndarray] - List of predicted fcast values
        Optional[float] - precision
        StatsForecast - Fit ETS model object.
        Union[int, str] - Best model
    """

    use_scalers = False
    # statsforecast preprocessing
    # when including more time series
    # the preprocessing is similar
    _, ticker_series = helpers.get_series(data, target_column, is_scaler=use_scalers)
    freq = ticker_series.freq_str
    ticker_series = ticker_series.pd_dataframe().reset_index()
    ticker_series.columns = ["ds", "y"]
    ticker_series.insert(0, "unique_id", target_column)

    # check statsforecast dependency
    try:
        from statsforecast.models import (  # pylint: disable=import-outside-toplevel
            AutoARIMA,
            ETS,
            AutoCES,
            MSTL,
            Naive,
            SeasonalNaive,
            SeasonalWindowAverage,
            RandomWalkWithDrift,
        )
    except Exception as e:
        error = str(e)
        if "cannot import name" in error:
            console.print(
                "[red]Please update statsforecast to version 1.2.0 or higher.[/red]"
            )
        else:
            console.print(f"[red]{error}[/red]")
        return [], [], [], None, None, None

    try:
        # Model Init
        season_length = int(seasonal_periods)
        models = [
            AutoARIMA(season_length=season_length),
            ETS(season_length=season_length),
            AutoCES(season_length=season_length),
            MSTL(season_length=season_length),
            SeasonalNaive(season_length=season_length),
            SeasonalWindowAverage(
                season_length=season_length, window_size=season_length
            ),
            RandomWalkWithDrift(),
        ]
        fcst = StatsForecast(
            df=ticker_series,
            models=models,
            freq=freq,
            verbose=True,
            fallback_model=Naive(),
        )
    except Exception as e:  # noqa
        error = str(e)
        if "got an unexpected keyword argument" in error:
            console.print(
                "[red]Please update statsforecast to version 1.1.3 or higher.[/red]"
            )
        else:
            console.print(f"[red]{error}[/red]")
        return [], [], [], None, None, None

    # Historical backtesting
    last_training_point = int((len(ticker_series) - 1) * start_window)
    historical_fcast = fcst.cross_validation(
        h=int(forecast_horizon),
        test_size=len(ticker_series) - last_training_point,
        n_windows=None,
        input_size=min(10 * forecast_horizon, len(ticker_series)),
    )
    # change name to AutoETS and AutoCES
    cols = [
        c if (c not in ["ETS", "CES"]) else f"Auto{c}" for c in historical_fcast.columns
    ]
    historical_fcast.columns = cols

    # train new model on entire timeseries to provide best current forecast
    # we have the historical fcast, now lets predict.
    forecast = fcst.forecast(int(n_predict))
    # change name to AutoETS and AutoCES
    cols = [c if (c not in ["ETS", "CES"]) else f"Auto{c}" for c in forecast.columns]
    forecast.columns = cols
    # Backtesting evaluation
    y_true = historical_fcast["y"].values
    model_names = historical_fcast.drop(columns=["ds", "cutoff", "y"]).columns
    precision_per_model = [
        helpers.mean_absolute_percentage_error(y_true, historical_fcast[model].values)
        for model in model_names
    ]
    precision: pd.DataFrame = pd.DataFrame(
        {"precision": precision_per_model}, index=model_names
    )
    precision = precision.sort_values(by="precision")
    # select best model
    best_precision: float = precision["precision"].min()
    best_model = precision["precision"].idxmin()

    # print results
    precision["precision"] = [  # pylint: disable=unsupported-assignment-operation
        precision_format(best_model, index, val)
        for index, val in precision["precision"].iteritems()
    ]
    console.print("\n")
    helpers.print_rich_table(
        precision,
        show_index=True,
        index_name="Model",
        headers=["MAPE"],
        title=f"Performance per model.\nBest model: [#00AAFF]{best_model}[/#00AAFF]",
    )

    # transform outputs to make them compatible with
    # plots
    use_scalers = False
    _, ticker_series = helpers.get_series(
        ticker_series.rename(columns={"y": target_column}),
        target_column,
        is_scaler=use_scalers,
        time_col="ds",
    )
    _, forecast = helpers.get_series(
        forecast.rename(columns={best_model: target_column}),
        target_column,
        is_scaler=use_scalers,
        time_col="ds",
    )
    _, historical_fcast = helpers.get_series(
        historical_fcast.groupby("ds")
        .head(1)
        .rename(columns={best_model: target_column}),
        target_column,
        is_scaler=use_scalers,
        time_col="ds",
    )

    return (ticker_series, historical_fcast, forecast, best_precision, fcst, best_model)
