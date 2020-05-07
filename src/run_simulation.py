import argparse
import re
import sys

import numpy as np
import scipy
import scipy.stats as ss
from Bio import Phylo
from Bio import SeqIO
from datetime import datetime

from sequence_info import NUCLEOTIDES, COMPLEMENT_DICT
from sequence_info import Sequence
from simulation import SimulateOnTree


def get_args(parser):
    parser.add_argument(
        'seq',
        help='Path to the file containing the query sequence.'
    )
    parser.add_argument(
        'tree',
        help='Path to file containing phylogenetic tree in Newick format.'
    )
    parser.add_argument(
        '--outfile', default=None, help='Path to the alignment file.'
    )
    parser.add_argument(
        '--orfs', default=None,
        help='Path to a csv file containing the start and end coordinates of the open reading frames. '
             'Format: start,end'
             'If no ORFS are specified, the program will find ORFs automatically'
    )
    parser.add_argument(
        '--mu', type=float, default=0.0005,
        help='Global substitution rate per site per unit time'
    )
    parser.add_argument(
        '--kappa', type=float, default=0.3,
        help='Transversion/ transition rate assuming time reversibility.'
    )
    parser.add_argument(
        '--pi', type=float, default=[None, None, None, None],
        help='Vector of stationary nucleotide frequencies. If no value is specified, '
             'the program will use the empirical frequencies in the sequence. Format: [A, T, G, C]'
    )
    parser.add_argument(
        '--omega', type=float, default=[None, None, None, None],
        help='List of dN/dS ratios along the length of the sequence. '
    )

    parser.add_argument(
        '--circular', action='store_true',
        help='True for circular genomes. By default, false for linear genomes'
    )

    return parser.parse_args()


def valid_sequence(seq):
    """
     Verifies that the length of the input sequence is valid and the sequence is composed of only nucleotides.
    A valid sequence is assumed to be composed of a START codon, at least one amino acid codon, and a STOP codon.
    :return is_valid: <True> if the sequence is valid, <False> otherwise
    """
    is_valid = len(seq) >= 9 and all(pos in NUCLEOTIDES for pos in seq.upper())
    return is_valid


def valid_orfs(orfs, seq_length):
    """
    Verifies that the input ORFs are a list of tuples containing the start and end positions of ORFs.
    Example of valid input: [(1, 9), (27, 13)]
    Example of invalid input: (1, 9), (27, 13)
    :param orfs: The list of open reading frames
    :param seq_length: The length of the original sequence
    :return: <True> if the ORFs are valid, <False> otherwise
    """
    invalid_orfs = []

    for orf in orfs:
        # Check that the ORF range is valid
        if orf[0] == orf[1]:
            invalid_orfs.append(orf)

        # Check that the start and end positions are integers
        if type(orf[0]) is not int or type(orf[1]) is not int and orf not in invalid_orfs:
            print("Invalid orf: {}; Start and end positions must be integers.".format(orf))
            invalid_orfs.append(orf)

        # Check that the start and stop positions are in the range of the sequence
        if 0 > orf[0] or seq_length < orf[0] or 0 > orf[1] or seq_length < orf[1] and orf not in invalid_orfs:
            print("Invalid orf: {}; Positions must be between 0 and {}".format(orf, seq_length))
            invalid_orfs.append(orf)

        # Check that the ORF is composed of codons
        if orf[1] > orf[0]:  # Forward strand
            if (orf[1] - orf[0]) % 3 != 0:      # Inclusive range (start and end coordinates included)
                print("Invalid orf: {}; Not multiple of three".format(orf))
                invalid_orfs.append(orf)

        if orf[0] > orf[1]:  # Reverse strand
            if (orf[0] - orf[1]) % 3 != 0:      # Inclusive range (start and end coordinates included)
                print("Invalid orf: {}; Not multiple of three".format(orf))
                invalid_orfs.append(orf)

    return invalid_orfs


def reverse_and_complement(seq):
    """
    Generates the reverse complement of a DNA sequence
    :param: my_region <option> A sub-sequence of the original sequence
    :return rcseq: The reverse complement of the sequence
    """
    rseq = reversed(seq.upper())
    rcseq = ''
    for i in rseq:  # reverse order
        rcseq += COMPLEMENT_DICT[i]
    return rcseq


def get_open_reading_frames(seq):
    """
    Gets positions of the START and STOP codons for each open reading frame in the forward and reverse directions.
    Positions of the START and STOP codons indexed relative to the forward strand.
    :return reading_frames: a list of tuples containing the index of the first nucleotide of
                the START codon and the index of the last nucleotide of the STOP codon
    """
    start_codon = re.compile('ATG', flags=re.IGNORECASE)
    stop = re.compile('(TAG)|(TAA)|(TGA)', flags=re.IGNORECASE)
    reading_frames = []

    # Record positions of all potential START codons in the forward (positive) reading frame
    fwd_start_positions = [match.start() for match in start_codon.finditer(seq)]

    # Find open forward open reading frames
    for position in fwd_start_positions:
        frame = position % 3

        internal_met = False
        # If the ATG codon is an internal methionine and not an initiation codon
        for orf in reversed(reading_frames):

            # If the START codon and the potential START codon are in the same reading frame
            # and the existing ORF ends before the potential ORF, stop searching
            if orf[0] % 3 == frame and orf[1] < position:
                break

            # If the potential START codon is between the range of the START and STOP codons,
            # and it is in the same frame, the codon is an internal methionine
            if orf[0] < position < orf[1] and orf[0] % 3 == frame:
                internal_met = True
                break

        # If the ATG is a START codon and not simply methionine
        if not internal_met:
            for match in stop.finditer(seq, position):
                orf_length = match.end() - position
                # Find a stop codon and ensure ORF length is sufficient in the forward strand
                if match.start() % 3 == frame and orf_length >= 8:
                    # Get the positions in the sequence for the first and last nt of the RF
                    orf = (position, match.end())
                    reading_frames.append(orf)
                    break

    # Forward (positive) reading frames of the reverse complement of the original
    # sequence is equivalent to reverse (negative) reading frames of the original sequence
    rcseq = reverse_and_complement(seq)

    # Record positions of all potential START codons in the reverse (negative) reading frame
    rev_start_positions = [match.start() for match in start_codon.finditer(rcseq)]

    # Find reverse open reading frames
    for position in rev_start_positions:
        frame = position % 3

        internal_met = False
        # If the ATG codon is an internal methionine and not an initiation codon
        for orf in reversed(reading_frames):

            # If the START codon and the potential START codon are in the same reading frame
            # and the existing ORF ends before the potential ORF, stop searching
            if orf[0] % 3 == frame and orf[1] < position:
                break

            # If the potential START codon is between the range of the START and STOP codons,
            # and it is in the same frame, the codon is an internal methionine
            if orf[0] < position < orf[1] and orf[0] % 3 == frame:
                internal_met = True
                break

        # If the ATG is a START codon and not simply methionine
        if not internal_met:
            for match in stop.finditer(rcseq, position):
                orf_length = match.end() - position
                # Find a stop codon and ensure ORF length is sufficient in the forward strand
                if match.start() % 3 == frame and orf_length >= 8:
                    # Get the positions in the sequence for the first and last nt of the RF
                    orf = (len(rcseq) - position, len(rcseq) - match.end())
                    reading_frames.append(orf)
                    break

    return reading_frames


def sort_orfs(unsorted_orfs):
    """
    Store ORFs in position according to plus zero ORF (first of the list).
    They will be classified as (+0, +1, +2, -0, -1, -2)
    :return sorted_orfs: List of ORFs classified according to their shift relative to the
                        plus zero reading frame (+0, +1, +2, -0, -1, -2)
    """
    sorted_orfs = {'+0': [], '+1': [], '+2': [], '-0': [], '-1': [], '-2': []}

    if unsorted_orfs:
        first_orf = unsorted_orfs[0]
        for orf in unsorted_orfs:
            difference = abs(orf[0] - first_orf[0]) % 3

            if first_orf[0] < first_orf[1]:
                if orf[0] < orf[1]:  # positive strand
                    if difference == 0:
                        sorted_orfs['+0'].append(orf)
                    elif difference == 1:
                        sorted_orfs['+1'].append(orf)
                    elif difference == 2:
                        sorted_orfs['+2'].append(orf)

                elif orf[0] > orf[1]:  # negative strand
                    if difference == 0:
                        sorted_orfs['-2'].append(orf)
                    elif difference == 1:
                        sorted_orfs['-1'].append(orf)
                    elif difference == 2:
                        sorted_orfs['-0'].append(orf)

            else:
                if orf[0] < orf[1]:  # positive strand
                    if difference == 0:
                        sorted_orfs['+2'].append(orf)
                    elif difference == 1:  # plus one
                        sorted_orfs['+1'].append(orf)
                    elif difference == 2:  # plus two
                        sorted_orfs['+0'].append(orf)

                elif orf[0] > orf[1]:  # negative strand
                    if difference == 0:
                        sorted_orfs['-0'].append(orf)
                    elif difference == 1:
                        sorted_orfs['-1'].append(orf)
                    elif difference == 2:
                        sorted_orfs['-2'].append(orf)

    return sorted_orfs


def get_omega_values(alpha, ncat):
    """
    Draw ncat number of omega values from a discretized gamma distribution
    :param alpha: shape parameter
    :param ncat: Number of categories (expected omegas)
    :return: list of ncat number of omega values (e.i. if ncat = 3, omega_values = [0.29, 0.65, 1.06])
    """
    values = discretize_gamma(alpha=alpha, ncat=ncat)
    omega_values = list(values)
    return omega_values


def discretize_gamma(alpha, ncat, dist=ss.gamma):
    """
    Divide the gamma distribution into a number of intervals with equal probability and get the mid point of those intervals
    From https://gist.github.com/kgori/95f604131ce92ec15f4338635a86dfb9
    :param alpha: shape parameter
    :param ncat: Number of categories
    :param dist: function from scipy stats
    :return: array with ncat number of values
    """
    if dist == ss.gamma:
        dist = dist(alpha, scale=1 / alpha)

    elif dist == ss.lognorm:
        dist = dist(s=alpha, scale=np.exp(0.5 * alpha ** 2))

    quantiles = dist.ppf(np.arange(0, ncat) / ncat)
    rates = np.zeros(ncat, dtype=np.double)  # return a new array of shape ncat and type double

    for i in range(ncat - 1):
        rates[i] = ncat * scipy.integrate.quad(lambda x: x * dist.pdf(x), quantiles[i], quantiles[i + 1])[0]
    rates[ncat - 1] = ncat * scipy.integrate.quad(lambda x: x * dist.pdf(x), quantiles[ncat - 1], np.inf)[0]
    return rates


def parse_genbank(in_seq, in_orfs=None):
    """
    When input is in <genbank> format, extract nucleotide sequence and orfs (in case user does not specify).
    :param in_seq: sequence in genbank Format
    :param in_orfs: file handle containing the orfs
    :return tuple: (sequence, orfs)
    """
    # Loop through records
    for rec in SeqIO.parse(in_seq, format="genbank"):
        seq = rec.seq  # TODO: deal with multipartite viruses?
        if in_orfs is None:  # User did not specify ORFs
            unsorted_orfs = []
            cds = [feat for feat in rec.features if feat.type == "CDS"]

            # Record the first occurrence of the ORFs
            for cd in cds:
                for loc in cd.location.parts:
                    coord = (int(loc.start), int(loc.end))
                    if coord not in unsorted_orfs:
                        unsorted_orfs.append(coord)
                    else:
                        print("ORF {} is common to multiple coding sequences.".format(coord))
        else:
            unsorted_orfs = check_orfs(in_orfs)

    return seq, unsorted_orfs


def parse_fasta(in_seq):
    """
    If input is a fasta file, retrieve nucleotide sequence
    :param in_seq: the sequence
    :return s: the nucleotide sequence
    """
    # Read in the sequence
    with open(in_seq) as seq_file:
        s = ''
        for line in seq_file:
            # Skip header if the file is a FASTA file
            if not (line.startswith(">") or line.startswith("#")):
                s += line.strip('\n\r').upper()
    return s


def check_orfs(in_orfs=None, s=None):
    """
    :param in_orfs: orfs specified by the user, default (None)
    :param s: the original sequence
    :return: ORFs as a list of tuples
    """

    # Check if the user specified orfs
    if in_orfs is None:
        unsorted_orfs = get_open_reading_frames(s)

    # Read ORFs as a list of tuples
    else:
        unsorted_orfs = []
        with open(in_orfs) as orf_handle:
            for line in orf_handle:
                line = line.split(',')
                orf = (int(line[0]), int(line[1]))
                unsorted_orfs.append(orf)

    return unsorted_orfs


def main():
    start_time = datetime.now()
    print("Started at: ", datetime.now())
    parser = argparse.ArgumentParser(
        description='Simulates and visualizes the evolution of a sequence through a phylogeny'
    )
    args = get_args(parser)

    # Check input format
    input = args.seq.lower()
    if input.endswith(".gb") or input.endswith("genbank"):  # If genbank file
        s, unsorted_orfs = parse_genbank(args.seq, args.orfs)
    elif input.endswith(".fasta") or input.endswith(".fa"):   # If fasta file
        s = parse_fasta(args.seq)
        unsorted_orfs = check_orfs(args.orfs, s)
        print(unsorted_orfs)
    else:
        print("Sequence files must end in '.fa', '.fasta', '.gb', 'genbank'")
        sys.exit()

    # Check if the ORFs are valid
    invalid_orfs = valid_orfs(unsorted_orfs, len(s))

    # Omit the invalid ORFs
    if invalid_orfs:
        invalid_orf_msg = ""
        for invalid_orf in invalid_orfs:
            invalid_orf_msg += " {} ".format(invalid_orf)
            unsorted_orfs.remove(invalid_orf)
        print("\nOmitted orfs: {}\n".format(invalid_orf_msg))

    # Since ORFs are valid, sort the ORFs by reading frame
    orfs = sort_orfs(unsorted_orfs)
    print("Valid sorted orfs: ", orfs)

    # Check if sequence is valid
    if not valid_sequence(s):
        print("Invalid sequence: {}".format(s))
        sys.exit(0)

    # If the user did not specify stationary frequencies
    if all(freq is None for freq in args.pi):
        pi = Sequence.get_frequency_rates(s)

    # If the user specified stationary frequencies
    elif all(freq is type(float) for freq in args.pi):
        keys = ['A', 'T', 'G', 'C']
        pi = dict(zip(keys, args.pi))

    else:
        print("Invalid input: {}".format(args.pi))
        exit(0)

    # If user did not specify omega values
    if all(v is None for v in args.omega):
        # Draw omega values from gamma distribution
        omegas = get_omega_values(2, 4)

    # Read in the tree
    phylo_tree = Phylo.read(args.tree, 'newick', rooted=True)

    # Make Sequence object
    print("\nCreating root sequence")
    root_sequence = Sequence(s, orfs, args.kappa, args.mu, pi, omegas, args.circular)
    # Run simulation
    #print("Event Tree:", root_sequence.event_tree["to_nt"]['T']["from_nt"]['G'])
    #print(root_sequence.event_tree["to_nt"]['T']["from_nt"]['G']['nts_in_subs'][0].rates)
    #print(root_sequence.event_tree["to_nt"]['T']["from_nt"]['G']['nts_in_subs'][0].mutation_rate)
    print("\nRunning simulation")

    simulation = SimulateOnTree(root_sequence, phylo_tree, args.outfile)
    simulation.get_alignment(args.outfile)

    print("Simulation runed during {} seconds".format(datetime.now() - start_time))


if __name__ == '__main__':
    main()