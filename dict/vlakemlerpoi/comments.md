## 2014-01-13T07:23:51Z — krtisfranks (comment 867, on definition 44227)

Mathematics

Would you recommend using this word for mathematics (where one spells
words over some alphabet of, say, group elements, yielding a quantity
(which is called the word))?


## 2014-01-13T08:25:54Z — filipos (comment 868, on definition 44227, in reply to 867)

Re: Mathematics

krtisfranks wrote:
> Would you recommend using this word for mathematics (where one spells
> words over some alphabet of, say, group elements, yielding a quantity
> (which is called the word))?

How do you consider using {valsi} in a mathematical context?

I would use plain {lerpoi} (the definition I entered, by tsani), with
lerpoi1 being the sequence of generators and lerpoi3 being their value.

{ci'e la'o gy.Klein four-group.gy.
me'o .abu cmarai lo lerpoi be fi li by. .abu by.}


I guess you could alternatively use {valsi} (or a lujvo based on it) as

"x1 is a sequence of generators with value x2 in group presentation x3",

with valsi2 being the mathematical word.

{me'o .abu cmarai lo valsi be li by. .abu by.
bei la'o gy.Klein four-group.gy.}


## 2014-01-13T09:12:50Z — Wuzzy (comment 871, on definition 44227, in reply to 868)

Re: Mathematics

filipos wrote:
> I would use plain {lerpoi} (the definition I entered, by tsani), with
> lerpoi1 being the sequence of generators and lerpoi3 being their value.
> 
> I guess you could alternatively use {valsi} (or a lujvo based on it) as
> 
> "x1 is a sequence of generators with value x2 in group presentation x3",
No, no, no, NO!
That’s WAY too far off from the original definitions.
Those definitions certainly would need new words.


## 2014-01-13T22:35:00Z — filipos (comment 876, on definition 44227, in reply to 871)

Re: Mathematics

Wuzzy wrote:
> filipos wrote:
> > I guess you could alternatively use {valsi} (or a lujvo based on it)
as
> > 
> > "x1 is a sequence of generators with value x2 in group presentation
x3",
> No, no, no, NO!
> That’s WAY too far off from the original definitions.
> Those definitions certainly would need new words.

Ok, this is more for fun than for the original point, but here is a PEG
for the Klein group

I <- e I | a A | b B | c C | eps
A <- e A | a I | b C | c B
B <- e B | a C | b I | c A
C <- e C | a B | b A | c I

More trivially, it is straightforward to define an attribute grammar for
computing the product of a sequence of elements.

So, we do have words (the sequences), interpretations for these words (the
values) and rules for how to determine the meaning of a composition of
them from its parts (the group operation).

