import requests
from datetime import datetime, timedelta
import pandas as pd
from pybaseball import statcast_batter, cache

# Enable caching to speed up data fetching
cache.enable()

# Maps MLB Team IDs to Statcast home team codes (so we know which stadium is hosting)
TEAM_ABBREVIATIONS = {
    108: "LAA", 109: "ARI", 110: "BAL", 111: "BOS", 112: "CHC", 113: "CIN", 114: "CLE",
    115: "COL", 116: "DET", 117: "HOU", 118: "KC",  119: "LAD", 120: "WSH", 121: "NYM",
    133: "OAK", 134: "PIT", 135: "SD",  136: "SEA", 137: "SF",  138: "STL", 139: "TB",
    140: "TEX", 141: "TOR", 142: "MIN", 143: "PHI", 144: "ATL", 145: "CWS", 146: "MIA",
    147: "NYY", 158: "MIL"
}

def get_player_park_statcast(p_id, home_team_code, start_date, end_date):
    """
    Fetches Statcast pitch/at-bat data for a batter and filters strictly
    for plate appearances that occurred at the specified host stadium.
    """
    try:
        df = statcast_batter(start_date, end_date, player_id=p_id)
        
        if df is None or df.empty:
            return {"pa": 0, "avg": ".000", "hr": 0, "ops": ".000", "note": "No Statcast Data"}

        # Filter strictly for games where the home team matches today's host stadium
        park_df = df[df['home_team'] == home_team_code].copy()
        
        # Keep only pitch events where a plate appearance outcome occurred
        events_df = park_df[park_df['events'].notna()]
        
        if events_df.empty:
            return {"pa": 0, "avg": ".000", "hr": 0, "ops": ".000", "note": "0 PA at Park"}

        pa = len(events_df)
        
        # Calculate hits, home runs, walks, HBP, sacrifice flies
        hits = events_df['events'].isin(['single', 'double', 'triple', 'home_run']).sum()
        home_runs = (events_df['events'] == 'home_run').sum()
        walks = events_df['events'].isin(['walk', 'intent_walk']).sum()
        hbp = (events_df['events'] == 'hit_by_pitch').sum()
        sac_flies = (events_df['events'] == 'sac_fly').sum()
        
        # Calculate official At-Bats
        non_ab_events = ['walk', 'intent_walk', 'hit_by_pitch', 'sac_fly', 'sac_bunt', 'catcher_interf']
        ab_df = events_df[~events_df['events'].isin(non_ab_events)]
        ab = len(ab_df)

        # Batting Average
        avg_val = (hits / ab) if ab > 0 else 0.0
        avg_str = f"{avg_val:.3f}".lstrip('0') if ab > 0 else ".000"

        # Slugging % components (Total Bases)
        singles = (events_df['events'] == 'single').sum()
        doubles = (events_df['events'] == 'double').sum()
        triples = (events_df['events'] == 'triple').sum()
        total_bases = singles + (doubles * 2) + (triples * 3) + (home_runs * 4)

        # OBP & SLG -> OPS
        obp_denom = (ab + walks + hbp + sac_flies)
        obp = (hits + walks + hbp) / obp_denom if obp_denom > 0 else 0.0
        slg = total_bases / ab if ab > 0 else 0.0
        ops_str = f"{(obp + slg):.3f}".lstrip('0')

        return {
            "pa": pa,
            "avg": avg_str,
            "hr": home_runs,
            "ops": ops_str,
            "note": "PyBaseball Venue Split"
        }

    except Exception as e:
        print(f"Error getting Statcast for player {p_id}: {e}")
        return {"pa": 0, "avg": ".000", "hr": 0, "ops": ".000", "note": "Data Error"}

def fetch_mlb_data():
    today = datetime.now().strftime('%Y-%m-%d')
    
    # 2-year window for Statcast venue data
    start_dt = (datetime.now() - timedelta(days=730)).strftime('%Y-%m-%d')
    end_dt = today
    
    print(f"Fetching schedule for {today} (Statcast window {start_dt} to {end_dt})...")

    sched_url = f"https://statsapi.mlb.com/api/v1/schedule?sportId=1&date={today}"
    try:
        sched_res = requests.get(sched_url, timeout=10).json()
        dates = sched_res.get('dates', [])
    except Exception as e:
        print(f"Error fetching schedule: {e}")
        dates = []

    # Off-season / off-day fallback
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
        home_team_id = game['teams']['home']['team']['id']
        home_code = TEAM_ABBREVIATIONS.get(home_team_id, "NYY")
        
        venue_name = game.get('venue', {}).get('name', 'Ballpark')
        away_team = game['teams']['away']['team']
        home_team = game['teams']['home']['team']
        
        print(f"\nProcessing Game: {away_team['name']} @ {home_team['name']} at {venue_name} (Stadium Code: {home_code})")
        
        game_info = {
            "venue": venue_name,
            "matchup": f"{away_team['name']} @ {home_team['name']}",
            "batters": []
        }

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
                    
                    print(f"Fetching Statcast for {p_name} at {home_code}...")
                    stats = get_player_park_statcast(p_id, home_code, start_dt, end_dt)

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
            .tag-zero {{ font-size: 0.85em; color: #721c24; background: #f8d7da; padding: 3px 8px; border-radius: 4px; }}
        </style>
    </head>
    <body>
        <h1>MLB Batter Stats by Specific Ballpark</h1>
        <div class="sub">Statcast-verified stadium splits • Updated for {date_str}</div>
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
                is_zero = b['pa'] == 0
                tag_class = 'tag-zero' if is_zero else 'tag-park'
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
