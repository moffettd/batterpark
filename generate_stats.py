import requests
from datetime import datetime

def get_player_park_stats(p_id, venue_id):
    """
    Queries MLB API for a player's career statistics at a specific ballpark venue.
    """
    # Query using statSplits for specific venue code (v + venue_id)
    url = f"https://statsapi.mlb.com/api/v1/people/{p_id}/stats?stats=statSplits&group=hitting&gameType=R&sitCodes=v{venue_id}"
    
    try:
        res = requests.get(url, timeout=5).json()
        stats_list = res.get('stats', [])
        
        if stats_list:
            splits = stats_list[0].get('splits', [])
            if splits:
                s = splits[0].get('stat', {})
                return {
                    "pa": s.get('plateAppearances', 0),
                    "avg": s.get('avg', '.000'),
                    "hr": s.get('homeRuns', 0),
                    "ops": s.get('ops', '.000'),
                    "note": "Park Career Split"
                }
    except Exception as e:
        pass

    # Secondary method: Query homeAndAway if the player is at home
    # Fallback to season totals if they have never played a single PA at this venue
    season_url = f"https://statsapi.mlb.com/api/v1/people/{p_id}/stats?stats=statsSingleSeason&group=hitting&gameType=R"
    try:
        res = requests.get(season_url, timeout=5).json()
        stats_list = res.get('stats', [])
        if stats_list:
            splits = stats_list[0].get('splits', [])
            if splits:
                s = splits[0].get('stat', {})
                return {
                    "pa": s.get('plateAppearances', 0),
                    "avg": s.get('avg', '.000'),
                    "hr": s.get('homeRuns', 0),
                    "ops": s.get('ops', '.000'),
                    "note": "Overall Season (0 PA at Park)"
                }
    except Exception:
        pass

    return {"pa": 0, "avg": ".000", "hr": 0, "ops": ".000", "note": "No Data"}

def fetch_mlb_data():
    today = datetime.now().strftime('%Y-%m-%d')
    print(f"Fetching MLB schedule for {today}...")
    
    # 1. Fetch today's schedule
    sched_url = f"https://statsapi.mlb.com/api/v1/schedule?sportId=1&date={today}"
    try:
        sched_res = requests.get(sched_url, timeout=10).json()
        dates = sched_res.get('dates', [])
    except Exception as e:
        print(f"Error fetching schedule: {e}")
        dates = []

    # Fallback if no games are scheduled today (offseason/off-day)
    if not dates or not dates[0].get('games'):
        print(f"No games found for {today}. Using Yankee Stadium as test sample.")
        games = [{
            "venue": {"id": 147, "name": "Yankee Stadium"},
            "teams": {
                "away": {"team": {"id": 111, "name": "Boston Red Sox"}},
                "home": {"team": {"id": 147, "name": "New York Yankees"}}
            }
        }]
    else:
        games = dates[0]['games']

    park_data = []

    for game in games:
        venue_id = game.get('venue', {}).get('id')
        venue_name = game.get('venue', {}).get('name', 'Unknown Ballpark')
        away_team = game['teams']['away']['team']
        home_team = game['teams']['home']['team']
        
        print(f"Processing Matchup: {away_team['name']} @ {home_team['name']} at {venue_name} (ID: {venue_id})")
        
        game_info = {
            "venue": venue_name,
            "matchup": f"{away_team['name']} @ {home_team['name']}",
            "batters": []
        }

        # Fetch active rosters for both teams
        for team in [away_team, home_team]:
            roster_url = f"https://statsapi.mlb.com/api/v1/teams/{team['id']}/roster?rosterType=active"
            try:
                roster_res = requests.get(roster_url, timeout=10).json()
                roster = roster_res.get('roster', [])
            except Exception as e:
                print(f"Could not fetch roster for {team['name']}: {e}")
                roster = []

            for player in roster:
                pos = player.get('position', {}).get('abbreviation', '')
                
                # Exclude Pitchers
                if pos not in ['P', 'SP', 'RP']:
                    p_id = player['person']['id']
                    p_name = player['person']['fullName']
                    
                    stats = get_player_park_stats(p_id, venue_id)

                    game_info["batters"].append({
                        "name": p_name,
                        "team": team['name'],
                        "pa": stats['pa'],
                        "avg": stats['avg'],
                        "hr": stats['hr'],
                        "ops": stats['ops'],
                        "note": stats['note']
                    })
                        
        park_data.append(game_info)
    return park_data, today

def build_html(park_data, date_str):
    html = f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>MLB Batter Ballpark Stats - {date_str}</title>
        <style>
            body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; margin: 2rem; background: #f4f6f8; color: #333; }}
            .card {{ background: white; padding: 1.5rem; margin-bottom: 2rem; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }}
            h1 {{ margin-bottom: 0.5rem; }}
            .sub {{ color: #666; margin-bottom: 2rem; }}
            table {{ width: 100%; border-collapse: collapse; margin-top: 1rem; }}
            th, td {{ padding: 10px 12px; text-align: left; border-bottom: 1px solid #ddd; }}
            th {{ background-color: #003366; color: white; }}
            tr:hover {{ background-color: #f8f9fa; }}
            .tag-park {{ font-size: 0.85em; color: #155724; background: #d4edda; padding: 3px 8px; border-radius: 4px; font-weight: 600; }}
            .tag-season {{ font-size: 0.85em; color: #856404; background: #fff3cd; padding: 3px 8px; border-radius: 4px; }}
        </style>
    </head>
    <body>
        <h1>MLB Batter Stats by Ballpark</h1>
        <div class="sub">Career stats at today's stadium • Updated for {date_str}</div>
    """

    for game in park_data:
        html += f"""
        <div class="card">
            <h2>{game['venue']}</h2>
            <h3>{game['matchup']}</h3>
            <table>
                <thead>
                    <tr>
                        <th>Player</th>
                        <th>Team</th>
                        <th>PA</th>
                        <th>AVG</th>
                        <th>HR</th>
                        <th>OPS</th>
                        <th>Stat Source</th>
                    </tr>
                </thead>
                <tbody>
        """
        if not game['batters']:
            html += "<tr><td colspan='7'>No active hitters found for this matchup.</td></tr>"
        else:
            for b in game['batters']:
                is_park = b['note'] == 'Park Career Split'
                tag_class = 'tag-park' if is_park else 'tag-season'
                html += f"""
                    <tr>
                        <td><strong>{b['name']}</strong></td>
                        <td>{b['team']}</td>
                        <td>{b['pa']}</td>
                        <td>{b['avg']}</td>
                        <td>{b['hr']}</td>
                        <td>{b['ops']}</td>
                        <td><span class="{tag_class}">{b['note']}</span></td>
                    </tr>
                """
        html += "</tbody></table></div>"

    html += "</body></html>"
    
    with open("index.html", "w") as f:
        f.write(html)
    print("\nSuccessfully updated index.html!")

if __name__ == "__main__":
    data, date_str = fetch_mlb_data()
    build_html(data, date_str)
