# From GenBank file create a YML to run on HexSE

import argparse
from Bio import SeqIO
import yaml
from random import randint


def get_args(parser):
    parser.add_argument(
        'gb_file',
        help = 'Path to the genbank file'
    )
    parser.add_argument(
        'yaml_file',
        help = 'Path to the yaml configuration file'
    )

    return parser.parse_args()

def get_locations(handle):
    
    open(handle)
    locations = []
    for record in SeqIO.parse(handle, format="genbank"):
        cds = [feat for feat in record.features if feat.type=="CDS"]
        for cd in cds:
            temp = []
            for loc in cd.location.parts:
                start, end = loc.start, loc.end
                temp.append((int(start),int(end)))
            locations.append(temp)

    return locations


def main():
    parser = argparse.ArgumentParser(
        description='Create a YAML configuration file to Hexse from GenBank file'
    )

    args = get_args(parser)
    gb_file = args.gb_file
    out = args.yaml_file
    
    orf_info = {}   
    for location in get_locations(gb_file):
        
        string_parts = []
        for part in location:
            string_parts.append(','.join([str(value) for value in part]))

        loc_string = ";".join(string_parts)  # Include all fragments on orf coordinates separated by colon
        
        omega_shape = 1+ (randint(0,10)/10)
        
        orf_info[loc_string] = {
                                'omega_classes': randint(2,6),
                                'omega_shape': omega_shape,
                                'omega_dist': 'gamma'
                        }

    info_for_yaml = {
                    'global_rate': 0.05,
                    'kappa': 0.3,
                    'pi': {'A': 0.25, 'C': 0.25, 'G': 0.25, 'T':0.25},
                    'mu':{'classes': 2, 'shape': 1.0, 'dist': 'lognorm'},
                    'circular': 'false',
                    'orfs': orf_info
                }


    with open(out, 'w+') as file:
        yaml.dump(info_for_yaml, file)


if __name__ == '__main__':
    main()