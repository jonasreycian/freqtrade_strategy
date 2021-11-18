# pragma pylint: disable=missing-docstring, invalid-name, pointless-string-statement
# flake8: noqa: F401

# --- Do not remove these libs ---
import numpy as np  # noqa
import pandas as pd  # noqa
from pandas import DataFrame

from freqtrade.strategy import (
    BooleanParameter,
    CategoricalParameter,
    DecimalParameter,
    IStrategy,
    IntParameter,
    informative,
)

# --------------------------------
# Add your lib to import here
import talib.abstract as ta
import freqtrade.vendor.qtpylib.indicators as qtpylib
from datetime import datetime
from freqtrade.persistence import Trade
from freqtrade.strategy import stoploss_from_open


class SidewayStrategy(IStrategy):
    """
    This is a strategy template to get you started.
    More information in https://www.freqtrade.io/en/latest/strategy-customization/

    You can:
        :return: a Dataframe with all mandatory indicators for the strategies
    - Rename the class name (Do not forget to update class_name)
    - Add any methods you want to build your strategy
    - Add any lib you need to build your strategy

    You must keep:
    - the lib in the section "Do not remove these libs"
    - the methods: populate_indicators, populate_buy_trend, populate_sell_trend
    You should keep:
    - timeframe, minimal_roi, stoploss, trailing_*
    """

    # Strategy interface version - allow new iterations of the strategy interface.
    # Check the documentation or the Sample strategy to get the latest version.
    INTERFACE_VERSION = 2

    minimal_roi = {
        "0": 0.09,
        "24": 0.077,
        "75": 0.038,
        "190": 0
    }

    # Stoploss:
    stoploss = -0.348

    # Trailing stop:
    trailing_stop = True
    trailing_stop_positive = 0.172
    trailing_stop_positive_offset = 0.2
    trailing_only_offset_is_reached = True

    # Optimal timeframe for the strategy.
    timeframe = "5m"

    # Run "populate_indicators()" only for new candle.
    process_only_new_candles = False

    # These values can be overridden in the "ask_strategy" section in the config.
    use_sell_signal = True
    sell_profit_only = False
    ignore_roi_if_buy_signal = False

    # use_custom_stoploss = True
    # Number of candles the strategy requires before producing valid signals
    # startup_candle_count: int = 50

    # Optional order type mapping.
    order_types = {
        "buy": "limit",
        "sell": "limit",
        "stoploss": "market",
        "stoploss_on_exchange": True,
    }

    # Optional order time in force.
    order_time_in_force = {"buy": "gtc", "sell": "gtc"}

    plot_config = {
        # Main plot indicators (Moving averages, ...)
        "main_plot": {
            "sma5": {"color": "yellow"},
            "sma20": {"color": "red"},
            "sma50": {"color": "violet"},
            "sma100": {"color": "pink"},
        },
        "subplots": {
            # Subplots - each dict defines one additional plot
            "MACD": {
                "macdhist": {"color": "green"},
            },
            "RSI": {
                "rsi_14": {"color": "green"},
                "rsi_30": {"color": "red"},
            },
        },
    }

    # Define informative upper timeframe for each pair. Decorators can be stacked on same
    # method. Available in populate_indicators as 'rsi_30m' and 'rsi_1h'.
    # @informative("30m")
    # # @informative("1h")
    # # @informative("1d")
    # def populate_indicators_1h(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
    #     dataframe["rsi_14"] = ta.RSI(dataframe, timeperiod=14)
    #     dataframe["rsi_30"] = ta.RSI(dataframe, timeperiod=30)
    #     dataframe["sma200"] = ta.SMA(dataframe, timeperiod=200)
    #     return dataframe

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        Adds several different TA indicators to the given DataFrame

        Performance Note: For the best performance be frugal on the number of indicators
        you are using. Let uncomment only the indicator you are using in your strategies
        or your hyperopt configuration, otherwise you will waste your memory and CPU usage.
        :param dataframe: Dataframe with data from the exchange
        :param metadata: Additional information, like the currently traded pair
        :return: a Dataframe with all mandatory indicators for the strategies
        """
        # Delete not usable columns
        # dataframe = dataframe.drop(
        #     columns=[
        #         "open_30m",
        #         "high_30m",
        #         "low_30m",
        #         "close_30m",
        #         "volume_30m",
        #     ],
        #     axis=1,
        # )

        # Calculate rsi of the original dataframe (15m timeframe)
        dataframe["rsi_14"] = ta.RSI(dataframe, timeperiod=14)
        dataframe["rsi_30"] = ta.RSI(dataframe, timeperiod=30)

        # MACD
        macd = ta.MACD(dataframe)
        dataframe["macd"] = macd["macd"]
        dataframe["macdsignal"] = macd["macdsignal"]
        dataframe["macdhist"] = macd["macdhist"]

        # # SMA - Simple Moving Average
        dataframe["sma5"] = ta.SMA(dataframe, timeperiod=5)
        dataframe["sma10"] = ta.SMA(dataframe, timeperiod=10)
        dataframe["sma20"] = ta.SMA(dataframe, timeperiod=20)
        dataframe["sma50"] = ta.SMA(dataframe, timeperiod=50)
        dataframe["sma100"] = ta.SMA(dataframe, timeperiod=100)
        dataframe["sma200"] = ta.SMA(dataframe, timeperiod=200)
        dataframe = dataframe.dropna()

        # print("-------------------")
        # print("-- inFORMATIVE")
        # print("-------------------")
        # print(dataframe.head())
        # print(dataframe.columns.tolist())

        # Retrieve best bid and best ask from the orderbook
        # ------------------------------------
        """
        # first check if dataprovider is available
        if self.dp:
            if self.dp.runmode.value in ('live', 'dry_run'):
                ob = self.dp.orderbook(metadata['pair'], 1)
                dataframe['best_bid'] = ob['bids'][0][0]
                dataframe['best_ask'] = ob['asks'][0][0]
        """

        return dataframe

    def populate_buy_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        Based on TA indicators, populates the buy signal for the given dataframe
        :param dataframe: DataFrame populated with indicators
        :param metadata: Additional information, like the currently traded pair
        :return: DataFrame with buy column
        """
        # Close price should trail around 4% from sma20
        trail_percent = (
            abs(dataframe["close"] - dataframe["sma20"]) / dataframe["sma20"] * 100
        )
        dataframe.loc[
            (
                (
                    (dataframe["sma5"] > dataframe["sma20"])
                    | (dataframe["sma5"] > dataframe["sma50"])
                    | (dataframe["sma5"] > dataframe["sma100"])
                    | (dataframe["sma5"] > dataframe["sma200"])
                )
                # & (trail_percent <= 4.0)
                # & (qtpylib.crossed_above(dataframe["rsi_14"], dataframe["rsi_30"]))
            ),
            "buy",
        ] = 1

        return dataframe

    def populate_sell_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        Based on TA indicators, populates the sell signal for the given dataframe
        :param dataframe: DataFrame populated with indicators
        :param metadata: Additional information, like the currently traded pair
        :return: DataFrame with buy column
        """
        dataframe.loc[
            (
                (dataframe["sma5"] < dataframe["sma20"])
                    | (dataframe["sma5"] < dataframe["sma50"])
                    | (dataframe["sma5"] < dataframe["sma100"])
                    | (dataframe["sma5"] < dataframe["sma200"])
            ),
            "sell",
        ] = 1
        return dataframe


pair_list = ['BTC/USDT', 'ETH/USDT', 'GALA/USDT', 'SAND/USDT', 'ALGO/USDT', 'MANA/USDT', 'AVAX/USDT', 'XRP/USDT', 'SHIB/USDT', 'DOT/USDT', 'SOL/USDT', 'FIL/USDT', 'TRX/USDT', 'ADA/USDT', 'LTC/USDT', 'WAXP/USDT', 'AUDIO/USDT', 'LUNA/USDT', 'FTM/USDT', 'DOGE/USDT', 'VET/USDT', 'OMG/USDT', 'ALICE/USDT', 'ROSE/USDT', 'MATIC/USDT']

"""
Backtesting:
docker-compose run --rm freqtrade backtesting -c user_data/config_priv.json -s SidewayStrategy --timeframe 5m --eps --timerange=-20211030

Hyperopt - SharpeHyperOptLossDaily
docker-compose run --rm freqtrade hyperopt --hyperopt-loss SharpeHyperOptLossDaily -c user_data/config_priv.json --spaces all --ignore-missing-spaces --strategy SidewayStrategy -e 1000 --eps --timerange=-20211030
`
# ROI table:
minimal_roi = {
    "0": 0.09,
    "24": 0.077,
    "75": 0.038,
    "190": 0
}

# Stoploss:
stoploss = -0.348

# Trailing stop:
trailing_stop = True
trailing_stop_positive = 0.172
trailing_stop_positive_offset = 0.2
trailing_only_offset_is_reached = True
`

"""