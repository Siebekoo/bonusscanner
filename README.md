# Bonusscanner

Collects this week's deals from Albert Heijn, Jumbo, Hoogvliet, Etos, Kruidvat, Dirk, Aldi,
Lidl, PLUS and Makro into one searchable page.

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

## When a store returns 0 deals

Store websites change regularly, so this will happen sometimes.

1. `python scan.py --debug --only <store>`
2. Check `debug/<store>.png`. Is it the correct offers page, or is there a cookie wall or captcha?
3. If the offers page moved, update the URL in `scanner/stores.py`.
4. `debug/<store>_responses.json` contains all data the page loaded. If the deals are there
   but not picked up, add the field names to the lists at the top of `scanner/extract.py`.

## Known limitations

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
- For public repositories with no new commits, GitHub switches scheduled runs off after
  60 days and sends you an email first. Click the link in that email to keep it running.

## Run it on your own PC instead

This only updates the copy on your PC.

- Windows: Task Scheduler → run `python scan.py` daily
- macOS/Linux: `crontab -e` → `0 7 * * * cd /path/to/bonusscanner && .venv/bin/python scan.py`
