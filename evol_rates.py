import scipy
from scipy.stats import gamma

# Calculate evolution rates across the sequence
def get_frequency_rates(seq):
    seq = list(seq)
    frequencies = {
        'A': 0,
        'C': 0,
        'T': 0,
        'G': 0,
    }

    for nucleotide in frequencies:
        frequencies[nucleotide] = round((float(seq.count(nucleotide))/(len(seq))),2)

    return frequencies


def evol_rates(seq, mu, bias, pi, omega):
    """
    Generate rate vector from sequence given parameters.
    @param seq: the nucleotide sequence of length <L>.  Assumed to start and end in reading frame +0.
    @param mu: the global rate (substitutions/site/unit time).
    @param pi: <optional> a vector of stationary nucleotide frequencies.  If not specified, defaults
               to the empirical frequencies in <seq>.
    @param bias: <optional> a List of 6 rates [AC, AG, AT, CG, CT, GT] assuming time-reversibility.
                    If not specified, defaults to 1's.
    @param omega: <optional> a List of dN/dS (omega) ratios along sequence length as {dict}.
                  {dict} always contains key +0 (parent reading frame).  May contain omega for alternate
                  reading frame as (+1, +2, -0, -1 or -2).  Codon position is determined by the nt's
                  location relative to start of <seq>.
    @return seq_rates: a List of tuples for rates of 3 possible nucleotide substitution at each site
                   in <seq> (3xL).
    """

    L = len(seq)
    seq_rates = [(mu, mu, mu) for position in range(L)]                      # initialize the list with baseline rates
    frequency_rates = get_frequency_rates(seq)
    # iterate over every nt in seq
    for position in range(L):
        # 1. what is the current nucleotide X?
        nucleotide = seq[position]

        # 2. apply stationary frequencies (pi) to tuple given X
        if pi is None:                                                       # If pi is no specified
            pi = frequency_rates[nucleotide]                                 # use empirical frequencies

        seq_rates[position] = tuple([pi*j for j in seq_rates[position]])     # Apply pi to every value in seq_rates according to the position

        # 3. apply biases to tuple
        biased_rates = []

        for rate in range(3):                                                      # Iterate over every item in the tuple
            modified_rates = seq_rates[position][rate] * bias[nucleotide][rate]    # Create a new list with values of the tuple modified by bias
            biased_rates.append(modified_rates)

        seq_rates[position] = tuple(biased_rates)                        # Update seq_rates

    # 4. apply omega in parent reading frame
    for position in range(L):
        rf_0plus = omega['reading_frame0plus']                          # Omega values for parental reading frame
        omega_rates = []
        for rate in range(3):
            modified_rates2 = seq_rates[position][rate] * rf_0plus[position][rate] #Apply omega values to seq_rates
            omega_rates.append(modified_rates2)

        seq_rates[position] = tuple(omega_rates)                         # Update seq_rates with modified values

    # 5. if alternate reading frame(s) is present, apply other omega(s)

    #return modified_rates2
    return seq_rates

# Create omega
def get_omega(reading_frames):
    """
    Get omega for every reading frame from a a gamma distribution
    :param reading_frames: User must indicate first and last nucleotide of every reading frame in seq
    :return omega: dictionary with keys for every reading frame in seq and the dN/dS rates for each codon.
     """
    omega = {}
    rf = reading_frames
    a = 1                       # Shape parameter
    for rf in seq:
        omega[rf] = gamma.rvs(a, size = number_of_codons)

    return omega


# Get Reading frames (in the 5'-3' strand)
start = 'ATG'
stop = ['TAG' , 'TAA']
def get_reading_frames(seq):
    """
    Creates a list with tuples containing the first and last position of the reading frames in seq
    according to start and stop codons
    """

    reading_frames = []
    for frame in range(3):
        for codon, position in codon_iterator(seq[frame:]): # Iterate over every codon in the RF
            if codon == start:                              # Find a start codon
                for codon_in_rf, position_in_rf in codon_iterator(seq[(position+frame):]):
                    if codon_in_rf in stop:                 # Find a stop codon
                        # Get the positions in the sequence for the first and last nt of the RF
                        rf = (position+frame, position_in_rf+(position+frame)+3)
                        #Use +3 to include the full stop codon
                        reading_frames.append(rf)
                        break
                break
    return reading_frames


def codon_iterator(list):
    """
    Generator to move every tree nucleotides (codon)
    Yield: codon and position of the first nucleotide of codon in seq (ex., ('GAA', 5))
    """
    i = 0
    while i < len(list):
        yield list[i:i + 3], i
        i += 3

