## 2015-11-25T22:34:05Z — krtisfranks (comment 2622, on definition 68112)

Notes on the Notes

1) "Module" has approximately the same meaning as it does in Mathematica.

2) The requirement that the sumti that fills sei'au1 begin with {li} is an 
artifact of {mau'au} (which produces a mekso operand) and not really of 
this word. In a sense, this word takes (a series of) mekso expression(s) 
and applies them to the linguistic structure of the bridi at a semantic 
level.

3) This word is its own terminator and the terminator is mandatory. This is
rather odd in Lojban but I made this requirement for practical 
considerations. Firstly, I did not want to use up another cmavo for the 
terminator but it seemed advisable to me to have one, since the next sumti 
can be anything and its typing will not necessarily be enough to 
distinguish it. Second, realistically, this word will not be used to edit 
the semantics of a structure multiple times in a row (but if the utterer 
wishes to do so, this is still possible). Note that {pi'u} can reduce the 
usage of this word as well. Thirdly, since this word is so clunky, it is 
good to have multiple arguments within it, as defined, that way it need not
be used too often; however, this further motivates the need for a 
terminator.

4) The language used for levels of syntactic nesting used in the notes is 
rather metaphorical. I was unsure of how to be clear without being verbose.
In particular, "open selbri" are those which have not been terminated.

5) The afterthought (so long as the selbri is still open) capability is 
useful. But this does mean garden-pathing/reinterpretation can be required 
of the audience. Also, it complicates this word's usage (one has to be 
careful with the arguments supplied). Additionally, the utility of 
afterthought editing being supported further promotes the existence of a 
terminator for this word.

6) If {goi} is used on the sumti of sei'au2, then the referent updates with
every new occurrence of the selbri (technically, after the occurrence of 
the terbri) to which this word applies. Thus, this value is 
context-dependent if used later in the discourse. This property is useful 
for overriding one sei'au application for another or for referencing how 
long one application has to remain active. This value decreases strictly 
monotonically until it reaches 0, where it remains until the variable is 
redefined.

7) This word really defines a new terbri which is $newbroda_m$ = 
f($broda_m$) and replaces every occurrence of $broda_m$ in the possibly 
zmico-affected definition of the currently open selbri with $newbroda_m$ 
for the next $n$ uses of the terbri (after which time, the definition 
reverts to it previous (possibly zmico-affected) form). Any sumti which 
fills this slot fills in $newbroda_m$. In order to be clear: It is not 
'f(sumti)' that fills $broda_m$; it is 'sumti' which fills $newbroda_m $.

8) I was not sure that {zi'a'o} was the best way to manually revert 
(temporarily) to the possibly zmico-affected definition. However, since f 
may not have an inverse (and may not even be properly defined, depending on
how the influence of sei'au constructs overlap), it was best to define a 
specific safety-word for this meaning. If you squint hard enough, this 
choice even makes a lot of sense; on the other hand, it can be problematic 
if one actually wants an elliptical or empty function.

