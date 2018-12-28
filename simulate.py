from Bio import Phylo
import random

class Simulate:
    def __init__(self, rate, matrix, alphabet='ACGT'):
        self.rate = rate
        self.matrix = matrix
        self.alphabet = alphabet
        # should include some checks on matrix here (e.g., square)

    # TODO: Ask the professor about the accuracy of this method
    def select_base(self, base_probabilities):
        """
        Select a random letter according to the probabilities of that nucleotide
        Source: https://github.com/hplgit/scipro-primer/blob/master/src-3rd/random/mutate.py
        """
        # Method:
        # http://en.wikipedia.org/wiki/Pseudo-random_number_sampling
        limit = 0
        r = random.random()
        for value in base_probabilities:
            limit += base_probabilities[value]
            if r < limit:
                return value

    def simulate_on_branch(self, seq0, evolution_time):
        """
        Simulate molecular evolution on the branch given starting sequence seq0
        :param seq0:
        :param evolution_time:
        :return:
        """
        seq_list = list(seq0)
        # Generate random waiting times to mutate while sum(t)<=branch_length
        times_sum = 0
        while True:
            random_time = random.random()
            times_sum += random_time
            if round(times_sum, 10) > evolution_time:
                break
            # Mutate sequence
            mutation_site = random.randint(0, len(seq_list)-1)
            nucleotide = seq_list[mutation_site]
            seq_list[mutation_site] = self.select_base(self.matrix[nucleotide])

        return ''.join(seq_list)

    def traverse_tree(self, tree, root_seq):
        """
        Post-order traversal of tree from the root.
        Call simulate_on_branch on each branch and feed the resulting sequence to initialize
        the next call.
        @return Phylo tree with Clade objects annotated with sequences.
        """
        # TODO: check if tree is rooted - if not, throw exception

        # assign root_seq to root Clade
        tree.root.sequence = root_seq

        # annotate Clades with parents
        for clade in tree.find_clades(order='level'):
            for child in clade:
                child.parent = clade

        for node in tree.find_clades(order='level'):
            # TODO: skip the root (sequence already assigned)
            node.sequence = self.simulate_on_branch(node.parent.sequence, node.branch_length)

        return tree

    def get_alignment(self, tree):
        """
        Iterates over tips (terminal nodes) of tree and returns sequence
        attributes as list.
        :param tree:
        :return:
        """


# sim = Sim()  # create an instance of object class Sim
# tree = Phylo.read('<some file>', 'newick')
# tree = sim.traverse_tree(tree, 'ACGT')
# result = sim.get_alignment(tree)
