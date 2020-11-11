import torch
import torch.nn as nn
from nlpmodels.models.transformer_blocks import sublayers, attention, gpt_decoder
from nlpmodels.utils.transformer_batch import TransformerBatch
from nlpmodels.utils.gpt_dataset import GPTDataset
from nlpmodels.utils import train


class GPT(nn.Module):
    """
    The GPT class of the decoder-only Transformer.

    MORE DESCRIPTION.
    """

    def __init__(self,
                 vocab_size: int,
                 num_layers_per_stack: int = 12,
                 dim_model: int = 768,
                 dim_ffn: int = 3072,
                 num_heads: int = 12,
                 block_size: int = 512,
                 dropout: float = 0.1):
        """
        Args:
           vocab_size (int): size of the target vocabulary.
           num_layers_per_stack (int): number of sequential encoder/decoder layers.
           dim_model (int): size of the embedding space.
           dim_ffn (int): size of the residual/skip-connection hidden layer.
           num_heads (int): number of simultaneous attention heads calculated during attention.
           block_size (int): the context window of the input/output sequences.
           dropout (float): Hyper-parameter used in drop-out regularization in training.
        """
        super(GPT, self).__init__()

        # (1) calculate embeddings
        self._embeddings = sublayers.NormalizedEmbeddingsLayer(vocab_size, dim_model)
        # (2) calculate positional_encoding (learn-able this time) + drop-out
        self._pos_encoding = nn.Sequential(nn.Parameter(torch.zeros(1, block_size, dim_model)),
                                            nn.Dropout(dropout))
        # (3) Pass embeddings + pe to GPT decoder block
        self._decoder_block = gpt_decoder.GPTCompositeDecoder(
            gpt_decoder.GPTDecoderBlock(block_size,
                                     # use the second drop-out not found in the original Transformer
                                     attention.MultiHeadedAttention(num_heads, dim_model, dropout, dropout),
                                     # replace activation function with GELU
                                     sublayers.PositionWiseFFNLayer(dim_model, dim_ffn, nn.GELU()),
                                     dropout),num_layers_per_stack)

        # (4) put through final linear layer
        self._final_linear = nn.Linear(dim_model, vocab_size)

        # init weights
        # TODO: Add init weights
        self._init_weights()

    def _init_weights(self):
        """
        Initialize all parameters to be trained using Xavier Uniform.
        Note: parameters added to buffer will not be affected.
        """
        for parameter in self.parameters():
            if parameter.dim() - 1:
                if isinstance(parameter, (nn.Linear, nn.Embedding)):
                    parameter.weight.data.normal_(mean=0.0, std=0.02)

    def _decode(self, index) -> torch.Tensor:

        embeddings = self._embeddings(index)
        # Add output embeddings to pos_encoding, apply drop out
        pos_encoding = self._pos_encoding(embeddings)

        return self._decoder_block(pos_encoding)

    def forward(self, data: TransformerBatch) -> torch.Tensor:

        # pass through decoder blocks
        decode = self._decode(data.src)
        # calculate yhat
        yhat = self._final_linear(decode)

        return yhat


if __name__ == '__main__':
    from nlpmodels.utils import train, utils, transformer_dataset
    from argparse import Namespace

    utils.set_seed_everywhere()
    args = Namespace(
        # Model hyper-parameters
        num_layers_per_stack=2,  # original value = 12
        dim_model=768,
        dim_ffn=3072,
        num_heads=12,
        block_size=512, # context window
        dropout=0.1,
        # Training hyper-parameters
        num_epochs=15,
        learning_rate=0.0,
        batch_size=64,
    )

    train_loader, vocab = GPTDataset.get_training_dataloader(args)
    model = GPT(vocab_size = len(vocab),
                num_layers_per_stack= args.num_layers_per_stack,
                dim_model = args.dim_model,
                dim_ffn = args.dim_ffn,
                num_heads = args.num_heads,
                block_size = args.block_size,
                dropout = args.dropout)
    trainer = train.GPTTrainer(args,vocab.mask_index,model,train_loader,vocab)
    trainer.run()
