# TikTok Shop Dataset — Hackathon for Good Youth Edition #2

## What's in here?

This dataset contains **19 days** of daily snapshots from the US TikTok Shop platform (9–27 October 2026). Every night, the same products and accounts were re-scraped so you can track changes over time.

### Two files

| File | Rows | What's inside |
|---|---|---|
| `products.csv` | 3,326 | One row = 1 product on 1 day. Price, units sold, reviews, category, brand. |
| `accounts.csv` | 245 | One row = 1 TikTok account on 1 day. Followers, likes, video count. |

### Which brands?

| Brand | Category | Why teens know it |
|---|---|---|
| Bubble Skincare | skincare | Made for Gen Z, huge on TikTok |
| Goli Nutrition | health | Apple cider vinegar gummies, viral on TikTok |
| medicube | skincare | Viral pore-suction device from Korea |
| e.l.f. Cosmetics | makeup | Affordable viral makeup |
| The Ordinary | skincare | Affordable science-based skincare |
| COSRX | skincare | Korean skincare, viral on TikTok |
| NYX Professional Makeup | makeup | Drugstore makeup favorite |
| Sol de Janeiro | bodycare | Viral Bum Bum Cream |
| CeraVe | skincare | #1 skincare brand on TikTok |
| Starface | skincare | Star-shaped pimple patches |

Plus 3 creators: Hyram (skincare), Mikayla Nogueira (beauty), Rocio (makeup).

## Columns in products.csv

| Column | Meaning |
|---|---|
| `date` | Snapshot date (YYYY-MM-DD) |
| `title` | Product name |
| `store_name` | Store / brand name |
| `category` | Product category (sometimes in Spanish or English) |
| `currency` | Currency (always USD) |
| `initial_price` | Original price |
| `final_price` | Current price |
| `discount_percent` | Discount percentage (empty = no discount) |
| `sold` | Units sold. **This is the key field for the PostNL challenge.** TikTok rounds large numbers to the nearest 1,000. |
| `reviews_count` | Number of reviews |
| `prodct_rating` | Average rating (0–5) |
| `In_stock` | In stock? (True/False) |
| `available` | Available? (True/False) |
| `colors` | Available colors |
| `sizes` | Available sizes |
| `shipping_fee` | Shipping cost in USD |
| `brand` | Brand name |

## Columns in accounts.csv

| Column | Meaning |
|---|---|
| `date` | Snapshot date |
| `handle` | TikTok username (without @) |
| `nickname` | Display name |
| `followers` | Follower count |
| `following` | Number of accounts they follow |
| `likes` | Total likes across all videos |
| `videos_count` | Number of videos posted |
| `is_verified` | Verified account? (True/False) |
| `biography` | Bio text |

## Analysis ideas

- **Sales velocity:** how does `sold` change day over day per product? Which products are growing fastest?
- **Hype vs. sales:** does follower/like growth on a brand's TikTok account predict sales spikes?
- **Price effect:** do discounts drive more sales?
- **Cross-brand comparison:** skincare vs. makeup vs. health — which category sells the most?
- **The PostNL angle:** which products generate the most parcels? Think about product size (pimple patches = letterbox parcel, skincare set = large box).
- **Data quality:** two nights (Oct 22 and 25) have fewer products due to a temporary issue with the data source. How do you handle that?

## How to open

- **Excel:** double-click the CSV file, or use Data > From Text/CSV
- **Google Sheets:** upload to Google Drive, open with Google Sheets
- **Python:** `import pandas as pd; df = pd.read_csv('products.csv')`

## Source

Data was collected via the Bright Data Scraper API from the US TikTok Shop platform. The Dutch TikTok Shop is not yet available in their database. The data structure (price, sales, reviews) is identical.
