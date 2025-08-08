select
    count(*) num_trades,
    count(distinct ta.trader_id) num_traders,
    sum(money_investment - trader_income) site_profits,
    sum(money_investment) site_volume,
    site_profits / site_volume margin
from highlow.marketspulse.tfc_trade_actions ta
join highlow.marketspulse.tp_players tp on tp.player_id = ta.trader_id 
where ta.trading_time between {start} and {end}
and tp.account_type = 0
and ta.status in (2, 4)