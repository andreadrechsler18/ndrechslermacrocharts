"""
Fetch Federal Reserve Industrial Production data via FRED API.

Covers all ~220 series from the G.17 release matching the detailed
industry breakdown (mining, utilities, and manufacturing by NAICS subsector).
"""

import os
import sys
import time
from datetime import datetime

sys.path.insert(0, os.path.dirname(__file__))
from utils import load_api_keys, write_json, retry_request

FRED_URL = "https://api.stlouisfed.org/fred/series/observations"

# Complete Industrial Production series list organized by sector.
# Each entry: (FRED series ID, short display name)
IP_SERIES = [
    # === MINING ===
    ("IPG211S", "Oil and gas extraction"),
    ("IPG21112S", "Crude oil"),
    ("IPG21113S", "Natural gas and natural gas liquids"),
    ("IPN21113GS", "Natural gas"),
    ("IPG21113PQS", "Natural gas liquid extraction"),
    ("IPG212S", "Mining (except oil and gas)"),
    ("IPN2121S", "Coal mining"),
    ("IPG2122S", "Metal ore mining"),
    ("IPN21221S", "Iron ore mining"),
    ("IPG21222S", "Gold ore and silver ore mining"),
    ("IPG21223S", "Copper, nickel, lead, and zinc mining"),
    ("IPG2123S", "Nonmetallic mineral mining and quarrying"),
    ("IPG213S", "Support activities for mining"),
    ("IPN213111S", "Drilling oil and gas wells"),

    # === UTILITIES: Electric ===
    ("IPG2211S", "Electric power generation, transmission, and distribution"),
    ("IPG22111S", "Electric power generation"),
    ("IPG221111A4T8S", "Hydroelectric, renewables, and other"),
    ("IPN221111S", "Hydroelectric power generation"),
    ("IPN221114T8S", "Renewables and other electric power generation"),
    ("IPN221112S", "Fossil Fuel electric power generation"),
    ("IPN221113S", "Nuclear electric power generation"),
    ("IPG22112S", "Electric power transmission, control, and distribution"),
    ("IPN22112CS", "Commercial and other electricity sales"),
    ("IPN22112MS", "Industrial electricity sales"),
    ("IPN22112RS", "Residential electricity sales"),

    # === UTILITIES: Gas ===
    ("IPG2212S", "Natural gas distribution"),
    ("IPN2212CS", "Commercial and other gas sales"),
    ("IPN2212MS", "Industrial gas sales"),
    ("IPN2212RS", "Residential gas sales"),
    ("IPN2212TS", "Gas transmission"),

    # === MANUFACTURING: Food ===
    ("IPG311S", "Food"),
    ("IPG3111S", "Animal food"),
    ("IPG3112S", "Grain and oilseed milling"),
    ("IPG3113S", "Sugar and confectionery product"),
    ("IPG3114S", "Fruit and vegetable preserving and specialty food"),
    ("IPG3115S", "Dairy product"),
    ("IPG31151S", "Dairy product (except frozen)"),
    ("IPN311511S", "Fluid milk"),
    ("IPN311512S", "Creamery butter"),
    ("IPN311513S", "Cheese"),
    ("IPN311514S", "Dry, condensed, and evaporated dairy product"),
    ("IPN31152S", "Ice cream and frozen dessert"),
    ("IPG3116S", "Animal slaughtering and processing"),
    ("IPG311611T3S", "Animal (except poultry) slaughtering and meat processing"),
    ("IPN311611T3BS", "Beef"),
    ("IPN311611T3PS", "Pork"),
    ("IPN311611T3ZS", "Miscellaneous meats"),
    ("IPN311615S", "Poultry processing"),
    ("IPN3118S", "Bakeries and tortilla"),
    ("IPG3119S", "Other food"),
    ("IPG31192S", "Coffee and tea"),

    # === MANUFACTURING: Beverage & Tobacco ===
    ("IPG312S", "Beverage and tobacco product"),
    ("IPG3121S", "Beverage"),
    ("IPN31211S", "Soft drink and ice"),
    ("IPN31212S", "Breweries"),
    ("IPG3122S", "Tobacco"),

    # === MANUFACTURING: Textiles ===
    ("IPG313S", "Textile mills"),
    ("IPG3131S", "Fiber, yarn, and thread mills"),
    ("IPG3132S", "Fabric mills"),
    ("IPG3133S", "Textile and fabric finishing and fabric coating mills"),
    ("IPG314S", "Textile product mills"),
    ("IPG3141S", "Textile furnishings mills"),
    ("IPG31411S", "Carpet and rug mills"),
    ("IPG3149S", "Other textile product mills"),

    # === MANUFACTURING: Apparel & Leather ===
    ("IPG315S", "Apparel"),
    ("IPG316S", "Leather and allied product"),

    # === MANUFACTURING: Wood Products ===
    ("IPG321S", "Wood product"),
    ("IPN3211S", "Sawmills and wood preservation"),
    ("IPG3212A9S", "Plywood and misc. wood products"),
    ("IPG3212S", "Veneer, plywood, and engineered wood product"),
    ("IPG321211A2S", "Veneer and plywood"),
    ("IPG321219S", "Reconstituted wood product"),
    ("IPG3219S", "Other wood product"),
    ("IPG32191S", "Millwork"),
    ("IPN32192S", "Wood container and pallet"),
    ("IPG32199S", "All other wood product"),
    ("IPN321991S", "Manufactured home (mobile home)"),

    # === MANUFACTURING: Paper ===
    ("IPG322S", "Paper"),
    ("IPG3221S", "Pulp, paper, and paperboard mills"),
    ("IPN32211S", "Pulp mills"),
    ("IPG32212S", "Paper mills"),
    ("IPN322121S", "Paper (except newsprint) mills"),
    ("IPN32213S", "Paperboard mills"),
    ("IPG3222S", "Converted paper product"),
    ("IPN32221S", "Paperboard container"),
    ("IPG32222S", "Paper bag and coated and treated paper"),
    ("IPG32223A9S", "Other converted paper products"),

    # === MANUFACTURING: Printing ===
    ("IPG323S", "Printing and related support activities"),

    # === MANUFACTURING: Petroleum & Coal ===
    ("IPG324S", "Petroleum and coal products"),
    ("IPG32411S", "Petroleum refineries"),
    ("IPN32411AS", "Aviation fuel and kerosene"),
    ("IPN32411DS", "Distillate fuel oil"),
    ("IPN32411GS", "Automotive gasoline"),
    ("IPN32411RS", "Residual fuel oil"),
    ("IPG32411XS", "Other refinery output"),
    ("IPN32412A9S", "Paving, roofing, and other petroleum and coal products"),

    # === MANUFACTURING: Chemical ===
    ("IPG325S", "Chemical"),
    ("IPG3254S", "Pharmaceutical and medicine"),
    ("IPG3254S84T", "Chemicals except pharmaceuticals and medicines"),
    ("IPG3251S", "Basic chemical"),
    ("IPG32511A9S", "Organic chemicals"),
    ("IPG32512T8S", "Basic inorganic chemicals"),
    ("IPG32512S", "Industrial gas"),
    ("IPG32513S", "Synthetic dye and pigment"),
    ("IPG32518S", "Other basic inorganic chemical"),
    ("IPN32518CS", "Alkalies and chlorine"),
    ("IPG3252S", "Resin, synthetic rubber, and artificial and synthetic fibers and filaments"),
    ("IPG32521S", "Resin and synthetic rubber"),
    ("IPN325211S", "Plastics material and resin"),
    ("IPG325212S", "Synthetic rubber"),
    ("IPG32522S", "Artificial and synthetic fibers and filaments"),
    ("IPG3253S", "Pesticide, fertilizer, and other agricultural chemical"),
    ("IPG3255T9S", "Paints, soaps and toiletries, and other chemical products"),
    ("IPG3255A9S", "Paints and other chemical products"),
    ("IPG3255S", "Paint, coating, and adhesive"),
    ("IPG32551S", "Paint and coating"),
    ("IPG3256S", "Soap, cleaning compound, and toilet preparation"),

    # === MANUFACTURING: Plastics & Rubber ===
    ("IPG326S", "Plastics and rubber products"),
    ("IPG3261S", "Plastics product"),
    ("IPG3262S", "Rubber product"),
    ("IPG32621S", "Tire"),
    ("IPG32622A9S", "Rubber products ex. tires"),

    # === MANUFACTURING: Nonmetallic Mineral ===
    ("IPG327S", "Nonmetallic mineral product"),
    ("IPG3271A4A9S", "Clay, lime, gypsum, and misc. nonmetallic mineral products"),
    ("IPG3271A9S", "Clay and misc. nonmetallic mineral products"),
    ("IPG3271S", "Clay product and refractory"),
    ("IPG32711S", "Pottery, ceramics, and plumbing fixture"),
    ("IPG32712S", "Clay building material and refractories"),
    ("IPG3279S", "Other nonmetallic mineral product"),
    ("IPG3274S", "Lime and gypsum product"),
    ("IPG3272S", "Glass and glass product"),
    ("IPG327213S", "Glass container"),
    ("IPG3273S", "Cement and concrete product"),
    ("IPN32731S", "Cement"),
    ("IPN32732T9S", "Concrete and product"),

    # === MANUFACTURING: Primary Metal ===
    ("IPG331S", "Primary metal"),
    ("IPG3311A2S", "Iron and steel products"),
    ("IPN3311A2RS", "Raw steel"),
    ("IPG3311A2FS", "Coke and products"),
    ("IPN3311A2BS", "Construction steel"),
    ("IPN3311A2CS", "Consumer durable steel"),
    ("IPN3311A2DS", "Can and closure steel"),
    ("IPN3311A2ES", "Equipment steel"),
    ("IPN3311A2ZS", "Miscellaneous steel"),
    ("IPG3313A4S", "Nonferrous except foundries"),
    ("IPG3313S", "Alumina and aluminum production and processing"),
    ("IPN331313PS", "Primary aluminum production"),
    ("IPN331314S", "Secondary smelting and alloying of aluminum"),
    ("IPN331315A8MS", "Misc. aluminum materials"),
    ("IPN331318ES", "Aluminum extruded product"),
    ("IPG3314S", "Nonferrous metal (ex. aluminum) production & processing"),
    ("IPG33141S", "Nonferrous metal (except aluminum) smelting and refining"),
    ("IPG33141CS", "Primary smelting and refining of copper"),
    ("IPN33141NS", "Primary smelting and refining of nonferrous metal (except copper and aluminum)"),
    ("IPG3315S", "Foundries"),

    # === MANUFACTURING: Fabricated Metal ===
    ("IPG332S", "Fabricated metal product"),
    ("IPN3321S", "Forging and stamping"),
    ("IPN3322S", "Cutlery and handtool"),
    ("IPN3323S", "Architectural and structural metals"),
    ("IPG3325S", "Hardware"),
    ("IPN3326S", "Spring and wire product"),
    ("IPG3327S", "Machine shops; turned product; and screw, nut, and bolt"),
    ("IPN3328S", "Coating, engraving, heat treating, and allied activities"),
    ("IPG3329S", "Other fabricated metal product"),
    ("IPG332991S", "Ball and roller bearing"),

    # === MANUFACTURING: Machinery ===
    ("IPG333S", "Machinery"),
    ("IPG3331S", "Agriculture, construction, and mining machinery"),
    ("IPG33311S", "Agricultural implement"),
    ("IPG333111S", "Farm machinery and equipment"),
    ("IPG33312S", "Construction machinery"),
    ("IPN33313S", "Mining and oil and gas field machinery"),
    ("IPG3332S", "Industrial machinery"),
    ("IPG3333A9S", "Commercial & service industry machinery & other general purpose machinery"),
    ("IPG3334T6S", "HVAC, metalworking, and power transmission machinery"),
    ("IPG3334S", "Ventilation, heating, air-conditioning, & commercial refrigeration equipment"),
    ("IPG3335S", "Metalworking machinery"),
    ("IPG3336S", "Engine, turbine, and power transmission equipment"),

    # === MANUFACTURING: Computer & Electronic ===
    ("IPG334S", "Computer and electronic product"),
    ("IPG3341S", "Computer and peripheral equipment"),
    ("IPG3342S", "Communications equipment"),
    ("IPG3343S", "Audio and video equipment"),
    ("IPG3344S", "Semiconductor and other electronic component"),
    ("IPG3345S", "Navigational, measuring, electromedical, control instrument"),

    # === MANUFACTURING: Electrical Equipment ===
    ("IPG335S", "Electrical equipment, appliance, and component"),
    ("IPG3352S", "Household appliance"),
    ("IPG33521S", "Small electrical appliance"),
    ("IPG33522S", "Major appliance"),
    ("IPG335A2S", "Electrical equipment except appliances"),
    ("IPG3351S", "Electric lighting equipment"),
    ("IPG3353S", "Electrical equipment"),
    ("IPG3359S", "Other electrical equipment and component"),
    ("IPG33591S", "Battery"),
    ("IPN33592S", "Communication and energy wire and cable"),
    ("IPG33593T9S", "Other electrical equipment"),

    # === MANUFACTURING: Transportation Equipment ===
    ("IPG336S", "Transportation equipment"),
    ("IPG3361S", "Motor vehicle"),
    ("IPG33611S", "Automobile and light duty motor vehicle"),
    ("IPG336111S", "Automobile"),
    ("IPG336112S", "Light truck and utility vehicle"),
    ("IPG33612S", "Heavy duty truck"),
    ("IPG3362S", "Motor vehicle body and trailer"),
    ("IPG336212S", "Truck trailer"),
    ("IPN336213S", "Motor home"),
    ("IPG336214S", "Travel trailer and camper"),
    ("IPG3363S", "Motor vehicle parts"),
    ("IPG3364S", "Aerospace product and parts"),
    ("IPG336411T3S", "Aircraft and parts"),
    ("IPG3365T9S", "Railroad eq., ships and boats, and other transportation eq."),
    ("IPN3365S", "Railroad rolling stock"),
    ("IPG3366S", "Ship and boat building"),
    ("IPN3369S", "Other transportation equipment"),

    # === MANUFACTURING: Furniture & Misc ===
    ("IPG337S", "Furniture and related product"),
    ("IPN3371S", "Household and institutional furniture and kitchen cabinet"),
    ("IPG3372A9S", "Office and other furniture"),
    ("IPG339S", "Miscellaneous"),
    ("IPN3391S", "Medical equipment and supplies"),

    # === OTHER ===
    ("IPN1133S", "Logging"),
    ("IPG5131PS", "Newspaper, periodical, book, and directory publishers"),
    ("IPG51311PS", "Newspaper publishers"),
    ("IPG51312T9PS", "Periodical, book, and other publishers"),
    ("IPG336111BS", "Automobile, business"),
    ("IPG336112BS", "Light trucks, business"),
]


def fetch_fred_series(api_key, series_id, name):
    """Fetch a single FRED series."""
    params = {
        "series_id": series_id,
        "api_key": api_key,
        "file_type": "json",
        "observation_start": "2000-01-01"
    }

    resp = retry_request(FRED_URL, params=params)
    data = resp.json()
    observations = data.get("observations", [])

    points = []
    for obs in observations:
        date_str = obs.get("date", "")
        val_str = obs.get("value", "")
        try:
            value = float(val_str) if val_str and val_str != "." else None
        except ValueError:
            value = None
        if date_str:
            points.append({"date": date_str, "value": value})

    return points


def run():
    print("Fetching Industrial Production data from FRED...")
    print(f"  {len(IP_SERIES)} series to fetch")
    keys = load_api_keys()
    api_key = keys["fred"]

    series_list = []
    errors = []
    for i, (series_id, name) in enumerate(IP_SERIES):
        print(f"  [{i+1}/{len(IP_SERIES)}] {series_id} - {name}...")
        try:
            data = fetch_fred_series(api_key, series_id, name)
        except Exception as e:
            print(f"    Skipping {series_id}: {e}")
            errors.append(series_id)
            continue
        if data and len(data) >= 2:
            series_list.append({
                "id": series_id,
                "name": name,
                "display_order": i,
                "data": data
            })
            print(f"    {len(data)} observations")
        else:
            print(f"    No data for {series_id}")
            errors.append(series_id)
        time.sleep(0.6)  # Stay under FRED rate limit (120 req/min)

    result = {
        "metadata": {
            "title": "Industrial Production",
            "source": "Federal Reserve (FRED)",
            "unit": "Index 2017=100",
            "frequency": "monthly",
            "last_updated": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
        },
        "series": series_list
    }

    write_json(result, "industrial_production/industrial_production.json")
    print(f"\n  {len(series_list)} series written, {len(errors)} errors")
    if errors:
        print(f"  Failed: {', '.join(errors)}")


if __name__ == "__main__":
    run()
