## 2016-12-26T07:01:18Z — krtisfranks (comment 3119, on definition 66414)

Elliptical operand

In mekso, there are times when an operand is not mentioned explicitly. When
this is anything other than a numeral string or a number derived therefrom 
(basically, just (2^n)-nions; mostly, just real numbers) - for example, a 
matrix, a function, a set, etc. - use of {xo'ei} is insufficient. Would 
this word (or certain generalizations thereof) work for this purpose (being
an elliptical mekso argument) when mekso is activated (such as in the case 
of it following immediately after {li})? I tentatively believe so, but 
there may be complications to the way that Lojban handles lerfu which I 
have not previously considered (such as an analog to the difference between
PA and numbers).


## 2016-12-26T07:27:40Z — krtisfranks (comment 3120, on definition 66414, in reply to 3119)

Re: Elliptical operand

krtisfranks wrote:
> there may be complications to the way that Lojban handles lerfu which I 
> have not previously considered (such as an analog to the difference 
between
> PA and numbers).


One such complication is the fact that concatenation with any immediately 
previous lerfu string which is unconverted will occur automatically, 
according to my current mental model of the language and how this word 
should work (which is derived by analogy from the same model for {xo'e} and
{xo'ei} which I have constructed). I do not see this as too much of a 
problem though because: On its own, this word would just potentially refer 
to any context-allowed lerfu (producing a 1-string which then is 
interpreted as referring to something, namely an operand, much as {xo'e} 
produces a numerical 1-string which is then understood as a (Lojbanically 
single-digit) number). But if there is an open letteral immediately 
preceding it, then it just concatenates into that, thereby forming an 
(n+1+m)-string which will then be interpreted to have a single referent 
(so, still an operand, in this intended context); in this way, the 
elliptical letteral is just 'modified' in its effect so that the pool of 
referants of the whole string is restricted to the possibilities such that 
the potential referents are named by strings of length n+1+m with the first
n and the final m letters matching the explicit ones specified by the 
resulting string (much as "ci pa xo'e" produces, after interpretation, a 
single number which belongs to a pool of potential referents such that all 
of them are three digits long in the base, the first two digits are "3" and
"1" in that order, and the last digit has free variation bounded only by 
context and the restrictions of the first two digits (so, if "317" is not 
an option for some reason, then the number cannot be called such)).

A potentially bigger complication is the fact that operators and all sorts 
of other things (even in the context of mekso) can be labelled by letters 
or can have lerfu strings refer to them. For example, a function f is of 
the first kind, but su'i (addition) may be referrenced by the lerfu string 
sy ("s") and thus sy/s in combination with su'i is of the second kind. This
can potentially cause unintended consequences, confusion, incorrectness, or
could incur a typing error. I do not think that this is resolved by the 
fact that ellipticals mean what the speaker wants (or, really, what the 
audience thinks that they want) them to mean. I think that it would be a 
fundamental flaw in the grammar simply because the elliptical lerfu could 
mean, say, another operator instead. In that case, there would be nesting 
an the second (potential) operator (the one referenced by the elliptical 
lerfu) would have implicit elliptical operands. The functionality of 
possibly referring to an operator or, indeed, anything which may be 
labelled in mekso, is necessary/useful and guaranteed by the grammar thus 
far, so we cannot avoid it here by artificially imposed restrictions 
(admittedly, operators usually have some sort of modifier which makes them 
clearly operators, but that is not sufficient help, I believe). Thus, I 
think that this is a deal-breaker. We need another word for elliptical 
operands, and a separate one for elliptical operators.

