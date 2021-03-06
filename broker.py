# -*- encoding=utf8 -*-
"""
@author: Jerry
@contact: lvjy3.15@sem.tsinghua.edu.cn
@file: broker.py
@time: 2016/5/4 21:53
"""

import math
from collections import defaultdict

import pandas as pd

from portfolio import Portfolio


class Broker(object):
	'''
	Broker class
	'''
	def __init__(self,commission=0.002,price_type='close',short=False,begin_equity=1000000,date="2015-11-01",output=True ):
		'''
		Initializing the broker class
		:param commission: commission fee, default 0.002
		:param price_type: vwap or close price or open price or other choices(close*0.5+open*0.5)
		:param short: True or False, True if shorting is allowed
		'''
		# set default parameters
		self.commission = commission
		self.price = price_type
		self.short = short
		self.output = output
		#
		self.port = Portfolio(begin_equity=begin_equity, commission=commission)
		self.order_list = []
		self.order_count = 0
		self.trading_data = pd.DataFrame()
		self.trade_info = {}
		# two checking triggers
		self.execute_trigger = False
		self.update_trigger = False
		# daily recorder
		self.trade_amount = 0.0
		self.trade_cost = 0.0
		self.date = date
		# log
		self.trade_log = {}

	def get_universe(self):
		'''
		Get the list of stock symbol
		:return: list of stocks which can be traded
		'''
		universe = list(self.trading_data[(self.trading_data['maxupordown'] == 0) & (self.trading_data['trade_status'] == u'交易')].index)
		return universe

	def execute(self,output=False):
		'''
		Execute the orders separately
		:return: none
		'''
		if not self.execute_trigger:
			# execute the orders
			fee = 0
			trade_amount = 0
			for order in self.order_list:
				info = Trade_info(cash=self.port.cash, # cash amount
				                  symbol=order.symbol,
				                  price=self.trading_data.loc[order.symbol,'adj_trade'],  # trade price
				                  maxupordown=self.trading_data.loc[order.symbol,'maxupordown'],
				                  status=self.trading_data.loc[order.symbol,'trade_status'],
				                  portfolio_value=self.port.portfolio_value,
				                  position=self.port.positions[order.symbol].position, # stock position
				                  commission=self.commission,
				                  short=self.short)
				# validate the orders
				order.validate(info)
				# execute the order
				fee, trade_amount, delta_cash = self.port.update(order)
				if output:
					print(fee)
					print(trade_amount)
					print(delta_cash)
					print(order)
				# update the daily record
				self.trade_amount += trade_amount
				self.trade_cost += fee

			# record the trade results
			self.trade_log[self.date] = {'trade_volume': self.trade_amount,
										 'trade_cost': self.trade_cost,
										 'order num':self.order_count}
			self.execute_trigger = True
			self.update_trigger = False

			if output:
				self.trade_summary()

		else:
			# warning
			print('You cannot execute the order twice in a single trade day or without update the data')

	def trade_summary(self):
		'''
		Print the trading result in a single day
		'''
		print('=================================================================')
		print('Date: ' + str(self.date))
		print('Trade volume %0.1f' % self.trade_amount + ';Port cash %0.1f' % self.port.cash)

	def update_value(self, output=False):
		'''
		Update the portfolio value
		:return: none
		'''
		self.port.update_port(self.trading_data, self.date)
		if output:
			print('Nav %0.1f' % self.port.portfolio_value+'; Cash:  %0.1f' % self.port.cash+'; Equity: %0.1f' % (self.port.portfolio_value - self.port.cash))

	def update_info(self,date,trading_data):
		'''
		Get the new trading data and update the trade information
		:param date: trading date
		:param trading_data: trading data
		:return: none
		'''
		# add trading data
		self.trading_data = trading_data.reset_index().set_index('sec_code')
		self.trading_data.loc[:, 'adj_close'] = self.trading_data.loc[:, 'close']*self.trading_data.loc[:, 'adjfactor']
		self.trading_data.loc[:, 'adj_trade'] = (self.trading_data.loc[:, self.price]*self.trading_data.loc[:, 'adjfactor'])
		self.trade_info = (self.trading_data.loc[:, ['adj_close', 'adj_trade', 'trade_status', 'maxupordown']]).to_dict(orient='index')
		self.date = date

		# reset the daily trading variable
		self.trade_cost = 0.0
		self.trade_amount = 0.0
		self.order_count = 0.0
		self.order_list = []
		#
		self.update_trigger = True # Finish data update
		self.execute_trigger = False

	def order(self, symbol, amount):
		'''
		Standard trade order
		:param symbol: stock symbol
		:param amount: order size
		:return:
		'''

		self.order_list.append(OrderNum(symbol, amount, self.date))
		self.order_count += 1

	def order_to(self, symbol, amount):
		'''

		:param symbol: stock symbol
		:param amount: target position
		:return: none
		'''
		self.order_list.append(OrderNumTo(symbol, amount, self.date))
		self.order_count += 1

	def order_pct(self, symbol, pct):
		'''

		:param symbol: stock symbol
		:param pct: order size (pct of value)
		:return: none
		'''
		self.order_list.append(OrderPct(symbol, pct, self.date))
		self.order_count += 1

	def order_pct_to(self, symbol, pct):
		'''

		:param symbol: stock symbol
		:param pct: target pct of value
		:return: none
		'''
		self.order_list.append(OrderPctTo(symbol, pct, self.date))
		self.order_count += 1

	def order_short(self, symbol, num):
		'''
		SHory order
		:param symbol: stock symbol
		:param num:
		:return:
		'''

		self.order_list.append(OrderShort(symbol, num, self.date))
		self.order_count += 1


	def portfolio_value(self):
		'''

		:return: portfolio value
		'''
		return self.port.portfolio_value

	def get_cash(self):
		'''

		:return: cash avaiable in the account
		'''
		return self.port.cash


	def get_hist_log(self):
		'''
		Return the dict of historical orders
		:return:
		'''
		return self.trade_log

	def get_hist_perf(self):
		'''
		Return the dict of historical nav
		:return:
		'''
		return self.port.get_hist_log()

	def trade_result(self):
		'''
		Rerurn the trading result
		:return:
		'''
		return self.date, self.trade_amount, self.trade_cost

	def get_position(self, symbol):
		'''
		get the position of a single stock in last trade day from portfolio
		:param symbol: stock symbol
		:return: the position size
		'''
		return self.port.get_position(symbol)

	def get_position_report(self):
		'''
		Return the historical position, close price dataframe
		:return:
		'''
		hist_pos = pd.DataFrame(self.port.get_hist_position_log()).fillna(0)
		hist_close = pd.DataFrame(self.port.get_hist_close_log())
		nav_dict = self.port.get_nav_log()
		hist_nav = pd.DataFrame(list(nav_dict.values()), index=nav_dict.keys())
		cash_dict = self.port.get_cash_log()
		hist_cash = pd.DataFrame(list(cash_dict.values()), index=cash_dict.keys())
		hist_trade = pd.DataFrame(self.trade_log).T
		return hist_pos,hist_close,hist_nav,hist_cash,hist_trade

	def get_weight(self,symbol):
		'''
		get the position of a single stock in last trade day from portfolio
		:param symbol: stock symbol
		:return: the stock weight
		'''
		return self.port.get_weight(symbol)


class Trade_info(object):
	'''
	Trade info class.
	'''
	def __init__(self,cash,symbol,price,maxupordown, status, portfolio_value, position, commission=0.001, short=False):
		self.__cash = cash
		self.__symbol = symbol
		self.__price = price
		self.__maxupordown = maxupordown
		self.__status = status
		self.__position = position
		self.__portfolio_value = portfolio_value
		self.max_amount = self.__calculate_max(cash,price,commission)
		self.min_amount = self.__calculate_min(short,position,cash,price,commission)

	def __calculate_max(self, cash, price, commission):
		'''
		Calculate the largest amount of stock which can be long
		:param cash: cash left in the account
		:param price: stock trade price
		:param commission: commission fee
		:return: largest long amount
		'''
		return math.floor(cash/(price*(1+commission)*100))

	def __calculate_min(self, short, position,cash,price,commission):
		'''
		Calculate the largest amount of stock which can be short
		:param short: whether short is allowed
		:param position: current position
		:return: largest short amount
		'''
		if not short:
			return -position
		else:
			return -self.__calculate_max(cash, price, commission)

	@property
	def symbol(self):
		return self.__symbol

	@property
	def maxupordown(self):
		return self.__maxupordown

	@property
	def status(self):
		return self.__status

	@property
	def position(self):
		return self.__position

	@property
	def portfolio_value(self):
		return self.__portfolio_value

	@property
	def cash(self):
		return self.__cash

	@property
	def price(self):
		return self.__price


class Order(object):
	'''
	Order class
	'''
	def __init__(self,symbol, num, date):
		'''

		:param symbol: stock symbol
		:param num: value for trade amount (pct or amount)
		:param date: trade date
		'''
		self.amount = num
		self.symbol = symbol
		self.__valid_volume = 0.0
		self.__valid_price = 0.0
		self.__date = date
		self.validation = False

	@property
	def valid_price(self):
		return self.__valid_price

	@property
	def valid_volume(self):
		return self.__valid_volume

	@property
	def date(self):
		return self.__date

	def validations(self, trade_amount, info):
		'''
		Validate the order
		:param trade_amount:
		:param info:
		:return:
		'''
		if (not info.maxupordown) and info.status == u'交易':
			self.__valid_volume = min(max(info.min_amount, trade_amount), info.max_amount)
		else:
			self.__valid_volume = 0
		# print('valid_num: %0.2f'%self.__valid_volume)

		self.__valid_price = info.price
		self.validation = True

	def __repr__(self):
		if self.validation:
			return 'Symbol:'+str(self.symbol) + '; price %0.3f'%self.valid_price +'; volume %0.2f' %self.valid_volume +' .'
		else:
			return 'The order has not been validated'


class OrderNum(Order):
	'''

	'''
	def __init__(self, symbol, num, date):
		Order.__init__(self, symbol, num, date)

	def validate(self, info):
		trade_amount = self.amount
		self.validations(trade_amount, info)


class OrderNumTo(Order):
	'''

	'''
	def __init__(self,symbol, num, date):
		Order.__init__(self, symbol, num, date)

	def validate(self, info):
		trade_amount = self.amount - info.position
		self.validations(trade_amount,info)


class OrderPct(Order):
	'''

	'''
	def __init__(self, symbol, num, date):
		Order.__init__(self, symbol, num, date)

	def validate(self, info):
		trade_amount = math.floor(self.amount*info.portfolio_value/(info.price*100))
		self.validations(trade_amount, info)


class OrderPctTo(Order):
	'''

	'''
	def __init__(self, symbol, num, date):
		Order.__init__(self, symbol, num, date)

	def validate(self, info):

		trade_amount = math.floor(self.amount * info.portfolio_value / (info.price * 100))-info.position

		self.validations(trade_amount, info)

class OrderShort(Order):
	'''
	Short order (will be integrated into the normal order in the future)
	'''

	def __init__(self, symbol, num, date):
		Order.__init__(self, symbol, num, date)


	def validate(self, info):
		trade_amount = self.amount

		self.validations(trade_amount, info)

def main():
	pass


def test():
	from datafeed import datafeed
	from portfolio import portfolio
	import random
	bk = broker()
	dd = datafeed(universe='allA')
	dd.initialize()

	for i in range(30):
		date, temp = dd.data_fetch()
		bk.update_info(date, temp)
		x = random.random()
		print('random: %0.3f' %x)
		bk.order_pct_to('000789.SZ', x)
		bk.execute()
		bk.update_value()



if __name__ == '__main__':
	test()



