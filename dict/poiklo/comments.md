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

