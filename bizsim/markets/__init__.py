"""
The markets subsystem for BizSim.
Handles product systems, SKU management, and market-related domain logic.
"""

from .consumer_market import SqliteConsumerMarket
from .industrial_market import SqliteIndustrialMarket

__all__ = ["SqliteConsumerMarket", "SqliteIndustrialMarket"]
