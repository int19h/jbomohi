## 2017-03-31T21:45:23Z — krtisfranks (comment 3183, on definition 1697)

Issue

This word does not mean just i, unlike what the current definition in most 
languages says here.

Zeroth, the CLL description gives it two properties: "?ka'o? is both a 
special number (meaning ?i?) and a number punctuation mark (separating the 
real and the imaginary parts of a complex number).".
So, if we are going by official documentation, both properties should be 
mentioned in the definitions here.

But I have two problems even with that:

First, this is at best overloading and at worst math-breaking. It is fine 
that it can act as a digit, but it cannot function as both a separator and 
as a representation of the unit i, which is a number unto itself. Either 
this is short-hand for "___ + ___i" (sorta as "{gei}" is short-hand for 
"___*(___^___)", roughly, and denoted usually as "___E___"; the analogy 
breaks because they are of different selma'o), or it means simply "i"; it 
cannot be both.

Just as importantly, in some base representations (confer quater-imaginary 
and then generalize a bit), the differences between a pure digit "i" which 
means i (and which would use up one digit slot in a string) and the 
'punctuation mark' meaning described by the CLL are incompatible and would 
cause breakage and confusion/syntactic and semantic ambiguities. Here is a 
simple example: Suppose that we expand traditional unbalanced decimal 
notation so that "i" is now a digit which works like any other? (such as 
"3"); then the string "1i2" ("pa ka'o re") means 1*10^2 + i*10^1 + 2*10^0 =
102 + 10i, which is distinct from the 'punctuation mark' interpretation 
which would result in the meaning 1 + 2i; even more strangely, "1ii2" ("pa 
ka'o ka'o re") would be allowed, meaning 1002 + 110i, but it is not at all 
clear that this would be even meaningful in the 'punctuation mark' 
interpretation (regardless of considerations about its actual meaning).

Second, I am not even sure that these two interpretations are grammatically
compatible. The first treats "ka'o" like "ci" (they both are PA); the 
second treats it something like "su'u" (basically, it is a VUhU 
masquerading as a PA; see previous discussion about "gei"). Now, it is up 
for debate, but some standards of Lojban may assume implicit "xo'ei"'s when
VUhU slots are left open. If this is the case, then "ka'o" alone cannot 
generally mean just i = 0 + 1i; it must mean x + yi, and this x can easily 
be nonzero and the y can easily be non-one. So, in such standards, the two 
interpretations conflict unresolvably. Moreover, we have already hit on two
other grammatical problems here. The first is that this word, according to 
the CLL, is essentially a fusion of PA and VUhU, which are disjoint 
selma'o, which means that such a blurring is prohibited for the sake of 
syntactic disambiguity. The second is the case before of "1ii2" being 
grammatically allowed but essentially (gramamtically, not just 
semantically!) uninterpretable according to the current description. The 
first part must be the real part and the second part must be the imaginary 
part. Not only are these implied to be restricted to (extended) real 
domains, but now there are multiple real parts and multiple imaginary 
parts, and multiple reading orders of these. What would "1i2i3" mean? How 
can that even be interpreted according to the rules, grammatically?  Does 
the first "i" or the second "i" come first? In the former case, how can it 
be that "1i2" the real part of the second one?

___

My solution:

We introduce a new word which is really a digit meaning "i" of selma'o PA. 
It works just like "ci". On its own (not in a nontrivial string of digits) 
it means i. If it is in a nontrivial string of digits, then it is 
interpreted according to the representational base. So, just as "20" can 
mean many things (consider the bases: decimal, hexadecimal, phinary, 
quaterimaginary, balanced ternary, and even binary (where it is improper)),
"2i" can mean many things, each dependent on the base of interpretation 
(specified by "ju'u"; the meaning comes from the base-interpretation step 
in the Order of Interpretation). It is rather unlikely, in any event, that 
"2i" means 2*i, though. Just as "21" does not mean 2*1 = 2 in most bases, 
"2i" will not mean 2*i in most bases. With such a word, the multiplication 
operator must be explicitly used between the two single-digit numbers 2 and
the unit i (which is, again, represented by the digit "i" on its own) in 
order to mean 2*i. There would be no "slot" on either side of "i" in this 
scenario; a string of digits could of course be multiple digits long (such 
as "1i2i3ii4i"), but there would be no inherent structure to the digit "i" 
(which would implicitly be filled by "xo'ei"'s in some Lojban systems). 
Complicated strings, such as the one just mentioned, would be interpreted 
according to the base. For this specific purpose, I propose "{ka'o'ai}". 
This word is exactly like "ci" but means i instead of 3.

Meanwhile, I simultaneously propose that we 
redefine/clarify/restructure/reduce the meaning of "{ka'o}" so that it 
joins selma'o VUhU (only) and that it is a binary mekso operator (like 
"{gei}", but binary) which means exactly "X1 + (X2*i)" such that X1 and X2 
(the first and second argument respectively) are (as a contextless default)
typically understood/restricted to be (strictly) real numbers (and this is 
their meaning when this is used in a veljvo unless explicitly 
contradicted). Thus, its arguments are not even necessarily a real numbers 
(but if both are, then the first is the real part of the result and the 
second is the imaginary part of the result). It could be denoted by "(X1, 
X2)" in C. Thus, it would follow whatsoever is the reading/priority order 
applied to mekso operators according to the culture and the utterances 
prior to its use. It would then have slots to be filled and would thus, 
according to some systems of Lojban, take on implicit "xo'ei"'s whensoever 
those were not explicitly filled. In some ways, this would be a macro for 
an expression involving "su'u", "pi'i", and a lone "ka'o'ai" (as described 
in the immediately previous paragraph), and nothing else (except operator 
prioritizers).  For example, "pa ka'o re ka'o ka'o ci" could mean (if we 
just read left-to-right/first-to-last for priority) (((1,2), x), 3) = (((1 
+ 2i) + x*i) + 3i) = 1 + (5+x)i, where x is represented by an implicit 
"xo'ei" and could mean any (probably complex, perhaps real, possibly 
nonzero) number. Other reading orders would produce different (perhaps more
exotic) results.

In my personal usages, I use these words to mean exactly these things (and 
I believe that implicit "xo'ei"'s are beneficial and maximize exotic 
utility, such as in my aforementioned examples).  Thus, in my "zei"-lujvo 
involving "ka'o", I mean the operator with implicit "xo'ei"'s as zero or 
more of its operands (even in the veljvo of these constructs).

Note, by the way, that if we ignore my proposals, then "ka'o" can be 
interpreted basically as my "ka'o'ai" would be. In this case, "{ka'o zei 
namcu}" would mean "x1 is a strictly imaginary number (including 0), not 
necessarily understood as a complex number as well". To me, this is the 
definition of "{ka'o'ai zei namcu}". Notice its similarity with the meaning
of "real number" which you knew prior to being introduced to the imaginary 
unit and complex numbers - a consideration of R which does not account for 
C. To me, "ka'o zei namcu" means and can mean only "x1 is a complex number"
(where the real and imaginary parts (really, the first and second operands 
of "ka'o") are implicit "xo'ei"'s).

___

? The only problem with this notational system is that there will need to 
be countably infinitely many separate digits, one for each iZ (where "Z" 
denotes the set of all integers); presently, there are only two: "0" and 
"i" (which means 1*i). But this representational base is selected for 
demonstration purposes only.


## 2017-03-31T21:51:46Z — krtisfranks (comment 3184, on definition 1697, in reply to 3183)

Re: Issue

Sorry for the formatting errors. I think that must of it is readable if you
realize that the final section is a footnote for the discussion about a 
generalized decimal system with "i" as a digit.

For everything else, pay little attention to the "?"'s and formatting, 
close quotation marks when it seems appropriate, etc. Some of the links do 
not seem to work when they should. When in doubt, click "reply" on the 
comment and see how what it is in the slightly more raw version.

Again, sorry.

