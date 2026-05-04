"""中文政策文本关键词 / 词频统计（jieba），供图谱方向解析与政策预测等模块复用。"""
from __future__ import annotations

import re
from collections import Counter
from typing import Any

import jieba.analyse
import jieba.posseg as pseg

from runtime_paths import data_path

_ATT_FLAGS = ("a", "ad", "ag", "an", "b", "z")
_NOUN_FLAGS = ("n",)


def load_prepositions() -> set[str]:
    stopword_file = data_path("STOPWORDS_PATH", "介词库.txt")
    words: set[str] = set()
    if stopword_file.exists():
        text = stopword_file.read_text(encoding="utf-8", errors="ignore")
        for token in re.findall(r"[\u4e00-\u9fffA-Za-z]+", text):
            t = token.strip().lower()
            if t:
                words.add(t)
    words.update({"以及", "或者", "一个", "一种", "相关", "进行"})
    return words


_PREPS = load_prepositions()


def is_valid_token(word: str) -> bool:
    if not word or len(word) < 2:
        return False
    if re.fullmatch(r"[\W_]+", word):
        return False
    if re.fullmatch(r"\d+", word):
        return False
    return True


def _pack(counter: Counter, topn: int) -> list[dict[str, Any]]:
    return [{"word": word, "count": count} for word, count in counter.most_common(topn)]


def analyze_policy_text(text: str) -> dict[str, Any]:
    """与 Neo4jService.get_policy_direction_analysis 返回结构一致。"""
    text = (text or "").strip()
    if not text:
        return {
            "keywords": [],
            "wordFrequency": [],
            "attributiveFrequency": [],
            "nounFrequency": [],
            "fourCharFrequency": [],
            "wordCloud": [],
        }

    keyword_rows = jieba.analyse.extract_tags(text, topK=20, withWeight=True)
    keywords = [{"word": str(word), "score": round(float(score), 4)} for word, score in keyword_rows if str(word).strip()]

    all_counter: Counter[str] = Counter()
    attributive_counter: Counter[str] = Counter()
    noun_counter: Counter[str] = Counter()
    four_char_counter: Counter[str] = Counter()

    for token in pseg.cut(text):
        word = str(token.word or "").strip()
        flag = str(token.flag or "").strip()
        lowered = word.lower()
        if lowered in _PREPS or not is_valid_token(word):
            continue
        all_counter[word] += 1
        if len(word) == 4:
            four_char_counter[word] += 1
        if flag.startswith(_ATT_FLAGS):
            attributive_counter[word] += 1
        if flag.startswith(_NOUN_FLAGS):
            noun_counter[word] += 1

    return {
        "keywords": keywords,
        "wordFrequency": _pack(all_counter, 30),
        "attributiveFrequency": _pack(attributive_counter, 30),
        "nounFrequency": _pack(noun_counter, 30),
        "fourCharFrequency": _pack(four_char_counter, 30),
        "wordCloud": _pack(all_counter, 5),
    }


def analyze_study_100(text: str) -> dict[str, Any]:
    """政策预测静态页 / 采集解析：四类各 25 个，共约 100 个关键词展示用。"""
    text = (text or "").strip()
    empty = {
        "fourCharFrequency": [],
        "nounFrequency": [],
        "attributiveFrequency": [],
        "generalFrequency": [],
        "keywords100": [],
        "tfidfKeywords": [],
        "freqAll": {},
    }
    if not text:
        return empty

    keyword_rows = jieba.analyse.extract_tags(text, topK=20, withWeight=True)
    tfidf_keywords = [{"word": str(word), "score": round(float(score), 4)} for word, score in keyword_rows if str(word).strip()]

    all_counter: Counter[str] = Counter()
    attributive_counter: Counter[str] = Counter()
    noun_counter: Counter[str] = Counter()
    four_char_counter: Counter[str] = Counter()

    for token in pseg.cut(text):
        word = str(token.word or "").strip()
        flag = str(token.flag or "").strip()
        lowered = word.lower()
        if lowered in _PREPS or not is_valid_token(word):
            continue
        all_counter[word] += 1
        if len(word) == 4:
            four_char_counter[word] += 1
        if flag.startswith(_ATT_FLAGS):
            attributive_counter[word] += 1
        if flag.startswith(_NOUN_FLAGS):
            noun_counter[word] += 1

    four = _pack(four_char_counter, 25)
    noun = _pack(noun_counter, 25)
    attr = _pack(attributive_counter, 25)
    seen = {x["word"] for x in four + noun + attr}
    gen: list[dict[str, Any]] = []
    for word, count in all_counter.most_common():
        if word in seen:
            continue
        gen.append({"word": word, "count": count})
        if len(gen) >= 25:
            break

    keywords100 = [x["word"] for x in four + noun + attr + gen]
    freq_all = dict(all_counter)
    return {
        "fourCharFrequency": four,
        "nounFrequency": noun,
        "attributiveFrequency": attr,
        "generalFrequency": gen,
        "keywords100": keywords100,
        "tfidfKeywords": tfidf_keywords,
        "freqAll": freq_all,
    }


def vocab_from_study(study: dict[str, Any]) -> set[str]:
    s: set[str] = set()
    for key in ("fourCharFrequency", "nounFrequency", "attributiveFrequency", "generalFrequency"):
        for item in study.get(key) or []:
            if item.get("word"):
                s.add(str(item["word"]))
    for item in study.get("tfidfKeywords") or []:
        if item.get("word"):
            s.add(str(item["word"]))
    return s


def overlap_bucket(corpus_bucket: list[dict], ref_bucket: list[dict], limit: int = 10) -> list[dict[str, Any]]:
    ref_words = {x["word"] for x in ref_bucket}
    out: list[dict[str, Any]] = []
    for x in corpus_bucket:
        if x["word"] in ref_words:
            out.append(dict(x))
        if len(out) >= limit:
            break
    return out
