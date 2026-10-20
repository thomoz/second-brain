# Industry → ETF Quick Reference

Static reference, not auto-generated (unlike `industry-ranking-full.md`). Built
2026-10-20 to answer one question fast: an industry shows up in the Top 10
Rising/Falling of `industry-ranking-full.md` (or `industry-ranking.md`/
`sector-ranking.md`) — which ETF actually tracks it? No trade action implied;
advisor-notes only, same as the rest of `investments/goat/` (see SOUL.md).

Covers all 144 Finviz industries (`industry-ranking-full.md`'s full universe),
alphabetical for lookup. Three tiers, in priority order:

- **Dedicated** — a real, currently-trading, industry-specific ETF. The 39 of these
  are `GOAT_INDUSTRY_ETFS` (`mytrader/config.py`), already researched and verified
  2026-08-23 for the breakout/candidate pipeline — reused here, not re-derived.
- **Related** — no pure-play ETF exists, but a broader multi-industry ETF has real,
  meaningful exposure (e.g. railroads/trucking/airlines all sit inside XTN).
  Verified live via web search 2026-10-20 (holdings, AUM, still trading) — not pulled
  from memory: XRT (retail), XTN (transportation), IAK (insurance), PBJ (food &
  beverage), PPH (pharma), VNQ (REITs), BJK (gaming, already dedicated for Gambling
  but also the closest fit for Resorts & Casinos), MOO (agribusiness, already
  dedicated for Agricultural Inputs but also the closest fit for Farm Products).
- **Sector ETF** — always shown as the fallback. The 11 SPDR Select Sector ETFs
  (`GOAT_SECTOR_ETFS`), same ones already used in `sector-ranking.md`. Guaranteed
  liquid and real; use this when neither of the above exists.

Sector tagging (which of the 11 an industry sits under) follows Finviz's own
grouping where known, otherwise the closest GICS parent — a small number of
consumer retail/staples industries are genuinely borderline (e.g. Discount Stores,
Grocery Stores) and are tagged by practical market behaviour, not a disputed
technicality. Good enough for "which ETF to glance at", not a tax/compliance
classification.

**Caveat:** ETF universe drifts over time (new launches, delistings, issuer
changes) — this file is a snapshot, not re-verified automatically. Spot-check a
ticker before acting on it if this file is more than a few months old.

Every ticker links to its Yahoo Finance holdings page (`finance.yahoo.com/quote/
<TICKER>/holdings/`) — click through to see the actual constituent companies
behind an ETF before picking one to look at individually.

| Industry | Popular ETF(s) | Sector ETF |
|---|---|---|
| Advertising Agencies | — | [XLC](https://finance.yahoo.com/quote/XLC/holdings/) |
| Aerospace & Defense | **[ITA](https://finance.yahoo.com/quote/ITA/holdings/)** (dedicated) | [XLI](https://finance.yahoo.com/quote/XLI/holdings/) |
| Agricultural Inputs | **[MOO](https://finance.yahoo.com/quote/MOO/holdings/)** (dedicated) | [XLB](https://finance.yahoo.com/quote/XLB/holdings/) |
| Airlines | **[JETS](https://finance.yahoo.com/quote/JETS/holdings/)** (dedicated) | [XLI](https://finance.yahoo.com/quote/XLI/holdings/) |
| Airports & Air Services | [XTN](https://finance.yahoo.com/quote/XTN/holdings/) (related — transportation) | [XLI](https://finance.yahoo.com/quote/XLI/holdings/) |
| Aluminum | [PICK](https://finance.yahoo.com/quote/PICK/holdings/) (related — industrial metals) | [XLB](https://finance.yahoo.com/quote/XLB/holdings/) |
| Apparel Manufacturing | — | [XLY](https://finance.yahoo.com/quote/XLY/holdings/) |
| Apparel Retail | [XRT](https://finance.yahoo.com/quote/XRT/holdings/) (related — retail) | [XLY](https://finance.yahoo.com/quote/XLY/holdings/) |
| Asset Management | [IAI](https://finance.yahoo.com/quote/IAI/holdings/) (related — capital markets) | [XLF](https://finance.yahoo.com/quote/XLF/holdings/) |
| Auto & Truck Dealerships | [CARZ](https://finance.yahoo.com/quote/CARZ/holdings/) (related — auto) | [XLY](https://finance.yahoo.com/quote/XLY/holdings/) |
| Auto Manufacturers | **[CARZ](https://finance.yahoo.com/quote/CARZ/holdings/)** (dedicated) | [XLY](https://finance.yahoo.com/quote/XLY/holdings/) |
| Auto Parts | [CARZ](https://finance.yahoo.com/quote/CARZ/holdings/) (related — auto) | [XLY](https://finance.yahoo.com/quote/XLY/holdings/) |
| Banks - Diversified | **[KBWB](https://finance.yahoo.com/quote/KBWB/holdings/)** (dedicated) | [XLF](https://finance.yahoo.com/quote/XLF/holdings/) |
| Banks - Regional | **[KRE](https://finance.yahoo.com/quote/KRE/holdings/)** (dedicated) | [XLF](https://finance.yahoo.com/quote/XLF/holdings/) |
| Beverages - Brewers | [PBJ](https://finance.yahoo.com/quote/PBJ/holdings/) (related — food & beverage) | [XLP](https://finance.yahoo.com/quote/XLP/holdings/) |
| Beverages - Non-Alcoholic | [PBJ](https://finance.yahoo.com/quote/PBJ/holdings/) (related — food & beverage) | [XLP](https://finance.yahoo.com/quote/XLP/holdings/) |
| Beverages - Wineries & Distilleries | [PBJ](https://finance.yahoo.com/quote/PBJ/holdings/) (related — food & beverage) | [XLP](https://finance.yahoo.com/quote/XLP/holdings/) |
| Biotechnology | **[XBI](https://finance.yahoo.com/quote/XBI/holdings/)** (dedicated) | [XLV](https://finance.yahoo.com/quote/XLV/holdings/) |
| Broadcasting | — | [XLC](https://finance.yahoo.com/quote/XLC/holdings/) |
| Building Materials | [XHB](https://finance.yahoo.com/quote/XHB/holdings/) (related — homebuilding-linked) | [XLB](https://finance.yahoo.com/quote/XLB/holdings/) |
| Building Products & Equipment | **[XHB](https://finance.yahoo.com/quote/XHB/holdings/)** (dedicated) | [XLY](https://finance.yahoo.com/quote/XLY/holdings/) |
| Business Equipment & Supplies | — | [XLI](https://finance.yahoo.com/quote/XLI/holdings/) |
| Capital Markets | **[IAI](https://finance.yahoo.com/quote/IAI/holdings/)** (dedicated) | [XLF](https://finance.yahoo.com/quote/XLF/holdings/) |
| Chemicals | — | [XLB](https://finance.yahoo.com/quote/XLB/holdings/) |
| Coking Coal | — | [XLE](https://finance.yahoo.com/quote/XLE/holdings/) |
| Communication Equipment | — | [XLK](https://finance.yahoo.com/quote/XLK/holdings/) |
| Computer Hardware | — | [XLK](https://finance.yahoo.com/quote/XLK/holdings/) |
| Confectioners | [PBJ](https://finance.yahoo.com/quote/PBJ/holdings/) (related — food & beverage) | [XLP](https://finance.yahoo.com/quote/XLP/holdings/) |
| Conglomerates | — | [XLI](https://finance.yahoo.com/quote/XLI/holdings/) |
| Consulting Services | — | [XLI](https://finance.yahoo.com/quote/XLI/holdings/) |
| Consumer Electronics | — | [XLY](https://finance.yahoo.com/quote/XLY/holdings/) |
| Copper | **[COPX](https://finance.yahoo.com/quote/COPX/holdings/)** (dedicated) | [XLB](https://finance.yahoo.com/quote/XLB/holdings/) |
| Credit Services | — | [XLF](https://finance.yahoo.com/quote/XLF/holdings/) |
| Department Stores | [XRT](https://finance.yahoo.com/quote/XRT/holdings/) (related — retail) | [XLY](https://finance.yahoo.com/quote/XLY/holdings/) |
| Diagnostics & Research | — | [XLV](https://finance.yahoo.com/quote/XLV/holdings/) |
| Discount Stores | [XRT](https://finance.yahoo.com/quote/XRT/holdings/) (related — retail) | [XLY](https://finance.yahoo.com/quote/XLY/holdings/) |
| Drug Manufacturers - General | [PPH](https://finance.yahoo.com/quote/PPH/holdings/) (related — pharma) | [XLV](https://finance.yahoo.com/quote/XLV/holdings/) |
| Drug Manufacturers - Specialty & Generic | [PPH](https://finance.yahoo.com/quote/PPH/holdings/) (related — pharma) | [XLV](https://finance.yahoo.com/quote/XLV/holdings/) |
| Education & Training Services | — | [XLY](https://finance.yahoo.com/quote/XLY/holdings/) |
| Electrical Equipment & Parts | — | [XLI](https://finance.yahoo.com/quote/XLI/holdings/) |
| Electronic Components | — | [XLK](https://finance.yahoo.com/quote/XLK/holdings/) |
| Electronic Gaming & Multimedia | **[ESPO](https://finance.yahoo.com/quote/ESPO/holdings/)** (dedicated) | [XLC](https://finance.yahoo.com/quote/XLC/holdings/) |
| Electronics & Computer Distribution | — | [XLK](https://finance.yahoo.com/quote/XLK/holdings/) |
| Engineering & Construction | **[PAVE](https://finance.yahoo.com/quote/PAVE/holdings/)** (dedicated) | [XLI](https://finance.yahoo.com/quote/XLI/holdings/) |
| Entertainment | — | [XLC](https://finance.yahoo.com/quote/XLC/holdings/) |
| Farm & Heavy Construction Machinery | — | [XLI](https://finance.yahoo.com/quote/XLI/holdings/) |
| Farm Products | [MOO](https://finance.yahoo.com/quote/MOO/holdings/) (related — agribusiness) | [XLP](https://finance.yahoo.com/quote/XLP/holdings/) |
| Financial Conglomerates | — | [XLF](https://finance.yahoo.com/quote/XLF/holdings/) |
| Financial Data & Stock Exchanges | [IAI](https://finance.yahoo.com/quote/IAI/holdings/) (related — capital markets) | [XLF](https://finance.yahoo.com/quote/XLF/holdings/) |
| Food Distribution | [PBJ](https://finance.yahoo.com/quote/PBJ/holdings/) (related — food & beverage) | [XLP](https://finance.yahoo.com/quote/XLP/holdings/) |
| Footwear & Accessories | — | [XLY](https://finance.yahoo.com/quote/XLY/holdings/) |
| Furnishings, Fixtures & Appliances | [XHB](https://finance.yahoo.com/quote/XHB/holdings/) (related — homebuilding-linked) | [XLY](https://finance.yahoo.com/quote/XLY/holdings/) |
| Gambling | **[BJK](https://finance.yahoo.com/quote/BJK/holdings/)** (dedicated) | [XLY](https://finance.yahoo.com/quote/XLY/holdings/) |
| Gold | **[GDX](https://finance.yahoo.com/quote/GDX/holdings/)** (dedicated) | [XLB](https://finance.yahoo.com/quote/XLB/holdings/) |
| Grocery Stores | [PBJ](https://finance.yahoo.com/quote/PBJ/holdings/) (related — food & beverage) | [XLP](https://finance.yahoo.com/quote/XLP/holdings/) |
| Health Information Services | — | [XLV](https://finance.yahoo.com/quote/XLV/holdings/) |
| Healthcare Plans | **[IHF](https://finance.yahoo.com/quote/IHF/holdings/)** (dedicated) | [XLV](https://finance.yahoo.com/quote/XLV/holdings/) |
| Home Improvement Retail | [XRT](https://finance.yahoo.com/quote/XRT/holdings/) (related — retail) | [XLY](https://finance.yahoo.com/quote/XLY/holdings/) |
| Household & Personal Products | — | [XLP](https://finance.yahoo.com/quote/XLP/holdings/) |
| Industrial Distribution | — | [XLI](https://finance.yahoo.com/quote/XLI/holdings/) |
| Information Technology Services | — | [XLK](https://finance.yahoo.com/quote/XLK/holdings/) |
| Insurance - Diversified | **[KIE](https://finance.yahoo.com/quote/KIE/holdings/)** (dedicated) | [XLF](https://finance.yahoo.com/quote/XLF/holdings/) |
| Insurance - Life | [IAK](https://finance.yahoo.com/quote/IAK/holdings/) (related — insurance) | [XLF](https://finance.yahoo.com/quote/XLF/holdings/) |
| Insurance - Property & Casualty | [IAK](https://finance.yahoo.com/quote/IAK/holdings/) (related — insurance) | [XLF](https://finance.yahoo.com/quote/XLF/holdings/) |
| Insurance - Reinsurance | [IAK](https://finance.yahoo.com/quote/IAK/holdings/) (related — insurance) | [XLF](https://finance.yahoo.com/quote/XLF/holdings/) |
| Insurance - Specialty | [IAK](https://finance.yahoo.com/quote/IAK/holdings/) (related — insurance) | [XLF](https://finance.yahoo.com/quote/XLF/holdings/) |
| Insurance Brokers | [IAK](https://finance.yahoo.com/quote/IAK/holdings/) (related — insurance) | [XLF](https://finance.yahoo.com/quote/XLF/holdings/) |
| Integrated Freight & Logistics | [XTN](https://finance.yahoo.com/quote/XTN/holdings/) (related — transportation) | [XLI](https://finance.yahoo.com/quote/XLI/holdings/) |
| Internet Content & Information | **[FDN](https://finance.yahoo.com/quote/FDN/holdings/)** (dedicated) | [XLC](https://finance.yahoo.com/quote/XLC/holdings/) |
| Internet Retail | **[IBUY](https://finance.yahoo.com/quote/IBUY/holdings/)** (dedicated) | [XLY](https://finance.yahoo.com/quote/XLY/holdings/) |
| Leisure | — | [XLY](https://finance.yahoo.com/quote/XLY/holdings/) |
| Lodging | — | [XLY](https://finance.yahoo.com/quote/XLY/holdings/) |
| Luxury Goods | — | [XLY](https://finance.yahoo.com/quote/XLY/holdings/) |
| Lumber & Wood Production | **[WOOD](https://finance.yahoo.com/quote/WOOD/holdings/)** (dedicated) | [XLB](https://finance.yahoo.com/quote/XLB/holdings/) |
| Marine Shipping | **[BOAT](https://finance.yahoo.com/quote/BOAT/holdings/)** (dedicated) | [XLI](https://finance.yahoo.com/quote/XLI/holdings/) |
| Medical Care Facilities | — | [XLV](https://finance.yahoo.com/quote/XLV/holdings/) |
| Medical Devices | **[IHI](https://finance.yahoo.com/quote/IHI/holdings/)** (dedicated) | [XLV](https://finance.yahoo.com/quote/XLV/holdings/) |
| Medical Distribution | — | [XLV](https://finance.yahoo.com/quote/XLV/holdings/) |
| Medical Instruments & Supplies | [IHI](https://finance.yahoo.com/quote/IHI/holdings/) (related — medical devices) | [XLV](https://finance.yahoo.com/quote/XLV/holdings/) |
| Metal Fabrication | — | [XLI](https://finance.yahoo.com/quote/XLI/holdings/) |
| Mortgage Finance | [REM](https://finance.yahoo.com/quote/REM/holdings/) (related — mortgage REITs) | [XLF](https://finance.yahoo.com/quote/XLF/holdings/) |
| Oil & Gas Drilling | — | [XLE](https://finance.yahoo.com/quote/XLE/holdings/) |
| Oil & Gas E&P | **[XOP](https://finance.yahoo.com/quote/XOP/holdings/)** (dedicated) | [XLE](https://finance.yahoo.com/quote/XLE/holdings/) |
| Oil & Gas Equipment & Services | **[XES](https://finance.yahoo.com/quote/XES/holdings/)** (dedicated) | [XLE](https://finance.yahoo.com/quote/XLE/holdings/) |
| Oil & Gas Integrated | — | [XLE](https://finance.yahoo.com/quote/XLE/holdings/) |
| Oil & Gas Midstream | — | [XLE](https://finance.yahoo.com/quote/XLE/holdings/) |
| Oil & Gas Refining & Marketing | **[CRAK](https://finance.yahoo.com/quote/CRAK/holdings/)** (dedicated) | [XLE](https://finance.yahoo.com/quote/XLE/holdings/) |
| Other Industrial Metals & Mining | **[PICK](https://finance.yahoo.com/quote/PICK/holdings/)** (dedicated) | [XLB](https://finance.yahoo.com/quote/XLB/holdings/) |
| Other Precious Metals & Mining | [SIL](https://finance.yahoo.com/quote/SIL/holdings/) / [GDX](https://finance.yahoo.com/quote/GDX/holdings/) (related — precious metals) | [XLB](https://finance.yahoo.com/quote/XLB/holdings/) |
| Packaged Foods | [PBJ](https://finance.yahoo.com/quote/PBJ/holdings/) (related — food & beverage) | [XLP](https://finance.yahoo.com/quote/XLP/holdings/) |
| Packaging & Containers | — | [XLB](https://finance.yahoo.com/quote/XLB/holdings/) |
| Paper & Paper Products | — | [XLB](https://finance.yahoo.com/quote/XLB/holdings/) |
| Personal Services | — | [XLY](https://finance.yahoo.com/quote/XLY/holdings/) |
| Pharmaceutical Retailers | — | [XLP](https://finance.yahoo.com/quote/XLP/holdings/) |
| Pollution & Treatment Controls | [EVX](https://finance.yahoo.com/quote/EVX/holdings/) (related — waste/environmental) | [XLI](https://finance.yahoo.com/quote/XLI/holdings/) |
| Publishing | — | [XLC](https://finance.yahoo.com/quote/XLC/holdings/) |
| Railroads | [XTN](https://finance.yahoo.com/quote/XTN/holdings/) (related — transportation) | [XLI](https://finance.yahoo.com/quote/XLI/holdings/) |
| Real Estate - Development | — | [XLRE](https://finance.yahoo.com/quote/XLRE/holdings/) |
| Real Estate - Diversified | — | [XLRE](https://finance.yahoo.com/quote/XLRE/holdings/) |
| Real Estate Services | — | [XLRE](https://finance.yahoo.com/quote/XLRE/holdings/) |
| Recreational Vehicles | — | [XLY](https://finance.yahoo.com/quote/XLY/holdings/) |
| REIT - Diversified | [VNQ](https://finance.yahoo.com/quote/VNQ/holdings/) (related — broad REIT) | [XLRE](https://finance.yahoo.com/quote/XLRE/holdings/) |
| REIT - Healthcare Facilities | [VNQ](https://finance.yahoo.com/quote/VNQ/holdings/) (related — broad REIT) | [XLRE](https://finance.yahoo.com/quote/XLRE/holdings/) |
| REIT - Hotel & Motel | [VNQ](https://finance.yahoo.com/quote/VNQ/holdings/) (related — broad REIT) | [XLRE](https://finance.yahoo.com/quote/XLRE/holdings/) |
| REIT - Industrial | **[INDS](https://finance.yahoo.com/quote/INDS/holdings/)** (dedicated) | [XLRE](https://finance.yahoo.com/quote/XLRE/holdings/) |
| REIT - Mortgage | **[REM](https://finance.yahoo.com/quote/REM/holdings/)** (dedicated) | [XLRE](https://finance.yahoo.com/quote/XLRE/holdings/) |
| REIT - Office | [VNQ](https://finance.yahoo.com/quote/VNQ/holdings/) (related — broad REIT) | [XLRE](https://finance.yahoo.com/quote/XLRE/holdings/) |
| REIT - Residential | [VNQ](https://finance.yahoo.com/quote/VNQ/holdings/) (related — broad REIT) | [XLRE](https://finance.yahoo.com/quote/XLRE/holdings/) |
| REIT - Retail | [VNQ](https://finance.yahoo.com/quote/VNQ/holdings/) (related — broad REIT) | [XLRE](https://finance.yahoo.com/quote/XLRE/holdings/) |
| REIT - Specialty | [VNQ](https://finance.yahoo.com/quote/VNQ/holdings/) (related — broad REIT) | [XLRE](https://finance.yahoo.com/quote/XLRE/holdings/) |
| Rental & Leasing Services | — | [XLI](https://finance.yahoo.com/quote/XLI/holdings/) |
| Residential Construction | **[ITB](https://finance.yahoo.com/quote/ITB/holdings/)** (dedicated) | [XLY](https://finance.yahoo.com/quote/XLY/holdings/) |
| Resorts & Casinos | [BJK](https://finance.yahoo.com/quote/BJK/holdings/) (related — gaming) | [XLY](https://finance.yahoo.com/quote/XLY/holdings/) |
| Restaurants | **[EATZ](https://finance.yahoo.com/quote/EATZ/holdings/)** (dedicated) | [XLY](https://finance.yahoo.com/quote/XLY/holdings/) |
| Scientific & Technical Instruments | — | [XLK](https://finance.yahoo.com/quote/XLK/holdings/) |
| Security & Protection Services | — | [XLI](https://finance.yahoo.com/quote/XLI/holdings/) |
| Semiconductor Equipment & Materials | [SMH](https://finance.yahoo.com/quote/SMH/holdings/) (related — semiconductors) | [XLK](https://finance.yahoo.com/quote/XLK/holdings/) |
| Semiconductors | **[SMH](https://finance.yahoo.com/quote/SMH/holdings/)** (dedicated) | [XLK](https://finance.yahoo.com/quote/XLK/holdings/) |
| Shell Companies | — | [XLF](https://finance.yahoo.com/quote/XLF/holdings/) |
| Silver | **[SIL](https://finance.yahoo.com/quote/SIL/holdings/)** (dedicated) | [XLB](https://finance.yahoo.com/quote/XLB/holdings/) |
| Software - Application | **[IGV](https://finance.yahoo.com/quote/IGV/holdings/)** (dedicated) | [XLK](https://finance.yahoo.com/quote/XLK/holdings/) |
| Software - Infrastructure | [IGV](https://finance.yahoo.com/quote/IGV/holdings/) (related — software) | [XLK](https://finance.yahoo.com/quote/XLK/holdings/) |
| Solar | **[TAN](https://finance.yahoo.com/quote/TAN/holdings/)** (dedicated) | [XLE](https://finance.yahoo.com/quote/XLE/holdings/) |
| Specialty Business Services | — | [XLI](https://finance.yahoo.com/quote/XLI/holdings/) |
| Specialty Chemicals | — | [XLB](https://finance.yahoo.com/quote/XLB/holdings/) |
| Specialty Industrial Machinery | — | [XLI](https://finance.yahoo.com/quote/XLI/holdings/) |
| Specialty Retail | [XRT](https://finance.yahoo.com/quote/XRT/holdings/) (related — retail) | [XLY](https://finance.yahoo.com/quote/XLY/holdings/) |
| Staffing & Employment Services | — | [XLI](https://finance.yahoo.com/quote/XLI/holdings/) |
| Steel | **[SLX](https://finance.yahoo.com/quote/SLX/holdings/)** (dedicated) | [XLB](https://finance.yahoo.com/quote/XLB/holdings/) |
| Telecom Services | **[IYZ](https://finance.yahoo.com/quote/IYZ/holdings/)** (dedicated) | [XLC](https://finance.yahoo.com/quote/XLC/holdings/) |
| Textile Manufacturing | — | [XLY](https://finance.yahoo.com/quote/XLY/holdings/) |
| Thermal Coal | — | [XLE](https://finance.yahoo.com/quote/XLE/holdings/) |
| Tobacco | — | [XLP](https://finance.yahoo.com/quote/XLP/holdings/) |
| Tools & Accessories | — | [XLI](https://finance.yahoo.com/quote/XLI/holdings/) |
| Travel Services | — | [XLY](https://finance.yahoo.com/quote/XLY/holdings/) |
| Trucking | [XTN](https://finance.yahoo.com/quote/XTN/holdings/) (related — transportation) | [XLI](https://finance.yahoo.com/quote/XLI/holdings/) |
| Uranium | **[URA](https://finance.yahoo.com/quote/URA/holdings/)** (dedicated) | [XLE](https://finance.yahoo.com/quote/XLE/holdings/) |
| Utilities - Diversified | — | [XLU](https://finance.yahoo.com/quote/XLU/holdings/) |
| Utilities - Independent Power Producers | — | [XLU](https://finance.yahoo.com/quote/XLU/holdings/) |
| Utilities - Regulated Electric | — | [XLU](https://finance.yahoo.com/quote/XLU/holdings/) |
| Utilities - Regulated Gas | — | [XLU](https://finance.yahoo.com/quote/XLU/holdings/) |
| Utilities - Regulated Water | **[PHO](https://finance.yahoo.com/quote/PHO/holdings/)** (dedicated) | [XLU](https://finance.yahoo.com/quote/XLU/holdings/) |
| Utilities - Renewable | **[ICLN](https://finance.yahoo.com/quote/ICLN/holdings/)** (dedicated) | [XLU](https://finance.yahoo.com/quote/XLU/holdings/) |
| Waste Management | **[EVX](https://finance.yahoo.com/quote/EVX/holdings/)** (dedicated) | [XLI](https://finance.yahoo.com/quote/XLI/holdings/) |

Last built: 2026-10-20.
