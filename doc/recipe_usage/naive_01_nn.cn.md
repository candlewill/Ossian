# Chinese TTS Tutorial

This doc tells you how to training a Chinese TTS model based on the `naive_01_nn.cn.cfg` recipe.

## Requirement

* *pypinyin* would be required for Chinese G2P.

## Environment

* Machine: Deep-Learning-1
* workspace: /root/Ossian

## Command

```shell
# export
export OSSIAN=/root/Ossian
export OSSIAN_LANG=cn
export DATA_NAME=toy_cn_corpus
export RECIPE=naive_01_nn.cn

# Clear
rm -r $OSSIAN/train/$OSSIAN_LANG/speakers/$DATA_NAME/$RECIPE/  $OSSIAN/voices/$OSSIAN_LANG/$DATA_NAME/$RECIPE/

# Run Ossian
python ./scripts/train.py -s $DATA_NAME -l $OSSIAN_LANG $RECIPE -c

# Merlin Training
export THEANO_FLAGS=""; python ./tools/merlin/src/run_merlin.py $OSSIAN/train/$OSSIAN_LANG/speakers/$DATA_NAME/$RECIPE/processors/duration_predictor/config.cfg
export THEANO_FLAGS=""; python ./tools/merlin/src/run_merlin.py $OSSIAN/train/$OSSIAN_LANG/speakers/$DATA_NAME/$RECIPE/processors/acoustic_predictor/config.cfg

# Export Model
python ./scripts/util/store_merlin_model.py $OSSIAN/train/$OSSIAN_LANG/speakers/$DATA_NAME/$RECIPE/processors/duration_predictor/config.cfg $OSSIAN/voices/$OSSIAN_LANG/$DATA_NAME/$RECIPE/processors/duration_predictor
python ./scripts/util/store_merlin_model.py $OSSIAN/train/$OSSIAN_LANG/speakers/$DATA_NAME/$RECIPE/processors/acoustic_predictor/config.cfg $OSSIAN/voices/$OSSIAN_LANG/$DATA_NAME/$RECIPE/processors/acoustic_predictor

# Test
mkdir -p $OSSIAN/test/wav/
python ./scripts/speak.py -l $OSSIAN_LANG -s $DATA_NAME -o ./test/wav/${OSSIAN_LANG}_${DATA_NAME}_test.wav $RECIPE ./test/txt/test.txt
```

### Edit config file

Edit the config file as appropriate and use for training with Merlin. Its existing path (just for example) is: 

```shell
/root/Ossian/train//cn/speakers/king_cn_corpus/naive_01_nn.cn/processors/duration_predictor/config.cfg
/root/Ossian/train//cn/speakers/king_cn_corpus/naive_01_nn.cn/processors/acoustic_predictor/config.cfg
```

You would want to increase training_epochs to train real voices. You would also want to experiment with learning_rate, batch_size, hidden_layer_size, hidden_layer_type. 

Particularly, in my case, I changed the following values:

```python
# Duration config
batch_size       : 32
training_epochs  : 30

buffer_size: 100000

# Acoustic config
batch_size       : 32
training_epochs  : 30
```

### Synthesis Multiple Texts

```shell
ls ./test/txt/pre/ | head -10 | while read line; do python ./scripts/speak.py -l $OSSIAN_LANG -s $DATA_NAME -o ./test/wav/${line}.wav $RECIPE ./test/txt/pre/$line; done

ls ./test/txt/ext_0000*.txt | head -10 | while read line; do python ./scripts/speak.py -l $OSSIAN_LANG -s $DATA_NAME -o ${line}.wav $RECIPE $line; done
```
#### 导出模型需要用到的几个文件

```
tar zcvf acoustic_model.tar.gz train/cn/speakers/king_cn_corpus/naive_01_nn.cn/dnn_training_ACOUST/nnets_model/feed_forward_6_tanh.model train/cn/speakers/king_cn_corpus/naive_01_nn.cn/dnn_training_ACOUST/inter_module/norm_info__mgc_lf0_vuv_bap_187_MVN.dat train/cn/speakers/king_cn_corpus/naive_01_nn.cn/dnn_training_ACOUST/inter_module/label_norm_HTS_6125.dat
```

