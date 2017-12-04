# encoding: utf-8

import pypinyin
from pypinyin import pinyin

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
        result = [item[0] for item in result]
        return result


if __name__ == '__main__':
    # Test
    p = PronunciationVocab()
    print(p.look_up(u"，。不错的‘"))
