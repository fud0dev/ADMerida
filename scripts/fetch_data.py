import json
import os
from datetime import datetime
from playwright.sync_api import sync_playwright

BASE_URL = "https://www.flashscore.es/equipo/ad-merida/W27VZS9l"
DATA_DIR = "docs/data"
os.makedirs(DATA_DIR, exist_ok=True)

def save_json(name, data):
    if data is not None:
        with open(os.path.join(DATA_DIR, f"{name}.json"), "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

def extract_flashscore_data():
    resultados = []
    partidos = []
    standings = []
    players = []
    noticias = []
    
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page(user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')
            
            # 1. Resultados (Past matches)
            print(f"Scraping Resultados...")
            page.goto(f"{BASE_URL}/resultados/")
            page.wait_for_timeout(3000) # Give it time to load XHRs
            try: page.click('button#onetrust-accept-btn-handler', timeout=2000)
            except: pass
            
            match_elements = page.query_selector_all('.event__match')
            for el in match_elements[:20]: # Top 20 recent matches
                home_el = el.query_selector('.event__homeParticipant')
                away_el = el.query_selector('.event__awayParticipant')
                score_home_el = el.query_selector('.event__score--home')
                score_away_el = el.query_selector('.event__score--away')
                time_el = el.query_selector('.event__time')
                
                home = home_el.inner_text().strip() if home_el else "Unknown"
                away = away_el.inner_text().strip() if away_el else "Unknown"
                score_h = score_home_el.inner_text().strip() if score_home_el else ""
                score_a = score_away_el.inner_text().strip() if score_away_el else ""
                time_str = time_el.inner_text().strip() if time_el else ""
                
                resultados.append({
                    "dateStr": time_str,
                    "home": home,
                    "away": away,
                    "score_home": score_h,
                    "score_away": score_a,
                    "status": "FT" if score_h and score_a else "NS"
                })

            # 2. Partidos (Future matches)
            print(f"Scraping Partidos...")
            page.goto(f"{BASE_URL}/partidos/")
            page.wait_for_timeout(3000)
            match_elements = page.query_selector_all('.event__match')
            for el in match_elements[:20]:
                home_el = el.query_selector('.event__homeParticipant')
                away_el = el.query_selector('.event__awayParticipant')
                time_el = el.query_selector('.event__time')
                
                home = home_el.inner_text().strip() if home_el else "Unknown"
                away = away_el.inner_text().strip() if away_el else "Unknown"
                time_str = time_el.inner_text().strip() if time_el else ""
                
                partidos.append({
                    "dateStr": time_str,
                    "home": home,
                    "away": away,
                    "score_home": "-",
                    "score_away": "-",
                    "status": "NS"
                })

            # 3. Clasificación
            print(f"Scraping Clasificación...")
            page.goto(f"{BASE_URL}/clasificacion/")
            page.wait_for_timeout(3000)
            rows = page.query_selector_all('.ui-table__row')
            for row in rows:
                rank_el = row.query_selector('.tableCellRank')
                name_el = row.query_selector('.tableCellParticipant__name')
                pts_el = row.query_selector('.table__cell--points')
                diff_el = row.query_selector('.table__cell--goalsForAgainstDiff')
                played_el = row.query_selector('.table__cell[title="Partidos jugados"]') 
                # Flashscore often uses a generic class for columns. Wait, we can get children.
                
                if not rank_el or not name_el or not pts_el: continue
                rank_text = rank_el.inner_text().replace('.', '').strip()
                if not rank_text.isdigit(): continue
                
                rank = int(rank_text)
                name = name_el.inner_text().strip()
                points = int(pts_el.inner_text().strip())
                diff = 0
                if diff_el:
                    try: diff = int(diff_el.inner_text().replace('+', '').strip())
                    except: pass
                
                standings.append({
                    "rank": rank,
                    "team": {"name": name, "id": (2501 if "Mérida" in name else rank)},
                    "points": points,
                    "goalsDiff": diff
                })

            # 4. Plantilla
            print(f"Scraping Plantilla...")
            page.goto(f"{BASE_URL}/plantilla/")
            page.wait_for_timeout(3000)
            player_elements = page.query_selector_all('.lineupTable__title, .lineupTable__row')
            current_pos = "Jugadores"
            for el in player_elements:
                class_name = el.get_attribute('class') or ''
                if 'lineupTable__title' in class_name:
                    current_pos = el.inner_text().strip()
                elif 'lineupTable__row' in class_name:
                    name_el = el.query_selector('.lineupTable__cell--name')
                    age_el = el.query_selector('.lineupTable__cell--age')
                    if not name_el: continue
                    
                    name = name_el.inner_text().strip()
                    age = age_el.inner_text().strip() if age_el else ""
                    if name:
                        players.append({
                            "name": name,
                            "age": age,
                            "pos": current_pos
                        })

            # 5. Noticias
            print(f"Scraping Noticias...")
            page.goto(f"{BASE_URL}/noticias/")
            page.wait_for_timeout(3000)
            news_elements = page.query_selector_all('a.news__item, a[class*="news"]')
            for el in news_elements[:10]:
                title_el = el.query_selector('.newsArticle__title, [class*="title"]')
                source_el = el.query_selector('.newsArticle__source, [class*="source"]')
                date_el = el.query_selector('.newsArticle__time, [class*="time"]')
                
                # Check innerText directly if child missing
                title = title_el.inner_text().strip() if title_el else el.inner_text().strip()
                source = source_el.inner_text().strip() if source_el else "Flashscore"
                date_str = date_el.inner_text().strip() if date_el else ""
                href = el.get_attribute("href") or "#"
                if not href.startswith("http"):
                    href = "https://www.flashscore.es" + href
                
                if title:
                    noticias.append({
                        "title": title[:100] + "..." if len(title) > 100 else title,
                        "source": source,
                        "date": date_str,
                        "url": href
                    })

            browser.close()
    except Exception as e:
        print(f"Error scraping with Playwright: {e}")

    return resultados, partidos, standings, players, noticias

def main():
    metadata = {
        "last_updated": datetime.now().isoformat(),
        "status": "success",
        "mode": "playwright_flashscore_tabs"
    }

    print("Starting Flashscore Playwright Extra Scraper...")
    resultados, partidos, standings, players, noticias = extract_flashscore_data()

    save_json("resultados", {"response": resultados})
    save_json("partidos", {"response": partidos})
    save_json("standings", {"response": [{"league": {"standings": [standings]}}]})
    save_json("players", {"response": [{"player": p} for p in players]})
    save_json("news", noticias)
    save_json("metadata", metadata)

    print("Scraping update complete.")

if __name__ == "__main__":
    main()
