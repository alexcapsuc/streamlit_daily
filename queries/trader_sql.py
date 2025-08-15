queries = {
    "all_trades": """
        select trade_action_id, trader_id, 
            case trade_type % 5 when 1 then 'BUY' when 2 then 'SELL' else 'ERR' end SIDE,
            trading_time, trading_strike, close_time, close_strike,
            money_investment VOLUME, trader_income - money_investment PROFIT,
            asset_id, fixed_duration_value::text DURATION
        from highlow.marketspulse.tfc_trade_actions ta
        join highlow.marketspulse.tfc_option_instances ins on ins.option_instance_id = ta.option_instance_id
        join highlow.marketspulse.tfc_option_definition def on def.option_def_id = ins.option_def_id 
        where trader_id = {trader_id} 
        and trading_time between {start_time} and {end_time} 
        """,
    "rtd_for_trades": """
        select asset_id, timestamp, sender_timestamp, real_strike PRICE
        from highlow.marketspulse.tfc_real_time_data
        where asset_id = {asset_id}
        and timestamp between {start_ts} and {end_ts}
        order by timestamp
        """
}