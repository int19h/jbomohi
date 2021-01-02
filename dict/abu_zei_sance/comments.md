## 2021-01-01T18:21:22Z — ues (comment 3631)

zei takes precedence here

Unfortunately, this zei lujvo does not work as intended. zei will take the
word to its right and left, which is bu, and leave "a" on its own. The
fact that "abu" is written as one word does not change the fact that they
parse as two separate words. I suggest using "a'y zei sance", which would
have the desired effect.


## 2021-01-02T05:39:30Z — zozeizeizeizeifaho (comment 3633, in reply to 3631)

Re: zei takes precedence here

ues wrote:
> Unfortunately, this zei lujvo does not work as intended. zei will take
the
> word to its right and left, which is bu, and leave "a" on its own. The
> fact that "abu" is written as one word does not change the fact that
they
> parse as two separate words. I suggest using "a'y zei sance", which
would
> have the desired effect.

The BPFK grammar processes magic words left-to-right, in general. After
the {bu} is read, the string ".{a} {bu}" works like a single word for any
following magic words, so for example, a single {si} deletes it, another
{bu} creates a the logical word ".{a} {bu} {bu}", and, yes, adding "{zei}
{broda}" creates the logical word ".{a} {bu} {zei} {broda}".

See https://mw.lojban.org/papri/magic_words_in_Lojban#Examples for more.

jbovlaste uses the same grammar to classify words, so if the word wasn't
valid, it would have refused to add it.

