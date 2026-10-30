# TikTok Shop Dataset — Hackathon for Good Youth Edition #2

## Wat zit erin?

Deze dataset bevat **19 dagen** aan dagelijkse snapshots van het Amerikaanse TikTok Shop-platform (9 t/m 27 oktober 2026). Elke nacht zijn dezelfde producten en accounts opnieuw opgehaald, zodat je veranderingen over tijd kunt volgen.

### Twee bestanden

| Bestand | Rijen | Wat erin zit |
|---|---|---|
| `products.csv` | 3.326 | Elke rij = 1 product op 1 dag. Prijs, aantal verkocht, beoordelingen, categorie, merk. |
| `accounts.csv` | 245 | Elke rij = 1 TikTok-account op 1 dag. Volgers, likes, aantal video's. |

### Welke merken?

| Merk | Categorie | Waarom tieners het kennen |
|---|---|---|
| Bubble Skincare | skincare | Gemaakt voor Gen Z, enorm populair op TikTok |
| Goli Nutrition | gezondheid | Appelazijn-gummies, viraal op TikTok |
| medicube | skincare | Virale porienzuiger uit Korea |
| e.l.f. Cosmetics | make-up | Betaalbare virale make-up |
| The Ordinary | skincare | Betaalbare wetenschappelijke skincare |
| COSRX | skincare | Koreaanse skincare, viraal op TikTok |
| NYX Professional Makeup | make-up | Favoriete drogisterij-make-up |
| Sol de Janeiro | bodycare | Virale Bum Bum Cream |
| CeraVe | skincare | #1 skincare-merk op TikTok |
| Starface | skincare | Stervormige puistjespleisters |

Plus 3 creators: Hyram (skincare), Mikayla Nogueira (beauty), Rocio (make-up).

## Kolommen in products.csv

| Kolom | Betekenis |
|---|---|
| `date` | Datum van de snapshot (JJJJ-MM-DD) |
| `title` | Productnaam |
| `store_name` | Naam van de winkel/het merk |
| `category` | Productcategorie (soms in het Spaans of Engels) |
| `currency` | Valuta (altijd USD) |
| `initial_price` | Oorspronkelijke prijs |
| `final_price` | Huidige prijs |
| `discount_percent` | Kortingspercentage (leeg = geen korting) |
| `sold` | Aantal verkochte stuks. **Dit is het belangrijkste veld voor de PostNL-challenge.** TikTok rondt af: grote aantallen zijn afgerond op 1.000-tallen. |
| `reviews_count` | Aantal beoordelingen |
| `prodct_rating` | Gemiddelde beoordeling (0-5) |
| `In_stock` | Op voorraad? (True/False) |
| `available` | Beschikbaar? (True/False) |
| `colors` | Beschikbare kleuren |
| `sizes` | Beschikbare maten |
| `shipping_fee` | Verzendkosten in USD |
| `brand` | Merknaam |

## Kolommen in accounts.csv

| Kolom | Betekenis |
|---|---|
| `date` | Datum van de snapshot |
| `handle` | TikTok-gebruikersnaam (zonder @) |
| `nickname` | Weergavenaam |
| `followers` | Aantal volgers |
| `following` | Aantal accounts dat ze volgen |
| `likes` | Totaal aantal likes op alle video's |
| `videos_count` | Aantal geplaatste video's |
| `is_verified` | Geverifieerd account? (True/False) |
| `biography` | Biografie-tekst |

## Ideeën voor analyse

- **Verkoopsnelheid:** hoe verandert `sold` per dag per product? Welke producten groeien het snelst?
- **Hype vs. verkoop:** voorspelt groei in volgers/likes een piek in verkopen?
- **Prijseffect:** leiden kortingen tot meer verkopen?
- **Merkvergelijking:** skincare vs. make-up vs. gezondheid — welke categorie verkoopt het meest?
- **De PostNL-hoek:** welke producten genereren de meeste pakketjes? Denk aan productgrootte (puistjespleisters = brievenbuspakket, skincare-set = groot pakket).
- **Datakwaliteit:** twee nachten (22 en 25 okt) hebben minder producten door een tijdelijke storing bij de databron. Hoe ga je daarmee om?

## Hoe openen?

- **Excel:** dubbelklik op het CSV-bestand, of gebruik Gegevens > Uit tekst/CSV
- **Google Sheets:** uploaden naar Google Drive, openen met Google Sheets
- **Python:** `import pandas as pd; df = pd.read_csv('products.csv')`

## Bron

De data is verzameld via de Bright Data Scraper API van het Amerikaanse TikTok Shop-platform. Het Nederlandse TikTok Shop is nog niet beschikbaar in hun database. De structuur (prijs, verkopen, beoordelingen) is identiek.
