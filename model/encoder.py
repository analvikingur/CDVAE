import torch as t
import torch.nn as nn
import torch.nn.functional as F
from torch_modules.other.highway import Highway
from utils.functions import parameters_allocation_check


class Encoder(nn.Module):
    def __init__(self, params):
        super(Encoder, self).__init__()

        self.params = params

        self.hw1 = Highway(self.params.sum_depth + self.params.word_embed_size, 2, F.relu)

        self.rnn = nn.GRU(input_size=self.params.word_embed_size + self.params.sum_depth,
                          hidden_size=self.params.encoder_rnn_size,
                          num_layers=self.params.encoder_num_layers,
                          batch_first=True,
                          bidirectional=True)

        self.hw2 = Highway(self.params.encoder_rnn_size * 2, 2, F.relu)
        self.fc1 = nn.Linear(self.params.encoder_rnn_size * 2, 4096)
        self.hw3 = Highway(4096, 2, F.relu)
        self.to_hidden = nn.Linear(4096, self.params.hidden_size)

    def forward(self, input):
        """
        :param input: [batch_size, seq_len, embed_size] tensor
        :return: context of input sentenses with shape of [batch_size, latent_variable_size]
        """

        [batch_size, seq_len, embed_size] = input.size()

        input = input.view(-1, embed_size)
        input = self.hw1(input)
        input = input.view(batch_size, seq_len, embed_size)

        assert parameters_allocation_check(self), \
            'Invalid CUDA options. Parameters should be allocated in the same memory'

        ''' Unfold rnn with zero initial state and get its final state from the last layer
        '''
        _, final_state = self.rnn(input)

        final_state = final_state.view(self.params.encoder_num_layers, 2, batch_size, self.params.encoder_rnn_size)
        final_state = final_state[-1]
        h_1, h_2 = final_state[0], final_state[1]
        final_state = t.cat([h_1, h_2], 1)
        final_state = self.hw2(final_state)

        result = self.fc1(final_state)
        result = self.hw3(result)
        result = self.to_hidden(result)

        [result_chanels, h, w] = self.params.hidden_view
        return result.view(-1, result_chanels, h, w)
