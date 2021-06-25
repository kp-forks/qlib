# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.
import warnings
import pandas as pd

from dataclasses import dataclass, field
from typing import ClassVar, Union, List, Set, Tuple


@dataclass
class Order:
    """
    stock_id : str
    amount : float
    start_time : pd.Timestamp
        closed start time for order trading
    end_time : pd.Timestamp
        closed end time for order trading
    direction : int
        Order.SELL for sell; Order.BUY for buy
    factor : float
            presents the weight factor assigned in Exchange()
    """

    stock_id: str
    amount: float
    start_time: pd.Timestamp
    end_time: pd.Timestamp
    direction: int
    factor: float
    deal_amount: float = field(init=False)
    SELL: ClassVar[int] = 0
    BUY: ClassVar[int] = 1

    def __post_init__(self):
        if self.direction not in {Order.SELL, Order.BUY}:
            raise NotImplementedError("direction not supported, `Order.SELL` for sell, `Order.BUY` for buy")
        self.deal_amount = 0


class BaseTradeDecision:
    def __init__(self, strategy):
        self.strategy = strategy

    def get_decision(self) -> List[object]:
        """
        get the concrete decision of the order
        This will be called by the inner strategy
        Returns
        -------
        List[object]:
            The decision result. Typically it is some orders
            Example:
                []:
                    Decision not available
                concrete_decision:
                    available
        """
        raise NotImplementedError(f"This type of input is not supported")

    def update(self, trade_calendar):
        """
        Be called at the **start** of each step
        Returns
        -------
        None:
            No update, use previous decision(or unavailable)
        BaseTradeDecison:
            New update, use new decision
        """
        return self.strategy.update_trade_decision(self, trade_calendar)

    def get_range_limit(self) -> Tuple[int, int]:
        """
        return the expected step range for limiting the dealing time of the order
        Returns
        -------
        Tuple[int, int]:
        Raises
        ------
        NotImplementedError:
            If the decision can't provide a unified start and end
        """
        raise NotImplementedError(f"This method is not implemented")


class TradeDecisonWithOrderPool:
    """trade decison that made by strategy"""

    def __init__(self, strategy, order_pool):
        """
        Parameters
        ----------
        strategy : BaseStrategy
            the original strategy that make the decison
        order_pool : list, optional
            the candinate order pool for generate trade decision
        """
        super(TradeDecisonWithOrderPool, self).__init__(strategy)
        self.order_pool = order_pool
        self.order_list = []

    def pop_order_pool(self, pop_len):
        if pop_len > len(self.order_pool):
            warnings.warn(
                f"pop len {pop_len} is too much length than order pool, cut it as pool length {len(self.order_pool)}"
            )
            pop_len = len(self.order_pool)
        res = self.order_pool[:pop_len]
        del self.order_pool[:pop_len]
        return res

    def push_order_list(self, order_list):
        self.order_list.extend(order_list)

    def get_decision(self):
        """get the order list

        Parameters
        ----------
        only_enable : bool, optional
            wether to ignore disabled order, by default False
        only_disable : bool, optional
            wether to ignore enabled order, by default False
        Returns
        -------
        List[Order]
            the order list
        """
        return self.order_list

    def update(self, trade_calendar):
        """make the original strategy update the enabled status of orders."""
        self.ori_strategy.update_trade_decision(self, trade_calendar)


class BaseDecisionUpdater:
    def update_decision(self, decison, trade_calendar) -> BaseTradeDecision:
        """[summary]

        Parameters
        ----------
        decison : BaseTradeDecision
            the trade decision to be updated
        trade_calendar : BaseTradeCalendar
            the trade calendar of inner execution

        Returns
        -------
        BaseTradeDecision
            the updated decision
        """
        raise NotImplementedError(f"This method is not implemented")


class DecisionUpdaterWithOrderPool:
    def __init__(self, plan_config=None):
        """
        Parameters
        ----------
        plan_config : Dict[Tuple(int, float)], optional
            the plan config, by default None
        """
        if plan_config is None:
            self.plan_config = [(0, 1)]
        else:
            self.plan_config = plan_config

    def update_decision(self, decision, trade_calendar) -> BaseTradeDecision:
        # get the number of trading step finished, trade_step can be [0, 1, 2, ..., trade_len - 1]
        trade_step = self.trade_calendar.get_trade_step()
        for _index, _ratio in self.plan_config:
            if trade_step == _index:
                pop_len = len(decision.order_pool) * _ratio
                pop_order_list = decision.pop_order_pool(pop_len)
                decision.push_order_list(pop_order_list)
