with prominents as (
    select
        tp.player_name,
        tp.player_id,
        count(*) num_trades,
        sum(ta.money_investment) vol,
        sum(trader_income - money_investment) trader_pnl,
        '' notes
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
)
select p.*, ls.ltv,
    (year || '-' || month || '-01')::date mm,
    coalesce(sum(case trans_type when 'invest' then -total_amount end), 0) invest,
    coalesce(sum(case trans_type when 'deposit' then total_amount end), 0) deposit,
    coalesce(sum(case trans_type when 'withdrawal' then -total_amount end), 0) withdrawal,
    coalesce(sum(case trans_type when 'bonus' then total_amount end), 0) bonus,
    coalesce(sum(case trans_type when 'income' then total_amount end), 0) income,
    coalesce(sum(case trans_type when 'adjustments' then total_amount end), 0) adjustments
from prominents p
left join (select player_id, sum(total_amount) ltv
    from highlow.mptemptables.tt_lifetime_summary
    where trans_type in (3, 12, 13, 14, 20) --, 53, 62, 63, 64, 70)
    group by player_id
) ls on ls.player_id = p.player_id
left join highlow.mptemptables.tt_monthly_summary ms on ms.player_id = p.player_id
group by 1, 2, 3, 4, 5, 6, 7, mm
order by trader_pnl desc, player_id, mm