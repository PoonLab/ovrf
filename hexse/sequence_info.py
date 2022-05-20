# Store sequence information

import random
import copy
import sys

import pprint

TRANSITIONS_DICT = {'A': 'G', 'G': 'A', 'T': 'C', 'C': 'T'}

NUCLEOTIDES = ['A', 'C', 'G', 'T']

COMPLEMENT_DICT = {'A': 'T', 'C': 'G', 'G': 'C', 'T': 'A',
                   'W': 'W', 'R': 'Y', 'K': 'M', 'Y': 'R',
                   'S': 'S', 'M': 'K', 'B': 'V', 'D': 'H',
                   'H': 'D', 'V': 'B', '*': '*', 'N': 'N',
                   '-': '-'}

CODON_DICT = {'TTT': 'F', 'TTC': 'F', 'TTA': 'L', 'TTG': 'L',
              'TCT': 'S', 'TCC': 'S', 'TCA': 'S', 'TCG': 'S',
              'TAT': 'Y', 'TAC': 'Y', 'TAA': '*', 'TAG': '*',
              'TGT': 'C', 'TGC': 'C', 'TGA': '*', 'TGG': 'W',
              'CTT': 'L', 'CTC': 'L', 'CTA': 'L', 'CTG': 'L',
              'CCT': 'P', 'CCC': 'P', 'CCA': 'P', 'CCG': 'P',
              'CAT': 'H', 'CAC': 'H', 'CAA': 'Q', 'CAG': 'Q',
              'CGT': 'R', 'CGC': 'R', 'CGA': 'R', 'CGG': 'R',
              'ATT': 'I', 'ATC': 'I', 'ATA': 'I', 'ATG': 'M',
              'ACT': 'T', 'ACC': 'T', 'ACA': 'T', 'ACG': 'T',
              'AAT': 'N', 'AAC': 'N', 'AAA': 'K', 'AAG': 'K',
              'AGT': 'S', 'AGC': 'S', 'AGA': 'R', 'AGG': 'R',
              'GTT': 'V', 'GTC': 'V', 'GTA': 'V', 'GTG': 'V',
              'GCT': 'A', 'GCC': 'A', 'GCA': 'A', 'GCG': 'A',
              'GAT': 'D', 'GAC': 'D', 'GAA': 'E', 'GAG': 'E',
              'GGT': 'G', 'GGC': 'G', 'GGA': 'G', 'GGG': 'G',
              '---': '-', 'XXX': '?'}


class Sequence:
    """
    Store inputs and create sequence objects
    """

    def __init__(self, str_sequence, orfs, kappa, global_rate, pi, cat_values, circular=False):
        """
        Creates a list of nucleotides, locates open reading frames, and creates a list of codons.

        :param str_sequence:  str, nucleotide sequence as a string object
        :param orfs:  dict, A dictionary of open reading frames (ORFs) in the sequence, sorted by reading frame where:
                        - the keys are the reading frames (+0, +1, +2, -0, -1, -2)
                        - the values are a list containing the information for each ORF
                        - for example:
            {'+0': [{'coords': [[2849, 3182]], 'omega_shape': 1.5, 'omega_classes': 3,
                     'omega_values': [0.17, 0.48, 1.14]},
                    {'coords': [[3173, 3182]], 'omega_shape': 1.9, 'omega_classes': 5,
                     'omega_values': [0.18, 0.40, 0.63, 0.93, 1.63]}],
             '+1': [],
             '+2': [{'coords': [[0, 837]], 'omega_shape': 1.7, 'omega_classes': 4,
                     'omega_values': [0.17, 0.42, 0.72, 1.40]},
                    {'coords': [[156, 837]], 'omega_shape': 1.2, 'omega_classes': 6,
                     'omega_values': [0.05, 0.16, 0.28, 0.44, 0.67, 1.26]}],
             '-0': [],
             '-1': [],
             '-2': []}
        :param kappa:  float, transition/ transversion rate ratio
        :param global_rate:  float, the global substitution rate (/site/unit time)
        :param pi:  float, stationary frequencies of nucleotides, with nucleotide as keys
        :param cat_values:  dict, values drawn from a gamma distribution modeling rate variation among nucleotides, keyed by 'mu1', etc.
        :param circular:  bool, true if the genome is circular, false if the genome is linear (default: false)
        """
        self.orfs = orfs
        self.kappa = kappa
        self.global_rate = global_rate
        self.pi = pi
        self.cat_values = cat_values
        self.is_circular = circular

        self.nt_sequence = []
        self.__codons = []  # Store references to all codons
        self.total_omegas = {}  # every possible combination of omegas present on the event tree

        pp = pprint.PrettyPrinter(indent=2)
        # Create Nucleotides
        for pos_in_seq, nt in enumerate(str_sequence):
            self.nt_sequence.append(Nucleotide(nt, pos_in_seq))

        # Set Codons based on the reading frames
        if self.orfs is not None:
            for frame, orf_list in self.orfs.items():
                for orf in orf_list:  # orf is a dictionary
                    codons = self.find_codons(frame, orf)  # generates Codon objects
                    # tell Nucleotide which Codon(s) it belongs to
                    for codon in codons:
                        for nt in codon.nts_in_codon:
                            nt.codons.append(codon)  # FIXME: shouldn't Codon __init__ do this?
                        self.__codons.append(codon)

        # Create event tree containing all possible mutations
        self.orf_map = self.create_orf_map()  # Orf coordinates and the binary code assigned to them
        self.event_tree = self.create_event_tree()  # Nested dict containing info about all possible mutation events
        
        #pp.pprint(self.event_tree)

        # Calculate mutation rates for each nucleotide in sequence, populate the event tree which each nucleotide
        for nt in self.nt_sequence:
            self.set_substitution_rates(nt)  # Get substitution rates for the nucleotide
            self.nt_in_event_tree(nt)  # Locate nucleotide in the event tree

        self.compute_probability()
        self.count_events_per_layer()



    def create_orf_map(self):
        """
        Create a dictionary with orf coordinates as keys and binary set of orf_map as value 
        (e.g, { '[[0, 837]]': [0, 1, 0, 0], '[[156, 837]]': [0, 0, 1, 0]})
        """
        orf_map = {}

        for rf, orf_list in self.orfs.items():
            for orf_info in orf_list:
                coord = str([item for sublist in orf_info['coords'] for item in sublist])
                map = list(orf_info['orf_map'])
                orf_map[coord] = map
        return orf_map

    def compare(self):
        """
        Compare orfs
        Store in orf_map if overlaps
        Assign new map value by summing the two orf_maps
        """

    def find_intersection(orf1,orf2):
        """
        Find positions with overlapping nucleotides
        orf: tuple?, start and end positions
        """
        orf1=range(orf1)
        orf2=range(orf2)
        set_orf1=set(orf1)
        
        return set_orf1.intersection(orf2)

    def get_sorted_coords(self):
        """
        Sort reading frames according to their position on the genome
        orf_list: list of tuples with start and end position for each open reading frame     
        """
        coords = []
        # Get list of orfs
        for rf, orf_list in self.orfs.items():
            for orf_info in orf_list:

                # Coords are a list of list (e.g, [[156, 837], [836,106]]) used to account for spliced orfs
                # Note: most orfs are a list of only one list (no splicing)
                # TODO: how to do this for spliced orfs?
                flat_coords = [item for sublist in orf_info['coords'] for item in sublist] 
                coords.append(flat_coords)
        
        return (sorted(coords, key=min))


    def compute_probability(self):
        """
        Get the probabilities of transition and transversion for latter selection of the branch on the tree
        """
        for to_nt in NUCLEOTIDES:
            for nuc in NUCLEOTIDES:
                if nuc != to_nt:
                    self.event_tree['to_nt'][to_nt]['from_nt'][nuc].update({'prob': 0, 'number_of_events': 0})

            for from_nt, current_branch in self.event_tree['to_nt'][to_nt]['from_nt'].items():
                if from_nt == to_nt:
                    continue

                # Update transition-transversion probability value
                if self.is_transv(from_nt, to_nt):  # Substitution is transversion
                    current_branch['prob'] += (self.kappa / (1 + 2 * self.kappa))
                else:  # Substitution is transition
                    current_branch['prob'] += (1 / (1 + 2 * self.kappa))

                # Update mu (base rate) classes
                for mu_cat in self.cat_values.keys():
                    prob = (self.cat_values[mu_cat] / sum(self.cat_values.values()))
                    current_branch['category'][mu_cat].update({'prob': prob, 'number_of_events': 0})

                    # extract keys (one-hot tuples) for omega on this branch of event_tree
                    combos = self.event_tree['to_nt'][to_nt]['from_nt'][from_nt]['category'][mu_cat]['omega'].keys()
                    # nonsyn_values = []
                    # omega_p = 1

                    for combo in combos:
                        # a combo is a tuple of length = maximum number of overlapping reading frames (?)
                        # each member of the tuple is a one-hot encoding of non-synonymous or synonymous categories
                        # (1, 0, 0) = non-synonymous, first omega of two categories
                        # (0, 1, 0) = non-synonymous, second omega of two categories
                        # (0, 0, 1) = synonymous (always last position)

                        nonsyn_values = []
                        omega_p = 1
                        
                        for omega in combo:
                            denominator = 1 + sum(self.total_omegas.values())
                            nonsyn_values.append(omega[:-1])

                            if not any(omega):
                                omega_p = (1 / denominator)

                            # Non-synonymous
                            elif any(nonsyn_values):
                                for nonsyn_val in nonsyn_values:
                                    # Check last position in omega tuple to avoid counting syn ORFs twice
                                    if any(nonsyn_val) and omega[-1] == 0:
                                        # Multiply probabilities if nucleotide is part of synonymous and non-synonymous
                                        omega_p *= (self.total_omegas[combo] / denominator)
                                    if omega[-1] > 1:
                                        omega_p *= (1 / denominator)

                            # Synonymous
                            else:
                                omega_p = (1 / denominator)

                        current_branch['category'][mu_cat]['omega'][combo].update({'prob': omega_p,  # prob for the 'omega branch' actually represents dN/dS
                                                                         'number_of_events': 0})



    def all_syn_values(self, nonsyn_values):
        for nonsyn_val in nonsyn_values:
            if any(nonsyn_val):
                return True
        return False

    def count_events_per_layer(self):
        """
        Traverse Event Tree to calculate and store the number of events in every branch, layer by layer
        Number of events are required to select a branch using weighter_random_choice
        """

        for to_nt in NUCLEOTIDES:
            to_events = 0

            for from_nt in NUCLEOTIDES:
                if to_nt != from_nt:
                    from_events = 0
                    branch = self.event_tree['to_nt'][to_nt]['from_nt'][from_nt]['category']

                    for cat in branch.keys():
                        cat_events = 0
                        branch_cat = branch[cat]['omega']

                        for omega_tuple in branch_cat.keys():
                            nt_list = branch_cat[omega_tuple]['nt']
                            events = len(nt_list)
                            self.event_tree['to_nt'][to_nt]['from_nt'][from_nt]['category'][cat]['omega'][omega_tuple]['number_of_events'] = events
                            cat_events += events

                        self.event_tree['to_nt'][to_nt]['from_nt'][from_nt]['category'][cat]['number_of_events'] = cat_events
                        from_events += cat_events

                    self.event_tree['to_nt'][to_nt]['from_nt'][from_nt]['number_of_events'] = from_events
                    to_events += from_events

            self.event_tree['to_nt'][to_nt]['number_of_events'] = to_events

    def count_nts_on_event_tree(self):
        """
        Traverse event tree and count total number of nucleotides on the tips
        Note: Final count should be around sequence length*3
        """
        total_nts = 0

        for to_nt in NUCLEOTIDES:

            for from_nt in NUCLEOTIDES:

                if to_nt != from_nt:
                    branch = self.event_tree['to_nt'][to_nt]['from_nt'][from_nt]['category']

                    for classification in branch.keys():
                        branch_cat = branch[classification]

                        for omega_key in branch_cat.keys():
                            nts_in_branch = len(branch_cat[omega_key])
                            total_nts += nts_in_branch

        return total_nts

    def __deepcopy__(self, memodict):
        """
        Creates a deepcopy of Sequence and sets the reference(s) for a Nucleotide's Codon(s)
        """

        # Creates a new Sequence
        cls = self.__class__
        new_sequence = cls.__new__(cls)
        memodict[id(self)] = new_sequence  # Avoid duplicate copying

        # Set attributes of new Sequence to the same as the original object
        for k, v in self.__dict__.items():
            setattr(new_sequence, k, copy.deepcopy(v, memodict))

        # Set references to Codons
        for codon in new_sequence.__codons:
            for i, nt in enumerate(codon.nts_in_codon):
                nt.codons.append(codon)

        return new_sequence

    def __str__(self):
        """
        Represents the Sequence as a string by casting nt_sequence to a string.
        """
        return ''.join(str(nt) for nt in self.nt_sequence)

    def get_sequence(self):
        return self.nt_sequence

    def get_right_nt(self, pos_in_seq):
        """
        Returns the next Nucleotide in the sequence
        :param pos_in_seq: the position of the Nucleotide in the sequence
        """
        if self.is_circular:
            if pos_in_seq == len(self.nt_sequence) - 1:
                return self.nt_sequence[0]
        else:
            return self.nt_sequence[pos_in_seq + 1]

    def get_left_nt(self, pos_in_seq):
        """
        Returns the previous Nucleotide in the sequence
        :param pos_in_seq: the position of the Nucleotide in the sequence
        """
        if pos_in_seq == 0:
            if self.is_circular:
                return self.nt_sequence[- 1]
            else:
                return None
        else:
            return self.nt_sequence[pos_in_seq - 1]

    def get_event_tree(self):
        return self.event_tree

    @staticmethod
    def complement(seq, rev=False):
        """
        Generates the complement of a DNA sequence
        :param seq: the input sequence
        :param <option> rev: option to find the reverse complement
        :return s: The complement (or reverse complement) of the sequence
        """
        if rev:
            s = reversed(seq.upper())
        else:
            s = seq

        result = ''
        for i in s:
            result += COMPLEMENT_DICT[i]

        return result

    @staticmethod
    def get_frequency_rates(seq):
        """
        Frequency of nucleotides in the DNA sequence
        :param seq: the DNA sequence
        :return frequencies: a dictionary frequencies where the key is the nucleotide and the value is the frequency
        """
        frequencies = {'A': 0, 'C': 0, 'T': 0, 'G': 0}

        for nucleotide in frequencies:
            frequencies[nucleotide] = round((float(seq.count(nucleotide)) / (len(seq))), 2)

        return frequencies

    def create_event_tree(self):
        """
        Create an event tree (nested dictionaries) that stores pi, kappa, mu,
        and information about whether a mutation is a transition or transversion.
        :return event tree: a nested dictionary containing information about the mutation event
        """
        event_tree = {'to_nt': dict([(nuc, {'from_nt': {}}) for nuc in NUCLEOTIDES])}
        # dictionary keyed by binary tuples indicating combination of orfs (e.g., {(1, 0): {}, (0, 1): {} })
        bin_orf_layer = {bin_code : {'omega':{}} for bin_code in [tuple(value) for  value in self.orf_map.values()]}
        # Add tuple key with all ceros for nucleotides that don't belong to any reading frame
        non_orf_tuple = tuple([0]*len(bin_orf_layer))
        bin_orf_layer[non_orf_tuple] =  {'nts': []}  # On the branch with no orfs there are no further layers, just the nucleotide list

        # dictionary keyed by mutation rate categories
        # (e.g., {'mu1': {(1, 0): {}, (0, 1): {}}, 'mu2': {(1, 0): {}, (0, 1): {}}})
        cat_dict = {cat : bin_orf_layer for cat in self.cat_values.keys()}

        for to_nt in NUCLEOTIDES:
            # Update nucleotides with possible mutations
            for from_nt in NUCLEOTIDES:
                if from_nt == to_nt:
                    event_tree['to_nt'][to_nt]['from_nt'][from_nt] = None
                else: 
                    event_tree['to_nt'][to_nt]['from_nt'][from_nt] = cat_dict
        return event_tree

    def set_substitution_rates(self, nt):
        """
        Calculates substitution rates of a nucleotide
        Sets the sub-rates, omega values, rate classes, and total mutation rate of a Nucleotide
        :param nt: object of class Nucleotide
        """
        current_nt = nt.state
        sub_rates = {}
        selected_omega = {}
        my_cat_keys = {}

        for to_nt in NUCLEOTIDES:
            if to_nt == current_nt:
                sub_rates[to_nt] = None
                selected_omega[to_nt] = None
            else:
                # Apply global substitution rate and stationary nucleotide frequency
                sub_rates[to_nt] = self.global_rate * self.pi[current_nt]
                if self.is_transv(current_nt, to_nt):
                    sub_rates[to_nt] *= self.kappa


                if nt.codons:
                # For each orf that the nucleotide is part of, select one omega value if non-syn or 'None' if syn
                # E.g., {(0, 1, 0, 0, 0): 1, (0, 0, 1, 0, 0): 3} for a nucleotide with non-syn in two reading frames
                    chosen_omegas = {}
 
                    for codon in nt.codons:
                        #chosen_omegas.append([0 for _ in range(num_omegas + 1)])


                        # If mutation does not introduce a STOP and nucleotide is not part of a START codon
                        if not self.is_start_stop_codon(nt, to_nt):
                            pos_in_codon = codon.nt_in_pos(nt)
                            
                            # If mutation is non-synonymous, select one omega index to an omega_values for the orf
                            if codon.is_nonsyn(pos_in_codon, to_nt):
            
                                omega_values = codon.orf['omega_values']
                                #Randomly select one of the omegas
                                omega_index = random.randrange(len(omega_values))
                                chosen_omegas[tuple(codon.orf['orf_map'])] = omega_index

                            # Is mutation is synonymous, no omega needs to be applyed
                            else:
                                chosen_omegas[codon.orf['orf_map']] = None

                            # Iterate over codons to initialize the list to store chosen omegas
                            # chosen_omegas = []
                            # for codon in nt.codons:
                            #     print(codon)
                            #     print(codon.orf)

                            #     num_omegas = len(codon.orf['omega_values'])
                            #     chosen_omegas.append([0 for _ in range(num_omegas + 1)])

                            # # Loop through codons again to process the codons
                            # for idx, codon in enumerate(nt.codons):
                            #     omega_values = codon.orf['omega_values']
                            #     pos_in_codon = codon.nt_in_pos(nt)
                            #     num_omegas = len(codon.orf['omega_values'])

                            #     # Apply omega when mutation is non-synonymous
                            #     if codon.is_nonsyn(pos_in_codon, to_nt):
                            #         # Randomly select a key in the omega values dictionary
                            #         omega_index = random.randrange(num_omegas)
                            #         sub_rates[to_nt] *= omega_values[omega_index]
                            #         chosen_omegas[idx][omega_index] += 1

                            #     # Record that mutation is synonymous
                            #     else:
                            #         chosen_omegas[idx][num_omegas] += 1  # last position

                        # Mutation introduces or destroys a STOP or nt is part of a START
                        else: 
                            chosen_omegas[codon.orf['orf_map']] = 'Stop_start'

                selected_omega[to_nt] = chosen_omegas  # Store omega keys used in the substitution
                # Randomly select one of the mu values (mutation rate) 
                selected_cat = random.choice(list(self.cat_values))
                sub_rates[to_nt] *= self.cat_values[selected_cat]
                my_cat_keys[to_nt] = selected_cat

                # If key is not in total omegas dict, create it
                #self.set_total_omegas(chosen_omegas, nt.codons)

        # Set substitution rates and key values for the nucleotide object
        nt.set_rates(sub_rates)
        nt.set_categories(my_cat_keys)
        nt.set_omega(selected_omega)
        nt.get_mutation_rate()

    def set_total_omegas(self, chosen_omegas, codons):
        """
        Find if the omega keys (one-hot tuples) of a nucleotide are stored in self.total_omegas.
        If not, store it. 
        :param chosen_omegas: tuple of tuples, representing the indices of the selected omega values
        :param codons: list, codons that a given nucleotide is part of
        """

        # Number of codons a nucleotide is part of is the same as the number of ORFS
        for codon_idx in range(len(codons)):
            # Exclude last position (synonymous)
            nonsyn_values = chosen_omegas[codon_idx][:len(chosen_omegas[codon_idx]) - 1]

            if any(nonsyn_values):
                if tuple(nonsyn_values) not in self.total_omegas:
                    value = 1
                    for pos, omega_index in enumerate(nonsyn_values):
                        if omega_index != 0:
                            # Access the omega value associated with the correct ORF
                            value *= codons[codon_idx].orf['omega_values'][pos] ** omega_index

                    # Store key of combined omegas, and their multiplied value
                    self.total_omegas[chosen_omegas] = value

    @staticmethod
    def is_start_stop_codon(nt, to_nt):
        """"
        Check if mutation is a STOP codon or nucleotide belongs to a START codon
        :param nt: a Nucleotide object
        :param to_nt: the new state of the Nucleotide as a string
        :return: False if mutation does not create a STOP in any of the codons the nucleotide is part of
        """
        for codon in nt.codons:
            if codon.is_stop() or codon.is_start() or codon.creates_stop(codon.nt_in_pos(nt), to_nt):
                return True

        return False

    def nt_in_event_tree(self, nt):
        """
        Store nucleotide in each branch of the Event Tree where it belongs
        :param nt: a Nucleotide object
        :return: the new omega key
        """
        current_nt = nt.state
        nt_omega_in_tree = {}  # Dictionary to omega keys to find nucleotide on the Event Tree
        new_omega_key = {}  # New omega created on the Event Tree

        for to_nt in NUCLEOTIDES:
            if to_nt != current_nt:

                if not self.is_start_stop_codon(nt, to_nt):
                    # Create one nucleotide key with all the omegas for that substitution
                    omega_cat = nt.omega_keys[to_nt]
                    category = nt.cat_keys[to_nt]
                    cat_branch = self.event_tree['to_nt'][to_nt]['from_nt'][current_nt]['category'][category]['omega']

                    # Store nucleotide according to omega keys
                    if omega_cat:
                        nt_omega_in_tree[to_nt] = omega_cat  # Store string in the nucleotide dict for omega on the tree

                        if omega_cat in cat_branch:  # Omega class is already created on the Event Tree
                            # Check if nucleotide is already in the branch
                            if nt not in cat_branch[omega_cat]['nt']:
                                cat_branch[omega_cat]['nt'].append(nt)

                        else:  # Create the new omega class
                            cat_branch.update({omega_cat: {'nt': [nt]}})
                            new_omega_key[to_nt] = {'cat': category, 'new_omega': omega_cat}

        # Set omega keys on nucleotide according to its path on the Event tree
        nt.set_omega_in_event_tree(nt_omega_in_tree)
        return new_omega_key

    @staticmethod
    def is_transv(from_nt, to_nt):
        """
        Checks if a mutation is a transition or a transversion
        :param from_nt: the current nucleotide
        :param to_nt: the new nucleotide
        :return transv: True if the mutation is a transversion,
                        False if the mutation is a transition,
                        None if the current and new nucleotides are the same
        """
        if from_nt == to_nt:
            transv = None
        else:
            transv = True
            if TRANSITIONS_DICT[from_nt] == to_nt:
                transv = False
        return transv

    @staticmethod
    def codon_iterator(my_orf, start_pos, end_pos):
        """
        Generator to move every three nucleotides (codon)
        :param my_orf: A list of Nucleotides in the ORF
        :param start_pos: The start position of the ORF
        :param end_pos: The end position of the ORF
        :yield codon
        """
        if start_pos > end_pos:  # Negative strand
            my_orf.reverse()
        i = 0
        while i < len(my_orf):
            yield my_orf[i:i + 3]
            i += 3

    def find_codons(self, frame, orf):
        """
        Gets the Codon sequence
        :param frame:  str, the frame of the ORF, e.g., "+1"
        :param orf:  dict, containing the coordinates of the ORF, and the associated omega values
        :return: a list of Codon objects for the specified ORF
        """
        # extract coding sequence
        cds = []
        for start, stop in orf['coords']:
            cds.extend(self.nt_sequence[start:stop])  # concatenates spliced ORFs
        if frame.startswith('-'):
            cds = cds[::-1]  # negative strand ORF

        # Iterate over string by threes and create Codon objects
        codons = []
        for i in range(3, len(cds)+1, 3):
            codons.append(Codon(frame, orf, cds[(i-3):i]))
        return codons

    def check_event_tree(self):
        """
        When debugging, useful to check if nucleotides are being properly stored on the Event Tree
        """
        for key1, to_nt in self.event_tree['to_nt'].items():
            subset = to_nt['from_nt']

            for key2, from_nt in subset.items():
                if key2 != 'T' and from_nt and from_nt.get('nts_in_subs'):
                    nts_in_subs = list(from_nt['nts_in_subs'].keys())
                    if len([1 for tip in nts_in_subs if str(tip).lower() == 't0']) > 0:
                        meta2 = {'nts_in_subs': nts_in_subs}
                        print(f'>>>>>>>>>>>> meta2: from {key2}', meta2)
                        sys.exit(1)


class Nucleotide:
    """
    Stores information about the base, the open reading frames to which a Nucleotide belongs,
    and references to the previous and next base in the sequence.
    """

    def __init__(self, state, pos_in_seq):
        """
        :param state:  str, nucleotide A, C, G or T
        :param pos_in_seq:  int, position of the nucleotide in the sequence
        """
        self.state = state
        self.pos_in_seq = pos_in_seq

        self.codons = []  # A list of codon objects the Nucleotide is part of
        self.complement_state = COMPLEMENT_DICT[self.state]  # The complement state
        self.rates = {}  # A dictionary of mutation rates
        self.omega_keys = {}  # omega keys chosen when calculating rates
        self.cat_keys = {}  # category keys chosen when calculating rates
        self.omega_in_event_tree = {}
        self.mutation_rate = 0  # The total mutation rate
        self.relevant_info = {}

    def __str__(self):
        return self.state

    def __repr__(self):
        return self.state.lower() + str(self.pos_in_seq)

    def __deepcopy__(self, memodict):
        """
        Creates a deepcopy of a Nucleotide.
        Note: A Nucleotide's reference(s) to its Codon(s) will be set in Sequence's deepcopy
        """

        # Creates a new Nucleotide
        cls = self.__class__
        new_nucleotide = cls.__new__(cls)
        memodict[id(self)] = new_nucleotide  # Avoid duplicate copying

        # Copy all attributes except the codons
        new_nucleotide.state = copy.deepcopy(self.state, memodict)
        new_nucleotide.pos_in_seq = copy.deepcopy(self.pos_in_seq, memodict)
        new_nucleotide.complement_state = copy.deepcopy(self.complement_state, memodict)
        new_nucleotide.rates = copy.deepcopy(self.rates, memodict)
        new_nucleotide.mutation_rate = copy.deepcopy(self.mutation_rate, memodict)
        new_nucleotide.omega_keys = copy.deepcopy(self.omega_keys, memodict)
        new_nucleotide.cat_keys = copy.deepcopy(self.cat_keys, memodict)
        new_nucleotide.omega_in_event_tree = copy.deepcopy(self.omega_in_event_tree, memodict)
        new_nucleotide.codons = []  # References to Codons will be set when the Sequence is deep-copied

        return new_nucleotide

    def set_omega_in_event_tree(self, nt_omega_in_tree):
        self.omega_in_event_tree = nt_omega_in_tree

    def set_relevant_info(self, relevant_info):
        self.relevant_info = relevant_info

    def set_state(self, new_state):
        self.state = new_state

    def get_complement_state(self):
        return self.complement_state

    def set_complement_state(self):
        self.complement_state = COMPLEMENT_DICT[self.state]

    def set_rates(self, rates):
        self.rates = rates

    def set_omega(self, omega_keys):
        self.omega_keys = omega_keys

    def set_categories(self, cat_keys):
        self.cat_keys = cat_keys

    def add_codon(self, codon):
        self.codons.append(codon)

    def set_mutation_rate(self, mutation_rate):
        self.mutation_rate = mutation_rate

    def get_mutation_rate(self):
        total_rate = 0
        for to_nt, value in self.rates.items():
            if value:
                total_rate += value
        self.mutation_rate = total_rate

    def get_relevant_info(self):
        """
        Create a dictionary with all relevant information related with the nucleotide
        (Useful for debugging)
        """
        info = {"state": self.state, "position": self.pos_in_seq,
                "rates": self.rates, "mutation rate": self.mutation_rate, "codons": self.codons}

        return info


class Codon:
    """
    Stores information about the frameshift, ORF, and pointers to 3 Nucleotide objects
    """

    def __init__(self, frame, orf, nts_in_codon):
        """
        Create a Codon
        :param frame:  str, the reading frame (+0, +1, +2, -0, -1, -2)
        :param orf:  tuple, containing the reading frame and the coordinates of the orf
        :param nts_in_codon:  a list of pointers to the Nucleotides in the Codon
        """
        self.frame = frame
        self.orf = orf
        self.nts_in_codon = nts_in_codon  # list of Nucleotides in the Codon

    def __repr__(self):
        return ''.join(str(nt) for nt in self.nts_in_codon)

    def nt_in_pos(self, query_nt):
        """
        Finds the position of the Nucleotide in the Codon
        :param query_nt: the Nucleotide of interest
        :return: the position of the Nucleotide in the Codon
        """
        # FIXME: isn't this just self.nts_in_codon.index(query_nt) ?
        for idx, nt in enumerate(self.nts_in_codon):
            if query_nt is nt:
                return idx

    def mutate_codon(self, pos_in_codon, to_nt):
        """
        Changes the state of the specified nucleotide in the codon
        :param pos_in_codon: the position in the Codon
        :param to_nt: the new state of the Nucleotide
        :return codon, mutated_codon: the codon and mutated codon represented as lists of strings
        """
        codon = [str(nt) for nt in self.nts_in_codon]  # Cast all Nucleotides in the Codon to strings
        mutated_codon = codon.copy()
        mutated_codon[pos_in_codon] = to_nt

        return codon, mutated_codon

    def is_nonsyn(self, pos_in_codon, to_nt):
        """
        Finds if a substitution at the specified position results in a non-synonymous mutation
        :param pos_in_codon: the position in the Codon
        :param to_nt: the new state of the Nucleotide (A, T, G, C)
        :return: True if the substitution leads to a non-synonymous mutation,
                 False if the substitution leads to a synonymous mutation
        """
        codon, mutated_codon = self.mutate_codon(pos_in_codon, to_nt)
        return CODON_DICT[''.join(mutated_codon)] != CODON_DICT[''.join(codon)]

    def creates_stop(self, pos_in_codon, to_nt):
        """
        Finds if a substitution at the specified position results in a stop codon
        :param pos_in_codon: the position in the Codon
        :param to_nt: the new state of the Nucleotide (A, T, G, C)
        :return: True if the substitution leads to stop codon,
                 False if the substitution doesn't lead to a stop codon
        """
        codon, mutated_codon = self.mutate_codon(pos_in_codon, to_nt)
        return CODON_DICT[''.join(mutated_codon)] == "*"

    def is_start(self):
        """
        Checks if the codon is a start codon
        :return True of the codon is a start codon, False otherwise
        """
        codon = ''.join(str(nt) for nt in self.nts_in_codon)  # Cast all Nucleotides in the Codon to strings
        if self.frame.startswith('+'):
            return codon == 'ATG' and self.nts_in_codon[0].pos_in_seq == self.orf['coords'][0][0]
        else:
            # +1 to account for non-inclusive indexing
            return codon == 'ATG' and self.nts_in_codon[0].pos_in_seq + 1 == self.orf['coords'][0][1]

    def is_stop(self):
        """
        Checks if the codon is a STOP codon
        :return True of the codon is a STOP codon, False otherwise
        """
        codon = ''.join(str(nt) for nt in self.nts_in_codon)  # Cast all Nucleotides in the Codon to strings
        return codon == 'TAA' or codon == 'TGA' or codon == 'TAG'
