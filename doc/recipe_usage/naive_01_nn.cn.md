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
# Export Merlin duration model
export THEANO_FLAGS=""; python ./tools/merlin/src/run_merlin.py $OSSIAN/train/$OSSIAN_LANG/speakers/$DATA_NAME/$RECIPE/processors/acoustic_predictor/config.cfg

# Export Model
python ./scripts/util/store_merlin_model.py $OSSIAN/train/$OSSIAN_LANG/speakers/$DATA_NAME/$RECIPE/processors/duration_predictor/config.cfg $OSSIAN/voices/$OSSIAN_LANG/$DATA_NAME/$RECIPE/processors/duration_predictor
python ./scripts/util/store_merlin_model.py $OSSIAN/train/$OSSIAN_LANG/speakers/$DATA_NAME/$RECIPE/processors/acoustic_predictor/config.cfg $OSSIAN/voices/$OSSIAN_LANG/$DATA_NAME/$RECIPE/processors/acoustic_predictor

# Test
mkdir -p $OSSIAN/test/wav/
python ./scripts/speak.py -l $OSSIAN_LANG -s $DATA_NAME -o ./test/wav/${OSSIAN_LANG}_${DATA_NAME}_test.wav $RECIPE ./test/txt/test.txt
```

