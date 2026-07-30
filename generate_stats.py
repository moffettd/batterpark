import requests
from datetime import datetime

def fetch_mlb_data():
    today = datetime.now().strftime('%Y-%m-%d')
    print(f"Fetching MLB schedule for {today}...")
    
    # 1. Fetch today's schedule
    sched_url = f"https://statsapi.mlb.com/api/v1/schedule?sportId=1&date={today}"
    try:
        sched_res = requests.get(sched_url, timeout=10).json()
    except Exception as e:
        print(f"Error fetching schedule: {e}")
        return [], today
    
    dates = sched_res.get('dates', [])
    if not dates or not dates[0].get('games'):
        print(f"No MLB games scheduled for {today}.")
        return [], today

    games = dates[0]['games']
    park_data = []

    for game in games:
        # Force venue_id to string so comparison works
        venue_id = str(game.get('venue', {}).get('id', ''))
        venue_name = game.get('venue', {}).get('name', 'Unknown Ballpark')
        away_team = game['teams']['away']['team']
        home_team = game['teams']['home']['team']
        
        print(f"\nProcessing Game: {away_team['name']} @ {home_team['name']} at {venue_name} (ID: {venue_id})")
        
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
                    
                    # Fetch Career Venue Stats AND Season Stats (as fallback)
                    stats_url = f"https://statsapi.mlb.com/api/v1/people/{p_id}/stats?stats=careerByVenue,statsSingleSeason&group=hitting&gameType=R"
                    
                    pa, avg, hr, ops = "-", "-", "-", "-"
                    note = ""
                    found_split = False
                    
                    try:
                        stats_res = requests.get(stats_url, timeout=5).json()
                        stats_group = stats_res.get('stats', [])
                        
                        # 1. Search for Career Venue Match
                        for stat_type in stats_group:
                            if stat_type.get('type', {}).get('displayName') == 'careerByVenue':
                                for split in stat_type.get('splits', []):
                                    # Compare strings to prevent type mismatch
                                    if str(split.get('venue', {}).get('id')) == venue_id:
                                        s = split.get('stat', {})
                                        pa = s.get('plateAppearances', 0)
                                        avg = s.get('avg', '.000')
                                        hr = s.get('homeRuns', 0)
                                        ops = s.get('ops', '.000')
                                        note = "Career at Park"
                                        found_split = True
                                        break
                        
                        # 2. Fallback to Season Total if no games played at this stadium
                        if not found_split:
                            for stat_type in stats_group:
                                if stat_type.get('type', {}).get('displayName') == 'statsSingleSeason':
                                    splits = stat_type.get('splits', [])
                                    if splits:
                                        s = splits[0].get('stat', {})
                                        pa = s.get('plateAppearances', 0)
                                        avg = s.get('avg', '.000')
                                        hr = s.get('homeRuns', 0)
                                        ops = s.get('ops', '.000')
                                        note = "Season Total (No Park History)"
                                        found_split = True
                                        break

                    except Exception as e:
                        print(f"Skipped stats fetch for {p_name}: {e}")

                    if not found_split:
                        pa, avg, hr, ops, note = "0", ".000", "0", ".000", "No Data"

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
            .tag {{ font-size: 0.85em; color: #666; background: #e9ecef; padding: 2px 6px; border-radius: 4px; }}
        </style>
    </head>
    <body>
        <h1>MLB Batter Stats by Ballpark</h1>
        <div class="sub">Career stats at today's stadium (or season totals for first-time visitors) • Updated for {date_str}</div>
    """

    if not park_data:
        html += "<p>No games scheduled for today.</p>"

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
                        <th>Sample Context</th>
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
