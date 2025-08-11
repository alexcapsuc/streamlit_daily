select player_name as username,
    player_id 
from highlow.marketspulse.tp_players
where player_id = {trader_id}