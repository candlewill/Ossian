#!/usr/bin/env python
# -*- coding: utf-8 -*-
## Project: Simple4All - March 2016 - www.simple4all.org 
## Contact: Oliver Watts - owatts@staffmail.ed.ac.uk


from UtteranceProcessor import SUtteranceProcessor
from util.NodeProcessors import *

from distutils.spawn import find_executable

from naive.naive_util import readlist
from util.speech_manip import get_speech, put_speech

import sys
import numpy as np
import numpy
import math

import time

import glob

import util.Wavelets as cwt
import util.cwt_utils
import tensorflow as tf

### Add Merlin tools to import path:-
this_file_location = os.path.split(os.path.realpath(os.path.abspath(os.path.dirname(__file__))))[0]
merlin_direc = os.path.join(this_file_location, '..', 'tools', 'merlin', 'src')
sys.path.append(merlin_direc)

from processors.FeatureExtractor import get_world_fft_and_apdim
from processors import data_utils

try:
    from frontend.label_normalisation import HTSLabelNormalisation, HTSDurationLabelNormalisation
    from frontend.mlpg_fast import MLParameterGenerationFast
except:
    sys.exit('trouble importting from merlin -- installed properly?')


class NN(object):
    def __init__(self, model_dir, inp_dim, out_dim):
        self.inp_dim = inp_dim
        self.out_dim = 5
        self.load_from_files(model_dir)

    def load_from_files(self, model_dir):
        self.model_dir = model_dir
        self.sess = tf.Session()
        new_saver = tf.train.import_meta_graph(os.path.join(model_dir, "TF_Model.ckpt.meta"))
        print("loading the model parameters...")
        new_saver.restore(self.sess, os.path.join(model_dir, "TF_Model.ckpt"))
        print("The model parameters are successfully restored")
        self.inp_scaler = data_utils.load_norm_stats(os.path.join(model_dir, "input_249_MINMAX_425.norm"), self.inp_dim,
                                                     method="MINMAX")
        self.out_scaler = data_utils.load_norm_stats(os.path.join(model_dir, "output_249_MINMAX_187.norm"),
                                                     self.out_dim, method="MINMAX")

    def predict(self, input, input_normalisation=True, output_denormalisation=True):
        nframe, ndim = numpy.shape(input)
        print("The input shape is %s X %s" % (nframe, ndim))

        if input_normalisation:
            ## normalise:
            data_utils.norm_data(input, self.inp_scaler)

        output_layer = tf.get_collection("output_layer")[0]
        input_layer = tf.get_collection("input_layer")[0]
        is_training_batch = tf.get_collection("is_training_batch")[0]
        y_predict = self.sess.run(output_layer,
                                  feed_dict={input_layer: input, is_training_batch: False})

        y_predict = data_utils.denorm_data(y_predict, self.out_scaler)

        return y_predict


class NNAcousticModel(NN):
    ## add speech specific stuff, like splitting into streams and param gen
    def __init__(self, model_dir, question_file_name,
                 silence_pattern='/2:sil/'):  ## TODO: where to handle silence pattern? Currently fragile
        super(NNAcousticModel, self).__init__(model_dir)
        self.load_stream_info()
        self.label_expander = HTSLabelNormalisation(question_file_name=question_file_name)
        self.param_generator = MLParameterGenerationFast()  # ParameterGeneration()
        self.silent_feature_indices = self.get_silent_feature_indices(question_file_name, silence_pattern)

        std = self.output_std
        m = numpy.shape(std)

        std = std.reshape((1, self.outdim))

        self.stream_std = self.split_into_streams(std)

    def get_silent_feature_indices(self, question_file_name, silence_pattern):
        print 'get_silent_feature_indices'
        indices = []
        questions = [q for q in readlist(question_file_name) if q != '']
        questions = [q for q in questions if 'CQS' not in q]
        for (i, question) in enumerate(questions):
            if silence_pattern in question:
                indices.append(i)
                print 'silence question found:'
                print question
        return indices

    def load_stream_info(self):
        stream_info_fname = os.path.join(self.model_dir, 'stream_info.txt')
        assert os.path.isfile(stream_info_fname)
        stream_data = readlist(stream_info_fname)
        stream_data = [line.split(' ') for line in stream_data]
        assert len(stream_data) == 4
        (self.instreams, indims, self.outstreams, outdims) = stream_data
        indims = [int(val) for val in indims]
        outdims = [int(val) for val in outdims]

        ## note that indims are not network input, but input to acoustic preprocessing of data!
        assert self.outdim == sum(outdims)
        self.indims = dict(zip(self.instreams, indims))
        self.outdims = dict(zip(self.outstreams, outdims))

    ## FOR DEBUGGING:-
    def generate_from_norm_binary_lab(self, bin_label_file, labdim, outwave, enforce_silence=False, mlpg=True,
                                      vuv_thresh=0.5, fzero_scale=1.0):

        input = get_speech(bin_label_file, labdim)

        # input = input[:500,:]
        output = self.predict(input, input_normalisation=True)

        put_speech(output, '/afs/inf.ed.ac.uk/user/o/owatts/temp/cpu_gen/undenorm_66_015_from_norm_lab.cmp')
        sys.exit('vliadnviadnvdvn stoped early')

        streams = self.split_into_streams(output)

        if mlpg:
            mlpged = {}
            for (stream, data) in streams.items():
                if stream in self.indims:
                    mlpg_data = self.param_generator.generation(data, self.stream_std[stream], self.indims[stream])
                else:
                    mlpg_data = data
                mlpged[stream] = mlpg_data
            streams = mlpged

        else:
            # take statics only!
            statics = {}
            for (stream, data) in streams.items():
                if stream in self.indims:
                    statics[stream] = data[:, :self.indims[stream]]
                else:  ## for e.g. vuv
                    statics[stream] = data
            streams = statics

        if enforce_silence:
            for (stream, data) in streams.items():
                print input[:, self.silent_feature_indices]
                sys.exit('ntfbdfbsfrbsfbr')
                silent_frames = numpy.sum(input[:, self.silent_feature_indices], axis=1)
                data[silent_frames == 1.0, :] = 0.0
                streams[stream] = data

        if 'lf0' in streams:
            fzero = numpy.exp(streams['lf0'])

            if 'vuv' in streams:
                vuv = streams['vuv']
                lf0 = streams['lf0']
                fzero[vuv <= vuv_thresh] = 0.0

            fzero *= fzero_scale

            streams['lf0'] = fzero

        self.world_resynth(streams, outwave)

    def generate(self, htk_label_file, enforce_silence=True, mlpg=True, fill_unvoiced_gaps=0, \
                 variance_expansion=1.0, vuv_thresh=0.5, fzero_scale=1.0):

        input = self.label_expander.load_labels_with_state_alignment(htk_label_file)
        output = self.predict(input)
        streams = self.split_into_streams(output)

        if mlpg:
            mlpged = {}
            for (stream, data) in streams.items():
                if stream in self.indims:
                    mlpg_data = self.param_generator.generation(data, self.stream_std[stream], self.indims[stream])
                else:
                    mlpg_data = data
                mlpged[stream] = mlpg_data
            streams = mlpged

        else:
            # take statics only!
            statics = {}
            for (stream, data) in streams.items():
                if stream in self.indims:
                    statics[stream] = data[:, :self.indims[stream]]
                else:  ## for e.g. vuv
                    statics[stream] = data
            streams = statics

        ## TODO: handle F0 separately
        if variance_expansion > 0.0:
            new_streams = {}
            for (stream, data) in streams.items():
                new_streams[stream] = self.simple_scale_variance_wrapper_p0(streams[stream], stream)
            streams = new_streams

        # impose 0 ceiling on baps, else we get artifacts:-
        # (I think this was the problem I was trying to fix by not scaling f0 and energy previously)
        streams['bap'] = np.minimum(streams['bap'], np.zeros(np.shape(streams['bap'])))

        #         if fill_unvoiced_gaps > 0:
        #             vuv = streams['vuv']
        #             ## turn from soft to binary:
        #             binary_vuv = np.zeros(np.shape(vuv))
        #             binary_vuv[vuv > vuv_thresh] = 1
        #             vuv = binary_vuv
        #             gaplength = fill_unvoiced_gaps
        #             vuv = fill_short_unvoiced_gaps(vuv, gaplength)
        #             print vuv
        #             streams['vuv'] = vuv
        #

        if enforce_silence:
            for (stream, data) in streams.items():
                silent_frames = numpy.sum(input[:, self.silent_feature_indices], axis=1)
                data[silent_frames == 1.0, :] = 0.0
                streams[stream] = data

        if 'lf0' in streams:
            fzero = numpy.exp(streams['lf0'])

            if 'vuv' in streams:
                vuv = streams['vuv']
                lf0 = streams['lf0']
                fzero[vuv <= vuv_thresh] = 0.0

            fzero *= fzero_scale

            streams['lf0'] = fzero

        # self.world_resynth(streams, outwave)
        return streams

    def split_into_streams(self, input):
        nframe, ndim = numpy.shape(input)
        assert ndim == self.outdim, (ndim, self.outdim)

        start = 0
        outputs = {}
        for stream in self.outstreams:
            end = start + self.outdims[stream]
            print stream
            outputs[stream] = input[:, start:end]
            start = end

        return outputs

        # def enforce_silence(streams):

    #    def expand_label():

    def simple_scale_variance_wrapper_0(self, speech, stream):

        return speech

    def simple_scale_variance_wrapper_p0(self, speech, stream):

        if stream == 'mgc':
            cep_speech = self.simple_scale_variance(speech, stream, gv_weight=1.0)
            ene_speech = self.simple_scale_variance(speech, stream, gv_weight=0.0)
            scaled_speech = np.hstack([ene_speech[:, :1], cep_speech[:, 1:]])
        else:
            scaled_speech = speech
        return scaled_speech

    def simple_scale_variance_wrapper_p2(self, speech, stream):

        if stream == 'mgc':
            cep_speech = self.simple_scale_variance(speech, stream, gv_weight=1.0)
            ene_speech = self.simple_scale_variance(speech, stream, gv_weight=0.2)
            scaled_speech = np.hstack([ene_speech[:, :1], cep_speech[:, 1:]])
        if stream == 'lf0':
            scaled_speech = self.simple_scale_variance(speech, stream, gv_weight=0.2)
        else:
            scaled_speech = speech
        return scaled_speech

    def simple_scale_variance_wrapper_p5(self, speech, stream):

        if stream == 'mgc':
            cep_speech = self.simple_scale_variance(speech, stream, gv_weight=1.0)
            ene_speech = self.simple_scale_variance(speech, stream, gv_weight=0.5)
            scaled_speech = np.hstack([ene_speech[:, :1], cep_speech[:, 1:]])
        if stream == 'lf0':
            scaled_speech = self.simple_scale_variance(speech, stream, gv_weight=0.5)
        else:
            scaled_speech = speech
        return scaled_speech

    def simple_scale_variance_wrapper_1(self, speech, stream):

        if stream == 'mgc':
            cep_speech = self.simple_scale_variance(speech, stream, gv_weight=1.0)
            ene_speech = self.simple_scale_variance(speech, stream, gv_weight=1.0)
            scaled_speech = np.hstack([ene_speech[:, :1], cep_speech[:, 1:]])
        if stream == 'lf0':
            scaled_speech = self.simple_scale_variance(speech, stream, gv_weight=1.0)
        else:
            scaled_speech = speech
        return scaled_speech

    def simple_scale_variance_wrapper_m2(self, speech, stream):

        if stream == 'mgc':
            cep_speech = self.simple_scale_variance(speech, stream, gv_weight=1.0)
            ene_speech = self.simple_scale_variance(speech, stream, gv_weight=0.0)
            scaled_speech = np.hstack([ene_speech[:, :1], cep_speech[:, 1:]])
        if stream == 'lf0':
            scaled_speech = self.simple_scale_variance(speech, stream, gv_weight=0.2)
        if stream == 'bap':
            scaled_speech = self.simple_scale_variance(speech, stream, gv_weight=1.0)

        else:
            scaled_speech = speech
        return scaled_speech

    def simple_scale_variance_wrapper_n2(self, speech, stream):

        if stream == 'mgc':
            cep_speech = self.simple_scale_variance(speech, stream, gv_weight=1.0)
            ene_speech = self.simple_scale_variance(speech, stream, gv_weight=0.2)
            scaled_speech = np.hstack([ene_speech[:, :1], cep_speech[:, 1:]])
        else:
            scaled_speech = speech
        return scaled_speech

    def simple_scale_variance_wrapper_nfull(self, speech, stream):

        if stream == 'mgc':
            scaled_speech = self.simple_scale_variance(speech, stream, gv_weight=1.0)
        else:
            scaled_speech = speech
        return scaled_speech

    def simple_scale_variance(self, speech, stream, gv_weight=1.0):

        stream_std = self.stream_std[stream][0, :]
        static_std = stream_std[:self.indims[stream]]

        assert gv_weight <= 1.0 and gv_weight >= 0.0
        local_weight = 1.0 - gv_weight

        utt_mean = numpy.mean(speech, axis=0)
        utt_std = numpy.std(speech, axis=0)

        global_std = numpy.transpose(static_std)
        weighted_global_std = (gv_weight * global_std) + (local_weight * utt_std)
        std_ratio = weighted_global_std / utt_std

        nframes, ndim = numpy.shape(speech)
        utt_mean_matrix = numpy.tile(utt_mean, (nframes, 1))
        std_ratio_matrix = numpy.tile(std_ratio, (nframes, 1))

        scaled_speech = ((speech - utt_mean_matrix) * std_ratio_matrix) + utt_mean_matrix

        return scaled_speech


class NNDurationModel(NN):
    ## assume single stream, with 1 output = with n elements for n states of 1 phone
    def __init__(self, model_dir, question_file_name):
        self.label_expander = HTSDurationLabelNormalisation(question_file_name=question_file_name)
        # self.label_expander = HTSLabelNormalisation(question_file_name=question_file_name, add_frame_features=False, subphone_feats='none') # , label_type='phone_align')
        super(NNDurationModel, self).__init__(model_dir, self.label_expander.dimension)

    def generate(self, htk_label_file, enforce_silence=False, mlpg=True, vuv_thresh=0.5, fzero_scale=1.0):
        input = self.label_expander.load_labels_with_state_alignment(htk_label_file)
        output = self.predict(input)

        ## as these are state durations in frames, enforce integer valued output, values greater than 0:
        output = numpy.round(output)
        output[output < 1] = 1
        output = numpy.array(output, dtype='int')

        return output


#### classes which apply NN models to utterances: #####

class NNDurationPredictor(SUtteranceProcessor):
    def __init__(self, processor_name='duration_predictor', target_nodes='//segment', \
                 input_label_filetype='lab_dur', \
                 question_file='questions_dur.hed.cont', \
                 ms_framerate=5, \
                 child_tag='state', \
                 ):

        self.processor_name = processor_name
        self.target_nodes = target_nodes
        self.input_label_filetype = input_label_filetype
        self.question_file_name = question_file
        self.ms_framerate = ms_framerate
        self.child_tag = child_tag

        super(NNDurationPredictor, self).__init__()

    def verify(self, voice_resources):
        self.voice_resources = voice_resources

        ## Set path to HTS binaries from voice resources:
        self.hts_dir = self.voice_resources.path[c.BIN]
        self.model_dir = os.path.join(self.get_location())

        try:
            qfile = os.path.join(self.voice_resources.path[c.TRAIN],
                                 self.question_file_name + '.cont')  ## TODO: cont handling
            ## TODO: pack up qfile too
            self.model = NNDurationModel(self.model_dir, qfile)
            self.trained = True
        except:
            print('Cannot load NN model from model_dir: %s -- not trained yet' % self.model_dir)
            self.trained = False

        ## TODO: neater handling of option of using .cont questions 
        self.question_file_path = self.voice_resources.get_filename(self.question_file_name, c.TRAIN)

        ## also one attachd to self.model, but need this in training before self.model created...
        # self.label_expander = HTSDurationLabelNormalisation(question_file_name=self.question_file_path)

    def do_training(self, speech_corpus, text_corpus):

        if self.trained:
            print 'NNDurationPredictor already trained'
            return

        print 'Training of NNDurationPredictor itself not supported within Ossian -- '
        print 'use Merlin to train on the prepared data'
        if not os.path.isdir(self.model_dir):
            os.makedirs(self.model_dir)

        ## TODO: refactor to share the block below and write_merlin_config between 
        ## NNDurationPredictor and NNAcousticPredictor

        ### Write merlin training list:
        utts_to_use = []
        for utterance in speech_corpus:
            if utterance.has_external_data(self.input_label_filetype):
                utts_to_use.append(utterance.get("utterance_name"))
        writelist(utts_to_use, os.path.join(self.model_dir, 'filelist.txt'))
        n_utts = len(utts_to_use)

        self.write_merlin_config(n_utts=n_utts)

    def write_merlin_config(self, n_utts=0):
        this_directory = os.path.realpath(os.path.abspath(os.path.dirname(__file__)))
        ossian_root = os.path.abspath(os.path.join(this_directory, '..', '..'))
        template_fname = os.path.join(ossian_root, 'scripts', 'merlin_interface',
                                      'feed_forward_dnn_ossian_duration_model.conf')

        f = open(template_fname, 'r')
        config_string = f.read()
        f.close()

        ## You need to divide the files available up into train/validation/test data. We don't need
        ## to do any testing, but set test_file_number to 1 to keep the tools happy. Split the remaining
        ## files between train and validation. Using about 5% or 10% of the data for validation is 
        ## pretty standard. 
        n_test = 1
        n_valid = int(float(n_utts) * 0.05)  ## take 5%
        extra = 0  ## hack - so that if merlin's data preparation fails for a couple of utterances, training won't break
        n_train = n_utts - (n_valid + n_test + extra)
        for quantity in [n_train, n_test, n_valid]:
            assert quantity > 0

        ## replace the markers in template with the relevant values:

        for (placeholder, value) in [('__INSERT_PATH_TO_OSSIAN_HERE__', ossian_root),
                                     ('__INSERT_LANGUAGE_HERE__', self.voice_resources.lang),
                                     ('__INSERT_SPEAKER_HERE__', self.voice_resources.speaker),
                                     ('__INSERT_RECIPE_HERE__', self.voice_resources.configuration),
                                     ('__INSERT_FILELIST_HERE__', os.path.join(self.model_dir, 'filelist.txt')),
                                     ('__INSERT_NUMBER_OF_TRAINING_FILES_HERE__', n_train),
                                     ('__INSERT_NUMBER_OF_VALIDATION_FILES_HERE__', n_valid),
                                     ('__INSERT_NUMBER_OF_TEST_FILES_HERE__', n_test)]:
            config_string = config_string.replace(placeholder, str(value))

        # mgc_dim = self.mcep_order + 1
        # lf0_dim = 1
        # _, bap_dim = get_world_fft_and_apdim(self.sample_rate)
        # for (placeholder, value) in [('__INSERT_MGC_DIM_HERE__', mgc_dim), 
        #                              ('__INSERT_DELTA_MGC_DIM_HERE__', mgc_dim * 3), 
        #                              ('__INSERT_BAP_DIM_HERE__', bap_dim), 
        #                              ('__INSERT_DELTA_BAP_DIM_HERE__', bap_dim * 3), 
        #                              ('__INSERT_LF0_DIM_HERE__', lf0_dim), 
        #                              ('__INSERT_DELTA_BAP_DIM_HERE__', lf0_dim * 3)  ]:
        #      config_string = config_string.replace(placeholder, str(value))

        ### Write config file:--        
        conf_file = os.path.join(self.model_dir, 'config.cfg')
        f = open(conf_file, 'w')
        f.write(config_string)
        f.close()

        ### Work out the processor's location in voices (i.e. where it will
        ### be after training has happened) -- TODO: find a cleaner way to do this:--
        voice_dir = os.path.join(ossian_root, 'voices', self.voice_resources.lang, \
                                 self.voice_resources.speaker, self.voice_resources.configuration, \
                                 'processors', self.processor_name)

        print '------------'
        print 'Wrote config file to: '
        print conf_file
        print 'Edit this config file as appropriate and use for training with Merlin.'
        print 'In particular, you will want to increase training_epochs to train real voices'
        print 'You will also want to experiment with learning_rate, batch_size, hidden_layer_size, hidden_layer_type'
        print
        print 'To train with Merlin and then store the resulting model in a format suitable for Ossian, please do:'
        print
        print 'cd %s' % (ossian_root)
        print 'export THEANO_FLAGS=""; python ./tools/merlin/src/run_merlin.py %s' % (conf_file)
        print 'python ./scripts/util/store_merlin_model.py %s %s' % (conf_file, voice_dir)
        print
        print '------------'

    def process_utterance(self, utt):
        if utt.has_attribute("waveform"):
            # print "Utt has a natural waveform -- don't synthesise"
            return

        # if not self.trained:
        #             print 'WARNING: Cannot apply processor %s till model is trained'%(self.processor_name)
        #             return

        label = utt.get_filename(self.input_label_filetype)

        durations = self.model.generate(label)

        m, n = numpy.shape(durations)
        nodes = utt.xpath(self.target_nodes)
        assert m == len(nodes)

        start = 0
        for (node, state_durs) in zip(nodes, durations):
            for dur in state_durs:
                end = start + dur
                child = Element(self.child_tag)
                child.set('start', str(start * self.ms_framerate))
                child.set('end', str(end * self.ms_framerate))
                node.add_child(child)

                start = end


class NNAcousticPredictor(SUtteranceProcessor):
    def __init__(self, processor_name='acoustic_predictor', input_label_filetype='dnn_lab', \
                 output_filetype='wav', \
                 question_file_name='questions_dnn.hed.cont', \
                 variance_expansion=0.0, \
                 fill_unvoiced_gaps=0, \
                 sample_rate=16000, \
                 alpha=0.42, \
                 mcep_order=39
                 ):

        self.processor_name = processor_name
        self.input_label_filetype = input_label_filetype
        self.output_filetype = output_filetype
        self.question_file_name = question_file_name
        self.variance_expansion = variance_expansion
        self.fill_unvoiced_gaps = fill_unvoiced_gaps
        self.sample_rate = sample_rate
        self.alpha = alpha
        self.mcep_order = mcep_order

        super(NNAcousticPredictor, self).__init__()

    def verify(self, voice_resources):
        return None
        self.voice_resources = voice_resources

        ## Set path to HTS binaries from voice resources:
        self.hts_dir = self.voice_resources.path[c.BIN]

        self.model_dir = os.path.join(self.get_location())

        try:
            qfile = os.path.join(self.voice_resources.path[c.TRAIN], self.question_file_name)
            ## TODO: pack up qfile too
            self.model = NNAcousticModel(self.model_dir, qfile)
            self.trained = True
        except:
            # sys.exit('Cannot load NN model from model_dir: %s'%self.model_dir)
            print('Cannot load NN model from model_dir: %s -- not trained yet' % self.model_dir)
            self.trained = False

        ## replicate GetFFTSizeForCheapTrick in src/cheaptrick.cpp:
        kLog2 = 0.69314718055994529  # set in src/world/constantnumbers.h 
        f0_floor = 71.0  ## set in analysis.cpp
        self.fftl = math.pow(2.0, (1.0 + int(math.log(3.0 * self.sample_rate / f0_floor + 1) / kLog2)))

    def do_training(self, speech_corpus, text_corpus):

        print 'Training of NNAcousticPredictor itself not supported within Ossian -- '
        print 'use Merlin to train on the prepared data'
        if not os.path.isdir(self.model_dir):
            os.makedirs(self.model_dir)

            ## TODO: refactor to share the block below and write_merlin_config between
        ## NNDurationPredictor and NNAcousticPredictor

        ### Write merlin training list:
        utts_to_use = []
        for utterance in speech_corpus:
            if utterance.has_external_data(self.input_label_filetype):
                utts_to_use.append(utterance.get("utterance_name"))
        writelist(utts_to_use, os.path.join(self.model_dir, 'filelist.txt'))
        n_utts = len(utts_to_use)

        self.write_merlin_config(n_utts=n_utts)

    def write_merlin_config(self, n_utts=0):
        this_directory = os.path.realpath(os.path.abspath(os.path.dirname(__file__)))
        ossian_root = os.path.abspath(os.path.join(this_directory, '..', '..'))
        template_fname = os.path.join(ossian_root, 'scripts', 'merlin_interface',
                                      'feed_forward_dnn_ossian_acoustic_model.conf')

        f = open(template_fname, 'r')
        config_string = f.read()
        f.close()

        ## You need to divide the files available up into train/validation/test data. We don't need 
        ## to do any testing, but set test_file_number to 1 to keep the tools happy. Split the remaining
        ## files between train and validation. Using about 5% or 10% of the data for validation is 
        ## pretty standard. 
        n_test = 1
        n_valid = int(float(n_utts) * 0.05)  ## take 5%
        extra = 0  ## hack - so that if merlin's data preparation fails for a couple of utterances, training won't break
        n_train = n_utts - (n_valid + n_test + extra)
        for quantity in [n_train, n_test, n_valid]:
            assert quantity > 0

        ## replace the markers in template with the relevant values:

        for (placeholder, value) in [('__INSERT_PATH_TO_OSSIAN_HERE__', ossian_root),
                                     ('__INSERT_LANGUAGE_HERE__', self.voice_resources.lang),
                                     ('__INSERT_SPEAKER_HERE__', self.voice_resources.speaker),
                                     ('__INSERT_RECIPE_HERE__', self.voice_resources.configuration),
                                     ('__INSERT_FILELIST_HERE__', os.path.join(self.model_dir, 'filelist.txt')),
                                     ('__INSERT_NUMBER_OF_TRAINING_FILES_HERE__', n_train),
                                     ('__INSERT_NUMBER_OF_VALIDATION_FILES_HERE__', n_valid),
                                     ('__INSERT_NUMBER_OF_TEST_FILES_HERE__', n_test)]:
            config_string = config_string.replace(placeholder, str(value))

        mgc_dim = self.mcep_order + 1
        lf0_dim = 1
        _, bap_dim = get_world_fft_and_apdim(self.sample_rate)
        for (placeholder, value) in [('__INSERT_MGC_DIM_HERE__', mgc_dim),
                                     ('__INSERT_DELTA_MGC_DIM_HERE__', mgc_dim * 3),
                                     ('__INSERT_BAP_DIM_HERE__', bap_dim),
                                     ('__INSERT_DELTA_BAP_DIM_HERE__', bap_dim * 3),
                                     ('__INSERT_LF0_DIM_HERE__', lf0_dim),
                                     ('__INSERT_DELTA_LF0_DIM_HERE__', lf0_dim * 3)]:
            config_string = config_string.replace(placeholder, str(value))

        ### Write config file:--        
        conf_file = os.path.join(self.model_dir, 'config.cfg')
        f = open(conf_file, 'w')
        f.write(config_string)
        f.close()

        ### Work out the processor's location in voices (i.e. where it will
        ### be after training has happened) -- TODO: find a cleaner way to do this:--
        voice_dir = os.path.join(ossian_root, 'voices', self.voice_resources.lang, \
                                 self.voice_resources.speaker, self.voice_resources.configuration, \
                                 'processors', self.processor_name)

        print '------------'
        print 'Wrote config file to: '
        print conf_file
        print 'Edit this config file as appropriate and use for training with Merlin.'
        print 'In particular, you will want to increase training_epochs to train real voices'
        print 'You will also want to experiment with learning_rate, batch_size, hidden_layer_size, hidden_layer_type'
        print
        print 'To train with Merlin and then store the resulting model in a format suitable for Ossian, please do:'
        print
        print 'cd %s' % (ossian_root)
        print 'export THEANO_FLAGS='' ; python ./tools/merlin/src/run_merlin.py %s' % (conf_file)
        print 'python ./scripts/util/store_merlin_model.py %s %s' % (conf_file, voice_dir)
        print
        print '------------'

    def process_utterance(self, utt):
        if utt.has_attribute("waveform"):
            # print "Utt has a natural waveform -- don't synthesise"
            return

        # if not self.trained:
        #             print 'WARNING: Cannot apply processor %s till model is trained'%(self.processor_name)
        #             return

        label = utt.get_filename(self.input_label_filetype)
        owave = utt.get_filename(self.output_filetype)

        streams = self.model.generate(label, variance_expansion=self.variance_expansion, \
                                      fill_unvoiced_gaps=self.fill_unvoiced_gaps)

        self.world_resynth(streams, owave)

    def world_resynth(self, streams, outfile):
        '''
        refactored this from AcousticModel. TODO: clean up more, and replace also in AM
        '''

        bin_dir = self.hts_dir  ## world here too

        #         alpha = 0.42
        #         order = 39
        #         fftl = 1024
        #         sr = 16000

        alpha = self.alpha  # 0.71
        order = self.mcep_order  # 59
        sr = self.sample_rate  # 44100
        fftl = self.fftl

        for (stream, data) in streams.items():
            put_speech(data, '/tmp/tmp.%s' % (stream))
            comm = bin_dir + "/x2x +fd /tmp/tmp." + stream + " >/tmp/tmp_d." + stream
            print comm
            os.system(comm)

        comm = "%s/mgc2sp -a %s -g 0 -m %s -l %s -o 2 /tmp/tmp.mgc | %s/sopr -d 32768.0 -P | %s/x2x +fd -o > /tmp/tmp.spec" % (
            bin_dir, alpha, order, fftl, bin_dir, bin_dir)
        print comm
        os.system(comm)

        '''Avoid:   x2x : error: input data is over the range of type 'double'!
               -o      : clip by minimum and maximum of output data            
                 type if input data is over the range of               
                 output data type.
        '''

        comm = "%s/synth %s %s /tmp/tmp_d.lf0 /tmp/tmp.spec /tmp/tmp_d.bap /tmp/tmp.resyn.wav" % (bin_dir, fftl, sr)
        print comm
        os.system(comm)

        os.system("mv /tmp/tmp.resyn.wav " + outfile)
        print 'Produced %s' % (outfile)


def fill_short_unvoiced_gaps(track, gaplength):
    '''
    fill in with 1s seqences of zeros up to length gaplength which are surrounded by 1s
    
    TODO: look at Antti's util.acoustic_feats -- lots of functions to do this kind of thing
    '''
    for i in xrange(len(track) - (gaplength + 1)):
        start = track[i]
        end = track[i + (gaplength + 1)]
        if start == 1 and end == 1:
            for j in xrange(i, i + (gaplength + 1)):
                track[j] = 1
    return track


def wavelet_manipulation(sequence, std_scaling_factors, scale_distance=0.5, num_octaves=12):
    #   sequence = sequence[:512]
    #    self.scale_distance = float(self.config.get('scale_distance',0.5))
    #    self.num_octaves = int(self.config.get('num_octaves', 12))

    # capetown wavelet package setup
    s0 = 2  # first scale in number of frames
    dj = scale_distance  # distance of bands in octaves
    J = num_octaves  # number of octaves
    maxscale = len(sequence) / (2.0 ** J)  # maximum scale defined as proportion of the signal

    # perform wavelet transform, select appropriate scale           
    wavelet_matrix = cwt.MexicanHat(sequence, maxscale, int(1 / scale_distance), scaling="log")

    wavelet_matrix = util.cwt_utils.scale_for_reconstruction(wavelet_matrix.getdata(), dj, s0)

    print 'aevbaoivaobdeiv'
    print np.shape(wavelet_matrix)

    # wavelet_matrix = wavelet_matrix.getdata()

    scales = np.transpose(wavelet_matrix)
    print np.shape(scales)

    (m, n) = np.shape(scales)
    assert len(std_scaling_factors) == n, 'need one std scaling factor for each of %s wavelet scales' % (n)

    means = np.mean(scales, axis=0)

    stds = np.std(scales, axis=0)
    stds = np.maximum(stds, 0.0000001)  ## floor to avoid div by 0 problems

    norm_scales = (scales - means) / stds
    print np.shape(norm_scales)
    print np.mean(norm_scales, axis=0)
    print np.std(norm_scales, axis=0)

    #    norm_scales *= np.array(std_scaling_factors)

    # sys.exit(np.shape(norm_scales))
    denormed = (norm_scales * stds) + means

    recon = np.sum(scales, axis=1)

    return recon[:len(sequence)]


'''
qfile = '/Users/owatts/repos/ossian_working/Ossian/train/sw/speakers/bible3/naive_SW6/questions_dur.hed.cont'
lfile = '/Users/owatts/repos/ossian_working/Ossian/train/sw/speakers/bible3/naive_SW6/lab_dur/19_062.lab_dur'
n = NNDurationModel('/afs/inf.ed.ac.uk/user/o/owatts/temp/sw6_bib3_DUR', qfile)

#data = numpy.ones((100,233)) * 1.0
##data = numpy.random.normal(0,0.1,(100,233))
p = n.generate(lfile)
print p
sys.exit('ntbsdbsb')
'''

'''
#     
#n = NN('/afs/inf.ed.ac.uk/user/o/owatts/temp/sw6_bib3_EMI')
qfile = '/Users/owatts/repos/ossian_working/Ossian/train/sw/speakers/bible3/naive_SW6/questions_dnn.hed.cont'
lfile = '/Users/owatts/repos/ossian_working/Ossian/train/sw/speakers/bible3/naive_SW6/dnn_lab/19_062.dnn_lab'
n = NNAcousticModel('/afs/inf.ed.ac.uk/user/o/owatts/temp/sw6_bib3_EMI', qfile)

#data = numpy.ones((100,233)) * 1.0
##data = numpy.random.normal(0,0.1,(100,233))
p = n.generate(lfile, vuv_thresh=0.5, fzero_scale=1.0)
'''

# qfile = '/Users/owatts/repos/ossian_working/Ossian/train/sw/speakers/bible3/naive_SW6/questions_dnn.hed.cont'
# lfile = '/afs/inf.ed.ac.uk/user/o/owatts/temp/gpu_gen/66_015.dnn_lab'
# owave = '/afs/inf.ed.ac.uk/user/o/owatts/temp/cpu_gen/66_015.wav'
# n = NNAcousticModel('/afs/inf.ed.ac.uk/user/o/owatts/temp/sw6_bib3_EMI', qfile)
# 
# #data = numpy.ones((100,233)) * 1.0
# ##data = numpy.random.normal(0,0.1,(100,233))
# p = n.generate(lfile, owave, vuv_thresh=0.5, fzero_scale=1.0)
# 


'''
qfile = '/Users/owatts/repos/ossian_working/Ossian/train/sw/speakers/bible3/naive_SW6/questions_dnn.hed.cont'
lfile = '/afs/inf.ed.ac.uk/user/o/owatts/temp/gpu_gen/66_015.dnn_lab_NORM_BIN'
owave = '/afs/inf.ed.ac.uk/user/o/owatts/temp/cpu_gen/66_015_FROM_NORMLAB.wav'
n = NNAcousticModel('/afs/inf.ed.ac.uk/user/o/owatts/temp/sw6_bib3_EMI', qfile)

#data = numpy.ones((100,233)) * 1.0
##data = numpy.random.normal(0,0.1,(100,233))
p = n.generate_from_norm_binary_lab(lfile, 233, owave, vuv_thresh=0.5, fzero_scale=1.0)
'''
'''
qfile = '/Users/owatts/repos/ossian_working/Ossian/train/sw/speakers/bible3/naive_SW6/questions_dnn.hed.cont'
lfile = '/afs/inf.ed.ac.uk/user/o/owatts/temp/gpu_gen/66_015.dnn_lab_BINONLY'
owave = '/afs/inf.ed.ac.uk/user/o/owatts/temp/cpu_gen/null.wav'
n = NNAcousticModel('/afs/inf.ed.ac.uk/user/o/owatts/temp/sw6_bib3_EMI', qfile)

#data = numpy.ones((100,233)) * 1.0
##data = numpy.random.normal(0,0.1,(100,233))
p = n.generate_from_norm_binary_lab(lfile, 233, owave, vuv_thresh=0.5, fzero_scale=1.0)

'''
