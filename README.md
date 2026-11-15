# Bonusscanner

Collects this week's (and next week's) deals from Albert Heijn, Jumbo, Hoogvliet, Etos,
Kruidvat, Dirk, Aldi, Lidl, PLUS, Vomar, DekaMarkt, Coop, Spar, Action, Gall & Gall and
Makro into one page.

## What the page does

- **Deze week / Volgende week**: deals starting later go to "Volgende week".
- **★ Mijn lijst**: tap ☆ on a product, or type words like "pepsi max". Matching deals
  from every store show up here. Your list is saved on your own device only.
- **Categories** (Zuivel, Drinken, Drogisterij, ...), store chips and search. The first tap
  on a store shows only that store; tap more stores to add them.
- **Vergelijk winkels**: the same product at several stores side by side, cheapest first.
- **Price per kg / liter** on every card, and a sort option for it.
- **Price history tags**: "Beste prijs in 8 weken", "Vaak in de aanbieding", "Nieuw",
  "Was eerder €x". These appear once a few weeks of history exist.
- **Deel**: copies a link that opens the page with your current filters.
- **Dark mode** (🌙 button).
- **Warning bar** when a store returns 0 deals or far fewer than usual, which usually means
  its website changed and the scraper needs fixing.

## Setup (once)

Requires Python 3.10+.

```bash
cd bonusscanner
python -m venv .venv
# Windows:  .venv\Scripts\activate      macOS/Linux:  source .venv/bin/activate
pip install -r requirements.txt
python -m playwright install chromium     # optional if Chrome or Edge is installed
```

## Run

```bash
python scan.py                     # all stores, takes a few minutes
python scan.py --only ah,lidl      # selected stores
python scan.py --show              # show the browser window
python scan.py --debug --only plus # save raw data and screenshots to debug/
python tests/sample_data.py        # preview the page with fake data (output/sample.html)
```

Open `output/deals.html` in a browser. You can search, sort by discount or price, filter
by minimum discount, and click store chips to hide or show a store. Shift-click a chip
to show only that store. The data is also saved in `output/deals.json`.

## How it works

| Store | Method |
|---|---|
| Albert Heijn | The Appie app API (anonymous token, no login) |
| Jumbo | The app API, falling back to the website |
| Others | A headless browser opens the offers page, accepts cookies, scrolls until all offers have loaded, and reads the product data the page loads in the background. If that fails, it reads the product cards shown on the page |

All stores are converted into one format (`scanner/models.py`): product, deal text,
current price, regular price, discount %, size, validity dates, image and link.
Deals come in two types, which are kept separate:

- **Korting** (orange badge): cheaper even if you buy one, e.g. "30% korting" or €2,49 → €1,87.
- **Meer kopen** (blue outlined badge): only cheaper if you buy several, e.g. 1+1 gratis,
  2e halve prijs or 3 voor €5. The badge shows the discount per item *when you buy the
  full amount*: "-50% bij 2". These are listed after the direct discounts by default.

## Price history

Every run saves a small file in `history/` (about 30 KB per day; files older than about a
year are deleted). The online run commits these files to your repository every morning.
Because of that, always click **Sync Changes** in VS Code (it pulls before pushing) rather
than force-pushing, or you'll overwrite the history.

## When a store returns 0 deals

Store websites change regularly, so this will happen sometimes.

1. `python scan.py --debug --only <store>`
2. Check `debug/<store>.png`. Is it the correct offers page, or is there a cookie wall or captcha?
3. If the offers page moved, update the URL in `scanner/stores.py`.
4. `debug/<store>_responses.json` contains all data the page loaded. If the deals are there
   but not picked up, add the field names to the lists at the top of `scanner/extract.py`.

## Known limitations

- **Vomar, DekaMarkt, Coop, Spar and Gall & Gall** were added with their likely offers
  addresses, which could not be tested. If one stays at 0, fix its URL in `scanner/stores.py`.
  Spar applies many deals only in the shopping cart, so it may find little.
- **Categories** come from keywords in the product name. Some products will land in
  "Overig" or the wrong group. Add words to the lists in `scanner/enrich.py`.
- **Vergelijk winkels** matches products by name, so it sometimes groups variants that
  differ slightly (e.g. Coca-Cola and Coca-Cola Zero).
- **Makro** is a wholesaler. Many prices only appear after logging in with a Makro card,
  and prices are usually excl. btw.
- **Lidl and Aldi** split offers by day (e.g. starting Monday, Thursday or Saturday). Some
  appear on separate pages. Add those in `stores.py` under `extra_urls`.
- Prices can differ per store location (Jumbo, PLUS, Dirk). The national online prices are used.
- Use it for personal purposes and don't run it too often. Once a day is plenty.

## Tests

```bash
python tests/test_all.py
```

These tests run offline against a fake shop in `tests/site/`.

## Put it online (free, updates every morning)

The file `.github/workflows/daily.yml` makes GitHub run the scanner every morning and
publish the page at `https://<your-github-name>.github.io/bonusscanner/`.

1. Create a free account on github.com.
2. In VS Code, open the `bonusscanner` folder, go to **Source Control** (the branch icon on
   the left) and click **Publish to GitHub**. Choose **public repository**. Free GitHub Pages
   only works for public repositories.
3. On github.com, open the repository and go to **Settings → Pages**. Under
   "Build and deployment", set **Source** to **GitHub Actions**.
4. Go to the **Actions** tab, click **Daily deals**, then **Run workflow** to run it now.
   It takes about 5 minutes. After that it runs by itself every morning.
5. Share the link from Settings → Pages with your friends.

Notes:
- GitHub's servers are not in the Netherlands. Some stores may block them, even if those
  stores work from your own PC. Check the store chips on the page: dashed ones failed.
- For public repositories without activity, GitHub switches scheduled runs off after
  60 days. The daily history commit should count as activity. If GitHub emails you that the
  workflow will be disabled, click the link in that email to keep it running.

## Run it on your own PC instead

This only updates the copy on your PC.

- Windows: Task Scheduler → run `python scan.py` daily
- macOS/Linux: `crontab -e` → `0 7 * * * cd /path/to/bonusscanner && .venv/bin/python scan.py`
