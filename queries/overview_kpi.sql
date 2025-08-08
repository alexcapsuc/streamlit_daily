SELECT
    SUM(deposit_amount) AS TOTAL_DEPOSITS,
    SUM(withdrawal_amount) AS TOTAL_WITHDRAWALS,
    SUM(trading_volume) AS TOTAL_VOLUME,
    SUM(profit) AS TOTAL_PROFIT,
    IFF(NULLIF(SUM(trading_volume),0) IS NULL, 0, SUM(profit)/SUM(trading_volume)) AS MARGIN
FROM trading_summary
WHERE date BETWEEN '{start}' AND '{end}'
  AND asset_id IN ({asset_ids})
  AND duration_id IN ({duration_ids});
