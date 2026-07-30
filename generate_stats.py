import requests
from datetime import datetime

def get_player_stats(p_id, venue_id):
    """Fetches player stats at a venue, falling back to season totals if unavailable."""
    # 1. Try fetching career stats split by venue
    venue_url = f"https://statsapi.mlb.com/api/v1/people/{p_id}/stats?stats=statSplits&group=hitting&gameType=R&sitCodes=v{venue_id}"
    
    pa, avg, hr, ops, note = 0, ".000", 0, ".000", "No Data"
    
    try:
        res = requests.get(venue_url, timeout=5).json()
        stats_list = res.get('stats', [])
        if stats_list:
            splits = stats_list[0].get('splits', [])
            if splits:
                s = splits[0].get('stat', {})
                pa = s.get('plateAppearances', 0)
                avg = s.get('avg', '.000')
                hr = s.get('homeRuns', 0)
                ops = s.get('ops', '.000')
                note = "Career at Park"
                return pa, avg, hr, ops, note
    except Exception:
        pass

    # 2. Fallback: Fetch current Season Totals if no venue stats exist yet
    season_url = f"https://statsapi.mlb.com/api/v1/people/{p_id}/stats?stats=statsSingleSeason&group=hitting&gameType=R"
    try:
        res = requests.get(season_url, timeout=5).json()
        stats_list = res.get('stats', [])
        if stats_list:
            splits = stats_list[0].get('splits', [])
            if splits:
                s = splits[0].get('stat', {})
                pa = s.get('plateAppearances', 0)
                avg = s.get('avg', '.000')
                hr = s.get('homeRuns', 0)
                ops = s.get('ops', '.000')
                note = "Season Total"
                return pa, avg, hr, ops, note
    except Exception:
        pass

    return pa, avg, hr, ops, note

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

    # Fallback to Yankee Stadium matchup if no games are scheduled today (offseason/off-day)
    if not dates or not dates[0].get('games'):
        print(f"No active games found for {today}. Using sample matchup (Yankees @ Red Sox) to build page.")
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
        
        print(f"Processing Matchup: {away_team['name']} @ {home_team['name']} at {venue_name} (Venue ID: {venue_id})")
        
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
                    
                    pa, avg, hr, ops, note = get_player_stats(p_id, venue_id)

                    game_info["batters"].append({
                        "name": p_name,
                        "team": team['name'],
                        "pa": pa,
                        "avg": avg,
                        "hr": hr,
                        "ops": ops,
                        "note": note
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
            .tag {{ font-size: 0.85em; color: #333; background: #e2e8f0; padding: 3px 8px; border-radius: 4px; font-weight: 500; }}
        </style>
    </head>
    <body>
        <h1>MLB Batter Stats by Ballpark</h1>
        <div class="sub">Ballpark splits and season metrics • Updated for {date_str}</div>
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
                        <th>Data Context</th>
                    </tr>
                </thead>
                <tbody>
        """
        if not game['batters']:
            html += "<tr><td colspan='7'>No active hitters found for this matchup.</td></tr>"
        else:
            for b in game['batters']:
                html += f"""
                    <tr>
                        <td><strong>{b['name']}</strong></td>
                        <td>{b['team']}</td>
                        <td>{b['pa']}</td>
                        <td>{b['avg']}</td>
                        <td>{b['hr']}</td>
                        <td>{b['ops']}</td>
                        <td><span class="tag">{b['note']}</span></td>
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
