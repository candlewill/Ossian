# encoding: utf-8

import pypinyin
from pypinyin import pinyin
from naive.naive_util import safetext

'''
Author: Yunchao He
heyunchao@xiaomi.com

2017.12.1

'''

"""
发音词典类

加载发音词典，输入一个单词，可以返回这个单词对应发音方式

对于多音字，则返回其最常用发音
"""


class PronunciationVocab(object):
    def look_up(self, word):
        result = pinyin(word, style=pypinyin.TONE3)
        result = [self.word_2_safetext(item[0]) for item in result]
        return result

    def word_2_safetext(self, word):
        if any(c not in "qwertyuiopasdfghjklmnbvcxz123456" for c in word):
            return safetext(word)
        name_reps = {
            "1": "ONE",
            "2": "TWO",
            "3": "THREE",
            "4": "FOUR",
            "5": "FIVE",
            "6": "SIX"}
        for key in name_reps.keys():
            word = word.replace(key, name_reps[key])
        return word


if __name__ == '__main__':
    # Test
    p = PronunciationVocab()
    print(p.look_up(u"，。不错的，我们都是中国人‘"))
