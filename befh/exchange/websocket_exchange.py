import logging
from datetime import datetime

import ccxt

from cryptofeed import FeedHandler
from cryptofeed.defines import L2_BOOK, TRADES, BID, ASK
from cryptofeed.callback import BookCallback, TradeCallback
import cryptofeed.exchanges as cryptofeed_exchanges

from .rest_api_exchange import RestApiExchange

LOGGER = logging.getLogger(__name__)


class WebsocketExchange(RestApiExchange):
    """Websocket exchange.
    """

    def __init__(self, **kwargs):
        """Constructor.
        """
        super().__init__(**kwargs)
        self._feed_handler = None
        self._instrument_mapping = None

    def load(self, **kwargs):
        """Load.
        """
        super().load(is_initialize_instmt=False, **kwargs)
        self._feed_handler = FeedHandler()
        self._instrument_mapping = self._create_instrument_mapping(
            self._instruments)
        exchange = getattr(
            cryptofeed_exchanges,
            self._get_exchange_name(self._name))
        callbacks = {
            L2_BOOK: BookCallback(self._update_order_book_callback),
            TRADES: TradeCallback(self._update_trade_callback)
        }

        if self._name.lower() == 'poloniex':
            self._feed_handler.add_feed(
                exchange(
                    channels=list(self._instrument_mapping.keys()),
                    callbacks=callbacks))
        else:
            self._feed_handler.add_feed(
                exchange(
                    pairs=list(self._instrument_mapping.keys()),
                    channels=list(callbacks.keys()),
                    callbacks=callbacks))

    def run(self):
        """Run.
        """
        self._feed_handler.run()

    @staticmethod
    def _get_exchange_name(name):
        """Get exchange name.
        """
        name = name.capitalize()
        if name == 'Hitbtc':
            return 'HitBTC'

        return name

    @staticmethod
    def _create_instrument_mapping(instruments):
        """Create instrument mapping.
        """
        mapping = {}
        for name in instruments.keys():
            mapping[name.replace('/', '-')] = name

        return mapping

    def _update_order_book_callback(self, feed, pair, book, timestamp):
        """Update order book callback.
        """
        if pair in self._instrument_mapping:
            # The instrument pair can be mapped directly from crypofeed
            # format to the ccxt format
            instmt_info = self._instruments[self._instrument_mapping[pair]]
        else:
            pass

        order_book = {}
        bids = []
        asks = []
        order_book['bids'] = bids
        order_book['asks'] = asks

        for price, volume in book[BID].items():
            bids.append((float(price), float(volume)))

        for price, volume in book[ASK].items():
            asks.append((float(price), float(volume)))

        is_updated = instmt_info.update_bids_asks(
            bids=bids,
            asks=asks)

        if not is_updated:
            return

        for handler in self._handlers.values():
            self._rotate_order_table(handler=handler,
                                     instmt_info=instmt_info)
            instmt_info.update_table(handler=handler)

    def _update_trade_callback(
            self, feed, pair, order_id, timestamp, side, amount, price):
        """Update trade callback.
        """
        instmt_info = self._instruments[self._instrument_mapping[pair]]
        trade = {}
        trade['timestamp'] = timestamp
        trade['id'] = order_id
        trade['price'] = float(price)
        trade['amount'] = float(amount)

        current_timestamp = datetime.utcnow()

        if not instmt_info.update_trade(trade, current_timestamp):
            return

        for handler in self._handlers.values():
            self._rotate_order_table(handler=handler,
                                     instmt_info=instmt_info)
            instmt_info.update_table(handler=handler)
