import os

"""
Handling of predicted zones (countriers, regions)
"""

def read_config_list(filename):
    with open(filename, "r") as f:
        conf_lines = f.readlines()
        conf_lines = [line.replace("\n", "") for line in conf_lines if line and not line.startswith("#")]
    return set(conf_lines)


def read_zones(args):
    print("root dir", args.root_dir)
    regions = read_config_list(
        os.path.join(args.root_dir, "active-regions.cfg")
    )
    active_countries = read_config_list(
        os.path.join(args.root_dir, "active-countries.cfg")        
        )
    # "active-countries.cfg" is used by R and expect "United_Kingdom"
    active_countries = set([country if country != "United_Kingdom" else "United Kingdom" for country in active_countries ])

    region_to_country_map = {region: "France" for region in regions}
    region_to_country_map.update({country: country for country in active_countries})
    #if "United_Kingdom" in region_to_country_map:
    #    region_to_country_map["United_Kingdom"] = "United Kingdom"
    return region_to_country_map