"""Build M3 code -> NAICS mapping based on Census Appendix B."""
import json
import os

# M3 code -> NAICS mapping
# Source: Census "Composition of Industry Categories" (appendixb.pdf)
# https://www.census.gov/manufacturing/m3/historical_data/appendixb.pdf
m3_naics = {
    # Food Products (NAICS 311)
    "11A": {"naics": "3112", "name": "Grain and Oilseed Milling"},
    "11B": {"naics": "3115", "name": "Dairy Product Manufacturing"},
    "11C": {"naics": "3116,3117", "name": "Animal Slaughtering/Processing, Seafood"},
    "11D": {"naics": "311 (other)", "name": "Other Food Manufacturing"},
    "11S": {"naics": "311", "name": "Food Products"},
    # Beverage and Tobacco (NAICS 312)
    "12A": {"naics": "3121", "name": "Beverage Manufacturing"},
    "12B": {"naics": "3122", "name": "Tobacco Manufacturing"},
    "12S": {"naics": "312", "name": "Beverage and Tobacco Products"},
    # Textile Mills (NAICS 313)
    "13A": {"naics": "313", "name": "Textile Mills"},
    "13S": {"naics": "313", "name": "Textile Mills"},
    # Textile Product Mills (NAICS 314)
    "14A": {"naics": "314", "name": "Textile Product Mills"},
    "14S": {"naics": "314", "name": "Textile Product Mills"},
    # Apparel (NAICS 315)
    "15A": {"naics": "315", "name": "Apparel Manufacturing"},
    "15S": {"naics": "315", "name": "Apparel"},
    # Leather (NAICS 316)
    "16A": {"naics": "316", "name": "Leather and Allied Products"},
    "16S": {"naics": "316", "name": "Leather and Allied Products"},
    # Wood Products (NAICS 321)
    "21A": {"naics": "321991,321992", "name": "Wood Building and Mobile Home Mfg"},
    "21B": {"naics": "321 (other)", "name": "Other Wood Product Manufacturing"},
    "21S": {"naics": "321", "name": "Wood Products"},
    # Paper Products (NAICS 322)
    "22A": {"naics": "3221", "name": "Pulp, Paper, and Paperboard Mills"},
    "22B": {"naics": "32221", "name": "Paperboard Container Manufacturing"},
    "22C": {"naics": "3222 (other)", "name": "Other Paper Manufacturing"},
    "22S": {"naics": "322", "name": "Paper Products"},
    # Printing (NAICS 323)
    "23A": {"naics": "323", "name": "Printing and Related Support Activities"},
    "23S": {"naics": "323", "name": "Printing"},
    # Petroleum and Coal (NAICS 324)
    "24A": {"naics": "324110", "name": "Petroleum Refineries"},
    "24B": {"naics": "324121,324122", "name": "Asphalt Paving and Roofing Materials"},
    "24C": {"naics": "324191,324199", "name": "Other Petroleum and Coal Products"},
    "24S": {"naics": "324", "name": "Petroleum and Coal Products"},
    # Chemical Products (NAICS 325)
    "25A": {"naics": "3253", "name": "Pesticides, Fertilizers, Ag Chemicals"},
    "25B": {"naics": "3254", "name": "Pharmaceutical and Medicine Mfg"},
    "25C": {"naics": "3255", "name": "Paint, Coating, and Adhesive Mfg"},
    "25D": {"naics": "325 (other)", "name": "Other Chemical Products"},
    "25S": {"naics": "325", "name": "Chemical Products"},
    # Plastics and Rubber (NAICS 326)
    "26A": {"naics": "32621", "name": "Tire Manufacturing"},
    "26B": {"naics": "326 (other)", "name": "Other Plastics and Rubber Products"},
    "26S": {"naics": "326", "name": "Plastics and Rubber Products"},
    # Nonmetallic Mineral Products (NAICS 327)
    "27A": {"naics": "327", "name": "Nonmetallic Mineral Products"},
    "27S": {"naics": "327", "name": "Nonmetallic Mineral Products"},
    # Primary Metals (NAICS 331)
    "31A": {"naics": "3311,3312", "name": "Iron and Steel Mills and Steel Products"},
    "31B": {"naics": "3313,3314", "name": "Alumina, Aluminum, and Nonferrous Metals"},
    "31C": {"naics": "33151", "name": "Ferrous Metal Foundries"},
    "31D": {"naics": "33152", "name": "Nonferrous Metal Foundries"},
    "31S": {"naics": "331", "name": "Primary Metals"},
    # Fabricated Metal Products (NAICS 332)
    "32A": {"naics": "3321", "name": "Forging and Stamping"},
    "32B": {"naics": "33221", "name": "Cutlery and Handtool Mfg"},
    "32C": {"naics": "3324", "name": "Boiler, Tank, and Shipping Container Mfg"},
    "32D": {"naics": "33291", "name": "Metal Valve Manufacturing"},
    "32E": {"naics": "33299", "name": "Small Arms and Ordnance, Nondefense"},
    "32F": {"naics": "33299", "name": "Small Arms and Ordnance, Defense"},
    "32G": {"naics": "332 (other)", "name": "Other Fabricated Metal Products"},
    "32S": {"naics": "332", "name": "Fabricated Metal Products"},
    # Machinery (NAICS 333)
    "33A": {"naics": "333111", "name": "Farm Machinery and Equipment"},
    "33B": {"naics": "333112", "name": "Lawn/Garden Tractor and Equipment"},
    "33C": {"naics": "333120", "name": "Construction Machinery"},
    "33D": {"naics": "33313", "name": "Mining, Oil and Gas Field Machinery"},
    "33E": {"naics": "33324", "name": "Industrial Machinery"},
    "33F": {"naics": "333318", "name": "Commercial and Service Industry Machinery"},
    "33G": {"naics": "333314,333316", "name": "Photographic Equipment"},
    "33H": {"naics": "33341", "name": "HVAC and Commercial Refrigeration Equipment"},
    "33I": {"naics": "33351", "name": "Metalworking Machinery"},
    "33J": {"naics": "333611", "name": "Turbine and Turbine Generator Set Units"},
    "33K": {"naics": "333612,333613,333618", "name": "Other Power Transmission Equipment"},
    "33L": {"naics": "33391", "name": "Pump and Compressor Mfg"},
    "33M": {"naics": "33392", "name": "Material Handling Equipment"},
    "33N": {"naics": "33399", "name": "All Other Machinery"},
    "33S": {"naics": "333", "name": "Machinery"},
    # Computers and Electronic Products (NAICS 334)
    "34A": {"naics": "334111", "name": "Electronic Computer Mfg"},
    "34B": {"naics": "334112", "name": "Computer Storage Device Mfg"},
    "34C": {"naics": "334118", "name": "Other Computer Peripheral Equipment"},
    "34D": {"naics": "33421,33422,33429", "name": "Communications Equipment, Nondefense"},
    "34E": {"naics": "33421,33422,33429", "name": "Communications Equipment, Defense"},
    "34F": {"naics": "334310", "name": "Audio and Video Equipment"},
    "34G": {"naics": "334413", "name": "Semiconductor Mfg"},
    "34H": {"naics": "33441 (other)", "name": "Other Electronic Components"},
    "34I": {"naics": "334511", "name": "Search/Navigation Equipment, Nondefense"},
    "34J": {"naics": "334511", "name": "Search/Navigation Equipment, Defense"},
    "34K": {"naics": "33451 (other)", "name": "Measuring, Electromedical, Control Instruments"},
    "34L": {"naics": "33461", "name": "Magnetic and Optical Media Mfg"},
    "34S": {"naics": "334", "name": "Computers and Electronic Products"},
    "34X": {"naics": "334", "name": "Computers and Electronic Products Subtotal"},
    # Electrical Equipment (NAICS 335)
    "35A": {"naics": "3351", "name": "Electric Lighting Equipment"},
    "35B": {"naics": "3352", "name": "Household Appliances"},
    "35C": {"naics": "3353", "name": "Electrical Equipment"},
    "35D": {"naics": "33591", "name": "Batteries"},
    "35E": {"naics": "3359 (other)", "name": "Other Electrical Equipment and Components"},
    "35S": {"naics": "335", "name": "Electrical Equipment and Components"},
    # Transportation Equipment (NAICS 336)
    "36A": {"naics": "336111", "name": "Automobile Manufacturing"},
    "36B": {"naics": "336112", "name": "Light Truck and Utility Vehicle Mfg"},
    "36C": {"naics": "336120", "name": "Heavy Duty Truck Manufacturing"},
    "36D": {"naics": "33621", "name": "Motor Vehicle Body and Trailer Mfg"},
    "36E": {"naics": "3363", "name": "Motor Vehicle Parts Mfg"},
    "36F": {"naics": "336411", "name": "Aircraft Manufacturing, Nondefense"},
    "36G": {"naics": "336411", "name": "Aircraft Manufacturing, Defense"},
    "36H": {"naics": "336412,336413", "name": "Aircraft Engine and Parts, Nondefense"},
    "36I": {"naics": "336412,336413", "name": "Aircraft Engine and Parts, Defense"},
    "36K": {"naics": "336510", "name": "Railroad Rolling Stock"},
    "36L": {"naics": "336611,336612", "name": "Ship and Boat Building, Nondefense"},
    "36M": {"naics": "336611,336612", "name": "Ship and Boat Building, Defense"},
    "36P": {"naics": "336414,336415,336419", "name": "Guided Missile/Space Vehicle, Nondefense"},
    "36Q": {"naics": "336414,336415,336419", "name": "Guided Missile/Space Vehicle, Defense"},
    "36R": {"naics": "336992", "name": "Military Armored Vehicle/Tank, Nondefense"},
    "36T": {"naics": "336992", "name": "Military Armored Vehicle/Tank, Defense"},
    "36U": {"naics": "336991,336999", "name": "Other Transportation Equipment"},
    "36S": {"naics": "336", "name": "Transportation Equipment"},
    "36Z": {"naics": "33621,3363", "name": "Motor Vehicle Bodies, Parts, and Trailers"},
    # Furniture (NAICS 337)
    "37A": {"naics": "3371", "name": "Household Furniture and Kitchen Cabinet"},
    "37B": {"naics": "33712,33721", "name": "Office and Institutional Furniture"},
    "37C": {"naics": "3379", "name": "Other Furniture Related Products"},
    "37S": {"naics": "337", "name": "Furniture and Related Products"},
    # Miscellaneous (NAICS 339)
    "39A": {"naics": "33911", "name": "Medical Equipment and Supplies"},
    "39B": {"naics": "33992,33993", "name": "Sporting/Athletic Goods, Doll/Toy/Game"},
    "39C": {"naics": "33994", "name": "Office Supplies (except Paper)"},
    "39D": {"naics": "339 (other)", "name": "Other Miscellaneous Manufacturing"},
    "39S": {"naics": "339", "name": "Miscellaneous Manufacturing"},
    # Aggregate codes (composites)
    "MTM": {"naics": "31-33", "name": "Total Manufacturing", "aggregate": True},
    "MDM": {"naics": "31-33 (durable)", "name": "Durable Goods", "aggregate": True},
    "MNM": {"naics": "31-33 (nondurable)", "name": "Nondurable Goods", "aggregate": True},
    "MXT": {"naics": "31-33 ex 336", "name": "Manufacturing excl. Transportation", "aggregate": True},
    "MXD": {"naics": "31-33 ex defense", "name": "Manufacturing excl. Defense", "aggregate": True},
    "DXT": {"naics": "durable ex 336", "name": "Durable Goods excl. Transportation", "aggregate": True},
    "DXD": {"naics": "durable ex defense", "name": "Durable Goods excl. Defense", "aggregate": True},
    "TCG": {"naics": "composite", "name": "Capital Goods", "aggregate": True},
    "NDE": {"naics": "composite", "name": "Nondefense Capital Goods", "aggregate": True},
    "NXA": {"naics": "composite", "name": "Nondefense Capital Goods excl. Aircraft", "aggregate": True},
    "DEF": {"naics": "composite", "name": "Defense Capital Goods", "aggregate": True},
    "CDG": {"naics": "composite", "name": "Consumer Durable Goods", "aggregate": True},
    "CNG": {"naics": "composite", "name": "Consumer Nondurable Goods", "aggregate": True},
    "COG": {"naics": "composite", "name": "Consumer Goods", "aggregate": True},
    "MVP": {"naics": "3361,3362,3363", "name": "Motor Vehicles and Parts", "aggregate": True},
    "BTP": {"naics": "33621,3363", "name": "Motor Vehicle Bodies, Trailers, Parts", "aggregate": True},
    "NAP": {"naics": "336411,336412,336413", "name": "Nondefense Aircraft and Parts", "aggregate": True},
    "DAP": {"naics": "336411,336412,336413", "name": "Defense Aircraft and Parts", "aggregate": True},
    "ITI": {"naics": "composite", "name": "Information Technology", "aggregate": True},
    "CRP": {"naics": "33411", "name": "Computers and Related Products", "aggregate": True},
    "CMS": {"naics": "composite", "name": "Construction Materials and Supplies", "aggregate": True},
    "ODG": {"naics": "321,327,337,339", "name": "Other Durable Goods", "aggregate": True},
    "TGP": {"naics": "33361", "name": "Turbines/Generators/Power Transmission", "aggregate": True},
    "MTU": {"naics": "composite", "name": "Manufacturing with Unfilled Orders", "aggregate": True},
    "ANM": {"naics": "3313,3314,33152", "name": "Aluminum and Nonferrous Metal Products", "aggregate": True},
}

# Cross-check against actual data
with open(os.path.join(os.path.dirname(__file__), "..", "data", "json", "m3", "m3.json")) as f:
    d = json.load(f)

data_codes = set()
for s in d["series"]:
    code = s["id"].split("_", 1)[0]
    data_codes.add(code)

mapped = data_codes & set(m3_naics.keys())
unmapped = data_codes - set(m3_naics.keys())

print(f"M3 codes in data: {len(data_codes)}")
print(f"Mapped: {len(mapped)}")
print(f"Unmapped: {len(unmapped)}")
if unmapped:
    print("Unmapped codes:", sorted(unmapped))

config_dir = os.path.join(os.path.dirname(__file__), "..", "config")
os.makedirs(config_dir, exist_ok=True)
out_path = os.path.join(config_dir, "m3_naics_map.json")
with open(out_path, "w") as f:
    json.dump(m3_naics, f, indent=2)
print(f"Saved {out_path} ({len(m3_naics)} entries)")


if __name__ == "__main__":
    pass  # Already runs on import
