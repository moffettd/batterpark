import requests
from datetime import datetime, timedelta
import pandas as pd
from pybaseball import statcast, cache

cache.enable()

TEAM_ABBREVIATIONS = {
    108: "LAA", 109: "ARI", 110: "BAL", 111: "BOS", 112: "CHC", 113: "CIN", 114: "CLE",
    115: "COL", 116: "DET", 117: "HOU", 118: "KC",  119: "LAD", 120: "WSH", 121: "NYM",
    133: "ATH", 134: "PIT", 135: "SD",  136: "SEA", 137: "SF",  138: "STL", 139: "TB",
    140: "TEX", 141: "TOR", 142: "MIN", 143: "PHI", 144: "ATL", 145: "CWS", 146: "MIA",
    147: "NYY", 158: "MIL"
}

def fetch_mlb_data():
    today = datetime.now().strftime('%Y-%m-%d')
    start_dt = (datetime.now() - timedelta(days=1095)).strftime('%Y-%m-%d')
    end_dt = today
    
    print(f"Fetching schedule for {today}...")

    sched_url = f"https://statsapi.mlb.com/api/v1/schedule?sportId=1&date={today}"
    try:
        sched_res = requests.get(sched_url, timeout=10).json()
        dates = sched_res.get('dates', [])
    except Exception as e:
        print(f"Error fetching schedule: {e}")
        dates = []

    games = []
    if dates and dates[0].get('games'):
        games = [g for g in dates[0]['games'] if g.get('gameType') == 'R']

    if not games:
        print(f"No regular season games on {today}. Displaying sample game.")
        games = [{
            "venue": {"id": 147, "name": "Yankee Stadium"},
            "teams": {
                "away": {"team": {"id": 111, "name": "Boston Red Sox"}},
                "home": {"team": {"id": 147, "name": "New York Yankees"}}
            }
        }]

    print(f"Pulling bulk 3-Year Statcast dataset ({start_dt} to {end_dt})...")
    try:
        full_df = statcast(start_dt=start_dt, end_dt=end_dt)
    except Exception as e:
        print(f"Statcast bulk fetch error: {e}")
        full_df = pd.DataFrame()

    park_data = []

    for game in games:
        home_team = game['teams']['home']['team']
        away_team = game['teams']['away']['team']
        home_team_id = home_team['id']
        
        home_code = TEAM_ABBREVIATIONS.get(home_team_id, "NYY")
        venue_name = game.get('venue', {}).get('name', 'Ballpark')
        
        print(f"\nProcessing Game: {away_team['name']} @ {home_team['name']} at {venue_name} (Code: {home_code})")
        
        game_info = {
            "venue": venue_name,
            "matchup": f"{away_team['name']} @ {home_team['name']}",
            "batters": []
        }

        player_map = {}
        for team in [away_team, home_team]:
            roster_url = f"https://statsapi.mlb.com/api/v1/teams/{team['id']}/roster?rosterType=active"
            try:
                roster_res = requests.get(roster_url, timeout=10).json()
                for p in roster_res.get('roster', []):
                    pos = p.get('position', {}).get('abbreviation', '')
                    if pos not in ['P', 'SP', 'RP']:
                        player_map[p['person']['id']] = {
                            "name": p['person']['fullName'],
                            "team": team['name']
                        }
            except Exception as e:
                print(f"Could not fetch roster for {team['name']}: {e}")

        if full_df is not None and not full_df.empty:
            df = full_df[full_df['home_team'] == home_code]
        else:
            df = pd.DataFrame()

        for p_id, p_info in player_map.items():
            pa, avg, hr, ops, note = 0, ".000", 0, ".000", "0 PA at Park (3-Yr)"
            
            if not df.empty and 'batter' in df.columns:
                p_df = df[df['batter'] == p_id]
                events_df = p_df[p_df['events'].notna()]
                
                if not events_df.empty:
                    pa = len(events_df)
                    hits = events_df['events'].isin(['single', 'double', 'triple', 'home_run']).sum()
                    hr = (events_df['events'] == 'home_run').sum()
                    walks = events_df['events'].isin(['walk', 'intent_walk']).sum()
                    hbp = (events_df['events'] == 'hit_by_pitch').sum()
                    sac_flies = (events_df['events'] == 'sac_fly').sum()
                    
                    non_ab = ['walk', 'intent_walk', 'hit_by_pitch', 'sac_fly', 'sac_bunt', 'catcher_interf']
                    ab_df = events_df[~events_df['events'].isin(non_ab)]
                    ab = len(ab_df)

                    avg_val = (hits / ab) if ab > 0 else 0.0
                    avg = f"{avg_val:.3f}".lstrip('0') if ab > 0 else ".000"

                    singles = (events_df['events'] == 'single').sum()
                    doubles = (events_df['events'] == 'double').sum()
                    triples = (events_df['events'] == 'triple').sum()
                    total_bases = singles + (doubles * 2) + (triples * 3) + (hr * 4)

                    obp_denom = (ab + walks + hbp + sac_flies)
                    obp = (hits + walks + hbp) / obp_denom if obp_denom > 0 else 0.0
                    slg = total_bases / ab if ab > 0 else 0.0
                    ops = f"{(obp + slg):.3f}".lstrip('0')
                    note = "Statcast 3-Yr Park Split"

            game_info["batters"].append({
                "name": p_info['name'],
                "team": p_info['team'],
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
            h1 {{ margin-bottom: 0.5rem; }}
            .sub {{ color: #666; margin-bottom: 2rem; }}
            
            /* Collapsible Card Styling */
            details.card {{
                background: white;
                border-radius: 8px;
                box-shadow: 0 2px 4px rgba(0,0,0,0.1);
                margin-bottom: 1.5rem;
                overflow: hidden;
            }}
            
            summary {{
                padding: 1.25rem 1.5rem;
                background: #ffffff;
                cursor: pointer;
                user-select: none;
                display: flex;
                justify-content: space-between;
                align-items: center;
                border-bottom: 1px solid #eee;
                transition: background 0.2s ease;
            }}
            summary:hover {{
                background: #f8f9fa;
            }}
            summary h2 {{ margin: 0; font-size: 1.25rem; color: #003366; }}
            summary h3 {{ margin: 0; font-size: 1rem; color: #555; font-weight: normal; }}
            summary .toggle-icon {{
                font-size: 0.9rem;
                color: #888;
                font-weight: bold;
            }}

            /* Table & Sticky Header Styling */
            .table-container {{
                max-height: 500px;
                overflow-y: auto;
                padding: 0 1.5rem 1.5rem 1.5rem;
            }}
            table {{
                width: 100%;
                border-collapse: collapse;
                margin-top: 1rem;
            }}
            th, td {{
                padding: 10px 12px;
                text-align: left;
                border-bottom: 1px solid #ddd;
            }}
            th {{
                background-color: #003366;
                color: white;
                position: sticky;
                top: 0;
                z-index: 10;
                box-shadow: 0 1px 0 #003366;
            }}
            tr:hover {{ background-color: #f8f9fa; }}
            
            /* Stat Badges */
            .tag-park {{ font-size: 0.85em; color: #155724; background: #d4edda; padding: 3px 8px; border-radius: 4px; font-weight: 600; }}
            .tag-zero {{ font-size: 0.85em; color: #721c24; background: #f8d7da; padding: 3px 8px; border-radius: 4px; }}
        </style>
    </head>
    <body>
        <h1>MLB Batter Stats by Ballpark</h1>
        <div class="sub">Statcast-verified venue splits (3-Year Window) • Updated for {date_str}</div>
    """

    for game in park_data:
        html += f"""
        <details class="card" open>
            <summary>
                <div>
                    <h2>{game['venue']}</h2>
                    <h3>{game['matchup']}</h3>
                </div>
                <span class="toggle-icon">▼ Toggle Game</span>
            </summary>
            <div class="table-container">
                <table>
                    <thead>
                        <tr>
                            <th>Player</th>
                            <th>Team</th>
                            <th>PA at Park (3-Yr)</th>
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
        html += "</tbody></table></div></details>"

    html += "</body></html>"
    
    with open("index.html", "w") as f:
        f.write(html)
    print("\nSuccessfully updated index.html with sticky headers and collapsible cards!")

if __name__ == "__main__":
    data, date_str = fetch_mlb_data()
    build_html(data, date_str)
