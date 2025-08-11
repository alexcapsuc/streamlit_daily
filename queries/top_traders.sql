select
    tp.player_name,
    tp.player_id,
    count(*) num_trades,
    sum(ta.money_investment) vol,
    sum(trader_income - money_investment) trader_pnl
from highlow.marketspulse.tfc_trade_actions ta
join highlow.marketspulse.tfc_option_instances ins on ins.option_instance_id = ta.option_instance_id
join highlow.marketspulse.tfc_option_definition def on def.option_def_id = ins.option_def_id
join highlow.marketspulse.tp_players tp on tp.player_id = ta.trader_id 
where ta.trading_time between {start} and {end}
and tp.account_type = 0
and ta.status in (2, 4)
and ({all_durations} = 1 or def.fixed_duration_value in ({durations}))
and ({all_assets} = 1 or def.asset_id in ({assets}))
group by 1, 2
having trader_pnl > {pnl_threshold}
order by trader_pnl desc
limit {limit_rows}