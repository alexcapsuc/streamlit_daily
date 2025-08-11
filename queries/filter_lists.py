assets_list = """
SELECT DISTINCT asset_id, asset_name 
FROM highlow.marketspulse.tfc_assets ast
where ast.asset_name not in ('MPTest')
ORDER BY 1"""

durations_list = """
SELECT DISTINCT fixed_duration_value as duration 
FROM highlow.marketspulse.tfc_option_definition def
where def.status = 1
ORDER BY 1"""
