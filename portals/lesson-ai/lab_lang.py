# -*- coding: utf-8 -*-
"""Lesson AI — the tutor's language, as data.

Two things live here, and both are tables rather than branches:

DIRECTIVE   the 【語言】 block of the system prompt, per locale. It is not a translation of the
            interface: a translated label cannot change the language a model answers in, so the
            instruction to answer in X has to sit in the prompt itself.
WORDS       the handful of Chinese words the post-processing in lab_core.py substitutes back into
            the model's text (the run button, the Scratch de-branding, colour names). Left as
            Chinese they leak into English turns — the same fault as a hardcoded label.

The default is zh-Hant and its directive is byte-identical to the original inline paragraph, so a
caller that sends no locale gets exactly the prompt it got before this module existed.

    import lab_lang as LL
    LL.enter(body.get("locale"))      # None -> zh-Hant
    LL.directive()                    # the prompt block
    LL.words()["run"]                 # 「執行」 / 「运行」 / "Run"
"""
import re
import threading

DEFAULT = "zh-Hant"

_TL = threading.local()

# Browser and URL spellings, collapsed onto the three the product ships.
ALIAS = {
    "zh": "zh-Hant", "zh-hant": "zh-Hant", "zh-tw": "zh-Hant", "zh-hk": "zh-Hant", "zh-mo": "zh-Hant",
    "zh-hans": "zh-Hans", "zh-cn": "zh-Hans", "zh-sg": "zh-Hans", "zh-my": "zh-Hans",
    "en": "en", "en-us": "en", "en-gb": "en", "en-hk": "en", "en-au": "en", "en-ca": "en",
}


def norm(code):
    """Any spelling a client might send -> one of the three locales, or None if we don't ship it."""
    c = str(code or "").strip().lower().replace("_", "-")
    if not c:
        return None
    return ALIAS.get(c) or ALIAS.get(c.split("-")[0])


# --- the prompt block ---------------------------------------------------------------------------

DIRECTIVE = {
    # Byte-identical to the paragraph this module replaced: a caller that sends no locale must get
    # the same prompt as before.
    "zh-Hant": """【語言】繁體中文（香港用字），句子短；學生用廣東話口語，你可以用簡單口語回應。提到積木時用積木上的中文名稱（例如「重複無限次」「如果…那麼」「碰到顏色」「移動 10 點」），不要說積木碼。
不要說「Scratch」，說「積木編程」或「Wonder Lab」。說顏色用名稱（例如「紅色」），不要寫 #a20000 這類色碼（色碼只放在積木裏）。學生可能用平板：沒有【裝置】時說「滑鼠／手指」。""",

    # Conversion, not translation: same pedagogy, simplified orthography, Mandarin register. The
    # examples stay Cantonese on purpose — they demonstrate the intent/ops decisions, and rewriting
    # fifteen of them by hand would put the two locales out of sync the first time one is edited.
    "zh-Hans": """【語言】简体中文（普通话书面语），句子短；不要用粤语口语或香港用语。提到积木时用编辑器上的简体中文名称（例如「重复无限次」「如果…那么」「碰到颜色」「移动 10 点」），不要说积木代码。
下面的示范对话用粤语写成，只示范怎样判断 intent、怎样组装 ops，不要模仿它的用词；你的 say 和 question 必须用简体中文重写。
不要说「Scratch」，说「积木编程」或「Wonder Lab」。说颜色用名称（例如「红色」），不要写 #a20000 这类色码（色码只放在积木里）。学生可能用平板：没有【装置】时说「鼠标／手指」。""",

    "en": """【LANGUAGE】Write say and question in English: British spelling, Hong Kong school register, short sentences, second person. Never output opcodes.
The worked examples below are written in Cantonese. They show how to classify a turn and how to assemble ops; do not copy their wording. Your say and question must be in English.
Name blocks as they read in the editor — "when green flag clicked", "forever", "if … then", "move 10 steps", "touching color?". Do not say "Scratch"; say "block coding" or "Wonder Lab". Name colours ("red"), never #a20000: colour codes belong inside blocks only. A student may be on a tablet: with no 【裝置】 line, say "the mouse or your finger".""",
}


# --- the words post-processing substitutes back into the model's text ----------------------------

COLOURS = {
    "zh-Hant": {"black": "黑色", "white": "白色", "grey": "灰色", "red": "紅色", "orange": "橙色",
                "yellow": "黃色", "green": "綠色", "cyan": "青色", "blue": "藍色", "purple": "紫色",
                "pink": "粉紅色", "other": "這個顏色"},
    "zh-Hans": {"black": "黑色", "white": "白色", "grey": "灰色", "red": "红色", "orange": "橙色",
                "yellow": "黄色", "green": "绿色", "cyan": "青色", "blue": "蓝色", "purple": "紫色",
                "pink": "粉红色", "other": "这个颜色"},
    "en": {"black": "black", "white": "white", "grey": "grey", "red": "red", "orange": "orange",
           "yellow": "yellow", "green": "green", "cyan": "cyan", "blue": "blue", "purple": "purple",
           "pink": "pink", "other": "that colour"},
}

WORDS = {
    "zh-Hant": {"run": "「執行」", "runAlt": "『執行』", "blockCoding": "積木編程",
                "colourPhrase": r"(的|嘅)?顏色\s*[「『（(]?\s*(#[0-9a-fA-F]{6})(?![0-9a-fA-F])\s*[」』）)]?",
                "colourParenOpen": "（", "colourParenClose": "）", "colours": COLOURS["zh-Hant"]},
    "zh-Hans": {"run": "「运行」", "runAlt": "『运行』", "blockCoding": "积木编程",
                "colourPhrase": r"(的)?颜色\s*[「『（(]?\s*(#[0-9a-fA-F]{6})(?![0-9a-fA-F])\s*[」』）)]?",
                "colourParenOpen": "（", "colourParenClose": "）", "colours": COLOURS["zh-Hans"]},
    "en": {"run": ' "Run" ', "runAlt": "“Run”", "blockCoding": "block coding",
           # A zero-width group 1 so name_colours sees the same shape as in Chinese; the pattern ends at
           # the hex so the word after it keeps its space ("Touching red stops it").
           "colourPhrase": r"()colou?r\s+(#[0-9a-fA-F]{6})(?![0-9a-fA-F])",
           "colourParenOpen": "(", "colourParenClose": ")", "colours": COLOURS["en"],
           "spaceBeforeColour": True},
}


def enter(code):
    """Pin this thread's locale. Called once per turn, next to lab_core's own thread state."""
    _TL.locale = norm(code) or DEFAULT
    return _TL.locale


def current():
    return getattr(_TL, "locale", DEFAULT)


def directive(code=None):
    return DIRECTIVE[norm(code) or current()]


def words(code=None):
    return WORDS[norm(code) or current()]


def colour_phrase_rx(code=None):
    return re.compile(words(code)["colourPhrase"])
