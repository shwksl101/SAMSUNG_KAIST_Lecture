''' Translate input text with trained model. '''

import torch
import argparse
import dill as pickle
from tqdm import tqdm

import matplotlib.pyplot as plt
import seq2seq_transformer.transformer.Constants as Constants
from torchtext.data import Dataset
from seq2seq_transformer.transformer.Models import Transformer
from seq2seq_transformer.transformer.Translator import Translator


def load_model(opt, device):

    checkpoint = torch.load(opt.model, map_location=device)
    model_opt = checkpoint['settings']

    model = Transformer(
        model_opt.src_vocab_size,
        model_opt.trg_vocab_size,

        model_opt.src_pad_idx,
        model_opt.trg_pad_idx,

        trg_emb_prj_weight_sharing=model_opt.proj_share_weight,
        emb_src_trg_weight_sharing=model_opt.embs_share_weight,
        d_k=model_opt.d_k,
        d_v=model_opt.d_v,
        d_model=model_opt.d_model,
        d_word_vec=model_opt.d_word_vec,
        d_inner=model_opt.d_inner_hid,
        n_layers=model_opt.n_layers,
        n_head=model_opt.n_head,
        dropout=model_opt.dropout).to(device)

    model.load_state_dict(checkpoint['model'])
    print('[Info] Trained model state loaded.')
    return model 


def plot_attention(attention: torch.Tensor, trg_text, src_text, name: str):
    _, ax = plt.subplots()
    _ = ax.pcolor(attention[0][0][0].cpu().detach())

    ax.set_xticks([tick + .5 for tick in range(len(src_text))], minor=False)
    ax.set_yticks([tick + .5 for tick in range(len(trg_text))], minor=False)

    ax.invert_yaxis()
    ax.xaxis.tick_top()
    ax.set_xticklabels(src_text, rotation=90, minor=False)
    ax.set_yticklabels(trg_text, minor=False)
    plt.savefig('attention_' + name + '.png')


def main():
    '''Main Function'''

    parser = argparse.ArgumentParser(description='translate.py')

    parser.add_argument('-model', required=True,
                        help='Path to model weight file')
    parser.add_argument('-data_pkl', required=True,
                        help='Pickle file with both instances and vocabulary.')
    parser.add_argument('-output', default='pred.txt',
                        help="""Path to output the predictions (each line will
                        be the decoded sequence""")
    parser.add_argument('-beam_size', type=int, default=1)
    parser.add_argument('-max_seq_len', type=int, default=100)
    parser.add_argument('-no_cuda', action='store_true')

    opt = parser.parse_args()
    opt.cuda = not opt.no_cuda

    data = pickle.load(open(opt.data_pkl, 'rb'))
    SRC, TRG = data['vocab']['src'], data['vocab']['trg']
    opt.src_pad_idx = SRC.vocab.stoi[Constants.PAD_WORD]
    opt.trg_pad_idx = TRG.vocab.stoi[Constants.PAD_WORD]
    opt.trg_bos_idx = TRG.vocab.stoi[Constants.BOS_WORD]
    opt.trg_eos_idx = TRG.vocab.stoi[Constants.EOS_WORD]

    test_loader = Dataset(examples=data['test'], fields={'src': SRC, 'trg': TRG})
    
    device = torch.device('cuda' if opt.cuda else 'cpu')
    translator = Translator(
        model=load_model(opt, device),
        beam_size=opt.beam_size,
        max_seq_len=opt.max_seq_len,
        src_pad_idx=opt.src_pad_idx,
        trg_pad_idx=opt.trg_pad_idx,
        trg_bos_idx=opt.trg_bos_idx,
        trg_eos_idx=opt.trg_eos_idx).to(device)

    unk_idx = SRC.vocab.stoi[SRC.unk_token]
    for i, example in enumerate(test_loader):
        src_seq = [SRC.vocab.stoi.get(word, unk_idx) for word in example.src]
        pred_seq, dec_slf_attn_list, dec_enc_attn_list = translator.translate_sentence(
            torch.LongTensor([src_seq]).to(device))
        src_seq = [SRC.vocab.itos[idx] for idx in src_seq]
        pred_seq = [TRG.vocab.itos[idx] for idx in pred_seq]
        plot_attention(dec_enc_attn_list, pred_seq, src_seq, name='enc_dec_attention' + str(i))

        if i == 3:
            break

    with open(opt.output, 'w') as f:
        for example in tqdm(test_loader, mininterval=2, desc='  - (Test)', leave=False):
            src_seq = [SRC.vocab.stoi.get(word, unk_idx) for word in example.src]
            pred_seq, dec_slf_attn_list, dec_enc_attn_list = translator.translate_sentence(torch.LongTensor([src_seq]).to(device))
            # pred_line = ' '.join(TRG.vocab.itos[idx] for idx in pred_seq)
            # pred_line = pred_line.replace(Constants.BOS_WORD, '').replace(Constants.EOS_WORD, '')

            src_seq = [SRC.vocab.itos[idx] for idx in src_seq]
            pred_seq = [TRG.vocab.itos[idx] for idx in pred_seq]
            ref_seq = example.trg

            f.write('Source     : ' + ' '.join(src_seq) + '\n')
            f.write('Reference  : ' + ' '.join(ref_seq) + '\n')
            f.write('Prediction : ' + ' '.join(pred_seq[1:-1]) + '\n\n')

    with open('./pred.txt', 'w') as f:
        for example in tqdm(test_loader, mininterval=2, desc='  - (Writing machine translation result)', leave=False):
            src_seq = [SRC.vocab.stoi.get(word, unk_idx) for word in example.src]
            pred_seq, dec_slf_attn_list, dec_enc_attn_list = translator.translate_sentence(torch.LongTensor([src_seq]).to(device))
            pred_seq = [TRG.vocab.itos[idx] for idx in pred_seq]
            f.write(' '.join(pred_seq[1:-1]) + '\n')

    with open('./ref.txt', 'w') as f:
        for example in tqdm(test_loader, mininterval=2, desc='  - (Writing reference sentence)', leave=False):
            ref_seq = example.trg
            f.write(' '.join(ref_seq) + '\n')

    print('[Info] Finished.')


if __name__ == "__main__":
    '''
    Usage: python translate.py -model trained.chkpt -data multi30k.pt -no_cuda
    '''
    main()
