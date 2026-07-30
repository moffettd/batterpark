import requests
from datetime import datetime

def fetch_mlb_data():
    today = datetime.now().strftime('%Y-%m-%d')
    
    # 1. Fetch today's schedule
    sched_url = f"https://statsapi.mlb.com/api/v1/schedule?sportId=1&date={today}"
    sched_res = requests.get(sched_url).json()
    
    dates = sched_res.get('dates', [])
    if not dates or not dates[0].get('games'):
        print("No games scheduled for today.")
        return [], today

    games = dates[0]['games']
    park_data = []

    for game in games:
        venue_id = game['venue']['id']
        venue_name = game['venue']['name']
        away_team = game['teams']['away']['team']
        home_team = game['teams']['home']['team']
        
        game_info = {
            "venue": venue_name,
            "matchup": f"{away_team['name']} @ {home_team['name']}",
            "batters": []
        }

        # Fetch active rosters for both teams
        for team in [away_team, home_team]:
            roster_url = f"https://statsapi.mlb.com/api/v1/teams/{team['id']}/roster"
            roster_res = requests.get(roster_url).json()
            
            for player in roster_res.get('roster', []):
                pos = player.get('position', {}).get('abbreviation', '')
                
                # Exclude Pitchers ('P')
                if pos != 'P':
                    p_id = player['person']['id']
                    p_name = player['person']['fullName']
                    
                    # Correct Venue Query using 'venueId' parameter
                    stats_url = f"https://statsapi.mlb.com/api/v1/people/{p_id}/stats?stats=statSplits&group=hitting&gameType=R&venueId={venue_id}"
                    stats_res = requests.get(stats_url).json()
                    
                    splits = stats_res.get('stats', [{}])[0].get('splits', [])
                    
                    if splits:
                        s = splits[0].get('stat', {})
                        game_info["batters"].append({
                            "name": p_name,
                            "team": team['name'],
                            "pa": s.get('plateAppearances', 0),
                            "avg": s.get('avg', '.000'),
                            "hr": s.get('homeRuns', 0),
                            "ops": s.get('ops', '.000')
                        })
                    else:
                        # Fallback if player has no career stats at this ballpark yet
                        game_info["batters"].append({
                            "name": p_name,
                            "team": team['name'],
                            "pa": 0,
                            "avg": ".000",
                            "hr": 0,
                            "ops": ".000"
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
            th, td {{ padding: 8px 12px; text-align: left; border-bottom: 1px solid #ddd; }}
            th {{ background-color: #003366; color: white; }}
            tr:hover {{ background-color: #f1f1f1; }}
        </style>
    </head>
    <body>
        <h1>MLB Batter Stats by Ballpark</h1>
        <div class="sub">Updated for {date_str}</div>
    """

    if not park_data:
        html += "<p>No games scheduled for today or season is in off-season.</p>"

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
                    </tr>
                </thead>
                <tbody>
        """
        for b in game['batters']:
            html += f"""
                <tr>
                    <td><strong>{b['name']}</strong></td>
                    <td>{b['team']}</td>
                    <td>{b['pa']}</td>
                    <td>{b['avg']}</td>
                    <td>{b['hr']}</td>
                    <td>{b['ops']}</td>
                </tr>
            """
        html += "</tbody></table></div>"

    html += "</body></html>"
    
    with open("index.html", "w") as f:
        f.write(html)

if __name__ == "__main__":
    data, date_str = fetch_mlb_data()
    build_html(data, date_str)
