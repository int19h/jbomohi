## 2014-12-07T01:55:53Z — krtisfranks (comment 1469, on definition 63897)

Offset?

Subsequences just have an extra index/map (internally composed). I do not
understand this definition.


## 2014-12-07T12:26:48Z — Ilmen (comment 1470, on definition 63897, in reply to 1469)

Re: Offset?

krtisfranks wrote:
> Subsequences just have an extra index/map (internally composed). I do
not
> understand this definition.

coi la .krtisfranks.

Actually I didn't know that "subsequence" was a technical term different
in meaning from "substring"; what I intended to mean was "substring". I
will correct the definition accordingly.

Making lujvo for technical terms is not always easy, as the place
structure is somewhat constrained.

What do you think of the following definition for {poiklo}:
«x1 (sequence/string) has an occurrence at position/offset x2 (number) in
sequence/string x3»

Examples: «zo ti poiklo li vo (lo lerpoi pe) lu mi ti do dunda li'u»,
«zo ti poiklo ci da (lo lerpoi pe) lu ti titranti li'u»
(I'm not quite sure whether quotes can be treated directly as phoneme
sequences, but this seems sensible enough.)

mi'e la .ilmen. mu'o


## 2014-12-07T14:53:07Z — Wuzzy (comment 1471, on definition 63897, in reply to 1470)

Re: Offset?

> Examples: «zo ti poiklo li vo (lo lerpoi pe) lu mi ti do dunda li'u»,
> «zo ti poiklo ci da (lo lerpoi pe) lu ti titranti li'u»
> (I'm not quite sure whether quotes can be treated directly as phoneme
> sequences, but this seems sensible enough.)


A string is an arbitrary sequence of characters (see {lerpoi}). The
closest equivalent in Lojban for this are zoi-quotes, not lu-quotes.
Your “lu” seems a bit contrived, since spacing in Lojban is a bit
liberal. Thus, “lu mi ti do dunda li'u” is (and should be) treated as
identical to “lu mitido dunda li'u”. Unless you invent a rule to count
positions in “lu” strings, I suggest to avoid “lu” and “lo'u”
quotes as sumti for poiklo.

I think that poiklo is most useful with zoi-quotes.

I guess a more practical example would be something like this:
“zoi gy.http.gy. poiklo li pa zoi gy.http://jbovlaste.lojban.org/.gy.”
→ “‘http’ is a substring at position 1 of the string
‘http://jbovlaste.lojban.org/’.”

Oh, and that counting begins by 0 is not at all a “standard” in
programming languages. There are a couple of languages where counting
starts by 1. I have removed that part of the sentence from the notes.


## 2014-12-07T22:20:11Z — Ilmen (comment 1475, on definition 63897, in reply to 1471)

Re: Offset?

Wuzzy wrote:
> A string is an arbitrary sequence of characters (see {lerpoi}). The
> closest equivalent in Lojban for this are zoi-quotes, not lu-quotes.
> Your “lu” seems a bit contrived, since spacing in Lojban is a bit
> liberal. Thus, “lu mi ti do dunda li'u” is (and should be) treated
as
> identical to “lu mitido dunda li'u”. Unless you invent a rule to
count
> positions in “lu” strings, I suggest to avoid “lu” and
“lo'u”
> quotes as sumti for poiklo.
> 
> I think that poiklo is most useful with zoi-quotes.

I think lu-quotes are either lerpoi (phoneme sequences), or vlapoi (word
sequences). If they are lerpoi, there needs to be a default spacing,
probably either fully-spaced Lojban or spaceless Lojban, so that «lu mi
ti dunda do li'u» is considered as identical to «lumitidúndadoli'u».
If the default is spaceless Lojban, then no matter how many space do you
put in the lu-quote, the resulting lerpoi would contain spaceless Lojban.
If lu-quotes are vlapoi, there's no spacing issue though, because each
word is in a different slot in the sequence.


## 2014-12-09T06:57:10Z — krtisfranks (comment 1478, on definition 63897, in reply to 1471)

Re: Offset?

Wuzzy wrote:
> > Examples: «zo ti poiklo li vo (lo lerpoi pe) lu mi ti do dunda
li'u»,
> > «zo ti poiklo ci da (lo lerpoi pe) lu ti titranti li'u»
> > (I'm not quite sure whether quotes can be treated directly as phoneme
> > sequences, but this seems sensible enough.)
> 
> 
> A string is an arbitrary sequence of characters (see {lerpoi}). The
> closest equivalent in Lojban for this are zoi-quotes, not lu-quotes.
> Your “lu” seems a bit contrived, since spacing in Lojban is a bit
> liberal. Thus, “lu mi ti do dunda li'u” is (and should be) treated
as
> identical to “lu mitido dunda li'u”. Unless you invent a rule to
count
> positions in “lu” strings, I suggest to avoid “lu” and
“lo'u”
> quotes as sumti for poiklo.
> 
> I think that poiklo is most useful with zoi-quotes.
> 
> I guess a more practical example would be something like this:
> “zoi gy.http.gy. poiklo li pa zoi
gy.http://jbovlaste.lojban.org/.gy.”
> → “‘http’ is a substring at position 1 of the string
> ‘http://jbovlaste.lojban.org/’.”
> 
> Oh, and that counting begins by 0 is not at all a “standard” in
> programming languages. There are a couple of languages where counting
> starts by 1. I have removed that part of the sentence from the notes.

I have made a proposal to la gleki about something quite closely related.
I decided that spaces do count between brivla because they must be encoded
somehow (alternatives include marking vowels or syllables in some way):
they convey indestructible information in that context. In that case,
strings have an extra "hidden letter", where I interpret each letter to be
a unit of conveyed information (meaningful in context). The information is
what is being counted, actually, not symbols or phonemes. I also start
counting from 1 in Lojban, but we should really formalize and systematize
it as a community after much debate. I usually specify at least the first
element in my definitions and also try to allude to the ordering. I will
try to find the message and post its content somewhere.
This has combinatorial uses, btw!

I much prefer the current definition and do not have any immediately
obvious concerns.

