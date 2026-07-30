import requests
from datetime import datetime

def get_player_park_career_stats(p_id, venue_id):
    """
    Fetches a player's full career hitting history specifically at today's venue_id
    by summing up their year-by-year venue splits.
    """
    # Force venue_id to int for strict checking
    target_venue_id = int(venue_id)
    
    # Query MLB API for year-by-year stats with venue hydration
    url = f"https://statsapi.mlb.com/api/v1/people/{p_id}/stats?stats=yearByYear&group=hitting&gameType=R&hydrate=venue"
    
    try:
        res = requests.get(url, timeout=5).json()
        stats_list = res.get('stats', [])
        
        total_pa = 0
        total_ab = 0
        total_hits = 0
        total_hr = 0
        total_bb = 0
        total_hbp = 0
        total_sf = 0
        total_tb = 0  # Total bases for slugging
        found_at_park = False

        if stats_list:
            splits = stats_list[0].get('splits', [])
            for split in splits:
                v_id = split.get('venue', {}).get('id')
                if v_id == target_venue_id:
                    s = split.get('stat', {})
                    total_pa += s.get('plateAppearances', 0)
                    total_ab += s.get('atBats', 0)
                    total_hits += s.get('hits', 0)
                    total_hr += s.get('homeRuns', 0)
                    total_bb += s.get('baseOnBalls', 0)
                    total_hbp += s.get('hitByPitch', 0)
                    total_sf += s.get('sacFlies', 0)
                    total_tb += s.get('totalBases', 0)
                    found_at_park = True

        if found_at_park and total_pa > 0:
            # Calculate batting average
            avg = f"{(total_hits / total_ab):.3f}".lstrip('0') if total_ab > 0 else ".000"
            
            # Calculate OBP and SLG for OPS
            obp_denom = (total_ab + total_bb + total_hbp + total_sf)
            obp = (total_hits + total_bb + total_hbp) / obp_denom if obp_denom > 0 else 0.0
            slg = total_tb / total_ab if total_ab > 0 else 0.0
            ops = f"{(obp + slg):.3f}".lstrip('0')

            return {
                "pa": total_pa,
                "avg": avg,
                "hr": total_hr,
                "ops": ops,
                "note": "Career at Park"
            }
    except Exception as e:
        pass

    # Fallback to current season totals if no games have been played at this park yet
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
                    "note": "Season Total (0 PA at Park)"
                }
    except Exception:
        pass

    return {"pa": 0, "avg": ".000", "hr": 0, "ops": ".000", "note": "No Data"}

def fetch_mlb_data():
    today = datetime.now().strftime('%Y-%m-%d')
    print(f"Fetching MLB schedule for {today}...")
    
    # Fetch today's schedule
    sched_url = f"https://statsapi.mlb.com/api/v1/schedule?sportId=1&date={today}"
    try:
        sched_res = requests.get(sched_url, timeout=10).json()
        dates = sched_res.get('dates', [])
    except Exception as e:
        print(f"Error fetching schedule: {e}")
        dates = []

    # Fallback if no games are scheduled today (off-day / off-season)
    if not dates or not dates[0].get('games'):
        print(f"No games found for {today}. Using test sample matchup.")
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
                
                # Filter out pitchers
                if pos not in ['P', 'SP', 'RP']:
                    p_id = player['person']['id']
                    p_name = player['person']['fullName']
                    
                    stats = get_player_park_career_stats(p_id, venue_id)

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
                        <th>PA at Park</th>
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
                is_park = b['note'] == 'Career at Park'
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
