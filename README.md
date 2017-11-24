# Ossian + DNN demo

Ossian is a collection of Python code for building text-to-speech (TTS) systems, with an emphasis on easing research into building TTS systems with minimal expert supervision. Work on it started with funding from the [EU FP7 Project Simple4All](http://simple4all.org), and this repository contains a version which is considerable more up-to-date than that previously available. In particular, the original version of the toolkit relied on [HTS](http://hts.sp.nitech.ac.jp/) to perform acoustic modelling. Although it is still possible to use HTS, it now supports the use of neural nets trained with the [Merlin toolkit](https://github.com/CSTR-Edinburgh/merlin) as duration and acoustic models.  All
comments and feedback about ways to improve it are very welcome.

Here is some Chinese document. 一些中文文档和总结可以发现于：[Chinese Ossian Doc](https://gist.github.com/candlewill/8141bbe9d6c4c6224be8d3b4c07723eb).

## Python dependencies

**Python 2.7** is required.

Use the ```pip``` package installer -- within a [Python ```virtualenv```](https://virtualenv.pypa.io/en/stable/) as necessary -- to get some necessary packages:

```
pip install numpy
pip install scipy
pip install configobj
pip install scikit-learn
pip install regex
pip install lxml
pip install argparse
```

We will use the Merlin toolkit to train neural networks, creating the following dependencies:

```
pip install bandmat 
pip install theano
pip install matplotlib
```

We will use `sox` to process speech data:

```
apt-get install sox
```

## Getting the tools


Clone the Ossian github repository as follows:

```
git clone https://github.com/candlewill/Ossian.git
```

This will create a directory called ```./Ossian```; 
the following discussion assumes that an environment
variable ```$OSSIAN``` is set to point to this directory.

### Install from scratch

Ossian relies on the [Hidden Markov Model Toolkit (HTK)](http://htk.eng.cam.ac.uk) and [HMM-based Speech Synthesis System (HTS)](http://hts.sp.nitech.ac.jp/)
for alignment and (optionally) acoustic modelling -- here are some notes on obtaining and compiling the necessary tools. 
To get a copy of the HTK source code it
is necessary to register on the [HTK website](http://htk.eng.cam.ac.uk/register.shtml) to obtain a 
username and password. It is here assumed that these have been obtained and the environment
variables ```$HTK_USERNAME``` and ```$HTK_PASSWORD``` point to them.


Running the following script will download and install the necessary tools (including Merlin):

```
./scripts/setup_tools.sh $HTK_USERNAME $HTK_PASSWORD
```

The script `./scripts/setup_tools.sh` will do the following things:

* clones down the Merlin repo to `$OSSIAN/tools/merlin`, and resets its head to `8aed278`
* cd into the `merlin/tools/WORLD/` folder, and build it, then copy `analysis` and `synth` into `$OSSIAN/tools/bin/`:
    ```shell
    cd $OSSIAN/tools/merlin/tools/WORLD/
    make -f makefile
    make -f makefile analysis
    make -f makefile synth
    mkdir -p $OSSIAN/tools/bin/
    cp $OSSIAN/tools/merlin/tools/WORLD/build/{analysis,synth} $OSSIAN/tools/bin/
    ```
* Download HTK, HDecode, HTS, and apply HTS patch. Build HTK, and install it to `$OSSIAN/tools/` folder.
* Download hts-engine, and install it to `$OSSIAN/tools/`
* Download SPTK, and install it to `$OSSIAN/tools/`
* The `g2p-r1668-r3` and `corenlp-python` packages would be installed if you changed the value of `SEQUITUR`, `STANFORD` from 0 to 1.

As all the tools are installed into `$OSSIAN/tools/` directory, the `$OSSIAN/tools/bin` directory would include all the binaries used by Ossian.


### Install from pre-built

If you have installed the above mentioned tools manually and don't want to install from scratch, you can make soft link to tell the Ossian where you have installed these tools.

```shell
# 1 Mannuly clone the merlin repo
# 2 Downlaod WORLD, HTK, HDecode, HTS, HTS-engine, SPTK, build and install.
# 3 Copy all of the binaries into one folder. E.g., bin.

# 3 Where is your merlin dir
export merlin_dir=/home/dl80/heyunchao/Programs/Ossian/tools/merlin
# 4 Where is the bin direcotry inculuding all the binaries
export bin_dir=/home/dl80/heyunchao/Programs/Ossian/tools/bin

# 5 Create soft link in your Ossian/tools direcotry
cd /home/dl80/heyunchao/Programs/MyOssian_Github/tools
ln -s $merlin_dir merlin
ln -s $bin_dir bin
```

We provide a pre-built binary collection here [Ossian_required_bin.tar](https://cnbj1.fds.api.xiaomi.com/tts/ExternalLink/Github/Ossian_required_bin.tar.gz). Download and move to the `$bin_dir` directory, if someone doesn't want to build for scratch. 

## Acquire some data

Ossian expects its training data to be in the directories:

```
 ./corpus/<OSSIAN_LANG>/speakers/<DATA_NAME>/txt/*.txt
 ./corpus/<OSSIAN_LANG>/speakers/<DATA_NAME>/wav/*.wav
```

Text and wave files should be numbered consistently with each other. ```<OSSIAN_LANG>``` and ```<DATA_NAME>``` are both arbitrary strings, but it is sensible to choose ones which make obvious sense. 

Download and unpack this toy (Romanian) corpus for some guidance:

```
cd $OSSIAN
wget https://www.dropbox.com/s/uaz1ue2dked8fan/romanian_toy_demo_corpus_for_ossian.tar?dl=0
tar xvf romanian_toy_demo_corpus_for_ossian.tar\?dl\=0
```

This will create the following directory structures:

```
./corpus/rm/speakers/rss_toy_demo/
./corpus/rm/text_corpora/wikipedia_10K_words/
```

Let's start by building some voices on this tiny dataset. The results will sound bad, but if you can get it to speak, no matter how badly, the tools are working and you can retrain on more data of your own choosing. Below are instructions on how to train HTS-based and neural network based voices on this data. 

You can download 1 hour sets of data in various languages we prepared here: http://tundra.simple4all.org/ssw8data.html

## DNN-based voice using a naive recipe

Ossian trains voices according to a given 'recipe' -- the recipe specifies a sequence of processes which are applied to an utterance to turn it from text into speech, and is given in a file called ```$OSSIAN/recipes/<RECIPE>.cfg``` (where ```<RECIPE>``` is the name of a the specific recipe you are using). We will start with a recipe called ```naive_01_nn```. If you want to add components to the synthesiser, the best way to start will be to take the file for an existing recipe, copy it to a file with a new name and modify it.

The recipe ```naive_01_nn``` is a language independent recipe which naively uses letters as acoustic modelling units. It will work reasonably for languages with sensible orthographies (e.g. Romanian) and less well for e.g. English.

Ossian will put all files generated during training on the data ```<DATA_NAME>``` in language ```<OSSIAN_LANG>``` according to recipe ```<RECIPE>``` in a directory called:

```
 $OSSIAN/train/<OSSIAN_LANG>/speakers/<DATA_NAME>/<RECIPE>/
```

When if has successfully trained a voice, the components needed at synthesis are copied to:

```
 $OSSIAN/voices/<OSSIAN_LANG>/<DATA_NAME>/<RECIPE>/
```

Assuming that we want to start by training a voice from scratch, we might want to check that these locations do not already exist for our combination of data/language/recipe:

```
rm -r $OSSIAN/train/rm/speakers/rss_toy_demo/naive_01_nn/ $OSSIAN/voices/rm/rss_toy_demo/naive_01_nn/
```

Then to train, do this:

```
cd $OSSIAN
python ./scripts/train.py -s rss_toy_demo -l rm naive_01_nn
```

As various messages printed during training will inform you, training of the neural networks themselves which will be used for duration and acoustic modelling is not directly supported within Ossian. The data and configs needed to train networks for duration and acoustic model are prepared by the above command line, but the Merlin toolkit needs to be called separately to actually train the models. The NNs it produces then need to be converted back to a suitable format for Ossian. This is a little messy, but better integration between Ossian and Merlin is an ongoing area of development. 

Here's how to do this -- these same instructions will have been printed when you called ```./scripts/train.py``` above. First, train the duration model:

```
cd $OSSIAN
export THEANO_FLAGS=""; python ./tools/merlin/src/run_merlin.py $OSSIAN/train/rm/speakers/rss_toy_demo/naive_01_nn/processors/duration_predictor/config.cfg
```

For this toy data, training on CPU like this will be quick. Alternatively, to use GPU for training, do:

```
./scripts/util/submit.sh ./tools/merlin/src/run_merlin.py $OSSIAN/train/rm/speakers/rss_toy_demo/naive_01_nn/processors/duration_predictor/config.cfg
```

If training went OK, then you can export the trained model to a better format for Ossian. The basic problem is that the NN-TTS tools store the model as a Python pickle file -- if this is made on a GPU machine, it can only be used on a GPU machine. This script converts to a more flexible format understood by Ossian -- call it with the same config file you used for training and the name of a directory when the new format should be put:

```
python ./scripts/util/store_merlin_model.py $OSSIAN/train/rm/speakers/rss_toy_demo/naive_01_nn/processors/duration_predictor/config.cfg $OSSIAN/voices/rm/rss_toy_demo/naive_01_nn/processors/duration_predictor
```

When training the duration model, there will be loads of warnings saying ```WARNING: no silence found!``` --  theses are not a problem and can be ignored.

Similarly for the acoustic model:

```
cd $OSSIAN
export THEANO_FLAGS=""; python ./tools/merlin/src/run_merlin.py $OSSIAN/train/rm/speakers/rss_toy_demo/naive_01_nn/processors/acoustic_predictor/config.cfg
```

Or:

```
./scripts/util/submit.sh ./tools/merlin/src/run_merlin.py $OSSIAN/train/rm/speakers/rss_toy_demo/naive_01_nn/processors/acoustic_predictor/config.cfg
```

Then:

```
python ./scripts/util/store_merlin_model.py $OSSIAN/train/rm/speakers/rss_toy_demo/naive_01_nn/processors/acoustic_predictor/config.cfg $OSSIAN/voices/rm/rss_toy_demo/naive_01_nn/processors/acoustic_predictor
```



If training went OK, you can synthesise speech. There is an example Romanian sentence in ```$OSSIAN/test/txt/romanian.txt``` -- we will synthesise a wave file for it in ```$OSSIAN/test/wav/romanian_toy_naive.wav``` like this:

```
mkdir $OSSIAN/test/wav/

python ./scripts/speak.py -l rm -s rss_toy_demo -o ./test/wav/romanian_toy_HTS.wav naive_01_nn ./test/txt/romanian.txt
```

You can find the audio for this sentence [here](https://www.dropbox.com/s/xm9d7j7125y6j13/romanian_test_sentence_reference.wav?dl=0) for comparison (it was not used in training).

The configuration files used for duration and acoustic model training will work as-is for the toy data set, but when you move to other data sets, you will want to experiment with editing them to get better permformance.
In particular, you will want to increase training_epochs to train voices on larger amounts of data; this could be set to e.g. 30 for the acoustic model and e.g. 100 for the duration model.
You will also want to experiment with learning_rate, batch_size, and network architecture (hidden_layer_size, hidden_layer_type). Currently, Ossian only supports feed-forward networks.


## Other recipes

We have used many other recipes with Ossian which will be documented here when cleaned up enough to be useful to others. These will give the ability to add more  knowledge to the voices built, in the form of lexicons, letter-to-sound rules etc., and integrate existing trained components where they are available for the target language.